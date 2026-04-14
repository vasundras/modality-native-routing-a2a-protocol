# Benchmark Data Sourcing Guide

You need **40 audio clips** and **40 product images** to run the full CrossModal-CS benchmark with real multimodal data. Here's how to get them efficiently.

---

## Quick Summary

| Asset | Count | Format | Target Size | Time Estimate |
|-------|-------|--------|-------------|---------------|
| Audio clips | 40 | WAV, 16kHz mono | 5-30 sec each | ~1 hour (record yourself) |
| Product images | 40 | JPEG, 640-1280px | 50-500 KB each | ~1.5 hours (photograph + search) |

---

## Audio Clips (40 files)

### Option A: Record Yourself (~1 hour)
The fastest approach. Read each transcript aloud into your phone or laptop mic.

**Specs:**
- Format: WAV (or M4A — the prep script converts)
- Sample rate: 16kHz mono (the prep script resamples)
- Duration: 5-30 seconds per clip
- Tone: Vary emotion — frustrated, confused, urgent, calm — to match the scenario

**Recording tips:**
- Use Voice Memos (Mac/iPhone) or Audacity
- Don't aim for perfection — real customer calls have background noise
- Vary your pace and tone across clips

**File naming:** Match the task IDs exactly:
```
benchmark/data/audio/defect_001.wav
benchmark/data/audio/assembly_001.wav
...
```

### Option B: Text-to-Speech (~15 min + API cost)
If you have an OpenAI API key:
```bash
python scripts/generate_tts_audio.py --api-key $OPENAI_API_KEY
```
This reads transcripts from the benchmark JSON and generates WAV files via the TTS API (~$0.50 total for 40 clips).

### Transcripts to Record

**Defect Reports (13 clips):**

| File | Transcript (read aloud) |
|------|------------------------|
| defect_001.wav | "Hi, I dropped my BlenderMax 3000 yesterday and now it's making a grinding noise whenever I turn it on. The blade assembly looks bent." |
| defect_002.wav | "I just unboxed this coffee maker and the carafe has a crack in it right out of the box. I haven't even used it yet." |
| defect_003.wav | "My toaster has been sparking inside when I use it. I've only had it for two weeks. I'm scared to use it now." |
| defect_004.wav | "I bought this laptop stand three months ago and one of the hinges just snapped off while I was adjusting it normally." |
| defect_005.wav | "My kid used this tablet for a month and the screen started flickering. Then yesterday the whole display went black but you can still hear sounds." |
| defect_006.wav | "I've been using this pan for about eight months and the non-stick coating is peeling off into my food. This can't be safe." |
| defect_007.wav | "My wireless earbuds won't charge anymore. I've tried different cables and outlets but the case LED doesn't light up at all." |
| defect_008.wav | "The stitching on my backpack shoulder strap came undone after just two weeks. I wasn't even carrying anything heavy." |
| defect_009.wav | "I got this robot vacuum last week and it keeps bumping into everything even though it has obstacle sensors." |
| defect_010.wav | "My pressure cooker lid won't seal properly anymore. Steam keeps escaping from the sides when it's supposed to be pressurized." |
| defect_011.wav | "I dropped my phone in the toilet briefly and now the screen has water under it. It says it's water resistant." |
| defect_012.wav | "My electric kettle started making a burning smell yesterday. I unplugged it immediately. I've only had it six months." |
| defect_013.wav | "I got this air purifier a few weeks ago and it's making a high-pitched whine constantly. All the lights say it's fine." |

**Assembly Guidance (12 clips):** assembly_001 through assembly_012
**Troubleshooting (2 clips with audio):** troubleshoot_005, troubleshoot_011
**Warranty Claims (13 clips):** warranty_001 through warranty_013

The full transcript for each is in `benchmark/data/benchmark_tasks_50.json` — look at the `voice_transcript` field.

---

## Product Images (40 files)

### Sourcing Strategy

**Tier 1 — Photograph your own stuff (~15 images, 30 min):**
Common items most people own — toaster, blender, pan, phone, backpack, vacuum, earbuds, kettle. Simulate the defect described:
- Crack = draw with marker, use tape
- Sparking damage = blacken with lighter (on something disposable)
- Display error = screenshot on actual device
- For undamaged warranty items, photograph the product label/serial number

**Tier 2 — Free stock photos (~15 images, 30 min):**
Sources (all free for research use):
- Unsplash.com — search "broken appliance", "product defect", etc.
- Pexels.com — similar searches
- Pixabay.com — CC0 licensed

**Tier 3 — Screenshots for error displays (~10 images, 15 min):**
Several tasks need screenshots of displays (router admin page, thermostat, error codes). Create these:
- Router admin: mock up a simple HTML page or screenshot your router's status page
- Thermostat: photo of a real thermostat or screenshot from the manual
- Error codes: photo of any appliance display or mock one

### Image Specifications

| Parameter | Value |
|-----------|-------|
| Format | JPEG (.jpg) |
| Resolution | 640-1280px on longest edge |
| Quality | 75-85% JPEG compression |
| File size | 50-500 KB per image |
| Content | Must show what `image_description` describes |

### Image File List

Each image must match its task's `image_description` field. Here's a quick guide by priority:

**Easy to photograph (things you probably own):**
- defect_001.jpg — Blender with visible damage
- defect_003.jpg — Toaster interior, burn marks
- defect_006.jpg — Pan with coating issues
- defect_007.jpg — Earbuds charging case
- defect_011.jpg — Phone with water spots
- warranty_002.jpg — Headphones, no visible damage
- warranty_011.jpg — Earbuds with water residue

**Easy to find online (stock photos):**
- defect_002.jpg — Cracked glass carafe
- defect_004.jpg — Broken metal hinge
- defect_008.jpg — Torn strap stitching
- warranty_004.jpg — Laptop with swollen battery
- warranty_005.jpg — Cracked microwave door

**Screenshots to create:**
- troubleshoot_001.jpg — Router admin page (WAN disconnected)
- troubleshoot_002.jpg — Washing machine E3 error
- troubleshoot_004.jpg — Thermostat display
- troubleshoot_009.jpg — Monitor "No Signal"

---

## After Sourcing: Validate

Run the prep script to validate all files, normalize formats, and check for missing assets:

```bash
python scripts/prep_benchmark_data.py --validate
python scripts/prep_benchmark_data.py --normalize   # resample audio, resize images
```

---

## Alternative: Run with Mock Data First

If you want to benchmark the system *now* and add real data later, the benchmark runner works fine with mock data (it generates synthetic base64 payloads from the transcript/description text). Just run:

```bash
python scripts/run_experiment.py --tasks 5
```

Then replace mock data with real files incrementally. The runner automatically uses real files when they exist in `data/audio/` and `data/images/`.
