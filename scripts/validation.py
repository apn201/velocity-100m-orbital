"""Build checks (spec section 9). Returns a list of failures; empty means pass."""
import re

import config
from timeline import LAYERS


def run(ctx, hud):
    fails, notes = [], []
    tl = ctx.tl
    fj_path = config.DATA / "frames.json"
    tool = config.ROOT / "tools" / "frames.py"
    if not fj_path.exists():
        fails.append("frames.json missing")
    elif fj_path.stat().st_mtime < tool.stat().st_mtime:
        fails.append("frames.json is older than tools/frames.py; rerun python tools/frames.py")

    # sources
    src = (config.DATA / "sources.md").read_text(encoding="utf-8")
    heads = set(re.findall(r"^## (\S+)", src, re.M))

    def has_source(key):
        k = key.split("#")[-1] if key.startswith("sources.md") else key
        return k in heads

    numbers = 0
    for t in hud.texts:
        m = t["meta"]
        if re.search(r"\d", t["body"]) and m.get("kind") in (None, "text"):
            if not re.fullmatch(r"(FRAME \d/\d|.*\d+(\.\d+)? N|.*15 deg.*|.*001)", t["body"]):
                fails.append(f"text '{t['body']}' contains a number but is not registered as a quantity")
        if m.get("kind") == "speed":
            numbers += 1
            for need in ("frame", "units", "source"):
                if not m.get(need):
                    fails.append(f"'{t['body']}' lacks {need}")
            if m.get("source") and not has_source(m["source"]):
                fails.append(f"'{t['body']}' source '{m['source']}' has no entry in sources.md")
        if m.get("kind") == "axis" and not m.get("units"):
            fails.append(f"axis label '{t['body']}' lacks units")
    for n in ctx.numbers:
        if not (n.get("frame") and n.get("units") and has_source(n["source"])):
            fails.append(f"number {n['name']} lacks frame/units/source")
    notes.append(f"{numbers} speed readings checked against sources.md")

    # segments
    segs = sorted(tl.d["segments"], key=lambda s: s["start"])
    for a, b in zip(segs, segs[1:]):
        if b["start"] <= a["end"]:
            fails.append(f"segments {a['key']} and {b['key']} overlap")
        if b["start"] != a["end"] + 1:
            notes.append(f"gap between {a['key']} and {b['key']}")
    total = (tl.f1 - tl.f0 + 1) / tl.fps
    if total > 30:
        fails.append(f"film is {total:.1f} s, over 30 s")
    notes.append(f"length {total:.2f} s, {tl.f1 - tl.f0 + 1} frames")

    # text size and safe area
    x0, y0, x1, y1 = hud.lay["title_safe"]
    for t in hud.texts:
        if t["essential"] and t["size"] < 28:
            fails.append(f"essential text '{t['body']}' is {t['size']} px, below 28")
        bx0, by0, bx1, by1 = t["bbox"]
        if bx0 < x0 or bx1 > x1 or by0 < y0 or by1 > y1:
            fails.append(f"text '{t['body']}' leaves title-safe area {tuple(round(v) for v in t['bbox'])}")

    # label readability: every essential label visible for >= 1.2 s in one run
    need = int(1.2 * tl.fps)
    for t in hud.texts:
        tr = ctx.tracks.items.get(t["obj"].name)
        if not t["essential"] or tr is None or t["obj"].name.startswith(("readout_", "hud_title")):
            continue
        run_, best = 0, 0
        for f in range(1, tl.f1 + 1):
            run_ = run_ + 1 if tr.vis[f] else 0
            best = max(best, run_)
        if best < need:
            fails.append(f"'{t['body']}' readable for only {best} frames (< {need})")

    # layer isolation: nothing from another layer visible in a layer's range except the handoffs
    h = tl.cross // 2
    hand = set()
    for L in LAYERS[1:]:
        hand |= set(range(tl.handoff[L] - h, tl.handoff[L] + h + 1))
    def frames_of(L):
        out = set()
        for a, b in tl.layer_range(L):
            out |= set(range(a, b + 1))
        return out
    for i, A in enumerate(LAYERS):
        for B in LAYERS[i + 1:]:
            both = (frames_of(A) & frames_of(B)) - hand
            if both:
                fails.append(f"layers {A} and {B} overlap outside a handoff at {sorted(both)[:5]}")
    for name, tr in ctx.tracks.items.items():
        if tr.layer not in LAYERS or tr.ob.type == "EMPTY":
            continue
        own = frames_of(tr.layer)
        leak = [f for f in range(1, tl.f1 + 1) if tr.vis[f] and f not in own]
        if leak:
            fails.append(f"{name} ({tr.layer}) visible outside its layer at frames {leak[:5]}")
    # seeds
    if not ctx.rngs.log:
        notes.append("no random streams used")
    for name, seed in ctx.rngs.log:
        if seed is None:
            fails.append(f"random stream {name} has no seed")
    notes.append("random streams: " + ", ".join(f"{n}={s}" for n, s in ctx.rngs.log))
    return fails, notes
