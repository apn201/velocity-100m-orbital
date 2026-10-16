"""Per-frame tracks, computed in Python and baked to F-Curves at the end of the build.

Nothing is keyframed by hand and nothing runs in a frame handler. Every animated
value is a pure function of the frame number, sampled here and written as keys
only where the value changes, so linear interpolation reproduces it exactly.
"""
import bpy

CONSTANT, LINEAR = 0, 1


class Track:
    def __init__(self, ob, n, layer):
        self.ob = ob
        self.layer = layer
        self.n = n
        self.vis = [False] * (n + 2)
        self.base_alpha = ob.color[3]
        self.alpha = [self.base_alpha] * (n + 2)
        self.rgb = None
        self.vis_custom = False
        self.xf = {}  # data_path -> {frame: tuple}

    def show(self, a, b):
        for f in range(max(a, 1), min(b, self.n) + 1):
            self.vis[f] = True

    def hide(self, a, b):
        for f in range(max(a, 1), min(b, self.n) + 1):
            self.vis[f] = False

    def set_alpha(self, f, a):
        if 1 <= f <= self.n:
            self.alpha[f] = a

    def mul_alpha(self, fn):
        for f in range(1, self.n + 1):
            self.alpha[f] *= fn(f)

    def set_rgb(self, f, rgb):
        if self.rgb is None:
            base = tuple(self.ob.color[:3])
            self.rgb = [base] * (self.n + 2)
        if 1 <= f <= self.n:
            self.rgb[f] = tuple(rgb)

    def key(self, path, f, value):
        self.xf.setdefault(path, {})[f] = tuple(value) if hasattr(value, "__len__") else (value,)


class Tracks:
    def __init__(self, n):
        self.n = n
        self.items = {}
        self.data_tracks = []  # (id, path, {frame: value})

    def __call__(self, ob, layer=None):
        t = self.items.get(ob.name)
        if t is None:
            t = Track(ob, self.n, layer)
            self.items[ob.name] = t
        elif layer is not None:
            t.layer = layer
        return t

    def data(self, idblock, path, values):
        self.data_tracks.append((idblock, path, values))

    # ------------------------------------------------------------------ bake
    @staticmethod
    def _fc(idb, path, index=0):
        ad = idb.animation_data_create()
        if ad.action is None:
            ad.action = bpy.data.actions.new(f"{idb.name}_act")
        return ad.action.fcurve_ensure_for_datablock(idb, path, index=index)

    @staticmethod
    def _write(fc, pts, interp):
        fc.keyframe_points.add(len(pts))
        flat = [c for p in pts for c in p]
        fc.keyframe_points.foreach_set("co", flat)
        fc.keyframe_points.foreach_set("interpolation", [interp] * len(pts))
        fc.update()

    @staticmethod
    def _compress(frames, vals, eps=1e-7):
        out = []
        k = len(frames)
        for i in range(k):
            if i == 0 or i == k - 1:
                out.append((frames[i], vals[i]))
                continue
            if abs(vals[i] - vals[i - 1]) > eps or abs(vals[i] - vals[i + 1]) > eps:
                out.append((frames[i], vals[i]))
        return out

    def bake(self):
        nkeys = 0
        for t in self.items.values():
            ob = t.ob
            # visibility: hidden wherever not shown or alpha is zero
            vis = [t.vis[f] and t.alpha[f] > 1e-4 for f in range(self.n + 2)]
            vis[0] = False
            hide = []
            prev = None
            for f in range(0, self.n + 1):
                h = 0.0 if vis[f] else 1.0
                if h != prev:
                    hide.append((max(f, 0), h))
                    prev = h
            for path in ("hide_render", "hide_viewport"):
                self._write(self._fc(ob, path), hide, CONSTANT)
            nkeys += 2 * len(hide)
            for path, d in t.xf.items():
                fr = sorted(d)
                dim = len(d[fr[0]])
                for i in range(dim):
                    pts = self._compress(fr, [d[f][i] for f in fr])
                    self._write(self._fc(ob, path, i), pts, LINEAR)
                    nkeys += len(pts)
            # colour / alpha, only over visible frames (+ one frame of margin)
            vf = [f for f in range(1, self.n + 1) if vis[f] or vis[f - 1] or vis[f + 1]]
            if not vf:
                continue
            al = [t.alpha[f] for f in vf]
            if any(abs(a - t.base_alpha) > 1e-7 for a in al):
                pts = self._compress(vf, al)
                self._write(self._fc(ob, "color", 3), pts, LINEAR)
                nkeys += len(pts)
            if t.rgb is not None:
                for i in range(3):
                    pts = self._compress(vf, [t.rgb[f][i] for f in vf])
                    self._write(self._fc(ob, "color", i), pts, LINEAR)
                    nkeys += len(pts)
        for idb, path, d in self.data_tracks:
            fr = sorted(d)
            pts = self._compress(fr, [d[f] for f in fr])
            self._write(self._fc(idb, path), pts, LINEAR)
            nkeys += len(pts)
        return nkeys
