"""Download the CelesTrak GP queries into data/raw/ (never published).

    python orbital/tools/fetch.py [--force]

One download per query per 2 hours. Stops on any HTTP error; never retries.
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
BASE = "https://celestrak.org/NORAD/elements/gp.php"
QUERIES = {
    "deb": "NAME=DEB&FORMAT=json",
    "rb": "NAME=R/B&FORMAT=json",
    "stations": "GROUP=stations&FORMAT=json",
}
MIN_AGE_S = 2 * 3600
UA = "VELOCITY-100M-ORBITAL/1.0 (RenderJuice contest entry; one fetch per 2 h)"


def main():
    force = "--force" in sys.argv
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / ".gitignore").write_text("*\n", encoding="utf-8")
    for key, q in QUERIES.items():
        out = RAW / f"{key}.json"
        if out.exists() and time.time() - out.stat().st_mtime < MIN_AGE_S and not force:
            print(f"[fetch] {key}: cache is {(time.time() - out.stat().st_mtime) / 60:.0f} min old, skipping")
            continue
        url = f"{BASE}?{q}"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                if r.status != 200:
                    sys.exit(f"[fetch] {key}: HTTP {r.status}, stopping")
                body = r.read()
        except urllib.error.HTTPError as e:
            sys.exit(f"[fetch] {key}: HTTP {e.code}, stopping (no retry)")
        try:
            rows = json.loads(body)
        except json.JSONDecodeError:
            sys.exit(f"[fetch] {key}: not JSON ({body[:120]!r}), stopping")
        out.write_bytes(body)
        (RAW / f"{key}.stamp").write_text(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), encoding="utf-8")
        print(f"[fetch] {key}: {len(rows)} rows -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
