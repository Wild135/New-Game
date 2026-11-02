# Testing Report

Environment used for development and testing: Linux cloud container, Python 3.13, pygame-ce 2.5.8
(SDL 2.32.10), headless SDL drivers (no GPU, no real audio device). **The game has not yet been
run on a physical Windows PC** — see "Manual verification" below.

## Automated tests — `python -m pytest`

**Result: 99 passed, 0 failed** (about 13 s).

| File | What it covers |
|---|---|
| `test_formulas.py` | number formatting (K…Dc, aa…, negatives, NaN, inf), durations, upgrade cost, bulk cost = summed cost, exact max-affordable, overflow safety, milestones, prestige formula |
| `test_factory.py` | manual vs automated floors, tapping, full chain, bottleneck detection, simulated throughput ≈ steady-state rate (within 8 %), no negative inventory, frame-rate independence (dt 0.05/0.1/0.5 within 6 %), storage caps, build rules, planet special resources, manual launch, serialization |
| `test_game.py` | can't overspend, single/bulk/max upgrades, level cap, milestone events, floor unlocks, manager hire/assign/slot rules/bonuses/levels/abilities/cooldowns/replacement, unique gem managers, research rules + effects, rocket unlock/select/value, planets unlock order + switching + preserved progress + parallel factories, prestige reset/keep rules, legacy upgrades, missions/achievements/daily/login/gift claimed only once, clock moved back, shop cosmetics/boosts/time-warp, workforce, rapid clicking, 1e299 money, large frame gaps, gradual feature unlocks |
| `test_offline_and_saves.py` | offline needs automation, cap (8 h default), matches steady-state math, collected only once, negative elapsed time, research extends cap, pending reward survives save, full save round-trip, missing save, corrupted save → backup restore, tampered checksum rejected, broken main never overwrites good backup, atomic write leaves no temp files, migration v0→v1 and newer-version refusal, invalid field values in a save |
| `test_config_and_architecture.py` | config validation (negative cost, unknown kind, duplicate id, bad growth, unknown component/research, missing files, bad JSON), **game logic does not import pygame** |
| `test_app_headless.py` | loading → menu → game via a real click, every screen and every floor panel opens and draws, **the tutorial can be completed by clicking only the highlighted targets**, upgrade button click, rapid clicks + wheel scrolling, save/reload through the app, computer sleep → offline screen |

## Economy simulation — `python tools/economy_sim.py`

A bot plays the real logic using two strategies ("bottleneck-first" and "cheapest-first").
These are design targets, not guarantees. Human players are slower than the bot early on and
faster later thanks to offline earnings.

| Milestone | Target | Bottleneck bot | Cheapest bot |
|---|---|---|---|
| First upgrade | < 1 min | 0 s | 0 s |
| First launch | ≈ 2 min (incl. tutorial) | 13 s (no tutorial reading) | 13 s |
| First manager / automation | 5–10 min | 6 s / full line at 1 m 55 s | 6 s / 4 m 25 s |
| First major expansion (Engine floor + Explorer I) | 20–30 min | 3 m 49 s / 5 m 19 s | 6 m 37 s / 9 m 55 s |
| Kestrel (3rd rocket) | — | 19.5 min | 38 min |
| Moon | — | ≈ 5 h 20 m | — |
| First Space Legacy | not mandatory early | ≈ 5 h 40 m | — |
| Mars / Europa / Titan | — | ≈ 1 d 4 h / 2 d / 3 d 5 h | — |

One-week bot run (bottleneck, with prestige): reaches 5 planets and about $111Qa/s income.
Offline (30-min save, automated): 1 h → $8.75M, 8 h → $70M, 24 h → capped at 8 h. ✔

Balancing problems found and fixed during development:

* The first version reached $500Qa in one hour. Fixed with steeper cost growth (1.145–1.165,
  matching the reference image's Lv.150 costs), much higher rocket/floor/planet unlock prices,
  and weaker support floors.
* Research Points exploded with production. RP now grows with log10 of each launch batch.
* Prestige feedback loop. Star exponent lowered to 0.33 and star bonus to 2 %.

Remaining observations: the first expansion arrives earlier than the 20–30 min target for an
optimal bot (fine for beginners). Switching to a new rocket temporarily lowers income until the new
component floor is upgraded. The BOTTLENECK badge explains this in game.

## Performance (headless, CPU-only software rendering)

* Mid-game factory with 7 floors, active launch particles (≈300 particles): **10–11 ms per frame**,
  about 90–100 FPS possible, so 60 FPS has headroom. Simulation cost is small (< 1 ms per tick).
* Startup: audio synthesis ≈ 0.5 s. Art is generated lazily and cached.
* The window drops to 20 FPS while unfocused or minimised to save CPU.
* Particle pool is fixed (700) and text/shape caches are LRU-bounded, so there is no unbounded
  memory growth.

## Packaging

The PyInstaller spec was built and the packaged binary ran (headless, 120 frames, screenshot OK)
**on Linux**. PyInstaller can't cross-compile, so the Windows `.exe` must be built on Windows with
`tools\build_windows.bat`.

## Manual verification still required (on your Windows PC)

1. `python main.py`: the window fits your screen, resizing keeps the portrait letterbox, and text
   is sharp.
2. Sound and music play. The volume sliders and mute work. (Headless tests used a dummy audio device.)
3. Mouse wheel and click-drag scrolling feel smooth at 60 FPS on your laptop.
4. Close and reopen after a few minutes: the Welcome Back screen appears with sensible numbers.
5. Build the `.exe` with `tools\build_windows.bat` and run it on a PC without Python.
6. Play the tutorial yourself and judge the pacing and fun. This can't be measured automatically.

## Known limitations

* Offline progress trusts the device clock. Backwards changes are blocked and rewards are capped,
  but a fully offline game can't be made tamper-proof.
* Mobile builds are not included (see `MOBILE_PUBLISHING.md`).
* Workers are decorative animations (2–3 per floor). Their simulated count drives the displayed
  "Workers" number and the workforce bonuses.
