# Sources for every displayed number

Validation looks up each `source` key from `frames.json` here. A displayed number without an entry fails the build.

## frames.py:ground
Muzzle velocity of Federal American Eagle 9mm Luger 147 gr FMJ Flat Point (AE9FP): 1000 ft/s = 0.3048 km/s, manufacturer's published figure. Vector due east, horizontal, at 60.9 N. VERIFY test-barrel length before final submission.

## frames.py:earth
astropy ITRS -> GCRS transform of the muzzle vector at the epoch 2026-10-31T23:59:00Z. Adds Earth rotation (about 0.465 km/s x cos 60.9 deg).

## frames.py:sun
astropy GCRS -> HCRS transform. Adds Earth's orbital velocity at the epoch. The site is on the night side at the epoch, so rotation adds to the orbital motion.

## frames.py:galaxy
astropy Galactocentric frame, `galactocentric_frame_defaults` "latest" parameter set (values recorded in frames.json).

## frames.py:cmb
Heliocentric vector plus the Planck 2018 solar dipole: 369.82 km/s toward galactic l = 264.021 deg, b = 48.253 deg (Planck Collaboration 2020, A&A 641, A1).

## frames.py:span
Ratio of the CMB-frame speed to the ground-frame speed, rounded to two significant figures.

## saturn-v
Apollo 11 S-IVB at translunar injection cutoff: inertial (Earth-centred) velocity 35,579 ft/s = 10.84 km/s. Source: Saturn V Launch Vehicle Flight Evaluation Report AS-506 (NASA MPR-SAT-FE-69-9). Shown as "~10.8". At TLI only the S-IVB third stage and the spacecraft remain, so the silhouette is that stack.

## pioneer-10
Pioneer 10 heliocentric speed, about 11.9 km/s in 2026 (asymptotic escape speed about 11.8 km/s). Source: NASA/JPL Horizons, target -23. Shown as "~12". VERIFY against Horizons at the epoch.

## range
Downrange distance ticks in metres, ground frame, from the muzzle. Positions follow the muzzle velocity and the slow-motion factor in timeline.json.

## ladder-axis
Logarithmic axis in km/s, frame-independent scale.
