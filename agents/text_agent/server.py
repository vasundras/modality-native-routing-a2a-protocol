"""Text Agent A2A Server.

A2A-compliant agent that processes text queries for customer service.
Exposes JSON-RPC 2.0 endpoints and Agent Card at /.well-known/agent-card.json.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from knowledge_base import (
    analyze_situation,
    format_product_info,
    format_troubleshooting,
    get_product_by_sku,
    search_products,
    search_troubleshooting,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="TextAgent", version="1.0.0")

AGENT_CARD_PATH = Path(__file__).parent / "agent_card.json"

tasks_store: dict[str, dict] = {}


class TextPart(BaseModel):
    type: str = "text"
    text: str


class FilePart(BaseModel):
    type: str = "file"
    mimeType: str
    name: Optional[str] = None
    uri: Optional[str] = None
    data: Optional[str] = None


class Message(BaseModel):
    role: str
    parts: list[dict]


class TaskSendParams(BaseModel):
    id: str
    message: Message
    sessionId: Optional[str] = None
    historyLength: Optional[int] = None
    metadata: Optional[dict] = None


class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[dict] = None
    id: Optional[str | int] = None


class JSONRPCResponse(BaseModel):
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[dict] = None
    id: Optional[str | int] = None


class TaskStatus(BaseModel):
    state: str
    timestamp: str
    message: Optional[Message] = None


class Task(BaseModel):
    id: str
    sessionId: str
    status: TaskStatus
    artifacts: list[dict] = Field(default_factory=list)
    history: list[Message] = Field(default_factory=list)
    metadata: Optional[dict] = None


@app.get("/.well-known/agent-card.json")
async def get_agent_card():
    """Serve the Agent Card as per A2A protocol."""
    with open(AGENT_CARD_PATH) as f:
        agent_card = json.load(f)
    return JSONResponse(content=agent_card)


def extract_text_from_message(message: Message) -> str:
    """Extract text content from message parts."""
    texts = []
    for part in message.parts:
        if part.get("type") == "text":
            texts.append(part.get("text", ""))
    return " ".join(texts)


def process_text_query(query: str) -> str:
    """Process a text query and return a response.
    
    This handles:
    - Product searches
    - Troubleshooting queries
    - Situation analysis for action recommendations
    """
    query_lower = query.lower()

    # Synthesis/final-decision prompts from the orchestrator contain dependency
    # results and should always go through situation analysis, not keyword routing.
    if "=== AVAILABLE INFORMATION ===" in query or "final recommendation" in query_lower:
        # Extract individual dependency sections for structured analysis
        voice_text = ""
        image_text = ""
        text_info = ""
        for section in query.split("==="):
            section_stripped = section.strip()
            section_lower = section_stripped.lower()
            if section_lower.startswith("voice") or section_lower.startswith("transcript"):
                voice_text = section_stripped
            elif section_lower.startswith("image") or section_lower.startswith("visual"):
                image_text = section_stripped
            elif section_lower.startswith("text") or "product:" in section_lower or "warranty:" in section_lower or "sku:" in section_lower:
                text_info = section_stripped

        # Also extract product/warranty info from the synthesis prompt itself
        # (the original text_context is embedded in the prompt)
        for line in query.split("\n"):
            if "exclusion" in line.lower() or "coverage:" in line.lower():
                text_info += "\n" + line

        analysis = analyze_situation(
            voice_transcript=voice_text or query,
            image_description=image_text,
            text_context=text_info,
        )
        return f"""Recommended Action: {analysis['recommended_action']}
Reasoning: {analysis['reasoning']}
Confidence: {analysis['confidence']:.0%}"""

    if "sku:" in query_lower:
        sku = query_lower.split("sku:")[-1].strip().split()[0].strip(".,;:!?").upper()
        product = get_product_by_sku(sku)
        if product:
            return format_product_info(product)
        return f"No product found with SKU: {sku}"
    
    if any(kw in query_lower for kw in ["warranty", "product info", "coverage", "return"]):
        query_words = [w.strip("?.,!") for w in query.split() if len(w.strip("?.,!")) > 3]
        non_generic_words = [w for w in query_words if w.lower() not in 
                           ("what", "warranty", "product", "info", "coverage", "return", 
                            "about", "tell", "does", "have", "that", "this", "with")]
        
        for word in non_generic_words:
            products = search_products(word)
            name_matches = [p for p in products if word.lower() in p.name.lower()]
            if name_matches:
                return "\n\n".join(format_product_info(p) for p in name_matches[:3])
            if products:
                return "\n\n".join(format_product_info(p) for p in products[:3])
    
    if any(kw in query_lower for kw in ["error", "troubleshoot", "fix", "not working", "problem"]):
        entries = search_troubleshooting(query)
        if entries:
            return "\n\n".join(format_troubleshooting(e) for e in entries[:2])
    
    if any(kw in query_lower for kw in ["recommend", "action", "should we", "what to do", "analyze"]):
        analysis = analyze_situation(voice_transcript=query)
        return f"""Recommended Action: {analysis['recommended_action']}
Reasoning: {analysis['reasoning']}
Confidence: {analysis['confidence']:.0%}"""
    
    products = search_products(query)
    if products:
        return "\n\n".join(format_product_info(p) for p in products[:2])
    
    entries = search_troubleshooting(query)
    if entries:
        return "\n\n".join(format_troubleshooting(e) for e in entries[:2])
    
    analysis = analyze_situation(voice_transcript=query)
    return f"""I processed your query: "{query[:100]}..."

Based on my analysis:
Recommended Action: {analysis['recommended_action']}
Reasoning: {analysis['reasoning']}
Confidence: {analysis['confidence']:.0%}

For more specific information, try:
- "SKU: <product-sku>" for product details
- Include "warranty" or "troubleshoot" in your query
- Describe the customer situation for action recommendations"""


async def handle_task_send(params: dict) -> dict:
    """Handle the tasks/send method."""
    task_id = params.get("id", str(uuid.uuid4()))
    message = params.get("message", {})
    session_id = params.get("sessionId", str(uuid.uuid4()))
    metadata = params.get("metadata", {})
    
    query = extract_text_from_message(Message(**message))
    logger.info(f"Processing task {task_id}: {query[:100]}...")
    
    response_text = process_text_query(query)
    
    now = datetime.now(timezone.utc).isoformat()
    
    response_message = Message(
        role="agent",
        parts=[{"type": "text", "text": response_text}]
    )
    
    task = Task(
        id=task_id,
        sessionId=session_id,
        status=TaskStatus(
            state="completed",
            timestamp=now,
            message=response_message
        ),
        artifacts=[{
            "index": 0,
            "name": "response",
            "parts": [{"type": "text", "text": response_text}]
        }],
        history=[Message(**message), response_message],
        metadata=metadata
    )
    
    tasks_store[task_id] = task.model_dump()
    
    return task.model_dump()


async def generate_sse_events(params: dict) -> AsyncGenerator[str, None]:
    """Generate SSE events for streaming response."""
    task_id = params.get("id", str(uuid.uuid4()))
    message = params.get("message", {})
    session_id = params.get("sessionId", str(uuid.uuid4()))
    
    query = extract_text_from_message(Message(**message))
    logger.info(f"Streaming task {task_id}: {query[:100]}...")
    
    now = datetime.now(timezone.utc).isoformat()
    yield f"data: {json.dumps({'type': 'status', 'status': {'state': 'working', 'timestamp': now}})}\n\n"
    
    await asyncio.sleep(0.1)
    
    response_text = process_text_query(query)
    
    chunk_size = 50
    for i in range(0, len(response_text), chunk_size):
        chunk = response_text[i:i + chunk_size]
        yield f"data: {json.dumps({'type': 'artifact', 'artifact': {'index': 0, 'name': 'response', 'parts': [{'type': 'text', 'text': chunk}], 'append': i > 0}})}\n\n"
        await asyncio.sleep(0.02)
    
    now = datetime.now(timezone.utc).isoformat()
    response_message = {"role": "agent", "parts": [{"type": "text", "text": response_text}]}
    
    task_result = {
        "id": task_id,
        "sessionId": session_id,
        "status": {
            "state": "completed",
            "timestamp": now,
            "message": response_message
        },
        "artifacts": [{"index": 0, "name": "response", "parts": [{"type": "text", "text": response_text}]}]
    }
    
    tasks_store[task_id] = task_result
    
    yield f"data: {json.dumps({'type': 'status', 'status': {'state': 'completed', 'timestamp': now, 'message': response_message}})}\n\n"
    yield "data: [DONE]\n\n"


async def handle_task_send_subscribe(params: dict) -> StreamingResponse:
    """Handle the tasks/sendSubscribe method with SSE streaming."""
    return StreamingResponse(
        generate_sse_events(params),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


async def handle_task_get(params: dict) -> dict:
    """Handle the tasks/get method."""
    task_id = params.get("id")
    if not task_id or task_id not in tasks_store:
        raise ValueError(f"Task not found: {task_id}")
    return tasks_store[task_id]


async def handle_task_cancel(params: dict) -> dict:
    """Handle the tasks/cancel method."""
    task_id = params.get("id")
    if task_id in tasks_store:
        tasks_store[task_id]["status"]["state"] = "cancelled"
        tasks_store[task_id]["status"]["timestamp"] = datetime.now(timezone.utc).isoformat()
    return {"id": task_id, "cancelled": True}


@app.post("/")
async def handle_jsonrpc(request: Request):
    """Main JSON-RPC 2.0 endpoint."""
    try:
        body = await request.json()
        rpc_request = JSONRPCRequest(**body)
        
        logger.info(f"Received JSON-RPC request: {rpc_request.method}")
        
        method = rpc_request.method
        params = rpc_request.params or {}
        
        if method == "tasks/send":
            result = await handle_task_send(params)
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "result": result,
                "id": rpc_request.id
            })
        
        elif method == "tasks/sendSubscribe":
            return await handle_task_send_subscribe(params)
        
        elif method == "tasks/get":
            result = await handle_task_get(params)
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "result": result,
                "id": rpc_request.id
            })
        
        elif method == "tasks/cancel":
            result = await handle_task_cancel(params)
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "result": result,
                "id": rpc_request.id
            })
        
        else:
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                },
                "id": rpc_request.id
            }, status_code=200)
    
    except Exception as e:
        logger.exception("Error processing request")
        return JSONResponse(content={
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": str(e)
            },
            "id": None
        }, status_code=200)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "agent": "TextAgent", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
