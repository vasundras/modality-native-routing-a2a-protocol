#!/usr/bin/env python3
"""Benchmark Data Preparation & Validation.

Validates that all required audio and image files exist for the benchmark,
normalizes formats (resample audio to 16kHz WAV, resize images to max 1280px),
and reports a readiness summary.

Usage:
    python scripts/prep_benchmark_data.py --validate       # check what's missing
    python scripts/prep_benchmark_data.py --normalize      # convert/resize files
    python scripts/prep_benchmark_data.py --stats          # show file statistics
"""

import argparse
import json
import os
import struct
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
BENCHMARK_DATA = PROJECT_ROOT / "benchmark" / "data"
AUDIO_DIR = BENCHMARK_DATA / "audio"
IMAGES_DIR = BENCHMARK_DATA / "images"


def load_tasks() -> list[dict]:
    """Load benchmark tasks."""
    path = BENCHMARK_DATA / "benchmark_tasks_50.json"
    with open(path) as f:
        return json.load(f)


def get_required_files(tasks: list[dict]) -> tuple[list[dict], list[dict]]:
    """Extract required audio and image files from tasks."""
    audio_files = []
    image_files = []

    for task in tasks:
        if task.get("voice_input"):
            filename = Path(task["voice_input"]).name
            audio_files.append({
                "task_id": task["task_id"],
                "filename": filename,
                "path": AUDIO_DIR / filename,
                "transcript": task.get("voice_transcript", "")[:80],
            })
        if task.get("image_input"):
            filename = Path(task["image_input"]).name
            image_files.append({
                "task_id": task["task_id"],
                "filename": filename,
                "path": IMAGES_DIR / filename,
                "description": task.get("image_description", "")[:80],
            })

    return audio_files, image_files


def validate(tasks: list[dict]):
    """Check which files exist and which are missing."""
    audio_files, image_files = get_required_files(tasks)

    print("=" * 60)
    print("  BENCHMARK DATA VALIDATION")
    print("=" * 60)

    # Audio
    audio_present = [f for f in audio_files if f["path"].exists()]
    audio_missing = [f for f in audio_files if not f["path"].exists()]

    # Also check for alternative extensions
    alt_extensions = [".m4a", ".mp3", ".ogg", ".flac", ".webm"]
    audio_convertible = []
    for f in audio_missing:
        stem = f["path"].stem
        for ext in alt_extensions:
            alt_path = AUDIO_DIR / (stem + ext)
            if alt_path.exists():
                audio_convertible.append({**f, "alt_path": alt_path, "alt_ext": ext})
                break

    print(f"\n  AUDIO ({len(audio_files)} required)")
    print(f"  {'─' * 40}")
    print(f"  Present (WAV):    {len(audio_present)}")
    print(f"  Convertible:      {len(audio_convertible)}")
    print(f"  Missing:          {len(audio_missing) - len(audio_convertible)}")

    if audio_missing and len(audio_missing) > len(audio_convertible):
        truly_missing = [f for f in audio_missing
                         if not any(c["task_id"] == f["task_id"] for c in audio_convertible)]
        print(f"\n  Missing audio files:")
        for f in truly_missing[:10]:
            print(f"    {f['filename']:30s} \"{f['transcript']}...\"")
        if len(truly_missing) > 10:
            print(f"    ... and {len(truly_missing) - 10} more")

    # Images
    image_present = [f for f in image_files if f["path"].exists()]
    image_missing = [f for f in image_files if not f["path"].exists()]

    # Check for PNG alternatives
    image_convertible = []
    for f in image_missing:
        stem = f["path"].stem
        for ext in [".png", ".webp", ".bmp", ".tiff"]:
            alt_path = IMAGES_DIR / (stem + ext)
            if alt_path.exists():
                image_convertible.append({**f, "alt_path": alt_path, "alt_ext": ext})
                break

    print(f"\n  IMAGES ({len(image_files)} required)")
    print(f"  {'─' * 40}")
    print(f"  Present (JPEG):   {len(image_present)}")
    print(f"  Convertible:      {len(image_convertible)}")
    print(f"  Missing:          {len(image_missing) - len(image_convertible)}")

    if image_missing and len(image_missing) > len(image_convertible):
        truly_missing = [f for f in image_missing
                         if not any(c["task_id"] == f["task_id"] for c in image_convertible)]
        print(f"\n  Missing image files:")
        for f in truly_missing[:10]:
            print(f"    {f['filename']:35s} \"{f['description']}...\"")
        if len(truly_missing) > 10:
            print(f"    ... and {len(truly_missing) - 10} more")

    # Overall readiness
    total_required = len(audio_files) + len(image_files)
    total_present = len(audio_present) + len(image_present) + len(audio_convertible) + len(image_convertible)
    pct = 100 * total_present / max(total_required, 1)

    print(f"\n  OVERALL READINESS: {total_present}/{total_required} ({pct:.0f}%)")

    if pct == 100:
        print("  Status: READY — all benchmark data available")
    elif pct > 50:
        print("  Status: PARTIAL — can run benchmark on tasks with data")
        print("  Tip: Use --tasks N to run only tasks with available data")
    else:
        print("  Status: MOCK MODE — benchmark will generate synthetic data")
        print("  See benchmark/DATA_SOURCING_GUIDE.md for sourcing instructions")

    print()
    return total_present == total_required


def show_stats(tasks: list[dict]):
    """Show statistics about existing data files."""
    audio_files, image_files = get_required_files(tasks)

    print("=" * 60)
    print("  BENCHMARK DATA STATISTICS")
    print("=" * 60)

    # Audio stats
    audio_sizes = []
    for f in audio_files:
        if f["path"].exists():
            size = f["path"].stat().st_size
            audio_sizes.append(size)

    if audio_sizes:
        print(f"\n  Audio files: {len(audio_sizes)}")
        print(f"  Total size:  {sum(audio_sizes) / (1024*1024):.1f} MB")
        print(f"  Avg size:    {sum(audio_sizes) / len(audio_sizes) / 1024:.1f} KB")
        print(f"  Min/Max:     {min(audio_sizes)/1024:.1f} KB / {max(audio_sizes)/1024:.1f} KB")

        # Check WAV format details
        for f in audio_files:
            if f["path"].exists() and f["path"].suffix.lower() == ".wav":
                try:
                    with open(f["path"], "rb") as wf:
                        riff = wf.read(4)
                        if riff == b"RIFF":
                            wf.seek(22)
                            channels = struct.unpack("<H", wf.read(2))[0]
                            sample_rate = struct.unpack("<I", wf.read(4))[0]
                            print(f"  Sample WAV:  {f['filename']} — {sample_rate}Hz, {channels}ch")
                            break
                except Exception:
                    pass

    # Image stats
    image_sizes = []
    for f in image_files:
        if f["path"].exists():
            size = f["path"].stat().st_size
            image_sizes.append(size)

    if image_sizes:
        print(f"\n  Image files: {len(image_sizes)}")
        print(f"  Total size:  {sum(image_sizes) / (1024*1024):.1f} MB")
        print(f"  Avg size:    {sum(image_sizes) / len(image_sizes) / 1024:.1f} KB")
        print(f"  Min/Max:     {min(image_sizes)/1024:.1f} KB / {max(image_sizes)/1024:.1f} KB")

    if not audio_sizes and not image_sizes:
        print("\n  No data files found yet.")
        print("  See benchmark/DATA_SOURCING_GUIDE.md for sourcing instructions.")

    print()


def normalize(tasks: list[dict]):
    """Normalize audio and image files to standard formats.

    Requires: Pillow (pip install Pillow) for images,
              ffmpeg (apt install ffmpeg) for audio conversion.
    """
    audio_files, image_files = get_required_files(tasks)
    converted = 0

    # Convert non-WAV audio to 16kHz mono WAV
    alt_extensions = [".m4a", ".mp3", ".ogg", ".flac", ".webm"]
    for f in audio_files:
        if f["path"].exists():
            continue
        # Check for alternatives
        stem = f["path"].stem
        for ext in alt_extensions:
            alt_path = AUDIO_DIR / (stem + ext)
            if alt_path.exists():
                print(f"  Converting {alt_path.name} → {f['filename']}")
                ret = os.system(
                    f'ffmpeg -y -i "{alt_path}" -ar 16000 -ac 1 -acodec pcm_s16le "{f["path"]}" -loglevel warning'
                )
                if ret == 0:
                    converted += 1
                else:
                    print(f"    FAILED — install ffmpeg: apt install ffmpeg / brew install ffmpeg")
                break

    # Resize images to max 1280px and convert to JPEG
    try:
        from PIL import Image
        has_pillow = True
    except ImportError:
        has_pillow = False
        print("  Note: Install Pillow for image normalization: pip install Pillow")

    if has_pillow:
        for f in image_files:
            target = f["path"]
            stem = target.stem

            # Check if non-JPEG version exists
            if not target.exists():
                for ext in [".png", ".webp", ".bmp", ".tiff"]:
                    alt_path = IMAGES_DIR / (stem + ext)
                    if alt_path.exists():
                        print(f"  Converting {alt_path.name} → {f['filename']}")
                        img = Image.open(alt_path)
                        img = img.convert("RGB")
                        img.thumbnail((1280, 1280), Image.LANCZOS)
                        img.save(target, "JPEG", quality=80)
                        converted += 1
                        break

            # Resize existing JPEG if too large
            if target.exists():
                try:
                    img = Image.open(target)
                    w, h = img.size
                    if max(w, h) > 1280:
                        print(f"  Resizing {f['filename']} ({w}x{h} → max 1280px)")
                        img.thumbnail((1280, 1280), Image.LANCZOS)
                        img = img.convert("RGB")
                        img.save(target, "JPEG", quality=80)
                        converted += 1
                except Exception as e:
                    print(f"  Error processing {f['filename']}: {e}")

    print(f"\n  Normalized {converted} files.")


def main():
    parser = argparse.ArgumentParser(description="Benchmark Data Preparation")
    parser.add_argument("--validate", action="store_true", help="Check for missing files")
    parser.add_argument("--normalize", action="store_true", help="Convert/resize files to standard formats")
    parser.add_argument("--stats", action="store_true", help="Show file statistics")
    args = parser.parse_args()

    if not any([args.validate, args.normalize, args.stats]):
        args.validate = True  # Default action

    tasks = load_tasks()

    if args.validate:
        validate(tasks)
    if args.stats:
        show_stats(tasks)
    if args.normalize:
        normalize(tasks)


if __name__ == "__main__":
    main()
