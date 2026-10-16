"""v3 paths and data. Palette, camera optics, seeding and pixel maths come from the v2 config."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
V2 = ROOT.parent / "scripts"
if str(V2) not in sys.path:
    sys.path.insert(1, str(V2))

import config as v2  # noqa: E402

DATA = ROOT / "data"
OUT = ROOT / "output"
PALETTE = dict(v2.PALETTE, grey=v2.hex_lin("#4a5550"), bg=v2.hex_lin("#030605"))
RES = v2.RES
PX_PER_SLOPE = v2.PX_PER_SLOPE
SEED = 100

# render.py reads config.PROFILES at call time; point it at the v3 output folders
v2.PROFILES = {
    "preview": {"scale": 50, "samples": 8, "out": OUT / "preview"},
    "final": {"scale": 100, "samples": 32, "out": OUT / "frames"},
}
PROFILES = v2.PROFILES


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def px_world_at(depth):
    return depth / PX_PER_SLOPE
