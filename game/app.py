"""The application: window, main loop, scenes, menus and saving.

Game rules live in ``game.core.game.Game``.  This file only connects that
logic to pygame (input, drawing, sound).
"""
from __future__ import annotations

import os
import sys
import time

import pygame

from game.audio.audio_manager import AudioManager
from game.core.config import ConfigError, GameConfig
from game.core.game import Game
from game.core.numformat import format_number
from game.rendering.draw import clear_caches, draw_text
from game.rendering.factory_view import FLOOR_H, SKY_H, FactoryView
from game.rendering.particles import ParticleSystem
from game.saves.save_manager import SaveManager
from game.ui import theme
from game.ui.hud import HUD
from game.ui.screens.base import ConfirmDialog, MessageDialog, Screen
from game.ui.screens.expansion import ExpansionScreen, PrestigeScreen
from game.ui.screens.floor_panel import FloorPanel
from game.ui.screens.managers import ManagersScreen
from game.ui.screens.menu import LoadingScene, MainMenu
from game.ui.screens.missions import DailyRewardScreen, MissionsScreen, RewardsScreen
from game.ui.screens.planets import PlanetsScreen
from game.ui.screens.research import ResearchScreen
from game.ui.screens.rockets import RocketsScreen
from game.ui.screens.settings import OfflineScreen, SettingsScreen, StatisticsScreen
from game.ui.screens.shop import ShopScreen
from game.ui.tutorial import Tutorial
from game.ui.widgets import UI

SCREENS = {
    "shop": ShopScreen, "managers": ManagersScreen, "rockets": RocketsScreen, "research": ResearchScreen,
    "expansion": ExpansionScreen, "planets": PlanetsScreen, "missions": MissionsScreen, "rewards": RewardsScreen,
    "daily": DailyRewardScreen, "settings": SettingsScreen, "statistics": StatisticsScreen,
    "prestige": PrestigeScreen, "offline": OfflineScreen,
}
FPS = 60
IDLE_FPS = 20


class App:
    def __init__(self, headless: bool = False, data_dir: str | None = None, clock=None):
        self.headless = headless
        self.clock_fn = clock or time.time
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        os.environ.setdefault("SDL_RENDER_SCALE_QUALITY", "best")
        pygame.init()
        theme.fonts.reset()
        clear_caches()
        pygame.display.set_caption("Rocket Empire: Idle Space Tycoon")
        self.screen = self._create_window()
        self.canvas = self.screen if self.screen.get_size() == (theme.WIDTH, theme.HEIGHT) else \
            pygame.Surface((theme.WIDTH, theme.HEIGHT))
        self.clock = pygame.time.Clock()
        self.ui = UI()
        self.running = True
        self.scene = "loading"
        self.stack: list[Screen] = []
        self.particles = ParticleSystem()
        self.saves = SaveManager(data_dir) if data_dir else SaveManager()
        self.config = GameConfig()
        self.game = Game(self.config)
        self.audio = AudioManager(self.game.settings)
        self.ui.clicked_sound = lambda: self.audio.play("click", 0.6)
        self.hud = HUD(self)
        self.factory_view = FactoryView(self)
        self.tutorial = Tutorial(self)
        self.loading = LoadingScene(self)
        self.menu = MainMenu(self)
        self.tutorial_rects: dict[str, pygame.Rect] = {}
        self._frame_targets: dict[str, pygame.Rect] = {}
        self.has_save = False
        self.autosave_timer = 0.0
        self.last_wall = self.now()
        self.fps_value = 0.0
        self._load_steps = [("Loading save...", self._load_save), ("Composing music...", self.audio.load),
                            ("Drawing the factory...", self._warm_up), ("Ready!", lambda: None)]
        self._load_index = 0

    # ------------------------------------------------------------------ window
    def _create_window(self) -> pygame.Surface:
        if self.headless:
            return pygame.display.set_mode((theme.WIDTH, theme.HEIGHT))
        try:
            screen = pygame.display.set_mode((theme.WIDTH, theme.HEIGHT), pygame.SCALED | pygame.RESIZABLE)
            # Shrink the window so the portrait canvas fits on a laptop screen.
            try:
                desktop_h = pygame.display.get_desktop_sizes()[0][1]
                target_h = int(desktop_h * 0.88)
                target_w = int(target_h * theme.WIDTH / theme.HEIGHT)
                window = pygame.Window.from_display_module()
                window.size = (target_w, target_h)
                window.position = pygame.WINDOWPOS_CENTERED
            except (AttributeError, pygame.error, IndexError):
                pass
            return screen
        except pygame.error:
            return pygame.display.set_mode((540, 960), pygame.RESIZABLE)

    def now(self) -> float:
        return self.clock_fn()

    # ------------------------------------------------------------------ loading / saving
    def _load_save(self) -> None:
        data = self.saves.load()
        if data is not None:
            try:
                self.game = Game.from_dict(data, self.config)
                self.has_save = True
            except (KeyError, ValueError, TypeError) as exc:
                print(f"Save could not be loaded ({exc}); starting a new game", file=sys.stderr)
                self.game = Game(self.config)
        else:
            self.game = Game(self.config)
        if self.saves.last_error:
            self.hud.toast(self.saves.last_error)
        self.audio.settings = self.game.settings

    def _warm_up(self) -> None:
        # Draw one frame of the factory off-screen so the first real frame is smooth.
        surf = pygame.Surface((theme.WIDTH, theme.HEIGHT))
        self.ui.enabled = False
        self.factory_view.draw(surf, self.ui, 0.016)
        self.ui.enabled = True

    def save_now(self) -> bool:
        try:
            self.game.touch(self.now())
            self.saves.save(self.game.to_dict())
            return True
        except (OSError, ValueError) as exc:
            self.hud.toast(f"Save failed: {exc}")
            return False

    def reset_progress(self) -> None:
        self.saves.delete_all()
        self.game = Game(self.config, now=self.now())
        self.audio.settings = self.game.settings
        self.stack.clear()
        self.factory_view = FactoryView(self)
        self.tutorial = Tutorial(self)
        self.particles.clear()
        self.save_now()
        self.hud.toast("Progress reset. A fresh start!")

    def start_game(self) -> None:
        self.scene = "game"
        self.stack = [s for s in self.stack if s.kind == "popup" and isinstance(s, (ConfirmDialog, MessageDialog))]
        report = self.game.apply_offline(self.now())
        if self.game.pending_offline is not None or report:
            self.push(OfflineScreen(self))
        self.audio.start_music()

    def go_to_menu(self) -> None:
        self.stack.clear()
        self.scene = "menu"
        self.has_save = True

    def quit(self) -> None:
        self.running = False

    # ------------------------------------------------------------------ screens
    def push(self, screen: Screen) -> None:
        self.stack.append(screen)
        self.audio.play("whoosh", 0.4)

    def close(self, screen: Screen) -> None:
        if screen in self.stack:
            self.stack.remove(screen)

    def open(self, name: str, **kwargs) -> None:
        if name not in SCREENS:
            return
        cls = SCREENS[name]
        for existing in self.stack:
            if type(existing) is cls:
                if "tab" in kwargs:
                    existing.tab = kwargs["tab"]
                self.stack.remove(existing)
                self.stack.append(existing)
                return
        screen = cls(self, **kwargs)
        if screen.kind == "page":
            # Only one page at a time - pages replace each other like tabs.
            self.stack = [s for s in self.stack if s.kind != "page"]
        self.push(screen)

    def open_floor_panel(self, floor_id: str, focus_manager: bool = False) -> None:
        for s in self.stack:
            if isinstance(s, FloorPanel):
                self.stack.remove(s)
                break
        self.push(FloorPanel(self, floor_id, focus_manager=focus_manager))

    def floor_panel_open(self, floor_id: str) -> bool:
        return any(isinstance(s, FloorPanel) and s.floor_id == floor_id for s in self.stack)

    def tutorial_target(self, key: str, rect: pygame.Rect) -> None:
        self._frame_targets[key] = pygame.Rect(rect)

    def draw_world_overlay(self, surface, ui, top) -> None:
        self.hud.draw_world_overlay(surface, ui, top)

    def scroll_factory_to(self, floor_id: str) -> None:
        self.factory_view.build_layout()
        for fid, y, h in self.factory_view.layout:
            if fid == floor_id:
                view_h = theme.HEIGHT - theme.NAV_H
                self.factory_view.scroll.content_height = self.factory_view.layout[-1][1] + FLOOR_H + 60
                self.factory_view.scroll.view = pygame.Rect(0, 0, theme.WIDTH, view_h)
                self.factory_view.scroll.scroll_to(y + h / 2 - view_h * 0.55)
                return
        self.factory_view.scroll.scroll_to(0 if floor_id == "sky" else SKY_H)

    # ------------------------------------------------------------------ game events
    def handle_game_events(self) -> None:
        for event in self.game.drain_events():
            k, d = event.kind, event.data
            if k == "launch":
                if d["planet"] == self.game.current_planet:
                    self.factory_view.on_launch(d["count"], d["revenue"])
            elif k == "toast":
                self.hud.toast(d["text"])
            elif k == "upgrade" and d.get("milestone"):
                lvl, mult = d["milestone"]
                self.hud.toast(f"Milestone Lv. {lvl}! Output x{format_number(mult)}", theme.YELLOW)
                self.audio.play("achievement")
            elif k == "ability":
                self.audio.play("ability")
                self.hud.toast(f"{d['name']} activated!", theme.YELLOW)
            elif k == "research":
                self.hud.toast(f"Researched {self.config.research[d['id']]['name']}!", theme.CYAN)
            elif k == "mission_complete":
                self.hud.toast("Mission complete! Claim your reward", theme.GREEN_LIGHT)
                self.audio.play("achievement", 0.6)
            elif k == "achievement":
                self.hud.toast(f"Achievement: {d['name']} tier {d['tier']}!", theme.GOLD)
                self.audio.play("achievement", 0.6)
            elif k == "reward":
                given = d.get("given", {})
                parts = []
                if "gems" in given:
                    parts.append(f"+{format_number(given['gems'])} gems")
                if "rp" in given:
                    parts.append(f"+{format_number(given['rp'])} RP")
                if "credits" in given:
                    parts.append("+" + self.game.describe_money(given["credits"]))
                if parts:
                    self.hud.toast("  ".join(parts), theme.YELLOW)
            elif k == "floor_unlocked":
                self.hud.toast(f"{self.config.floors[d['floor']]['name']} unlocked!", theme.GREEN_LIGHT)
            elif k == "rocket_unlocked":
                self.hud.toast(f"{self.config.rockets[d['rocket']]['name']} unlocked! Build it from the Rockets menu",
                               theme.GREEN_LIGHT)
            elif k == "planet_unlocked":
                self.audio.play("unlock")
            elif k == "manager_hired":
                self.audio.play("coin", 0.5)

    # ------------------------------------------------------------------ main loop
    def run(self, max_frames: int | None = None, screenshot: str | None = None) -> None:
        frames = 0
        while self.running:
            # Save CPU/battery when the window is in the background or minimised.
            focused = self.headless or (pygame.display.get_active() and pygame.key.get_focused())
            dt = self.clock.tick(FPS if focused else IDLE_FPS) / 1000.0
            self.frame(min(dt, 0.25))
            frames += 1
            if max_frames is not None and frames >= max_frames:
                break
        if screenshot:
            pygame.image.save(self.canvas, screenshot)
        self.shutdown()

    def shutdown(self) -> None:
        if self.scene == "game":
            self.save_now()
        self.audio.stop()
        pygame.quit()

    def process_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue
            if event.type in (pygame.WINDOWFOCUSLOST, pygame.WINDOWMINIMIZED) and self.scene == "game":
                self.save_now()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.stack:
                        top = self.stack[-1]
                        if not isinstance(top, OfflineScreen):
                            self.close(top)
                    elif self.scene == "game":
                        self.open("settings")
                elif event.key == pygame.K_F12:
                    path = os.path.join(str(self.saves.directory), f"screenshot_{int(time.time())}.png")
                    pygame.image.save(self.canvas, path)
                    self.hud.toast("Screenshot saved")
                continue
            if event.type in (pygame.FINGERDOWN, pygame.FINGERUP, pygame.FINGERMOTION):
                continue  # SDL also sends mouse events for touches; avoid double input
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.scene == "game" \
                    and self.tutorial.active and not self.stack_blocks_tutorial() and self.tutorial.blocks(event.pos):
                continue
            if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
                event = self._map_mouse(event)
            self.ui.handle_event(event)

    def _map_mouse(self, event):
        # With SCALED displays pygame already maps to canvas coordinates.
        if self.canvas is self.screen:
            return event
        sw, sh = self.screen.get_size()
        scale = min(sw / theme.WIDTH, sh / theme.HEIGHT)
        ox = (sw - theme.WIDTH * scale) / 2
        oy = (sh - theme.HEIGHT * scale) / 2
        x = int((event.pos[0] - ox) / scale)
        y = int((event.pos[1] - oy) / scale)
        attrs = dict(event.dict)
        attrs["pos"] = (x, y)
        return pygame.event.Event(event.type, attrs)

    def stack_blocks_tutorial(self) -> bool:
        """Popups other than the tutorial's own floor panel pause the tutorial overlay."""
        return any(s.kind == "popup" and not isinstance(s, FloorPanel) for s in self.stack)

    def frame(self, dt: float) -> None:
        self.process_events()
        self.ui.begin_frame(dt)
        self._frame_targets = {}
        surface = self.canvas
        if self.scene == "loading":
            self.frame_loading(surface, dt)
        elif self.scene == "menu":
            self.ui.enabled = not self.stack
            self.menu.draw(surface, self.ui, dt)
            self.draw_stack(surface, dt)
            self.particles.update(dt)
            self.particles.draw(surface, 0, screen_layer=True)
        else:
            self.frame_game(surface, dt)
        self.ui.end_frame()
        if self.canvas is not self.screen:
            sw, sh = self.screen.get_size()
            scale = min(sw / theme.WIDTH, sh / theme.HEIGHT)
            scaled = pygame.transform.smoothscale(self.canvas, (int(theme.WIDTH * scale), int(theme.HEIGHT * scale)))
            self.screen.fill((0, 0, 0))
            self.screen.blit(scaled, scaled.get_rect(center=(sw // 2, sh // 2)))
        if not self.headless:
            pygame.display.flip()

    def frame_loading(self, surface, dt) -> None:
        label, step = self._load_steps[min(self._load_index, len(self._load_steps) - 1)]
        self.loading.progress = self._load_index / (len(self._load_steps) - 1)
        self.loading.draw(surface, self.ui, dt, label)
        if self._load_index < len(self._load_steps):
            step()
            self._load_index += 1
        else:
            self.scene = "menu"

    def frame_game(self, surface, dt) -> None:
        game = self.game
        now = self.now()
        wall_gap = now - self.last_wall
        self.last_wall = now
        if wall_gap > 30:
            # The computer slept or the window was frozen: treat it as offline time.
            if game.apply_offline(now) is not None and not any(isinstance(s, OfflineScreen) for s in self.stack):
                self.push(OfflineScreen(self))
        else:
            game.update(dt)
            game.touch(now)
        self.handle_game_events()
        self.hud.update(dt)
        self.factory_view.update(dt)
        self.particles.update(dt)
        for s in self.stack:
            s.update(dt)
        # Autosave
        self.autosave_timer += dt
        if self.autosave_timer >= self.config.economy["autosave_seconds"]:
            self.autosave_timer = 0.0
            self.save_now()
        # Draw: factory, pages, bars, popups, overlays
        top = self.stack[-1] if self.stack else None
        self.ui.enabled = top is None
        self.factory_view.draw(surface, self.ui, dt)
        pages = [s for s in self.stack if s.kind == "page"]
        popups = [s for s in self.stack if s.kind == "popup"]
        for s in pages:
            self.ui.enabled = (s is top)
            s.draw(surface, self.ui, dt)
        self.ui.enabled = not popups
        self.hud.draw_top_bar(surface, self.ui)
        self.hud.draw_bottom(surface, self.ui, pages[-1].nav_id if pages else None, page_open=bool(pages))
        for s in popups:
            self.ui.enabled = (s is top)
            s.draw(surface, self.ui, dt)
        self.ui.enabled = True
        self.particles.draw(surface, 0, screen_layer=True)
        self.hud.draw_toasts(surface)
        # Tutorial overlay (paused while unrelated popups are open)
        self.tutorial_rects = dict(self.factory_view.highlight_rects)
        self.tutorial_rects.update(self.hud.highlight_rects)
        self.tutorial_rects.update(self._frame_targets)
        if self.tutorial.active and not self.stack_blocks_tutorial() and not pages:
            self.tutorial.update(dt)
            self.tutorial.draw(surface, self.ui)
        elif self.tutorial.active and pages:
            # Let the player explore menus; the tutorial resumes when they close.
            pass
        if game.settings.get("show_fps"):
            self.fps_value = self.clock.get_fps()
            draw_text(surface, f"{self.fps_value:.0f} FPS", (theme.WIDTH // 2, theme.TOP_BAR_H + 4), 28, theme.WHITE,
                      anchor="midtop", outline=2)

    def draw_stack(self, surface, dt) -> None:
        top = self.stack[-1] if self.stack else None
        for s in self.stack:
            s.update(dt)
            self.ui.enabled = s is top
            s.draw(surface, self.ui, dt)
        self.ui.enabled = True


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Rocket Empire: Idle Space Tycoon")
    parser.add_argument("--data-dir", help="Folder for save files (default: your user data folder)")
    parser.add_argument("--headless", action="store_true", help="Run without a window (for testing)")
    parser.add_argument("--frames", type=int, help="Quit after this many frames (testing)")
    parser.add_argument("--screenshot", help="Save a screenshot when quitting (testing)")
    args = parser.parse_args(argv)
    try:
        app = App(headless=args.headless, data_dir=args.data_dir)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    app.run(max_frames=args.frames, screenshot=args.screenshot)
    return 0
