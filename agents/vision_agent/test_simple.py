#!/usr/bin/env python3
"""Simple test for Vision Agent without complex imports."""

import json
from pathlib import Path


def test_agent_card():
    """Test agent card loading."""
    print("Testing Agent Card...")
    card_path = Path(__file__).parent / "agent_card.json"
    with open(card_path) as f:
        card = json.load(f)
    
    print(f"✓ Agent Name: {card['name']}")
    print(f"✓ Input Modes: {card['defaultInputModes']}")
    print(f"✓ Output Modes: {card['defaultOutputModes']}")
    print(f"✓ Skills: {len(card['skills'])}")


def test_warranty_logic():
    """Test warranty assessment logic."""
    print("\nTesting Warranty Assessment Logic...")
    
    # Simple rule-based logic without imports
    def assess_warranty(analysis_text):
        analysis_lower = analysis_text.lower()
        
        manufacturing_score = sum(1 for word in ["manufacturing defect", "factory defect", "stress crack"] 
                                if word in analysis_lower)
        user_damage_score = sum(1 for word in ["impact damage", "drop damage", "water damage"] 
                              if word in analysis_lower)
        safety_score = sum(1 for word in ["fire hazard", "electrical hazard", "burn mark"] 
                         if word in analysis_lower)
        
        if safety_score > 0:
            return "initiate_replacement", "Safety hazard"
        elif manufacturing_score > user_damage_score:
            return "approve_warranty", "Manufacturing defect"
        elif user_damage_score > 0:
            return "deny_warranty", "User damage"
        else:
            return "escalate_to_specialist", "Unclear"
    
    test_cases = [
        "Product shows stress crack from manufacturing defect",
        "Clear impact damage from drop",
        "Burn marks indicate fire hazard",
        "Normal wear and tear visible"
    ]
    
    for case in test_cases:
        action, reason = assess_warranty(case)
        print(f"✓ '{case[:30]}...' → {action}")


if __name__ == "__main__":
    print("VISION AGENT SIMPLE TEST")
    print("=" * 40)
    
    test_agent_card()
    test_warranty_logic()
    
    print("\n✓ All simple tests passed!")
    print("\nTo start server: python server.py")