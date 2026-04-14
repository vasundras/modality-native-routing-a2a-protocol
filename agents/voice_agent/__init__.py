"""Voice Agent - A2A compliant audio processing agent."""

from .whisper_processor import WhisperProcessor, create_processor

__all__ = ["WhisperProcessor", "create_processor"]