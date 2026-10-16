"""Devpost gallery: final 1080p frames padded to 3:2 (1920x1280) with the film's
background colour, saved as JPG. Run: blender -b --python orbital/tools/make_gallery.py"""
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC, OUT = ROOT / "output" / "frames", ROOT / "submission"
PICKS = [(290, "01_thumbnail_finalists"), (110, "02_heat2_low_orbit"), (240, "03_heat3_ellipses"),
         (494, "04_photo_finish"), (540, "05_meanwhile_start_line"), (600, "06_results"), (660, "07_final_card")]
BG = (3 / 255, 6 / 255, 5 / 255)  # #030605, same as the film background (display space)
W, H = 1920, 1280

OUT.mkdir(exist_ok=True)
sc = bpy.context.scene
sc.render.image_settings.file_format = "JPEG"
sc.render.image_settings.quality = 92
sc.view_settings.view_transform = "Standard"
for frame, name in PICKS:
    src = bpy.data.images.load(str(SRC / f"{frame:04d}.png"))
    src.colorspace_settings.name = "Non-Color"   # copy pixel values as they are
    w, h = src.size
    px = np.array(src.pixels[:], dtype=np.float32).reshape(h, w, 4)
    canvas = np.empty((H, W, 4), dtype=np.float32)
    canvas[...] = (*BG, 1.0)
    y0 = (H - h) // 2
    canvas[y0:y0 + h, :w] = px
    img = bpy.data.images.new(name, W, H)
    img.colorspace_settings.name = "Non-Color"
    img.pixels[:] = canvas.ravel()
    img.filepath_raw = str(OUT / f"{name}.jpg")
    img.file_format = "JPEG"
    img.save_render(str(OUT / f"{name}.jpg"), scene=sc)
    print(f"[gallery] {name}.jpg")
