# MMA2A Experiments

**Paper:** "Beyond Text-as-Lingua-Franca: Modality-Native Routing in A2A Networks"
**Goal:** Validate that modality-native A2A routing beats text-bottleneck pipelines on cross-modal tasks.


## Hypothesis

> For tasks requiring cross-modal reasoning, modality-native routing over A2A — where agents exchange voice, image, and text parts directly — achieves lower end-to-end latency and higher task completion accuracy than a text-bottleneck pipeline that serializes all modalities to text before inter-agent communication.


## Folder Structure

```
mma2a-experiments/
├── EXPERIMENT.md          ← you are here
├── CLAUDE.md              ← instructions for Claude Code
├── agents/
│   ├── voice/             ← Voice agent (Whisper + Bark), A2A server
│   ├── vision/            ← Vision agent (LLaVA-NeXT), A2A server
│   └── text/              ← Text agent (Llama-3-70B), A2A server
├── mar/                   ← Modality-Aware Router
├── orchestrator/          ← Task decomposition + result merging
├── benchmark/
│   ├── data/              ← CrossModal-CS task definitions (JSON)
│   └── annotations/       ← Ground truth labels
├── configs/
│   ├── api_mode.yaml      ← $8-15 budget: API-hosted models
│   ├── single_gpu.yaml    ← $5-10 budget: single A100, self-hosted
│   └── full_cluster.yaml  ← $25-45 budget: 4× A100 distributed
├── scripts/
│   ├── run_experiment.py  ← Main experiment runner
│   ├── evaluate.py        ← Compute TCA, latency, bandwidth metrics
│   └── generate_tables.py ← Produce LaTeX tables from results
└── results/               ← Experiment output (JSON + traces)
```


## Three Experiment Configurations

### 1. API Mode ($8–15)
No GPU needed. Run everything on your laptop with Docker Compose.

| Agent | Backend | Cost |
|-------|---------|------|
| Voice | OpenAI Whisper API ($0.006/min) + TTS API | ~$1 |
| Vision | GPT-4o-mini with image input (~$0.0002/query) | ~$0.15 |
| Text | Llama-3-70B via Together AI ($0.90/1M tokens) | ~$5 |
| Oracle | Gemini 1.5 Pro API | ~$3 |

### 2. Single GPU ($5–10)
Rent one A100 80GB on RunPod spot (~$0.79/hr). Self-host all models.

- Whisper-large-v3 (native)
- LLaVA-NeXT-7B (fits alongside other models)
- Llama-3-70B-4bit (AWQ quantized, ~40GB VRAM)
- Caveat: run models sequentially, not in parallel (single GPU)

### 3. Full Cluster ($25–45)
4× A100 80GB on RunPod/Lambda spot for 8 hours. One model per node.
This is what the paper describes. Most realistic distributed A2A test.


## How to Run (Claude Code)

### Step 1: Setup
```bash
cd mma2a-experiments
pip install -r requirements.txt
# Set API keys in .env (for API mode)
cp .env.example .env
```

### Step 2: Pick a config
```bash
# API mode (cheapest, no GPU)
python scripts/run_experiment.py --config configs/api_mode.yaml

# Single GPU (RunPod)
python scripts/run_experiment.py --config configs/single_gpu.yaml

# Full cluster
python scripts/run_experiment.py --config configs/full_cluster.yaml
```

### Step 3: Evaluate
```bash
python scripts/evaluate.py --results results/latest/
python scripts/generate_tables.py --results results/latest/ --output ../multimodal_a2a_paper_tables.tex
```


## What Each Script Does

### `run_experiment.py`
1. Starts A2A agent servers (or configures API endpoints)
2. Loads benchmark tasks from `benchmark/data/`
3. Runs each task through three pipelines: Text-BN, MMA2A, Oracle
4. Records latency (via OpenTelemetry spans), accuracy, and bandwidth
5. Saves raw results to `results/`

### `evaluate.py`
1. Loads results JSON
2. Computes: TCA (overall + per-category), median E2E latency ± IQR, bandwidth per task
3. Runs paired bootstrap significance test (n=10,000 resamples)
4. Outputs summary table to stdout + JSON

### `generate_tables.py`
1. Reads evaluation output
2. Produces LaTeX table fragments matching the paper's table format
3. Drop these directly into the .tex file


## Benchmark Construction Guide

The benchmark needs 1,200 tasks across 4 categories. Here's how to build it cheaply:

### Quick path (synthetic, ~2 hours)
- **Images:** Use Amazon product review images (publicly available) or COCO dataset
- **Voice:** Synthesize from text scripts using OpenAI TTS API or Bark
- **Text KB:** Write 50 product FAQ entries as your knowledge base
- **Labels:** Since you control the generation, ground truth is deterministic

### Better path (semi-real, ~1 day)
- **Images:** Photograph 20-30 real products with simulated defects
- **Voice:** Record yourself + 2-3 friends describing issues (5-15s clips)
- **Text KB:** Scrape public product support pages
- **Labels:** Annotate with 3 raters, compute Cohen's kappa

### Each task is a JSON file:
```json
{
  "task_id": "defect_001",
  "category": "product_defect_report",
  "modalities_required": ["voice", "image", "text"],
  "voice_input": "data/audio/defect_001.wav",
  "image_input": "data/images/defect_001.jpg",
  "text_context": "Product: BlenderMax 3000. Warranty: 2 years.",
  "ground_truth_action": "initiate_return",
  "ground_truth_reason": "Physical damage from drop, grinding noise confirms motor damage, within warranty period"
}
```


## Key Dependencies

```
# A2A SDK
a2a-sdk              # Official Python SDK from github.com/a2aproject/A2A

# Models (for self-hosted mode)
openai-whisper       # or faster-whisper for optimized inference
transformers         # LLaVA-NeXT, BLIP-2
vllm                 # Llama-3-70B serving with quantization support
bark                 # TTS synthesis

# APIs (for API mode)
openai               # Whisper API, GPT-4o-mini
together             # Llama-3-70B hosted
google-generativeai  # Gemini 1.5 Pro (oracle)

# Instrumentation
opentelemetry-api
opentelemetry-sdk
opentelemetry-exporter-jaeger

# Evaluation
numpy
scipy                # Bootstrap significance testing
```


## Metrics Checklist

Before writing results into the paper, verify:

- [ ] TCA computed as exact-match on ground_truth_action (not fuzzy)
- [ ] E2E latency is wall-clock median over 3 runs (not mean — outliers skew)
- [ ] Bandwidth measured at A2A channel level (HTTP payload size), not including TCP overhead
- [ ] Paired bootstrap test confirms p < 0.001 for TCA difference
- [ ] Per-category breakdown matches overall numbers (weighted average check)
- [ ] Latency breakdown stages sum to within 5% of total E2E (accounting for parallelism)
- [ ] Report IQR alongside median for all latency figures


## Known Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLaVA-NeXT latency higher than expected | Latency gains shrink | Use LLaVA-7B or Qwen-VL as fallback |
| Llama-3-70B OOM at 4-bit on single A100 | Can't run single-GPU config | Use Llama-3-8B or switch to API mode |
| Synthetic voice data too clean | Inflates accuracy for both pipelines | Add background noise augmentation |
| Small benchmark (1,200 tasks) | Significance concerns | Bootstrap test handles this; report confidence intervals |
| A2A SDK version mismatch | Agent Card schema differs | Pin SDK version in requirements.txt |
