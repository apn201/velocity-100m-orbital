"""Generated soundtrack (spec 11): a boot tick, one low tone that rises a step at
each frame change, silence from the hard cut. Pure Python, written as 16-bit WAV."""
import math
import struct
import wave

SR = 48000


def write(ctx, path):
    tl = ctx.tl
    n = int((tl.f1 - tl.f0 + 1) / tl.fps * SR)
    buf = [0.0] * n
    sec = lambda f: (f - tl.f0) / tl.fps

    # boot ticks: a click on the first frame and on every title flicker onset
    def tick(t0, amp, freq=2400.0):
        i0 = int(t0 * SR)
        for i in range(int(0.03 * SR)):
            if i0 + i < n:
                tt = i / SR
                buf[i0 + i] += amp * math.sin(math.tau * freq * tt) * math.exp(-tt * 180)
    tick(0.02, 0.35)
    title = ctx.tracks.items.get("hud_title")
    if title:
        for f in range(2, tl.f1):
            if title.vis[f] and not title.vis[f - 1]:
                tick(sec(f), 0.12, 3200.0)

    # tone: semitone steps up per reference frame, glide over the roll
    keys = [fr["key"] for fr in ctx.frames]
    steps = {k: 41.2 * 2 ** (i * 3 / 12) for i, k in enumerate(keys)}  # E1 and minor-third steps
    steps[keys[-1]] *= 2 ** (2 / 12)  # rises more at the CMB
    ev = [(sec(tl.event[k]), steps[k]) for k in keys]
    cut = sec(tl.seg["local"]["start"])
    start = sec(tl.seg["ground"]["start"])
    glide = 12 / tl.fps
    phase = 0.0
    for i in range(int(start * SR), min(int(cut * SR), n)):
        t = i / SR
        f = ev[0][1]
        for (t0, f0), (t1, f1) in zip(ev, ev[1:]):
            if t >= t1:
                f = f1
            if t1 <= t < t1 + glide:
                u = (t - t1) / glide
                u = u * u * (3 - 2 * u)
                f = f0 * (f1 / f0) ** u
        phase += math.tau * f / SR
        env = min(1.0, (t - start) / 1.5)
        lvl = 0.16 + 0.10 * min(1.0, max(0.0, (t - ev[-1][0]) / 1.0))
        s = math.sin(phase) + 0.35 * math.sin(2 * phase) + 0.12 * math.sin(3 * phase + 0.4)
        buf[i] = buf[i] + lvl * env * s
    # frame-change blips
    for t0, f0 in ev:
        tick(t0, 0.18, 1800.0)

    peak = max(1e-9, max(abs(x) for x in buf))
    g = 0.8 / peak if peak > 0.8 else 1.0
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, x * g)) * 32767)) for x in buf))
    return path
