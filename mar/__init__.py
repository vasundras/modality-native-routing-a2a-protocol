"""Modality-Aware Router (MAR) - Core component of MMA2A system."""

from .agent_registry import AgentRegistry, AgentInfo
from .routing_engine import RoutingEngine, RoutingDecision

__all__ = ["AgentRegistry", "AgentInfo", "RoutingEngine", "RoutingDecision"]