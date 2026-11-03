# Testing Report

Environment used for development and testing: Linux cloud container, Python 3.13, pygame-ce 2.5.8
(SDL 2.32.10), headless SDL drivers (no GPU, no real audio device). **The game has not yet been
run on a physical Windows PC** — see "Manual verification" below.

## Automated tests — `python -m pytest`

**Result: 109 passed, 0 failed** (about 11 s).

| File | What it covers |
|---|---|
| `test_formulas.py` | number formatting (K…Dc, aa…, negatives, NaN, inf), durations, upgrade cost, bulk cost = summed cost, exact max-affordable, overflow safety, milestones, prestige formula |
| `test_factory.py` | manual vs automated floors, tapping, full chain, bottleneck detection, simulated throughput ≈ steady-state rate (within 8 %), no negative inventory, frame-rate independence (dt 0.05/0.1/0.5 within 6 %), storage caps, build rules, planet special resources, manual launch, serialization |
| `test_game.py` | can't overspend, single/bulk/max upgrades, level cap, milestone events, floor unlocks, manager hire/assign/slot rules/bonuses/levels/abilities/cooldowns/replacement, unique gem managers, research rules + effects, rocket unlock/select/value, planets unlock order + switching + preserved progress + parallel factories, prestige reset/keep rules, legacy upgrades, missions/achievements/daily/login/gift claimed only once, clock moved back, shop cosmetics/boosts/time-warp, workforce, rapid clicking, 1e299 money, large frame gaps, gradual feature unlocks |
| `test_offline_and_saves.py` | offline needs automation, cap (8 h default), matches steady-state math, collected only once, negative elapsed time, research extends cap, pending reward survives save, full save round-trip, missing save, corrupted save → backup restore, tampered checksum rejected, broken main never overwrites good backup, atomic write leaves no temp files, migration v0→v1 and newer-version refusal, invalid field values in a save |
| `test_config_and_architecture.py` | config validation (negative cost, unknown kind, duplicate id, bad growth, unknown component/research, missing files, bad JSON), **game logic does not import pygame** |
| `test_store.py` | store purchases (test provider), one-time items, failed payments, duplicate transactions never grant twice, Golden Investor perk survives prestige, exclusive cosmetics, store saves, Collect ×2, ability reset |
| `test_app_headless.py` | loading → menu → game via a real click, every screen and every floor panel opens and draws, **the tutorial can be completed by clicking only the highlighted targets**, upgrade button click, rapid clicks + wheel scrolling, save/reload through the app, computer sleep → offline screen |

## Economy simulation: `python tools/economy_sim.py`

A bot plays the real logic. It plays non-stop and optimally, so a real player (a few hours a day
plus offline earnings) will be roughly 3–5× slower in calendar time. The **"longest wait"** column
is the longest stretch without reaching any new goal (unlock, research, mission), which is the
main measure of boredom.

Latest run ("cheapest" strategy, with saving for planets and Space Legacy resets):

| Time played | Goals reached | Longest wait |
|---|---|---|
| 0–30 min | 25 | 5 m 36 s |
| 30 min–3 h | 32 | 24 m 45 s |
| 3 h–12 h | 144 | 30 m 40 s |
| 12 h–1 day | 195 | 38 m |
| 1–7 days | 1,249 | 1 d 11 h (late game, Asteroid Belt → Kepler) |

Milestones: Explorer I 15 min · Kestrel 31 min · Moon 2 h · first Space Legacy ≈3 h · Mars ≈8.5 h ·
Europa ≈20 h · Titan ≈1.4 d · Venus ≈2.4 d · Asteroid Belt ≈2.8 d · Kepler ≈6.3 d ·
Deep Space Colony ≈7 d · Quantum Starship ≈9.8 d (bot time).

Balancing history:
* v1 reached $500Qa in one hour. Fixed with steeper cost growth, higher unlock prices and weaker
  support floors.
* Research Points now grow with log10 of each launch batch.
* v2 had a 9-hour dead zone after the Kestrel and a 17-hour wall after Mars. Fixed by moving
  electronics, the Heavy Lifter and the Moon earlier, adding 7 mid-game missions, and shrinking the
  late planet price jumps.
* Switching rockets could lower income. The Rockets screen now shows each rocket's estimated income.
* Bug fixed: stale stats for removed planets after a prestige reset inflated the displayed income.

Known remaining issue: one late-game stretch (about 1.5 days of non-stop bot play) between the
Asteroid Belt and Kepler Verdant.

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
