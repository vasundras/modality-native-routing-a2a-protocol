#!/usr/bin/env python3
"""Test script for the Text Agent.

Run with: python test_agent.py

This tests the agent locally without starting the server.
For server testing, use curl commands after starting the server.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from knowledge_base import (
    analyze_situation,
    format_product_info,
    format_troubleshooting,
    get_product_by_sku,
    search_products,
    search_troubleshooting,
)


def test_product_search():
    """Test product search functionality."""
    print("=" * 60)
    print("TEST: Product Search")
    print("=" * 60)
    
    print("\n1. Search by SKU (BM3K-2024):")
    product = get_product_by_sku("BM3K-2024")
    if product:
        print(format_product_info(product))
    else:
        print("ERROR: Product not found")
    
    print("\n2. Search by name (blender):")
    products = search_products("blender")
    for p in products:
        print(f"  - {p.name} ({p.sku})")
    
    print("\n3. Search by feature (lifetime):")
    products = search_products("lifetime")
    for p in products:
        print(f"  - {p.name} ({p.sku})")


def test_troubleshooting():
    """Test troubleshooting search."""
    print("\n" + "=" * 60)
    print("TEST: Troubleshooting Search")
    print("=" * 60)
    
    print("\n1. Search for router issues:")
    entries = search_troubleshooting("router")
    for e in entries:
        print(format_troubleshooting(e))
    
    print("\n2. Search for error E3:")
    entries = search_troubleshooting("E3")
    for e in entries:
        print(format_troubleshooting(e))


def test_situation_analysis():
    """Test situation analysis and action recommendations."""
    print("\n" + "=" * 60)
    print("TEST: Situation Analysis")
    print("=" * 60)
    
    test_cases = [
        {
            "name": "Dropped product",
            "voice": "I dropped my BlenderMax 3000 and the blade is bent",
            "image": "Visible crack on housing and bent blade assembly",
        },
        {
            "name": "DOA product",
            "voice": "I just unboxed this and it has a crack in it",
            "image": "Product still in packaging with visible defect",
        },
        {
            "name": "Safety hazard",
            "voice": "My toaster is sparking when I use it",
            "image": "Blackened heating element with burn marks",
        },
        {
            "name": "Water damage",
            "voice": "I accidentally washed my earbuds in the laundry",
            "image": "Earbuds showing water residue",
        },
        {
            "name": "Assembly help",
            "voice": "I'm on step 4 and don't know which screw to use",
            "image": None,
        },
    ]
    
    for case in test_cases:
        print(f"\nCase: {case['name']}")
        print(f"  Voice: {case['voice']}")
        if case.get('image'):
            print(f"  Image: {case['image']}")
        
        result = analyze_situation(
            voice_transcript=case['voice'],
            image_description=case.get('image'),
        )
        print(f"  → Action: {result['recommended_action']}")
        print(f"  → Reasoning: {result['reasoning']}")
        print(f"  → Confidence: {result['confidence']:.0%}")


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
    print(f"Input Modes: {card['defaultInputModes']}")
    print(f"Output Modes: {card['defaultOutputModes']}")
    print(f"Skills: {len(card['skills'])}")
    for skill in card['skills']:
        print(f"  - {skill['name']}: {skill['description'][:50]}...")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("TEXT AGENT TEST SUITE")
    print("=" * 60)
    
    test_agent_card()
    test_product_search()
    test_troubleshooting()
    test_situation_analysis()
    
    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)
    print("\nTo test the server, run:")
    print("  cd agents/text_agent && python server.py")
    print("\nThen in another terminal:")
    print('  curl http://localhost:8001/.well-known/agent-card.json')
    print('  curl -X POST http://localhost:8001/ \\')
    print('    -H "Content-Type: application/json" \\')
    print('    -d \'{"jsonrpc":"2.0","method":"tasks/send","params":{"id":"test-1","message":{"role":"user","parts":[{"type":"text","text":"What is the warranty on the BlenderMax 3000?"}]}},"id":1}\'')


if __name__ == "__main__":
    main()
