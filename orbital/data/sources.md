# Sources for every displayed number

Validation looks up each `source` key used by the HUD here. A displayed number without an entry fails the build.

## field.json:count
Number of tracked objects after filtering (section 2.3 of the spec): CelesTrak GP queries `NAME=DEB` and `NAME=R/B`, unique catalogue numbers, epoch within 30 days of the common epoch, 0 <= e < 1, perigee above 120 km. Counts per filter are stored in field.json.

## field.json:epoch
Common epoch. The requested epoch (2026-10-31) is later than the data, so rank.py uses the most recent day in the data. Mean anomalies are moved to this epoch with two-body motion. Display orbits are two-body Keplerian propagation from the epoch elements; accurate enough to look right for a few revolutions, not a conjunction tool.

## field.json:vp
Perigee speed of each object, two-body: v_p = sqrt(mu (2/r_p - 1/a)), mu = 398600.4418 km^3/s^2, a from mean motion, r_p = a(1 - e). The survivor counter counts objects with v_p above the threshold on screen.

## heats.json:threshold
Heat thresholds, chosen in rank.py so each heat removes a recognisable population: 7.0 km/s (geostationary and navigation orbits are slow), the ISS's own perigee speed (most of low orbit), 10.0 km/s (the rest of low orbit). The final keeps the five fastest.

## finalists.json:iss
ISS (ZARYA, catalogue number 25544) from CelesTrak `GROUP=stations`, same two-body perigee speed formula.

## race.json:lanes
100 m time = 100 m / v_p. Distance at the winner's finish = v_p x winner's time. Gap = 100 m minus that distance. Flying start through perigee at each object's perigee speed, Earth-centred inertial frame. Lane 7 is world record pace and does not start (see world-record, reaction-time).

## race.json:winner_time_ms
The winner's 100 m time in milliseconds. The counter shows real elapsed time since the leader crossed the start line, capped at the winner's time.

## race.json:sound_m_at_finish
Speed of sound 343 m/s (dry air, 20 C) x the winner's time. The starter stands on the inside of lane 1 at the start line. Lane width 1.22 m (World Athletics), so lane 7's centre is 7.9 m away.

## timeline:slowmo
Slow-motion factor = screen duration of the winner's 100 m (race_frames in timeline.json / 24 fps) / the winner's real time.

## world-record
Men's 100 m world record, 9.58 s (Usain Bolt, Berlin 2009, World Athletics). Shown only as a pace; the figure is generic, no likeness.

## reaction-time
Typical elite sprint reaction time about 0.15 s; World Athletics treats anything under 0.100 s as a false start.

## track
Track distance labels in metres from the start line.
