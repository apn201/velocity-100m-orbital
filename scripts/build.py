"""VELOCITY // FLIGHT TEST 001 - entry point. Builds the whole film from an empty scene.

    blender -b --python scripts/build.py -- --validate
    blender -b --python scripts/build.py -- --preview [--start N --end M]
    blender -b --python scripts/build.py -- --final
    blender -b --python scripts/build.py -- --stills 60,180,300 [--preview]
Options: --seed N, --save-blend PATH
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy  # noqa: E402

import anim  # noqa: E402
import audio  # noqa: E402
import config  # noqa: E402
import geometry as G  # noqa: E402
import hud as H  # noqa: E402
import layers as Ly  # noqa: E402
import render as R  # noqa: E402
import validation  # noqa: E402
from timeline import Timeline  # noqa: E402


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="build.py")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--start", type=int)
    ap.add_argument("--end", type=int)
    ap.add_argument("--stills", type=str)
    ap.add_argument("--seed", type=int, default=config.SEED)
    ap.add_argument("--save-blend", type=str)
    return ap.parse_args(argv)


SHORT = {"ground": "GROUND", "earth": "EARTH", "sun": "SUN", "galaxy": "GALAXY", "cmb": "CMB"}


class Ctx:
    def __init__(self, seed):
        self.tl = Timeline()
        self.pal = config.PALETTE
        self.rngs = config.Rngs(seed)
        self.tracks = anim.Tracks(self.tl.f1)
        self.fj = json.loads((config.DATA / "frames.json").read_text(encoding="utf-8"))
        self.frames = self.fj["frames"]
        self.frame_by_key = {f["key"]: f for f in self.frames}
        self.comparisons = self.fj["comparisons"]
        self.span = self.fj["span"]
        self.muzzle_m_s = self.fj["muzzle_m_s"]
        self.short = SHORT
        lat = self.fj["site"]["lat_deg"]
        self.frame_line = {"ground": f"GROUND / TEST RANGE {lat:.1f} N", "earth": "EARTH-CENTRED (GCRS)",
                           "sun": "SUN-CENTRED (HCRS)", "galaxy": "GALACTOCENTRIC", "cmb": "CMB REST FRAME"}
        self.passes = {}
        self.numbers = []
        self._colls = {}
        self.cam = None

    def coll(self, name):
        c = self._colls.get(name)
        if c is None:
            c = bpy.data.collections.new(name)
            bpy.context.scene.collection.children.link(c)
            self._colls[name] = c
        return c

    @staticmethod
    def prefix(fr):
        return "~" if fr.get("approx") else ""

    @staticmethod
    def fmt(v):
        d = max(3 - 1 - int(math.floor(math.log10(v))), 0) if v > 0 else 3
        return f"{v:.{d}f}"


def clean_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    prefs = bpy.context.preferences.edit
    prefs.keyframe_new_interpolation_type = "LINEAR"
    scene = bpy.context.scene
    scene.name = "VELOCITY"
    return scene


def build(seed):
    scene = clean_scene()
    ctx = Ctx(seed)
    tl = ctx.tl
    scene.frame_start, scene.frame_end = tl.f0, tl.f1
    scene.render.fps = tl.fps
    # world
    world = bpy.data.worlds.new("void")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (*ctx.pal["bg"], 1)
    bg.inputs["Strength"].default_value = 1.0
    scene.world = world
    # locked camera
    cd = bpy.data.cameras.new("instrument")
    cd.lens, cd.sensor_width, cd.sensor_fit = config.LENS, config.SENSOR, "HORIZONTAL"
    cd.clip_start, cd.clip_end = 0.1, 1000.0
    cam = bpy.data.objects.new("instrument", cd)
    cam.location = (0, -config.CAM_DIST, 0)
    cam.rotation_euler = (math.pi / 2, 0, 0)
    ctx.coll("CAMERA").objects.link(cam)
    scene.camera = cam
    ctx.cam = cam

    ly = Ly.Layers(ctx)
    ly.build_L1()
    ly.build_L2()
    ly.build_L3()
    ly.build_L4()
    ly.build_L5()
    ly.build_dust()
    ly.finish()
    hud = H.Hud(ctx)
    hud.build()
    nkeys = ctx.tracks.bake()
    print(f"[build] {len(bpy.data.objects)} objects, {nkeys} baked keys")
    return scene, ctx, hud


def main():
    a = parse()
    print(f"[build] Blender {bpy.app.version_string}")
    print(f"[build] args {vars(a)}")
    scene, ctx, hud = build(a.seed)
    print(ctx.tl.report())
    fails, notes = validation.run(ctx, hud)
    for n in notes:
        print(f"[validate] {n}")
    for f in fails:
        print(f"[validate] FAIL {f}")
    print(f"[validate] {'PASS' if not fails else f'{len(fails)} FAILURES'}")
    wav = audio.write(ctx, config.OUT / "audio" / "velocity.wav")
    print(f"[audio] {wav}")
    if a.save_blend:
        Path(a.save_blend).resolve().parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(Path(a.save_blend).resolve()))
    if a.validate:
        sys.exit(1 if fails else 0)
    if fails and a.final:
        print("[build] refusing final render with validation failures")
        sys.exit(1)
    profile = "final" if a.final else "preview"
    R.setup(scene, profile, ctx.tl)
    print(f"[build] profile {profile} {config.PROFILES[profile]}")
    if a.stills:
        for f in [int(x) for x in a.stills.split(",")]:
            R.render(scene, profile, f, f, ctx.tl)
        return
    if a.preview or a.final:
        R.render(scene, profile, a.start or ctx.tl.f0, a.end or ctx.tl.f1, ctx.tl)


main()
