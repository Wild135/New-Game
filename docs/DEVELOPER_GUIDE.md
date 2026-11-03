# Developer Guide

## Architecture in one picture

```
            ┌──────────────── pygame layer ────────────────┐
 input ───▶ │ app.py ─ UI (widgets.py, immediate mode)      │
            │   ├─ FactoryView (rendering/factory_view.py)  │
            │   ├─ HUD, Tutorial, screens/*                 │
            │   └─ AudioManager, ParticleSystem             │
            └──────────────┬───────────────▲───────────────┘
                 actions   │               │  events + state (read only)
            ┌──────────────▼───────────────┴───────────────┐
            │ Game (core/game.py)   ← pure Python, testable │
            │  Factory × planets · ManagerSystem · Research │
            │  Prestige · Missions · Shop · offline · saves │
            └──────────────▲───────────────────────────────┘
                           │ loads
                     config/*.json
```

* **Logic never imports pygame.** A test (`test_game_logic_does_not_import_pygame`) enforces this,
  so the rules can be reused if the game is ported to another engine.
* The UI calls `Game` methods (`upgrade_floor`, `managers.hire`, …). `Game` emits `GameEvent`s
  (`launch`, `upgrade`, `achievement`, `toast`, …) which `App.handle_game_events` turns into sounds,
  particles and messages.
* The UI is **immediate mode**: every frame, screens draw widgets and `ui.button(...)` returns
  `True` when clicked. There are no widget objects to keep in sync with game state.

## Simulation

`Game.update(real_dt)` runs fixed steps of `tick_seconds` (0.1 s). Each step:

1. Manager ability and boost timers tick down.
2. `refresh_stats()` recomputes every rate from levels and bonuses (`FactoryStats`).
3. Every factory runs `Factory.step(dt)`:
   * **Producers** add components to their own storage (capped).
   * **Transport** moves a budget of `rate × dt` items, shared between components in recipe
     proportions, into the assembly buffer (capped).
   * **Assembly** consumes components in recipe ratio and adds finished rockets to the pad queue.
   * **Launchpad** launches up to `capacity` rockets each launch window (automated) or after a
     3-second countdown (manual).
4. Launches pay credits and Research Points.

A floor works only if it has a manager, or while it has banked "manual seconds" from taps.
Big real-time gaps (over 30 s: sleep, frozen window) go through the offline calculation instead,
so frame rate never changes how much money you earn.

**Bottleneck:** `FactoryStats.stage_rockets[floor]` = rockets/s that stage could sustain.
The minimum is `bottleneck` and the shown `$X/s` badge on each floor is
`stage_rockets × value_per_rocket`.

## Economy formulas

| Thing | Formula (config key) |
|---|---|
| Upgrade cost | `base_cost × planet.cost_mult × cost_mods × cost_growth^(level-1)` |
| Bulk / max buy | geometric series sum (`formulas.bulk_cost`, `max_affordable`) |
| Floor output | `base_rate × level × milestone(level) × modifiers` |
| Milestones | `economy.milestones`: Lv10 ×2, 25 ×3, 50 ×5, 100 ×10, 150 ×15 … (total multiplier) |
| Support floor | `1 + per_level × level × support_milestone(level)` |
| Rocket value | `rocket.value × planet.value_mult × value_mods` |
| RP per launch | `rocket.rp × rp_mods × (1 + log10(rockets in batch))` |
| Storage | `max(min_storage, rate × storage_seconds) × storage_mods` |
| Offline | `automated rocket rate × min(time, cap) × efficiency × value` |
| Legacy Stars | `floor(scale × (run_earnings / divisor)^exponent)` (prestige.json) |
| Star bonus | `1 + star_bonus × unspent stars` on all lines |

Modifiers (`economy/modifiers.py`) multiply together. Sources: research, legacy upgrades and
stars, shop boosts, planet traits, workforce, support floors, the rocket's bonus, and manager
passives/abilities.

Numbers are Python floats clamped to `1e300` (`numformat.clamp_big`), so values never overflow.
They are shown as K, M, B, T, Qa, Qi, Sx, Sp, Oc, No, Dc, then aa, ab, …

## Save system (`saves/save_manager.py`)

* JSON payload `{format, checksum (SHA-256 of data), data}`.
* Atomic write: temp file → `fsync` → `os.replace`.
* Rotating backups `save.bak1..3.json`. A damaged main save is never rotated into the backups.
* `load()` returns the newest valid file; `last_error` explains any recovery.
* `migrate()` upgrades old versions step by step (bump `CURRENT_VERSION` and add a step).
* `Game.from_dict` validates every field and drops unknown ids, so old saves survive config changes.

## How to add content (no code changes needed)

**A new rocket** — add an entry to `config/rockets.json`:
```json
{"id": "comet", "name": "Comet", "recipe": {"parts": 14, "engines": 6}, "value": 120, "rp": 0.45,
 "unlock_cost": 30000, "planet": null, "research": null,
 "colors": {"body": [240,240,250], "accent": [40,200,120]}, "fins": 3, "height": 1.15,
 "bonus": null, "description": "A nimble mid-range launcher."}
```
Use `"special"` in the recipe plus `"planet": "<id>"` for planet-exclusive rockets.

**A new planet** — add to `config/planets.json` with `unlock_cost`, `value_mult`, `cost_mult`,
`special` (a component id from `floors.json → components`, or null), `modifiers`
(e.g. `{"transport": 2.0}`), a `theme` (sky/hill/ground/planet colours), `trait` and `description`.
Planets unlock in list order.

**A new manager** — add to `config/managers.json`: `rarity` (common/rare cost credits,
epic/legendary cost gems), `slot` (producer/transport/assembly/launch/any), `passive` effects
(`stat` `rate`/`storage` boosts the floor, or `scope: "factory"`), an `active` ability and a `look`.

**A new factory floor** — add to `config/floors.json`. `kind: "producer"` needs a new `component`
(add it to `components` too and use it in a rocket recipe). `kind: "support"` needs `effect`
(a modifier stat such as `production`, `value`, `logistics`, `rp_gain`) and `per_level`.
The floor appears in every factory automatically. To give it unique machinery, add a branch in
`FactoryView.draw_support` / `draw_producer`.

Research nodes, missions, achievements, legacy upgrades, shop items and workforce upgrades all
follow the same pattern in their JSON files. `GameConfig.validate()` reports mistakes with a clear
message when the game starts.

## Art and audio

* `rendering/icons.py` – vector icons drawn at 256 px and smooth-scaled down.
* `rendering/art.py` – rockets, workers (6 animation states × 8 frames), sky scenes, floors,
  logo, planets. Everything is cached after the first draw.
* `audio/synth.py` – sound effects and a 32-second music loop synthesised with numpy.
  `tools/generate_assets.py` exports everything to `assets/`. If WAV files exist there the game
  uses them, so you can replace any sound with your own (properly licensed) recording.

Only 2–3 workers are drawn per floor. The simulated employee count comes from the level and
workforce, so huge factories never need thousands of sprites.
