#!/usr/bin/env python3
"""Test script for the Voice Agent.

Run with: python test_agent.py

This tests the agent locally and provides curl examples for server testing.
"""

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from whisper_processor import WhisperProcessor


def create_test_audio():
    """Create a simple test audio file for testing.
    
    This creates a minimal WAV file with silence for testing purposes.
    In a real scenario, you'd use actual audio files.
    """
    # Minimal WAV header for 1 second of silence at 16kHz mono
    wav_header = bytes([
        0x52, 0x49, 0x46, 0x46,  # "RIFF"
        0x2C, 0x7D, 0x00, 0x00,  # File size (32044 bytes)
        0x57, 0x41, 0x56, 0x45,  # "WAVE"
        0x66, 0x6D, 0x74, 0x20,  # "fmt "
        0x10, 0x00, 0x00, 0x00,  # Subchunk1Size (16)
        0x01, 0x00,              # AudioFormat (PCM)
        0x01, 0x00,              # NumChannels (1)
        0x40, 0x3E, 0x00, 0x00,  # SampleRate (16000)
        0x80, 0x7D, 0x00, 0x00,  # ByteRate (32000)
        0x02, 0x00,              # BlockAlign (2)
        0x10, 0x00,              # BitsPerSample (16)
        0x64, 0x61, 0x74, 0x61,  # "data"
        0x00, 0x7D, 0x00, 0x00,  # Subchunk2Size (32000)
    ])
    
    # 1 second of silence (32000 bytes of zeros for 16kHz mono 16-bit)
    silence = b'\x00' * 32000
    
    return wav_header + silence


def test_processor_mock():
    """Test the processor with mock data (no actual API calls)."""
    print("=" * 60)
    print("TEST: Voice Processor (Mock Mode)")
    print("=" * 60)
    
    # Test sentiment analysis without actual transcription
    test_transcripts = [
        "I dropped my BlenderMax 3000 and the blade is bent",
        "I just unboxed this coffee maker and it has a crack",
        "My toaster is sparking when I use it! This is dangerous!",
        "I'm on step 4 and don't know which screw to use?",
        "This product is amazing! I love it so much!",
        "The warranty expired but can you help me anyway?",
    ]
    
    # Create a mock processor (won't actually call APIs)
    try:
        processor = WhisperProcessor(backend="openai", model="whisper-1")
    except Exception as e:
        print(f"Note: Could not initialize processor ({e})")
        print("This is expected if API keys are not configured.")
        processor = None
    
    for i, transcript in enumerate(test_transcripts, 1):
        print(f"\n{i}. Testing: \"{transcript}\"")
        
        if processor:
            sentiment = processor.analyze_sentiment(transcript, {})
            print(f"   Sentiment: {sentiment['sentiment'].upper()}")
            print(f"   Confidence: {sentiment['confidence']:.2f}")
            print(f"   Urgency: {sentiment.get('urgency_detected', False)}")
            print(f"   Frustration: {sentiment.get('frustration_detected', False)}")
            if sentiment['indicators']:
                print(f"   Indicators: {', '.join(sentiment['indicators'])}")
        else:
            print("   (Processor not available)")


def test_agent_card():
    """Verify agent card is valid JSON."""
    print("\n" + "=" * 60)
    print("TEST: Agent Card")
    print("=" * 60)
    
    card_path = Path(__file__).parent / "agent_card.json"
    with open(card_path) as f:
        card = json.load(f)
    
    print(f"Agent Name: {card['name']}")
    print(f"Version: {card['version']}")
    print(f"URL: {card['url']}")
    print(f"Input Modes: {card['defaultInputModes']}")
    print(f"Output Modes: {card['defaultOutputModes']}")
    print(f"Skills: {len(card['skills'])}")
    for skill in card['skills']:
        print(f"  - {skill['name']}: {skill['description'][:50]}...")


def generate_curl_examples():
    """Generate curl examples for testing the server."""
    print("\n" + "=" * 60)
    print("SERVER TESTING EXAMPLES")
    print("=" * 60)
    
    # Create test audio data
    test_audio = create_test_audio()
    audio_b64 = base64.b64encode(test_audio).decode('ascii')
    
    print("\n1. Test Agent Card:")
    print("curl http://localhost:8081/.well-known/agent-card.json | python -m json.tool")
    
    print("\n2. Test Health Check:")
    print("curl http://localhost:8081/health")
    
    print("\n3. Test Audio Processing (tasks/send):")
    print("curl -X POST http://localhost:8081/ \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{")
    print('    "jsonrpc": "2.0",')
    print('    "method": "tasks/send",')
    print('    "params": {')
    print('      "id": "voice-test-001",')
    print('      "message": {')
    print('        "role": "user",')
    print('        "parts": [')
    print('          {')
    print('            "type": "file",')
    print('            "mimeType": "audio/wav",')
    print('            "name": "test.wav",')
    print(f'            "data": "{audio_b64[:100]}..."')
    print('          }')
    print('        ]')
    print('      }')
    print('    },')
    print('    "id": 1')
    print("  }' | python -m json.tool")
    
    print(f"\nNote: The actual base64 data is {len(audio_b64)} characters long.")
    print("For real testing, you'd use actual audio files with speech content.")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("VOICE AGENT TEST SUITE")
    print("=" * 60)
    
    test_agent_card()
    test_processor_mock()
    generate_curl_examples()
    
    print("\n" + "=" * 60)
    print("SETUP INSTRUCTIONS")
    print("=" * 60)
    print("\nTo test with real audio:")
    print("1. Set environment variable: export OPENAI_API_KEY=your_key_here")
    print("2. Start the server: cd agents/voice_agent && python server.py")
    print("3. Use the curl examples above with real audio files")
    print("\nFor local Whisper (no API key needed):")
    print("1. pip install faster-whisper")
    print("2. Change config backend from 'openai' to 'local'")
    print("3. First run will download the Whisper model (~150MB for base model)")


if __name__ == "__main__":
    main()