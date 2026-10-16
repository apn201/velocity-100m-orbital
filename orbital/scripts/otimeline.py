"""Every frame number and every animated quantity of v3, as pure functions of the frame.
Pure Python (no bpy), so it can be checked outside Blender."""
import math

import oconfig
from timeline import clamp, ease_in_out, lerp, smoother  # v2 easing


def kepler_E(M, e, iters=10):
    """Same starter and iteration count as the Geometry Nodes tree."""
    E = M + 0.85 * e * (1 if math.sin(M) >= 0 else -1)
    for _ in range(iters):
        E -= (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
    return E


def pq(o):
    """Perifocal unit vectors P, Q in the Earth-centred inertial frame (Blender world: Z = north)."""
    W, w, i = math.radians(o["raan_deg"]), math.radians(o["argp_deg"]), math.radians(o["i_deg"])
    cW, sW, cw, sw, ci, si = math.cos(W), math.sin(W), math.cos(w), math.sin(w), math.cos(i), math.sin(i)
    P = (cW * cw - sW * sw * ci, sW * cw + cW * sw * ci, sw * si)
    Q = (-cW * sw - sW * cw * ci, -sW * sw + cW * cw * ci, cw * si)
    return P, Q


def position(o, t):
    """Two-body position in Earth radii, t in seconds from the common epoch."""
    M = (o["M0_epoch_rad"] + o["n_rad_s"] * t) % math.tau
    E = kepler_E(M, o["e"])
    a, e = o["a_er"], o["e"]
    x, y = a * (math.cos(E) - e), a * math.sqrt(1 - e * e) * math.sin(E)
    P, Q = o["_pq"] if "_pq" in o else pq(o)
    return tuple(x * P[k] + y * Q[k] for k in range(3))


def ellipse(o, n=128):
    a, e = o["a_er"], o["e"]
    P, Q = pq(o)
    pts = []
    for k in range(n):
        E = math.tau * k / n
        x, y = a * (math.cos(E) - e), a * math.sqrt(1 - e * e) * math.sin(E)
        pts.append(tuple(x * P[j] + y * Q[j] for j in range(3)))
    return pts


class TL:
    def __init__(self, heats, race, winner):
        d = oconfig.load("timeline.json")
        self.d = d
        self.fps = d["fps"]
        self.f0, self.f1 = d["frame_start"], d["frame_end"]
        self.seg = {s["key"]: s for s in d["segments"]}
        # ---- heats
        self.heats = []
        for sch, h in zip(d["heats"]["schedule"], heats["heats"]):
            assert sch["label"] == h["label"], (sch, h)
            self.heats.append(dict(h, start=sch["start"], ramp=sch["ramp"]))
        self.grey = d["heats"]["grey_frames"]
        self.fade = d["heats"]["fade_frames"]
        self.trails_from = d["heats"]["trails_from"]
        # ---- clock
        tlc = d["timelapse"]
        self.f_peri = tlc["winner_perigee_frame"]
        rate = {}
        dv = self.seg["dive"]
        for f in range(self.f0 - 1, self.f1 + 2):
            u = smoother((f - dv["start"]) / (dv["end"] - dv["start"]))
            rate[f] = math.exp(lerp(math.log(tlc["base"]), math.log(tlc["dive"]), u)) / self.fps
        # perigee time of the winner nearest after a full run-up
        run = sum(rate[f] for f in range(self.f0, self.f_peri))
        n, M0 = winner["n_rad_s"], winner["M0_epoch_rad"]
        k = math.ceil((run * n + M0) / math.tau)
        t_p = (math.tau * k - M0) / n
        self.t = {}
        acc = t_p
        for f in range(self.f_peri, self.f0 - 2, -1):
            self.t[f] = acc
            acc -= rate[f - 1] if f - 1 in rate else rate[f]
        acc = t_p
        for f in range(self.f_peri + 1, self.f1 + 2):
            acc += rate[f - 1]
            self.t[f] = acc
        self.rate = rate
        # ---- race
        r = d["race"]
        self.race_start = self.seg["dash"]["start"] + r["preroll_frames"]   # leader crosses the start line
        self.race_frames = r["race_frames"]
        self.winner_finish = self.race_start + self.race_frames
        self.slowmo = (self.race_frames / self.fps) / (race["winner_time_ms"] / 1000)

    # ------------------------------------------------------------- qualifying
    def threshold(self, f):
        thr = 0.0
        prev = 0.0
        for h in self.heats:
            if f < h["start"]:
                break
            u = ease_in_out((f - h["start"] + 1) / h["ramp"])
            thr = lerp(prev, h["threshold_km_s"], u)
            prev = h["threshold_km_s"]
        return thr

    def heat_at(self, f):
        cur = None
        for h in self.heats:
            if f >= h["start"]:
                cur = h
        return cur

    def elim_frame(self, v):
        """First frame the threshold reaches v. Survivors of the final never get one."""
        last = self.heats[-1]
        if v > last["threshold_km_s"]:
            return 1.0e6
        for f in range(self.heats[0]["start"], last["start"] + last["ramp"] + 1):
            if self.threshold(f) >= v:
                return float(f)
        return float(last["start"] + last["ramp"])

    # ------------------------------------------------------------- race
    def real_t(self, f):
        """Real elapsed race time in seconds; 0 when the leader crosses the start line."""
        return (f - self.race_start) / self.fps / self.slowmo


if __name__ == "__main__":
    h = oconfig.load("heats.json")
    race = oconfig.load("race.json")
    fin = oconfig.load("finalists.json")["finalists"]
    tl = TL(h, race, fin[0])
    print("slow motion", round(tl.slowmo, 1), "x; race start", tl.race_start, "finish", tl.winner_finish)
    for f in (49, 60, 71, 99, 120, 129, 163, 189, 221, 239):
        print(f, round(tl.threshold(f), 3))
    print("t_sim", tl.t[1], tl.t[tl.f_peri], tl.t[tl.f1])
    print("winner at perigee frame", [round(x, 3) for x in position(fin[0], tl.t[tl.f_peri])],
          "r", math.dist((0, 0, 0), position(fin[0], tl.t[tl.f_peri])))
