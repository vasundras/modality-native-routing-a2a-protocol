"""Vision Agent A2A Server.

A2A-compliant agent that processes images using multimodal AI for customer service
scenarios like defect detection and troubleshooting. Exposes JSON-RPC 2.0 endpoints.
"""

import asyncio
import base64
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

import yaml
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from vision_processor import VisionProcessor, create_processor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="VisionAgent", version="1.0.0")

AGENT_CARD_PATH = Path(__file__).parent / "agent_card.json"
CONFIG_PATH = Path(__file__).parent.parent.parent / "configs" / "api_mode.yaml"

# Global processor instance
processor: Optional[VisionProcessor] = None
tasks_store: dict[str, dict] = {}


def load_config() -> dict:
    """Load configuration from YAML file."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            config = yaml.safe_load(f)
        return config.get("agents", {}).get("vision", {})
    return {"backend": "openai", "model": "gpt-4o-mini"}


class MockVisionProcessor:
    """Mock processor for testing when API keys are not available."""
    
    def analyze_image(self, image_data: bytes, mime_type: str, context: str = "") -> tuple[str, dict]:
        """Mock image analysis that simulates realistic customer service scenarios."""
        # Simulate different analyses based on image size
        image_size = len(image_data)
        
        mock_analyses = [
            {
                "analysis": """**OVERALL CONDITION**: BlenderMax 3000 blender base unit with visible damage to the housing and blade assembly.

**DEFECTS/DAMAGE**: 
- Visible crack on the plastic housing near the motor base (approximately 2-inch hairline crack)
- Blade assembly appears bent and misaligned
- Scuff marks on the bottom indicating impact damage
- Motor housing shows stress marks around the crack

**ASSEMBLY STATUS**: Unit appears fully assembled but damaged from external force.

**ERROR INDICATORS**: No error displays visible, but physical damage prevents safe operation.

**WARRANTY ASSESSMENT**: This appears to be impact damage from dropping, which is typically excluded from warranty coverage. The crack pattern and blade deformation are consistent with drop damage rather than manufacturing defects.

**RECOMMENDED ACTION**: Deny warranty claim due to physical damage exclusion. Offer replacement parts (blade assembly $29, housing replacement if available) at customer cost.""",
                "defect_type": "physical_damage"
            },
            {
                "analysis": """**OVERALL CONDITION**: Coffee maker carafe with packaging materials still visible, indicating recent unboxing.

**DEFECTS/DAMAGE**: 
- Hairline crack visible near the handle attachment point
- Crack appears to run vertically for approximately 1 inch
- No impact points or external damage visible
- Glass appears to be tempered glass with stress failure pattern

**ASSEMBLY STATUS**: Product appears new and unused, still in original packaging context.

**ERROR INDICATORS**: No electronic components visible in this image.

**WARRANTY ASSESSMENT**: This appears to be a manufacturing defect or damage during shipping. The crack pattern suggests stress failure in tempered glass rather than impact damage. Product is clearly new/unused.

**RECOMMENDED ACTION**: Approve warranty replacement. This qualifies as DOA (Dead on Arrival) or manufacturing defect. Expedite replacement within 7-day window for new products.""",
                "defect_type": "manufacturing_defect"
            },
            {
                "analysis": """**OVERALL CONDITION**: Toaster interior showing heating elements with visible damage and burn marks.

**DEFECTS/DAMAGE**: 
- Blackened heating element with visible burn marks on crumb tray
- Electrical discoloration around heating element connections
- Possible carbon buildup indicating overheating or electrical arcing
- Interior walls show heat damage beyond normal use patterns

**ASSEMBLY STATUS**: Unit appears properly assembled but shows electrical failure.

**ERROR INDICATORS**: No digital display visible, but physical evidence of electrical malfunction.

**WARRANTY ASSESSMENT**: This appears to be an electrical defect causing overheating/arcing. This is a safety hazard and covered under electrical defects warranty.

**RECOMMENDED ACTION**: Immediate replacement required due to fire/electrical hazard. Flag for quality control review. Customer should discontinue use immediately.""",
                "defect_type": "electrical_hazard"
            },
            {
                "analysis": """**OVERALL CONDITION**: Router administration interface displayed on computer screen showing network status.

**DEFECTS/DAMAGE**: 
- No physical damage visible to router hardware
- Software interface shows connectivity issues

**ASSEMBLY STATUS**: Router appears properly connected and powered (status lights visible).

**ERROR INDICATORS**: 
- WAN Status: Disconnected (red indicator)
- LAN Status: Active (green indicator)  
- DNS: 0.0.0.0 (indicating DNS resolution failure)

**WARRANTY ASSESSMENT**: This appears to be a configuration or ISP connectivity issue rather than hardware defect.

**RECOMMENDED ACTION**: Provide troubleshooting steps: 1) Check physical cable connections, 2) Power cycle modem, 3) Contact ISP if issue persists. Not a warranty hardware issue.""",
                "defect_type": "configuration_issue"
            },
        ]
        
        # Select analysis based on image size (deterministic for testing)
        analysis_idx = (image_size // 1000) % len(mock_analyses)
        selected = mock_analyses[analysis_idx]
        
        metadata = {
            "model": "mock-vision",
            "backend": "mock",
            "image_format": mime_type.split("/")[-1],
            "image_size_bytes": image_size,
            "tokens_used": len(selected["analysis"]) // 4,  # Rough estimate
            "analysis_length": len(selected["analysis"]),
            "defect_type": selected["defect_type"]
        }
        
        return selected["analysis"], metadata
    
    def assess_warranty_eligibility(self, analysis: str) -> dict:
        """Use the real warranty assessment logic."""
        # Create a real processor instance just for warranty assessment
        real_processor = VisionProcessor.__new__(VisionProcessor)
        return real_processor.assess_warranty_eligibility(analysis)
    
    def extract_error_codes(self, analysis: str) -> list[str]:
        """Use the real error code extraction logic."""
        real_processor = VisionProcessor.__new__(VisionProcessor)
        return real_processor.extract_error_codes(analysis)


def initialize_processor():
    """Initialize the Vision processor."""
    global processor
    config = load_config()
    try:
        processor = create_processor(config)
        logger.info(f"Initialized processor: {config.get('backend', 'openai')}")
    except Exception as e:
        logger.error(f"Failed to initialize processor: {e}")
        logger.info("Running in mock mode - will simulate image analysis")
        processor = MockVisionProcessor()


class TextPart(BaseModel):
    type: str = "text"
    text: str


class FilePart(BaseModel):
    type: str = "file"
    mimeType: str
    name: Optional[str] = None
    uri: Optional[str] = None
    data: Optional[str] = None  # Base64 encoded data


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


@app.on_event("startup")
async def startup_event():
    """Initialize processor on startup."""
    initialize_processor()


@app.get("/.well-known/agent-card.json")
async def get_agent_card():
    """Serve the Agent Card as per A2A protocol."""
    with open(AGENT_CARD_PATH) as f:
        agent_card = json.load(f)
    return JSONResponse(content=agent_card)


def extract_image_from_message(message: Message) -> Optional[tuple[bytes, str, str]]:
    """Extract image data from message parts.
    
    Returns:
        Tuple of (image_bytes, mime_type, context) or None if no image found
    """
    image_data = None
    context_parts = []
    
    for part in message.parts:
        if part.get("type") == "file":
            mime_type = part.get("mimeType", "")
            if mime_type.startswith("image/"):
                # Get image data from base64 encoded data field
                data = part.get("data")
                if data:
                    try:
                        image_bytes = base64.b64decode(data)
                        image_data = (image_bytes, mime_type)
                    except Exception as e:
                        logger.error(f"Failed to decode base64 image data: {e}")
                        return None
                
                # TODO: Handle URI-based images if needed
                uri = part.get("uri")
                if uri and not image_data:
                    logger.warning(f"URI-based images not yet supported: {uri}")
                    return None
        
        elif part.get("type") == "text":
            # Collect text parts as context
            text = part.get("text", "")
            if text.strip():
                context_parts.append(text.strip())
    
    if image_data:
        context = " ".join(context_parts)
        return image_data[0], image_data[1], context
    
    return None


def process_image(image_data: bytes, mime_type: str, context: str = "") -> str:
    """Process image data and return formatted analysis."""
    if not processor:
        return "Error: Vision processor not initialized"
    
    try:
        # Analyze image
        analysis, metadata = processor.analyze_image(image_data, mime_type, context)
        
        if not analysis or "failed" in analysis.lower():
            error_msg = metadata.get("error", "Unknown analysis error")
            return f"Image analysis failed: {error_msg}"
        
        # Assess warranty eligibility
        warranty_assessment = processor.assess_warranty_eligibility(analysis)
        
        # Extract error codes
        error_codes = processor.extract_error_codes(analysis)
        
        # Format response
        response_parts = [
            "=== IMAGE ANALYSIS ===",
            analysis,
            "",
            "=== TECHNICAL METADATA ===",
            f"Model: {metadata.get('model', 'unknown')}",
            f"Backend: {metadata.get('backend', 'unknown')}",
            f"Image Format: {metadata.get('image_format', 'unknown')}",
            f"Image Size: {metadata.get('image_size_bytes', 0)} bytes",
            f"Tokens Used: {metadata.get('tokens_used', 0)}",
            "",
            "=== WARRANTY ASSESSMENT ===",
            f"Recommended Action: {warranty_assessment['recommended_action'].upper()}",
            f"Reasoning: {warranty_assessment['reasoning']}",
            f"Confidence: {warranty_assessment['confidence']:.2f}",
        ]
        
        # Add indicator details
        indicators = warranty_assessment.get('indicators', {})
        if any(indicators.values()):
            response_parts.extend([
                "",
                "Damage Indicators:",
                f"  • Manufacturing Defects: {indicators.get('manufacturing_defects', 0)}",
                f"  • User Damage: {indicators.get('user_damage', 0)}",
                f"  • Safety Issues: {indicators.get('safety_issues', 0)}",
                f"  • Assembly Issues: {indicators.get('assembly_issues', 0)}",
            ])
        
        # Add error codes if found
        if error_codes:
            response_parts.extend([
                "",
                f"Error Codes Detected: {', '.join(error_codes)}"
            ])
        
        # Add context if provided
        if context.strip():
            response_parts.extend([
                "",
                f"Context Provided: {context}"
            ])
        
        return "\n".join(response_parts)
    
    except Exception as e:
        logger.exception("Error processing image")
        return f"Image processing failed: {str(e)}"


async def handle_task_send(params: dict) -> dict:
    """Handle the tasks/send method."""
    task_id = params.get("id", str(uuid.uuid4()))
    message = params.get("message", {})
    session_id = params.get("sessionId", str(uuid.uuid4()))
    metadata = params.get("metadata", {})
    
    logger.info(f"Processing vision task {task_id}")
    
    # Extract image from message
    image_result = extract_image_from_message(Message(**message))
    if not image_result:
        response_text = "Error: No image data found in message. Expected FilePart with image/* MIME type."
    else:
        image_data, mime_type, context = image_result
        logger.info(f"Processing {len(image_data)} bytes of {mime_type} image")
        response_text = process_image(image_data, mime_type, context)
    
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
            "name": "image_analysis",
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
    
    logger.info(f"Streaming vision task {task_id}")
    
    now = datetime.now(timezone.utc).isoformat()
    yield f"data: {json.dumps({'type': 'status', 'status': {'state': 'working', 'timestamp': now}})}\n\n"
    
    # Extract and process image
    image_result = extract_image_from_message(Message(**message))
    if not image_result:
        response_text = "Error: No image data found in message."
    else:
        image_data, mime_type, context = image_result
        
        # Stream processing status
        yield f"data: {json.dumps({'type': 'status', 'status': {'state': 'working', 'timestamp': now, 'message': 'Analyzing image content'}})}\n\n"
        await asyncio.sleep(0.1)
        
        response_text = process_image(image_data, mime_type, context)
    
    # Stream response in chunks
    chunk_size = 150
    for i in range(0, len(response_text), chunk_size):
        chunk = response_text[i:i + chunk_size]
        yield f"data: {json.dumps({'type': 'artifact', 'artifact': {'index': 0, 'name': 'image_analysis', 'parts': [{'type': 'text', 'text': chunk}], 'append': i > 0}})}\n\n"
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
        "artifacts": [{"index": 0, "name": "image_analysis", "parts": [{"type": "text", "text": response_text}]}]
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
    return {
        "status": "healthy", 
        "agent": "VisionAgent", 
        "version": "1.0.0",
        "processor_ready": processor is not None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8082)