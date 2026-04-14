#!/bin/bash
# MMA2A System Demo Commands
# Run these in your terminal to interact with the system

echo "🚀 MMA2A System Demo Commands"
echo "================================="

echo ""
echo "1️⃣ Check System Health:"
echo "curl http://localhost:8084/health | python -m json.tool"
echo ""

echo "2️⃣ List Available Task Types:"
echo "curl http://localhost:8084/task-types | python -m json.tool"
echo ""

echo "3️⃣ Simple Text Query:"
echo 'curl -X POST http://localhost:8084/ \'
echo '  -H "Content-Type: application/json" \'
echo '  -d '"'"'{
    "jsonrpc": "2.0",
    "method": "tasks/send",
    "params": {
      "id": "demo_text_001",
      "message": {
        "role": "user",
        "parts": [
          {"type": "text", "text": "What is the warranty on BlenderMax 3000?"}
        ]
      }
    },
    "id": 1
  }'"'"' | python -m json.tool'
echo ""

echo "4️⃣ Multi-Modal Task (Text + Image):"
echo 'curl -X POST http://localhost:8084/ \'
echo '  -H "Content-Type: application/json" \'
echo '  -d '"'"'{
    "jsonrpc": "2.0",
    "method": "tasks/send",
    "params": {
      "id": "demo_multimodal_001",
      "message": {
        "role": "user",
        "parts": [
          {"type": "text", "text": "Analyze this product defect for warranty"},
          {"type": "file", "mimeType": "image/png", "name": "defect.png", "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAI9jQL7ZgAAAABJRU5ErkJggg=="}
        ]
      },
      "metadata": {"benchmark": {"category": "product_defect_report"}}
    },
    "id": 2
  }'"'"' | python -m json.tool'
echo ""

echo "5️⃣ Check MAR Routing Status:"
echo "curl http://localhost:8080/agents | python -m json.tool"
echo ""

echo "6️⃣ Toggle Text-BN Baseline Mode:"
echo "# Enable Text-BN (forces all to text)"
echo 'curl -X POST "http://localhost:8080/force-text-mode?enable=true"'
echo ""
echo "# Disable Text-BN (back to MMA2A native routing)"
echo 'curl -X POST "http://localhost:8080/force-text-mode?enable=false"'
echo ""

echo "7️⃣ Voice + Image Task:"
echo 'curl -X POST http://localhost:8084/ \'
echo '  -H "Content-Type: application/json" \'
echo '  -d '"'"'{
    "jsonrpc": "2.0", 
    "method": "tasks/send",
    "params": {
      "id": "demo_voice_image_001",
      "message": {
        "role": "user",
        "parts": [
          {"type": "file", "mimeType": "audio/wav", "name": "complaint.wav", "data": "UklGRix9AABXQVZFZm10IBAAAAABAAEAQD4AAIB9AAACABAAZGF0YQB9AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"},
          {"type": "file", "mimeType": "image/png", "name": "damage.png", "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAI9jQL7ZgAAAABJRU5ErkJggg=="}
        ]
      }
    },
    "id": 3
  }'"'"' | python -m json.tool'
echo ""

echo "🔍 System Status Check:"
echo "curl -s http://localhost:8084/health && echo '✅ Orchestrator'"
echo "curl -s http://localhost:8080/health && echo '✅ MAR'" 
echo "curl -s http://localhost:8001/health && echo '✅ Text Agent'"
echo "curl -s http://localhost:8081/health && echo '✅ Voice Agent'"
echo "curl -s http://localhost:8082/health && echo '✅ Vision Agent'"