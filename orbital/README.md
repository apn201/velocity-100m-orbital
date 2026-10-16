# VELOCITY // 100 M ORBITAL

Every tracked piece of debris and spent rocket stage, on its real orbit. Qualifying heats knock out the slow ones until five remain. Then they race 100 m at perigee speed, with the ISS in lane 6 and world-record pace in lane 7.

28 s, 1920x1080, 24 fps. Blender 5.2 + Python. Spec: `../VELOCITY_100M_Orbital_Spec.md`. The v2 film (`../scripts`) is untouched and still rebuilds; v3 imports its modules.

## Rebuild

Run from the `Vauhti` folder:

```bash
python orbital/tools/fetch.py
python orbital/tools/rank.py
blender -b --python orbital/scripts/build.py -- --validate
blender -b --python orbital/scripts/build.py -- --preview
blender -b --python orbital/scripts/build.py -- --final
blender -b --python scripts/encode.py -- --src orbital/output/frames --out orbital/output/final/velocity_100m.mp4 --audio orbital/output/audio/velocity_100m.wav
```

`fetch.py` downloads three CelesTrak queries into `data/raw/` (never published), at most once per 2 hours. `--stills 30,240,494` renders single frames.

## What the data said (epoch 2026-10-19)

- 12,379 objects after filtering: 10,238 debris + 2,169 rocket bodies, minus 15 duplicates and 13 stale element sets.
- Heat 1, v > 7.00 km/s: geostationary and navigation orbits go. 11,635 remain.
- Heat 2, v > 7.66 km/s (the ISS's own speed): most of low orbit goes. 2,069 remain.
- Heat 3, v > 10.00 km/s: the rest of low orbit goes. 270 remain, all upper stages on transfer ellipses.
- Final: four Falcon 9 second stages and a Delta 4 stage. Winner: FALCON 9 R/B, launched 2021, perigee 170 km, 10.42 km/s, 100 m in 9.60 ms.
- The ISS (7.66 km/s) is 26.4 m behind. The pistol's sound has gone 3.3 m. Lane 7 is 7.9 m away.

## Reused from v2

`geometry.py` (globe, Lines2D, lathe, curves, discs), `materials.py`, `anim.py` (every value baked from a function of the frame), `hud.py` (camera-parented pixel HUD, font, text bookkeeping), `layers.text_obj`, `render.py`, `encode.py`, the palette and camera optics from `config.py`, and the easing curves from `timeline.py`.

## New in v3

- `tools/fetch.py`, `tools/rank.py`: data, heats, finalists, race table.
- `scripts/orbits_gn.py`: one vertex per object; a script-built Geometry Nodes tree solves Kepler's equation every frame (10 unrolled Newton steps) and handles elimination colour and fade. Trails use the same tree.
- `scripts/otimeline.py`: threshold curve, per-object elimination frame, time-lapse clock (set so the winner hits perigee on the last frame of the dive), slow-motion factor.
- `scripts/obuilders.py`: track, rocket-stage and ISS tokens, crouched sprinter, sound ring.
- `scripts/ohud.py`, `ovalidation.py`, `oaudio.py`.

## Deviations from the spec

- Heat thresholds are 7.0 / ISS speed / 10.0 rather than 7.6 / 7.9 / 10.0. In the real data, 7.9 left 1,403 objects including 47 in low orbit; setting heat 2 at the ISS's speed makes the reference meaningful.
- The straighten morph is a dive to perigee plus a white flash cut (the spec's fallback). The race ends on a photo-finish freeze at the winner's time.
- The joke on the meanwhile shot is "lane 7 has not heard the gun yet": at 3.3 m the sound reaches lane 3, not lane 2 as the spec guessed.
- Tokens are not to scale (labelled).
