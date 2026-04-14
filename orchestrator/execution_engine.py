"""Execution Engine for the Task Orchestrator.

Handles parallel execution of sub-tasks, result collection, and synthesis.
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

import httpx

from task_decomposer import SubTask, TaskPlan, SubTaskType

logger = logging.getLogger(__name__)


class SubTaskStatus(Enum):
    """Status of a sub-task execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class SubTaskResult:
    """Result of a sub-task execution."""
    subtask_id: str
    status: SubTaskStatus
    result: Optional[dict] = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    duration_seconds: Optional[float] = None
    
    def __post_init__(self):
        if self.start_time and self.end_time:
            self.duration_seconds = self.end_time - self.start_time


@dataclass
class ExecutionContext:
    """Context for task execution."""
    task_id: str
    plan: TaskPlan
    results: Dict[str, SubTaskResult] = field(default_factory=dict)
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    @property
    def duration_seconds(self) -> Optional[float]:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def is_complete(self) -> bool:
        """Check if all sub-tasks are complete."""
        for subtask in self.plan.sub_tasks:
            result = self.results.get(subtask.id)
            if not result or result.status not in [SubTaskStatus.COMPLETED, SubTaskStatus.FAILED]:
                return False
        return True
    
    @property
    def has_failures(self) -> bool:
        """Check if any sub-tasks failed."""
        return any(r.status == SubTaskStatus.FAILED for r in self.results.values())


class ExecutionEngine:
    """Executes task plans with parallel sub-task dispatch."""
    
    def __init__(self, mar_url: str = "http://localhost:8080", max_parallel: int = 3, timeout_seconds: int = 30):
        self.mar_url = mar_url
        self.max_parallel = max_parallel
        self.default_timeout = timeout_seconds
        self.client = httpx.AsyncClient(timeout=60.0)
        
        # Active executions
        self.executions: Dict[str, ExecutionContext] = {}
    
    async def execute_task(self, task_plan: TaskPlan) -> ExecutionContext:
        """Execute a task plan and return the execution context with results."""
        context = ExecutionContext(task_id=task_plan.task_id, plan=task_plan)
        context.start_time = time.time()
        
        self.executions[task_plan.task_id] = context
        
        try:
            logger.info(f"Starting execution of task {task_plan.task_id} with {len(task_plan.sub_tasks)} sub-tasks")
            
            # Execute sub-tasks according to execution order
            for group_idx, group in enumerate(task_plan.execution_order):
                logger.info(f"Executing group {group_idx + 1}: {group}")
                
                # Prepare sub-tasks for this group
                group_subtasks = []
                for subtask_id in group:
                    subtask = task_plan.get_subtask_by_id(subtask_id)
                    if subtask:
                        # Update subtask message with dependency results if needed
                        updated_subtask = await self._prepare_subtask_with_dependencies(subtask, context)
                        group_subtasks.append(updated_subtask)
                
                # Execute group in parallel (up to max_parallel limit)
                await self._execute_subtask_group(group_subtasks, context)
                
                # Check if we should continue (stop on critical failures)
                if self._should_stop_execution(context):
                    logger.warning(f"Stopping execution due to critical failures in task {task_plan.task_id}")
                    break
            
            context.end_time = time.time()
            logger.info(f"Completed execution of task {task_plan.task_id} in {context.duration_seconds:.2f}s")
            
        except Exception as e:
            logger.exception(f"Execution failed for task {task_plan.task_id}: {e}")
            context.end_time = time.time()
        
        return context
    
    async def _prepare_subtask_with_dependencies(self, subtask: SubTask, context: ExecutionContext) -> SubTask:
        """Prepare a sub-task by incorporating results from its dependencies."""
        if not subtask.dependencies or subtask.type != SubTaskType.FINAL_DECISION:
            return subtask

        # Collect results from dependency tasks
        dependency_results = []

        for dep_id in subtask.dependencies:
            dep_result = context.results.get(dep_id)
            if dep_result and dep_result.status == SubTaskStatus.COMPLETED and dep_result.result:
                # Extract the text response from the dependency result
                response_text = self._extract_response_text(dep_result.result)
                if response_text:
                    dependency_results.append(f"=== {dep_id.upper()} RESULT ===\n{response_text}")

        # Update the final decision message with dependency results
        if dependency_results:
            # Combine original synthesis prompt with dependency results
            original_parts = subtask.message.get("parts", [])
            synthesis_prompt = original_parts[0].get("text", "") if original_parts else ""
            
            combined_content = f"""{synthesis_prompt}

=== AVAILABLE INFORMATION ===
{chr(10).join(dependency_results)}

Based on the above information, provide your final recommendation and reasoning."""
            
            updated_message = {
                **subtask.message,
                "parts": [{"type": "text", "text": combined_content}]
            }
            
            # Create updated subtask
            return SubTask(
                id=subtask.id,
                type=subtask.type,
                target_agent=subtask.target_agent,
                message=updated_message,
                dependencies=subtask.dependencies,
                priority=subtask.priority,
                timeout_seconds=subtask.timeout_seconds
            )
        
        return subtask
    
    def _extract_response_text(self, result: dict) -> Optional[str]:
        """Extract text response from a task result."""
        try:
            # Try to get from status message
            status = result.get("status", {})
            message = status.get("message", {})
            parts = message.get("parts", [])
            
            for part in parts:
                if part.get("type") == "text":
                    return part.get("text", "")
            
            # Try to get from artifacts
            artifacts = result.get("artifacts", [])
            for artifact in artifacts:
                artifact_parts = artifact.get("parts", [])
                for part in artifact_parts:
                    if part.get("type") == "text":
                        return part.get("text", "")
            
            return None
        except Exception as e:
            logger.warning(f"Failed to extract response text: {e}")
            return None
    
    async def _execute_subtask_group(self, subtasks: List[SubTask], context: ExecutionContext) -> None:
        """Execute a group of sub-tasks in parallel."""
        # Limit parallelism
        semaphore = asyncio.Semaphore(self.max_parallel)
        
        # Create tasks for parallel execution
        async def execute_with_semaphore(subtask: SubTask) -> None:
            async with semaphore:
                await self._execute_single_subtask(subtask, context)
        
        # Execute all subtasks in the group concurrently
        await asyncio.gather(*[execute_with_semaphore(st) for st in subtasks], return_exceptions=True)
    
    async def _execute_single_subtask(self, subtask: SubTask, context: ExecutionContext) -> None:
        """Execute a single sub-task."""
        result = SubTaskResult(subtask_id=subtask.id, status=SubTaskStatus.PENDING)
        result.start_time = time.time()
        
        context.results[subtask.id] = result
        
        try:
            logger.info(f"Executing subtask {subtask.id} -> {subtask.target_agent}")
            result.status = SubTaskStatus.RUNNING
            
            # Prepare JSON-RPC request for MAR
            rpc_request = {
                "jsonrpc": "2.0",
                "method": "tasks/send",
                "params": {
                    "id": subtask.id,
                    "message": subtask.message,
                    "metadata": {
                        "orchestrator": {
                            "task_id": context.task_id,
                            "subtask_type": subtask.type.value,
                            "target_agent": subtask.target_agent
                        }
                    }
                },
                "id": str(uuid.uuid4())
            }
            
            # Execute with timeout
            timeout = subtask.timeout_seconds or self.default_timeout
            
            response = await asyncio.wait_for(
                self.client.post(self.mar_url, json=rpc_request),
                timeout=timeout
            )
            
            response.raise_for_status()
            rpc_result = response.json()
            
            if "result" in rpc_result:
                result.result = rpc_result["result"]
                result.status = SubTaskStatus.COMPLETED
                logger.info(f"Subtask {subtask.id} completed successfully")
            elif "error" in rpc_result:
                result.error = str(rpc_result["error"])
                result.status = SubTaskStatus.FAILED
                logger.error(f"Subtask {subtask.id} failed: {result.error}")
            else:
                result.error = "Invalid JSON-RPC response"
                result.status = SubTaskStatus.FAILED
                logger.error(f"Subtask {subtask.id} failed: {result.error}")
        
        except asyncio.TimeoutError:
            result.status = SubTaskStatus.TIMEOUT
            result.error = f"Timeout after {subtask.timeout_seconds or self.default_timeout}s"
            logger.error(f"Subtask {subtask.id} timed out")
        
        except Exception as e:
            result.status = SubTaskStatus.FAILED
            result.error = str(e)
            logger.exception(f"Subtask {subtask.id} failed with exception: {e}")
        
        finally:
            result.end_time = time.time()
    
    def _aggregate_mar_routing(self, context: ExecutionContext) -> dict:
        """Merge MAR routing metadata from every completed subtask (for evaluation metrics)."""
        all_decisions: list = []
        force_text: Optional[bool] = None
        targets: list = []
        for r in context.results.values():
            if r.status != SubTaskStatus.COMPLETED or not r.result:
                continue
            md = r.result.get("metadata") or {}
            mr = md.get("mar_routing")
            if not isinstance(mr, dict):
                continue
            all_decisions.extend(mr.get("routing_decisions", []))
            if mr.get("force_text_mode") is not None:
                force_text = mr.get("force_text_mode")
            if mr.get("target_agent"):
                targets.append(mr["target_agent"])
        return {
            "routing_decisions": all_decisions,
            "force_text_mode": force_text,
            "subtask_targets": targets,
            "aggregated": True,
        }

    def _should_stop_execution(self, context: ExecutionContext) -> bool:
        """Determine if execution should stop due to failures."""
        # For now, continue execution even with failures
        # In production, you might want to stop on critical failures
        return False
    
    def get_execution_status(self, task_id: str) -> Optional[dict]:
        """Get status of a task execution."""
        context = self.executions.get(task_id)
        if not context:
            return None
        
        return {
            "task_id": task_id,
            "status": "completed" if context.is_complete else "running",
            "start_time": context.start_time,
            "end_time": context.end_time,
            "duration_seconds": context.duration_seconds,
            "subtasks": {
                result.subtask_id: {
                    "status": result.status.value,
                    "duration_seconds": result.duration_seconds,
                    "error": result.error
                }
                for result in context.results.values()
            },
            "has_failures": context.has_failures
        }
    
    def synthesize_final_result(self, context: ExecutionContext) -> dict:
        """Synthesize the final result from all sub-task results."""
        # Find the final decision subtask result
        final_subtask = None
        for subtask in context.plan.sub_tasks:
            if subtask.type == SubTaskType.FINAL_DECISION:
                final_subtask = subtask
                break
        
        if final_subtask:
            final_result = context.results.get(final_subtask.id)
            if final_result and final_result.status == SubTaskStatus.COMPLETED and final_result.result:
                # Use the final decision result as the primary result
                synthesized_result = final_result.result.copy()
                
                # Add orchestration metadata
                synthesized_result["metadata"] = synthesized_result.get("metadata", {})
                synthesized_result["metadata"]["orchestrator"] = {
                    "task_id": context.task_id,
                    "task_type": context.plan.task_type.value,
                    "subtasks_executed": len(context.results),
                    "total_duration_seconds": context.duration_seconds,
                    "execution_summary": {
                        result.subtask_id: {
                            "status": result.status.value,
                            "duration": result.duration_seconds
                        }
                        for result in context.results.values()
                    }
                }
                # Aggregate MAR routing from all subtasks (benchmark metrics need full picture)
                agg = self._aggregate_mar_routing(context)
                if agg.get("routing_decisions"):
                    synthesized_result["metadata"]["mar_routing"] = agg
                
                return synthesized_result
        
        # Fallback: create a summary result if no final decision available
        return {
            "id": context.task_id,
            "status": {
                "state": "completed" if context.is_complete else "failed",
                "timestamp": time.time(),
                "message": {
                    "role": "orchestrator",
                    "parts": [{
                        "type": "text",
                        "text": f"Task execution {'completed' if context.is_complete else 'failed'}. "
                               f"Executed {len(context.results)} subtasks in {context.duration_seconds:.2f}s."
                    }]
                }
            },
            "metadata": {
                "orchestrator": {
                    "task_id": context.task_id,
                    "has_failures": context.has_failures,
                    "execution_summary": {
                        result.subtask_id: result.status.value
                        for result in context.results.values()
                    }
                }
            }
        }
    
    async def close(self):
        """Clean up resources."""
        await self.client.aclose()