"""Low level drawing helpers with caching.

Pygame redraws everything every frame, so anything expensive (gradients,
outlined text, glossy buttons) is rendered once and cached as a Surface.
"""
from __future__ import annotations

import math
from collections import OrderedDict
from typing import Sequence

import pygame

from game.ui import theme

Color = Sequence[int]


class LRU(OrderedDict):
    def __init__(self, limit: int):
        super().__init__()
        self.limit = limit

    def fetch(self, key):
        value = self.get(key)
        if value is not None:
            self.move_to_end(key)
        return value

    def store(self, key, value):
        self[key] = value
        if len(self) > self.limit:
            self.popitem(last=False)
        return value


_text_cache = LRU(1500)
_shape_cache = LRU(600)


def clear_caches() -> None:
    _text_cache.clear()
    _shape_cache.clear()


def lighten(color: Color, amount: float) -> tuple[int, int, int]:
    return tuple(min(255, int(c + (255 - c) * amount)) for c in color[:3])  # type: ignore


def darken(color: Color, amount: float) -> tuple[int, int, int]:
    return tuple(max(0, int(c * (1 - amount))) for c in color[:3])  # type: ignore


def mix(a: Color, b: Color, t: float) -> tuple[int, int, int]:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore


# ---------------------------------------------------------------- text
def text_surface(text: str, size: int, color: Color = theme.WHITE, kind: str = "title",
                 outline: int = 0, outline_color: Color = theme.OUTLINE,
                 shadow: bool = False) -> pygame.Surface:
    key = (text, size, tuple(color), kind, outline, tuple(outline_color), shadow)
    surf = _text_cache.fetch(key)
    if surf is not None:
        return surf
    font = theme.fonts.get(size, kind)
    base = font.render(text, True, color)
    if outline <= 0 and not shadow:
        return _text_cache.store(key, base)
    pad = outline + (4 if shadow else 0)
    w, h = base.get_width() + pad * 2, base.get_height() + pad * 2
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    if outline > 0:
        edge = font.render(text, True, outline_color)
        steps = max(8, outline * 6)
        for i in range(steps):
            ang = 2 * math.pi * i / steps
            surf.blit(edge, (pad + round(math.cos(ang) * outline), pad + round(math.sin(ang) * outline)))
        if shadow:
            for dy in range(1, 5):
                surf.blit(edge, (pad, pad + outline // 2 + dy))
    elif shadow:
        shade = font.render(text, True, (0, 0, 0))
        shade.set_alpha(110)
        surf.blit(shade, (pad + 2, pad + 3))
    surf.blit(base, (pad, pad))
    return _text_cache.store(key, surf)


def draw_text(surface: pygame.Surface, text: str, pos: tuple[float, float], size: int,
              color: Color = theme.WHITE, anchor: str = "topleft", kind: str = "title",
              outline: int = 0, outline_color: Color = theme.OUTLINE, shadow: bool = False,
              max_width: int | None = None) -> pygame.Rect:
    surf = text_surface(text, size, color, kind, outline, outline_color, shadow)
    if max_width and surf.get_width() > max_width and size > 12:
        # Shrink until it fits (cheap thanks to caching).
        return draw_text(surface, text, pos, size - 2, color, anchor, kind, outline,
                         outline_color, shadow, max_width)
    rect = surf.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    surface.blit(surf, rect)
    return rect


def wrap_text(text: str, size: int, width: int, kind: str = "body") -> list[str]:
    font = theme.fonts.get(size, kind)
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        current = ""
        for word in words:
            trial = (current + " " + word).strip()
            if font.size(trial)[0] <= width or not current:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def draw_paragraph(surface: pygame.Surface, text: str, rect: pygame.Rect, size: int,
                   color: Color = theme.OFF_WHITE, kind: str = "body", align: str = "left",
                   line_gap: int = 4) -> int:
    """Draw wrapped text inside rect; returns the height used."""
    y = rect.top
    for line in wrap_text(text, size, rect.width, kind):
        surf = text_surface(line, size, color, kind)
        if align == "center":
            surface.blit(surf, surf.get_rect(midtop=(rect.centerx, y)))
        else:
            surface.blit(surf, (rect.left, y))
        y += surf.get_height() + line_gap
    return y - rect.top


# ---------------------------------------------------------------- shapes
def gradient_surface(size: tuple[int, int], top: Color, bottom: Color, radius: int = 0,
                     border: int = 0, border_color: Color = (0, 0, 0)) -> pygame.Surface:
    w, h = max(1, int(size[0])), max(1, int(size[1]))
    key = ("grad", w, h, tuple(top), tuple(bottom), radius, border, tuple(border_color))
    surf = _shape_cache.fetch(key)
    if surf is not None:
        return surf
    column = pygame.Surface((1, h))
    for y in range(h):
        column.set_at((0, y), mix(top, bottom, y / max(1, h - 1)))
    grad = pygame.transform.scale(column, (w, h)).convert_alpha() if pygame.display.get_init() \
        and pygame.display.get_surface() else pygame.transform.scale(column, (w, h))
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    if radius > 0:
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
        surf.blit(grad, (0, 0))
        surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    else:
        surf.blit(grad, (0, 0))
    if border > 0:
        pygame.draw.rect(surf, border_color, surf.get_rect(), border, border_radius=radius)
    return _shape_cache.store(key, surf)


def panel(surface: pygame.Surface, rect: pygame.Rect, color: Color = theme.PANEL,
          border_color: Color = theme.PANEL_BORDER, radius: int = 24, border: int = 4,
          shadow: int = 8, gradient: bool = True, alpha: int = 255) -> None:
    rect = pygame.Rect(rect)
    if shadow:
        shade = _shadow(rect.size, radius)
        surface.blit(shade, (rect.x, rect.y + shadow))
    if gradient:
        surf = gradient_surface(rect.size, lighten(color, 0.12), darken(color, 0.12), radius, border, border_color)
    else:
        surf = gradient_surface(rect.size, color, color, radius, border, border_color)
    if alpha < 255:
        surf = surf.copy()
        surf.set_alpha(alpha)
    surface.blit(surf, rect)


def _shadow(size: tuple[int, int], radius: int, alpha: int = 90) -> pygame.Surface:
    key = ("shadow", size, radius, alpha)
    surf = _shape_cache.fetch(key)
    if surf is None:
        surf = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.rect(surf, (0, 0, 20, alpha), surf.get_rect(), border_radius=radius)
        _shape_cache.store(key, surf)
    return surf


def glossy_button(size: tuple[int, int], color: Color, radius: int = 22, pressed: bool = False,
                  hover: bool = False, disabled: bool = False) -> pygame.Surface:
    """A cartoon button: gradient face, darker 'lip' at the bottom and a shine."""
    w, h = int(size[0]), int(size[1])
    key = ("btn", w, h, tuple(color), radius, pressed, hover, disabled)
    surf = _shape_cache.fetch(key)
    if surf is not None:
        return surf
    if disabled:
        color = (120, 128, 145)
    if hover and not disabled:
        color = lighten(color, 0.12)
    lip = 8 if not pressed else 3
    surf = pygame.Surface((w, h + 8), pygame.SRCALPHA)
    pygame.draw.rect(surf, (0, 0, 20, 80), pygame.Rect(0, 8, w, h), border_radius=radius)
    base_y = 8 - lip
    pygame.draw.rect(surf, darken(color, 0.45), pygame.Rect(0, base_y + lip, w, h - lip + 0),
                     border_radius=radius)
    face_rect = pygame.Rect(0, 8 - lip + (0 if not pressed else 5), w, h - 6)
    face = gradient_surface(face_rect.size, lighten(color, 0.25), darken(color, 0.1), radius,
                            3, darken(color, 0.5))
    surf.blit(face, face_rect)
    shine = pygame.Surface((w - radius, max(4, h // 4)), pygame.SRCALPHA)
    pygame.draw.rect(shine, (255, 255, 255, 70), shine.get_rect(), border_radius=max(2, h // 8))
    surf.blit(shine, (radius // 2, face_rect.y + 6))
    return _shape_cache.store(key, surf)


def circle_surface(radius: int, color: Color, alpha: int = 255) -> pygame.Surface:
    key = ("circle", radius, tuple(color), alpha)
    surf = _shape_cache.fetch(key)
    if surf is None:
        surf = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*color[:3], alpha), (radius + 1, radius + 1), radius)
        _shape_cache.store(key, surf)
    return surf


def soft_glow(radius: int, color: Color, strength: int = 120) -> pygame.Surface:
    key = ("glow", radius, tuple(color), strength)
    surf = _shape_cache.fetch(key)
    if surf is None:
        surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        for r in range(radius, 0, -max(1, radius // 12)):
            a = int(strength * (1 - r / radius) ** 1.5)
            pygame.draw.circle(surf, (*color[:3], a), (radius, radius), r)
        _shape_cache.store(key, surf)
    return surf


def progress_bar(surface: pygame.Surface, rect: pygame.Rect, fraction: float,
                 color: Color = theme.GREEN, back: Color = (14, 24, 50), border: Color = (8, 14, 30),
                 radius: int | None = None) -> None:
    rect = pygame.Rect(rect)
    radius = rect.height // 2 if radius is None else radius
    pygame.draw.rect(surface, back, rect, border_radius=radius)
    fraction = max(0.0, min(1.0, fraction))
    if fraction > 0:
        inner = rect.inflate(-6, -6)
        fill = pygame.Rect(inner.x, inner.y, max(inner.height, int(inner.width * fraction)), inner.height)
        surface.blit(gradient_surface(fill.size, lighten(color, 0.3), darken(color, 0.15),
                                      fill.height // 2), fill)
    pygame.draw.rect(surface, border, rect, 3, border_radius=radius)


def overlay(size: tuple[int, int], color: Color) -> pygame.Surface:
    """A cached translucent rectangle (dim layers, shades).  Never allocate these per frame."""
    key = ("overlay", tuple(size), tuple(color))
    surf = _shape_cache.fetch(key)
    if surf is None:
        surf = pygame.Surface(size, pygame.SRCALPHA)
        surf.fill(color)
        surf = _shape_cache.store(key, _fast(surf))
    return surf


def dim_except(surface: pygame.Surface, color: Color, hole: pygame.Rect | None = None) -> None:
    """Dim the whole screen, optionally leaving a rectangular hole uncovered."""
    w, h = surface.get_size()
    dim = overlay((w, h), color)
    if hole is None:
        surface.blit(dim, (0, 0))
        return
    hole = hole.clip(pygame.Rect(0, 0, w, h))
    for area in (pygame.Rect(0, 0, w, hole.top), pygame.Rect(0, hole.bottom, w, h - hole.bottom),
                 pygame.Rect(0, hole.top, hole.left, hole.height),
                 pygame.Rect(hole.right, hole.top, w - hole.right, hole.height)):
        if area.width > 0 and area.height > 0:
            surface.blit(dim, area.topleft, area)


def _fast(surf: pygame.Surface) -> pygame.Surface:
    """Convert to the display's pixel format (much faster to blit) when a window exists."""
    if pygame.display.get_init() and pygame.display.get_surface() is not None:
        try:
            return surf.convert_alpha() if surf.get_flags() & pygame.SRCALPHA else surf.convert()
        except pygame.error:
            return surf
    return surf


def rotated(surface: pygame.Surface, angle: float) -> pygame.Surface:
    return pygame.transform.rotozoom(surface, angle, 1.0)
