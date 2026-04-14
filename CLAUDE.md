# CLAUDE.md — Instructions for Claude Code

## Project Overview

This is the experiment harness for the MMA2A research paper. MMA2A is a modality-native routing layer for the A2A (Agent-to-Agent) protocol. We're comparing three pipelines on a cross-modal customer service benchmark:

1. **Text-BN** (baseline): All inter-agent messages serialized to text via STT/captioning before A2A exchange
2. **MMA2A** (ours): Route voice/image/text parts natively when the receiving agent supports the modality
3. **Oracle**: Single multimodal model (Gemini 1.5 Pro) processes everything in one call

## Key Architecture

- Each agent is a standard **A2A server** exposing an Agent Card at `/.well-known/agent-card.json`
- The **Modality-Aware Router (MAR)** intercepts `tasks/send` calls, checks the destination's Agent Card for `inputModes`, and decides whether to forward the part natively or transcode to text
- The **Task Orchestrator** splits cross-modal tasks into sub-tasks and dispatches them in parallel where possible
- Communication uses **JSON-RPC 2.0 over HTTP** with SSE for streaming

## Implementation Order

Build in this order — each step is independently testable:

1. **Benchmark data** (`benchmark/data/`): Generate 50 tasks first as a smoke test, then scale to 1,200
2. **Text Agent**: Simplest A2A server — accepts TextPart, queries a knowledge base, returns TextPart
3. **Voice Agent**: Accepts audio/wav FilePart, runs Whisper, returns TextPart with transcript + analysis
4. **Vision Agent**: Accepts image/png FilePart, runs VQA model, returns TextPart with analysis
5. **MAR**: Routing proxy — reads Agent Cards, applies routing rule from Eq. 1 in the paper
6. **Orchestrator**: Task decomposition + parallel dispatch + result merging
7. **Text-BN pipeline**: Wire everything through MAR with forced text serialization
8. **MMA2A pipeline**: Wire through MAR with modality-native routing enabled
9. **Oracle pipeline**: Direct Gemini API call with all modalities
10. **Evaluation**: Run all three, compute metrics, generate LaTeX tables

## Tech Stack

- Python 3.11+
- A2A SDK: `pip install a2a-sdk` (from github.com/a2aproject/A2A)
- Model serving: `vllm` for LLMs, `faster-whisper` for STT, `transformers` for vision
- API clients: `openai`, `together`, `google-generativeai`
- Instrumentation: `opentelemetry-api`, `opentelemetry-sdk`
- Config: YAML files in `configs/`

## Config System

Three configs in `configs/`:
- `api_mode.yaml` — uses hosted APIs, no GPU needed
- `single_gpu.yaml` — self-hosted on 1× A100
- `full_cluster.yaml` — self-hosted on 4× A100

Each config specifies: model names, endpoints, API keys (via env vars), and pipeline flags.

## A2A Protocol Notes

- Agent Cards use `/.well-known/agent-card.json` (NOT agent.json)
- Part types in v0.2: TextPart, FilePart, DataPart
- FilePart carries audio/images with `mimeType` field (renamed to `mediaType` in v1.0)
- Streaming uses SSE via `tasks/sendSubscribe`
- Pin to A2A SDK version matching v0.2 spec

## Testing

- Each agent should be independently testable: `curl` to its A2A endpoint with a sample task
- MAR should have unit tests for routing decisions (mock Agent Cards)
- End-to-end test: single task through full pipeline, verify correct routing path

## Metrics to Collect

For every task, record:
- `task_id`, `category`, `pipeline` (text-bn / mma2a / oracle)
- `tca`: 1 if ground_truth_action matches, 0 otherwise
- `e2e_latency_ms`: wall-clock from task submit to final artifact
- `bandwidth_bytes`: total HTTP payload across all A2A calls for this task
- `routing_decisions`: list of {part_modality, destination_agent, action: native|transcode}
- OpenTelemetry trace ID for latency breakdown

## Important Constraints

- Llama-3-70B at 4-bit quantization barely fits on A100 80GB — monitor VRAM usage
- Whisper-large-v3 needs ~10GB VRAM — if sharing a GPU, load/unload sequentially
- For API mode, respect rate limits: OpenAI (500 RPM), Together (varies), Gemini (60 RPM)
- All results go in `results/` as timestamped JSON files
