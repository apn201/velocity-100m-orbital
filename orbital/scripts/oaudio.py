"""Generated soundtrack. The film works without it.

A low hum whose pitch follows the qualifying threshold, a click on every heat,
a sweep into the dive, near silence for the slow-motion race (the pistol has not
reached us either), a tick per finishing lane, blips for the results board."""
import math
import struct
import wave

SR = 48000


def write(ctx, path):
    tl = ctx.tl
    n = int((tl.f1 - tl.f0 + 1) / tl.fps * SR)
    buf = [0.0] * n
    sec = lambda f: (f - tl.f0) / tl.fps

    def tone(t0, dur, freq, amp, decay=40.0):
        i0 = int(t0 * SR)
        for i in range(int(dur * SR)):
            if 0 <= i0 + i < n:
                tt = i / SR
                buf[i0 + i] += amp * math.sin(math.tau * freq * tt) * math.exp(-tt * decay)

    # hum: 110 Hz rising with the threshold, from the first frame to the flash
    dv = tl.seg["dive"]
    phase = 0.0
    end = int(sec(dv["end"]) * SR)
    for i in range(min(end, n)):
        t = i / SR
        f = tl.f0 + t * tl.fps
        thr = tl.threshold(int(f))
        hz = 110.0 * 2 ** (thr / 10.5)  # one octave over the qualifying; harmonics carry it on small speakers
        if f >= dv["start"]:
            hz *= 2 ** (1 * smooth((f - dv["start"]) / (dv["end"] - dv["start"])))
        phase += math.tau * hz / SR
        env = min(1.0, t / 1.2)
        s = math.sin(phase) + 0.3 * math.sin(2 * phase) + 0.1 * math.sin(3 * phase)
        buf[i] += 0.14 * env * s
    for h in tl.heats:
        tone(sec(h["start"]), 0.05, 1000.0, 0.18, 120)
        tone(sec(h["start"]), 0.6, 165.0, 0.25, 6)
    # race: one tick per finishing lane, a low note for the photo finish
    for ln in ctx.lanes:
        if ln.get("dns"):
            continue
        f = tl.race_start + ln["time_ms"] / 1000 * tl.slowmo * tl.fps
        if f < tl.seg["meanwhile"]["start"]:
            tone(sec(f), 0.04, 1200.0, 0.15, 140)
    tone(sec(tl.winner_finish), 1.2, 196.0, 0.3, 3)
    # results
    for i in range(7):
        tone(sec(tl.seg["results"]["start"] + 4 + i * 3), 0.05, 660.0 + 40 * i, 0.15, 90)
    tone(sec(tl.seg["final"]["start"] + 30), 2.0, 98.0, 0.35, 1.5)

    peak = max(1e-9, max(abs(x) for x in buf))
    g = 0.8 / peak if peak > 0.8 else 1.0
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, x * g)) * 32767)) for x in buf))
    return path


def smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)
