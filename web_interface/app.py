"""MMA2A Web Interface

A user-friendly web interface for testing the MMA2A system with real multimodal inputs.
"""

import asyncio
import base64
import json
import logging
import uuid
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MMA2A Web Interface", version="1.0.0")

# Setup static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# MMA2A system URLs
ORCHESTRATOR_URL = "http://localhost:8084"
MAR_URL = "http://localhost:8080"

# HTTP client for API calls
client = httpx.AsyncClient(timeout=60.0)


@app.on_event("shutdown")
async def shutdown_event():
    await client.aclose()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Main page with multimodal task interface."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health_check():
    """Check health of all system components."""
    services = {
        "orchestrator": f"{ORCHESTRATOR_URL}/health",
        "mar": f"{MAR_URL}/health",
        "text_agent": "http://localhost:8001/health",
        "voice_agent": "http://localhost:8081/health",
        "vision_agent": "http://localhost:8082/health"
    }
    
    status = {}
    for name, url in services.items():
        try:
            response = await client.get(url, timeout=5.0)
            status[name] = {
                "healthy": response.status_code == 200,
                "url": url,
                "response": response.json() if response.status_code == 200 else None
            }
        except Exception as e:
            status[name] = {
                "healthy": False,
                "url": url,
                "error": str(e)
            }
    
    return status


@app.post("/submit-task")
async def submit_task(
    request: Request,
    text_input: str = Form(""),
    task_category: str = Form("product_defect_report"),
    routing_mode: str = Form("mma2a"),
    image_file: Optional[UploadFile] = File(None),
    audio_file: Optional[UploadFile] = File(None)
):
    """Submit a multimodal task to the MMA2A system."""
    
    try:
        # Set routing mode
        if routing_mode == "text_bn":
            await client.post(f"{MAR_URL}/force-text-mode?enable=true")
        else:
            await client.post(f"{MAR_URL}/force-text-mode?enable=false")
        
        # Build message parts
        parts = []
        
        # Add text part if provided
        if text_input.strip():
            parts.append({
                "type": "text",
                "text": text_input.strip()
            })
        
        # Add image part if uploaded
        if image_file and image_file.size > 0:
            image_content = await image_file.read()
            image_b64 = base64.b64encode(image_content).decode('ascii')
            
            # Determine MIME type
            mime_type = image_file.content_type or "image/png"
            if not mime_type.startswith("image/"):
                mime_type = "image/png"  # Default fallback
            
            parts.append({
                "type": "file",
                "mimeType": mime_type,
                "name": image_file.filename,
                "data": image_b64
            })
        
        # Add audio part if uploaded
        if audio_file and audio_file.size > 0:
            audio_content = await audio_file.read()
            audio_b64 = base64.b64encode(audio_content).decode('ascii')
            
            # Determine MIME type
            mime_type = audio_file.content_type or "audio/wav"
            if not mime_type.startswith("audio/"):
                mime_type = "audio/wav"  # Default fallback
            
            parts.append({
                "type": "file",
                "mimeType": mime_type,
                "name": audio_file.filename,
                "data": audio_b64
            })
        
        if not parts:
            raise HTTPException(status_code=400, detail="At least one input (text, image, or audio) is required")
        
        # Create task payload
        task_id = f"web_{uuid.uuid4().hex[:8]}"
        payload = {
            "jsonrpc": "2.0",
            "method": "tasks/send",
            "params": {
                "id": task_id,
                "message": {
                    "role": "user",
                    "parts": parts
                },
                "metadata": {
                    "benchmark": {"category": task_category},
                    "web_interface": {
                        "routing_mode": routing_mode,
                        "input_types": [part.get("type") for part in parts]
                    }
                }
            },
            "id": 1
        }
        
        # Submit to orchestrator
        logger.info(f"Submitting task {task_id} with {len(parts)} parts")
        response = await client.post(ORCHESTRATOR_URL, json=payload, timeout=60.0)
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Orchestrator request failed")
        
        result = response.json()
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=f"Task execution error: {result['error']}")
        
        return {
            "success": True,
            "task_id": task_id,
            "routing_mode": routing_mode,
            "result": result["result"]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error processing task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/system-status")
async def get_system_status():
    """Get detailed system status for the dashboard."""
    try:
        # Get MAR agent registry
        mar_response = await client.get(f"{MAR_URL}/agents", timeout=5.0)
        agent_registry = mar_response.json() if mar_response.status_code == 200 else {}
        
        # Get routing stats
        routing_response = await client.get(f"{MAR_URL}/routing-stats", timeout=5.0)
        routing_stats = routing_response.json() if routing_response.status_code == 200 else {}
        
        # Get orchestrator task types
        types_response = await client.get(f"{ORCHESTRATOR_URL}/task-types", timeout=5.0)
        task_types = types_response.json() if types_response.status_code == 200 else {}
        
        return {
            "agent_registry": agent_registry,
            "routing_stats": routing_stats,
            "task_types": task_types,
            "timestamp": asyncio.get_event_loop().time()
        }
    
    except Exception as e:
        logger.exception(f"Error getting system status: {e}")
        return {"error": str(e)}


@app.post("/toggle-routing-mode")
async def toggle_routing_mode(request: Request):
    """Toggle between MMA2A and Text-BN routing modes."""
    body = await request.json()
    enable_text_bn = body.get("enable_text_bn", False)
    
    try:
        response = await client.post(f"{MAR_URL}/force-text-mode?enable={str(enable_text_bn).lower()}")
        result = response.json() if response.status_code == 200 else {"error": "Failed to toggle mode"}
        
        return {
            "success": response.status_code == 200,
            "mode": "text_bn" if enable_text_bn else "mma2a",
            "result": result
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090)