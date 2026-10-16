"""Render settings and the frame loop. PNG sequence only; encoding is a separate step."""
import time

import bpy

import config


def setup(scene, profile, tl):
    p = config.PROFILES[profile]
    r = scene.render
    r.engine = "BLENDER_EEVEE"
    r.resolution_x, r.resolution_y = config.RES
    r.resolution_percentage = p["scale"]
    r.fps = tl.fps
    r.film_transparent = False
    r.use_motion_blur = False
    r.filter_size = 1.2
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGB"
    r.image_settings.color_depth = "8"
    ee = scene.eevee
    ee.taa_render_samples = p["samples"]
    for attr, val in (("use_shadows", True), ("use_raytracing", False), ("use_gtao", False)):
        if hasattr(ee, attr):
            setattr(ee, attr, val)
    vs = scene.view_settings
    vs.view_transform = "Standard"
    vs.look = "None"
    vs.exposure = 0.0
    vs.gamma = 1.0
    scene.display_settings.display_device = "sRGB"
    scene.sequencer_colorspace_settings.name = "sRGB"
    return p


def render(scene, profile, start, end, tl):
    p = config.PROFILES[profile]
    out = p["out"]
    out.mkdir(parents=True, exist_ok=True)
    times = []
    for f in range(start, end + 1):
        scene.frame_set(f)
        scene.render.filepath = str(out / f"{f:04d}.png")
        t = time.time()
        bpy.ops.render.render(write_still=True)
        times.append(time.time() - t)
        if f == start or f % 24 == 0 or f == end:
            print(f"[render] frame {f} {times[-1]:.2f} s  (avg {sum(times) / len(times):.2f} s)", flush=True)
    if times:
        print(f"[render] {len(times)} frames, avg {sum(times) / len(times):.2f} s/frame, "
              f"total {sum(times) / 60:.1f} min -> {out}")
