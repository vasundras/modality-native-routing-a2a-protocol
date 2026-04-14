#!/bin/bash
# MMA2A System Startup Script

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | grep -v '^\s*$' | xargs)
    echo "✅ Loaded .env"
fi

echo "🚀 Starting MMA2A System Components..."
echo "======================================"

# Check if components are already running
check_port() {
    local port=$1
    local name=$2
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "✅ $name already running on port $port"
        return 0
    else
        echo "❌ $name not running on port $port"
        return 1
    fi
}

echo ""
echo "🔍 Checking current system status:"
check_port 8001 "Text Agent"
check_port 8081 "Voice Agent"
check_port 8082 "Vision Agent"
check_port 8080 "MAR"
check_port 8084 "Orchestrator"
check_port 8090 "Web Interface"

echo ""
echo "📋 System Architecture:"
echo "┌─────────────────────────────────────────┐"
echo "│  Web Interface (8090) - Browser UI     │"
echo "│            ↓                            │"
echo "│  Task Orchestrator (8084)              │"
echo "│            ↓                            │"
echo "│  Modality-Aware Router (8080)          │"
echo "│            ↓                            │"
echo "│  ┌─────────┬─────────┬─────────────┐    │"
echo "│  │Text(8001)│Voice(8081)│Vision(8082)│    │"
echo "│  └─────────┴─────────┴─────────────┘    │"
echo "└─────────────────────────────────────────┘"

echo ""
echo "🌐 Access Points:"
echo "• Web Interface: http://localhost:8090"
echo "• API Health Checks:"
echo "  - Orchestrator: http://localhost:8084/health"
echo "  - MAR: http://localhost:8080/health"
echo "  - Text Agent: http://localhost:8001/health"
echo "  - Voice Agent: http://localhost:8081/health"
echo "  - Vision Agent: http://localhost:8082/health"

echo ""
echo "📝 Usage Instructions:"
echo "1. Open http://localhost:8090 in your browser"
echo "2. Upload images, audio files, or enter text"
echo "3. Select task category and routing mode"
echo "4. Submit to see MMA2A routing in action!"

echo ""
echo "🔄 Routing Modes:"
echo "• MMA2A: Routes parts natively when supported (efficient)"
echo "• Text-BN: Forces all parts to text (baseline comparison)"

echo ""
echo "💡 Example Test Cases:"
echo "• Product Defect: Upload damage photo + describe issue"
echo "• Warranty Claim: Audio complaint + product image"
echo "• Assembly Help: Photo of current progress + question"
echo "• Troubleshooting: Error screen image + description"

echo ""
echo "🛠️ If components aren't running, start them manually:"
echo "Terminal 1: cd agents/text_agent && python server.py"
echo "Terminal 2: cd agents/voice_agent && python server.py"
echo "Terminal 3: cd agents/vision_agent && python server.py"
echo "Terminal 4: cd mar && python server.py"
echo "Terminal 5: cd orchestrator && python server.py"
echo "Terminal 6: cd web_interface && python app.py"

echo ""
echo "✨ Ready to test the MMA2A system!"