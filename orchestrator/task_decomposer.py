"""Task Decomposer for the Task Orchestrator.

Handles decomposition of cross-modal tasks into sub-tasks that can be
dispatched to appropriate agents via the MAR.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Types of customer service tasks."""
    PRODUCT_DEFECT_REPORT = "product_defect_report"
    ASSEMBLY_GUIDANCE = "assembly_guidance"
    VISUAL_TROUBLESHOOTING = "visual_troubleshooting"
    WARRANTY_CLAIM = "warranty_claim"


class SubTaskType(Enum):
    """Types of sub-tasks."""
    VOICE_TRANSCRIPTION = "voice_transcription"
    IMAGE_ANALYSIS = "image_analysis"
    TEXT_PROCESSING = "text_processing"
    FINAL_DECISION = "final_decision"


@dataclass
class SubTask:
    """Represents a sub-task to be executed by an agent."""
    id: str
    type: SubTaskType
    target_agent: str
    message: dict
    dependencies: List[str] = None  # IDs of sub-tasks this depends on
    priority: int = 1  # Higher number = higher priority
    timeout_seconds: Optional[int] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class TaskPlan:
    """Represents a decomposed task with sub-tasks and execution plan."""
    task_id: str
    task_type: TaskType
    sub_tasks: List[SubTask]
    execution_order: List[List[str]]  # List of parallel execution groups
    estimated_duration_seconds: float
    
    def get_subtask_by_id(self, subtask_id: str) -> Optional[SubTask]:
        """Get a sub-task by ID."""
        for subtask in self.sub_tasks:
            if subtask.id == subtask_id:
                return subtask
        return None


class TaskDecomposer:
    """Decomposes cross-modal tasks into executable sub-tasks."""
    
    def __init__(self):
        # Agent preferences for different modalities
        self.agent_preferences = {
            "voice": "voice_agent",
            "image": "vision_agent", 
            "text": "text_agent"
        }
    
    def decompose_task(self, task_id: str, message: dict, context: dict = None) -> TaskPlan:
        """Decompose a task into sub-tasks based on message content and modalities.
        
        Args:
            task_id: Unique task identifier
            message: The A2A message with parts
            context: Optional context about the task (category, etc.)
        
        Returns:
            TaskPlan with sub-tasks and execution order
        """
        # Analyze message to determine task type and required processing
        task_type = self._determine_task_type(message, context)
        modalities = self._analyze_modalities(message)
        
        logger.info(f"Decomposing task {task_id}: type={task_type.value}, modalities={modalities}")
        
        # Create sub-tasks based on modalities and task type
        sub_tasks = []
        
        # Phase 1: Process individual modalities in parallel
        voice_subtask_id = None
        image_subtask_id = None
        text_subtask_id = None
        
        if "voice" in modalities:
            voice_subtask_id = f"{task_id}_voice"
            voice_subtask = self._create_voice_subtask(voice_subtask_id, message, modalities["voice"])
            sub_tasks.append(voice_subtask)
        
        if "image" in modalities:
            image_subtask_id = f"{task_id}_image"
            image_subtask = self._create_image_subtask(image_subtask_id, message, modalities["image"])
            sub_tasks.append(image_subtask)
        
        if "text" in modalities:
            text_subtask_id = f"{task_id}_text"
            text_subtask = self._create_text_subtask(text_subtask_id, message, modalities["text"])
            sub_tasks.append(text_subtask)
        
        # Phase 2: Final decision/synthesis task
        final_subtask_id = f"{task_id}_final"
        dependencies = [sid for sid in [voice_subtask_id, image_subtask_id, text_subtask_id] if sid]
        
        final_subtask = self._create_final_decision_subtask(
            final_subtask_id, task_type, message, dependencies
        )
        sub_tasks.append(final_subtask)
        
        # Create execution plan
        execution_order = self._create_execution_order(sub_tasks)
        
        # Estimate duration
        estimated_duration = self._estimate_duration(sub_tasks, execution_order)
        
        return TaskPlan(
            task_id=task_id,
            task_type=task_type,
            sub_tasks=sub_tasks,
            execution_order=execution_order,
            estimated_duration_seconds=estimated_duration
        )
    
    def _determine_task_type(self, message: dict, context: dict = None) -> TaskType:
        """Determine the type of customer service task."""
        if context and "category" in context:
            category = context["category"]
            if category in [t.value for t in TaskType]:
                return TaskType(category)
        
        # Analyze message content for task type indicators
        text_content = self._extract_text_content(message)
        text_lower = text_content.lower()
        
        # Keywords for different task types
        if any(word in text_lower for word in ["defect", "broken", "damage", "crack", "bent"]):
            return TaskType.PRODUCT_DEFECT_REPORT
        elif any(word in text_lower for word in ["assembly", "step", "instruction", "screw", "attach"]):
            return TaskType.ASSEMBLY_GUIDANCE
        elif any(word in text_lower for word in ["error", "troubleshoot", "not working", "problem", "fix"]):
            return TaskType.VISUAL_TROUBLESHOOTING
        elif any(word in text_lower for word in ["warranty", "claim", "replace", "return", "refund"]):
            return TaskType.WARRANTY_CLAIM
        else:
            # Default based on modalities present
            modalities = self._analyze_modalities(message)
            if "image" in modalities:
                return TaskType.VISUAL_TROUBLESHOOTING
            else:
                return TaskType.WARRANTY_CLAIM
    
    def _analyze_modalities(self, message: dict) -> Dict[str, List[dict]]:
        """Analyze message parts to identify modalities."""
        modalities = {}
        
        for part in message.get("parts", []):
            if part.get("type") == "text":
                if "text" not in modalities:
                    modalities["text"] = []
                modalities["text"].append(part)
            elif part.get("type") == "file":
                mime_type = part.get("mimeType", "")
                if mime_type.startswith("audio/"):
                    if "voice" not in modalities:
                        modalities["voice"] = []
                    modalities["voice"].append(part)
                elif mime_type.startswith("image/"):
                    if "image" not in modalities:
                        modalities["image"] = []
                    modalities["image"].append(part)
        
        return modalities
    
    def _extract_text_content(self, message: dict) -> str:
        """Extract all text content from message."""
        text_parts = []
        for part in message.get("parts", []):
            if part.get("type") == "text":
                text_parts.append(part.get("text", ""))
        return " ".join(text_parts)
    
    def _create_voice_subtask(self, subtask_id: str, original_message: dict, voice_parts: List[dict]) -> SubTask:
        """Create a voice processing sub-task."""
        # Create message with only voice parts
        voice_message = {
            "role": "user",
            "parts": voice_parts
        }
        
        return SubTask(
            id=subtask_id,
            type=SubTaskType.VOICE_TRANSCRIPTION,
            target_agent=self.agent_preferences["voice"],
            message=voice_message,
            priority=2,  # High priority for voice (often contains urgency)
            timeout_seconds=15
        )
    
    def _create_image_subtask(self, subtask_id: str, original_message: dict, image_parts: List[dict]) -> SubTask:
        """Create an image analysis sub-task."""
        # Add text context if available
        text_content = self._extract_text_content(original_message)
        parts = image_parts.copy()
        
        if text_content.strip():
            parts.insert(0, {"type": "text", "text": f"Context: {text_content}"})
        
        image_message = {
            "role": "user",
            "parts": parts
        }
        
        return SubTask(
            id=subtask_id,
            type=SubTaskType.IMAGE_ANALYSIS,
            target_agent=self.agent_preferences["image"],
            message=image_message,
            priority=2,  # High priority for images (visual evidence)
            timeout_seconds=20
        )
    
    def _create_text_subtask(self, subtask_id: str, original_message: dict, text_parts: List[dict]) -> SubTask:
        """Create a text processing sub-task."""
        text_message = {
            "role": "user",
            "parts": text_parts
        }
        
        return SubTask(
            id=subtask_id,
            type=SubTaskType.TEXT_PROCESSING,
            target_agent=self.agent_preferences["text"],
            message=text_message,
            priority=1,  # Lower priority (can be processed after others)
            timeout_seconds=10
        )
    
    def _create_final_decision_subtask(self, subtask_id: str, task_type: TaskType, 
                                     original_message: dict, dependencies: List[str]) -> SubTask:
        """Create final decision synthesis sub-task."""
        # The final task will be sent to text agent with synthesized context
        # This will be populated with results from dependency tasks during execution
        
        synthesis_prompt = self._get_synthesis_prompt(task_type)
        
        final_message = {
            "role": "user",
            "parts": [
                {"type": "text", "text": synthesis_prompt}
            ]
        }
        
        return SubTask(
            id=subtask_id,
            type=SubTaskType.FINAL_DECISION,
            target_agent=self.agent_preferences["text"],
            message=final_message,
            dependencies=dependencies,
            priority=3,  # Highest priority (final result)
            timeout_seconds=15
        )
    
    def _get_synthesis_prompt(self, task_type: TaskType) -> str:
        """Get synthesis prompt based on task type."""
        prompts = {
            TaskType.PRODUCT_DEFECT_REPORT: """Based on the voice transcript, image analysis, and product information, provide a final warranty decision. Consider:
1. What the customer reported (voice)
2. Visual evidence of damage/defects (image)  
3. Product warranty terms and exclusions (text)
Recommend: approve_warranty, deny_warranty, escalate_to_specialist, or initiate_replacement.""",
            
            TaskType.ASSEMBLY_GUIDANCE: """Based on the customer's question and any visual evidence, provide clear assembly instructions. Consider:
1. What step they're stuck on (voice/text)
2. Current assembly state (image if provided)
3. Product assembly instructions (text)
Recommend: provide_instructions or escalate_to_specialist if unclear.""",
            
            TaskType.VISUAL_TROUBLESHOOTING: """Based on the problem description and visual evidence, provide troubleshooting guidance. Consider:
1. Symptoms described (voice/text)
2. Visual indicators like error codes or damage (image)
3. Troubleshooting procedures (text)
Recommend: troubleshoot_step, escalate_to_specialist, or initiate_replacement for safety issues.""",
            
            TaskType.WARRANTY_CLAIM: """Based on all available information, make a warranty determination. Consider:
1. Customer's claim and timeline (voice/text)
2. Product condition evidence (image if provided)
3. Warranty terms and coverage (text)
Recommend: approve_warranty, deny_warranty, order_part, or initiate_return."""
        }
        
        return prompts.get(task_type, "Analyze all provided information and recommend the appropriate customer service action.")
    
    def _create_execution_order(self, sub_tasks: List[SubTask]) -> List[List[str]]:
        """Create execution order respecting dependencies."""
        # Group tasks by dependency level
        no_deps = []
        with_deps = []
        
        for subtask in sub_tasks:
            if not subtask.dependencies:
                no_deps.append(subtask.id)
            else:
                with_deps.append(subtask.id)
        
        execution_order = []
        
        # First group: tasks with no dependencies (can run in parallel)
        if no_deps:
            execution_order.append(no_deps)
        
        # Second group: tasks with dependencies (usually just the final task)
        if with_deps:
            execution_order.append(with_deps)
        
        return execution_order
    
    def _estimate_duration(self, sub_tasks: List[SubTask], execution_order: List[List[str]]) -> float:
        """Estimate total execution duration."""
        total_duration = 0.0
        
        for group in execution_order:
            # For parallel groups, use the maximum duration
            group_duration = 0.0
            for subtask_id in group:
                subtask = next(st for st in sub_tasks if st.id == subtask_id)
                task_duration = subtask.timeout_seconds or 10.0
                group_duration = max(group_duration, task_duration)
            
            total_duration += group_duration
        
        # Add buffer for network latency and processing
        return total_duration + 5.0