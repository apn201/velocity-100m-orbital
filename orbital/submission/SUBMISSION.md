# VELOCITY // 100 M ORBITAL - submission texts

Video: https://youtu.be/bkjEwBM9kNo
Source: https://github.com/apn201/velocity-100m-orbital

Files in this folder:

- `01_thumbnail_finalists.jpg` - Devpost thumbnail (first gallery image), 1920x1280 (3:2)
- `02` to `07` - more gallery images, 3:2
- `wip_blender.png` - Blender work-in-progress image: Geometry Nodes workspace, viewport at frame 110 mid-heat, the generated orbit tree, the attribute spreadsheet

---

## 1. Discord, #challenges, Official Entry

Use the Official Entry tag. Attach `wip_blender.png`.

```
Title:    VELOCITY // 100 M ORBITAL
Runtime:  28.0 seconds, 672 frames at 24 fps
Format:   1920x1080, H.264, AAC stereo 48 kHz
Engine:   Blender 5.2.2 LTS, EEVEE, 32 samples
Scene:    built by one Python script from an empty scene, no modelling, no sculpting, no hand keyframes
Data:     real orbital elements of 12,379 tracked objects, CelesTrak public catalogue (US Space Force)
Video:    https://youtu.be/bkjEwBM9kNo
Source:   https://github.com/apn201/velocity-100m-orbital

Every tracked piece of space debris and every spent rocket stage, on its real orbit.
Qualifying heats knock out the slow ones until five remain. Nothing from low orbit
makes the final. The five fastest are old upper stages on long transfer ellipses,
diving through perigee at 10.4 km/s. Then they race 100 m, with the ISS in lane 6
and world record pace in lane 7. The winner takes 9.60 ms. The ISS is 26 m behind.
The sound of the starter's pistol has travelled 3.3 m, so lane 7 has not heard the
gun yet.

Speed is the selection rule, the race and the joke. Orbits are solved in Geometry
Nodes from real Keplerian elements. Code written by AI (Claude Code), spec with
AI assistance. No AI images or audio, no third party assets.
```

---

## 2. Devpost

### Project name

VELOCITY // 100 M ORBITAL

### Elevator pitch (tagline)

The fastest things near Earth are old rocket stages nobody is steering. 12,379 real orbits, qualifying heats, and a 100 m final that lasts 9.60 ms.

### About the project

```markdown
## What it is

A 28 second film about speed. Every tracked piece of space debris and every spent rocket stage is put on its real orbit around Earth. Then qualifying heats raise the speed limit and knock out the slow ones, until five remain. The five race 100 m against the ISS and world record pace.

Everything is made in Blender 5.2 by Python. One script builds the whole film from an empty scene. There is no modelling, no sculpting and no hand keyframing. The globe, the 12,379 objects, the track, the rocket stages, the ISS, the sprinter, the text and the sound are all generated. The orbits come from real data, the public satellite catalogue (US Space Force, published by CelesTrak).

## Why

My previous attempt for this contest was a bullet seen from five reference frames. It was good looking, but boring and confusing. So I made a more fun one, and reused as much as I could from it (globe, HUD, materials, render pipeline).

## How I interpreted Speed

In a circular orbit speed depends only on altitude. Everything in low orbit, the ISS included, goes 7.3 to 7.9 km/s. So if you race low orbit junk, it is a tie and nobody cares.

The fast ones come from elsewhere. Upper stages left on geostationary transfer orbits fly long ellipses, from a few hundred km up to 40,000 km and more. At the bottom of the ellipse (perigee) they go about 10.4 km/s. In the film this shows up in the qualifying: when the limit goes over the ISS speed, the whole cloud around Earth disappears, and what is left is a few hundred thin ellipses that were hidden in the noise.

Speed for each object is the perigee speed, two-body:

$$ v_p = \sqrt{\mu \left( \frac{2}{r_p} - \frac{1}{a} \right)}, \quad \mu = 398600.4418 \ \text{km}^3/\text{s}^2 $$

The heats, from the data:

- Heat 1, v > 7.00 km/s: geostationary and navigation orbits are out. 11,635 remain.
- Heat 2, v > 7.66 km/s, which is the ISS speed: most of low orbit is out. 2,069 remain.
- Heat 3, v > 10.00 km/s: the rest of low orbit is out. 270 remain, all upper stages on transfer ellipses.
- Final: the five fastest. Four Falcon 9 second stages and one Delta 4 stage.

The winner is a Falcon 9 second stage launched in January 2021 (2021-001B, the Turksat 5A launch), perigee 170 km, apogee 47,173 km, 10.42 km/s.

At that speed 100 m takes 9.60 ms. The race runs at 469x slow motion so it lasts 4.5 seconds on screen. When the winner crosses the line:

- the other Falcons are 0.1 to 0.9 m behind (photo finish)
- the ISS, at 7.66 km/s, is 26.4 m behind
- the sound of the starter's pistol has gone 3.3 m (343 m/s), lane 7 is 7.9 m away, so the world record pace runner has not heard the gun yet. Reaction time (about 0.15 s) would not have run out either.

The last card says the winner was launched in 2021 and nobody is steering it.

## How it was built

I did not write the code myself. Claude Code wrote it from the spec, I directed it and gave feedback on the renders (for example captions overlapping and the sound being too high pitched).


- `fetch.py` downloads three CelesTrak queries (debris, rocket bodies, stations), once, and caches them.
- `rank.py` (plain Python) filters the catalogue, computes perigee speed for every object, picks the heats, the finalists and the race table, and writes JSON. Every number on screen comes from these files or a constant listed in `sources.md`, and the build fails if a number has no source.
- `build.py` runs inside Blender (bpy). It builds everything from an empty scene: camera moves, globe, track, tokens, HUD text, and bakes every animated value from a function of the frame number. No keyframes set by hand.
- The 12,379 objects are one mesh, one vertex per object, with the orbit elements as attributes. A Geometry Nodes tree, generated by the script, solves Kepler's equation for every object every frame (10 Newton iterations, unrolled into nodes), and handles the elimination: grey, then shrink to nothing. Orbit trails use the same tree.
- A time-lapse clock is set so that the winner hits perigee on the exact frame the camera dives in. Then a white flash cut to the track.
- Rocket stages, ISS and sprinter are built from lathe profiles, boxes and curves in code. Not to scale (they are tokens in 1.22 m lanes).
- The soundtrack is generated in Python too (a hum that follows the speed limit, ticks, a low note at the finish). The film works without sound.
- Render: EEVEE, 32 samples, 0.72 s per frame, 8 minutes for the whole film.

## Challenges

- The first threshold idea from my spec (7.6 / 7.9 / 10.0 km/s) did not empty low orbit in the real data. 1,403 objects were left after 7.9, still 47 in low orbit. Setting heat 2 to the ISS's own speed fixed it, and gave the ISS a reason to be in the film.
- Four of the five finalists have the same name, FALCON 9 R/B. On the cards and results the launch year tells them apart.
- In the first race render the rocket stages were invisible. The ground plane was drawn over them, because of transparent material sorting in EEVEE. Solid materials for ground and tokens fixed it.
- The first preview had no sound. The audio file was fine, but the encoder was given a relative path and Blender silently made a silent track.

## Honesty notes

- Orbits are two-body Keplerian propagation from the epoch elements (epoch 2026-10-19). Good for display, not a collision tool.
- The race is a flying start through perigee, at each object's perigee speed, in the Earth centred frame. The lanes are a straightening of the real perigee arc, they do not claim the objects share an orbit.
- World record pace is 9.58 s, shown as a generic wire figure, no likeness.

## AI and assets

The code was written by AI (Claude Code, Anthropic). The spec was written with AI assistance. No AI generated images, video or audio. No third party models, textures or sounds. The only thing not generated is the font, DejaVu Sans Mono, which ships with Blender. Orbital data is CelesTrak public data, used as input data.
```

### Built with

blender, python, bpy, geometry-nodes, eevee, celestrak, ffmpeg, claude-code

### "Try it out" links

- https://youtu.be/bkjEwBM9kNo
- https://github.com/apn201/velocity-100m-orbital

### Image gallery (in this order)

1. `01_thumbnail_finalists.jpg`
2. `wip_blender.png` (the required Blender WIP image)
3. `02_heat2_low_orbit.jpg`
4. `03_heat3_ellipses.jpg`
5. `04_photo_finish.jpg`
6. `05_meanwhile_start_line.jpg`
7. `06_results.jpg`
8. `07_final_card.jpg`

### Video demo link

https://youtu.be/bkjEwBM9kNo

---

## 3. YouTube

### Title

VELOCITY // 100 M ORBITAL - space junk races 100 m (Blender, real orbital data)

### Description

```
Every tracked piece of space debris and every spent rocket stage, 12,379 objects, on their real orbits. Qualifying heats knock out the slow ones until five remain. Then they race 100 m against the ISS and world record pace.

The fastest things near Earth are not satellites. They are old rocket stages on long transfer ellipses, diving through perigee at 10.4 km/s. The winner, a Falcon 9 second stage launched in 2021, does 100 m in 9.60 ms. The ISS is 26 m behind. The sound of the starter's pistol has travelled 3.3 m, so lane 7 has not heard the gun yet.

Made in Blender 5.2 with Python. One script builds the whole film from an empty scene: no modelling, no sculpting, no hand keyframes. Orbits are solved every frame in Geometry Nodes from real Keplerian elements. Data: CelesTrak public catalogue (US Space Force), epoch 2026-10-19. Orbits are two-body, for display.

Entry for the RenderJuice Blender Animation & Programmatic Rendering Contest, theme Speed.

Code written by AI (Claude Code), spec with AI assistance. No AI images or audio.

Source code: https://github.com/apn201/velocity-100m-orbital
```

### Tags

blender, blender 5.2, python, bpy, geometry nodes, procedural animation, programmatic animation, eevee, space debris, space junk, orbital mechanics, kepler, rocket stage, falcon 9, iss, international space station, 100m sprint, slow motion, data visualization, celestrak, renderjuice, speed
