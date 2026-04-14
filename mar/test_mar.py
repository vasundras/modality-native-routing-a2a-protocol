#!/usr/bin/env python3
"""Test script for the Modality-Aware Router (MAR).

Run with: python test_mar.py

This tests the MAR routing logic and provides examples for server testing.
"""

import asyncio
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agent_registry import AgentRegistry, AgentInfo
from routing_engine import RoutingEngine, RoutingDecision


def create_mock_agent_cards():
    """Create mock agent cards for testing."""
    return {
        "text_agent": {
            "name": "TextAgent",
            "url": "http://localhost:8001",
            "defaultInputModes": ["text"],
            "defaultOutputModes": ["text"],
            "capabilities": {"streaming": True}
        },
        "voice_agent": {
            "name": "VoiceAgent", 
            "url": "http://localhost:8081",
            "defaultInputModes": ["voice"],
            "defaultOutputModes": ["text"],
            "capabilities": {"streaming": True}
        },
        "vision_agent": {
            "name": "VisionAgent",
            "url": "http://localhost:8082", 
            "defaultInputModes": ["image"],
            "defaultOutputModes": ["text"],
            "capabilities": {"streaming": True}
        }
    }


async def test_agent_registry():
    """Test agent registry functionality."""
    print("=" * 80)
    print("TEST: Agent Registry")
    print("=" * 80)
    
    registry = AgentRegistry(cache_ttl_seconds=60)
    mock_cards = create_mock_agent_cards()
    
    # Manually register mock agents (bypassing HTTP calls)
    for name, card in mock_cards.items():
        agent_info = AgentInfo(name, card["url"], card)
        registry.agents[name] = agent_info
        print(f"✓ Registered {name} with input modes: {agent_info.input_modes}")
    
    # Test modality queries
    print(f"\n✓ Text agents: {[a.name for a in registry.find_agents_for_modality('text')]}")
    print(f"✓ Voice agents: {[a.name for a in registry.find_agents_for_modality('voice')]}")
    print(f"✓ Image agents: {[a.name for a in registry.find_agents_for_modality('image')]}")
    
    # Test best agent selection
    best_text = registry.get_best_agent_for_modality("text")
    best_voice = registry.get_best_agent_for_modality("voice")
    best_image = registry.get_best_agent_for_modality("image")
    
    print(f"\n✓ Best for text: {best_text.name if best_text else 'None'}")
    print(f"✓ Best for voice: {best_voice.name if best_voice else 'None'}")
    print(f"✓ Best for image: {best_image.name if best_image else 'None'}")
    
    await registry.close()


async def test_routing_engine():
    """Test routing engine logic."""
    print("\n" + "=" * 80)
    print("TEST: Routing Engine")
    print("=" * 80)
    
    # Setup
    registry = AgentRegistry()
    mock_cards = create_mock_agent_cards()
    
    for name, card in mock_cards.items():
        agent_info = AgentInfo(name, card["url"], card)
        registry.agents[name] = agent_info
    
    # Test both MMA2A and Text-BN modes
    for force_text in [False, True]:
        mode_name = "Text-BN" if force_text else "MMA2A"
        print(f"\n--- {mode_name} Mode ---")
        
        engine = RoutingEngine(registry, force_text_mode=force_text)
        
        # Test cases
        test_messages = [
            {
                "name": "Text-only message",
                "message": {
                    "role": "user",
                    "parts": [
                        {"type": "text", "text": "What is the warranty on BlenderMax 3000?"}
                    ]
                },
                "target": "text_agent"
            },
            {
                "name": "Voice message to voice agent",
                "message": {
                    "role": "user", 
                    "parts": [
                        {"type": "file", "mimeType": "audio/wav", "name": "complaint.wav", "data": "base64data"}
                    ]
                },
                "target": "voice_agent"
            },
            {
                "name": "Voice message to text agent",
                "message": {
                    "role": "user",
                    "parts": [
                        {"type": "file", "mimeType": "audio/wav", "name": "question.wav", "data": "base64data"}
                    ]
                },
                "target": "text_agent"
            },
            {
                "name": "Image message to vision agent",
                "message": {
                    "role": "user",
                    "parts": [
                        {"type": "file", "mimeType": "image/png", "name": "defect.png", "data": "base64data"}
                    ]
                },
                "target": "vision_agent"
            },
            {
                "name": "Image message to text agent",
                "message": {
                    "role": "user",
                    "parts": [
                        {"type": "file", "mimeType": "image/png", "name": "product.png", "data": "base64data"}
                    ]
                },
                "target": "text_agent"
            },
            {
                "name": "Multi-modal message",
                "message": {
                    "role": "user",
                    "parts": [
                        {"type": "text", "text": "Analyze this defect report"},
                        {"type": "file", "mimeType": "audio/wav", "name": "complaint.wav", "data": "base64data"},
                        {"type": "file", "mimeType": "image/png", "name": "damage.png", "data": "base64data"}
                    ]
                },
                "target": "text_agent"
            }
        ]
        
        for test_case in test_messages:
            print(f"\n  {test_case['name']} → {test_case['target']}:")
            
            routed_msg, decisions = await engine.route_message(test_case["message"], test_case["target"])
            
            for decision in decisions:
                part_type = decision.part.get("type")
                modality = decision._get_part_modality()
                print(f"    {part_type}({modality}) → {decision.action} ({decision.reasoning[:50]}...)")
    
    await registry.close()


def test_routing_decisions():
    """Test routing decision logic."""
    print("\n" + "=" * 80)
    print("TEST: Routing Decision Logic")
    print("=" * 80)
    
    # Test part modality detection
    test_parts = [
        {"type": "text", "text": "Hello"},
        {"type": "file", "mimeType": "audio/wav", "name": "test.wav"},
        {"type": "file", "mimeType": "image/png", "name": "test.png"},
        {"type": "file", "mimeType": "application/pdf", "name": "test.pdf"},
    ]
    
    for part in test_parts:
        decision = RoutingDecision(part, "test_agent", "native", "test")
        modality = decision._get_part_modality()
        print(f"✓ {part} → modality: {modality}")


def generate_curl_examples():
    """Generate curl examples for testing the MAR server."""
    print("\n" + "=" * 80)
    print("MAR SERVER TESTING EXAMPLES")
    print("=" * 80)
    
    print("\n1. Check MAR Health:")
    print("curl http://localhost:8080/health | python -m json.tool")
    
    print("\n2. List Registered Agents:")
    print("curl http://localhost:8080/agents | python -m json.tool")
    
    print("\n3. Get Routing Stats:")
    print("curl http://localhost:8080/routing-stats | python -m json.tool")
    
    print("\n4. Test Text Message Routing:")
    print("curl -X POST http://localhost:8080/ \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{")
    print('    "jsonrpc": "2.0",')
    print('    "method": "tasks/send",')
    print('    "params": {')
    print('      "id": "mar-test-001",')
    print('      "message": {')
    print('        "role": "user",')
    print('        "parts": [')
    print('          {')
    print('            "type": "text",')
    print('            "text": "What is the warranty on BlenderMax 3000?"')
    print('          }')
    print('        ]')
    print('      }')
    print('    },')
    print('    "id": 1')
    print("  }' | python -m json.tool")
    
    print("\n5. Test Multi-modal Message Routing:")
    print("curl -X POST http://localhost:8080/ \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{")
    print('    "jsonrpc": "2.0",')
    print('    "method": "tasks/send",')
    print('    "params": {')
    print('      "id": "mar-test-002",')
    print('      "message": {')
    print('        "role": "user",')
    print('        "parts": [')
    print('          {')
    print('            "type": "text",')
    print('            "text": "Analyze this product defect"')
    print('          },')
    print('          {')
    print('            "type": "file",')
    print('            "mimeType": "image/png",')
    print('            "name": "defect.png",')
    print('            "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAI9jGL7ZgAAAABJRU5ErkJggg=="')
    print('          }')
    print('        ]')
    print('      }')
    print('    },')
    print('    "id": 2')
    print("  }' | python -m json.tool")
    
    print("\n6. Toggle Text-BN Mode:")
    print("curl -X POST http://localhost:8080/force-text-mode?enable=true")
    print("curl -X POST http://localhost:8080/force-text-mode?enable=false")


async def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("MODALITY-AWARE ROUTER (MAR) TEST SUITE")
    print("=" * 80)
    
    await test_agent_registry()
    await test_routing_engine()
    test_routing_decisions()
    generate_curl_examples()
    
    print("\n" + "=" * 80)
    print("SETUP INSTRUCTIONS")
    print("=" * 80)
    print("\nTo test the full system:")
    print("1. Start all agents:")
    print("   Terminal 1: cd agents/text_agent && python server.py")
    print("   Terminal 2: cd agents/voice_agent && python server.py") 
    print("   Terminal 3: cd agents/vision_agent && python server.py")
    print("2. Start MAR:")
    print("   Terminal 4: cd mar && python server.py")
    print("3. Use the curl examples above to test routing")
    print("\nKey Features:")
    print("• MMA2A Mode: Routes parts natively when supported")
    print("• Text-BN Mode: Forces all parts to text (baseline)")
    print("• Agent Discovery: Automatically finds agents via Agent Cards")
    print("• Routing Decisions: Logged for metrics collection")


if __name__ == "__main__":
    asyncio.run(main())