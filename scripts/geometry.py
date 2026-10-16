"""All builders. Each takes a name, a parent (transform), a palette and, where it
needs randomness, a named seeded RNG, and returns its root object."""
import math

import bpy
from mathutils import Matrix, Vector

import materials

TAU = math.tau


# ------------------------------------------------------------------ primitives
def link(ob, coll, parent=None):
    coll.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


def empty(name, coll, parent=None, loc=(0, 0, 0), scale=1.0):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_size = 0.2
    ob.location = loc
    ob.scale = (scale, scale, scale)
    return link(ob, coll, parent)


def mesh_obj(name, verts, faces, mat, coll, parent=None, uv=None, col=None,
             color=(1, 1, 1), alpha=1.0, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    if uv is not None:
        lay = me.uv_layers.new(name="UV")
        vi = [0] * len(me.loops)
        me.loops.foreach_get("vertex_index", vi)
        lay.data.foreach_set("uv", [c for i in vi for c in uv[i]])
    if col is not None:
        at = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
        at.data.foreach_set("color", [c for v in col for c in v])
    if smooth:
        me.shade_smooth()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    ob.color = (*color, alpha)
    return link(ob, coll, parent)


def curve_obj(name, polylines, radius, coll, parent=None, color=(1, 1, 1), alpha=1.0,
              closed=False, mat=None):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 1
    cu.fill_mode = "FULL"
    for pts in polylines:
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        sp.points.foreach_set("co", [c for p in pts for c in (p[0], p[1], p[2], 1.0)])
        sp.use_cyclic_u = closed
    cu.materials.append(mat or materials.flat())
    ob = bpy.data.objects.new(name, cu)
    ob.color = (*color, alpha)
    return link(ob, coll, parent)


class Lines2D:
    """Accumulates flat quads in a 2D pixel plane (z = 0)."""

    def __init__(self):
        self.v, self.f, self.uv = [], [], []

    def quad(self, a, b, c, d, uvs=((0, 0), (1, 0), (1, 1), (0, 1))):
        i = len(self.v)
        self.v += [(a[0], a[1], 0), (b[0], b[1], 0), (c[0], c[1], 0), (d[0], d[1], 0)]
        self.uv += list(uvs)
        self.f.append((i, i + 1, i + 2, i + 3))

    def seg(self, p0, p1, w, extend=True):
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dy) or 1e-9
        ux, uy = dx / L, dy / L
        nx, ny = -uy * w / 2, ux * w / 2
        e = w / 2 if extend else 0
        a = (p0[0] - ux * e, p0[1] - uy * e)
        b = (p1[0] + ux * e, p1[1] + uy * e)
        self.quad((a[0] - nx, a[1] - ny), (b[0] - nx, b[1] - ny), (b[0] + nx, b[1] + ny), (a[0] + nx, a[1] + ny))

    def poly(self, pts, w, closed=False):
        n = len(pts)
        for i in range(n if closed else n - 1):
            self.seg(pts[i], pts[(i + 1) % n], w)

    def rect(self, x0, y0, x1, y1):
        self.quad((x0, y0), (x1, y0), (x1, y1), (x0, y1))

    def dashed(self, p0, p1, w, dash, gap):
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dy)
        s = 0.0
        while s < L:
            e = min(s + dash, L)
            self.seg((p0[0] + dx * s / L, p0[1] + dy * s / L), (p0[0] + dx * e / L, p0[1] + dy * e / L), w, False)
            s += dash + gap

    def circle(self, c, r, w, n=48):
        self.poly([(c[0] + r * math.cos(TAU * i / n), c[1] + r * math.sin(TAU * i / n)) for i in range(n)], w, True)

    def disc(self, c, r, n=24):
        for i in range(n):
            a0, a1 = TAU * i / n, TAU * (i + 1) / n
            p0 = (c[0] + r * math.cos(a0), c[1] + r * math.sin(a0))
            p1 = (c[0] + r * math.cos(a1), c[1] + r * math.sin(a1))
            self.quad(c, p0, p1, c)

    def obj(self, name, coll, parent=None, color=(1, 1, 1), alpha=1.0, mat=None):
        return mesh_obj(name, self.v, self.f, mat or materials.flat(), coll, parent,
                        uv=self.uv, color=color, alpha=alpha)


def circle3(center, u, v, r, n=96):
    c, u, v = Vector(center), Vector(u), Vector(v)
    return [tuple(c + r * (math.cos(TAU * i / n) * u + math.sin(TAU * i / n) * v)) for i in range(n)]


def billboard_disc(name, center, r, coll, parent, color, alpha=1.0, n=20):
    """Flat disc facing the camera (camera looks along +Y)."""
    cx, cy, cz = center
    v = [(cx, cy, cz)] + [(cx + r * math.cos(TAU * i / n), cy, cz + r * math.sin(TAU * i / n)) for i in range(n)]
    f = [(0, 1 + i, 1 + (i + 1) % n) for i in range(n)]
    return mesh_obj(name, v, f, materials.flat(), coll, parent, color=color, alpha=alpha)


def billboard_ring(name, center, r, w, coll, parent, color, alpha=1.0, n=48):
    cx, cy, cz = center
    v, f = [], []
    for i in range(n):
        a = TAU * i / n
        v += [(cx + (r - w / 2) * math.cos(a), cy, cz + (r - w / 2) * math.sin(a)),
              (cx + (r + w / 2) * math.cos(a), cy, cz + (r + w / 2) * math.sin(a))]
    for i in range(n):
        j = (i + 1) % n
        f.append((2 * i, 2 * j, 2 * j + 1, 2 * i + 1))
    return mesh_obj(name, v, f, materials.flat(), coll, parent, color=color, alpha=alpha)


def lathe(profile, n, radius_fn=None):
    """profile: list of (axial, radius). Axis = +X. Returns verts, faces."""
    verts, rings = [], []
    for k, (z, r) in enumerate(profile):
        if r < 1e-9:
            rings.append([len(verts)])
            verts.append((z, 0.0, 0.0))
            continue
        ring = []
        for i in range(n):
            th = TAU * i / n
            rr = radius_fn(z, r, th) if radius_fn else r
            ring.append(len(verts))
            verts.append((z, rr * math.cos(th), rr * math.sin(th)))
        rings.append(ring)
    faces = []
    for a, b in zip(rings, rings[1:]):
        if len(a) == 1 and len(b) == 1:
            continue
        if len(a) == 1:
            faces += [(a[0], b[(i + 1) % n], b[i]) for i in range(n)]
        elif len(b) == 1:
            faces += [(a[i], a[(i + 1) % n], b[0]) for i in range(n)]
        else:
            faces += [(a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]) for i in range(n)]
    return verts, faces


# ------------------------------------------------------------------ builders
BULLET = {"length_mm": 16.5, "radius_mm": 4.51, "shank_mm": 8.6, "meplat_r_mm": 1.8,
          "grooves": 6, "groove_frac": 0.36, "groove_depth_mm": 0.05, "twist_m": 0.254}


def bullet_profile(p=BULLET):
    R, Ls, L, rm = p["radius_mm"], p["shank_mm"], p["length_mm"], p["meplat_r_mm"]
    # tangent ogive from (Ls, R) through (L, rm)
    dz = L - Ls
    dr = R - rm
    Rog = (dz * dz + dr * dr) / (2 * dr)
    prof = [(0.0, 0.0), (0.0, R - 0.3), (0.08, R - 0.12), (0.3, R)]
    for i in range(1, 30):
        prof.append((0.3 + (Ls - 0.3) * i / 30, R))
    for i in range(0, 41):
        z = Ls + dz * i / 40
        r = (R - Rog) + math.sqrt(max(Rog * Rog - (z - Ls) ** 2, 0.0))
        prof.append((z, r))
    prof[-1] = (L, rm)
    prof += [(L, rm * 0.5), (L, 0.0)]
    return prof


def build_projectile(name, coll, parent, pal, length_bu):
    p = BULLET
    k = length_bu / p["length_mm"]
    twist = math.atan(math.pi * 2 * p["radius_mm"] / (p["twist_m"] * 1000))  # helix angle
    n = 192

    def phase(z, r, th):
        return th - (z * math.tan(twist)) / r

    def rfn(z, r, th):
        if 1.0 < z < p["shank_mm"] - 0.2 and abs(r - p["radius_mm"]) < 1e-6:
            u = (phase(z, r, th) * p["grooves"] / TAU) % 1.0
            if u < p["groove_frac"]:
                return r - p["groove_depth_mm"]
        return r

    prof = bullet_profile()
    verts, faces = lathe(prof, n, rfn)
    verts = [((z - p["length_mm"] / 2) * k, y * k, w * k) for z, y, w in verts]
    root = empty(name, coll, parent)
    body = mesh_obj(f"{name}_jacket", verts, faces, materials.metal(pal["copper"]), coll, root, smooth=True)
    # wireframe edge pass: groove edges on the shank continuing up the ogive, plus profile rings
    lines = []
    R = p["radius_mm"] * 1.012
    for g in range(p["grooves"]):
        th0 = TAU * g / p["grooves"]
        pts = []
        for z, r in prof[3:-2]:
            rr = r * 1.012
            th = th0 + (min(z, p["shank_mm"]) * math.tan(twist)) / p["radius_mm"]
            pts.append(((z - p["length_mm"] / 2) * k, rr * k * math.cos(th), rr * k * math.sin(th)))
        lines.append(pts)
    for zr in (0.3, p["shank_mm"], 12.6, p["length_mm"]):
        r = min(prof, key=lambda q: abs(q[0] - zr))[1] * 1.012 if zr < p["length_mm"] else p["meplat_r_mm"] * 1.01
        lines.append(circle3(((zr - p["length_mm"] / 2) * k, 0, 0), (0, 1, 0), (0, 0, 1), r * k, 96))
    wire = curve_obj(f"{name}_wire", lines, 0.0045, coll, root, color=pal["green"], alpha=0.55)
    wire.data.splines[-1].use_cyclic_u = True
    for sp in list(wire.data.splines)[p["grooves"]:]:
        sp.use_cyclic_u = True
    return root, body, wire


def build_range(name, coll, parent, pal, px_per_m, length_m):
    """Backdrop in pixel units: graph grid every 0.1 m, ruler with 0.1 m / 1 m ticks, muzzle marker.
    x = 0 is the muzzle."""
    root = empty(name, coll, parent)
    cell = px_per_m * 0.1
    x0, x1 = -1600, length_m * px_per_m + 1600
    g = Lines2D()
    x = math.floor(x0 / cell) * cell
    while x <= x1:
        g.seg((x, -760), (x, 760), 1.6, False)
        x += cell
    y = -760
    while y <= 760:
        g.seg((x0, y), (x1, y), 1.6, False)
        y += cell
    grid = g.obj(f"{name}_grid", coll, root, color=pal["green_dim"], alpha=0.10)
    r = Lines2D()
    ry = 240
    r.seg((x0, ry), (x1, ry), 2.0)
    i = int(x0 / cell)
    while i * cell <= x1:
        major = i % 10 == 0
        r.seg((i * cell, ry), (i * cell, ry - (30 if major else 12)), 2.0 if major else 1.6, False)
        i += 1
    r.dashed((0, -380), (0, 300), 2.4, 18, 12)
    ruler = r.obj(f"{name}_ruler", coll, root, color=pal["green"], alpha=0.7)
    return root, grid, ruler


def build_dust(name, coll, parent, pal, rng, streak_px, spacing, tint, tile_w=2400, tile_h=1400):
    """Frame dust: a jittered lattice of points and ticks, each with a streak trailing to the right.
    Two tiles side by side so a modulo offset streams seamlessly."""
    root = empty(name, coll, parent)
    heads, tails = Lines2D(), Lines2D()
    sx, sy = spacing
    cols, rows = int(tile_w / sx), int(tile_h / sy)
    pts = []
    for j in range(rows):
        for i in range(cols):
            px = -tile_w / 2 + (i + 0.5) * sx + rng.uniform(-0.38, 0.38) * sx
            py = -tile_h / 2 + (j + 0.5) * sy + rng.uniform(-0.38, 0.38) * sy
            kind = rng.random()
            pts.append((px, py, kind))
    for tile in (0, 1):
        ox = tile * tile_w
        for px, py, kind in pts:
            x, y = px + ox, py
            if kind < 0.16:
                heads.seg((x - 7, y), (x + 7, y), 2.0, False)
                heads.seg((x, y - 7), (x, y + 7), 2.0, False)
            else:
                heads.rect(x - 2, y - 2, x + 2, y + 2)
            L = streak_px * (0.75 + 0.5 * ((kind * 7.13) % 1.0))
            tails.quad((x, y - 1.1), (x + L, y - 1.1), (x + L, y + 1.1), (x, y + 1.1),
                       uvs=((0, 0), (1, 0), (1, 1), (0, 1)))
    h = heads.obj(f"{name}_pts", coll, root, color=tint, alpha=1.0)
    t = tails.obj(f"{name}_streaks", coll, root, color=tint, alpha=1.0, mat=materials.streak())
    return root, h, t


def enu_to_view():
    """Site ENU -> view: east = +X (screen right), north = +Z (up), up = -Y (toward camera)."""
    return Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))


def build_globe(name, coll, parent, pal, radius, lat_deg, lon_deg, sun_enu):
    """Wireframe globe seen straight down onto the test site. The site is at the
    root origin; the centre sits radius behind it."""
    root = empty(name, coll, parent)
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    east = Vector((-math.sin(lon), math.cos(lon), 0))
    north = Vector((-math.sin(lat) * math.cos(lon), -math.sin(lat) * math.sin(lon), math.cos(lat)))
    up = Vector((math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)))
    ecef_to_enu = Matrix((east, north, up))
    M = enu_to_view() @ ecef_to_enu
    centre = Vector((0, radius, 0))

    def P(v_ecef, r=radius):
        return tuple(centre + (M @ Vector(v_ecef)) * r)

    # solid core, rotated with the same matrix so its UV seam is out of sight
    nlat, nlon = 48, 96
    verts, faces = [], []
    for i in range(nlat + 1):
        th = math.pi * i / nlat
        for j in range(nlon):
            ph = TAU * j / nlon
            verts.append(P((math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th)), radius * 0.996))
    for i in range(nlat):
        for j in range(nlon):
            a, b = i * nlon + j, i * nlon + (j + 1) % nlon
            faces.append((a, b, b + nlon, a + nlon))
    core = mesh_obj(f"{name}_core", verts, faces, materials.globe(pal["globe"]), coll, root, smooth=True)
    lines = []
    for la in range(-75, 90, 15):
        t = math.radians(la)
        lines.append([P((math.cos(t) * math.cos(TAU * j / 144), math.cos(t) * math.sin(TAU * j / 144), math.sin(t)), radius * 1.002)
                      for j in range(144)])
    for lo in range(0, 360, 15):
        p_ = math.radians(lo)
        lines.append([P((math.cos(math.radians(a)) * math.cos(p_), math.cos(math.radians(a)) * math.sin(p_),
                         math.sin(math.radians(a))), radius * 1.002) for a in range(-90, 91, 2)])
    grid = curve_obj(f"{name}_graticule", lines[:11], 0.01, coll, root, color=pal["green"], alpha=0.75, closed=True)
    mer = curve_obj(f"{name}_meridians", lines[11:], 0.01, coll, root, color=pal["green"], alpha=0.75)
    # site marker
    dot = billboard_disc(f"{name}_site", (0, -0.01, 0), 0.03, coll, root, pal["white"])
    ring = billboard_ring(f"{name}_site_ring", (0, -0.01, 0), 0.12, 0.012, coll, root, pal["green"])
    # sun lamp: the terminator comes from the real sun direction at the epoch
    s = enu_to_view() @ Vector(sun_enu)
    ld = bpy.data.lights.new(f"{name}_sun", "SUN")
    ld.energy = 4.0
    ld.angle = math.radians(1.0)
    sun = bpy.data.objects.new(f"{name}_sun", ld)
    sun.rotation_euler = (-s).to_track_quat("-Z", "Y").to_euler()
    link(sun, coll, root)
    return root, [core, grid, mer, dot, ring, sun], (grid, mer), centre


def build_saturn_v_tli(name, coll, parent, pal, length):
    """S-IVB + SLA + CSM, the stack that remains at translunar injection. Axis +X, nose +X.
    Silhouette only: cylinders, a taper, a cone, one J-2 bell, an exhaust taper."""
    root = empty(name, coll, parent)
    # real proportions in metres: S-IVB 17.8 x 6.6 dia, SLA 8.5 taper 6.6->3.9, SM 7.5 x 3.9, CM 3.2 cone
    segs = [(0.0, 3.3), (17.8, 3.3), (17.8, 3.3), (26.3, 1.95), (33.8, 1.95), (33.9, 1.95), (37.1, 0.25), (37.3, 0.0)]
    tot = 37.3
    k = length / tot
    prof = [(0.0, 0.0)] + [(z, r) for z, r in segs]
    v, f = lathe([((z - tot / 2) * k, r * k) for z, r in prof], 24)
    body = mesh_obj(f"{name}_body", v, f, materials.flat(), coll, root, color=pal["white"], alpha=0.92)
    bands = curve_obj(f"{name}_bands", [circle3(((z - tot / 2) * k, 0, 0), (0, 1, 0), (0, 0, 1), r * k * 1.02, 32)
                                         for z, r in ((4.0, 3.3), (17.8, 3.3), (26.3, 1.95))],
                      0.006, coll, root, color=pal["bg"], closed=True)
    bell = [(0.0, 0.6), (-1.2, 1.0), (-3.0, 1.45)]
    v, f = lathe([((z - tot / 2) * k, r * k) for z, r in bell], 20)
    nozzle = mesh_obj(f"{name}_j2", v, f, materials.flat(), coll, root, color=pal["muted"])
    ex = [(-3.0, 1.3), (-9.0, 0.9), (-20.0, 0.0)]
    v, f = lathe([((z - tot / 2) * k, r * k) for z, r in ex], 20)
    exhaust = mesh_obj(f"{name}_exhaust", v, f, materials.flat(), coll, root, color=pal["amber"], alpha=0.55)
    return root, [body, bands, nozzle, exhaust]


def build_pioneer_10(name, coll, parent, pal, size):
    """Dish, hexagonal bus behind it, two RTG booms at 120 deg and a long magnetometer boom.
    Dish axis along -Y (toward camera), so it reads as a disc with booms."""
    root = empty(name, coll, parent)
    k = size / 2.74  # dish diameter 2.74 m
    prof = [(0.0, 0.0), (0.12, 0.5), (0.3, 0.95), (0.45, 1.37)]
    v, f = lathe([(z * k, r * k) for z, r in prof], 40)
    rot = Matrix.Rotation(math.radians(90), 3, "Z")
    v = [tuple(rot @ Vector(p)) for p in v]
    dish = mesh_obj(f"{name}_dish", v, f, materials.flat(), coll, root, color=pal["white"], alpha=0.9)
    hexv = []
    for d in (0.0, 0.36):
        for i in range(6):
            a = TAU * i / 6
            hexv.append((0.71 * k * math.cos(a), (0.5 + d) * k, 0.71 * k * math.sin(a)))
    hexf = [(i, (i + 1) % 6, 6 + (i + 1) % 6, 6 + i) for i in range(6)] + [tuple(range(6)), tuple(range(11, 5, -1))]
    bus = mesh_obj(f"{name}_bus", hexv, hexf, materials.flat(), coll, root, color=pal["muted"])
    booms = []
    for a, L in ((math.radians(210), 3.0), (math.radians(330), 3.0), (math.radians(90), 6.6)):
        d = Vector((math.cos(a), 0.6, math.sin(a))).normalized()
        booms.append([(0, 0.6 * k, 0), tuple(Vector((0, 0.6 * k, 0)) + d * L * k)])
    b = curve_obj(f"{name}_booms", booms, 0.012, coll, root, color=pal["white"], alpha=0.9)
    rtg = []
    for a in (math.radians(210), math.radians(330)):
        d = Vector((math.cos(a), 0.6, math.sin(a))).normalized()
        rtg.append([tuple(Vector((0, 0.6 * k, 0)) + d * 2.0 * k), tuple(Vector((0, 0.6 * k, 0)) + d * 3.0 * k)])
    r = curve_obj(f"{name}_rtg", rtg, 0.05, coll, root, color=pal["muted"])
    return root, [dish, bus, b, r]


def build_orbits(name, coll, parent, pal, r_earth, tilt_deg):
    """Sun-centred layer. Earth (the marker) at the origin, moving +X. Sun at r_earth * w."""
    root = empty(name, coll, parent)
    t = math.radians(tilt_deg)
    w = Vector((0, math.cos(t), math.sin(t)))
    sun_c = r_earth * w
    X = Vector((1, 0, 0))
    objs = []
    earth = curve_obj(f"{name}_earth_orbit", [circle3(sun_c, X, w, r_earth, 256)], 0.012, coll, root,
                      color=pal["green"], alpha=0.85, closed=True)
    inner = curve_obj(f"{name}_inner", [circle3(sun_c, X, w, r_earth * a, 256) for a in (0.387, 0.723, 1.524)],
                      0.008, coll, root, color=pal["green_dim"], alpha=0.6, closed=True)
    sun = billboard_disc(f"{name}_sun", tuple(sun_c), 0.16, coll, root, pal["white"])
    sun_ring = billboard_ring(f"{name}_sun_ring", tuple(sun_c), 0.26, 0.012, coll, root, pal["muted"], 0.7)
    dot = billboard_disc(f"{name}_earth", (0, -0.01, 0), 0.03, coll, root, pal["white"])
    objs = [earth, inner, sun, sun_ring, dot]
    return root, objs, (earth, inner), w, sun_c


def log_spiral_galaxy(rng, n_arm, n_bar, n_bulge, n_disk, r_max, r_sun):
    """Points (u, v) in the galactic plane, Sun at (0, -r_sun) relative to the centre,
    rotation counter-clockwise in (u, v) so the Sun moves +u. Trailing arms."""
    pts = []
    pitch = math.radians(12.5)
    b = math.tan(pitch)
    a = 0.18 * r_max
    for arm in range(2):
        th0 = math.pi * arm + 0.6
        for _ in range(n_arm):
            r = a + (r_max - a) * rng.random() ** 0.8
            th = th0 - math.log(r / a) / b
            sc = 0.032 * r_max * (0.5 + r / r_max)
            pts.append((r * math.cos(th) + rng.gauss(0, sc), r * math.sin(th) + rng.gauss(0, sc),
                        0.55 + 0.45 * rng.random()))
    ang = math.radians(28) + math.pi / 2 + math.pi
    L = 0.24 * r_max
    for _ in range(n_bar):
        s = rng.uniform(-L, L)
        pts.append((s * math.cos(ang) + rng.gauss(0, 0.03 * r_max), s * math.sin(ang) + rng.gauss(0, 0.03 * r_max),
                    0.6 + 0.4 * rng.random()))
    for _ in range(n_bulge):
        r = abs(rng.gauss(0, 0.07 * r_max))
        t = rng.uniform(0, TAU)
        pts.append((r * math.cos(t), r * math.sin(t), 0.7 + 0.3 * rng.random()))
    for _ in range(n_disk):
        r = r_max * math.sqrt(rng.random())
        t = rng.uniform(0, TAU)
        pts.append((r * math.cos(t), r * math.sin(t), 0.18 + 0.25 * rng.random()))
    # shift so the Sun is at the origin
    return [(u, v + r_sun, br) for u, v, br in pts]


def build_galaxy(name, coll, parent, pal, rng, r_max, r_sun, tilt_deg, pt_size, counts):
    root = empty(name, coll, parent)
    t = math.radians(tilt_deg)
    w = Vector((0, math.cos(t), math.sin(t)))
    X = Vector((1, 0, 0))
    pts = log_spiral_galaxy(rng, *counts, r_max, r_sun)
    verts, faces, cols = [], [], []
    h = pt_size
    for u, v, br in pts:
        c = u * X + v * w
        i = len(verts)
        s = h * (0.7 + 0.6 * br)
        verts += [(c.x - s, c.y, c.z - s), (c.x + s, c.y, c.z - s), (c.x + s, c.y, c.z + s), (c.x - s, c.y, c.z + s)]
        faces.append((i, i + 1, i + 2, i + 3))
        cols += [(br, br, br, br)] * 4
    cloud = mesh_obj(f"{name}_stars", verts, faces, materials.points(), coll, root, col=cols, color=pal["green"])
    gc = r_sun * w
    sun_orbit = curve_obj(f"{name}_sun_orbit", [circle3(gc, X, w, r_sun, 256)], 0.008, coll, root,
                          color=pal["muted"], alpha=0.45, closed=True)
    dot = billboard_disc(f"{name}_sun", (0, -0.02, 0), 0.03, coll, root, pal["white"])
    return root, [cloud, sun_orbit, dot], (sun_orbit,), gc


def build_cmb_sphere(name, coll, parent, pal, radius, dipole_dir):
    root = empty(name, coll, parent)
    # inward-facing sphere + backface culling: only the far inner hemisphere draws, like a sky
    nlat, nlon = 48, 96
    verts, faces = [], []
    for i in range(nlat + 1):
        th = math.pi * i / nlat
        for j in range(nlon):
            ph = TAU * j / nlon
            verts.append((radius * math.sin(th) * math.cos(ph), radius * math.sin(th) * math.sin(ph), radius * math.cos(th)))
    for i in range(nlat):
        for j in range(nlon):
            a, b = i * nlon + j, i * nlon + (j + 1) % nlon
            faces.append((a, a + nlon, b + nlon, b))  # reversed winding: normals point inward
    sky = mesh_obj(f"{name}_sky", verts, faces, materials.dipole(pal["green"], pal["amber"], dipole_dir),
                   coll, root, color=(1, 1, 1))
    lines = []
    d = Vector(dipole_dir).normalized()
    u = d.orthogonal().normalized()
    v = d.cross(u)
    for k in range(-2, 3):  # circles of constant angle to the dipole
        a = math.radians(30 * k)
        lines.append(circle3(tuple(d * radius * math.sin(a)), u, v, radius * math.cos(a), 144))
    for k in range(6):
        ang = math.pi * k / 6
        e = math.cos(ang) * u + math.sin(ang) * v
        lines.append(circle3((0, 0, 0), d, e, radius, 144))
    grat = curve_obj(f"{name}_lines", lines, 0.008, coll, root, color=pal["green"], alpha=0.35, closed=True)
    dot = billboard_disc(f"{name}_galaxy", (0, -0.02, 0), 0.03, coll, root, pal["white"])
    return root, [sky, grat, dot], (grat,)
