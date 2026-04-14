"""Voice Agent A2A Server.

A2A-compliant agent that processes audio files using Whisper for transcription
and provides sentiment analysis. Exposes JSON-RPC 2.0 endpoints and Agent Card.
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

from whisper_processor import WhisperProcessor, create_processor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockWhisperProcessor:
    """Mock processor for testing when API keys are not available."""
    
    def transcribe_audio(self, audio_data: bytes, mime_type: str) -> tuple[str, dict]:
        """Mock transcription that simulates realistic customer service scenarios."""
        # Simulate different transcripts based on audio length
        audio_length = len(audio_data)
        
        mock_transcripts = [
            "I dropped my BlenderMax 3000 and now it's making a grinding noise. The blade assembly looks bent.",
            "I just unboxed this coffee maker and the carafe has a crack in it right out of the box.",
            "My toaster has been sparking inside when I use it. I've only had it for two weeks.",
            "I'm on step 4 where it says to attach the crossbar but I can't figure out which screw to use.",
            "My vacuum suction has completely died. I've cleaned the filter and replaced the bag.",
            "The glass door on my microwave cracked while I was just standing there.",
        ]
        
        # Select transcript based on audio size (deterministic for testing)
        transcript_idx = (audio_length // 1000) % len(mock_transcripts)
        transcript = mock_transcripts[transcript_idx]
        
        metadata = {
            "language": "en",
            "duration": max(1.0, audio_length / 16000),  # Estimate duration
            "confidence": 0.85,
            "word_count": len(transcript.split()),
            "backend": "mock",
            "model": "mock-whisper"
        }
        
        return transcript, metadata
    
    def analyze_sentiment(self, transcript: str, metadata: dict) -> dict:
        """Use the real sentiment analysis logic."""
        # Create a real processor instance just for sentiment analysis
        real_processor = WhisperProcessor.__new__(WhisperProcessor)
        return real_processor.analyze_sentiment(transcript, metadata)

app = FastAPI(title="VoiceAgent", version="1.0.0")

AGENT_CARD_PATH = Path(__file__).parent / "agent_card.json"
CONFIG_PATH = Path(__file__).parent.parent.parent / "configs" / "api_mode.yaml"

# Global processor instance
processor: Optional[WhisperProcessor] = None
tasks_store: dict[str, dict] = {}


def load_config() -> dict:
    """Load configuration from YAML file."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            config = yaml.safe_load(f)
        return config.get("agents", {}).get("voice", {})
    return {"backend": "openai", "model": "whisper-1"}


def initialize_processor():
    """Initialize the Whisper processor."""
    global processor
    config = load_config()
    try:
        processor = create_processor(config)
        logger.info(f"Initialized processor: {config.get('backend', 'openai')}")
    except Exception as e:
        logger.error(f"Failed to initialize processor: {e}")
        logger.info("Running in mock mode - will simulate transcription")
        # Create a mock processor for testing
        processor = MockWhisperProcessor()


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


def extract_audio_from_message(message: Message) -> Optional[tuple[bytes, str]]:
    """Extract audio data from message parts.
    
    Returns:
        Tuple of (audio_bytes, mime_type) or None if no audio found
    """
    for part in message.parts:
        if part.get("type") == "file":
            mime_type = part.get("mimeType", "")
            if mime_type.startswith("audio/"):
                # Get audio data from base64 encoded data field
                data = part.get("data")
                if data:
                    try:
                        audio_bytes = base64.b64decode(data)
                        return audio_bytes, mime_type
                    except Exception as e:
                        logger.error(f"Failed to decode base64 audio data: {e}")
                        return None
                
                # TODO: Handle URI-based audio files if needed
                uri = part.get("uri")
                if uri:
                    logger.warning(f"URI-based audio not yet supported: {uri}")
                    return None
    
    return None


def process_audio(audio_data: bytes, mime_type: str) -> str:
    """Process audio data and return formatted analysis."""
    if not processor:
        return "Error: Audio processor not initialized"
    
    try:
        # Transcribe audio
        transcript, metadata = processor.transcribe_audio(audio_data, mime_type)
        
        if not transcript:
            error_msg = metadata.get("error", "Unknown transcription error")
            return f"Transcription failed: {error_msg}"
        
        # Analyze sentiment
        sentiment_analysis = processor.analyze_sentiment(transcript, metadata)
        
        # Format response
        response_parts = [
            "=== VOICE ANALYSIS ===",
            f"Transcript: {transcript}",
            "",
            "=== TECHNICAL METADATA ===",
            f"Language: {metadata.get('language', 'unknown')}",
            f"Duration: {metadata.get('duration', 'unknown')}s",
            f"Confidence: {metadata.get('confidence', 0):.2f}",
            f"Word Count: {metadata.get('word_count', 0)}",
            f"Backend: {metadata.get('backend', 'unknown')}",
            "",
            "=== SENTIMENT ANALYSIS ===",
            f"Overall Sentiment: {sentiment_analysis['sentiment'].upper()}",
            f"Confidence: {sentiment_analysis['confidence']:.2f}",
            f"Sentiment Score: {sentiment_analysis['score']:.2f}",
        ]
        
        if sentiment_analysis.get('urgency_detected'):
            response_parts.append("⚠️  URGENCY DETECTED - Customer needs immediate attention")
        
        if sentiment_analysis.get('frustration_detected'):
            response_parts.append("😤 FRUSTRATION DETECTED - Customer may need extra care")
        
        if sentiment_analysis['indicators']:
            response_parts.extend([
                "",
                "Indicators:",
                *[f"  • {indicator}" for indicator in sentiment_analysis['indicators']]
            ])
        
        return "\n".join(response_parts)
    
    except Exception as e:
        logger.exception("Error processing audio")
        return f"Audio processing failed: {str(e)}"


async def handle_task_send(params: dict) -> dict:
    """Handle the tasks/send method."""
    task_id = params.get("id", str(uuid.uuid4()))
    message = params.get("message", {})
    session_id = params.get("sessionId", str(uuid.uuid4()))
    metadata = params.get("metadata", {})
    
    logger.info(f"Processing voice task {task_id}")
    
    # Extract audio from message
    audio_result = extract_audio_from_message(Message(**message))
    if not audio_result:
        response_text = "Error: No audio data found in message. Expected FilePart with audio/* MIME type."
    else:
        audio_data, mime_type = audio_result
        logger.info(f"Processing {len(audio_data)} bytes of {mime_type} audio")
        response_text = process_audio(audio_data, mime_type)
    
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
            "name": "voice_analysis",
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
    
    logger.info(f"Streaming voice task {task_id}")
    
    now = datetime.now(timezone.utc).isoformat()
    yield f"data: {json.dumps({'type': 'status', 'status': {'state': 'working', 'timestamp': now}})}\n\n"
    
    # Extract and process audio
    audio_result = extract_audio_from_message(Message(**message))
    if not audio_result:
        response_text = "Error: No audio data found in message."
    else:
        audio_data, mime_type = audio_result
        
        # Stream processing status
        yield f"data: {json.dumps({'type': 'status', 'status': {'state': 'working', 'timestamp': now, 'message': 'Transcribing audio input'}})}\n\n"
        await asyncio.sleep(0.1)
        
        response_text = process_audio(audio_data, mime_type)
    
    # Stream response in chunks
    chunk_size = 100
    for i in range(0, len(response_text), chunk_size):
        chunk = response_text[i:i + chunk_size]
        yield f"data: {json.dumps({'type': 'artifact', 'artifact': {'index': 0, 'name': 'voice_analysis', 'parts': [{'type': 'text', 'text': chunk}], 'append': i > 0}})}\n\n"
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
        "artifacts": [{"index": 0, "name": "voice_analysis", "parts": [{"type": "text", "text": response_text}]}]
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
        "agent": "VoiceAgent", 
        "version": "1.0.0",
        "processor_ready": processor is not None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)