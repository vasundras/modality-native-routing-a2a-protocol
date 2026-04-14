# Paper Audit Report: MMA2A

**Paper:** "Beyond Text-as-Lingua-Franca: Modality-Native Routing in A2A Networks"
**Audit date:** April 12, 2026


## CRITICAL ERRORS (must fix before submission)

### 1. Three citation author names are fabricated

| Citation | Paper claims | Actual authors |
|----------|-------------|----------------|
| arXiv:2505.02279 (agent interop survey) | "Abdelaziz et al." | Ehtesham, Singh, Gupta, Kumar |
| arXiv:2601.13671 (orchestration survey) | "F. Chen et al." | Adimulam, Gupta, Kumar |
| arXiv:2508.01531 (gossip coordination) | "R. Patel et al." | Habiba and Khan |

**Severity:** CRITICAL. Wrong author names are the fastest way to get a paper desk-rejected and damage your reputation. Reviewers check citations.

### 2. Agent Card discovery path is wrong

**Paper says:** `/.well-known/agent.json`
**Actual spec:** `/.well-known/agent-card.json`

### 3. gRPC version attribution is wrong

**Paper says:** "as of v0.2 adds gRPC transport"
**Actual:** gRPC support was added in v0.3, not v0.2. v0.2 focused on stateless interactions and JSON-RPC/HTTP bindings.

### 4. GPT-4o-mini pricing is off by 50x

**Paper says:** "~$0.01 per image query"
**Actual:** ~$0.0002 per query ($0.15/1M input tokens, ~765 tokens per image). The $0.01 figure overstates cost by a factor of 50.


## SIGNIFICANT ERRORS (should fix)

### 5. RunPod A100 spot pricing is 2-3x too high

**Paper says:** "$1.50-2.50/hour"
**Actual (April 2026):** ~$0.79/hour spot. This changes the mid-range experiment budget significantly — it's much cheaper than we claimed, which is actually good news for reproducibility.

### 6. Together AI Llama-3-70B pricing is 50% too low

**Paper says:** "~$0.60 per million tokens"
**Actual:** $0.90/1M tokens on Together AI.

### 7. FilePart field name change in A2A v1.0

**Paper says:** `mimeType` field
**Actual:** Renamed to `mediaType` in v1.0. Since we reference v0.2, using `mimeType` is technically correct for that version, but the paper should clarify which spec version it targets.

### 8. Part type consolidation in A2A v1.0

The paper says "A2A defines three part types: TextPart, FilePart, DataPart" — this is correct for v0.2/v0.3 but in the current v1.0 spec, these are consolidated into a unified `Part` message type with fields distinguished by presence. The paper should pin to a specific spec version.


## CLAIMS NEEDING BETTER EVIDENCE

### 9. LLaVA-NeXT 310ms inference — no supporting benchmark exists

No published benchmark confirms LLaVA-NeXT VQA inference at 310ms on A100. LLaVA-NeXT uses up to 2,880 vision tokens (much more than smaller models), and community reports suggest it runs "very slowly" on A100. This number may be optimistic. Either cite a benchmark or caveat it as "measured in our setup" (after you actually run it).

### 10. Llama-3-70B latency (520-680ms) — unclear metric

Is this time-to-first-token or full response generation time? A 200-token response at ~3-5ms/token = 600-1000ms for token generation alone, plus TTFT. The paper should specify.

### 11. Whisper-large-v3 at 420ms — plausible but uncited

420ms for 8 seconds of audio (~52ms per second of speech) is plausible for A100 inference, but no specific benchmark is cited. Reference MLCommons MLPerf Inference v5.1 (September 2025) which includes Whisper benchmarks.

### 12. Llama-3-70B 4-bit on single A100 — technically true but tight

Model weights at 4-bit ≈ 35-45GB. Fits on A100 80GB, but leaves minimal headroom for KV cache. At batch size >1 or context >4K tokens, you'll hit OOM. Paper should note this constraint.


## CLAIMS VERIFIED AS CORRECT

- A2A is JSON-RPC-over-HTTP ✓
- Agent Cards are the capability discovery mechanism ✓
- Task lifecycle states (submitted, working, input-required, completed, failed, canceled) ✓
- tasks/send and tasks/sendSubscribe are correct endpoint names ✓
- SSE is the streaming mechanism ✓
- TaskArtifactUpdateEvent is a real event type ✓
- A2A was contributed to Linux Foundation in 2025 ✓
- OpenAPI-aligned authentication ✓
- Agent Cards have skills array with inputModes/outputModes ✓
- FilePart supports both inline bytes and URI reference ✓
- AgentMaster BERTScore F1 96.3% and G-Eval 87.1% ✓
- AgentMaster authors (Liao, Liao, Gadiraju) ✓
- ACP is from IBM Research ✓
- LACP paper arXiv:2510.13821 by X. Li et al. ✓
- Gemini paper arXiv:2312.11805 ✓
- Gartner 40% prediction ✓
- A2A 50+ technology partners ✓
- 10-second WAV at 16kHz mono ≈ 320KB ✓
- Whisper API $0.006/minute ✓
- GCP T4 spot ~$0.12/hour (approximately correct) ✓
- Inter-annotator κ = 0.81 is strong and plausible ✓
- 34% latency reduction + 8.7pp accuracy — plausible magnitudes if baselines are properly specified ✓


## OVERALL ASSESSMENT

The paper's core hypothesis, architecture, and experimental design are sound. The A2A protocol technical details are mostly correct with a few specific errors. However, there are three categories of problems that would undermine the paper if submitted as-is:

1. **Fabricated author names** (3 citations) — this is the most serious issue and must be fixed immediately.
2. **Wrong protocol details** (discovery path, gRPC version) — factual errors that reviewers familiar with A2A will catch instantly.
3. **Inaccurate pricing** — the reproduction section's cost estimates have errors ranging from 50% to 50x, undermining the practical guidance.

All of these are fixable. The hypothesis and experimental design hold up under scrutiny.
