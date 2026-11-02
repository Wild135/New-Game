"""Base classes and helpers shared by every menu screen."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import pygame

from game.rendering import icons
from game.rendering.draw import darken, draw_paragraph, draw_text, panel
from game.ui import theme
from game.ui.widgets import ScrollArea

if TYPE_CHECKING:  # pragma: no cover
    from game.app import App

# Area between the top bar and bottom navigation used by full screens.
PAGE_RECT = pygame.Rect(16, theme.TOP_BAR_H + 6, theme.WIDTH - 32,
                        theme.HEIGHT - theme.TOP_BAR_H - theme.NAV_H - 12)


class Screen:
    """A menu shown on top of the factory.

    ``kind`` = 'page' (fills the area between the top bar and the navigation;
    both stay usable) or 'popup' (a centred dialog that blocks everything).
    """
    kind = "page"
    title = ""
    nav_id: str | None = None

    def __init__(self, app: "App", **kwargs) -> None:
        self.app = app
        self.scroll = ScrollArea()
        self.tab = int(kwargs.get("tab", 0))
        self.age = 0.0

    @property
    def game(self):
        return self.app.game

    def close(self) -> None:
        self.app.close(self)

    def update(self, dt: float) -> None:
        self.age += dt

    def draw(self, surface: pygame.Surface, ui, dt: float) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    # ------------------------------------------------------------------ helpers
    def page_frame(self, surface: pygame.Surface, ui, title: str, icon: str | None = None) -> pygame.Rect:
        """Draws the page background + header. Returns the content rect."""
        rect = PAGE_RECT
        anim = min(1.0, self.age / 0.18)
        rect = rect.move(0, int((1 - anim) * 60))
        panel(surface, rect, (26, 44, 90), (110, 160, 240), radius=30, border=5, shadow=10)
        header = pygame.Rect(rect.x + 20, rect.y + 16, rect.width - 40, 96)
        panel(surface, header, (50, 90, 170), (150, 200, 255), radius=26, border=4, shadow=4)
        x = header.x + 24
        if icon:
            surface.blit(icons.icon(icon, 74), (x, header.centery - 37))
            x += 90
        draw_text(surface, title, (x, header.centery), 54, theme.WHITE, anchor="midleft", outline=4,
                  max_width=header.width - 220)
        close = pygame.Rect(header.right - 92, header.y + 10, 78, 76)
        if ui.button(surface, f"close:{id(self)}", close, "", theme.RED, icon="close", icon_size=44, radius=20):
            self.close()
        return pygame.Rect(rect.x + 20, header.bottom + 14, rect.width - 40, rect.bottom - header.bottom - 30)

    def popup_frame(self, surface: pygame.Surface, ui, title: str, size: tuple[int, int],
                    closable: bool = True, icon: str | None = None) -> pygame.Rect:
        dim = pygame.Surface((theme.WIDTH, theme.HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 20, 150))
        surface.blit(dim, (0, 0))
        anim = min(1.0, self.age / 0.2)
        scale = 0.85 + 0.15 * (1 - (1 - anim) ** 3)
        w, h = int(size[0] * scale), int(size[1] * scale)
        rect = pygame.Rect(0, 0, w, h)
        rect.center = (theme.WIDTH // 2, theme.HEIGHT // 2 - 40)
        panel(surface, rect, (30, 50, 100), (130, 180, 255), radius=34, border=5, shadow=12)
        ribbon = pygame.Rect(rect.x + 60, rect.y - 34, rect.width - 120, 96)
        panel(surface, ribbon, (60, 110, 210), (170, 210, 255), radius=30, border=4, shadow=6)
        if icon:
            surface.blit(icons.icon(icon, 70), (ribbon.x + 20, ribbon.centery - 35))
        draw_text(surface, title, ribbon.center, 50, theme.WHITE, anchor="center", outline=4,
                  max_width=ribbon.width - 180)
        if closable:
            close = pygame.Rect(rect.right - 86, rect.y + 6, 74, 72)
            if ui.button(surface, f"close:{id(self)}", close, "", theme.RED, icon="close", icon_size=40, radius=20):
                self.close()
        return pygame.Rect(rect.x + 30, ribbon.bottom + 20, rect.width - 60, rect.bottom - ribbon.bottom - 40)

    def begin_scroll(self, surface: pygame.Surface, ui, area: pygame.Rect, content_height: float,
                     dt: float) -> float:
        self.scroll.update(ui, area, content_height, dt)
        ui.set_clip(surface, area)
        return area.y - self.scroll.offset

    def end_scroll(self, surface: pygame.Surface, ui, area: pygame.Rect) -> None:
        ui.set_clip(surface, None)
        if self.scroll.max_offset() > 0:
            track = pygame.Rect(area.right - 8, area.y + 6, 6, area.height - 12)
            pygame.draw.rect(surface, (20, 30, 60), track, border_radius=3)
            frac = self.scroll.offset / max(1, self.scroll.max_offset())
            h = max(60, track.height * area.height / max(1, self.scroll.content_height))
            y = track.y + (track.height - h) * max(0, min(1, frac))
            pygame.draw.rect(surface, (150, 190, 255), pygame.Rect(track.x, y, 6, h), border_radius=3)

    def card(self, surface: pygame.Surface, rect: pygame.Rect, color=(36, 58, 112), border=(90, 130, 210)) -> None:
        panel(surface, rect, color, border, radius=24, border=4, shadow=5)

    def tabs(self, surface: pygame.Surface, ui, rect: pygame.Rect, labels: list[str]) -> None:
        new = ui.tab_bar(surface, f"tabs:{id(self)}", rect, labels, self.tab, size=34)
        if new != self.tab:
            self.tab = new
            self.scroll.scroll_to(0)

    def cost_button(self, surface, ui, uid: str, rect: pygame.Rect, label: str, cost: float,
                    currency: str = "credits", enabled: bool = True, color=theme.GREEN) -> bool:
        balance = {"credits": self.game.credits, "gems": self.game.gems, "rp": self.game.rp,
                   "stars": self.game.prestige.stars}[currency]
        affordable = enabled and balance >= cost
        if currency == "credits":
            sub = self.game.describe_money(cost)
        else:
            from game.core.numformat import format_number
            sub = format_number(cost) + {"gems": " gems", "rp": " RP", "stars": " stars"}[currency]
        clicked = ui.button(surface, uid, rect, label, color if affordable else theme.GREY, size=34,
                            sublabel=sub)
        if clicked and not affordable:
            self.app.audio.play("error")
            reason = "Not enough " + {"credits": "credits", "gems": "gems", "rp": "Research Points",
                                      "stars": "Legacy Stars"}[currency]
            self.app.hud.toast(reason if enabled else "Not available yet")
            return False
        return clicked


class ConfirmDialog(Screen):
    kind = "popup"

    def __init__(self, app: "App", title: str, message: str, on_yes: Callable[[], None],
                 yes_label: str = "Confirm", danger: bool = False, **kw) -> None:
        super().__init__(app, **kw)
        self.title = title
        self.message = message
        self.on_yes = on_yes
        self.yes_label = yes_label
        self.danger = danger

    def draw(self, surface, ui, dt):
        content = self.popup_frame(surface, ui, self.title, (860, 640))
        draw_paragraph(surface, self.message, pygame.Rect(content.x + 10, content.y + 20, content.width - 20, 300),
                       36, align="center")
        no = pygame.Rect(content.x + 20, content.bottom - 120, content.width // 2 - 40, 100)
        yes = pygame.Rect(content.centerx + 20, content.bottom - 120, content.width // 2 - 40, 100)
        if ui.button(surface, f"no:{id(self)}", no, "Cancel", theme.GREY_DARK, size=40):
            self.close()
        if ui.button(surface, f"yes:{id(self)}", yes, self.yes_label, theme.RED if self.danger else theme.GREEN, size=40):
            self.close()
            self.on_yes()


class MessageDialog(Screen):
    kind = "popup"

    def __init__(self, app: "App", title: str, message: str, icon: str | None = None, **kw) -> None:
        super().__init__(app, **kw)
        self.title, self.message, self.icon = title, message, icon

    def draw(self, surface, ui, dt):
        content = self.popup_frame(surface, ui, self.title, (860, 620), icon=self.icon)
        draw_paragraph(surface, self.message, pygame.Rect(content.x + 10, content.y + 20, content.width - 20, 320),
                       34, align="center")
        ok = pygame.Rect(content.centerx - 150, content.bottom - 120, 300, 100)
        if ui.button(surface, f"ok:{id(self)}", ok, "OK", theme.GREEN, size=44):
            self.close()


def rarity_tag(surface: pygame.Surface, pos: tuple[int, int], rarity: str) -> None:
    color = theme.RARITY_COLORS[rarity]
    text = rarity.upper()
    w = theme.fonts.get(24).size(text)[0] + 28
    rect = pygame.Rect(pos[0], pos[1], w, 38)
    pygame.draw.rect(surface, color, rect, border_radius=14)
    pygame.draw.rect(surface, darken(color, 0.5), rect, 3, border_radius=14)
    draw_text(surface, text, rect.center, 24, theme.WHITE, anchor="center", outline=2,
              outline_color=darken(color, 0.6))
