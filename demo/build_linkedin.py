#!/usr/bin/env python3
"""Build the LinkedIn video from a MODE=linkedin recording (demo/out/*.webm + scenes.json).

  python3 demo/build_linkedin.py                       -> silent video with subtitles
  python3 demo/build_linkedin.py --voice voice.mp3     -> one voice track, aligned from 0:00
  python3 demo/build_linkedin.py --voice-dir clips/    -> one clip per scene (intro.mp3, track.mp3, ...)
"""
import glob, json, re, subprocess, sys
from pathlib import Path

D = Path(__file__).resolve().parent
OUT, LI = D / "out", D / "linkedin"
LI.mkdir(exist_ok=True)
narr = json.loads((D / "narration.json").read_text())
scenes = json.loads((OUT / "scenes.json").read_text())
starts = {s["key"]: s["start"] for s in scenes}
WPS = 2.3


def ts(t, ass=True):
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return f"{h}:{m:02d}:{s:05.2f}" if ass else f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def chunks(text, maxw=9):
    out, cur = [], []
    for w in text.split():
        cur.append(w)
        if len(cur) >= maxw or (len(cur) >= 4 and re.search(r"[.,:;?!]$", w)):
            out.append(" ".join(cur)); cur = []
    return out + ([" ".join(cur)] if cur else [])


# ---- per-scene speaking time: real clip length with --voice-dir, otherwise estimated
args = sys.argv[1:]
dur = {}
if "--voice-dir" in args:
    vd = Path(args[args.index("--voice-dir") + 1])
    for k in narr:
        f = next(vd.glob(f"{k}.*"), None)
        if f:
            dur[k] = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                                    "-of", "csv=p=0", str(f)]))

# ---- subtitles + narration sheet
events, sheet = [], []
keys = [s["key"] for s in scenes]
for s in scenes:
    if s["key"] not in narr:
        continue
    t = s["start"] + 0.4
    end = scenes[keys.index(s["key"]) + 1]["start"]
    sheet.append(f"**{int(s['start']//60)}:{int(s['start']%60):02d} - {int(end//60)}:{int(end%60):02d}** ({s['key']})\n\n> {narr[s['key']]}\n")
    wps = len(narr[s["key"]].split()) / dur[s["key"]] if s["key"] in dur else WPS
    for c in chunks(narr[s["key"]]):
        d = len(c.split()) / wps
        events.append((t, t + d, c)); t += d

(OUT / "subs.ass").write_text(
    "[Script Info]\nScriptType: v4.00+\nPlayResX: 1280\nPlayResY: 800\n\n[V4+ Styles]\n"
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
    "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
    "Style: Sub,Inter,30,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,2,40,40,24,1\n\n"
    "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    + "".join(f"Dialogue: 0,{ts(a)},{ts(b)},Sub,,0,0,0,,{c}\n" for a, b, c in events))
(LI / "subtitles.srt").write_text("".join(f"{i}\n{ts(a, False)} --> {ts(b, False)}\n{c}\n\n" for i, (a, b, c) in enumerate(events, 1)))
(LI / "narration-script.md").write_text(
    "# LinkedIn video: narration script\n\nRead each part when the video reaches its start time. Speak softly and "
    "slowly (about 2 words per second). Each part has a little spare time, so there is no need to rush.\n\n" + "\n".join(sheet))

# ---- video
webm = glob.glob(str(OUT / "*.webm"))[0]
vf = f"pad=1280:800:0:0:color=0x1d2330,ass={OUT / 'subs.ass'}"
cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", webm]
if "--voice" in args:
    cmd += ["-i", args[args.index("--voice") + 1]]
    audio = ["-filter_complex", f"[0:v]{vf}[v];[1:a]loudnorm=I=-16:TP=-1.5[a]", "-map", "[v]", "-map", "[a]"]
    name = "linkedin-demo.mp4"
elif "--voice-dir" in args:
    vd = Path(args[args.index("--voice-dir") + 1])
    clips = [(k, f) for k in narr for f in vd.glob(f"{k}.*")]
    parts = []
    for i, (k, f) in enumerate(clips, 1):
        cmd += ["-i", str(f)]
        ms = int((starts[k] + 0.4) * 1000)
        parts.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(1, len(clips) + 1))
    audio = ["-filter_complex", f"[0:v]{vf}[v];" + ";".join(parts) + f";{mix}amix=inputs={len(clips)}:normalize=0,loudnorm=I=-16:TP=-1.5[a]",
             "-map", "[v]", "-map", "[a]"]
    name = "linkedin-demo.mp4"
else:
    audio, name = ["-vf", vf], "linkedin-demo-silent.mp4"
cmd += audio + ["-c:v", "libx264", "-preset", "slow", "-crf", "21", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
if name != "linkedin-demo-silent.mp4":
    cmd += ["-c:a", "aac", "-b:a", "160k", "-t", str(scenes[-1]["start"] + 0.5)]
cmd += [str(LI / name)]
subprocess.run(cmd, check=True)
print(LI / name)
