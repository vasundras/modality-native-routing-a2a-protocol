#!/usr/bin/env python3
"""Interactive MMA2A System Demo

Run this script to interact with the MMA2A system through a simple menu.
"""

import json
import requests
import base64
from typing import Dict, Any


class MMA2ADemo:
    def __init__(self):
        self.orchestrator_url = "http://localhost:8084"
        self.mar_url = "http://localhost:8080"
        
    def check_system_health(self) -> Dict[str, bool]:
        """Check if all components are running."""
        services = {
            "Orchestrator (8084)": f"{self.orchestrator_url}/health",
            "MAR (8080)": f"{self.mar_url}/health", 
            "Text Agent (8001)": "http://localhost:8001/health",
            "Voice Agent (8081)": "http://localhost:8081/health",
            "Vision Agent (8082)": "http://localhost:8082/health"
        }
        
        status = {}
        print("🔍 System Health Check:")
        print("-" * 40)
        
        for name, url in services.items():
            try:
                response = requests.get(url, timeout=2)
                is_healthy = response.status_code == 200
                status[name] = is_healthy
                print(f"{'✅' if is_healthy else '❌'} {name}")
            except Exception as e:
                status[name] = False
                print(f"❌ {name} - {str(e)}")
        
        return status
    
    def send_text_query(self, text: str) -> Dict[str, Any]:
        """Send a simple text query."""
        payload = {
            "jsonrpc": "2.0",
            "method": "tasks/send",
            "params": {
                "id": f"demo_text_{hash(text) % 1000:03d}",
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": text}]
                }
            },
            "id": 1
        }
        
        response = requests.post(self.orchestrator_url, json=payload)
        return response.json()
    
    def send_multimodal_task(self, text: str, include_image: bool = True, include_voice: bool = False) -> Dict[str, Any]:
        """Send a multi-modal task."""
        parts = [{"type": "text", "text": text}]
        
        if include_image:
            # Minimal PNG image (1x1 pixel)
            image_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAI9jQL7ZgAAAABJRU5ErkJggg=="
            parts.append({
                "type": "file",
                "mimeType": "image/png", 
                "name": "test_image.png",
                "data": image_data
            })
        
        if include_voice:
            # Minimal WAV audio (silence)
            audio_data = "UklGRix9AABXQVZFZm10IBAAAAABAAEAQD4AAIB9AAACABAAZGF0YQB9AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            parts.append({
                "type": "file",
                "mimeType": "audio/wav",
                "name": "test_audio.wav", 
                "data": audio_data
            })
        
        payload = {
            "jsonrpc": "2.0",
            "method": "tasks/send",
            "params": {
                "id": f"demo_multi_{hash(text) % 1000:03d}",
                "message": {
                    "role": "user",
                    "parts": parts
                },
                "metadata": {"benchmark": {"category": "product_defect_report"}}
            },
            "id": 2
        }
        
        response = requests.post(self.orchestrator_url, json=payload)
        return response.json()
    
    def toggle_text_bn_mode(self, enable: bool) -> Dict[str, Any]:
        """Toggle Text-BN baseline mode."""
        response = requests.post(f"{self.mar_url}/force-text-mode?enable={str(enable).lower()}")
        return response.json()
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """Get MAR routing statistics."""
        response = requests.get(f"{self.mar_url}/agents")
        return response.json()
    
    def print_result_summary(self, result: Dict[str, Any]) -> None:
        """Print a summary of the task result."""
        if "result" in result:
            task_result = result["result"]
            task_id = task_result.get("id", "unknown")
            status = task_result.get("status", {}).get("state", "unknown")
            
            print(f"\n📋 Task Result Summary:")
            print(f"   Task ID: {task_id}")
            print(f"   Status: {status}")
            
            # Show orchestration metadata if available
            metadata = task_result.get("metadata", {})
            if "orchestrator" in metadata:
                orch_meta = metadata["orchestrator"]
                print(f"   Task Type: {orch_meta.get('task_plan', {}).get('task_type', 'unknown')}")
                print(f"   Subtasks: {orch_meta.get('subtasks_executed', 0)}")
                print(f"   Duration: {orch_meta.get('actual_duration', 0):.2f}s")
                
                # Show subtask execution
                exec_summary = orch_meta.get('execution_summary', {})
                if exec_summary:
                    print(f"   Subtask Execution:")
                    for subtask_id, info in exec_summary.items():
                        print(f"     • {subtask_id}: {info.get('status', 'unknown')}")
            
            # Show routing decisions if available
            if "mar_routing" in metadata:
                routing = metadata["mar_routing"]
                print(f"   Target Agent: {routing.get('target_agent', 'unknown')}")
                print(f"   Force Text Mode: {routing.get('force_text_mode', False)}")
                
                decisions = routing.get('routing_decisions', [])
                if decisions:
                    print(f"   Routing Decisions:")
                    for decision in decisions:
                        modality = decision.get('part_modality', 'unknown')
                        action = decision.get('action', 'unknown')
                        print(f"     • {modality} → {action}")
            
            # Show response preview
            response_parts = task_result.get("status", {}).get("message", {}).get("parts", [])
            if response_parts:
                text = response_parts[0].get("text", "")
                preview = text[:200] + "..." if len(text) > 200 else text
                print(f"   Response: {preview}")
        
        elif "error" in result:
            print(f"\n❌ Error: {result['error']}")
    
    def run_interactive_demo(self):
        """Run the interactive demo."""
        print("🚀 MMA2A System Interactive Demo")
        print("=" * 50)
        
        # Check system health first
        health = self.check_system_health()
        if not all(health.values()):
            print("\n⚠️  Some services are not running. Please start all components first.")
            return
        
        print("\n✅ All services are running!")
        
        while True:
            print("\n" + "=" * 50)
            print("Choose a demo option:")
            print("1. Simple text query")
            print("2. Multi-modal task (text + image)")
            print("3. Multi-modal task (text + image + voice)")
            print("4. Toggle Text-BN baseline mode")
            print("5. Check routing statistics")
            print("6. System health check")
            print("0. Exit")
            
            choice = input("\nEnter your choice (0-6): ").strip()
            
            if choice == "0":
                print("👋 Goodbye!")
                break
            
            elif choice == "1":
                text = input("Enter your text query: ").strip()
                if text:
                    print("\n🔄 Processing text query...")
                    result = self.send_text_query(text)
                    self.print_result_summary(result)
            
            elif choice == "2":
                text = input("Enter your query (will include test image): ").strip()
                if text:
                    print("\n🔄 Processing multi-modal task (text + image)...")
                    result = self.send_multimodal_task(text, include_image=True, include_voice=False)
                    self.print_result_summary(result)
            
            elif choice == "3":
                text = input("Enter your query (will include test image + voice): ").strip()
                if text:
                    print("\n🔄 Processing multi-modal task (text + image + voice)...")
                    result = self.send_multimodal_task(text, include_image=True, include_voice=True)
                    self.print_result_summary(result)
            
            elif choice == "4":
                current_mode = input("Enable Text-BN mode? (y/n): ").strip().lower()
                enable = current_mode == 'y'
                result = self.toggle_text_bn_mode(enable)
                mode_name = "Text-BN" if enable else "MMA2A"
                print(f"\n✅ Switched to {mode_name} mode")
            
            elif choice == "5":
                print("\n🔄 Getting routing statistics...")
                stats = self.get_routing_stats()
                print(f"\n📊 Routing Statistics:")
                print(f"   Total Agents: {stats.get('total_agents', 0)}")
                agents = stats.get('agents', {})
                for name, info in agents.items():
                    modes = ', '.join(info.get('input_modes', []))
                    print(f"   • {name}: {modes}")
            
            elif choice == "6":
                self.check_system_health()
            
            else:
                print("❌ Invalid choice. Please try again.")


if __name__ == "__main__":
    demo = MMA2ADemo()
    demo.run_interactive_demo()