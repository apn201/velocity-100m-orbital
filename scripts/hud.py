"""HUD: camera-parented, laid out in screen pixels from hud_layout.json.

Counter rolls are pre-built text objects, one per intermediate value, switched by
baked hide_render keys. No frame handlers."""
import math
import os

import bpy

import config
import geometry as G
import materials
from timeline import clamp, ease_in_out

_font = None


def font():
    global _font
    if _font is None:
        p = os.path.join(os.path.dirname(bpy.app.binary_path), f"{bpy.app.version[0]}.{bpy.app.version[1]}",
                         "datafiles", "fonts", "DejaVuSansMono.woff2")
        _font = bpy.data.fonts.load(p)
    return _font


ADV = 0.602  # DejaVu Sans Mono advance width per em


class Hud:
    def __init__(self, ctx):
        self.c = ctx
        self.lay = config.load("hud_layout.json")
        self.coll = ctx.coll("HUD")
        k = config.HUD_DEPTH / config.PX_PER_SLOPE
        self.root = G.empty("hud_root", self.coll, ctx.cam, loc=(0, 0, -config.HUD_DEPTH), scale=k)
        self.texts = []  # for validation: (obj, size_px, essential, meta)

    # ---------------------------------------------------------------- helpers
    def P(self, x, y):
        return config.px_to_hud(x, y)

    def text(self, name, body, pos, size, color, align="LEFT", essential=False, meta=None, alpha=1.0):
        cu = bpy.data.curves.new(name, "FONT")
        cu.body = body
        cu.font = font()
        cu.size = size
        cu.align_x = align
        cu.align_y = "BOTTOM_BASELINE"
        cu.materials.append(materials.flat())
        ob = bpy.data.objects.new(name, cu)
        x, y = self.P(*pos)
        ob.location = (x, y, 0)
        ob.color = (*color, alpha)
        G.link(ob, self.coll, self.root)
        w = len(body) * ADV * size
        x0 = pos[0] - (w if align == "RIGHT" else w / 2 if align == "CENTER" else 0)
        self.texts.append({"obj": ob, "size": size, "essential": essential, "meta": meta or {},
                           "bbox": (x0, pos[1] - 0.75 * size, x0 + w, pos[1] + 0.22 * size), "body": body})
        return ob

    def lines(self, name, build, color, alpha=1.0, mat=None):
        g = G.Lines2D()
        build(g)
        return g.obj(name, self.coll, self.root, color=color, alpha=alpha, mat=mat)

    def track(self, ob):
        return self.c.tracks(ob, "HUD")

    # ---------------------------------------------------------------- build
    def build(self):
        c, tl, pal, L = self.c, self.c.tl, self.c.pal, self.lay
        W, H = config.RES
        ax, ay = L["anchor"]
        end_main = tl.seg["cmb"]["end"]
        b = tl.d["boot"]

        # faint grid
        def grid(g):
            s = L["grid_step"]
            for x in range(0, W + 1, s):
                g.seg(self.P(x, 0), self.P(x, H), 1.4, False)
            for y in range(0, H + 1, s):
                g.seg(self.P(0, y), self.P(W, y), 1.4, False)
        ob = self.lines("hud_grid", grid, pal["green"], 0.06)
        t = self.track(ob)
        t.show(1, end_main)
        for f in range(1, b["grid_fade"][1] + 1):
            t.set_alpha(f, 0.06 * clamp((f - b["grid_fade"][0] + 1) / (b["grid_fade"][1] - b["grid_fade"][0] + 1)))

        # crosshair through the anchor, drawn on outward from a gap around it
        gap = 300
        arms = [((ax - gap, ay), (0, ay)), ((ax + gap, ay), (W, ay)), ((ax, ay - gap), (ax, 0)), ((ax, ay + gap), (ax, H))]
        for i, (p0, p1) in enumerate(arms):
            hx0, hy0 = self.P(*p0)
            hx1, hy1 = self.P(*p1)
            ob = self.lines(f"hud_cross_{i}", lambda g: g.seg((0, 0), (hx1 - hx0, hy1 - hy0), 1.6, False),
                            pal["green"], 0.22)
            ob.location = (hx0, hy0, 0)
            t = self.track(ob)
            t.show(b["crosshair_draw"][0], end_main)
            a0, a1 = b["crosshair_draw"]
            for f in range(a0, a1 + 2):
                s = max(ease_in_out((f - a0) / (a1 - a0)), 1e-3)
                t.key("scale", f, (s, s, 1))

        # coordinate ticks along the edges of the title-safe frame
        x0, y0, x1, y1 = L["title_safe"]

        def ticks(g):
            for x in range(x0, x1 + 1, 40):
                ln = 16 if (x - x0) % 200 == 0 else 7
                g.seg(self.P(x, y0), self.P(x, y0 + ln), 1.6, False)
                g.seg(self.P(x, y1), self.P(x, y1 - ln), 1.6, False)
            for y in range(y0, y1 + 1, 40):
                ln = 16 if (y - y0) % 200 == 0 else 7
                g.seg(self.P(x0, y), self.P(x0 + ln, y), 1.6, False)
        ob = self.lines("hud_edge_ticks", ticks, pal["green"], 0.4)
        t = self.track(ob)
        t.show(b["ticks_draw"][0], end_main)
        for f in range(b["ticks_draw"][0], b["ticks_draw"][1] + 1):
            t.set_alpha(f, 0.4 * clamp((f - b["ticks_draw"][0]) / (b["ticks_draw"][1] - b["ticks_draw"][0])))

        # title flicker
        ti = L["title"]
        ob = self.text("hud_title", "VELOCITY // FLIGHT TEST 001", ti["pos"], ti["size"], pal["white"], "CENTER",
                       essential=True)
        t = self.track(ob)
        rng = c.rngs.get("title_flicker")
        f0, f1 = b["title_flicker"]
        for f in range(f0, f1 + 1):
            p = (f - f0) / (f1 - f0)
            on = rng.random() < (0.35 if p < 0.3 else 0.95 if p < 0.85 else 0.3)
            if on:
                t.show(f, f)

        self.build_ladder()
        self.build_tracking_box()
        self.build_object_block()
        self.build_readout()
        self.build_frame_line()
        self.build_comparisons()
        self.build_labels()
        self.build_final()

    # ---------------------------------------------------------------- ladder
    def ly(self, v):
        d = self.lay["ladder"]
        u = (math.log10(v) - d["log_min"]) / (d["log_max"] - d["log_min"])
        return d["y_bottom"] - u * (d["y_bottom"] - d["y_top"])

    def build_ladder(self):
        c, tl, pal, d = self.c, self.c.tl, self.c.pal, self.lay["ladder"]
        end_main = tl.seg["cmb"]["end"]
        b = tl.d["boot"]["ladder_draw"]
        x = d["x"]
        hx0, hy0 = self.P(x, d["y_bottom"])
        hy1 = self.P(x, d["y_top"])[1]
        axis = self.lines("ladder_axis", lambda g: g.seg((0, 0), (0, hy1 - hy0), 2.0), pal["green"], 0.8)
        axis.location = (hx0, hy0, 0)
        t = self.track(axis)
        t.show(b[0], end_main)
        for f in range(b[0], b[1] + 2):
            s = max(ease_in_out((f - b[0]) / (b[1] - b[0])), 1e-3)
            t.key("scale", f, (1, s, 1))

        def dec(g):
            for e in range(d["log_min"], d["log_max"] + 1):
                y = self.ly(10 ** e)
                g.seg(self.P(x, y), self.P(x + 14, y), 2.0, False)
                for m in range(2, 10):
                    if e < d["log_max"]:
                        ym = self.ly(m * 10 ** e)
                        g.seg(self.P(x, ym), self.P(x + 6, ym), 1.4, False)
        ob = self.lines("ladder_decades", dec, pal["green"], 0.6)
        objs = [ob]
        for e in range(d["log_min"], d["log_max"] + 1):
            v = 10 ** e
            s = f"{v:g}"
            objs.append(self.text(f"ladder_axis_{e}", s, (x + 22, self.ly(v) + 8), d["axis_size"], pal["muted"],
                                  meta={"kind": "axis", "units": "km/s", "source": "ladder-axis"}))
        objs.append(self.text("ladder_units", "km/s  LOG", (1816, d["y_top"] - 34), d["axis_size"], pal["muted"], "RIGHT",
                              meta={"kind": "text"}))
        for ob in objs:
            t = self.track(ob)
            t.show(b[0], end_main)
            for f in range(b[0], b[1] + 1):
                t.set_alpha(f, ob.color[3] * clamp((f - b[0]) / (b[1] - b[0])))

        # one tick per reference frame
        tick_frames = {}
        for fr in c.frames:
            key = fr["key"]
            land = tl.ev(key, "tick_land")
            tick_frames[key] = land
            y = self.ly(fr["speed_km_s"])
            tk = self.lines(f"ladder_tick_{key}", lambda g, y=y: g.seg(self.P(x - 26, y), self.P(x + 2, y), 3.0),
                            pal["white"])
            lab = self.text(f"ladder_label_{key}", f"{c.prefix(fr)}{fr['display']} {c.short[key]}",
                            (x - d["label_gap"] - 18, y + 10), d["label_size"], pal["white"], "RIGHT",
                            meta={"kind": "speed", "frame": key, "units": "km/s", "source": fr["source"]})
            for ob in (tk, lab):
                t = self.track(ob)
                t.show(land, end_main)
                for i in range(0, 10):
                    f = land + i
                    k = i / 9
                    t.set_rgb(f, tuple(pal["amber"][j] * (1 - k) + pal["white"][j] * k for j in range(3)))
                    t.key("location", f, (ob.location.x + 40 * (1 - ease_in_out(min(i / 4, 1))), ob.location.y, 0))
                t.set_rgb(land + 10, pal["white"])
        # span bracket and label, after the last tick
        last = c.frames[-1]
        land = tick_frames[last["key"]] + 2
        ya, yb = self.ly(c.frames[0]["speed_km_s"]), self.ly(last["speed_km_s"])
        sx = d["span_x"]

        def br(g):
            g.seg(self.P(sx, ya), self.P(sx, yb), 2.4)
            g.seg(self.P(sx, ya), self.P(sx + 18, ya), 2.4)
            g.seg(self.P(sx, yb), self.P(sx + 18, yb), 2.4)
        bro = self.lines("ladder_span_bracket", br, pal["amber"])
        lab = self.text("ladder_span", c.span["display"], (sx - 16, (ya + yb) / 2 + 16), d["span_size"], pal["amber"],
                        "RIGHT", essential=True,
                        meta={"kind": "speed", "frame": "ratio", "units": "x", "source": "frames.py:span"})
        for ob in (bro, lab):
            t = self.track(ob)
            t.show(land, end_main)
            for f in range(land, land + 6):
                t.set_alpha(f, (f - land + 1) / 6)

    # ---------------------------------------------------------------- tracking box
    def build_tracking_box(self):
        c, tl, pal = self.c, self.c.tl, self.c.pal
        ax, ay = self.lay["anchor"]
        h = self.lay["tracking_box"] / 2
        ln = h * 0.45

        def box(g):
            for sx in (-1, 1):
                for sy in (-1, 1):
                    cx, cy = ax + sx * h, ay + sy * h
                    g.seg(self.P(cx, cy), self.P(cx - sx * ln, cy), 2.2)
                    g.seg(self.P(cx, cy), self.P(cx, cy - sy * ln), 2.2)
        ob = self.lines("hud_track_box", box, pal["green"], 0.9)
        t = self.track(ob)
        a = next(f for f in range(tl.seg["earth"]["start"], tl.f1) if tl.hero_px["L1"] * tl.scale("L1", f) < 150)
        t.show(a, tl.seg["cmb"]["end"])
        for f in range(a, a + 10):
            t.set_alpha(f, 0.9 * (f - a + 1) / 10)

    # ---------------------------------------------------------------- object block
    def build_object_block(self):
        c, tl, pal, L = self.c, self.c.tl, self.c.pal, self.lay
        a, end_main = tl.seg["ground"]["start"], tl.seg["cmb"]["end"]
        for name, key, body, col, ess in (("hud_obj_name", "object_name", "9x19 mm PROJECTILE", pal["white"], True),
                                          ("hud_obj_detail", "object_detail", "147 gr FMJ", pal["muted"], False)):
            ob = self.text(name, body, L[key]["pos"], L[key]["size"], col, essential=ess,
                           meta={"kind": "spec", "units": "mm/gr", "source": "frames.py:ground"})
            self.track(ob).show(a, end_main)
        keys = [fr["key"] for fr in c.frames]
        for i, key in enumerate(keys):
            ob = self.text(f"hud_shot_{key}", f"FRAME {i + 1}/{len(keys)}", L["shot_index"]["pos"],
                           L["shot_index"]["size"], pal["muted"], meta={"kind": "index"})
            s = tl.event[key]
            e = tl.event[keys[i + 1]] - 1 if i + 1 < len(keys) else end_main
            self.track(ob).show(s, e)

    # ---------------------------------------------------------------- readout
    def build_readout(self):
        c, tl, pal, r = self.c, self.c.tl, self.c.pal, self.lay["readout"]
        e = tl.d["event"]
        steps = e["roll_steps"]
        end_main = tl.seg["cmb"]["end"]
        unit = self.text("hud_unit", "km/s", (r["pos"][0] + r["unit_gap"], r["pos"][1]), r["unit_size"], pal["white"],
                         essential=True, meta={"kind": "units"})
        ut = self.track(unit)
        ut.show(tl.seg["ground"]["start"], end_main)
        ut.show(tl.seg["local"]["start"], tl.f1 - 1)
        prev = None
        keys = [fr["key"] for fr in c.frames]
        self.final_value_obj = None
        for i, fr in enumerate(c.frames):
            key = fr["key"]
            r0 = tl.ev(key, "roll_start")
            nxt_r0 = tl.ev(keys[i + 1], "roll_start") if i + 1 < len(keys) else end_main + 1
            a = prev["speed_km_s"] if prev else 0.0
            bv = fr["speed_km_s"]
            for k in range(steps):
                u = ease_in_out((k + 1) / steps)
                if k == steps - 1:
                    txt = fr["display"]
                elif prev is None:
                    txt = f"{bv * u:.3f}"
                else:
                    txt = c.fmt(math.exp(math.log(a) + (math.log(bv) - math.log(a)) * u))
                ob = self.text(f"readout_{key}_{k:02d}", c.prefix(fr) + txt, r["pos"], r["size"], pal["white"],
                               "RIGHT", essential=True,
                               meta={"kind": "speed", "frame": key, "units": "km/s", "source": fr["source"]})
                t = self.track(ob)
                if k == steps - 1:
                    t.show(r0 + k, nxt_r0 - 1)
                    if i == 0:
                        t.show(tl.seg["local"]["start"], tl.f1 - 1)
                else:
                    t.show(r0 + k, r0 + k)
            # the old value holds until the roll starts; before the first roll show 0.000
            if prev is None:
                ob = self.text("readout_zero", "0.000", r["pos"], r["size"], pal["white"], "RIGHT", essential=True,
                               meta={"kind": "speed", "frame": key, "units": "km/s", "source": fr["source"]})
                self.track(ob).show(tl.event[key], r0 - 1)
            prev = fr

    # ---------------------------------------------------------------- frame line
    def build_frame_line(self):
        c, tl, pal, fl = self.c, self.c.tl, self.c.pal, self.lay["frame_line"]
        e = tl.d["event"]
        keys = [fr["key"] for fr in c.frames]
        end_main = tl.seg["cmb"]["end"]
        for i, fr in enumerate(c.frames):
            key = fr["key"]
            body = "FRAME: " + c.frame_line[key]
            ob = self.text(f"frame_line_{key}", body, fl["pos"], fl["size"], pal["white"], essential=True,
                           meta={"kind": "frame"})
            t = self.track(ob)
            s = tl.event[key]
            end = tl.event[keys[i + 1]] - 1 if i + 1 < len(keys) else end_main
            t.show(s, end)
            for f in range(s, s + e["amber_frames"]):
                t.set_rgb(f, pal["amber"])
            for j in range(e["white_fade"] + 1):
                k = j / e["white_fade"]
                t.set_rgb(s + e["amber_frames"] + j,
                          tuple(pal["amber"][m] * (1 - k) + pal["white"][m] * k for m in range(3)))

    # ---------------------------------------------------------------- comparisons
    def build_comparisons(self):
        c, tl, pal = self.c, self.c.tl, self.c.pal
        for cmp_ in c.comparisons:
            key = cmp_["key"]
            lay = self.lay["comparison"][key]
            ps = c.passes[key]
            verb = "OVERTAKEN BY" if cmp_["speed_km_s"] > c.frame_by_key[cmp_["frame"]]["speed_km_s"] else "OVERTAKING"
            line2 = f"{cmp_['display']} {cmp_['units']}" + (f" / {cmp_['detail']}" if cmp_["detail"] else "")
            x, y = lay["pos"]
            l1 = self.text(f"cmp_{key}_1", f"{verb}: {cmp_['name']}", (x, y), lay["size"], pal["amber"], essential=True,
                           meta={"kind": "name"})
            l2 = self.text(f"cmp_{key}_2", line2, (x, y + lay["size2"] * 1.35), lay["size2"], pal["amber"],
                           essential=True,
                           meta={"kind": "speed", "frame": cmp_["frame"], "units": cmp_["units"],
                                 "source": cmp_["source"]})
            a, b = ps["label"]
            for ob in (l1, l2):
                t = self.track(ob)
                t.show(a, b)
                for f in range(a, a + 4):
                    t.set_alpha(f, (f - a + 1) / 4)
            # leader line: from under the label to the object's projected position, baked per frame
            start = (x - 14, y + lay["size2"] * 1.35 + 14)
            lead = self.lines(f"cmp_{key}_leader", lambda g: g.seg((0, 0), (1, 0), 2.0, False), pal["amber"], 0.8)
            t = self.track(lead)
            sx, sy = self.P(*start)
            vis_frames = []
            for f in range(a, b + 1):
                px = ps["screen"](f)
                if px is None or not (0 <= px[0] <= config.RES[0] and 0 <= px[1] <= config.RES[1]):
                    continue
                ex, ey = self.P(*px)
                dx, dy = ex - sx, ey - sy
                Ld = math.hypot(dx, dy)
                # stop short of the object
                Ld = max(Ld - 34, 1.0)
                t.key("location", f, (sx, sy, 0))
                t.key("rotation_euler", f, (0, 0, math.atan2(dy, dx)))
                t.key("scale", f, (Ld, 1, 1))
                vis_frames.append(f)
            if vis_frames:
                t.show(vis_frames[0], vis_frames[-1])
                for f in range(vis_frames[0], vis_frames[0] + 4):
                    t.set_alpha(f, 0.8 * (f - vis_frames[0] + 1) / 4)

    # ---------------------------------------------------------------- schematic labels
    def build_labels(self):
        c, tl, pal, sl = self.c, self.c.tl, self.c.pal, self.lay["schematic_label"]
        for L, body in (("L2", "GLOBE: GRATICULE 15 deg, NO COASTLINES"), ("L3", "ORBITS TO SCALE, BODIES NOT"),
                        ("L4", "MILKY WAY (SCHEMATIC)"), ("L5", "CMB DIPOLE (SCHEMATIC)")):
            ob = self.text(f"label_{L}", body, sl["pos"], sl["size"], pal["muted"], meta={"kind": "text"})
            t = self.track(ob)
            a = tl.handoff[L] + 4
            b = tl.layer_range(L)[0][1] - 4 if L != "L5" else tl.seg["cmb"]["end"]
            t.show(a, b)
            for f in range(a, a + 6):
                t.set_alpha(f, (f - a + 1) / 6)

    # ---------------------------------------------------------------- final card
    def build_final(self):
        c, tl, pal, fc = self.c, self.c.tl, self.c.pal, self.lay["final_card"]
        fin = tl.d["final"]
        x, y = fc["pos"]
        a = self.text("final_motion", "MOTION DETECTED.", (x, y), fc["size"], pal["amber"], essential=True,
                      meta={"kind": "text"})
        b = self.text("final_frame", "REFERENCE FRAME: LOCAL.", (x, y + fc["line_gap"]), fc["size"], pal["amber"],
                      essential=True, meta={"kind": "frame"})
        self.track(a).show(fin["motion_detected"], fin["black"] - 1)
        self.track(b).show(fin["reference_frame"], fin["black"] - 1)
