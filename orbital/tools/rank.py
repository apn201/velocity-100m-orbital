"""Rank every tracked debris piece and rocket body by perigee speed. Writes
field.json, heats.json, finalists.json and race.json. Plain two-body maths.

    python orbital/tools/rank.py [--epoch 2026-10-31T00:00:00Z]
"""
import argparse
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DATA = ROOT / "data"

MU = 398600.4418        # km^3/s^2
R_E = 6378.137          # km
SOUND = 343.0           # m/s, dry air at 20 C
WR_S = 9.58             # 100 m world record, s
REACTION_S = 0.15       # typical elite sprint reaction time, s
LANE_W = 1.22           # m, World Athletics lane width
TRACK_M = 100.0
ISS_ID = 25544
HEATS = [  # (label, threshold km/s or "ISS", note); the final is the top 5
    ("HEAT 1", 7.0, "HIGH ORBITS ARE SLOW"),
    ("HEAT 2", "ISS", "FASTER THAN THE ISS"),
    ("HEAT 3", 10.0, "LOW ORBIT IS OUT"),
]


def parse_epoch(s):
    s = s.rstrip("Z")
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def elements(row):
    n = row["MEAN_MOTION"] * math.tau / 86400.0          # rad/s
    a = (MU / n ** 2) ** (1 / 3)
    e = row["ECCENTRICITY"]
    rp, ra = a * (1 - e), a * (1 + e)
    vp = math.sqrt(MU * (2 / rp - 1 / a))
    va = math.sqrt(MU * (2 / ra - 1 / a))
    m = re.match(r"(\d{4})-", row.get("OBJECT_ID") or "")
    return {
        "id": row["NORAD_CAT_ID"],
        "name": row["OBJECT_NAME"].strip(),
        "cospar": row.get("OBJECT_ID"),
        "launch_year": int(m.group(1)) if m else None,
        "epoch": row["EPOCH"],
        "a_er": a / R_E,
        "e": e,
        "i_deg": row["INCLINATION"],
        "raan_deg": row["RA_OF_ASC_NODE"],
        "argp_deg": row["ARG_OF_PERICENTER"],
        "M0_deg": row["MEAN_ANOMALY"],
        "n_rad_s": n,
        "vp_km_s": vp,
        "va_km_s": va,
        "perigee_km": rp - R_E,
        "apogee_km": ra - R_E,
    }


def propagate_M0(el, epoch):
    """Mean anomaly moved from the element epoch to the common epoch (two-body)."""
    dt = (epoch - parse_epoch(el["epoch"])).total_seconds()
    return (math.radians(el["M0_deg"]) + el["n_rad_s"] * dt) % math.tau


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epoch", default="2026-10-31T00:00:00Z")
    a = ap.parse_args()
    rows = []
    for key, typ in (("deb", "DEBRIS"), ("rb", "ROCKET BODY")):
        for r in json.loads((RAW / f"{key}.json").read_text(encoding="utf-8")):
            r["_type"] = typ
            rows.append(r)
    stations = json.loads((RAW / "stations.json").read_text(encoding="utf-8"))
    iss_row = next(r for r in stations if r["NORAD_CAT_ID"] == ISS_ID)
    print(f"[rank] raw rows: {len(rows)}  (deb + r/b)")

    newest = max(parse_epoch(r["EPOCH"]) for r in rows)
    epoch = parse_epoch(a.epoch)
    if epoch > newest:
        epoch = newest.replace(hour=0, minute=0, second=0, microsecond=0)
        print(f"[rank] requested epoch is past the data; using {epoch:%Y-%m-%d}")
    log = []

    def step(label, items):
        log.append({"filter": label, "count": len(items)})
        print(f"[rank] {label:<34} {len(items):>6}")
        return items

    seen, uniq = set(), []
    for r in rows:
        if r["NORAD_CAT_ID"] in seen:
            continue
        seen.add(r["NORAD_CAT_ID"])
        uniq.append(r)
    f = step("unique catalogue numbers", uniq)
    f = step("epoch within 30 days", [r for r in f if abs(parse_epoch(r["EPOCH"]) - epoch) <= timedelta(days=30)])
    f = step("0 <= e < 1", [r for r in f if 0 <= r["ECCENTRICITY"] < 1])
    els = []
    for r in f:
        el = elements(r)
        el["type"] = r["_type"]
        els.append(el)
    els = step("perigee altitude > 120 km", [e for e in els if e["perigee_km"] > 120])

    els.sort(key=lambda e: -e["vp_km_s"])
    for i, e in enumerate(els):
        e["rank"] = i + 1
        e["M0_epoch_rad"] = propagate_M0(e, epoch)

    iss = elements(iss_row)
    iss["type"] = "STATION"
    iss["name"] = "ISS"
    iss["M0_epoch_rad"] = propagate_M0(iss, epoch)
    heats = []
    for label, thr, note in HEATS:
        thr = round(iss["vp_km_s"], 2) if thr == "ISS" else thr
        n = sum(1 for e in els if e["vp_km_s"] > thr)
        leo_n = sum(1 for e in els if e["vp_km_s"] > thr and e["apogee_km"] < 2000)
        heats.append({"label": label, "threshold_km_s": thr, "remain": n, "leo_remain": leo_n, "note": note})
    heats.append({"label": "FINAL", "threshold_km_s": els[5]["vp_km_s"], "remain": 5, "note": "THE FIVE FASTEST GO THROUGH"})
    leo = sum(1 for e in els if e["apogee_km"] < 2000)
    print(f"[rank] LEO objects (apogee < 2000 km): {leo}")
    for h in heats:
        print(f"[rank] {h['label']:<7} v > {h['threshold_km_s']:.3f} km/s  {h['remain']:>6} remain"
              f"  ({h.get('leo_remain', 0)} LEO)  {h['note']}")

    fin = els[:5]
    print("\n[rank] FINALISTS")
    for e in fin + [iss]:
        print(f"  {e['rank'] if 'rank' in e else '-':>2} {e['name']:<26} {e['type']:<12} {e['launch_year']}  "
              f"v_p {e['vp_km_s']:.3f} km/s  perigee {e['perigee_km']:.0f} km  apogee {e['apogee_km']:.0f} km")

    lanes = [dict(e, lane=i + 1) for i, e in enumerate(fin)] + [dict(iss, lane=6)]
    t_win = TRACK_M / (fin[0]["vp_km_s"] * 1000)            # s
    race = {"track_m": TRACK_M, "winner_time_ms": t_win * 1000, "sound_m_s": SOUND,
            "sound_m_at_finish": SOUND * t_win, "lane_width_m": LANE_W, "lanes": []}
    for L in lanes:
        v = L["vp_km_s"] * 1000
        t = TRACK_M / v
        d = min(v * t_win, TRACK_M)
        race["lanes"].append({"lane": L["lane"], "id": L["id"], "cospar": L["cospar"], "name": L["name"], "type": L["type"],
                              "launch_year": L["launch_year"], "v_km_s": L["vp_km_s"], "time_ms": t * 1000,
                              "dist_at_winner_m": d, "gap_m": TRACK_M - d})
    race["lanes"].append({"lane": 7, "id": None, "name": "WORLD RECORD PACE", "type": "HUMAN", "launch_year": None,
                          "v_km_s": TRACK_M / WR_S / 1000, "time_ms": WR_S * 1000, "dist_at_winner_m": 0.0,
                          "gap_m": TRACK_M, "dns": True, "reaction_s": REACTION_S})
    # the pistol stands at the start line on the inside of lane 1; distance to the centre of each lane
    race["sound_reaches_lane"] = max([0] + [k for k in range(1, 8) if (k - 0.5) * LANE_W <= SOUND * t_win])
    race["lane7_dist_m"] = 6.5 * LANE_W
    race["slow_motion_factor"] = None  # set by the build from timeline.json
    print("\n[rank] RACE  (winner %.2f ms, pistol sound %.2f m, reaches lane %d)"
          % (t_win * 1000, SOUND * t_win, race["sound_reaches_lane"]))
    for L in race["lanes"]:
        print(f"  lane {L['lane']} {L['name']:<26} {L['time_ms']:>9.2f} ms  at winner's finish {L['dist_at_winner_m']:6.1f} m"
              f"  gap {L['gap_m']:5.1f} m")

    keep = ["id", "cospar", "name", "type", "launch_year", "a_er", "e", "i_deg", "raan_deg", "argp_deg", "M0_epoch_rad",
            "n_rad_s", "vp_km_s", "perigee_km", "apogee_km", "rank"]
    epoch_s = epoch.strftime("%Y-%m-%dT%H:%M:%SZ")
    stamp = {k: (RAW / f"{k}.stamp").read_text(encoding="utf-8").strip() for k in ("deb", "rb", "stations")}
    (DATA / "field.json").write_text(json.dumps({
        "epoch": epoch_s, "fetched": stamp, "filters": log, "count": len(els),
        "cols": keep, "rows": [[e[k] for k in keep] for e in els],
    }, separators=(",", ":")), encoding="utf-8")
    (DATA / "heats.json").write_text(json.dumps({"epoch": epoch_s, "leo_count": leo, "heats": heats}, indent=1),
                                     encoding="utf-8")
    (DATA / "finalists.json").write_text(json.dumps({"epoch": epoch_s, "finalists": [{k: e[k] for k in keep} for e in fin],
                                                     "iss": {k: iss.get(k) for k in keep}}, indent=1), encoding="utf-8")
    (DATA / "race.json").write_text(json.dumps(race, indent=1), encoding="utf-8")
    print(f"\n[rank] wrote field.json ({len(els)} objects), heats.json, finalists.json, race.json  epoch {epoch_s}")


if __name__ == "__main__":
    main()
