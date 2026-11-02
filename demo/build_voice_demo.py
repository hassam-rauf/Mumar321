#!/usr/bin/env python3
"""Mix the TTS clips from demo/record_voice_demo.js onto the recording.

Usage: python3 demo/build_voice_demo.py   -> demo/vapi/voice-agent-demo.mp4
Reads demo/out/*.webm (newest) and demo/out/voice/timeline.json.
"""
import json, subprocess
from pathlib import Path

D = Path(__file__).resolve().parent
OUT = D / "out"
video = max(OUT.glob("*.webm"), key=lambda p: p.stat().st_mtime)
timeline = json.loads((OUT / "voice" / "timeline.json").read_text())
dest = D / "vapi" / "voice-agent-demo.mp4"
dest.parent.mkdir(exist_ok=True)

inputs, filters = ["-i", str(video)], []
for i, clip in enumerate(timeline, start=1):
    inputs += ["-i", clip["wav"]]
    ms = int(clip["start"] * 1000)
    filters.append(f"[{i}:a]adelay={ms}|{ms},volume=1.25[a{i}]")
mix = "".join(f"[a{i}]" for i in range(1, len(timeline) + 1))
filters.append(f"{mix}amix=inputs={len(timeline)}:normalize=0,apad[aout]")

subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(filters),
                "-map", "0:v", "-map", "[aout]", "-shortest",
                "-c:v", "libx264", "-preset", "slow", "-crf", "22", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "160k", "-ac", "2", "-ar", "48000", "-movflags", "+faststart", str(dest)], check=True)
print(f"Wrote {dest}")
