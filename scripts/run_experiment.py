#!/usr/bin/env python3
"""MMA2A Benchmark Runner.

Runs the CrossModal-CS benchmark against the MMA2A system in two modes:
  1. MMA2A (modality-native routing) — default
  2. Text-BN (text-bottleneck baseline) — force_text_mode=true

Collects per-task metrics: latency, routing decisions, action accuracy.
Outputs results to results/ as JSON for analysis by evaluate.py.

Usage:
    python scripts/run_experiment.py                    # run both modes
    python scripts/run_experiment.py --mode mma2a       # native only
    python scripts/run_experiment.py --mode text-bn     # baseline only
    python scripts/run_experiment.py --tasks 10         # first N tasks
    python scripts/run_experiment.py --dry-run           # validate tasks, no execution
"""

import argparse
import asyncio
import base64
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("benchmark")

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
BENCHMARK_DATA = PROJECT_ROOT / "benchmark" / "data"
RESULTS_DIR = PROJECT_ROOT / "results"

# Service URLs
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8084")
MAR_URL = os.getenv("MAR_URL", "http://localhost:8080")
WEB_UI_URL = os.getenv("WEB_UI_URL", "http://localhost:8090")


def load_benchmark_tasks(path: Path, limit: Optional[int] = None) -> list[dict]:
    """Load benchmark task definitions from JSON."""
    with open(path) as f:
        tasks = json.load(f)
    if limit:
        tasks = tasks[:limit]
    logger.info(f"Loaded {len(tasks)} benchmark tasks from {path.name}")
    return tasks


def load_real_file(relative_path: str) -> Optional[tuple[str, str]]:
    """Load a real file from benchmark/data/ and return (base64, mime_type).

    Returns None if the file doesn't exist.
    """
    full_path = BENCHMARK_DATA.parent / relative_path
    if not full_path.exists():
        # Also check without the data/ prefix
        full_path = BENCHMARK_DATA / Path(relative_path).name
    if not full_path.exists():
        return None

    with open(full_path, "rb") as f:
        data = f.read()

    b64_data = base64.b64encode(data).decode("ascii")

    # Determine MIME type from extension
    ext = full_path.suffix.lower()
    mime_map = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    mime = mime_map.get(ext, "application/octet-stream")

    logger.debug(f"Loaded real file: {full_path.name} ({len(data)} bytes, {mime})")
    return b64_data, mime


def generate_mock_audio(transcript: str) -> tuple[str, str]:
    """Generate mock audio data (base64) from transcript text.

    Fallback when real audio files aren't available.
    Encodes the transcript as fake WAV bytes so the voice agent's
    mock processor can work with it.
    """
    fake_audio = transcript.encode("utf-8")
    b64_data = base64.b64encode(fake_audio).decode("ascii")
    return b64_data, "audio/wav"


def generate_mock_image(description: str) -> tuple[str, str]:
    """Generate mock image data (base64) from description.

    Fallback when real image files aren't available.
    """
    fake_image = description.encode("utf-8")
    b64_data = base64.b64encode(fake_image).decode("ascii")
    return b64_data, "image/jpeg"


def build_a2a_message(task: dict) -> dict:
    """Build an A2A-compliant message from a benchmark task definition.

    Uses real audio/image files when available in benchmark/data/,
    falls back to mock data generated from transcripts/descriptions.
    """
    parts = []
    data_source = {"audio": "mock", "image": "mock"}

    # Add text context
    if task.get("text_context"):
        parts.append({
            "type": "text",
            "text": task["text_context"],
        })

    # Add voice input — prefer real file, fall back to mock
    if task.get("voice_transcript"):
        real_audio = None
        if task.get("voice_input"):
            real_audio = load_real_file(task["voice_input"])

        if real_audio:
            audio_b64, mime = real_audio
            data_source["audio"] = "real"
        else:
            audio_b64, mime = generate_mock_audio(task["voice_transcript"])

        parts.append({
            "type": "file",
            "mimeType": mime,
            "name": f"{task['task_id']}_audio.wav",
            "data": audio_b64,
        })

    # Add image input — prefer real file, fall back to mock
    if task.get("image_description"):
        real_image = None
        if task.get("image_input"):
            real_image = load_real_file(task["image_input"])

        if real_image:
            img_b64, mime = real_image
            data_source["image"] = "real"
        else:
            img_b64, mime = generate_mock_image(task["image_description"])

        parts.append({
            "type": "file",
            "mimeType": mime,
            "name": f"{task['task_id']}_image.jpg",
            "data": img_b64,
        })

    return {
        "role": "user",
        "parts": parts,
        "_data_source": data_source,  # Internal tracking, stripped before sending
    }


def build_jsonrpc_request(task_id: str, message: dict, metadata: dict) -> dict:
    """Build a JSON-RPC 2.0 request for tasks/send."""
    return {
        "jsonrpc": "2.0",
        "method": "tasks/send",
        "params": {
            "id": task_id,
            "message": message,
            "metadata": metadata,
        },
        "id": str(uuid.uuid4()),
    }


async def set_routing_mode(client: httpx.AsyncClient, force_text: bool) -> bool:
    """Toggle the MAR's routing mode."""
    try:
        resp = await client.post(
            f"{MAR_URL}/force-text-mode",
            params={"enable": str(force_text).lower()},
        )
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"Routing mode set: force_text_mode={result.get('force_text_mode')}")
        return True
    except Exception as e:
        logger.warning(f"Failed to set routing mode via MAR, trying web UI: {e}")
        try:
            resp = await client.post(
                f"{WEB_UI_URL}/toggle-routing-mode",
                json={"enable_text_bn": force_text},
            )
            resp.raise_for_status()
            return True
        except Exception as e2:
            logger.error(f"Failed to set routing mode: {e2}")
            return False


async def execute_task(
    client: httpx.AsyncClient,
    task: dict,
    mode: str,
) -> dict:
    """Execute a single benchmark task and collect metrics."""
    task_id = f"{mode}_{task['task_id']}_{uuid.uuid4().hex[:8]}"

    # Build A2A message
    message = build_a2a_message(task)
    data_source = message.pop("_data_source", {"audio": "mock", "image": "mock"})

    metadata = {
        "benchmark": {
            "task_id": task["task_id"],
            "category": task["category"],
            "mode": mode,
            "ground_truth_action": task["ground_truth_action"],
        }
    }

    rpc_request = build_jsonrpc_request(task_id, message, metadata)

    # Measure payload size
    payload_json = json.dumps(rpc_request)
    payload_bytes = len(payload_json.encode("utf-8"))

    # Execute with timing
    start_time = time.perf_counter()
    error = None
    response_data = None

    try:
        resp = await client.post(
            ORCHESTRATOR_URL,
            json=rpc_request,
            timeout=60.0,
        )
        resp.raise_for_status()
        response_data = resp.json()
    except httpx.TimeoutException:
        error = "timeout"
    except Exception as e:
        error = str(e)

    end_time = time.perf_counter()
    latency_seconds = end_time - start_time

    # Extract result details
    result_action = None
    routing_decisions = []
    subtask_details = []
    response_text = ""

    if response_data and "result" in response_data:
        result = response_data["result"]

        # Extract response text
        status = result.get("status", {})
        msg = status.get("message", {})
        for part in msg.get("parts", []):
            if part.get("type") == "text":
                response_text += part.get("text", "")

        # Extract recommended action from response
        result_action = _extract_action(response_text)

        # Extract routing metadata
        meta = result.get("metadata", {})
        orchestrator_meta = meta.get("orchestrator", {})
        mar_meta = meta.get("mar_routing", {})

        routing_decisions = mar_meta.get("routing_decisions", [])
        exec_summary = orchestrator_meta.get("execution_summary", {})

        for st_id, st_info in exec_summary.items():
            subtask_details.append({
                "id": st_id,
                "status": st_info.get("status", "unknown") if isinstance(st_info, dict) else str(st_info),
                "duration": st_info.get("duration") if isinstance(st_info, dict) else None,
            })

    # Compute accuracy
    ground_truth = task["ground_truth_action"]
    action_correct = (result_action == ground_truth) if result_action else False

    # Response payload size
    response_bytes = len(json.dumps(response_data).encode("utf-8")) if response_data else 0

    return {
        "task_id": task["task_id"],
        "run_id": task_id,
        "mode": mode,
        "category": task["category"],
        "modalities_required": task.get("modalities_required", []),
        "latency_seconds": round(latency_seconds, 4),
        "request_bytes": payload_bytes,
        "response_bytes": response_bytes,
        "total_bytes": payload_bytes + response_bytes,
        "ground_truth_action": ground_truth,
        "predicted_action": result_action,
        "action_correct": action_correct,
        "routing_decisions": routing_decisions,
        "subtask_details": subtask_details,
        "response_text_preview": response_text[:300],
        "data_source": data_source,
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _extract_action(text: str) -> Optional[str]:
    """Extract the recommended action from response text."""
    text_lower = text.lower()

    # Priority-ordered action detection
    action_keywords = {
        "initiate_replacement": ["initiate_replacement", "immediate replacement", "replace immediately", "expedited replacement"],
        "approve_warranty": ["approve_warranty", "approve warranty", "warranty approved", "covered under warranty"],
        "deny_warranty": ["deny_warranty", "deny warranty", "warranty denied", "excluded from warranty", "not covered"],
        "escalate_to_specialist": ["escalate_to_specialist", "escalate to", "specialist review", "further review"],
        "provide_instructions": ["provide_instructions", "provide instructions", "assembly guidance", "here are the steps"],
        "troubleshoot_step": ["troubleshoot_step", "troubleshoot", "troubleshooting steps", "try the following"],
        "initiate_return": ["initiate_return", "process return", "return for refund"],
        "order_part": ["order_part", "replacement part", "order part"],
    }

    for action, keywords in action_keywords.items():
        for kw in keywords:
            if kw in text_lower:
                return action

    return None


async def check_services(client: httpx.AsyncClient) -> dict:
    """Check health of all services."""
    services = {
        "orchestrator": f"{ORCHESTRATOR_URL}/health",
        "mar": f"{MAR_URL}/health",
    }

    status = {}
    for name, url in services.items():
        try:
            resp = await client.get(url, timeout=5.0)
            status[name] = "healthy" if resp.status_code == 200 else f"status:{resp.status_code}"
        except Exception as e:
            status[name] = f"unreachable: {e}"

    return status


async def run_benchmark(
    tasks: list[dict],
    mode: str,
    client: httpx.AsyncClient,
    delay_between: float = 0.5,
) -> list[dict]:
    """Run all tasks in a given mode, collecting results."""
    logger.info(f"=== Running benchmark: mode={mode}, tasks={len(tasks)} ===")

    # Set routing mode
    force_text = mode == "text-bn"
    if not await set_routing_mode(client, force_text):
        logger.error("Could not set routing mode — results may be invalid")

    # Brief pause for mode to take effect
    await asyncio.sleep(1.0)

    results = []
    successes = 0
    failures = 0

    for i, task in enumerate(tasks, 1):
        logger.info(f"[{i}/{len(tasks)}] {mode}: {task['task_id']} ({task['category']})")

        result = await execute_task(client, task, mode)
        results.append(result)

        if result["error"]:
            failures += 1
            logger.warning(f"  FAILED: {result['error']}")
        else:
            successes += 1
            correct_str = "CORRECT" if result["action_correct"] else f"WRONG (predicted={result['predicted_action']}, truth={result['ground_truth_action']})"
            logger.info(f"  {correct_str} | latency={result['latency_seconds']:.2f}s | bytes={result['total_bytes']}")

        # Rate limiting
        if delay_between > 0 and i < len(tasks):
            await asyncio.sleep(delay_between)

    logger.info(f"=== {mode} complete: {successes} succeeded, {failures} failed ===")
    return results


def save_results(results: list[dict], mode: str, run_id: str) -> Path:
    """Save results to JSON file."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{mode}_{timestamp}_{run_id}.json"
    path = RESULTS_DIR / filename

    output = {
        "run_id": run_id,
        "mode": mode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "task_count": len(results),
        "results": results,
    }

    with open(path, "w") as f:
        json.dump(output, f, indent=2)

    logger.info(f"Results saved to {path}")
    return path


async def main():
    parser = argparse.ArgumentParser(description="MMA2A Benchmark Runner")
    parser.add_argument("--mode", choices=["mma2a", "text-bn", "both"], default="both",
                        help="Routing mode to benchmark")
    parser.add_argument("--tasks", type=int, default=None,
                        help="Limit to first N tasks")
    parser.add_argument("--benchmark-file", type=str, default="benchmark_tasks_50.json",
                        help="Benchmark task file name")
    parser.add_argument("--delay", type=float, default=0.5,
                        help="Delay between tasks (seconds)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate tasks without executing")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose logging")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load tasks
    benchmark_path = BENCHMARK_DATA / args.benchmark_file
    if not benchmark_path.exists():
        logger.error(f"Benchmark file not found: {benchmark_path}")
        sys.exit(1)

    tasks = load_benchmark_tasks(benchmark_path, limit=args.tasks)

    if args.dry_run:
        logger.info("=== DRY RUN — validating tasks ===")
        categories = {}
        modalities = set()
        for task in tasks:
            cat = task["category"]
            categories[cat] = categories.get(cat, 0) + 1
            modalities.update(task.get("modalities_required", []))

        logger.info(f"Tasks: {len(tasks)}")
        logger.info(f"Categories: {json.dumps(categories, indent=2)}")
        logger.info(f"Modalities: {sorted(modalities)}")

        # Validate each task has required fields
        required = ["task_id", "category", "ground_truth_action"]
        for task in tasks:
            missing = [f for f in required if f not in task]
            if missing:
                logger.error(f"Task {task.get('task_id', '?')} missing fields: {missing}")
        logger.info("Dry run complete.")
        return

    # Check services
    async with httpx.AsyncClient() as client:
        logger.info("Checking service health...")
        health = await check_services(client)
        all_healthy = all("healthy" in str(v) for v in health.values())

        for svc, status in health.items():
            icon = "✓" if "healthy" in str(status) else "✗"
            logger.info(f"  {icon} {svc}: {status}")

        if not all_healthy:
            logger.error("Not all services are healthy. Start the system first (./start_system.sh)")
            logger.error("Continuing anyway — some tasks may fail.")

        run_id = uuid.uuid4().hex[:12]
        all_results = []
        result_files = []

        modes = []
        if args.mode in ("mma2a", "both"):
            modes.append("mma2a")
        if args.mode in ("text-bn", "both"):
            modes.append("text-bn")

        for mode in modes:
            results = await run_benchmark(tasks, mode, client, delay_between=args.delay)
            all_results.extend(results)
            path = save_results(results, mode, run_id)
            result_files.append(path)

        # Print summary
        print("\n" + "=" * 60)
        print(f"BENCHMARK COMPLETE — Run ID: {run_id}")
        print("=" * 60)

        for mode in modes:
            mode_results = [r for r in all_results if r["mode"] == mode]
            correct = sum(1 for r in mode_results if r["action_correct"])
            errors = sum(1 for r in mode_results if r["error"])
            total = len(mode_results)
            avg_latency = sum(r["latency_seconds"] for r in mode_results) / max(total, 1)
            avg_bytes = sum(r["total_bytes"] for r in mode_results) / max(total, 1)

            print(f"\n  {mode.upper()}")
            print(f"  Tasks:     {total}")
            print(f"  Accuracy:  {correct}/{total - errors} ({100*correct/max(total-errors,1):.1f}%)")
            print(f"  Errors:    {errors}")
            print(f"  Avg Latency: {avg_latency:.2f}s")
            print(f"  Avg Payload: {avg_bytes/1024:.1f} KB")

        print(f"\nResults saved to:")
        for p in result_files:
            print(f"  {p}")
        print(f"\nNext: python scripts/evaluate.py results/")


if __name__ == "__main__":
    asyncio.run(main())
