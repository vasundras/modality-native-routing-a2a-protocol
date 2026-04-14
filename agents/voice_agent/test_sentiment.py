#!/usr/bin/env python3
"""Test sentiment analysis functionality without API calls."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from whisper_processor import WhisperProcessor


def test_sentiment_analysis():
    """Test sentiment analysis with various customer scenarios."""
    
    # Create a mock processor that bypasses API initialization
    class MockProcessor:
        def analyze_sentiment(self, transcript: str, metadata: dict) -> dict:
            # Use the same logic as the real processor
            processor = WhisperProcessor.__new__(WhisperProcessor)  # Create without __init__
            return processor.analyze_sentiment(transcript, metadata)
    
    processor = MockProcessor()
    
    test_cases = [
        {
            "name": "Frustrated customer with drop damage",
            "transcript": "I dropped my BlenderMax 3000 and now it's making a grinding noise. The blade assembly looks bent and I'm really frustrated!",
        },
        {
            "name": "Happy customer with DOA replacement",
            "transcript": "I just unboxed this coffee maker and it has a crack. Can you help me get a replacement?",
        },
        {
            "name": "Urgent safety concern",
            "transcript": "My toaster started sparking this morning! I need help immediately. This is dangerous and I'm scared to use it.",
        },
        {
            "name": "Assembly confusion",
            "transcript": "I'm on step 4 of the KALLAX assembly and I don't know which screw to use? There are three different sizes.",
        },
        {
            "name": "Very satisfied customer",
            "transcript": "This vacuum is amazing! It works perfectly and I love how quiet it is. Excellent product!",
        },
        {
            "name": "Warranty expiration concern",
            "transcript": "My air fryer stopped working two weeks after the warranty ended. I paid good money for this.",
        },
        {
            "name": "Multiple problems",
            "transcript": "This is terrible! The product is broken, doesn't work at all, and I'm really angry. I need this fixed now!",
        },
    ]
    
    print("=" * 80)
    print("SENTIMENT ANALYSIS TEST")
    print("=" * 80)
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n{i}. {case['name']}")
        print(f"   Transcript: \"{case['transcript']}\"")
        
        result = processor.analyze_sentiment(case['transcript'], {})
        
        print(f"   → Sentiment: {result['sentiment'].upper()}")
        print(f"   → Confidence: {result['confidence']:.2f}")
        print(f"   → Score: {result['score']:.2f}")
        
        if result.get('urgency_detected'):
            print("   → ⚠️  URGENCY DETECTED")
        
        if result.get('frustration_detected'):
            print("   → 😤 FRUSTRATION DETECTED")
        
        if result['indicators']:
            print(f"   → Indicators: {', '.join(result['indicators'])}")


if __name__ == "__main__":
    test_sentiment_analysis()