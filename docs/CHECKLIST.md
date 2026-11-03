# Development Checklist

Legend: ✅ done and tested · 🟡 done, needs manual check on Windows · ⬜ not done

## Phase 1 – Planning
- ✅ Environment inspected (Python, pygame-ce, numpy, pytest)
- ✅ Reference image analysed → layout: top bar, mission panel, side buttons, launchpad, floors, nav
- ✅ Architecture (logic / rendering separation), economy design, project structure

## Phase 2 – Core game
- ✅ Main loop, scalable portrait window (1080×1920 canvas, letterboxed) 🟡 real-window check
- ✅ Immediate-mode UI toolkit (buttons, tabs, sliders, toggles, scroll areas with inertia)
- ✅ Factory screen with scrolling floors, production simulation, currencies, upgrades x1/x10/x25/MAX
- ✅ First rocket launch with countdown, smoke, flames, camera shake/tilt, revenue popup

## Phase 3 – Automation
- ✅ Animated workers (idle, walk, work, carry, inspect, celebrate)
- ✅ 15 managers, 4 rarities, passives, abilities, cooldowns, levels, assignment/replacement
- ✅ Capacities, storage, transport bottlenecks shown in UI

## Phase 4 – Progression
- ✅ 10 rockets (3 planet-exclusive), unlocks, selection, bonuses
- ✅ 29 research nodes in 7 categories
- ✅ 31 main missions, daily missions, 10 tiered achievements, daily login calendar, free gift
- ✅ 13 floor types (5 producers, planetary refinery, 4 support departments + core)
- ✅ 9 planets with unique traits, resources, art; parallel factories
- ✅ Space Legacy prestige with 8 legacy upgrades

## Phase 5 – Visual polish
- ✅ Original procedural cartoon art, icons, logo, planets
- ✅ Particles (smoke, fire, coins, gems, stars, confetti, sparkles), UI animations
- ✅ Synthesised SFX (16) and music loop 🟡 listen on real speakers
- ✅ Cosmetics: paints, decals, exhausts, launch effects, factory themes, hats

## Phase 6 – Persistence
- ✅ Autosave/manual save, validation, checksum, backups, migration, atomic writes
- ✅ Offline earnings with cap, efficiency, boosts, clock protection, Welcome Back screen

## Phase 7 – QA
- ✅ 99 automated tests passing
- ✅ Economy bot (1 h / 24 h / 1 week, two strategies, offline)
- ✅ Headless screenshot tour of every screen; visual issues fixed
- ✅ Performance profiled (≈10 ms/frame headless)

## Phase 8 – Packaging
- ✅ PyInstaller spec + `build_windows.bat`; packaged build verified on Linux
- 🟡 Build and test the `.exe` on Windows

## Future ideas
- ⬜ Mobile port (see MOBILE_PUBLISHING.md)
- ⬜ More planet-specific machinery art and missions per planet
- ⬜ Localisation
