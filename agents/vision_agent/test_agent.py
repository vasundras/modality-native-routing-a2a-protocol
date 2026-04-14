#!/usr/bin/env python3
"""Test script for the Vision Agent.

Run with: python test_agent.py

This tests the agent locally and provides curl examples for server testing.
"""

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from vision_processor import VisionProcessor


def create_test_image():
    """Create a simple test image for testing.
    
    This creates a minimal PNG file for testing purposes.
    In a real scenario, you'd use actual product photos.
    """
    # Minimal PNG file (1x1 pixel, transparent)
    png_data = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
        0x00, 0x00, 0x00, 0x0D,  # IHDR chunk length
        0x49, 0x48, 0x44, 0x52,  # "IHDR"
        0x00, 0x00, 0x00, 0x01,  # Width: 1
        0x00, 0x00, 0x00, 0x01,  # Height: 1
        0x08, 0x06, 0x00, 0x00, 0x00,  # Bit depth: 8, Color type: 6 (RGBA), Compression: 0, Filter: 0, Interlace: 0
        0x1F, 0x15, 0xC4, 0x89,  # CRC
        0x00, 0x00, 0x00, 0x0B,  # IDAT chunk length
        0x49, 0x44, 0x41, 0x54,  # "IDAT"
        0x78, 0x9C, 0x62, 0x00, 0x02, 0x00, 0x00, 0x05, 0x00, 0x01, 0x0D,  # Compressed image data
        0x0A, 0x2D, 0xB4,  # CRC
        0x00, 0x00, 0x00, 0x00,  # IEND chunk length
        0x49, 0x45, 0x4E, 0x44,  # "IEND"
        0xAE, 0x42, 0x60, 0x82   # CRC
    ])
    
    return png_data


def test_warranty_assessment():
    """Test warranty assessment logic without API calls."""
    print("=" * 80)
    print("TEST: Warranty Assessment Logic")
    print("=" * 80)
    
    # Create a mock processor that bypasses API initialization
    class MockProcessor:
        def assess_warranty_eligibility(self, analysis: str) -> dict:
            processor = VisionProcessor.__new__(VisionProcessor)
            return processor.assess_warranty_eligibility(analysis)
        
        def extract_error_codes(self, analysis: str) -> list[str]:
            processor = VisionProcessor.__new__(VisionProcessor)
            return processor.extract_error_codes(analysis)
    
    processor = MockProcessor()
    
    test_cases = [
        {
            "name": "Manufacturing defect - stress crack",
            "analysis": "Product shows stress crack from manufacturing defect in the glass panel. No impact points visible. Material failure at weld joint indicates production flaw.",
        },
        {
            "name": "User damage - drop impact",
            "analysis": "Clear impact damage visible with dent from external force. Drop damage evident from collision marks and physical abuse patterns.",
        },
        {
            "name": "Safety hazard - electrical issue",
            "analysis": "Visible burn marks and fire hazard indicators. Electrical components show overheating and melting. Immediate safety concern.",
        },
        {
            "name": "Assembly issue - missing component",
            "analysis": "Product appears to have missing component in the assembly. Loose connection visible and not properly seated. Installation error likely.",
        },
        {
            "name": "Mixed indicators",
            "analysis": "Some manufacturing defect signs but also shows water damage and corrosion. Difficult to determine primary cause.",
        },
        {
            "name": "Error codes visible",
            "analysis": "Display shows error code E3 and F12. Also mentions ERROR 404 in the documentation visible in image.",
        },
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n{i}. {case['name']}")
        print(f"   Analysis: \"{case['analysis'][:60]}...\"")
        
        result = processor.assess_warranty_eligibility(case['analysis'])
        
        print(f"   → Recommended Action: {result['recommended_action'].upper()}")
        print(f"   → Reasoning: {result['reasoning']}")
        print(f"   → Confidence: {result['confidence']:.2f}")
        
        indicators = result['indicators']
        print(f"   → Indicators: Mfg:{indicators['manufacturing_defects']} "
              f"User:{indicators['user_damage']} "
              f"Safety:{indicators['safety_issues']} "
              f"Assembly:{indicators['assembly_issues']}")
        
        # Test error code extraction
        error_codes = processor.extract_error_codes(case['analysis'])
        if error_codes:
            print(f"   → Error Codes: {', '.join(error_codes)}")


def test_agent_card():
    """Verify agent card is valid JSON."""
    print("\n" + "=" * 80)
    print("TEST: Agent Card")
    print("=" * 80)
    
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
    print("\n" + "=" * 80)
    print("SERVER TESTING EXAMPLES")
    print("=" * 80)
    
    # Create test image data
    test_image = create_test_image()
    image_b64 = base64.b64encode(test_image).decode('ascii')
    
    print("\n1. Test Agent Card:")
    print("curl http://localhost:8082/.well-known/agent-card.json | python -m json.tool")
    
    print("\n2. Test Health Check:")
    print("curl http://localhost:8082/health")
    
    print("\n3. Test Image Analysis (tasks/send):")
    print("curl -X POST http://localhost:8082/ \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{")
    print('    "jsonrpc": "2.0",')
    print('    "method": "tasks/send",')
    print('    "params": {')
    print('      "id": "vision-test-001",')
    print('      "message": {')
    print('        "role": "user",')
    print('        "parts": [')
    print('          {')
    print('            "type": "text",')
    print('            "text": "Analyze this product image for defects"')
    print('          },')
    print('          {')
    print('            "type": "file",')
    print('            "mimeType": "image/png",')
    print('            "name": "product.png",')
    print(f'            "data": "{image_b64[:100]}..."')
    print('          }')
    print('        ]')
    print('      }')
    print('    },')
    print('    "id": 1')
    print("  }' | python -m json.tool")
    
    print(f"\nNote: The actual base64 data is {len(image_b64)} characters long.")
    print("For real testing, you'd use actual product photos with visible defects.")


def test_mock_scenarios():
    """Test the mock image analysis scenarios."""
    print("\n" + "=" * 80)
    print("TEST: Mock Analysis Scenarios")
    print("=" * 80)
    
    # Simulate different image sizes to trigger different mock responses
    test_sizes = [1000, 2000, 3000, 4000]  # Different sizes trigger different scenarios
    
    from server import MockVisionProcessor
    mock_processor = MockVisionProcessor()
    
    for i, size in enumerate(test_sizes, 1):
        fake_image_data = b'x' * size  # Create fake image data of specific size
        
        print(f"\n{i}. Mock scenario for {size}-byte image:")
        
        analysis, metadata = mock_processor.analyze_image(fake_image_data, "image/png", "")
        
        print(f"   Defect Type: {metadata.get('defect_type', 'unknown')}")
        print(f"   Analysis Preview: \"{analysis[:100]}...\"")
        
        # Test warranty assessment
        warranty = mock_processor.assess_warranty_eligibility(analysis)
        print(f"   → Action: {warranty['recommended_action']}")
        print(f"   → Confidence: {warranty['confidence']:.2f}")


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("VISION AGENT TEST SUITE")
    print("=" * 80)
    
    test_agent_card()
    test_warranty_assessment()
    test_mock_scenarios()
    generate_curl_examples()
    
    print("\n" + "=" * 80)
    print("SETUP INSTRUCTIONS")
    print("=" * 80)
    print("\nTo test with real images:")
    print("1. Set environment variable: export OPENAI_API_KEY=your_key_here")
    print("2. Start the server: cd agents/vision_agent && python server.py")
    print("3. Use the curl examples above with real product images")
    print("\nFor testing without API key:")
    print("1. The server will automatically use mock mode")
    print("2. Mock mode provides realistic customer service scenarios")
    print("3. Perfect for testing the A2A protocol and routing logic")


if __name__ == "__main__":
    main()