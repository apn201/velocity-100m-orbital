"""Scale layers, handoffs, frame dust and the two comparison passes.

Every layer root sits at the screen anchor. Its scale is exp(rest - zeta(frame)),
baked per frame, so the test article never leaves the anchor."""
import math

import bpy
from mathutils import Vector

import config
import geometry as G
import hud
from timeline import LAYERS, clamp, ease_in_out

ANCHOR_PX = (640, 540)


def anchor_world():
    x = (ANCHOR_PX[0] - config.RES[0] / 2) * config.px_world_at(config.CAM_DIST)
    z = (config.RES[1] / 2 - ANCHOR_PX[1]) * config.px_world_at(config.CAM_DIST)
    return Vector((x, 0.0, z))


def text_obj(name, body, pos, size, color, coll, parent, align="LEFT", alpha=1.0):
    import materials
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.font = hud.font()
    cu.size = size
    cu.align_x = align
    cu.align_y = "BOTTOM_BASELINE"
    cu.materials.append(materials.flat())
    ob = bpy.data.objects.new(name, cu)
    ob.location = (pos[0], pos[1], 0)
    ob.color = (*color, alpha)
    return G.link(ob, coll, parent)


class Layers:
    def __init__(self, ctx):
        self.c = ctx
        self.roots = {}
        self.objs = {L: [] for L in LAYERS}
        self.curves = []  # (curve object, px width, layer, local depth)

    # ------------------------------------------------------------- common
    def root(self, L):
        r = G.empty(f"{L}_root", self.c.coll(L), None, loc=tuple(anchor_world()))
        self.roots[L] = r
        return r

    def add(self, L, *obs):
        for ob in obs:
            if ob.type != "EMPTY":
                self.objs[L].append(ob)

    def width(self, ob, px, L, depth_local=0.0):
        self.curves.append((ob, px, L, depth_local))

    def visible_frames(self, L, margin=1):
        out = []
        for a, b in self.c.tl.layer_range(L):
            out += list(range(max(a - margin, 1), min(b + margin, self.c.tl.f1) + 1))
        return out

    def finish(self):
        tl, tr = self.c.tl, self.c.tracks
        for L in LAYERS:
            root = self.roots[L]
            for f in self.visible_frames(L):
                s = tl.scale(L, f)
                tr(root, L).key("scale", f, (s, s, s))
            for ob in self.objs[L]:
                t = tr(ob, L)
                for a, b in tl.layer_range(L):
                    if not t.vis_custom:
                        t.show(a, b)
                t.mul_alpha(lambda f, L=L: tl.layer_alpha(L, f))
        for ob, px, L, dl in self.curves:
            d = {}
            for f in self.visible_frames(L):
                s = tl.scale(L, f)
                depth = config.CAM_DIST + dl * s
                d[f] = px / 2 * config.px_world_at(depth) / s
            tr.data(ob.data, "bevel_depth", d)

    # ------------------------------------------------------------- L1 range
    def build_L1(self):
        c, tl, pal = self.c, self.c.tl, self.c.pal
        coll = c.coll("L1")
        root = self.root("L1")
        sm = tl.d["slow_motion"]
        fps = tl.fps
        t0 = tl.seg["ground"]["start"]
        broot, body, wire = G.build_projectile("bullet", coll, root, pal, 3.6)
        self.add("L1", body, wire)
        self.width(wire, 1.3, "L1", 0.0)
        spin_hz = c.muzzle_m_s / sm["twist_m"] / sm["factor"]  # rev/s on screen
        for f in self.visible_frames("L1"):
            t = (f - t0) / fps
            c.tracks(broot, "L1").key("rotation_euler", f, (math.tau * spin_hz * t, 0, 0))
        # lights for the bullet only
        for nm, loc, size, energy in (("key", (0.6, -4.5, 4.2), (7.0, 1.2), 420.0),
                                      ("rim", (-0.5, 5.0, 3.0), (7.0, 0.8), 650.0),
                                      ("fill", (-1.5, -6.0, -3.0), (5.0, 3.0), 45.0)):
            ld = bpy.data.lights.new(f"L1_{nm}", "AREA")
            ld.shape = "RECTANGLE"
            ld.size, ld.size_y = size
            ld.energy = energy
            ob = bpy.data.objects.new(f"L1_{nm}", ld)
            ob.location = Vector(loc) + anchor_world()
            ob.rotation_euler = (-Vector(loc)).to_track_quat("-Z", "Y").to_euler()
            G.link(ob, coll, None)
            t = c.tracks(ob, "L1")
            t.vis_custom = True
            t.show(tl.seg["ground"]["start"], tl.handoff["L2"] - tl.cross // 2 - 1)
            t.show(tl.seg["local"]["start"], tl.f1 - 1)

        # backdrop range, in camera space, pixel units at its depth
        ppm = 800.0
        bk = G.empty("range_root", coll, c.cam, loc=(0, 0, -config.BACKDROP_DEPTH),
                     scale=config.px_world_at(config.BACKDROP_DEPTH))
        scaler = G.empty("range_scaler", coll, bk)
        stream = G.empty("range_stream", coll, scaler)
        rroot, grid, ruler = G.build_range("range", coll, stream, pal, ppm, 8.0)
        labels = [text_obj("range_muzzle", "MUZZLE", (12, 252), 26, pal["green"], coll, stream, alpha=0.8)]
        for m in range(1, 8):
            labels.append(text_obj(f"range_{m}m", f"{m} m", (m * ppm + 10, 252), 26, pal["green"], coll, stream,
                                   alpha=0.8))
            c.numbers.append({"name": f"range_{m}m", "frame": "ground", "units": "m", "source": "range"})
        v_scr = c.muzzle_m_s / sm["factor"]  # m/s on screen
        d0 = 0.25
        ax = ANCHOR_PX[0] - config.RES[0] / 2
        for f in self.visible_frames("L1"):
            t = (f - t0) / fps
            s = tl.scale("L1", f)
            c.tracks(scaler, "L1").key("location", f, (ax * (1 - s), 0, 0))
            c.tracks(scaler, "L1").key("scale", f, (s, s, 1))
            c.tracks(stream, "L1").key("location", f, (ax - (d0 + v_scr * t) * ppm, 0, 0))
        fade = lambda f: 1.0 if f >= tl.seg["local"]["start"] else clamp((tl.scale("L1", f) - 0.3) / 0.6)
        for ob in [grid, ruler] + labels:
            self.add("L1", ob)
            c.tracks(ob, "L1").mul_alpha(fade)

    # ------------------------------------------------------------- L2 globe
    def build_L2(self):
        c, tl, pal = self.c, self.c.tl, self.c.pal
        coll = c.coll("L2")
        root = self.root("L2")
        site = c.fj["site"]
        groot, objs, curves, centre = G.build_globe("globe", coll, root, pal, 3.0, site["lat_deg"], site["lon_deg"],
                                                    c.fj["sun_direction_enu"])
        self.add("L2", *objs)
        for cv in curves:
            self.width(cv, 1.8, "L2", 1.5)
        # Saturn V pass on a TLI arc
        ps = tl.d["passes"]["saturn_v"]
        a = tl.event["earth"] + ps["after_event"]
        n = ps["frames"]
        P0, P1, P2 = Vector((-6.8, -0.9, -3.0)), Vector((-1.0, -0.9, 0.9)), Vector((9.5, -0.9, 1.2))

        def B(u):
            return (1 - u) ** 2 * P0 + 2 * (1 - u) * u * P1 + u * u * P2

        def dB(u):
            return 2 * (1 - u) * (P1 - P0) + 2 * u * (P2 - P1)

        rk, robjs = G.build_saturn_v_tli("saturn_v", coll, root, pal, 1.15)
        trail = G.curve_obj("saturn_v_trail", [[tuple(B(i / 200)) for i in range(201)]], 0.01, coll, root,
                            color=pal["amber"], alpha=0.65)
        trail.data.bevel_factor_mapping_end = "SPLINE"
        trail.data.bevel_factor_mapping_start = "SPLINE"
        self.width(trail, 1.8, "L2", -0.9)
        bf = {}
        for f in range(a - 1, a + n + 2):
            u = clamp((f - a) / n)
            p, d = B(u), dB(u)
            c.tracks(rk, "L2").key("location", f, tuple(p))
            c.tracks(rk, "L2").key("rotation_euler", f, (0, -math.atan2(d.z, d.x), 0))
            bf[f] = max(u, 0.001)
        c.tracks.data(trail.data, "bevel_factor_end", bf)
        c.tracks.data(trail.data, "bevel_factor_start", {f: max(v - 0.32, 0.0) for f, v in bf.items()})
        label_end = tl.seg["earth"]["end"]
        for ob in robjs:
            t = c.tracks(ob, "L2")
            t.vis_custom = True
            t.show(a, a + n)
            self.add("L2", ob)
        t = c.tracks(trail, "L2")
        t.vis_custom = True
        t.show(a, label_end)
        for f in range(a + n, label_end + 1):
            t.set_alpha(f, 0.65 * clamp(1 - (f - a - n) / 12))
        self.add("L2", trail)
        aw = anchor_world()

        def screen(f):
            if not a <= f <= a + n:
                return None
            u = clamp((f - a) / n)
            w = aw + tl.scale("L2", f) * B(u)
            return config.world_to_px(*w)
        c.passes["saturn_v"] = {"label": (a + 2, label_end), "screen": screen}

    # ------------------------------------------------------------- L3 orbits
    def build_L3(self):
        c, tl, pal = self.c, self.c.tl, self.c.pal
        coll = c.coll("L3")
        root = self.root("L3")
        oroot, objs, curves, w, sun_c = G.build_orbits("orbits", coll, root, pal, 4.5, 25.0)
        self.add("L3", *objs)
        self.width(curves[0], 1.8, "L3", 3.0)
        self.width(curves[1], 1.3, "L3", 3.0)
        ps = tl.d["passes"]["pioneer_10"]
        a = tl.event["sun"] + ps["after_event"]
        n = ps["frames"]
        X = Vector((1, 0, 0))

        def p(u):
            return X * (9.8 - 17.0 * u) + w * 1.9

        pr, pobjs = G.build_pioneer_10("pioneer_10", coll, root, pal, 0.62)
        trail = G.curve_obj("pioneer_trail", [[tuple(p(i / 100)) for i in range(101)]], 0.01, coll, root,
                            color=pal["amber"], alpha=0.6)
        trail.data.bevel_factor_mapping_end = "SPLINE"
        trail.data.bevel_factor_mapping_start = "SPLINE"
        self.width(trail, 1.8, "L3", 1.7)
        bf = {}
        for f in range(a - 1, a + n + 2):
            u = clamp((f - a) / n)
            c.tracks(pr, "L3").key("location", f, tuple(p(u)))
            c.tracks(pr, "L3").key("rotation_euler", f, (math.radians(-20), 0, math.radians(18 + 25 * u)))
            bf[f] = max(u, 0.001)
        c.tracks.data(trail.data, "bevel_factor_end", bf)
        c.tracks.data(trail.data, "bevel_factor_start", {f: max(v - 0.13, 0.0) for f, v in bf.items()})
        label_end = tl.seg["sun"]["end"]
        for ob in pobjs:
            t = c.tracks(ob, "L3")
            t.vis_custom = True
            t.show(a, a + n)
            self.add("L3", ob)
        t = c.tracks(trail, "L3")
        t.vis_custom = True
        t.show(a, label_end)
        for f in range(a + n, label_end + 1):
            t.set_alpha(f, 0.6 * clamp(1 - (f - a - n) / 12))
        self.add("L3", trail)
        aw = anchor_world()

        def screen(f):
            if not a <= f <= a + n:
                return None
            w_ = aw + tl.scale("L3", f) * p(clamp((f - a) / n))
            return config.world_to_px(*w_)
        c.passes["pioneer_10"] = {"label": (a + 2, label_end), "screen": screen}

    # ------------------------------------------------------------- L4 galaxy
    def build_L4(self):
        c = self.c
        coll = c.coll("L4")
        root = self.root("L4")
        groot, objs, curves, gc = G.build_galaxy("galaxy", coll, root, c.pal, c.rngs.get("galaxy"), 6.0, 3.3, 38.0,
                                                 0.010, (2600, 500, 600, 500))
        self.add("L4", *objs)
        self.width(curves[0], 1.2, "L4", 3.5)

    # ------------------------------------------------------------- L5 CMB
    def build_L5(self):
        c = self.c
        coll = c.coll("L5")
        root = self.root("L5")
        sroot, objs, curves = G.build_cmb_sphere("cmb", coll, root, c.pal, 2.1, (1.0, 0.3, 0.32))
        self.add("L5", *objs)
        self.width(curves[0], 1.3, "L5", 0.0)

    # ------------------------------------------------------------- frame dust
    def build_dust(self):
        c, tl, pal = self.c, self.c.tl, self.c.pal
        coll = c.coll("DUST")
        droot = G.empty("dust_root", coll, c.cam, loc=(0, 0, -config.DUST_DEPTH),
                        scale=config.px_world_at(config.DUST_DEPTH))
        e = tl.d["event"]["dust_fade"]
        keys = [fr["key"] for fr in c.frames]
        spec = {"ground": ((300, 230), pal["muted"], 0.55), "earth": ((220, 170), pal["green"], 0.5),
                "sun": ((200, 150), pal["green"], 0.55), "galaxy": ((190, 140), pal["green"], 0.6),
                "cmb": ((180, 130), pal["green"], 0.65)}
        c.dust_streaks = {}
        for i, fr in enumerate(c.frames):
            key = fr["key"]
            v = fr["speed_km_s"] * 1000.0
            L = clamp(-150.0 + 70.0 * math.log10(v), 8.0, 320.0)  # streak length, log of speed
            c.dust_streaks[key] = L
            spacing, tint, amax = spec[key]
            root, pts, streaks = G.build_dust(f"dust_{key}", coll, droot, pal, c.rngs.get(f"dust_{key}"), L,
                                              spacing, tint)
            pts.color[3] = amax
            streaks.color[3] = amax
            v_px = 8.5 * L
            s = tl.event[key] + e[0]
            end = tl.event[keys[i + 1]] + e[1] if i + 1 < len(keys) else tl.seg["cmb"]["end"]
            ranges = [(s, end)]
            if key == "ground":
                ranges.append((tl.seg["local"]["start"], tl.f1 - 1))
            for f in range(1, tl.f1 + 1):
                if any(a - 1 <= f <= b + 1 for a, b in ranges):
                    c.tracks(root, "DUST").key("location", f, (-((v_px * f / tl.fps) % 2400.0), 0, 0))
            nxt = tl.event[keys[i + 1]] if i + 1 < len(keys) else None

            def al(f, s=s, nxt=nxt):
                if f >= tl.seg["local"]["start"]:
                    return 1.0
                a = clamp((f - s + 1) / (e[1] - e[0]))
                if nxt is not None:
                    a = min(a, clamp((nxt + e[1] - f) / (e[1] - e[0])))
                return a
            for ob in (pts, streaks):
                t = c.tracks(ob, "DUST")
                for a, b in ranges:
                    t.show(a, b)
                t.mul_alpha(al)
