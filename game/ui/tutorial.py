"""Interactive first-time tutorial.

Each step highlights one thing on screen and waits until the player does it.
While a step has a target, taps outside the target are ignored so the player
can't get lost.  The tutorial can be replayed from Settings.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Callable

import pygame

from game.rendering import icons
from game.rendering.draw import draw_paragraph, panel
from game.ui import theme

if TYPE_CHECKING:  # pragma: no cover
    from game.app import App


class Step:
    def __init__(self, text: str, target: str | None = None, done: Callable[["App"], bool] | None = None,
                 scroll_to: str | None = None, on_enter: Callable[["App"], None] | None = None,
                 button: str | None = None):
        self.text = text
        self.target = target
        self.done = done
        self.scroll_to = scroll_to
        self.on_enter = on_enter
        self.button = button


def _parts(app):
    return app.game.factories["earth"]


def _ensure_credits(amount):
    def apply(app):
        if app.game.credits < amount:
            app.game.earn(amount - app.game.credits)
            app.hud.toast("Here are some credits to get you started!")
    return apply


STEPS = [
    Step("Welcome to ROCKET EMPIRE! You just bought a tiny rocket company. Let's build your very first rocket!",
         button="Let's go!"),
    Step("This is your factory. Each floor does one job: make parts, carry them, assemble rockets, and launch them "
         "from the pad at the top.", button="Next"),
    Step("Parts Production makes rocket parts. Tap the floor to put your workers to work!", target="floor:parts",
         scroll_to="parts", done=lambda app: _parts(app).components_made >= 10),
    Step("Great! Transport carries parts to Assembly. Tap the Transport floor!", target="floor:transport",
         scroll_to="transport", done=lambda app: _parts(app).rockets_built > 0 or sum(_parts(app).buffer.values()) >= 10),
    Step("Assembly turns parts into a rocket. Tap the Assembly floor!", target="floor:assembly", scroll_to="assembly",
         done=lambda app: _parts(app).ready >= 1 or app.game.stats["rockets_launched"] >= 1),
    Step("Your rocket is ready! Press LAUNCH to send it into space!", target="launch_btn", scroll_to="launchpad",
         done=lambda app: app.game.stats["rockets_launched"] >= 1),
    Step("Liftoff! Every launch pays you credits. More rockets per minute = more money.", button="Awesome!"),
    Step("Spend credits on upgrades. Upgrade Parts Production to make parts faster.", target="upg:parts",
         scroll_to="parts", on_enter=_ensure_credits(10),
         done=lambda app: _parts(app).floors["parts"].level >= 2),
    Step("Tapping gets tiring! Managers run floors for you. Tap the manager slot on Parts Production.",
         target="mgr:parts", scroll_to="parts", on_enter=_ensure_credits(70),
         done=lambda app: app.game.stats["managers_hired"] >= 1 or app.floor_panel_open("parts")),
    Step("Hire a Production Supervisor to automate this floor.", target="hire_quick",
         done=lambda app: app.game.stats["managers_hired"] >= 1),
    Step("Parts Production now works by itself, even while you're away! Automate every floor, watch the BOTTLENECK "
         "badge, complete missions and grow your empire. Have fun!", button="Start playing!"),
]


class Tutorial:
    def __init__(self, app: "App"):
        self.app = app
        self.time = 0.0
        self._entered = -1

    @property
    def state(self):
        return self.app.game.tutorial

    @property
    def active(self) -> bool:
        return not self.state.get("done") and self.state.get("step", 0) < len(STEPS)

    def restart(self) -> None:
        self.state["done"] = False
        self.state["step"] = 0
        self._entered = -1

    def current(self) -> Step | None:
        if not self.active:
            return None
        return STEPS[self.state["step"]]

    def advance(self) -> None:
        self.state["step"] += 1
        self.app.audio.play("click")
        if self.state["step"] >= len(STEPS):
            self.state["done"] = True

    def skip(self) -> None:
        self.state["done"] = True

    def target_rect(self) -> pygame.Rect | None:
        step = self.current()
        if step is None or step.target is None:
            return None
        return self.app.tutorial_rects.get(step.target)

    def update(self, dt: float) -> None:
        self.time += dt
        step = self.current()
        if step is None:
            return
        idx = self.state["step"]
        if self._entered != idx:
            self._entered = idx
            if step.on_enter:
                step.on_enter(self.app)
            if step.scroll_to:
                self.app.scroll_factory_to(step.scroll_to)
        # The "hire" step needs the manager picker open; fall back if it was closed.
        if step.target == "hire_quick" and not self.app.floor_panel_open("parts") and \
                self.app.game.stats["managers_hired"] < 1:
            self.state["step"] -= 1
            self._entered = -1
            return
        if step.done and step.done(self.app):
            self.advance()

    def blocks(self, pos) -> bool:
        """True if a press at ``pos`` should be ignored (outside the highlighted target)."""
        step = self.current()
        if step is None:
            return False
        if step.button:
            return not self._button_rect().collidepoint(pos) and not self._skip_rect().collidepoint(pos)
        rect = self.target_rect()
        if rect is None:
            return False
        return not rect.inflate(20, 20).collidepoint(pos) and not self._skip_rect().collidepoint(pos)

    def _bubble_rect(self, target: pygame.Rect | None) -> pygame.Rect:
        h = 300
        if target is not None and target.centery < theme.HEIGHT * 0.5:
            return pygame.Rect(40, theme.HEIGHT - theme.NAV_H - h - 140, theme.WIDTH - 80, h)
        return pygame.Rect(40, theme.TOP_BAR_H + 140, theme.WIDTH - 80, h)

    def _button_rect(self) -> pygame.Rect:
        bubble = self._bubble_rect(self.target_rect())
        return pygame.Rect(bubble.centerx - 190, bubble.bottom - 40, 380, 100)

    def _skip_rect(self) -> pygame.Rect:
        return pygame.Rect(20, theme.TOP_BAR_H + 12, 210, 70)

    def draw(self, surface: pygame.Surface, ui) -> None:
        step = self.current()
        if step is None:
            return
        target = self.target_rect()
        dim = pygame.Surface((theme.WIDTH, theme.HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 20, 150 if step.button else 110))
        if target is not None:
            hole = target.inflate(24, 24)
            pygame.draw.rect(dim, (0, 0, 0, 0), hole, border_radius=26)
        surface.blit(dim, (0, 0))
        if target is not None:
            pulse = 6 + int(4 * math.sin(self.time * 6))
            pygame.draw.rect(surface, theme.YELLOW, target.inflate(24 + pulse, 24 + pulse), 6, border_radius=28)
            # pointing hand / arrow
            ax = target.centerx
            above = target.top > 260
            ay = (target.top - 90 - abs(math.sin(self.time * 5)) * 24) if above else \
                (target.bottom + 20 + abs(math.sin(self.time * 5)) * 24)
            arrow = icons.icon("arrow_up", 90)
            if above:
                arrow = pygame.transform.flip(arrow, False, True)
            surface.blit(arrow, (ax - 45, ay))
        bubble = self._bubble_rect(target)
        panel(surface, bubble, (30, 60, 130), theme.YELLOW, radius=34, border=5, shadow=10)
        surface.blit(icons.manager_portrait({"skin": [230, 180, 140], "hair": [250, 90, 140], "shirt": [255, 215, 80]},
                                            170), (bubble.x + 14, bubble.y + 30))
        draw_paragraph(surface, step.text, pygame.Rect(bubble.x + 200, bubble.y + 30, bubble.width - 230,
                                                       bubble.height - 60), 34, theme.WHITE)
        prev_enabled = ui.enabled
        ui.enabled = True
        if step.button:
            if ui.button(surface, "tut_next", self._button_rect(), step.button, theme.GREEN, size=40):
                self.advance()
        if ui.button(surface, "tut_skip", self._skip_rect(), "Skip tutorial", theme.GREY_DARK, size=28):
            self.skip()
        ui.enabled = prev_enabled
