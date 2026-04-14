# Modality-Native Routing in Agent-to-Agent Networks  
## A Multimodal A2A Protocol Extension

**Companion repository** for the paper (April 2026). This repository contains the implementation, benchmark, configuration, and published run artifacts referenced in the work.

---

## Summary of the paper

The **Agent-to-Agent (A2A)** protocol can carry native audio and images (`FilePart`s), but many deployments still **serialize everything to text** between services. That **text-bottleneck** path drops cues that matter for decisions (e.g., prosody in speech, spatial detail in images).

The paper studies **modality-native routing**: forwarding parts in their **original modality** when the receiving agent’s **Agent Card** says it can consume them. It introduces **MMA2A** (Multimodal Modality-native A2A)—a thin routing layer that inspects capability declarations and routes accordingly, without changing the protocol.

The central empirical finding is a **two-layer requirement**. Native routing **raises task completion accuracy** only when downstream agents use **capable reasoning** (here, an LLM). An **ablation** that replaces LLM reasoning with **keyword matching** wipes out the gap (**36% vs. 36%**): richer signals are delivered but not used. With LLM reasoning, a controlled benchmark (**CrossModal-CS**, 50 tasks, same model and tasks, routing as the variable) shows **MMA2A at 52%** vs. **text-bottleneck at 32%**, with larger gains on vision-heavy categories, at the cost of higher end-to-end latency (native multimodal inference is more expensive).

**Takeaway:** routing is a first-order design knob in multi-agent systems because it controls **what evidence** reaches agents that actually decide.

---

## How to use this companion repository

| Goal | What to do |
|------|------------|
| **Understand the system layout** | See the directory tree below (`agents/`, `mar/`, `orchestrator/`, `benchmark/`, `scripts/`). |
| **Reproduce or extend experiments** | Install dependencies (`requirements.txt`), set `GOOGLE_API_KEY` from `.env.example`, add benchmark audio/images per `benchmark/DATA_SOURCING_GUIDE.md`, start the services (ports in `start_system.sh`), then run `scripts/run_experiment.py` and `scripts/evaluate.py`. |
| **Reinspect published numbers** | Open `results/run2-gemini-reasoning/` (main MMA2A vs. Text-BN run) and `results/run1-keyword-matcher/` (keyword ablation). Optional: `python scripts/compute_stats.py` for McNemar / bootstrap on the paired JSON files. |
| **Protocol / A2A alignment notes** | Read `A2A_COMPLIANCE.md`. |

---

## Repository layout

```
├── agents/              # Text, voice, vision A2A HTTP servers + agent cards
├── mar/                 # Modality-Aware Router (proxy)
├── orchestrator/        # Task decomposition + execution
├── benchmark/
│   ├── data/            # benchmark_tasks_50.json (+ audio/images — see guide)
│   └── DATA_SOURCING_GUIDE.md
├── configs/             # e.g. api_mode.yaml (Gemini 2.5 Flash for published runs)
├── scripts/
│   ├── run_experiment.py   # MMA2A and/or Text-BN runs
│   ├── evaluate.py         # metrics; optional `--latex` table fragments
│   ├── compute_stats.py    # McNemar + bootstrap CI on paired result JSON
│   ├── prep_benchmark_data.py
│   └── generate_tables.py
├── results/
│   ├── run2-gemini-reasoning/   # paper: LLM reasoning, 52% vs 32%
│   ├── run1-keyword-matcher/    # paper: keyword ablation, 36% vs 36%
│   └── dev-runs/                # local scratch (gitignored)
├── web_interface/       # optional demo UI
├── start_system.sh
├── .env.example
└── requirements.txt
```

---

## Prerequisites

- **Google AI API key** for Gemini (`export GOOGLE_API_KEY=...` or copy `.env.example` to `.env`).
- **Benchmark media** referenced from `benchmark/data/benchmark_tasks_50.json`: populate `benchmark/data/audio/` and `benchmark/data/images/` using **`benchmark/DATA_SOURCING_GUIDE.md`** (paths are gitignored for size).

---

## Running the stack (API mode, as in the paper)

1. Copy `.env.example` to `.env` and set `GOOGLE_API_KEY`.
2. Start components (see **`start_system.sh`** for ports and health checks): MAR (**8080**), voice / vision / text agents (**8081**, **8082**, **8001**), orchestrator (**8084**), optional web UI (**8090**).

---

## Running the benchmark

With services up, from the repository root:

```bash
python scripts/run_experiment.py --mode both --tasks 50
python scripts/evaluate.py
python scripts/evaluate.py --latex
```

New runs are written under `results/` as `mma2a_<timestamp>_<run_id>.json` and `text-bn_<timestamp>_<run_id>.json`.

---

## Recomputing statistics from the published paired run

```bash
python scripts/compute_stats.py \
  --mma2a results/run2-gemini-reasoning/mma2a_20260413_165258_afffb9b1bcf7.json \
  --text-bn results/run2-gemini-reasoning/text-bn_20260413_165923_afffb9b1bcf7.json
```

`compute_stats.py` defaults point at these files, so you can run it with **no arguments** after cloning.

---

## Published result bundles

| Location | Role |
|----------|------|
| `results/run2-gemini-reasoning/` | Primary paired run (LLM reasoning); includes `evaluation_*.json` |
| `results/run1-keyword-matcher/` | Keyword-matching ablation |
