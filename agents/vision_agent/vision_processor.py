"""Vision processing for the Vision Agent.

Handles image analysis using OpenAI's GPT-4 Vision API or other multimodal models,
focusing on customer service scenarios like defect detection and troubleshooting.
"""

import base64
import io
import logging
import os
from typing import Optional, Tuple

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# PIL not needed for this implementation
PIL_AVAILABLE = False

logger = logging.getLogger(__name__)


class VisionProcessor:
    """Handles image analysis for customer service scenarios."""
    
    def __init__(self, backend: str = "openai", model: str = "gpt-4o-mini"):
        self.backend = backend
        self.model = model
        
        if backend == "openai":
            if not OPENAI_AVAILABLE:
                raise ImportError("OpenAI package not available. Install with: pip install openai")
            
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            
            self.client = openai.OpenAI(api_key=api_key)
            logger.info(f"Initialized OpenAI Vision client with model: {model}")
        
        elif backend == "gemini":
            if not GENAI_AVAILABLE:
                raise ImportError("google-generativeai not available. Install with: pip install google-generativeai")

            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY environment variable not set")

            genai.configure(api_key=api_key)
            self.genai_model = genai.GenerativeModel(model)
            logger.info(f"Initialized Gemini Vision client with model: {model}")

        else:
            raise ValueError(f"Unknown backend: {backend}. Use 'openai' or 'gemini'")
    
    def analyze_image(self, image_data: bytes, mime_type: str, context: str = "") -> Tuple[str, dict]:
        """Analyze an image for customer service scenarios.
        
        Args:
            image_data: Raw image bytes
            mime_type: MIME type of image (image/png, image/jpeg, etc.)
            context: Optional context about what to look for
        
        Returns:
            Tuple of (analysis_text, metadata_dict)
        """
        if self.backend == "openai":
            return self._analyze_openai(image_data, mime_type, context)
        elif self.backend == "gemini":
            return self._analyze_gemini(image_data, mime_type, context)
        else:
            raise ValueError(f"Unknown backend: {self.backend}")
    
    def _analyze_openai(self, image_data: bytes, mime_type: str, context: str) -> Tuple[str, dict]:
        """Analyze image using OpenAI GPT-4 Vision."""
        try:
            # Encode image as base64
            image_b64 = base64.b64encode(image_data).decode('utf-8')
            
            # Determine format from MIME type
            if mime_type == "image/png":
                format_type = "png"
            elif mime_type in ["image/jpeg", "image/jpg"]:
                format_type = "jpeg"
            elif mime_type == "image/webp":
                format_type = "webp"
            else:
                format_type = "jpeg"  # Default fallback
            
            # Build the prompt for customer service image analysis
            system_prompt = """You are a customer service image analysis expert. Analyze images to help with:
- Product defect identification
- Assembly and troubleshooting guidance  
- Warranty claim assessment
- Visual problem diagnosis

Focus on practical, actionable observations that help customer service representatives make decisions."""

            user_prompt = f"""Analyze this customer service image. Provide a detailed analysis covering:

1. **OVERALL CONDITION**: Describe what you see - product type, general condition, any obvious issues
2. **DEFECTS/DAMAGE**: Identify any visible damage, defects, or abnormalities
3. **ASSEMBLY STATUS**: If applicable, assess assembly progress or identify missing/incorrect components
4. **ERROR INDICATORS**: Look for error codes, warning lights, or status displays
5. **WARRANTY ASSESSMENT**: Based on visible condition, is this likely covered under warranty?
6. **RECOMMENDED ACTION**: What should customer service do based on this image?

{f"Additional context: {context}" if context else ""}

Be specific and detailed in your observations. Focus on facts you can clearly see in the image."""

            # Make API call
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user", 
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_b64}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                temperature=0.1  # Low temperature for consistent, factual analysis
            )
            
            analysis = response.choices[0].message.content.strip()
            
            # Extract metadata
            metadata = {
                "model": self.model,
                "backend": "openai",
                "image_format": format_type,
                "image_size_bytes": len(image_data),
                "tokens_used": response.usage.total_tokens if response.usage else 0,
                "analysis_length": len(analysis)
            }
            
            return analysis, metadata
        
        except Exception as e:
            logger.error(f"OpenAI vision analysis failed: {e}")
            return f"Vision analysis failed: {str(e)}", {"error": str(e), "backend": "openai"}
    
    def _analyze_gemini(self, image_data: bytes, mime_type: str, context: str) -> Tuple[str, dict]:
        """Analyze image using Google Gemini multimodal API."""
        try:
            import tempfile

            # Determine extension from MIME type
            ext_map = {
                "image/png": ".png", "image/jpeg": ".jpg",
                "image/jpg": ".jpg", "image/webp": ".webp",
            }
            ext = ext_map.get(mime_type, ".jpg")

            # Write to temporary file for upload
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_file:
                temp_file.write(image_data)
                temp_path = temp_file.name

            try:
                uploaded = genai.upload_file(temp_path, mime_type=mime_type)

                prompt = f"""Analyze this customer service image. Provide a detailed analysis covering:

1. **OVERALL CONDITION**: Describe what you see - product type, general condition, any obvious issues
2. **DEFECTS/DAMAGE**: Identify any visible damage, defects, or abnormalities
3. **ASSEMBLY STATUS**: If applicable, assess assembly progress or identify missing/incorrect components
4. **ERROR INDICATORS**: Look for error codes, warning lights, or status displays
5. **WARRANTY ASSESSMENT**: Based on visible condition, is this likely covered under warranty?
6. **RECOMMENDED ACTION**: What should customer service do based on this image?

{f"Additional context: {context}" if context else ""}

Be specific and detailed in your observations. Focus on facts you can clearly see in the image."""

                response = self.genai_model.generate_content([uploaded, prompt])
                analysis = response.text.strip()

                metadata = {
                    "model": self.model,
                    "backend": "gemini",
                    "image_format": ext.lstrip("."),
                    "image_size_bytes": len(image_data),
                    "analysis_length": len(analysis),
                }

                return analysis, metadata

            finally:
                os.unlink(temp_path)
                try:
                    genai.delete_file(uploaded.name)
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Gemini vision analysis failed: {e}")
            return f"Vision analysis failed: {str(e)}", {"error": str(e), "backend": "gemini"}

    def assess_warranty_eligibility(self, analysis: str) -> dict:
        """Assess warranty eligibility based on image analysis.
        
        This uses rule-based logic to recommend warranty actions based on
        the image analysis content.
        """
        analysis_lower = analysis.lower()
        
        # Indicators of warranty-covered issues
        manufacturing_defects = [
            "manufacturing defect", "factory defect", "production flaw",
            "material failure", "component failure", "internal damage",
            "stress crack", "fatigue crack", "weld failure", "joint failure"
        ]
        
        # Indicators of user damage (not covered)
        user_damage = [
            "impact damage", "drop damage", "physical abuse", "user damage",
            "external force", "collision", "scratch", "dent from impact",
            "water damage", "liquid damage", "corrosion", "rust"
        ]
        
        # Safety concerns (immediate action needed)
        safety_issues = [
            "fire hazard", "electrical hazard", "burn mark", "melting",
            "smoke damage", "overheating", "swelling", "bulging battery",
            "exposed wiring", "cracked housing"
        ]
        
        # Assembly issues (instruction needed)
        assembly_issues = [
            "missing component", "incorrect assembly", "loose connection",
            "misaligned", "not properly seated", "installation error"
        ]
        
        # Count indicators
        manufacturing_score = sum(1 for indicator in manufacturing_defects if indicator in analysis_lower)
        user_damage_score = sum(1 for indicator in user_damage if indicator in analysis_lower)
        safety_score = sum(1 for indicator in safety_issues if indicator in analysis_lower)
        assembly_score = sum(1 for indicator in assembly_issues if indicator in analysis_lower)
        
        # Determine recommendation
        if safety_score > 0:
            recommendation = "initiate_replacement"
            reason = "Safety hazard identified - immediate replacement required"
            confidence = 0.95
        elif manufacturing_score > user_damage_score and manufacturing_score > 0:
            recommendation = "approve_warranty"
            reason = "Manufacturing defect indicators detected"
            confidence = min(0.9, 0.6 + manufacturing_score * 0.1)
        elif user_damage_score > manufacturing_score and user_damage_score > 0:
            recommendation = "deny_warranty"
            reason = "User damage indicators detected"
            confidence = min(0.9, 0.6 + user_damage_score * 0.1)
        elif assembly_score > 0:
            recommendation = "provide_instructions"
            reason = "Assembly or installation issue detected"
            confidence = min(0.8, 0.5 + assembly_score * 0.1)
        else:
            recommendation = "escalate_to_specialist"
            reason = "Unclear from image - requires human review"
            confidence = 0.3
        
        return {
            "recommended_action": recommendation,
            "reasoning": reason,
            "confidence": confidence,
            "indicators": {
                "manufacturing_defects": manufacturing_score,
                "user_damage": user_damage_score,
                "safety_issues": safety_score,
                "assembly_issues": assembly_score
            }
        }
    
    def extract_error_codes(self, analysis: str) -> list[str]:
        """Extract error codes mentioned in the analysis."""
        import re
        
        # Common error code patterns
        patterns = [
            r'\bE\d{1,3}\b',  # E1, E23, E123
            r'\bF\d{1,3}\b',  # F1, F23, F123
            r'\b\d{3,4}\b',   # 404, 1234
            r'\bERR\s*\d+\b', # ERR 123, ERR123
            r'\bERROR\s*\d+\b' # ERROR 123, ERROR123
        ]
        
        error_codes = []
        for pattern in patterns:
            matches = re.findall(pattern, analysis, re.IGNORECASE)
            error_codes.extend(matches)
        
        return list(set(error_codes))  # Remove duplicates


def create_processor(config: dict) -> VisionProcessor:
    """Factory function to create VisionProcessor from config."""
    backend = config.get("backend", "openai")
    model = config.get("model", "gpt-4o-mini")
    return VisionProcessor(backend=backend, model=model)