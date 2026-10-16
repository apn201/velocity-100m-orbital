"""fps, resolution, palette, quality profiles, seed, paths. Pure Python, no bpy."""
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "output"

FPS = 24
RES = (1920, 1080)

# Camera: fixed pinhole at (0, -CAM_DIST, 0) looking +Y. Horizontal FOV from a 50 mm lens on 36 mm.
CAM_DIST = 20.0
LENS = 50.0
SENSOR = 36.0
PX_PER_SLOPE = RES[0] / (SENSOR / LENS)   # px per unit of (x / depth)
HUD_DEPTH = 2.0
DUST_DEPTH = 150.0
BACKDROP_DEPTH = 200.0

PROFILES = {
    "preview": {"scale": 50, "samples": 8, "out": OUT / "preview"},
    "final": {"scale": 100, "samples": 32, "out": OUT / "frames"},
}

SEED = 1200


def hex_lin(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


PALETTE = {
    "bg": hex_lin("#050908"),
    "green": hex_lin("#5fe08f"),
    "green_dim": hex_lin("#3c8c5c"),
    "muted": hex_lin("#86a092"),
    "white": hex_lin("#f2ebdc"),
    "amber": hex_lin("#ffb03a"),
    "copper": (0.62, 0.30, 0.17),
    "globe": hex_lin("#1a2a22"),
}


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


class Rngs:
    """Every random stream is named and seeded from the global seed. Validation reads the log."""

    def __init__(self, seed):
        self.seed = seed
        self.log = []

    def get(self, name):
        s = (self.seed * 1_000_003 + sum(ord(c) * 131 ** i for i, c in enumerate(name))) % (2 ** 32)
        self.log.append((name, s))
        return random.Random(s)


def px_to_hud(px, py):
    """Pixel position -> HUD-root local coordinates (pixels, y up, origin at screen centre)."""
    return (px - RES[0] / 2, RES[1] / 2 - py)


def world_to_px(x, y, z):
    depth = y + CAM_DIST
    return (RES[0] / 2 + x / depth * PX_PER_SLOPE, RES[1] / 2 - z / depth * PX_PER_SLOPE)


def px_world_at(depth):
    """World units per pixel at a given depth from the camera."""
    return depth / PX_PER_SLOPE
