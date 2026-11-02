"""A tiny immediate-mode UI toolkit.

Every frame, screens call functions like ``ui.button(...)`` while drawing.
The function draws the widget and returns True if it was clicked.  This keeps
screen code short and avoids keeping widget objects in sync with game state.

How clicks work:
* On mouse/touch down we remember the position.
* While drawing, every widget under that position registers itself; the last
  one drawn (the top-most) becomes the "pressed" widget.
* On release over the same widget - and if the pointer did not drag far
  (scrolling) - that widget reports a click.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from game.rendering import icons
from game.rendering.draw import (darken, draw_text, glossy_button, gradient_surface, lighten,
                                 panel, progress_bar)
from game.ui import theme

DRAG_THRESHOLD = 14


@dataclass
class Pointer:
    pos: tuple[int, int] = (-1000, -1000)
    down: bool = False
    down_pos: tuple[int, int] | None = None
    dragged: bool = False
    released_pos: tuple[int, int] | None = None
    wheel: float = 0.0


class ScrollArea:
    """Vertical scrolling region with drag, mouse wheel and inertia."""

    def __init__(self) -> None:
        self.offset = 0.0
        self.velocity = 0.0
        self.content_height = 0.0
        self.view = pygame.Rect(0, 0, 0, 0)
        self.dragging = False
        self._last_y = 0.0

    def max_offset(self) -> float:
        return max(0.0, self.content_height - self.view.height)

    def scroll_to(self, y: float) -> None:
        self.offset = max(0.0, min(self.max_offset(), y))
        self.velocity = 0.0

    def update(self, ui: "UI", view: pygame.Rect, content_height: float, dt: float) -> None:
        self.view = pygame.Rect(view)
        self.content_height = content_height
        p = ui.pointer
        if ui.enabled:
            if p.down and p.down_pos and self.view.collidepoint(p.down_pos):
                if not self.dragging and p.dragged:
                    self.dragging = True
                    self._last_y = p.pos[1]
                if self.dragging:
                    dy = p.pos[1] - self._last_y
                    self._last_y = p.pos[1]
                    self.offset -= dy
                    self.velocity = -dy / max(dt, 1e-3)
            elif self.dragging:
                self.dragging = False
            if p.wheel and self.view.collidepoint(p.pos):
                self.velocity = 0
                self.offset -= p.wheel * 90
        if not self.dragging:
            self.offset += self.velocity * dt
            self.velocity *= max(0.0, 1 - 5 * dt)
            if abs(self.velocity) < 5:
                self.velocity = 0
        # Elastic clamp
        if self.offset < 0:
            self.offset += (0 - self.offset) * min(1.0, dt * 14) if not self.dragging else 0
            if self.dragging:
                self.offset = max(self.offset, -120)
        elif self.offset > self.max_offset():
            mx = self.max_offset()
            self.offset += (mx - self.offset) * min(1.0, dt * 14) if not self.dragging else 0
            if self.dragging:
                self.offset = min(self.offset, mx + 120)


class UI:
    def __init__(self) -> None:
        self.pointer = Pointer()
        self.enabled = True
        self.pressed_id: str | None = None
        self._candidates: list[str] = []
        self.clip: pygame.Rect | None = None
        self.time = 0.0
        self.clicked_sound = None       # callback set by the app (plays click sfx)
        self.hover_cursor = False
        self.consumed = False
        self.deferred_click: str | None = None
        self._deferred_ready = False

    # ------------------------------------------------------------------ frame
    def handle_event(self, event: pygame.event.Event) -> None:
        p = self.pointer
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            p.down = True
            p.down_pos = event.pos
            p.pos = event.pos
            p.dragged = False
            self.pressed_id = None
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            p.pos = event.pos
            p.down = False
            p.released_pos = event.pos
        elif event.type == pygame.MOUSEMOTION:
            p.pos = event.pos
            if p.down and p.down_pos:
                if math.dist(p.pos, p.down_pos) > DRAG_THRESHOLD:
                    p.dragged = True
        elif event.type == pygame.MOUSEWHEEL:
            p.wheel += event.y

    def begin_frame(self, dt: float) -> None:
        self.time += dt
        self._candidates = []
        self.hover_cursor = False
        self.consumed = False

    def end_frame(self) -> None:
        p = self.pointer
        if self._deferred_ready:
            self.deferred_click = None
            self._deferred_ready = False
        if p.down and self.pressed_id is None and self._candidates:
            self.pressed_id = self._candidates[-1]
        if p.released_pos is not None and self.pressed_id is None and self._candidates \
                and not p.dragged:
            # Press and release happened within one frame: deliver the click next frame.
            self.deferred_click = self._candidates[-1]
            self._deferred_ready = True
        if p.released_pos is not None:
            p.released_pos = None
            p.down_pos = None
            self.pressed_id = None
            p.dragged = False
        p.wheel = 0.0

    # ------------------------------------------------------------------ hit testing
    def _inside(self, rect: pygame.Rect, pos) -> bool:
        if pos is None or not rect.collidepoint(pos):
            return False
        return self.clip is None or self.clip.collidepoint(pos)

    def interact(self, uid: str, rect: pygame.Rect) -> tuple[bool, bool, bool]:
        """Returns (hovered, pressed, clicked) for a widget."""
        if not self.enabled:
            return False, False, False
        p = self.pointer
        hovered = self._inside(rect, p.pos)
        if self._inside(rect, p.down_pos) and self.pressed_id is None:
            self._candidates.append(uid)
        pressed = p.down and self.pressed_id == uid and hovered and not p.dragged
        clicked = False
        if self.deferred_click == uid and self._deferred_ready:
            clicked = True
            self.deferred_click = None
            self.consumed = True
            if self.clicked_sound:
                self.clicked_sound()
        elif p.released_pos is not None and self.pressed_id == uid and not p.dragged \
                and self._inside(rect, p.released_pos):
            clicked = True
            self.consumed = True
            if self.clicked_sound:
                self.clicked_sound()
        if hovered:
            self.hover_cursor = True
        return hovered, pressed, clicked

    # ------------------------------------------------------------------ widgets
    def button(self, surface: pygame.Surface, uid: str, rect: pygame.Rect, label: str = "",
               color=theme.GREEN, size: int = 40, icon: str | None = None, icon_size: int | None = None,
               disabled: bool = False, sublabel: str | None = None, text_color=theme.WHITE,
               radius: int = 22) -> bool:
        rect = pygame.Rect(rect)
        if not label and sublabel:
            label, sublabel = sublabel, None
        hovered, pressed, clicked = self.interact(uid, rect)
        surf = glossy_button(rect.size, color, radius, pressed, hovered, disabled)
        surface.blit(surf, (rect.x, rect.y - 8 + (5 if pressed else 0)))
        dy = 4 if pressed else -2
        content_x = rect.centerx
        if icon:
            isz = icon_size or int(rect.height * 0.6)
            ic = icons.icon(icon, isz)
            if label:
                total = isz + 10 + theme.fonts.get(size).size(label)[0]
                ix = rect.centerx - total // 2
                surface.blit(ic, (ix, rect.centery - isz // 2 + dy - (10 if sublabel else 0)))
                content_x = ix + isz + 10 + (total - isz - 10) // 2
            else:
                surface.blit(ic, ic.get_rect(center=(rect.centerx, rect.centery + dy)))
        if label:
            ly = rect.centery + dy - (16 if sublabel else 0)
            draw_text(surface, label, (content_x, ly), size, text_color, anchor="center",
                      outline=3, outline_color=darken(color if not disabled else (120, 128, 145), 0.55),
                      max_width=rect.width - 16)
        if sublabel:
            draw_text(surface, sublabel, (rect.centerx, rect.centery + dy + 22), int(size * 0.8), text_color,
                      anchor="center", outline=3,
                      outline_color=darken(color if not disabled else (120, 128, 145), 0.55),
                      max_width=rect.width - 16)
        return clicked and not disabled

    def icon_button(self, surface: pygame.Surface, uid: str, rect: pygame.Rect, icon: str,
                    label: str | None = None, badge: bool = False, color=theme.NAVY_LIGHT,
                    selected: bool = False, label_size: int = 30) -> bool:
        rect = pygame.Rect(rect)
        hovered, pressed, clicked = self.interact(uid, rect)
        base = theme.BLUE if selected else color
        r = rect.move(0, 3 if pressed else 0)
        panel(surface, r, lighten(base, 0.1) if hovered else base, lighten(base, 0.45), radius=22,
              border=4, shadow=6)
        isz = int(min(r.width, r.height) * (0.52 if label else 0.7))
        ic = icons.icon(icon, isz)
        iy = r.y + (r.height - isz) // 2 - (label_size // 2 if label else 0)
        bounce = int(math.sin(self.time * 6) * 4) if selected else 0
        surface.blit(ic, (r.centerx - isz // 2, iy - bounce))
        if label:
            draw_text(surface, label, (r.centerx, r.bottom - 10), label_size, theme.WHITE,
                      anchor="midbottom", outline=3, max_width=r.width - 6)
        if badge:
            bx, by = r.right - 10, r.y + 10
            pygame.draw.circle(surface, theme.WHITE, (bx, by), 22)
            pygame.draw.circle(surface, theme.RED, (bx, by), 18)
            draw_text(surface, "!", (bx, by + 1), 30, theme.WHITE, anchor="center")
        return clicked

    def tab_bar(self, surface: pygame.Surface, uid: str, rect: pygame.Rect, tabs: list[str],
                selected: int, size: int = 34) -> int:
        rect = pygame.Rect(rect)
        width = rect.width / len(tabs)
        for i, label in enumerate(tabs):
            r = pygame.Rect(rect.x + i * width + 4, rect.y, width - 8, rect.height)
            if self.button(surface, f"{uid}:{i}", r, label, theme.BLUE if i == selected else theme.GREY_DARK,
                           size=size, radius=18):
                selected = i
        return selected

    def slider(self, surface: pygame.Surface, uid: str, rect: pygame.Rect, value: float) -> float:
        rect = pygame.Rect(rect)
        hit = rect.inflate(0, 40)
        hovered, pressed, _ = self.interact(uid, hit)
        p = self.pointer
        if self.enabled and p.down and p.down_pos and hit.collidepoint(p.down_pos):
            value = (p.pos[0] - rect.x) / max(1, rect.width)
            value = max(0.0, min(1.0, value))
        progress_bar(surface, rect, value, theme.CYAN)
        knob_x = rect.x + rect.width * value
        pygame.draw.circle(surface, theme.OUTLINE, (int(knob_x), rect.centery), rect.height)
        pygame.draw.circle(surface, theme.WHITE if not hovered else theme.YELLOW, (int(knob_x), rect.centery),
                           rect.height - 5)
        return value

    def toggle(self, surface: pygame.Surface, uid: str, rect: pygame.Rect, value: bool) -> bool:
        rect = pygame.Rect(rect)
        _, _, clicked = self.interact(uid, rect)
        if clicked:
            value = not value
        color = theme.GREEN if value else theme.GREY_DARK
        surface.blit(gradient_surface(rect.size, lighten(color, 0.2), darken(color, 0.1), rect.height // 2,
                                      4, theme.OUTLINE), rect)
        kx = rect.right - rect.height // 2 if value else rect.x + rect.height // 2
        pygame.draw.circle(surface, theme.WHITE, (kx, rect.centery), rect.height // 2 - 7)
        pygame.draw.circle(surface, theme.OUTLINE, (kx, rect.centery), rect.height // 2 - 7, 3)
        return value

    def region(self, uid: str, rect: pygame.Rect) -> bool:
        """An invisible clickable area."""
        return self.interact(uid, pygame.Rect(rect))[2]

    def set_clip(self, surface: pygame.Surface, rect: pygame.Rect | None) -> None:
        self.clip = pygame.Rect(rect) if rect else None
        surface.set_clip(self.clip)
