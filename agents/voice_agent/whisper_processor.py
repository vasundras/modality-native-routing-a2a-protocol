"""Whisper audio processing for the Voice Agent.

Handles audio transcription using OpenAI's Whisper API or local faster-whisper,
plus basic sentiment analysis from voice patterns.
"""

import base64
import io
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

logger = logging.getLogger(__name__)


class WhisperProcessor:
    """Handles audio transcription and basic voice analysis."""
    
    def __init__(self, backend: str = "openai", model: str = "whisper-1"):
        self.backend = backend
        self.model = model
        self._whisper_model = None
        
        if backend == "openai":
            if not OPENAI_AVAILABLE:
                raise ImportError("OpenAI package not available. Install with: pip install openai")
            
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            
            self.client = openai.OpenAI(api_key=api_key)
            logger.info("Initialized OpenAI Whisper client")
        
        elif backend == "local":
            if not FASTER_WHISPER_AVAILABLE:
                raise ImportError("faster-whisper package not available. Install with: pip install faster-whisper")
            
            # Use smaller model for development, can be configured
            model_size = model if model in ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"] else "base"
            self._whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")
            logger.info(f"Initialized local Whisper model: {model_size}")
        
        elif backend == "gemini":
            if not GENAI_AVAILABLE:
                raise ImportError("google-generativeai not available. Install with: pip install google-generativeai")

            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY environment variable not set")

            genai.configure(api_key=api_key)
            self.genai_model = genai.GenerativeModel(model)
            logger.info(f"Initialized Gemini audio client with model: {model}")

        else:
            raise ValueError(f"Unknown backend: {backend}. Use 'openai', 'local', or 'gemini'")
    
    def transcribe_audio(self, audio_data: bytes, mime_type: str = "audio/wav") -> Tuple[str, dict]:
        """Transcribe audio data to text.
        
        Args:
            audio_data: Raw audio bytes
            mime_type: MIME type of audio (audio/wav, audio/webm, etc.)
        
        Returns:
            Tuple of (transcript_text, metadata_dict)
        """
        if self.backend == "openai":
            return self._transcribe_openai(audio_data, mime_type)
        elif self.backend == "local":
            return self._transcribe_local(audio_data, mime_type)
        elif self.backend == "gemini":
            return self._transcribe_gemini(audio_data, mime_type)
        else:
            raise ValueError(f"Unknown backend: {self.backend}")
    
    def _transcribe_openai(self, audio_data: bytes, mime_type: str) -> Tuple[str, dict]:
        """Transcribe using OpenAI Whisper API."""
        try:
            # Determine file extension from MIME type
            if mime_type == "audio/wav":
                ext = ".wav"
            elif mime_type == "audio/webm":
                ext = ".webm"
            elif mime_type == "audio/mp3":
                ext = ".mp3"
            elif mime_type == "audio/m4a":
                ext = ".m4a"
            else:
                ext = ".wav"  # Default fallback
            
            # Write to temporary file (OpenAI API requires file upload)
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            try:
                # Transcribe with OpenAI
                with open(temp_path, "rb") as audio_file:
                    transcript = self.client.audio.transcriptions.create(
                        model=self.model,
                        file=audio_file,
                        response_format="verbose_json",
                        timestamp_granularities=["word"]
                    )
                
                # Extract transcript and metadata
                text = transcript.text.strip()
                metadata = {
                    "language": getattr(transcript, "language", "en"),
                    "duration": getattr(transcript, "duration", None),
                    "confidence": self._estimate_confidence_openai(transcript),
                    "word_count": len(text.split()) if text else 0,
                    "backend": "openai",
                    "model": self.model
                }
                
                return text, metadata
            
            finally:
                # Clean up temp file
                os.unlink(temp_path)
        
        except Exception as e:
            logger.error(f"OpenAI transcription failed: {e}")
            return "", {"error": str(e), "backend": "openai"}
    
    def _transcribe_local(self, audio_data: bytes, mime_type: str) -> Tuple[str, dict]:
        """Transcribe using local faster-whisper."""
        try:
            # Determine file extension
            if mime_type == "audio/wav":
                ext = ".wav"
            elif mime_type == "audio/webm":
                ext = ".webm"
            else:
                ext = ".wav"
            
            # Write to temporary file
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            try:
                # Transcribe with faster-whisper
                segments, info = self._whisper_model.transcribe(
                    temp_path,
                    beam_size=5,
                    word_timestamps=True
                )
                
                # Collect segments
                text_parts = []
                total_confidence = 0
                segment_count = 0
                
                for segment in segments:
                    text_parts.append(segment.text.strip())
                    if hasattr(segment, 'avg_logprob'):
                        total_confidence += segment.avg_logprob
                        segment_count += 1
                
                text = " ".join(text_parts).strip()
                avg_confidence = total_confidence / segment_count if segment_count > 0 else 0
                
                metadata = {
                    "language": info.language,
                    "language_probability": info.language_probability,
                    "duration": info.duration,
                    "confidence": max(0, min(1, (avg_confidence + 5) / 5)),  # Normalize logprob to 0-1
                    "word_count": len(text.split()) if text else 0,
                    "backend": "local",
                    "model": self.model
                }
                
                return text, metadata
            
            finally:
                os.unlink(temp_path)
        
        except Exception as e:
            logger.error(f"Local transcription failed: {e}")
            return "", {"error": str(e), "backend": "local"}
    
    def _transcribe_gemini(self, audio_data: bytes, mime_type: str) -> Tuple[str, dict]:
        """Transcribe using Google Gemini multimodal API."""
        try:
            # Determine file extension from MIME type
            ext_map = {
                "audio/wav": ".wav", "audio/webm": ".webm",
                "audio/mp3": ".mp3", "audio/mpeg": ".mp3",
                "audio/m4a": ".m4a", "audio/mp4": ".m4a",
            }
            ext = ext_map.get(mime_type, ".wav")

            # Write to temporary file for upload
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name

            try:
                # Upload file to Gemini
                uploaded = genai.upload_file(temp_path, mime_type=mime_type)

                # Transcribe with Gemini
                response = self.genai_model.generate_content(
                    [
                        uploaded,
                        "Transcribe this audio exactly. Output only the transcript text, nothing else.",
                    ]
                )

                text = response.text.strip()
                metadata = {
                    "word_count": len(text.split()) if text else 0,
                    "backend": "gemini",
                    "model": self.model,
                    "confidence": 0.85,
                }
                return text, metadata

            finally:
                os.unlink(temp_path)
                try:
                    genai.delete_file(uploaded.name)
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Gemini transcription failed: {e}")
            return "", {"error": str(e), "backend": "gemini"}

    def _estimate_confidence_openai(self, transcript) -> float:
        """Estimate confidence from OpenAI transcript (they don't provide it directly)."""
        # OpenAI doesn't provide confidence scores, so we estimate based on:
        # - Presence of word timestamps (indicates good quality)
        # - Text length vs expected duration
        # - Absence of common transcription artifacts
        
        text = transcript.text.strip()
        if not text:
            return 0.0
        
        confidence = 0.8  # Base confidence for OpenAI
        
        # Check for word-level timestamps (indicates good quality)
        if hasattr(transcript, 'words') and transcript.words:
            confidence += 0.1
        
        # Penalize very short transcripts (likely errors)
        if len(text) < 10:
            confidence -= 0.2
        
        # Penalize transcripts with many repeated words (transcription artifacts)
        words = text.lower().split()
        if len(words) > 5:
            unique_ratio = len(set(words)) / len(words)
            if unique_ratio < 0.5:  # More than 50% repeated words
                confidence -= 0.3
        
        return max(0.0, min(1.0, confidence))
    
    def analyze_sentiment(self, transcript: str, metadata: dict) -> dict:
        """Basic sentiment analysis from transcript and audio metadata.
        
        This is a simple rule-based approach. In production, you'd use
        a proper sentiment analysis model.
        """
        if not transcript.strip():
            return {"sentiment": "neutral", "confidence": 0.0, "indicators": []}
        
        text_lower = transcript.lower()
        
        # Emotion indicators
        frustration_words = ["frustrated", "angry", "mad", "upset", "annoyed", "terrible", "awful", "horrible"]
        urgency_words = ["urgent", "immediately", "asap", "emergency", "now", "quickly", "help"]
        satisfaction_words = ["great", "excellent", "perfect", "wonderful", "amazing", "love", "happy"]
        problem_words = ["broken", "doesn't work", "failed", "problem", "issue", "wrong", "defect"]
        
        indicators = []
        sentiment_score = 0
        
        # Check for frustration
        frustration_count = sum(1 for word in frustration_words if word in text_lower)
        if frustration_count > 0:
            sentiment_score -= frustration_count * 0.3
            indicators.append(f"frustration_indicators: {frustration_count}")
        
        # Check for urgency
        urgency_count = sum(1 for word in urgency_words if word in text_lower)
        if urgency_count > 0:
            sentiment_score -= urgency_count * 0.2  # Urgency often correlates with negative sentiment
            indicators.append(f"urgency_indicators: {urgency_count}")
        
        # Check for satisfaction
        satisfaction_count = sum(1 for word in satisfaction_words if word in text_lower)
        if satisfaction_count > 0:
            sentiment_score += satisfaction_count * 0.4
            indicators.append(f"satisfaction_indicators: {satisfaction_count}")
        
        # Check for problems
        problem_count = sum(1 for word in problem_words if word in text_lower)
        if problem_count > 0:
            sentiment_score -= problem_count * 0.2
            indicators.append(f"problem_indicators: {problem_count}")
        
        # Check for exclamation marks (intensity)
        exclamation_count = transcript.count("!")
        if exclamation_count > 0:
            # Could be positive or negative intensity
            indicators.append(f"exclamation_marks: {exclamation_count}")
        
        # Check for question marks (confusion/seeking help)
        question_count = transcript.count("?")
        if question_count > 1:  # Multiple questions suggest confusion
            sentiment_score -= 0.1
            indicators.append(f"multiple_questions: {question_count}")
        
        # Determine overall sentiment
        if sentiment_score > 0.2:
            sentiment = "positive"
        elif sentiment_score < -0.2:
            sentiment = "negative"
        else:
            sentiment = "neutral"
        
        # Confidence based on number of indicators
        confidence = min(0.9, len(indicators) * 0.2 + 0.1)
        
        return {
            "sentiment": sentiment,
            "confidence": confidence,
            "score": sentiment_score,
            "indicators": indicators,
            "urgency_detected": urgency_count > 0,
            "frustration_detected": frustration_count > 0
        }


def create_processor(config: dict) -> WhisperProcessor:
    """Factory function to create WhisperProcessor from config."""
    backend = config.get("backend", "openai")
    model = config.get("model", "whisper-1")
    return WhisperProcessor(backend=backend, model=model)