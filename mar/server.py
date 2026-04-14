"""Modality-Aware Router (MAR) Server.

The core routing proxy that implements MMA2A routing logic. Intercepts tasks/send
calls and routes message parts based on destination agent capabilities.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import yaml
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent_registry import AgentRegistry
from routing_engine import RoutingEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MMA2A Router", version="1.0.0")

CONFIG_PATH = Path(__file__).parent.parent / "configs" / "api_mode.yaml"

# Global components
agent_registry: Optional[AgentRegistry] = None
routing_engine: Optional[RoutingEngine] = None
http_client: Optional[httpx.AsyncClient] = None


def load_config() -> dict:
    """Load MAR configuration."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            config = yaml.safe_load(f)
        return config.get("mar", {})
    return {"port": 8080, "agent_card_cache_ttl_seconds": 60, "force_text_mode": False}


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


@app.on_event("startup")
async def startup_event():
    """Initialize MAR components."""
    global agent_registry, routing_engine, http_client
    
    config = load_config()
    
    # Initialize components
    agent_registry = AgentRegistry(cache_ttl_seconds=config.get("agent_card_cache_ttl_seconds", 60))
    routing_engine = RoutingEngine(agent_registry, force_text_mode=config.get("force_text_mode", False))
    http_client = httpx.AsyncClient(timeout=30.0)
    
    # Discover agents
    await agent_registry.discover_agents()
    
    logger.info(f"MAR initialized with force_text_mode={config.get('force_text_mode', False)}")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources."""
    if agent_registry:
        await agent_registry.close()
    if http_client:
        await http_client.aclose()


async def route_to_agent(agent_name: str, method: str, params: dict) -> dict:
    """Route a JSON-RPC call to a specific agent."""
    agent_info = await agent_registry.get_agent(agent_name)
    if not agent_info:
        raise ValueError(f"Agent not found: {agent_name}")
    
    # Prepare JSON-RPC request
    rpc_request = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": str(uuid.uuid4())
    }
    
    # Send to agent
    try:
        response = await http_client.post(
            agent_info.url,
            json=rpc_request,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        result = response.json()
        
        # Extract result from JSON-RPC response
        if "result" in result:
            return result["result"]
        elif "error" in result:
            raise Exception(f"Agent error: {result['error']}")
        else:
            raise Exception("Invalid JSON-RPC response")
    
    except Exception as e:
        logger.error(f"Failed to route to agent {agent_name}: {e}")
        raise


async def handle_tasks_send(params: dict) -> dict:
    """Handle tasks/send with MMA2A routing logic."""
    # Extract message and determine target agent
    message = params.get("message", {})
    task_id = params.get("id", str(uuid.uuid4()))
    
    # For demo, route based on message content analysis
    # In production, this would be specified by the orchestrator
    target_agent = await determine_target_agent(message)
    
    logger.info(f"Routing task {task_id} to {target_agent}")
    
    # Apply MMA2A routing
    routed_message, routing_decisions = await routing_engine.route_message(message, target_agent)
    
    # Log routing decisions
    for decision in routing_decisions:
        logger.info(f"Routing decision: {decision.to_dict()}")
    
    # Update params with routed message
    routed_params = {
        **params,
        "message": routed_message,
        "metadata": {
            **params.get("metadata", {}),
            "mar_routing": {
                "target_agent": target_agent,
                "routing_decisions": [d.to_dict() for d in routing_decisions],
                "force_text_mode": routing_engine.force_text_mode
            }
        }
    }
    
    # Forward to target agent
    result = await route_to_agent(target_agent, "tasks/send", routed_params)
    
    # Add routing metadata to result
    if isinstance(result, dict) and "metadata" in result:
        result["metadata"]["mar_routing"] = routed_params["metadata"]["mar_routing"]
    
    return result


async def determine_target_agent(message: dict) -> str:
    """Determine target agent based on message content.
    
    In production, this would be handled by the orchestrator.
    For demo, we use simple heuristics.
    """
    parts = message.get("parts", [])
    
    # Check for text content to determine intent
    text_content = ""
    has_voice = False
    has_image = False
    
    for part in parts:
        if part.get("type") == "text":
            text_content += " " + part.get("text", "")
        elif part.get("type") == "file":
            mime_type = part.get("mimeType", "")
            if mime_type.startswith("audio/"):
                has_voice = True
            elif mime_type.startswith("image/"):
                has_image = True
    
    text_lower = text_content.lower()
    
    # Route based on content and modalities
    if has_voice and ("transcribe" in text_lower or "audio" in text_lower or "voice" in text_lower):
        return "voice_agent"
    elif has_image and ("analyze" in text_lower or "image" in text_lower or "photo" in text_lower or "defect" in text_lower):
        return "vision_agent"
    elif any(keyword in text_lower for keyword in ["warranty", "product", "sku", "troubleshoot", "assembly"]):
        return "text_agent"
    else:
        # Default routing based on primary modality
        if has_voice:
            return "voice_agent"
        elif has_image:
            return "vision_agent"
        else:
            return "text_agent"


@app.post("/")
async def handle_jsonrpc(request: Request):
    """Main JSON-RPC 2.0 endpoint with routing logic."""
    try:
        body = await request.json()
        rpc_request = JSONRPCRequest(**body)
        
        logger.info(f"Received request: {rpc_request.method}")
        
        method = rpc_request.method
        params = rpc_request.params or {}
        
        if method == "tasks/send":
            # Apply MMA2A routing
            result = await handle_tasks_send(params)
            
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "result": result,
                "id": rpc_request.id
            })
        
        elif method in ["tasks/get", "tasks/cancel", "tasks/sendSubscribe"]:
            # These methods need to be routed to the appropriate agent
            # For now, we'll need additional logic to track which agent handled which task
            # This is a simplification - production would need task tracking
            
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "error": {
                    "code": -32601,
                    "message": f"Method {method} requires task tracking (not implemented in demo)"
                },
                "id": rpc_request.id
            }, status_code=200)
        
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
    registry_status = agent_registry.get_registry_status() if agent_registry else {"error": "not initialized"}
    routing_stats = routing_engine.get_routing_stats() if routing_engine else {"error": "not initialized"}
    
    return {
        "status": "healthy",
        "service": "MMA2A Router",
        "version": "1.0.0",
        "agent_registry": registry_status,
        "routing_engine": routing_stats
    }


@app.get("/agents")
async def list_agents():
    """List all registered agents and their capabilities."""
    if not agent_registry:
        return {"error": "Agent registry not initialized"}
    
    return agent_registry.get_registry_status()


@app.get("/routing-stats")
async def get_routing_stats():
    """Get routing engine statistics."""
    if not routing_engine:
        return {"error": "Routing engine not initialized"}
    
    return routing_engine.get_routing_stats()


@app.post("/force-text-mode")
async def toggle_force_text_mode(enable: bool = True):
    """Toggle force text mode for Text-BN baseline simulation."""
    if not routing_engine:
        return {"error": "Routing engine not initialized"}
    
    routing_engine.force_text_mode = enable
    
    return {
        "force_text_mode": enable,
        "message": f"Text-BN baseline mode {'enabled' if enable else 'disabled'}"
    }


if __name__ == "__main__":
    import uvicorn
    config = load_config()
    port = config.get("port", 8080)
    uvicorn.run(app, host="0.0.0.0", port=port)