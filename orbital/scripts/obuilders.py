"""v3 builders. The globe is v2's build_globe, re-oriented so the root is the
Earth-centred inertial frame (Z = north, 1 unit = 1 Earth radius). The track is in
metres. Primitives (Lines2D, lathe, curve_obj, mesh_obj, text) are v2's."""
import math

import bpy
from mathutils import Matrix, Vector

import geometry as G
import layers
import materials

TAU = math.tau
LANE_W = 1.22
_opaque = None


def opaque():
    """Like v2's flat material, but depth-writing, so blended lines and text sort correctly against it."""
    global _opaque
    if _opaque is None:
        m, nt, out = materials._base("flat_opaque", "DITHERED")
        oi = nt.nodes.new("ShaderNodeObjectInfo")
        em = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(oi.outputs["Color"], em.inputs["Color"])
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        _opaque = m
    return _opaque


def build_globe_eci(ctx, sun_eci):
    """v2's globe seen from the north pole, rotated back into ECI axes, centre at the origin."""
    coll = ctx.coll("GLOBE")
    R = 1.0
    holder = G.empty("globe_eci", coll)
    rot = Matrix(((0, 0, -1), (1, 0, 0), (0, -1, 0))).to_4x4()
    holder.matrix_world = rot @ Matrix.Translation((0, -R, 0))
    s = Vector(sun_eci).normalized()
    sun_enu = (s.y, -s.x, s.z)  # ENU of the pole "site" at lon 0
    root, objs, curves, centre = G.build_globe("globe", coll, holder, ctx.pal, R, 90.0, 0.0, sun_enu)
    keep = [o for o in objs if not o.name.endswith(("_site", "_site_ring"))]
    for o in objs:
        if o not in keep:
            o.hide_render = o.hide_viewport = True
    return keep, curves


def ground(name, coll, parent, x0, x1, y0, y1, color, alpha=1.0, z=0.0):
    v = [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)]
    return G.mesh_obj(name, v, [(0, 1, 2, 3)], opaque(), coll, parent, color=color, alpha=alpha)


def build_track(ctx, root, lanes=7, length=100.0):
    """Lane lines, start and finish lines, 10 m ticks and labels, on the XY plane in metres."""
    coll, pal = ctx.coll("TRACK"), ctx.pal
    objs = [ground("track_ground", coll, root, -80, 150, -16, lanes * LANE_W + 24, pal["globe"], 1.0, -0.06)]
    g = G.Lines2D()
    for k in range(lanes + 1):
        g.seg((-80, k * LANE_W), (150, k * LANE_W), 0.05, False)
    objs.append(g.obj("track_lanes", coll, root, color=pal["green"], alpha=0.75))
    w = G.Lines2D()
    for x in (0.0, length):
        w.rect(x - 0.08, 0, x + 0.08, lanes * LANE_W)
    objs.append(w.obj("track_lines", coll, root, color=pal["white"]))
    t = G.Lines2D()
    for m in range(-30, int(length) + 31, 10):
        if m in (0, int(length)):
            continue
        t.rect(m - 0.04, -0.9, m + 0.04, -0.2)
        t.rect(m - 0.04, lanes * LANE_W + 0.2, m + 0.04, lanes * LANE_W + 0.9)
    objs.append(t.obj("track_ticks", coll, root, color=pal["green"], alpha=0.8))
    for m in range(10, int(length) + 1, 10):
        body = "FINISH" if m == length else f"{m} m"
        ob = layers.text_obj(f"track_{m}m", body, (m + (0.3 if m == length else -0.9 * len(body) * 0.3), -2.4),
                             1.5, pal["white"] if m == length else pal["green"], coll, root, alpha=0.9)
        objs.append(ob)
        ctx.numbers.append({"name": ob.name, "units": "m", "source": "track"})
    st = layers.text_obj("track_start", "START", (-5.2, -2.4), 1.5, pal["white"], coll, root)
    objs.append(st)
    for k in range(1, lanes + 1):
        ob = layers.text_obj(f"track_lane_{k}", str(k), (-3.0, (k - 0.5) * LANE_W - 0.4), 0.9, pal["white"], coll, root,
                             alpha=0.85)
        objs.append(ob)
    return objs


def build_rocket_body(name, coll, parent, pal, length, diameter, colour):
    """Generic upper stage along +X (nose forward): tank cylinder, dome, inter-tank band, one engine bell."""
    root = G.empty(name, coll, parent)
    L, r = length, diameter / 2
    prof = [(-0.5 * L, 0.0), (-0.5 * L, r * 0.92), (-0.48 * L, r), (0.38 * L, r), (0.47 * L, r * 0.72),
            (0.5 * L, r * 0.3), (0.5 * L, 0.0)]
    v, f = G.lathe(prof, 28)
    body = G.mesh_obj(f"{name}_tank", v, f, opaque(), coll, root, color=colour)
    bell = [(-0.5 * L, r * 0.22), (-0.62 * L, r * 0.45), (-0.74 * L, r * 0.82), (-0.745 * L, 0.0)]
    v, f = G.lathe(bell, 20)
    eng = G.mesh_obj(f"{name}_bell", v, f, opaque(), coll, root, color=pal["muted"])
    bands = G.curve_obj(f"{name}_bands", [G.circle3((x, 0, 0), (0, 1, 0), (0, 0, 1), r * 1.03, 28)
                                         for x in (-0.3 * L, 0.05 * L, 0.38 * L)],
                        0.012 * L, coll, root, color=pal["bg"], closed=True, mat=opaque())
    return root, [body, eng, bands]


def build_iss(name, coll, parent, pal, span, colour):
    """Silhouette: truss across the lane (Y), 8 solar wings, a module stack along X, two radiators."""
    root = G.empty(name, coll, parent)
    k = span / 109.0  # real truss span ~109 m
    objs = []

    def box(nm, c, s, col, alpha=1.0):
        cx, cy, cz = c
        sx, sy, sz = s
        v = [(cx + dx * sx / 2, cy + dy * sy / 2, cz + dz * sz / 2)
             for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)]
        f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        objs.append(G.mesh_obj(f"{name}_{nm}", v, f, opaque(), coll, root, color=col, alpha=alpha))

    box("truss", (0, 0, 0), (2.4 * k, 109 * k, 2.4 * k), colour)
    for i, y in enumerate((-46, -34, 34, 46)):
        for j, sgn in enumerate((-1, 1)):
            box(f"wing_{i}{j}", (sgn * 19 * k, y * k, 0), (34 * k, 11.6 * k, 0.4 * k), pal["amber"], 0.85)
    box("modules", (0, 0, -4 * k), (52 * k, 4.4 * k, 4.4 * k), colour)
    for i, y in enumerate((-14, 14)):
        box(f"radiator_{i}", (0, y * k, 6 * k), (12 * k, 3 * k, 0.4 * k), pal["muted"])
    return root, objs


def capsule_lines(segs):
    return [[tuple(a), tuple(b)] for a, b in segs]


def build_sprinter(name, coll, parent, pal, colour):
    """Wireframe figure in the 'set' position, facing +X, hands on the start line (x = 0).
    Built from thick curve segments (capsules) and a head ring. Never moves."""
    root = G.empty(name, coll, parent)
    J = {
        "hand_l": (0.0, 0.18, 0.0), "hand_r": (0.0, -0.18, 0.0),
        "sh_l": (0.05, 0.2, 0.6), "sh_r": (0.05, -0.2, 0.6),
        "neck": (0.1, 0.0, 0.66), "hip_l": (-0.5, 0.12, 0.74), "hip_r": (-0.5, -0.12, 0.74),
        "knee_f": (-0.3, 0.12, 0.38), "foot_f": (-0.62, 0.12, 0.06),
        "knee_b": (-0.74, -0.12, 0.2), "foot_b": (-1.02, -0.12, 0.1),
    }
    segs = [("hand_l", "sh_l"), ("hand_r", "sh_r"), ("sh_l", "sh_r"), ("sh_l", "hip_l"), ("sh_r", "hip_r"),
            ("hip_l", "hip_r"), ("hip_l", "knee_f"), ("knee_f", "foot_f"), ("hip_r", "knee_b"), ("knee_b", "foot_b")]
    limbs = G.curve_obj(f"{name}_limbs", capsule_lines([(J[a], J[b]) for a, b in segs]), 0.045, coll, root,
                        color=colour, mat=opaque())
    head = G.curve_obj(f"{name}_head", [G.circle3((0.2, 0, 0.66), (1, 0, 0), (0, 0, 1), 0.11, 24),
                                        G.circle3((0.2, 0, 0.66), (0, 1, 0), (0, 0, 1), 0.11, 24)],
                       0.022, coll, root, color=colour, closed=True, mat=opaque())
    blocks = G.curve_obj(f"{name}_blocks", [[(-0.62, 0.25, 0.02), (-0.62, -0.25, 0.02)],
                                            [(-1.02, 0.25, 0.02), (-1.02, -0.25, 0.02)]],
                         0.04, coll, root, color=pal["muted"], mat=opaque())
    return root, [limbs, head, blocks]


def build_sound_ring(name, coll, parent, pal):
    """Unit circle on the ground around the pistol; its scale is the sound radius in metres."""
    root = G.empty(name, coll, parent)
    ring = G.curve_obj(f"{name}_ring", [G.circle3((0, 0, 0.02), (1, 0, 0), (0, 1, 0), 1.0, 128)], 0.012, coll, root,
                       color=pal["amber"], closed=True)
    return root, ring
