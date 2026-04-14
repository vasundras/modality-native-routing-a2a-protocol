"""Routing Engine for the Modality-Aware Router.

Implements the core routing logic from Eq. 1 in the MMA2A paper:
- Route parts natively when destination supports the modality
- Transcode to text when destination doesn't support the modality
"""

import base64
import logging
from typing import Dict, List, Optional, Tuple, Any

from agent_registry import AgentInfo, AgentRegistry

logger = logging.getLogger(__name__)


class RoutingDecision:
    """Represents a routing decision for a message part."""
    
    def __init__(self, part: dict, destination_agent: str, action: str, reasoning: str):
        self.part = part
        self.destination_agent = destination_agent
        self.action = action  # "native" or "transcode"
        self.reasoning = reasoning
        self.transcoded_part: Optional[dict] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging/metrics."""
        return {
            "part_type": self.part.get("type"),
            "part_modality": self._get_part_modality(),
            "destination_agent": self.destination_agent,
            "action": self.action,
            "reasoning": self.reasoning
        }
    
    def _get_part_modality(self) -> str:
        """Determine the modality of a part."""
        if self.part.get("type") == "text":
            return "text"
        elif self.part.get("type") == "file":
            mime_type = self.part.get("mimeType", "")
            if mime_type.startswith("audio/"):
                return "voice"
            elif mime_type.startswith("image/"):
                return "image"
            else:
                return "file"
        else:
            return "unknown"


class RoutingEngine:
    """Core routing engine implementing MMA2A routing logic."""
    
    def __init__(self, agent_registry: AgentRegistry, force_text_mode: bool = False):
        self.agent_registry = agent_registry
        self.force_text_mode = force_text_mode  # For Text-BN baseline simulation
        
        # Transcoding services (in production these would be separate services)
        self.transcoding_services = {
            "voice_to_text": self._mock_voice_to_text,
            "image_to_text": self._mock_image_to_text
        }
    
    async def route_message(self, message: dict, target_agent: str) -> Tuple[dict, List[RoutingDecision]]:
        """Route a message to the target agent, applying MMA2A routing logic.
        
        Args:
            message: The A2A message with parts
            target_agent: Name of the destination agent
        
        Returns:
            Tuple of (routed_message, routing_decisions)
        """
        # Get target agent info
        agent_info = await self.agent_registry.get_agent(target_agent)
        if not agent_info:
            raise ValueError(f"Unknown target agent: {target_agent}")
        
        # Process each part according to routing rules
        routed_parts = []
        routing_decisions = []
        
        for part in message.get("parts", []):
            decision = await self._route_part(part, agent_info)
            routing_decisions.append(decision)
            
            if decision.action == "native":
                # Forward part as-is
                routed_parts.append(part)
            elif decision.action == "transcode":
                # Use transcoded version
                if decision.transcoded_part:
                    routed_parts.append(decision.transcoded_part)
                else:
                    # Fallback to original if transcoding failed
                    routed_parts.append(part)
                    logger.warning(f"Transcoding failed for part, using original: {decision.reasoning}")
        
        # Create routed message
        routed_message = {
            **message,
            "parts": routed_parts
        }
        
        return routed_message, routing_decisions
    
    async def _route_part(self, part: dict, target_agent: AgentInfo) -> RoutingDecision:
        """Apply routing logic to a single message part."""
        part_modality = self._get_part_modality(part)
        
        # Force text mode for Text-BN baseline
        if self.force_text_mode and part_modality != "text":
            return await self._transcode_part(part, target_agent, "text", 
                                            "Force text mode enabled (Text-BN baseline)")
        
        # MMA2A routing rule (Eq. 1 from paper):
        # If target agent supports the part's modality, route natively
        # Otherwise, transcode to text
        
        if target_agent.supports_input_mode(part_modality):
            # Native routing
            return RoutingDecision(
                part=part,
                destination_agent=target_agent.name,
                action="native",
                reasoning=f"Target agent supports {part_modality} natively"
            )
        else:
            # Transcode to text (target agent always supports text)
            return await self._transcode_part(part, target_agent, "text",
                                            f"Target agent doesn't support {part_modality}, transcoding to text")
    
    def _get_part_modality(self, part: dict) -> str:
        """Determine the modality of a message part."""
        if part.get("type") == "text":
            return "text"
        elif part.get("type") == "file":
            mime_type = part.get("mimeType", "")
            if mime_type.startswith("audio/"):
                return "voice"
            elif mime_type.startswith("image/"):
                return "image"
            else:
                return "file"
        else:
            return "unknown"
    
    async def _transcode_part(self, part: dict, target_agent: AgentInfo, 
                            target_modality: str, reasoning: str) -> RoutingDecision:
        """Transcode a part to the target modality."""
        part_modality = self._get_part_modality(part)
        
        decision = RoutingDecision(
            part=part,
            destination_agent=target_agent.name,
            action="transcode",
            reasoning=reasoning
        )
        
        # Perform transcoding
        if part_modality == "voice" and target_modality == "text":
            decision.transcoded_part = await self._transcode_voice_to_text(part)
        elif part_modality == "image" and target_modality == "text":
            decision.transcoded_part = await self._transcode_image_to_text(part)
        else:
            # Unsupported transcoding, use description
            decision.transcoded_part = {
                "type": "text",
                "text": f"[{part_modality.upper()} CONTENT: {part.get('name', 'unnamed')}]"
            }
            decision.reasoning += f" (unsupported transcoding {part_modality}→{target_modality})"
        
        return decision
    
    async def _transcode_voice_to_text(self, voice_part: dict) -> dict:
        """Transcode voice to text using voice agent."""
        try:
            # In production, this would call the voice agent
            # For now, use mock transcoding
            return await self.transcoding_services["voice_to_text"](voice_part)
        except Exception as e:
            logger.error(f"Voice transcoding failed: {e}")
            return {
                "type": "text",
                "text": f"[VOICE TRANSCRIPTION FAILED: {voice_part.get('name', 'audio')}]"
            }
    
    async def _transcode_image_to_text(self, image_part: dict) -> dict:
        """Transcode image to text using vision agent."""
        try:
            # In production, this would call the vision agent
            # For now, use mock transcoding
            return await self.transcoding_services["image_to_text"](image_part)
        except Exception as e:
            logger.error(f"Image transcoding failed: {e}")
            return {
                "type": "text", 
                "text": f"[IMAGE DESCRIPTION FAILED: {image_part.get('name', 'image')}]"
            }
    
    async def _mock_voice_to_text(self, voice_part: dict) -> dict:
        """Mock voice-to-text transcoding."""
        # Simulate transcription based on file name or content
        name = voice_part.get("name", "audio")
        
        mock_transcriptions = {
            "defect": "I dropped my product and now it's making a grinding noise. The blade assembly looks bent.",
            "warranty": "I bought this six months ago and the suction has completely died. I need this fixed ASAP.",
            "assembly": "I'm on step 4 where it says to attach the crossbar but I can't figure out which screw to use.",
            "troubleshoot": "My garage door goes down about a foot and then immediately reverses back up."
        }
        
        # Select transcription based on filename
        transcript = "Customer audio message"
        for keyword, text in mock_transcriptions.items():
            if keyword in name.lower():
                transcript = text
                break
        
        return {
            "type": "text",
            "text": f"[TRANSCRIBED]: {transcript}"
        }
    
    async def _mock_image_to_text(self, image_part: dict) -> dict:
        """Mock image-to-text transcoding."""
        # Simulate image description based on file name or content
        name = image_part.get("name", "image")
        
        mock_descriptions = {
            "defect": "Product showing visible crack on housing and bent blade assembly, consistent with drop damage",
            "warranty": "New product still in packaging with hairline crack near handle, appears to be manufacturing defect",
            "assembly": "Partially assembled furniture with missing crossbar, screws of different sizes visible",
            "troubleshoot": "Router admin interface showing WAN disconnected status and DNS error 0.0.0.0"
        }
        
        # Select description based on filename
        description = "Product image showing general condition"
        for keyword, text in mock_descriptions.items():
            if keyword in name.lower():
                description = text
                break
        
        return {
            "type": "text",
            "text": f"[IMAGE DESCRIPTION]: {description}"
        }
    
    def get_routing_stats(self) -> dict:
        """Get routing statistics."""
        # In production, this would track actual routing metrics
        return {
            "force_text_mode": self.force_text_mode,
            "transcoding_services": list(self.transcoding_services.keys()),
            "supported_modalities": ["text", "voice", "image"]
        }