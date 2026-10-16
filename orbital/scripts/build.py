"""VELOCITY // 100 M ORBITAL - entry point. Builds the whole film from an empty scene.

    blender -b --python orbital/scripts/build.py -- --validate
    blender -b --python orbital/scripts/build.py -- --preview [--start N --end M]
    blender -b --python orbital/scripts/build.py -- --final
    blender -b --python orbital/scripts/build.py -- --stills 30,140,300 [--preview]
Options: --seed N, --save-blend PATH

Reuses v2 (../../scripts): geometry builders, materials, Tracks baking, the HUD
base class and its font, render settings and the frame loop.
"""
import argparse
import bisect
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oconfig  # noqa: E402  (also puts the v2 scripts on sys.path)

import bpy  # noqa: E402
from mathutils import Euler, Matrix, Vector  # noqa: E402

import anim  # noqa: E402
import config as v2config  # noqa: E402
import geometry as G  # noqa: E402
import materials  # noqa: E402
import render as R  # noqa: E402
from timeline import clamp, ease_in_out, lerp, smoother  # noqa: E402

import oaudio  # noqa: E402
import obuilders as B  # noqa: E402
import ohud  # noqa: E402
import orbits_gn  # noqa: E402
import otimeline as T  # noqa: E402
import ovalidation  # noqa: E402

TRACK_Z = -500.0


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="build.py")
    for flag in ("--validate", "--preview", "--final"):
        ap.add_argument(flag, action="store_true")
    ap.add_argument("--start", type=int)
    ap.add_argument("--end", type=int)
    ap.add_argument("--stills", type=str)
    ap.add_argument("--seed", type=int, default=oconfig.SEED)
    ap.add_argument("--save-blend", type=str)
    return ap.parse_args(argv)


class Ctx:
    def __init__(self, seed):
        self.pal = oconfig.PALETTE
        self.rngs = v2config.Rngs(seed)
        fj = oconfig.load("field.json")
        cols = fj["cols"]
        self.field = [dict(zip(cols, r)) for r in fj["rows"]]
        self.field_count = fj["count"]
        self.epoch = fj["epoch"]
        self.heats = oconfig.load("heats.json")
        fin = oconfig.load("finalists.json")
        self.finalists, self.iss = fin["finalists"], fin["iss"]
        self.race = oconfig.load("race.json")
        self.lanes = self.race["lanes"]
        self.tl = T.TL(self.heats, self.race, self.finalists[0])
        self.race["slow_motion_factor"] = self.tl.slowmo
        self.tracks = anim.Tracks(self.tl.f1)
        self._vp = sorted(o["vp_km_s"] for o in self.field)
        self.numbers = []
        self._colls = {}
        self.cam = None
        self.lane_px, self.mw_px = {}, {}

    def survivors(self, v):
        return len(self._vp) - bisect.bisect_right(self._vp, v)

    def coll(self, name):
        c = self._colls.get(name)
        if c is None:
            c = bpy.data.collections.new(name)
            bpy.context.scene.collection.children.link(c)
            self._colls[name] = c
        return c


# ---------------------------------------------------------------------- camera maths
def look(loc, target, prev=None):
    q = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y")
    return q.to_euler("XYZ", prev) if prev is not None else q.to_euler("XYZ")


def sph(dist, elev, azim):
    e, a = math.radians(elev), math.radians(azim)
    return Vector((dist * math.cos(e) * math.sin(a), -dist * math.cos(e) * math.cos(a), dist * math.sin(e)))


def project(loc, rot, p):
    """World point -> screen pixels for the 50 mm camera."""
    m = rot.to_matrix()
    pc = m.transposed() @ (Vector(p) - Vector(loc))
    k = oconfig.PX_PER_SLOPE / -pc.z
    return (oconfig.RES[0] / 2 + pc.x * k, oconfig.RES[1] / 2 - pc.y * k)


def globe_waypoint(tl, f):
    wps = tl.d["camera"]["waypoints"]
    if f <= wps[0][0]:
        w = wps[0]
        return w[1], w[2], w[3]
    for a, b in zip(wps, wps[1:]):
        if f <= b[0]:
            u = smoother((f - a[0]) / (b[0] - a[0]))
            return math.exp(lerp(math.log(a[1]), math.log(b[1]), u)), lerp(a[2], b[2], u), lerp(a[3], b[3], u)
    w = wps[-1]
    return w[1], w[2], w[3]


class Film:
    def __init__(self, ctx):
        self.c = ctx
        self.cam_pose = {}   # frame -> (loc, rot, depth for pixel sizing)

    # ------------------------------------------------------------------ scene
    def scene(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
        sc = bpy.context.scene
        sc.name = "VELOCITY_100M"
        tl = self.c.tl
        sc.frame_start, sc.frame_end = tl.f0, tl.f1
        sc.render.fps = tl.fps
        world = bpy.data.worlds.new("void")
        world.use_nodes = True
        bg = world.node_tree.nodes["Background"]
        bg.inputs["Color"].default_value = (*self.c.pal["bg"], 1)
        sc.world = world
        cd = bpy.data.cameras.new("cam")
        cd.lens, cd.sensor_width, cd.sensor_fit = v2config.LENS, v2config.SENSOR, "HORIZONTAL"
        cd.clip_start, cd.clip_end = 0.004, 4000.0
        cam = bpy.data.objects.new("cam", cd)
        self.c.coll("CAMERA").objects.link(cam)
        sc.camera = cam
        self.c.cam = cam
        self.clock = G.empty("clock", self.c.coll("CAMERA"))
        return sc

    # ------------------------------------------------------------------ globe part
    def camera_globe(self):
        c, tl = self.c, self.c.tl
        dv = tl.seg["dive"]
        win = dict(c.finalists[0])
        prev = None
        for f in range(tl.f0, dv["end"] + 1):
            if f < dv["start"]:
                d, el, az = globe_waypoint(tl, f)
                loc, target = sph(d, el, az), Vector((0, 0, 0))
                depth = d
            else:
                u = (f - dv["start"]) / (dv["end"] - dv["start"])
                d0, el, az = globe_waypoint(tl, dv["start"] - 1)
                pw = Vector(T.position(win, tl.t[f]))
                target = pw * smoother(min(u * 1.6, 1.0))
                dir0 = sph(1.0, el, az).normalized()
                radial = (pw.normalized() * 0.8 + Vector((0, 0, 0.6))).normalized()
                direc = dir0.lerp(radial, smoother(u)).normalized()
                d = math.exp(lerp(math.log(d0), math.log(tl.d["camera"]["dive_end_dist"]), ease_in_out(u) ** 1.4))
                loc = target + direc * d
                depth = d
            rot = look(loc, target, prev)
            prev = rot
            self.cam_pose[f] = (loc, rot, depth)

    def globe(self):
        c, tl, pal = self.c, self.c.tl, self.c.pal
        end = tl.seg["dive"]["end"]
        objs, curves = B.build_globe_eci(c, sun_eci=(-0.90, -0.40, -0.17))
        px = tl.d["camera"]["graticule_px"]
        for ob in objs:
            c.tracks(ob, "GLOBE").show(tl.f0, end)
        for cv in curves:
            c.tracks.data(cv.data, "bevel_depth",
                          {f: px / 2 * oconfig.px_world_at(max(self.cam_pose[f][2] - 1.0, 0.02)) for f in range(1, end + 1)})
            t = c.tracks(cv, "GLOBE")
            for f in range(1, 12):
                t.set_alpha(f, cv.color[3] * f / 12)

    def field(self):
        c, tl, pal = self.c, self.c.tl, self.c.pal
        end = tl.seg["dive"]["end"]
        fin_ids = {o["id"] for o in c.finalists}
        amber_at = float(tl.seg["finalists"]["start"])
        objs = []
        green, dim = pal["green"], tuple(x * 0.75 for x in pal["green"])
        for o in c.field:
            q = dict(o)
            q["elim"] = tl.elim_frame(o["vp_km_s"])
            q["amber"] = amber_at if o["id"] in fin_ids else 1e6
            q["base"] = green if o["type"] == "ROCKET BODY" else dim
            q["size"] = 2.6 if o["id"] in fin_ids else 1.0
            objs.append(q)
        iss = dict(c.iss, elim=1e6, amber=1e6, base=pal["white"], size=2.4)
        objs.append(iss)
        self.field_objs = objs
        ob = orbits_gn.build_field(c, objs, self.clock)
        c.tracks(ob, "FIELD").show(tl.f0, end)
        # trails: survivors of heat 3, plus the ISS
        h3 = tl.heats[2]["threshold_km_s"]
        tr_objs = [q for q in objs if q["vp_km_s"] > h3] + [iss]
        tr = orbits_gn.build_trails(c, tr_objs, self.clock)
        tr.color = (1, 1, 1, 0.45)
        t = c.tracks(tr, "FIELD")
        t.show(tl.trails_from, end)
        for f in range(tl.trails_from, tl.trails_from + 18):
            t.set_alpha(f, 0.45 * (f - tl.trails_from + 1) / 18)
        dv = tl.seg["dive"]
        for f in range(dv["start"], end + 1):
            t.set_alpha(f, 0.45 * (1 - 0.7 * smoother((f - dv["start"]) / (end - dv["start"]))))
        # the clock: simulated time, point radius, trail radius (all per frame)
        cam = tl.d["camera"]
        for f in range(1, end + 2):
            depth = self.cam_pose[min(f, end)][2]
            c.tracks(self.clock, "CAMERA").key("location", f, (
                tl.t[f], cam["point_px"] * oconfig.px_world_at(depth), cam["trail_px"] / 2 * oconfig.px_world_at(depth)))

    # ------------------------------------------------------------------ race part
    def race_root(self):
        self.troot = G.empty("track_root", self.c.coll("TRACK"), loc=(0, 0, TRACK_Z))

    def camera_race(self):
        c, tl = self.c, self.c.tl
        r = tl.d["race"]
        a, b = tl.seg["dash"]["start"], tl.seg["meanwhile"]["end"]
        off = (r["leader_screen_x"] - 0.5) * oconfig.RES[0] * oconfig.px_world_at(r["cam_dist_m"])
        lane_mid = 3.5 * B.LANE_W
        v_lead = c.lanes[0]["v_km_s"] * 1000
        prev = None
        for f in range(a, tl.seg["dash"]["end"] + 1):
            x_lead = v_lead * tl.real_t(min(f, tl.winner_finish))
            target = Vector((x_lead - off, lane_mid, TRACK_Z))
            loc = target + sph(r["cam_dist_m"], r["cam_elev_deg"], 0)
            rot = look(loc, target, prev)
            prev = rot
            self.cam_pose[f] = (loc, rot, r["cam_dist_m"])
        loc, rot, _ = self.cam_pose[tl.seg["dash"]["end"]]
        for k in range(1, 8):
            c.lane_px[k] = project(loc, rot, (loc.x, (k - 0.5) * B.LANE_W, TRACK_Z + 0.3))[1]
        mc = r["meanwhile_cam"]
        target = Vector(mc["target"]) + Vector((0, 0, TRACK_Z))
        loc = target + sph(mc["dist_m"], mc["elev_deg"], 0)
        rot = look(loc, target)
        for f in range(tl.seg["meanwhile"]["start"], b + 1):
            self.cam_pose[f] = (loc, rot, mc["dist_m"])
        s = c.race["sound_m_at_finish"]
        p_sound = project(loc, rot, (s * 0.6, -0.4 + s * 0.8, TRACK_Z))
        p_runner = project(loc, rot, (0.4, 6.5 * B.LANE_W, TRACK_Z + 1.0))
        c.mw_px["sound"] = (p_sound[0] + 40, p_sound[1] + 30)
        c.mw_px["runner"] = (p_runner[0] + 90, p_runner[1] - 30)
        # results and final card: camera parked looking at nothing
        for f in range(b + 1, tl.f1 + 1):
            self.cam_pose[f] = (Vector((0, 0, TRACK_Z - 50)), Euler((0, 0, 0)), 10.0)

    def track(self):
        c, tl, pal = self.c, self.c.tl, self.c.pal
        a, b = tl.seg["dash"]["start"], tl.seg["meanwhile"]["end"]
        objs = B.build_track(c, self.troot)
        for i, ob in enumerate(objs):
            t = c.tracks(ob, "TRACK")
            t.show(a, b)
            for f in range(a, a + 8):
                t.set_alpha(f, ob.color[3] * (f - a + 1) / 8)
        coll = c.coll("TRACK")
        rs = tl.race_start
        # tokens
        for ln in c.lanes:
            y = (ln["lane"] - 0.5) * B.LANE_W
            if ln["lane"] <= 5:
                root, parts = B.build_rocket_body(f"rb_{ln['lane']}", coll, self.troot, pal, 3.6, 0.6,
                                                  pal["white"] if ln["lane"] > 1 else pal["amber"])
                z, nose = 0.45, 1.8
            elif ln["lane"] == 6:
                root, parts = B.build_iss("iss", coll, self.troot, pal, 1.15, pal["white"])
                z, nose = 0.5, 0.15
            else:
                root, parts = B.build_sprinter("sprinter", coll, self.troot, pal, pal["green"])
                root.location = (0, y, 0)
                for p in parts:
                    c.tracks(p, "TRACK").show(a, b)
                continue
            v = ln["v_km_s"] * 1000
            streak = G.Lines2D()
            streak.quad((0, -0.18), (-12, -0.18), (-12, 0.18), (0, 0.18))
            st = streak.obj(f"streak_{ln['lane']}", coll, root, color=pal["amber"] if ln["lane"] <= 5 else pal["white"],
                            alpha=0.55, mat=materials.streak())
            st.location = (-1.6, 0, -z + 0.03)
            parts.append(st)
            for f in range(a, b + 1):
                x = v * tl.real_t(min(f, tl.winner_finish))   # photo finish: time freezes at the winner's line
                c.tracks(root, "TRACK").key("location", f, (x - nose, y, z))
            for p in parts:
                c.tracks(p, "TRACK").show(a, b)
        # starter's pistol and its sound
        pistol = G.empty("pistol", coll, self.troot, loc=(0, -0.4, 0))
        flash = G.billboard_disc("pistol_flash", (0, 0, 0), 0.6, coll, pistol, pal["amber"])
        flash.rotation_euler = (math.pi / 2, 0, 0)
        c.tracks(flash, "TRACK").show(rs, rs + 2)
        mark = G.billboard_disc("pistol_mark", (0, 0, 0), 0.12, coll, pistol, pal["white"])
        mark.rotation_euler = (math.pi / 2, 0, 0)
        c.tracks(mark, "TRACK").show(a, b)
        sroot, ring = B.build_sound_ring("sound", coll, pistol, pal)
        t = c.tracks(ring, "TRACK")
        t.show(rs, b)
        bev = {}
        for f in range(rs, b + 1):
            ff = min(f, tl.winner_finish)
            rad = max(c.race["sound_m_s"] * tl.real_t(ff), 0.02)
            c.tracks(sroot, "TRACK").key("scale", f, (rad, rad, 1))
            bev[f] = 0.05 / rad
        c.tracks.data(ring.data, "bevel_depth", bev)

    # ------------------------------------------------------------------ camera bake
    def bake_camera(self):
        tr = self.c.tracks(self.c.cam, "CAMERA")
        near, far = {}, {}
        for f, (loc, rot, depth) in self.cam_pose.items():
            tr.key("location", f, tuple(loc))
            tr.key("rotation_euler", f, tuple(rot))
            near[f] = min(depth * 0.02, 0.5)   # the HUD plane sits 2 units in front of the camera
            far[f] = max(depth * 60.0, 400.0)
        self.c.tracks.data(self.c.cam.data, "clip_start", near)
        self.c.tracks.data(self.c.cam.data, "clip_end", far)
        tr.show(self.c.tl.f0, self.c.tl.f1)


def build(seed):
    ctx = Ctx(seed)
    film = Film(ctx)
    sc = film.scene()
    film.camera_globe()
    film.race_root()
    film.camera_race()
    film.globe()
    film.field()
    film.track()
    film.bake_camera()
    hud = ohud.Hud3(ctx)
    hud.build()
    nkeys = ctx.tracks.bake()
    print(f"[build] {len(bpy.data.objects)} objects, {nkeys} baked keys, slow motion {ctx.tl.slowmo:.1f}x")
    return sc, ctx, hud


def main():
    a = parse()
    print(f"[build] Blender {bpy.app.version_string}  args {vars(a)}")
    sc, ctx, hud = build(a.seed)
    fails, notes = ovalidation.run(ctx, hud)
    for n in notes:
        print(f"[validate] {n}")
    for f in fails:
        print(f"[validate] FAIL {f}")
    print(f"[validate] {'PASS' if not fails else f'{len(fails)} FAILURES'}")
    wav = oaudio.write(ctx, oconfig.OUT / "audio" / "velocity_100m.wav")
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
    R.setup(sc, profile, ctx.tl)
    if a.stills:
        for f in [int(x) for x in a.stills.split(",")]:
            R.render(sc, profile, f, f, ctx.tl)
        return
    if a.preview or a.final:
        R.render(sc, profile, a.start or ctx.tl.f0, a.end or ctx.tl.f1, ctx.tl)


main()
