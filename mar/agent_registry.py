"""Agent Registry for the Modality-Aware Router.

Manages discovery and caching of A2A agent cards to determine routing capabilities.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin

import httpx

logger = logging.getLogger(__name__)


class AgentInfo:
    """Information about a registered A2A agent."""
    
    def __init__(self, name: str, url: str, agent_card: dict):
        self.name = name
        self.url = url
        self.agent_card = agent_card
        self.last_updated = time.time()
    
    @property
    def input_modes(self) -> List[str]:
        """Get supported input modalities."""
        return self.agent_card.get("defaultInputModes", [])
    
    @property
    def output_modes(self) -> List[str]:
        """Get supported output modalities."""
        return self.agent_card.get("defaultOutputModes", [])
    
    @property
    def capabilities(self) -> dict:
        """Get agent capabilities."""
        return self.agent_card.get("capabilities", {})
    
    @property
    def skills(self) -> List[dict]:
        """Get agent skills."""
        return self.agent_card.get("skills", [])
    
    def supports_input_mode(self, mode: str) -> bool:
        """Check if agent supports a specific input modality."""
        # Normalize mode names
        mode_mapping = {
            "text": "text",
            "voice": "voice", 
            "audio": "voice",
            "image": "image",
            "vision": "image"
        }
        
        normalized_mode = mode_mapping.get(mode.lower(), mode.lower())
        normalized_inputs = [mode_mapping.get(m.lower(), m.lower()) for m in self.input_modes]
        
        return normalized_mode in normalized_inputs
    
    def is_stale(self, ttl_seconds: int) -> bool:
        """Check if cached agent info is stale."""
        return (time.time() - self.last_updated) > ttl_seconds


class AgentRegistry:
    """Registry for discovering and caching A2A agents."""
    
    def __init__(self, cache_ttl_seconds: int = 60):
        self.cache_ttl_seconds = cache_ttl_seconds
        self.agents: Dict[str, AgentInfo] = {}
        self.client = httpx.AsyncClient(timeout=10.0)
        
        # Default agent endpoints (can be configured)
        self.known_agents = {
            "text_agent": "http://localhost:8001",
            "voice_agent": "http://localhost:8081", 
            "vision_agent": "http://localhost:8082"
        }
    
    async def discover_agents(self) -> None:
        """Discover agents by fetching their Agent Cards."""
        logger.info("Discovering A2A agents...")
        
        for agent_name, base_url in self.known_agents.items():
            try:
                await self.register_agent(agent_name, base_url)
            except Exception as e:
                logger.warning(f"Failed to discover agent {agent_name} at {base_url}: {e}")
    
    async def register_agent(self, name: str, base_url: str) -> None:
        """Register an agent by fetching its Agent Card."""
        agent_card_url = urljoin(base_url.rstrip('/') + '/', '.well-known/agent-card.json')
        
        try:
            response = await self.client.get(agent_card_url)
            response.raise_for_status()
            
            agent_card = response.json()
            agent_info = AgentInfo(name, base_url, agent_card)
            
            self.agents[name] = agent_info
            logger.info(f"Registered agent '{name}' with input modes: {agent_info.input_modes}")
            
        except Exception as e:
            logger.error(f"Failed to register agent {name} from {base_url}: {e}")
            raise
    
    async def get_agent(self, name: str) -> Optional[AgentInfo]:
        """Get agent info, refreshing if stale."""
        if name not in self.agents:
            # Try to discover if not found
            if name in self.known_agents:
                await self.register_agent(name, self.known_agents[name])
            else:
                return None
        
        agent_info = self.agents.get(name)
        if agent_info and agent_info.is_stale(self.cache_ttl_seconds):
            # Refresh stale agent info
            try:
                await self.register_agent(name, agent_info.url)
                agent_info = self.agents.get(name)
            except Exception as e:
                logger.warning(f"Failed to refresh agent {name}: {e}")
                # Continue with stale info
        
        return agent_info
    
    def find_agents_for_modality(self, modality: str) -> List[AgentInfo]:
        """Find all agents that support a specific input modality."""
        compatible_agents = []
        
        for agent_info in self.agents.values():
            if agent_info.supports_input_mode(modality):
                compatible_agents.append(agent_info)
        
        return compatible_agents
    
    def get_best_agent_for_modality(self, modality: str, preferred_agents: List[str] = None) -> Optional[AgentInfo]:
        """Get the best agent for a specific modality."""
        compatible_agents = self.find_agents_for_modality(modality)
        
        if not compatible_agents:
            return None
        
        # Prefer agents in the preferred list
        if preferred_agents:
            for preferred in preferred_agents:
                for agent in compatible_agents:
                    if agent.name == preferred:
                        return agent
        
        # Default preference order by modality
        modality_preferences = {
            "text": ["text_agent"],
            "voice": ["voice_agent"], 
            "image": ["vision_agent"]
        }
        
        preferred = modality_preferences.get(modality.lower(), [])
        for pref_name in preferred:
            for agent in compatible_agents:
                if agent.name == pref_name:
                    return agent
        
        # Return first available if no preference match
        return compatible_agents[0]
    
    async def health_check_agent(self, agent_info: AgentInfo) -> bool:
        """Check if an agent is healthy."""
        try:
            health_url = urljoin(agent_info.url.rstrip('/') + '/', 'health')
            response = await self.client.get(health_url)
            return response.status_code == 200
        except Exception:
            return False
    
    async def close(self):
        """Clean up resources."""
        await self.client.aclose()
    
    def get_registry_status(self) -> dict:
        """Get status of all registered agents."""
        status = {
            "total_agents": len(self.agents),
            "agents": {}
        }
        
        for name, agent_info in self.agents.items():
            status["agents"][name] = {
                "url": agent_info.url,
                "input_modes": agent_info.input_modes,
                "output_modes": agent_info.output_modes,
                "last_updated": agent_info.last_updated,
                "is_stale": agent_info.is_stale(self.cache_ttl_seconds)
            }
        
        return status