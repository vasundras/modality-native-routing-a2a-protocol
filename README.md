# MMA2A experiments

Runnable code for the **CrossModal-CS** benchmark and the **MMA2A** vs **Text-BN** pipelines described in the paper. Configuration for the published runs uses **Gemini 2.5 Flash** via `GOOGLE_API_KEY` (`configs/api_mode.yaml`).

## Layout

```
mma2a-experiments/
├── agents/              # Text, voice, vision A2A HTTP servers + agent cards
├── mar/                 # Modality-Aware Router (proxy)
├── orchestrator/        # Task decomposition + execution
├── benchmark/
│   ├── data/            # benchmark_tasks_50.json (+ audio/images — see below)
│   └── DATA_SOURCING_GUIDE.md
├── configs/             # api_mode.yaml (Gemini), optional GPU cluster YAML
├── scripts/
│   ├── run_experiment.py   # run MMA2A and/or Text-BN on N tasks
│   ├── evaluate.py         # metrics + optional LaTeX tables
│   ├── compute_stats.py    # McNemar + bootstrap CI (paired runs)
│   ├── prep_benchmark_data.py
│   └── generate_tables.py
├── results/
│   ├── run2-gemini-reasoning/   # paper: LLM reasoning, 52% vs 32%
│   ├── run1-keyword-matcher/    # paper: keyword ablation, 36% vs 36%
│   └── dev-runs/                # gitignored scratch
├── web_interface/       # optional demo UI
├── start_system.sh
├── .env.example         # copy to .env — do not commit .env
└── requirements.txt
```

## Prerequisites

- **Google AI API key** for Gemini (`export GOOGLE_API_KEY=...` or `.env`).
- **Benchmark media**: `benchmark/data/benchmark_tasks_50.json` references audio and image files. Large binaries are gitignored; follow **`benchmark/DATA_SOURCING_GUIDE.md`** to populate `benchmark/data/audio/` and `benchmark/data/images/`.

## Running the stack

Use **API mode** (Gemini) as in the paper:

1. `cp .env.example .env` and set `GOOGLE_API_KEY`.
2. Start each component (separate terminals or a process manager), for example:
   - MAR → port **8080**
   - Voice / Vision / Text agents → **8081**, **8082**, **8001** (see `start_system.sh` and each `server.py`)
   - Orchestrator → **8084**
   - Optional web UI → **8090**

Exact commands depend on your layout; `start_system.sh` documents ports and health URLs.

## Running the benchmark

From this directory, with services up:

```bash
# Full 50-task paired run (MMA2A + Text-BN)
python scripts/run_experiment.py --mode both --tasks 50

# Summarize latest paired results (searches results/ recursively)
python scripts/evaluate.py

# LaTeX fragments for the paper tables
python scripts/evaluate.py --latex
```

Outputs are written under `results/` as `mma2a_<timestamp>_<run_id>.json` and `text-bn_<timestamp>_<run_id>.json`.

## Recomputing statistics from the paper runs

Published JSON for the main comparison:

```bash
python scripts/compute_stats.py \
  --mma2a results/run2-gemini-reasoning/mma2a_20260413_165258_afffb9b1bcf7.json \
  --text-bn results/run2-gemini-reasoning/text-bn_20260413_165923_afffb9b1bcf7.json
```

Defaults in `compute_stats.py` point at these paths so you can run it with no arguments after cloning.

## Published artifacts

| Directory | Role |
|-----------|------|
| `results/run2-gemini-reasoning/` | Primary **52% / 32%** paired run + `evaluation_*.json` |
| `results/run1-keyword-matcher/` | Keyword ablation **36% / 36%** |

See also **`A2A_COMPLIANCE.md`** and **`../docs/A2A_SPEC_COMPLIANCE_REVIEW.md`** for protocol notes.
