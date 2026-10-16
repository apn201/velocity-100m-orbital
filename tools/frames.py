"""Compute the bullet's speed in each reference frame and write data/frames.json.

Runs outside Blender (needs astropy). If astropy is missing, falls back to the
provisional constants from the spec and flags every value "approx": true.

    python tools/frames.py
"""
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "frames.json"

# --- Shot definition (spec 3.2) ---------------------------------------------
EPOCH = "2026-10-31T23:59:00"          # UTC, the contest deadline
LAT_DEG = 60.9                          # test range latitude
LON_DEG = 25.0                          # longitude is needed for the maths only; never displayed
HEIGHT_M = 0.0
MUZZLE_M_S = 304.8                      # Federal American Eagle AE9FP 147 gr FMJ FP: 1000 ft/s published
# Planck 2018 solar dipole (Planck Collaboration 2020, A&A 641, A1)
CMB_V_KM_S = 369.82
CMB_L_DEG = 264.021
CMB_B_DEG = 48.253

FALLBACK = {
    "ground": 0.305, "earth": 0.53, "sun": 29.8, "galaxy": 250.0, "cmb": 370.0,
}

FRAME_META = [
    ("ground", "GROUND", "ITRS: muzzle vector only, ground point at rest"),
    ("earth", "EARTH-CENTRED", "GCRS: muzzle + Earth rotation (astropy ITRS->GCRS with velocity)"),
    ("sun", "SUN-CENTRED", "HCRS: + Earth orbital motion (astropy GCRS->HCRS)"),
    ("galaxy", "GALACTOCENTRIC", "astropy Galactocentric, default parameter set"),
    ("cmb", "CMB REST FRAME", "HCRS velocity + Planck 2018 solar dipole vector"),
]


def display(v):
    """Three significant figures, no exponent."""
    if v <= 0:
        return "0"
    digits = 3 - 1 - int(math.floor(math.log10(v)))
    digits = max(digits, 0)
    return f"{v:.{digits}f}"


def compute_astropy():
    import astropy
    import astropy.units as u
    import numpy as np
    from astropy.coordinates import (
        ITRS, GCRS, HCRS, ICRS, Galactic, Galactocentric, EarthLocation,
        CartesianRepresentation, CartesianDifferential, get_sun, galactocentric_frame_defaults,
    )
    from astropy.time import Time

    t = Time(EPOCH, scale="utc")
    loc = EarthLocation.from_geodetic(LON_DEG * u.deg, LAT_DEG * u.deg, HEIGHT_M * u.m)
    lat, lon = math.radians(LAT_DEG), math.radians(LON_DEG)
    east = np.array([-math.sin(lon), math.cos(lon), 0.0])
    north = np.array([-math.sin(lat) * math.cos(lon), -math.sin(lat) * math.sin(lon), math.cos(lat)])
    up = np.array([math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)])

    v_itrs = east * MUZZLE_M_S / 1000.0  # km/s
    pos = loc.get_itrs(obstime=t).cartesian
    rep = CartesianRepresentation(pos.xyz, differentials=CartesianDifferential(v_itrs * u.km / u.s))
    c_itrs = ITRS(rep, obstime=t)

    def speed(c):
        d = c.cartesian.differentials["s"]
        return float(np.linalg.norm(d.d_xyz.to_value(u.km / u.s))), d.d_xyz.to_value(u.km / u.s)

    s_ground, _ = speed(c_itrs)
    c_gcrs = c_itrs.transform_to(GCRS(obstime=t))
    s_earth, _ = speed(c_gcrs)
    c_hcrs = c_gcrs.transform_to(HCRS(obstime=t))
    s_sun, v_hcrs = speed(c_hcrs)
    with galactocentric_frame_defaults.set("latest"):
        gc_frame = Galactocentric()
        c_gal = c_hcrs.transform_to(gc_frame)
        gc_params = {
            "galcen_distance_kpc": float(gc_frame.galcen_distance.to_value(u.kpc)),
            "galcen_v_sun_km_s": [float(x) for x in gc_frame.galcen_v_sun.xyz.to_value(u.km / u.s)],
            "z_sun_pc": float(gc_frame.z_sun.to_value(u.pc)),
            "roll_deg": float(gc_frame.roll.to_value(u.deg)),
            "defaults": "latest",
        }
    s_gal, _ = speed(c_gal)

    # CMB dipole direction, galactic (l, b) -> ICRS cartesian unit vector (same axes as HCRS)
    d = Galactic(l=CMB_L_DEG * u.deg, b=CMB_B_DEG * u.deg).transform_to(ICRS())
    dhat = d.cartesian.xyz.value
    dhat = dhat / np.linalg.norm(dhat)
    v_cmb = v_hcrs + CMB_V_KM_S * dhat
    s_cmb = float(np.linalg.norm(v_cmb))

    # Sun direction in the site's local ENU frame (drives the globe's terminator)
    sun_itrs = get_sun(t).transform_to(ITRS(obstime=t)).cartesian.xyz.to_value(u.km)
    s_hat = sun_itrs / np.linalg.norm(sun_itrs)  # 1 AU away: geocentric direction is enough
    sun_enu = [float(np.dot(s_hat, east)), float(np.dot(s_hat, north)), float(np.dot(s_hat, up))]

    values = {"ground": s_ground, "earth": s_earth, "sun": s_sun, "galaxy": s_gal, "cmb": s_cmb}
    meta = {
        "astropy_version": astropy.__version__,
        "galactocentric": gc_params,
        "sun_direction_enu": sun_enu,
        "cmb_dipole": {"v_km_s": CMB_V_KM_S, "l_deg": CMB_L_DEG, "b_deg": CMB_B_DEG, "source": "Planck 2018"},
    }
    return values, meta, False


def main():
    try:
        values, meta, approx = compute_astropy()
    except ImportError as e:
        print(f"astropy unavailable ({e}); writing fallback constants, approx=true")
        values, meta, approx = dict(FALLBACK), {"astropy_version": None,
                                                "sun_direction_enu": [0.0, -0.5, -0.86]}, True

    frames = []
    for key, name, method in FRAME_META:
        v = values[key]
        frames.append({
            "key": key, "name": name, "method": method,
            "speed_km_s": v, "display": display(v), "units": "km/s",
            "approx": approx, "source": f"frames.py:{key}",
        })
    ratio = values["cmb"] / values["ground"]
    ratio_round = float(f"{ratio:.2g}")
    doc = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "epoch_utc": EPOCH + "Z",
        "site": {"lat_deg": LAT_DEG, "lon_deg": LON_DEG, "height_m": HEIGHT_M,
                 "direction": "due east, horizontal"},
        "muzzle_m_s": MUZZLE_M_S,
        "frames": frames,
        "span": {"ratio": ratio, "display": f"x{int(ratio_round):,}"},
        "comparisons": [
            {"key": "saturn_v", "name": "SATURN V", "speed_km_s": 10.84, "display": "~10.8",
             "units": "km/s", "frame": "earth", "detail": "TLI", "approx": True,
             "source": "sources.md#saturn-v"},
            {"key": "pioneer_10", "name": "PIONEER 10", "speed_km_s": 11.9, "display": "~12",
             "units": "km/s", "frame": "sun", "detail": "", "approx": True,
             "source": "sources.md#pioneer-10"},
        ],
        **meta,
        "python": sys.version.split()[0],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    for f in frames:
        print(f"{f['name']:16s} {f['speed_km_s']:12.6f} km/s  -> {f['display']}")
    print(f"span {doc['span']['display']}  ({ratio:.1f})")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
