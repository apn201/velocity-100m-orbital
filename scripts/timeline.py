"""Loads timeline.json and derives every frame number the build uses. Pure Python.

The camera never moves. A "pull-out" scales each layer about the anchor point,
which is optically the same as dollying a pinhole camera away from that point.
"""
import math

import config

LAYERS = ["L1", "L2", "L3", "L4", "L5"]


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def smoother(x):
    x = clamp(x)
    return x * x * x * (x * (6 * x - 15) + 10)


def ease_in_out(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def lerp(a, b, t):
    return a + (b - a) * t


class Timeline:
    def __init__(self):
        self.d = config.load("timeline.json")
        self.fps = self.d["fps"]
        self.f0 = self.d["frame_start"]
        self.f1 = self.d["frame_end"]
        self.seg = {s["key"]: s for s in self.d["segments"]}
        z = self.d["zoom"]
        self.gaps = z["gaps"]
        self.dur = z["durations"]
        self.drift = z["drift_per_frame"]
        self.cross = z["crossfade_frames"]
        self.hero_px = self.d["hero_px"]
        # rest log-zoom of each layer
        self.rest = {"L1": 0.0}
        acc = 0.0
        for L in LAYERS[1:]:
            acc += self.gaps[L]
            self.rest[L] = acc
        self.layer_seg = {"L1": "ground", "L2": "earth", "L3": "sun", "L4": "galaxy", "L5": "cmb"}
        self._handoffs()
        self._events()

    @property
    def frames(self):
        return range(self.f0, self.f1 + 1)

    def zeta(self, f):
        """Global log-zoom. 0 = bullet at rest size. Each hold drifts slowly outward,
        and the next pull-out absorbs the drift so every layer lands on its rest scale."""
        if f >= self.seg["local"]["start"]:
            return 0.0
        z = 0.0
        prog = {}
        for L in LAYERS[1:]:
            s = self.seg[self.layer_seg[L]]["start"]
            prog[L] = smoother((f - s) / self.dur[L])
            z += self.gaps[L] * prog[L]
        for i, L in enumerate(LAYERS[1:], start=1):
            s = self.seg[self.layer_seg[L]]["start"] + self.dur[L]
            nxt = LAYERS[i + 1] if i + 1 < len(LAYERS) else None
            e = self.seg[self.layer_seg[nxt]]["start"] if nxt else self.seg["local"]["start"]
            d = self.drift * clamp(f - s, 0, e - s)
            if nxt:
                d *= 1.0 - prog[nxt]
            z += d
        return z

    def scale(self, L, f):
        if f >= self.seg["local"]["start"]:
            return 1.0 if L == "L1" else 1e-6
        return math.exp(self.rest[L] - self.zeta(f))

    def _handoffs(self):
        thr = self.d["zoom"]["handoff_px"]
        self.handoff = {}
        for i, L in enumerate(LAYERS[1:], start=1):
            inner = LAYERS[i - 1]
            s = self.seg[self.layer_seg[L]]["start"]
            for f in range(s, s + self.dur[L] + 1):
                if self.hero_px[inner] * self.scale(inner, f) < thr:
                    self.handoff[L] = f
                    break
            else:
                raise ValueError(f"handoff into {L} never reaches {thr}px")

    def _events(self):
        """Frame-change event start per frame key."""
        self.event = {"ground": self.seg["ground"]["start"]}
        for L in LAYERS[1:]:
            self.event[self.layer_seg[L]] = self.handoff[L]

    def layer_range(self, L):
        """Frames the layer is visible (inclusive), list of (a, b)."""
        h = self.cross // 2
        if L == "L1":
            return [(self.seg["ground"]["start"], self.handoff["L2"] + h),
                    (self.seg["local"]["start"], self.f1 - 1)]
        i = LAYERS.index(L)
        a = self.handoff[L] - h
        b = self.handoff[LAYERS[i + 1]] + h if i + 1 < len(LAYERS) else self.seg["cmb"]["end"]
        return [(a, b)]

    def layer_alpha(self, L, f):
        h = self.cross // 2
        i = LAYERS.index(L)
        nxt = LAYERS[i + 1] if i + 1 < len(LAYERS) else None
        for a, b in self.layer_range(L):
            if not a <= f <= b:
                continue
            if f >= self.seg["local"]["start"]:
                return 1.0
            al = 1.0
            if L != "L1":
                al = clamp((f - a + 1) / (2 * h + 1))
            if nxt:
                al = min(al, clamp((self.handoff[nxt] + h - f + 1) / (2 * h + 1)))
            return al
        return 0.0

    def ev(self, key, name):
        e = self.d["event"]
        base = self.event[key]
        return base + e[name] if isinstance(e[name], int) else [base + x for x in e[name]]

    def report(self):
        lines = []
        for L in LAYERS:
            lines.append(f"{L}: visible {self.layer_range(L)}"
                         + (f", handoff {self.handoff[L]}" if L in self.handoff else ""))
        for k, v in self.event.items():
            lines.append(f"event {k}: {v}")
        return "\n".join(lines)


if __name__ == "__main__":
    t = Timeline()
    print(t.report())
    for f in (145, 160, 171, 200, 240, 267, 363, 433, 460, 504):
        print(f, round(t.zeta(f), 3), {L: round(t.scale(L, f), 4) for L in LAYERS})
