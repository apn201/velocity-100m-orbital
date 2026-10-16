"""Encode a PNG sequence (+ generated audio) to H.264 MP4 with Blender's own FFmpeg.

    blender -b --python scripts/encode.py -- [--src output/frames] [--out output/final/velocity.mp4] [--no-audio]
"""
import argparse
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--src", default=str(ROOT / "output" / "frames"))
ap.add_argument("--out", default=str(ROOT / "output" / "final" / "velocity_flight_test_001.mp4"))
ap.add_argument("--audio", default=str(ROOT / "output" / "audio" / "velocity.wav"))
ap.add_argument("--no-audio", action="store_true")
ap.add_argument("--quality", default="HIGH", help="Blender CRF preset: HIGH, MEDIUM, LOW, VERYLOW ...")
a = ap.parse_args(argv)

src = Path(a.src).resolve()
frames = sorted(src.glob("*.png"))
if not frames:
    sys.exit(f"no PNGs in {src}")
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = 24
w, h = bpy.data.images.load(str(frames[0])).size
sc.render.resolution_x, sc.render.resolution_y = w, h
sc.render.resolution_percentage = 100
sc.view_settings.view_transform = "Standard"
sc.sequence_editor_create()
seqs = sc.sequence_editor.strips if hasattr(sc.sequence_editor, "strips") else sc.sequence_editor.sequences
strip = seqs.new_image("frames", str(frames[0]), 1, 1)
for f in frames[1:]:
    strip.elements.append(f.name)
sc.frame_start, sc.frame_end = 1, len(frames)
audio = Path(a.audio).resolve()  # Blender does not resolve plain relative paths; the strip would be silent
if not a.no_audio:
    if not audio.exists():
        sys.exit(f"no audio at {audio} (pass --no-audio to encode without)")
    seqs.new_sound("audio", str(audio), 2, 1)
r = sc.render
if hasattr(r.image_settings, "media_type"):
    r.image_settings.media_type = "VIDEO"
r.image_settings.file_format = "FFMPEG"
r.ffmpeg.format = "MPEG4"
r.ffmpeg.codec = "H264"
r.ffmpeg.constant_rate_factor = a.quality
r.ffmpeg.ffmpeg_preset = "GOOD"
r.ffmpeg.gopsize = 24
r.ffmpeg.audio_codec = "AAC" if not a.no_audio else "NONE"
r.ffmpeg.audio_bitrate = 192
Path(a.out).resolve().parent.mkdir(parents=True, exist_ok=True)
r.filepath = str(Path(a.out).resolve())
bpy.ops.render.render(animation=True)
print(f"[encode] {len(frames)} frames {w}x{h} -> {a.out}")
