#!/usr/bin/env python3
"""Test script for the Task Orchestrator.

Run with: python test_orchestrator.py

This tests task decomposition logic and provides examples for server testing.
"""

import asyncio
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from task_decomposer import TaskDecomposer, TaskType, SubTaskType
from execution_engine import ExecutionEngine


def test_task_decomposition():
    """Test task decomposition logic."""
    print("=" * 80)
    print("TEST: Task Decomposition")
    print("=" * 80)
    
    decomposer = TaskDecomposer()
    
    # Test cases representing different customer service scenarios
    test_cases = [
        {
            "name": "Text-only warranty inquiry",
            "message": {
                "role": "user",
                "parts": [
                    {"type": "text", "text": "What is the warranty on BlenderMax 3000? I bought it 6 months ago."}
                ]
            },
            "context": {"category": "warranty_claim"}
        },
        {
            "name": "Voice complaint with defect",
            "message": {
                "role": "user", 
                "parts": [
                    {"type": "file", "mimeType": "audio/wav", "name": "defect_complaint.wav", "data": "base64data"}
                ]
            },
            "context": {"category": "product_defect_report"}
        },
        {
            "name": "Image-only troubleshooting",
            "message": {
                "role": "user",
                "parts": [
                    {"type": "file", "mimeType": "image/png", "name": "error_screen.png", "data": "base64data"}
                ]
            },
            "context": {"category": "visual_troubleshooting"}
        },
        {
            "name": "Multi-modal defect report",
            "message": {
                "role": "user",
                "parts": [
                    {"type": "text", "text": "I need help with this broken product"},
                    {"type": "file", "mimeType": "audio/wav", "name": "complaint.wav", "data": "base64data"},
                    {"type": "file", "mimeType": "image/png", "name": "damage.png", "data": "base64data"}
                ]
            },
            "context": {"category": "product_defect_report"}
        },
        {
            "name": "Assembly help with image",
            "message": {
                "role": "user",
                "parts": [
                    {"type": "text", "text": "I'm stuck on step 4 of assembly"},
                    {"type": "file", "mimeType": "image/png", "name": "current_state.png", "data": "base64data"}
                ]
            },
            "context": {"category": "assembly_guidance"}
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}")
        
        task_id = f"test_task_{i:03d}"
        plan = decomposer.decompose_task(task_id, test_case["message"], test_case["context"])
        
        print(f"   Task Type: {plan.task_type.value}")
        print(f"   Sub-tasks: {len(plan.sub_tasks)}")
        print(f"   Estimated Duration: {plan.estimated_duration_seconds:.1f}s")
        print(f"   Execution Groups: {len(plan.execution_order)}")
        
        for j, subtask in enumerate(plan.sub_tasks):
            deps = f" (deps: {subtask.dependencies})" if subtask.dependencies else ""
            print(f"     {j+1}. {subtask.id} → {subtask.target_agent} [{subtask.type.value}]{deps}")
        
        print(f"   Execution Order: {plan.execution_order}")


def test_modality_analysis():
    """Test modality analysis logic."""
    print("\n" + "=" * 80)
    print("TEST: Modality Analysis")
    print("=" * 80)
    
    decomposer = TaskDecomposer()
    
    test_messages = [
        {
            "name": "Text only",
            "parts": [{"type": "text", "text": "Help with warranty"}]
        },
        {
            "name": "Voice only", 
            "parts": [{"type": "file", "mimeType": "audio/wav", "name": "complaint.wav"}]
        },
        {
            "name": "Image only",
            "parts": [{"type": "file", "mimeType": "image/png", "name": "defect.png"}]
        },
        {
            "name": "Text + Voice",
            "parts": [
                {"type": "text", "text": "Listen to this"},
                {"type": "file", "mimeType": "audio/wav", "name": "issue.wav"}
            ]
        },
        {
            "name": "All modalities",
            "parts": [
                {"type": "text", "text": "Complete report"},
                {"type": "file", "mimeType": "audio/wav", "name": "description.wav"},
                {"type": "file", "mimeType": "image/png", "name": "evidence.png"}
            ]
        }
    ]
    
    for test in test_messages:
        message = {"role": "user", "parts": test["parts"]}
        modalities = decomposer._analyze_modalities(message)
        
        print(f"\n{test['name']}:")
        for modality, parts in modalities.items():
            print(f"  {modality}: {len(parts)} part(s)")


def test_task_type_detection():
    """Test task type detection logic."""
    print("\n" + "=" * 80)
    print("TEST: Task Type Detection")
    print("=" * 80)
    
    decomposer = TaskDecomposer()
    
    test_texts = [
        ("I dropped my blender and it's making noise", "defect report"),
        ("I'm on step 4 of assembly and stuck", "assembly guidance"),
        ("My router shows error E3 on display", "troubleshooting"),
        ("I want to return this under warranty", "warranty claim"),
        ("The product is broken and won't work", "defect report"),
        ("How do I attach the crossbar?", "assembly guidance"),
        ("Screen is flickering with lines", "troubleshooting"),
        ("Can I get a refund for this?", "warranty claim")
    ]
    
    for text, expected in test_texts:
        message = {"role": "user", "parts": [{"type": "text", "text": text}]}
        detected_type = decomposer._determine_task_type(message)
        
        print(f"'{text[:40]}...' → {detected_type.value}")


def generate_curl_examples():
    """Generate curl examples for testing the orchestrator."""
    print("\n" + "=" * 80)
    print("ORCHESTRATOR SERVER TESTING EXAMPLES")
    print("=" * 80)
    
    print("\n1. Check Orchestrator Health:")
    print("curl http://localhost:8084/health | python -m json.tool")
    
    print("\n2. List Task Types:")
    print("curl http://localhost:8084/task-types | python -m json.tool")
    
    print("\n3. Test Task Decomposition (without execution):")
    print("curl -X POST http://localhost:8084/decompose \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{")
    print('    "task_id": "decompose_test_001",')
    print('    "message": {')
    print('      "role": "user",')
    print('      "parts": [')
    print('        {')
    print('          "type": "text",')
    print('          "text": "I need help with this broken product"')
    print('        },')
    print('        {')
    print('          "type": "file",')
    print('          "mimeType": "image/png",')
    print('          "name": "damage.png",')
    print('          "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAI9jQL7ZgAAAABJRU5ErkJggg=="')
    print('        }')
    print('      ]')
    print('    },')
    print('    "context": {"category": "product_defect_report"}')
    print("  }' | python -m json.tool")
    
    print("\n4. Execute Multi-modal Task:")
    print("curl -X POST http://localhost:8084/ \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{")
    print('    "jsonrpc": "2.0",')
    print('    "method": "tasks/send",')
    print('    "params": {')
    print('      "id": "orchestrator_test_001",')
    print('      "message": {')
    print('        "role": "user",')
    print('        "parts": [')
    print('          {')
    print('            "type": "text",')
    print('            "text": "Analyze this product defect for warranty claim"')
    print('          },')
    print('          {')
    print('            "type": "file",')
    print('            "mimeType": "image/png",')
    print('            "name": "defect.png",')
    print('            "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAI9jQL7ZgAAAABJRU5ErkJggg=="')
    print('          }')
    print('        ]')
    print('      },')
    print('      "metadata": {')
    print('        "benchmark": {"category": "product_defect_report"}')
    print('      }')
    print('    },')
    print('    "id": 1')
    print("  }' | python -m json.tool")
    
    print("\n5. Execute Voice + Image Task:")
    print("curl -X POST http://localhost:8084/ \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{")
    print('    "jsonrpc": "2.0",')
    print('    "method": "tasks/send",')
    print('    "params": {')
    print('      "id": "orchestrator_test_002",')
    print('      "message": {')
    print('        "role": "user",')
    print('        "parts": [')
    print('          {')
    print('            "type": "file",')
    print('            "mimeType": "audio/wav",')
    print('            "name": "complaint.wav",')
    print('            "data": "UklGRix9AABXQVZFZm10IBAAAAABAAEAQD4AAIB9AAACABAAZGF0YQB9AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"')
    print('          },')
    print('          {')
    print('            "type": "file",')
    print('            "mimeType": "image/png",')
    print('            "name": "damage.png",')
    print('            "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAI9jQL7ZgAAAABJRU5ErkJggg=="')
    print('          }')
    print('        ]')
    print('      }')
    print('    },')
    print('    "id": 2')
    print("  }' | python -m json.tool")


async def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("TASK ORCHESTRATOR TEST SUITE")
    print("=" * 80)
    
    test_task_decomposition()
    test_modality_analysis()
    test_task_type_detection()
    generate_curl_examples()
    
    print("\n" + "=" * 80)
    print("FULL SYSTEM TESTING")
    print("=" * 80)
    print("\nTo test the complete MMA2A system:")
    print("1. Start all agents:")
    print("   Terminal 1: cd agents/text_agent && python server.py")
    print("   Terminal 2: cd agents/voice_agent && python server.py")
    print("   Terminal 3: cd agents/vision_agent && python server.py")
    print("2. Start MAR:")
    print("   Terminal 4: cd mar && python server.py")
    print("3. Start Orchestrator:")
    print("   Terminal 5: cd orchestrator && python server.py")
    print("4. Use the curl examples above to test end-to-end orchestration")
    
    print("\n" + "=" * 80)
    print("SYSTEM ARCHITECTURE")
    print("=" * 80)
    print("\nRequest Flow:")
    print("Client → Orchestrator → MAR → Agents")
    print("                ↓")
    print("         Task Decomposition")
    print("         Parallel Execution")
    print("         Result Synthesis")
    
    print("\nKey Features:")
    print("• Cross-modal task decomposition")
    print("• Parallel sub-task execution") 
    print("• Dependency management")
    print("• Result synthesis")
    print("• MMA2A vs Text-BN comparison")


if __name__ == "__main__":
    asyncio.run(main())