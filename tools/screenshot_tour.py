"""Runs the real game headlessly and saves screenshots of every screen.

Usage:  python tools/screenshot_tour.py [output_folder]

Useful for checking visuals without clicking through the game by hand.  It
uses a temporary save folder, so your real save is never touched.
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame  # noqa: E402

from game.app import App  # noqa: E402


def click(app: App, pos: tuple[int, int], frames_between: int = 2) -> None:
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
    app.frame(1 / 60)
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=pos))
    for _ in range(frames_between):
        app.frame(1 / 60)


def run_frames(app: App, n: int, dt: float = 1 / 60) -> None:
    for _ in range(n):
        app.frame(dt)


def shot(app: App, folder: str, name: str) -> str:
    path = os.path.join(folder, f"{name}.png")
    pygame.image.save(app.canvas, path)
    return path


def advanced_state(app: App) -> None:
    """Fast-forward a game to mid-game so screens have interesting content."""
    g = app.game
    g.tutorial["done"] = True
    g.earn(5e9)
    g.gems = 1230
    g.rp = 560
    for fid in ("engines", "fuel", "electronics", "robotics"):
        g.unlock_floor(fid)
    for fid in g.factory.floors:
        if g.factory.floors[fid].level > 0:
            g.factory.floors[fid].level = 150 if fid in ("parts", "transport", "assembly") else 120
    for def_id, fid in (("alex", "parts"), ("sam", "transport"), ("riley", "assembly"), ("jordan", "launchpad"),
                        ("kai", "engines"), ("alex", "fuel"), ("alex", "electronics")):
        g.credits += 1e9
        inst = g.managers.hire(def_id)
        if inst:
            g.managers.assign(inst.uid, "earth", fid)
    for rid in ("explorer", "kestrel", "heavy_lifter"):
        g.credits += 1e8
        g.unlock_rocket(rid)
    g.select_rocket("heavy_lifter")
    for rid in ("precision_lathes", "fast_conveyors", "reduced_assembly", "launch_revenue"):
        g.rp += 100
        g.research.research(rid)
    g.unlock_planet("moon")
    g.credits = 12.6e9
    g.refresh_stats()


def main() -> None:
    folder = sys.argv[1] if len(sys.argv) > 1 else "screenshots"
    os.makedirs(folder, exist_ok=True)
    data_dir = tempfile.mkdtemp(prefix="rocket_empire_tour_")
    app = App(headless=True, data_dir=data_dir)
    run_frames(app, 6)
    shot(app, folder, "00_loading")
    run_frames(app, 10)
    shot(app, folder, "01_main_menu")
    app.start_game()
    run_frames(app, 30)
    shot(app, folder, "02_tutorial_welcome")
    app.tutorial.skip()
    run_frames(app, 10)
    shot(app, folder, "03_factory_start")
    advanced_state(app)
    app.factory_view.scroll.scroll_to(0)
    run_frames(app, 120)
    shot(app, folder, "04_factory_midgame")
    app.factory_view.scroll.scroll_to(700)
    run_frames(app, 40)
    shot(app, folder, "05_factory_floors")
    app.factory_view.scroll.scroll_to(0)
    app.factory_view.on_launch(250, 2.5e6)
    run_frames(app, 70)
    shot(app, folder, "06_launch")
    for i, name in enumerate(["managers", "rockets", "research", "shop", "expansion", "planets", "missions",
                              "prestige", "settings", "statistics"]):
        app.stack.clear()
        app.open(name)
        run_frames(app, 25)
        shot(app, folder, f"{10 + i:02d}_{name}")
    app.stack.clear()
    app.open("managers", tab=1)
    run_frames(app, 25)
    shot(app, folder, "20_managers_recruit")
    app.stack.clear()
    app.open("rockets", tab=1)
    run_frames(app, 25)
    shot(app, folder, "21_rockets_customize")
    app.stack.clear()
    app.open("missions", tab=1)
    run_frames(app, 25)
    shot(app, folder, "22_achievements")
    app.stack.clear()
    app.open_floor_panel("transport")
    run_frames(app, 25)
    shot(app, folder, "23_floor_panel")
    app.stack.clear()
    app.open("daily")
    run_frames(app, 25)
    shot(app, folder, "24_daily")
    app.stack.clear()
    app.open("rewards")
    run_frames(app, 25)
    shot(app, folder, "25_rewards")
    app.stack.clear()
    app.game.last_seen -= 4 * 3600 + 32 * 60
    app.game.apply_offline(app.now())
    app.open("offline")
    run_frames(app, 25)
    shot(app, folder, "26_offline")
    app.stack.clear()
    app.game.switch_planet("moon")
    run_frames(app, 40)
    shot(app, folder, "27_moon")
    print(f"Screenshots saved to {folder}")
    app.shutdown()


if __name__ == "__main__":
    main()
