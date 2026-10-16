"""v3 build checks (spec section 7). Returns (failures, notes)."""
import re
import time

import oconfig

MAX_S = 30.0
MIN_PX = 28


def run(ctx, hud):
    fails, notes = [], []
    tl = ctx.tl
    raw = oconfig.DATA / "raw"
    field = oconfig.DATA / "field.json"
    stamps = list(raw.glob("*.json"))
    if not stamps:
        fails.append("no raw data in data/raw; run tools/fetch.py")
    else:
        newest = max(p.stat().st_mtime for p in stamps)
        if field.stat().st_mtime < newest:
            fails.append("field.json is older than the raw data; rerun tools/rank.py")
        age_d = (time.time() - newest) / 86400
        notes.append(f"raw data age {age_d:.1f} days")
        if age_d > 7:
            notes.append("WARNING raw data older than 7 days (fails a final render)")
            if "--final" in " ".join(__import__("sys").argv):
                fails.append("raw data older than 7 days at final render")
    for o in ctx.finalists:
        if o["perigee_km"] < 120 or not 0 <= o["e"] < 1:
            fails.append(f"finalist {o['name']} has perigee {o['perigee_km']:.0f} km, e {o['e']:.3f}")
    dur = (tl.f1 - tl.f0 + 1) / tl.fps
    notes.append(f"duration {dur:.1f} s, {tl.f1 - tl.f0 + 1} frames")
    if dur > MAX_S:
        fails.append(f"film runs {dur:.1f} s > {MAX_S} s")
    prev = None
    for s in tl.d["segments"]:
        if prev and s["start"] != prev["end"] + 1:
            fails.append(f"segment {s['key']} does not follow {prev['key']}")
        prev = s
    # numbers and sources
    src = (oconfig.DATA / "sources.md").read_text(encoding="utf-8")
    heads = set(re.findall(r"^## (\S+)", src, re.M))
    n_q = 0
    for t in hud.texts:
        m, body = t["meta"], t["body"]
        if m.get("kind") == "q":
            n_q += 1
            key = m.get("source", "")
            key = key.split("#")[-1] if key.startswith("sources.md") else key
            if key not in heads:
                fails.append(f"'{body}' source '{key}' has no entry in sources.md")
        elif re.search(r"\d", body) and not re.fullmatch(r"(\d|.*100 [Mm].*|HEAT \d|RESULTS  100 m)", body):
            fails.append(f"text '{body}' contains a number but is not registered with a source")
        if t["essential"] and t["size"] < MIN_PX:
            fails.append(f"essential text '{body}' is {t['size']} px < {MIN_PX}")
        x0, y0, x1, y1 = t["bbox"]
        sx0, sy0, sx1, sy1 = hud.lay["title_safe"]
        if t["essential"] and (x0 < sx0 - 1 or x1 > sx1 + 1 or y0 < sy0 - 1 or y1 > sy1 + 1):
            fails.append(f"essential text '{body}' leaves the title-safe area {t['bbox']}")
    for n in ctx.numbers:
        key = n["source"].split("#")[-1] if n["source"].startswith("sources.md") else n["source"]
        if key not in heads:
            fails.append(f"number {n} has no entry in sources.md")
    spans = sorted(getattr(hud, "cap_spans", []), key=lambda s: s[1])
    for (k1, a1, b1), (k2, a2, b2) in zip(spans, spans[1:]):
        if a2 <= b1:
            fails.append(f"caption '{k2}' (frames {a2}-{b2}) overlaps caption '{k1}' ({a1}-{b1})")
    notes.append(f"{n_q} quantity texts checked against sources.md")
    notes.append(f"slow motion {tl.slowmo:.1f}x, winner {ctx.race['winner_time_ms']:.2f} ms, "
                 f"sound {ctx.race['sound_m_at_finish']:.2f} m")
    return fails, notes
