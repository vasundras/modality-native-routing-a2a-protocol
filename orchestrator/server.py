"""Task Orchestrator Server.

The main entry point for cross-modal customer service tasks. Decomposes tasks,
orchestrates parallel execution via MAR, and synthesizes final results.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from task_decomposer import TaskDecomposer, TaskType
from execution_engine import ExecutionEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Task Orchestrator", version="1.0.0")

CONFIG_PATH = Path(__file__).parent.parent / "configs" / "api_mode.yaml"

# Global components
task_decomposer: Optional[TaskDecomposer] = None
execution_engine: Optional[ExecutionEngine] = None


def load_config() -> dict:
    """Load orchestrator configuration."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            config = yaml.safe_load(f)
        return config.get("orchestrator", {})
    return {"port": 8084, "max_parallel_subtasks": 3, "timeout_seconds": 30}


class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[dict] = None
    id: Optional[str | int] = None


@app.on_event("startup")
async def startup_event():
    """Initialize orchestrator components."""
    global task_decomposer, execution_engine
    
    config = load_config()
    
    # Initialize components
    task_decomposer = TaskDecomposer()
    execution_engine = ExecutionEngine(
        mar_url="http://localhost:8080",
        max_parallel=config.get("max_parallel_subtasks", 3),
        timeout_seconds=config.get("timeout_seconds", 30)
    )
    
    logger.info(f"Orchestrator initialized with max_parallel={config.get('max_parallel_subtasks', 3)}")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources."""
    if execution_engine:
        await execution_engine.close()


async def handle_tasks_send(params: dict) -> dict:
    """Handle tasks/send by orchestrating cross-modal task execution."""
    task_id = params.get("id", str(uuid.uuid4()))
    message = params.get("message", {})
    metadata = params.get("metadata", {})
    
    logger.info(f"Orchestrating task {task_id}")
    
    try:
        # Extract task context from metadata
        context = {}
        if "benchmark" in metadata:
            # Benchmark task with known category
            context["category"] = metadata["benchmark"].get("category")
        
        # Decompose task into sub-tasks
        task_plan = task_decomposer.decompose_task(task_id, message, context)
        
        logger.info(f"Task {task_id} decomposed into {len(task_plan.sub_tasks)} subtasks, "
                   f"estimated duration: {task_plan.estimated_duration_seconds:.1f}s")
        
        # Execute the task plan
        execution_context = await execution_engine.execute_task(task_plan)
        
        # Synthesize final result
        final_result = execution_engine.synthesize_final_result(execution_context)
        
        # Add orchestration metadata
        final_result["metadata"] = final_result.get("metadata", {})
        final_result["metadata"].setdefault("orchestrator", {})["task_plan"] = {
            "task_type": task_plan.task_type.value,
            "subtasks_planned": len(task_plan.sub_tasks),
            "execution_groups": len(task_plan.execution_order),
            "estimated_duration": task_plan.estimated_duration_seconds,
            "actual_duration": execution_context.duration_seconds
        }
        
        logger.info(f"Task {task_id} orchestration completed in {execution_context.duration_seconds:.2f}s")
        
        return final_result
    
    except Exception as e:
        logger.exception(f"Orchestration failed for task {task_id}: {e}")
        
        # Return error result
        return {
            "id": task_id,
            "status": {
                "state": "failed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": {
                    "role": "orchestrator",
                    "parts": [{
                        "type": "text",
                        "text": f"Task orchestration failed: {str(e)}"
                    }]
                }
            },
            "metadata": {
                "orchestrator": {
                    "task_id": task_id,
                    "error": str(e),
                    "status": "failed"
                }
            }
        }


@app.post("/")
async def handle_jsonrpc(request: Request):
    """Main JSON-RPC 2.0 endpoint."""
    try:
        body = await request.json()
        rpc_request = JSONRPCRequest(**body)
        
        logger.info(f"Received request: {rpc_request.method}")
        
        method = rpc_request.method
        params = rpc_request.params or {}
        
        if method == "tasks/send":
            # Orchestrate cross-modal task
            result = await handle_tasks_send(params)
            
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "result": result,
                "id": rpc_request.id
            })
        
        elif method == "tasks/get":
            # Get task status
            task_id = params.get("id")
            if not task_id:
                raise ValueError("Task ID required for tasks/get")
            
            status = execution_engine.get_execution_status(task_id)
            if not status:
                raise ValueError(f"Task not found: {task_id}")
            
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "result": status,
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
    config = load_config()
    
    return {
        "status": "healthy",
        "service": "Task Orchestrator",
        "version": "1.0.0",
        "config": {
            "max_parallel_subtasks": config.get("max_parallel_subtasks", 3),
            "timeout_seconds": config.get("timeout_seconds", 30),
            "mar_url": "http://localhost:8080"
        },
        "components": {
            "task_decomposer": task_decomposer is not None,
            "execution_engine": execution_engine is not None
        }
    }


@app.get("/task-types")
async def list_task_types():
    """List supported task types."""
    return {
        "task_types": [
            {
                "name": task_type.value,
                "description": _get_task_type_description(task_type)
            }
            for task_type in TaskType
        ]
    }


def _get_task_type_description(task_type: TaskType) -> str:
    """Get description for a task type."""
    descriptions = {
        TaskType.PRODUCT_DEFECT_REPORT: "Customer reporting product defects or damage",
        TaskType.ASSEMBLY_GUIDANCE: "Customer needing help with product assembly",
        TaskType.VISUAL_TROUBLESHOOTING: "Customer troubleshooting issues with visual evidence",
        TaskType.WARRANTY_CLAIM: "Customer making warranty or return claims"
    }
    return descriptions.get(task_type, "Unknown task type")


@app.post("/decompose")
async def decompose_task_endpoint(request: Request):
    """Endpoint to decompose a task without executing it (for testing)."""
    try:
        body = await request.json()
        task_id = body.get("task_id", str(uuid.uuid4()))
        message = body.get("message", {})
        context = body.get("context", {})
        
        if not task_decomposer:
            raise ValueError("Task decomposer not initialized")
        
        task_plan = task_decomposer.decompose_task(task_id, message, context)
        
        return {
            "task_id": task_plan.task_id,
            "task_type": task_plan.task_type.value,
            "estimated_duration_seconds": task_plan.estimated_duration_seconds,
            "subtasks": [
                {
                    "id": st.id,
                    "type": st.type.value,
                    "target_agent": st.target_agent,
                    "dependencies": st.dependencies,
                    "priority": st.priority,
                    "timeout_seconds": st.timeout_seconds
                }
                for st in task_plan.sub_tasks
            ],
            "execution_order": task_plan.execution_order
        }
    
    except Exception as e:
        logger.exception("Error decomposing task")
        return JSONResponse(content={"error": str(e)}, status_code=400)


if __name__ == "__main__":
    import uvicorn
    config = load_config()
    port = config.get("port", 8084)
    uvicorn.run(app, host="0.0.0.0", port=port)