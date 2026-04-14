# A2A v0.2 Protocol Compliance

This document outlines how the MMA2A system implements the A2A (Agent-to-Agent) v0.2 protocol specification.

## ✅ **Core Protocol Compliance**

### **1. JSON-RPC 2.0 Transport**
- All inter-agent communication uses JSON-RPC 2.0 over HTTP
- Proper request/response format with `jsonrpc`, `method`, `params`, and `id` fields
- Error handling follows JSON-RPC 2.0 specification

### **2. Agent Card Discovery**
- Each agent exposes its capabilities at `/.well-known/agent-card.json`
- Agent Cards include `defaultInputModes`, `defaultOutputModes`, `capabilities`, and `skills`
- MAR uses Agent Cards for capability-based routing decisions

### **3. Part-based Message Passing**
- Messages contain `parts` array with typed content (`TextPart`, `FilePart`)
- `FilePart` includes `mimeType` field (A2A v0.2 format, not v1.0 `mediaType`)
- Parts are routed individually based on modality and destination capabilities

### **4. Task States**
- Valid A2A v0.2 task states: `submitted`, `working`, `input-required`, `completed`, `canceled`, `failed`, `unknown`
- SSE streams use `working` state with descriptive status messages
- No custom states like "transcribing" or "analyzing"

### **5. Artifact Format**
- All artifacts include required `index` field for ordering
- Artifacts have `name` and `parts` fields as specified
- SSE streaming artifacts include `append` flag for incremental updates

## 🔀 **MMA2A Routing Implementation**

### **Equation 1: Part-Level Routing Rule**
The MAR implements the core MMA2A routing rule at the **part level**:

```
For each part P in message M to agent A:
  if A.inputModes.supports(P.modality):
    route(P, A, "native")
  else:
    route(P, A, "transcode_to_text")
```

**Key Distinction:**
- **Part-level routing** (MAR's responsibility): Decides how to deliver each message part
- **Agent-level targeting** (Orchestrator's responsibility): Decides which agent should handle the task

### **Text-BN Baseline Comparison**
- `force_text_mode=true`: All non-text parts transcoded regardless of destination capabilities
- `force_text_mode=false`: Native MMA2A routing based on Agent Card `inputModes`

## 📡 **SSE Streaming Format**

### **Simplified Envelope Format**
The implementation uses a simplified SSE envelope format suitable for the research context:

```json
data: {"type": "status", "status": {"state": "working", "timestamp": "...", "message": "Processing..."}}
data: {"type": "artifact", "artifact": {"index": 0, "name": "response", "parts": [...], "append": false}}
data: [DONE]
```

**Note:** Production A2A implementations may use different SSE envelope formats. This format is optimized for the MMA2A research evaluation.

## 🏗️ **Architecture Components**

### **1. Agents (Text, Voice, Vision)**
- **Compliance**: Full A2A v0.2 servers with Agent Cards
- **Endpoints**: `/.well-known/agent-card.json`, `/health`, JSON-RPC at `/`
- **Methods**: `tasks/send`, `tasks/sendSubscribe`, `tasks/get`, `tasks/cancel`

### **2. Modality-Aware Router (MAR)**
- **Role**: Routing proxy implementing MMA2A logic
- **Function**: Reads destination Agent Cards, applies part-level routing rules
- **Innovation**: Native routing when supported, transcoding when necessary

### **3. Task Orchestrator**
- **Role**: Cross-modal task decomposition and coordination
- **Function**: Splits tasks into parallel sub-tasks, manages dependencies
- **Scope**: Agent-level targeting and result synthesis

## 🔧 **Implementation Notes**

### **A2A v0.2 Specific Features**
1. **FilePart.mimeType**: Uses v0.2 field name (not v1.0 `mediaType`)
2. **Agent Card Format**: Compatible with v0.2 specification
3. **Task State Names**: Strict adherence to v0.2 allowed states
4. **Artifact Indexing**: Required `index` field on all artifacts

### **Research-Specific Adaptations**
1. **Mock Transcoding**: Simplified transcoding services for evaluation
2. **Deterministic Routing**: Consistent routing decisions for reproducible results
3. **Comprehensive Logging**: Detailed routing decisions and performance metrics
4. **Baseline Comparison**: Text-BN mode for controlled comparison

## 📊 **Evaluation Metrics**

The system collects A2A-compliant metrics for research evaluation:

- **Task Completion Accuracy (TCA)**: Binary success metric per task
- **End-to-End Latency**: Wall-clock time from submission to completion
- **Bandwidth Usage**: Total HTTP payload size across all A2A calls
- **Routing Decisions**: Part-level routing choices (native vs transcode)
- **OpenTelemetry Traces**: Distributed tracing for latency breakdown

## 🚀 **Production Readiness Notes**

For production deployment beyond research evaluation:

1. **Authentication**: Add proper A2A authentication schemes
2. **Error Recovery**: Implement robust retry and fallback mechanisms  
3. **Rate Limiting**: Add per-agent rate limiting and backpressure
4. **Monitoring**: Enhanced observability and alerting
5. **Security**: Input validation, sanitization, and access controls

---

**Version**: A2A v0.2 compliant  
**Last Updated**: April 2026  
**Implementation**: MMA2A Research System