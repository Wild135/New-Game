"""Original vector-style icons drawn with pygame primitives (cached).

``icon(name, size)`` returns a transparent Surface.  All icons are drawn at 4x
resolution then smoothly scaled down, which gives clean anti-aliased edges.
"""
from __future__ import annotations

import math

import pygame

from game.rendering.draw import LRU, darken, lighten
from game.ui import theme

_cache = LRU(400)
O = theme.OUTLINE


def _poly(s, color, pts, outline=True, width=10):
    pygame.draw.polygon(s, color, pts)
    if outline:
        pygame.draw.polygon(s, O, pts, width)


def _circle(s, color, c, r, outline=True, width=10):
    pygame.draw.circle(s, color, c, r)
    if outline:
        pygame.draw.circle(s, O, c, r, width)


def _rrect(s, color, rect, radius, outline=True, width=10):
    pygame.draw.rect(s, color, rect, border_radius=radius)
    if outline:
        pygame.draw.rect(s, O, rect, width, border_radius=radius)


def _gear(s, c, r, color, teeth=8):
    cx, cy = c
    pts = []
    for i in range(teeth * 2):
        ang = math.pi * i / teeth
        rad = r if i % 2 == 0 else r * 0.78
        for off in (-0.16, 0.16):
            a = ang + off
            pts.append((cx + math.cos(a) * rad, cy + math.sin(a) * rad))
    _poly(s, color, pts)
    _circle(s, darken(color, 0.35), c, int(r * 0.36))


def _coin(s, size):
    c = (size // 2, size // 2)
    _circle(s, theme.YELLOW_DARK, (c[0], c[1] + 8), size // 2 - 12)
    _circle(s, theme.YELLOW, c, size // 2 - 14)
    _circle(s, lighten(theme.YELLOW, 0.3), c, size // 2 - 50, outline=False)
    pygame.draw.circle(s, theme.YELLOW_DARK, c, size // 2 - 50, 8)
    font = theme.fonts.get(int(size * 0.55))
    t = font.render("$", True, theme.YELLOW_DARK)
    s.blit(t, t.get_rect(center=(c[0], c[1] + 4)))


def _gem(s, size):
    m = size * 0.12
    top = size * 0.25
    pts = [(m + size * 0.18, top), (size - m - size * 0.18, top), (size - m, size * 0.42),
           (size / 2, size - m), (m, size * 0.42)]
    _poly(s, theme.PURPLE, pts)
    pygame.draw.polygon(s, lighten(theme.PURPLE, 0.45), [(m + size * 0.18, top), (size / 2, top),
                                                          (size * 0.4, size * 0.42), (m, size * 0.42)])
    pygame.draw.polygon(s, darken(theme.PURPLE, 0.25), [(size / 2, size - m), (size - m, size * 0.42),
                                                         (size * 0.6, size * 0.42)])
    pygame.draw.polygon(s, O, pts, 10)
    pygame.draw.line(s, O, (m, size * 0.42), (size - m, size * 0.42), 6)


def _ticket(s, size, color=theme.CYAN):
    """Research point icon: a glowing blue data card with a flask."""
    r = pygame.Rect(size * 0.08, size * 0.24, size * 0.84, size * 0.52)
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    _rrect(surf, color, r, 26)
    pygame.draw.rect(surf, lighten(color, 0.4), r.inflate(-50, -50), 6, border_radius=16)
    rotated = pygame.transform.rotate(surf, 25)
    s.blit(rotated, rotated.get_rect(center=(size // 2, size // 2)))
    _flask(s, size, scale=0.5, offset=(0, 0))


def _flask(s, size, scale=1.0, offset=(0, 0), liquid=(160, 90, 255)):
    cx = size / 2 + offset[0]
    cy = size / 2 + offset[1]
    w = size * 0.55 * scale
    h = size * 0.8 * scale
    neck = w * 0.32
    top = cy - h / 2
    pts = [(cx - neck / 2, top), (cx + neck / 2, top), (cx + neck / 2, top + h * 0.35),
           (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2), (cx - neck / 2, top + h * 0.35)]
    _poly(s, (225, 240, 255), pts, width=max(4, int(10 * scale)))
    lpts = [(cx - w * 0.36, cy + h * 0.12), (cx + w * 0.36, cy + h * 0.12),
            (cx + w / 2 - 6, cy + h / 2 - 6), (cx - w / 2 + 6, cy + h / 2 - 6)]
    pygame.draw.polygon(s, liquid, lpts)
    pygame.draw.polygon(s, O, pts, max(4, int(10 * scale)))
    pygame.draw.circle(s, lighten(liquid, 0.5), (int(cx - w * 0.1), int(cy + h * 0.3)), max(3, int(10 * scale)))


def _rocket(s, size, body=(245, 245, 250), accent=theme.RED):
    cx = size / 2
    _poly(s, accent, [(cx - size * 0.3, size * 0.78), (cx - size * 0.12, size * 0.5), (cx - size * 0.12, size * 0.82)])
    _poly(s, accent, [(cx + size * 0.3, size * 0.78), (cx + size * 0.12, size * 0.5), (cx + size * 0.12, size * 0.82)])
    body_pts = [(cx, size * 0.06), (cx + size * 0.16, size * 0.3), (cx + size * 0.15, size * 0.8),
                (cx - size * 0.15, size * 0.8), (cx - size * 0.16, size * 0.3)]
    _poly(s, body, body_pts)
    pygame.draw.polygon(s, accent, [(cx, size * 0.06), (cx + size * 0.12, size * 0.24), (cx - size * 0.12, size * 0.24)])
    pygame.draw.polygon(s, O, body_pts, 10)
    _circle(s, theme.CYAN, (int(cx), int(size * 0.42)), int(size * 0.08))
    _poly(s, theme.ORANGE, [(cx - size * 0.09, size * 0.84), (cx + size * 0.09, size * 0.84), (cx, size * 0.98)], width=6)


def _crate(s, size):
    r = pygame.Rect(size * 0.14, size * 0.2, size * 0.72, size * 0.62)
    _rrect(s, (225, 165, 90), r, 12)
    pygame.draw.line(s, darken((225, 165, 90), 0.3), (r.left + 10, r.centery), (r.right - 10, r.centery), 12)
    pygame.draw.line(s, darken((225, 165, 90), 0.3), (r.centerx, r.top + 10), (r.centerx, r.bottom - 10), 12)
    pygame.draw.rect(s, O, r, 10, border_radius=12)


def _engine(s, size):
    _rrect(s, (190, 195, 210), pygame.Rect(size * 0.3, size * 0.1, size * 0.4, size * 0.3), 10)
    _poly(s, (150, 155, 170), [(size * 0.32, size * 0.4), (size * 0.68, size * 0.4), (size * 0.85, size * 0.85), (size * 0.15, size * 0.85)])
    _poly(s, theme.ORANGE, [(size * 0.25, size * 0.86), (size * 0.75, size * 0.86), (size * 0.5, size * 0.99)], width=6)


def _fuel(s, size):
    r = pygame.Rect(size * 0.25, size * 0.12, size * 0.5, size * 0.78)
    _rrect(s, (90, 200, 240), r, 40)
    pygame.draw.rect(s, lighten((90, 200, 240), 0.5), pygame.Rect(r.x + 18, r.y + 30, 18, r.height - 60), border_radius=8)
    pygame.draw.rect(s, O, r, 10, border_radius=40)
    _rrect(s, (70, 80, 100), pygame.Rect(size * 0.42, size * 0.04, size * 0.16, size * 0.1), 4)


def _chip(s, size):
    r = pygame.Rect(size * 0.22, size * 0.22, size * 0.56, size * 0.56)
    for i in range(4):
        off = size * 0.3 + i * size * 0.13
        for (a, b) in (((off, size * 0.08), (off, size * 0.22)), ((off, size * 0.78), (off, size * 0.92)),
                       ((size * 0.08, off), (size * 0.22, off)), ((size * 0.78, off), (size * 0.92, off))):
            pygame.draw.line(s, (200, 200, 120), a, b, 14)
    _rrect(s, (60, 170, 90), r, 14)
    _rrect(s, (40, 60, 70), r.inflate(-size * 0.22, -size * 0.22), 8)


def _beam(s, size):
    pts = [(size * 0.1, size * 0.3), (size * 0.9, size * 0.3), (size * 0.9, size * 0.42), (size * 0.6, size * 0.42),
           (size * 0.6, size * 0.6), (size * 0.9, size * 0.6), (size * 0.9, size * 0.72), (size * 0.1, size * 0.72),
           (size * 0.1, size * 0.6), (size * 0.4, size * 0.6), (size * 0.4, size * 0.42), (size * 0.1, size * 0.42)]
    _poly(s, (190, 195, 215), pts)


def _crystal(s, size, color=(200, 120, 255)):
    _poly(s, color, [(size * 0.5, size * 0.05), (size * 0.75, size * 0.4), (size * 0.5, size * 0.95), (size * 0.25, size * 0.4)])
    _poly(s, lighten(color, 0.3), [(size * 0.25, size * 0.3), (size * 0.38, size * 0.55), (size * 0.25, size * 0.85), (size * 0.12, size * 0.55)])
    _poly(s, darken(color, 0.1), [(size * 0.75, size * 0.3), (size * 0.88, size * 0.55), (size * 0.75, size * 0.85), (size * 0.62, size * 0.55)])


def _robot(s, size):
    _rrect(s, (170, 180, 220), pygame.Rect(size * 0.22, size * 0.25, size * 0.56, size * 0.45), 24)
    _circle(s, theme.CYAN, (int(size * 0.38), int(size * 0.46)), int(size * 0.07))
    _circle(s, theme.CYAN, (int(size * 0.62), int(size * 0.46)), int(size * 0.07))
    pygame.draw.line(s, O, (size * 0.5, size * 0.25), (size * 0.5, size * 0.1), 10)
    _circle(s, theme.RED, (int(size * 0.5), int(size * 0.1)), int(size * 0.06))
    _rrect(s, (140, 150, 190), pygame.Rect(size * 0.3, size * 0.72, size * 0.4, size * 0.2), 10)


def _flame(s, size):
    pts = [(size * 0.5, size * 0.05), (size * 0.78, size * 0.45), (size * 0.75, size * 0.75), (size * 0.5, size * 0.95),
           (size * 0.25, size * 0.75), (size * 0.22, size * 0.45)]
    _poly(s, theme.ORANGE, pts)
    pygame.draw.polygon(s, theme.YELLOW, [(size * 0.5, size * 0.4), (size * 0.65, size * 0.65), (size * 0.5, size * 0.88), (size * 0.35, size * 0.65)])


def _satellite(s, size):
    _rrect(s, (90, 140, 230), pygame.Rect(size * 0.04, size * 0.38, size * 0.3, size * 0.24), 6)
    _rrect(s, (90, 140, 230), pygame.Rect(size * 0.66, size * 0.38, size * 0.3, size * 0.24), 6)
    _rrect(s, (220, 220, 230), pygame.Rect(size * 0.36, size * 0.3, size * 0.28, size * 0.4), 10)
    pygame.draw.line(s, O, (size * 0.5, size * 0.3), (size * 0.5, size * 0.12), 8)
    _circle(s, theme.YELLOW, (int(size * 0.5), int(size * 0.12)), int(size * 0.05))


def _manager(s, size, skin=(255, 214, 170), shirt=(70, 130, 220), hat=theme.YELLOW):
    _rrect(s, shirt, pygame.Rect(size * 0.2, size * 0.66, size * 0.6, size * 0.34), 30)
    _circle(s, skin, (int(size * 0.5), int(size * 0.5)), int(size * 0.24))
    pygame.draw.circle(s, O, (int(size * 0.42), int(size * 0.52)), int(size * 0.03))
    pygame.draw.circle(s, O, (int(size * 0.58), int(size * 0.52)), int(size * 0.03))
    pygame.draw.arc(s, O, pygame.Rect(size * 0.4, size * 0.52, size * 0.2, size * 0.12), math.pi * 1.1, math.pi * 1.9, 8)
    hat_rect = pygame.Rect(size * 0.24, size * 0.18, size * 0.52, size * 0.28)
    pygame.draw.ellipse(s, hat, hat_rect)
    pygame.draw.rect(s, hat, pygame.Rect(size * 0.2, size * 0.36, size * 0.6, size * 0.08), border_radius=8)
    pygame.draw.ellipse(s, O, hat_rect, 8)
    pygame.draw.rect(s, O, pygame.Rect(size * 0.2, size * 0.36, size * 0.6, size * 0.08), 8, border_radius=8)


def _star(s, size, color=theme.GOLD):
    cx, cy, r = size / 2, size / 2 + 4, size * 0.44
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + math.pi * i / 5
        rad = r if i % 2 == 0 else r * 0.45
        pts.append((cx + math.cos(ang) * rad, cy + math.sin(ang) * rad))
    _poly(s, color, pts)


def _planet(s, size, color=(110, 110, 240)):
    _circle(s, color, (size // 2, size // 2), int(size * 0.3))
    pygame.draw.circle(s, lighten(color, 0.4), (int(size * 0.42), int(size * 0.4)), int(size * 0.08))
    ring = pygame.Rect(size * 0.06, size * 0.4, size * 0.88, size * 0.22)
    pygame.draw.arc(s, theme.YELLOW, ring, math.pi * 0.95, math.pi * 2.05, 16)
    pygame.draw.arc(s, O, ring.inflate(10, 10), math.pi * 0.95, math.pi * 2.05, 6)


def _wrench(s, size):
    pygame.draw.line(s, O, (size * 0.25, size * 0.75), (size * 0.65, size * 0.35), 36)
    pygame.draw.line(s, (200, 205, 220), (size * 0.25, size * 0.75), (size * 0.65, size * 0.35), 20)
    _circle(s, (200, 205, 220), (int(size * 0.7), int(size * 0.3)), int(size * 0.18))
    _circle(s, (0, 0, 0, 0), (int(size * 0.78), int(size * 0.22)), int(size * 0.08), outline=False)
    pygame.draw.circle(s, (0, 0, 0, 0), (int(size * 0.78), int(size * 0.22)), int(size * 0.09))


def _bolt(s, size):
    _poly(s, theme.YELLOW, [(size * 0.55, size * 0.05), (size * 0.2, size * 0.55), (size * 0.45, size * 0.55),
                            (size * 0.35, size * 0.95), (size * 0.8, size * 0.4), (size * 0.55, size * 0.4)])


def _clock(s, size):
    _circle(s, (240, 245, 255), (size // 2, size // 2), int(size * 0.4))
    pygame.draw.line(s, O, (size / 2, size / 2), (size / 2, size * 0.22), 12)
    pygame.draw.line(s, O, (size / 2, size / 2), (size * 0.7, size * 0.6), 12)


def _moon(s, size):
    _circle(s, (240, 230, 160), (size // 2, size // 2), int(size * 0.38))
    pygame.draw.circle(s, (0, 0, 0, 0), (int(size * 0.66), int(size * 0.38)), int(size * 0.3))
    pygame.draw.circle(s, O, (int(size * 0.66), int(size * 0.38)), int(size * 0.3), 8)


def _atom(s, size):
    for ang in (0, 60, 120):
        e = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.ellipse(e, theme.CYAN, pygame.Rect(size * 0.08, size * 0.36, size * 0.84, size * 0.28), 12)
        e = pygame.transform.rotate(e, ang)
        s.blit(e, e.get_rect(center=(size // 2, size // 2)))
    _circle(s, theme.PURPLE, (size // 2, size // 2), int(size * 0.1))


def _settings(s, size):
    _gear(s, (size // 2, size // 2), int(size * 0.4), (220, 230, 245), teeth=8)


def _check(s, size, color=theme.GREEN):
    pygame.draw.lines(s, O, False, [(size * 0.18, size * 0.52), (size * 0.42, size * 0.76), (size * 0.84, size * 0.26)], 34)
    pygame.draw.lines(s, color, False, [(size * 0.18, size * 0.52), (size * 0.42, size * 0.76), (size * 0.84, size * 0.26)], 18)


def _lock(s, size):
    pygame.draw.arc(s, O, pygame.Rect(size * 0.28, size * 0.12, size * 0.44, size * 0.5), 0, math.pi, 26)
    pygame.draw.arc(s, (200, 205, 220), pygame.Rect(size * 0.28, size * 0.12, size * 0.44, size * 0.5), 0, math.pi, 14)
    _rrect(s, theme.YELLOW, pygame.Rect(size * 0.2, size * 0.4, size * 0.6, size * 0.48), 14)
    _circle(s, O, (size // 2, int(size * 0.6)), int(size * 0.06), outline=False)


def _plus(s, size):
    pygame.draw.rect(s, theme.WHITE, pygame.Rect(size * 0.4, size * 0.16, size * 0.2, size * 0.68), border_radius=10)
    pygame.draw.rect(s, theme.WHITE, pygame.Rect(size * 0.16, size * 0.4, size * 0.68, size * 0.2), border_radius=10)


def _arrow_up(s, size, color=theme.GREEN_LIGHT):
    _poly(s, color, [(size * 0.5, size * 0.08), (size * 0.88, size * 0.5), (size * 0.64, size * 0.5), (size * 0.64, size * 0.92),
                     (size * 0.36, size * 0.92), (size * 0.36, size * 0.5), (size * 0.12, size * 0.5)])


def _gift(s, size):
    _rrect(s, theme.RED, pygame.Rect(size * 0.14, size * 0.42, size * 0.72, size * 0.5), 10)
    _rrect(s, lighten(theme.RED, 0.15), pygame.Rect(size * 0.08, size * 0.3, size * 0.84, size * 0.16), 8)
    pygame.draw.rect(s, theme.YELLOW, pygame.Rect(size * 0.44, size * 0.3, size * 0.12, size * 0.62))
    pygame.draw.ellipse(s, theme.YELLOW, pygame.Rect(size * 0.22, size * 0.1, size * 0.28, size * 0.22), 14)
    pygame.draw.ellipse(s, theme.YELLOW, pygame.Rect(size * 0.5, size * 0.1, size * 0.28, size * 0.22), 14)


def _calendar(s, size):
    r = pygame.Rect(size * 0.12, size * 0.16, size * 0.76, size * 0.72)
    _rrect(s, theme.WHITE, r, 16)
    pygame.draw.rect(s, theme.RED, pygame.Rect(r.x + 5, r.y + 5, r.width - 10, size * 0.18), border_top_left_radius=12, border_top_right_radius=12)
    pygame.draw.rect(s, O, r, 10, border_radius=16)
    font = theme.fonts.get(int(size * 0.42))
    t = font.render("7", True, (40, 50, 80))
    s.blit(t, t.get_rect(center=(size // 2, int(size * 0.6))))


def _clipboard(s, size):
    r = pygame.Rect(size * 0.18, size * 0.12, size * 0.64, size * 0.8)
    _rrect(s, (210, 160, 100), r, 12)
    _rrect(s, theme.WHITE, r.inflate(-size * 0.12, -size * 0.14).move(0, 6), 6, outline=False)
    _rrect(s, (150, 160, 180), pygame.Rect(size * 0.36, size * 0.06, size * 0.28, size * 0.12), 6)
    _check(s, size)


def _cart(s, size):
    pygame.draw.lines(s, O, False, [(size * 0.05, size * 0.2), (size * 0.2, size * 0.2), (size * 0.32, size * 0.66), (size * 0.82, size * 0.66)], 14)
    _poly(s, theme.YELLOW, [(size * 0.22, size * 0.3), (size * 0.92, size * 0.3), (size * 0.82, size * 0.6), (size * 0.3, size * 0.6)])
    _circle(s, (60, 60, 70), (int(size * 0.38), int(size * 0.8)), int(size * 0.08))
    _circle(s, (60, 60, 70), (int(size * 0.76), int(size * 0.8)), int(size * 0.08))


def _map_pin(s, size):
    _planet(s, size, color=(80, 200, 120))
    pts = [(size * 0.5, size * 0.6), (size * 0.32, size * 0.3), (size * 0.5, size * 0.08), (size * 0.68, size * 0.3)]
    _poly(s, theme.RED, pts)
    _circle(s, theme.WHITE, (size // 2, int(size * 0.28)), int(size * 0.07))


def _trophy(s, size):
    _poly(s, theme.GOLD, [(size * 0.25, size * 0.12), (size * 0.75, size * 0.12), (size * 0.68, size * 0.5), (size * 0.32, size * 0.5)])
    pygame.draw.arc(s, O, pygame.Rect(size * 0.08, size * 0.16, size * 0.3, size * 0.3), math.pi * 0.5, math.pi * 1.5, 10)
    pygame.draw.arc(s, O, pygame.Rect(size * 0.62, size * 0.16, size * 0.3, size * 0.3), -math.pi * 0.5, math.pi * 0.5, 10)
    _rrect(s, theme.GOLD, pygame.Rect(size * 0.44, size * 0.5, size * 0.12, size * 0.2), 4)
    _rrect(s, (150, 100, 60), pygame.Rect(size * 0.28, size * 0.7, size * 0.44, size * 0.16), 6)


def _chart(s, size):
    for i, h in enumerate((0.3, 0.5, 0.75)):
        r = pygame.Rect(size * (0.14 + i * 0.26), size * (0.86 - h), size * 0.2, size * h)
        _rrect(s, (theme.CYAN, theme.GREEN, theme.YELLOW)[i], r, 6)


def _sound(s, size, muted=False):
    _poly(s, theme.WHITE, [(size * 0.12, size * 0.38), (size * 0.3, size * 0.38), (size * 0.52, size * 0.18),
                           (size * 0.52, size * 0.82), (size * 0.3, size * 0.62), (size * 0.12, size * 0.62)])
    if muted:
        pygame.draw.line(s, theme.RED, (size * 0.62, size * 0.3), (size * 0.9, size * 0.7), 14)
        pygame.draw.line(s, theme.RED, (size * 0.9, size * 0.3), (size * 0.62, size * 0.7), 14)
    else:
        pygame.draw.arc(s, theme.WHITE, pygame.Rect(size * 0.45, size * 0.3, size * 0.3, size * 0.4), -1.0, 1.0, 10)
        pygame.draw.arc(s, theme.WHITE, pygame.Rect(size * 0.45, size * 0.18, size * 0.45, size * 0.64), -1.0, 1.0, 10)


def _question(s, size):
    _circle(s, theme.BLUE, (size // 2, size // 2), int(size * 0.42))
    font = theme.fonts.get(int(size * 0.6))
    t = font.render("?", True, theme.WHITE)
    s.blit(t, t.get_rect(center=(size // 2, size // 2 + 4)))


def _home(s, size):
    _poly(s, (230, 235, 245), [(size * 0.5, size * 0.12), (size * 0.9, size * 0.48), (size * 0.78, size * 0.48),
                                (size * 0.78, size * 0.88), (size * 0.22, size * 0.88), (size * 0.22, size * 0.48), (size * 0.1, size * 0.48)])


def _close(s, size):
    pygame.draw.line(s, O, (size * 0.24, size * 0.24), (size * 0.76, size * 0.76), 34)
    pygame.draw.line(s, O, (size * 0.76, size * 0.24), (size * 0.24, size * 0.76), 34)
    pygame.draw.line(s, theme.WHITE, (size * 0.24, size * 0.24), (size * 0.76, size * 0.76), 18)
    pygame.draw.line(s, theme.WHITE, (size * 0.76, size * 0.24), (size * 0.24, size * 0.76), 18)


def _paint(s, size):
    _rrect(s, (210, 210, 220), pygame.Rect(size * 0.2, size * 0.3, size * 0.6, size * 0.6), 16)
    _rrect(s, theme.RED, pygame.Rect(size * 0.2, size * 0.3, size * 0.6, size * 0.2), 10)
    pygame.draw.circle(s, theme.RED, (int(size * 0.7), int(size * 0.62)), int(size * 0.06))


def _coin_stack(s, size):
    for i in range(3):
        y = size * (0.62 - i * 0.16)
        _rrect(s, theme.YELLOW, pygame.Rect(size * 0.2, y, size * 0.6, size * 0.2), 30)


DRAWERS = {
    "coin": _coin, "gem": _gem, "rp": _ticket, "flask": lambda s, z: _flask(s, z), "rocket": _rocket,
    "crate": _crate, "engine": _engine, "fuel": _fuel, "chip": _chip, "beam": _beam, "crystal": _crystal,
    "robot": _robot, "flame": _flame, "satellite": _satellite, "manager": _manager, "star": _star,
    "planet": _planet, "wrench": _wrench, "bolt": _bolt, "clock": _clock, "moon": _moon, "atom": _atom,
    "settings": _settings, "check": _check, "lock": _lock, "plus": _plus, "arrow_up": _arrow_up,
    "gift": _gift, "calendar": _calendar, "clipboard": _clipboard, "cart": _cart, "map": _map_pin,
    "trophy": _trophy, "chart": _chart, "sound": _sound, "muted": lambda s, z: _sound(s, z, True),
    "question": _question, "home": _home, "close": _close, "paint": _paint, "coins": _coin_stack,
    "gear": lambda s, z: _gear(s, (z // 2, z // 2), int(z * 0.42), (190, 200, 220)),
}


def icon(name: str, size: int) -> pygame.Surface:
    key = (name, size)
    surf = _cache.fetch(key)
    if surf is not None:
        return surf
    big = 256
    canvas = pygame.Surface((big, big), pygame.SRCALPHA)
    drawer = DRAWERS.get(name, DRAWERS["gear"])
    drawer(canvas, big)
    surf = pygame.transform.smoothscale(canvas, (size, size))
    return _cache.store(key, surf)


def manager_portrait(look: dict, size: int, hat=theme.YELLOW, bg=None) -> pygame.Surface:
    key = ("mgr", tuple(look["skin"]), tuple(look["hair"]), tuple(look["shirt"]), size, tuple(hat), bg)
    surf = _cache.fetch(key)
    if surf is not None:
        return surf
    big = 256
    s = pygame.Surface((big, big), pygame.SRCALPHA)
    if bg:
        pygame.draw.circle(s, bg, (128, 128), 124)
    skin, hair, shirt = look["skin"], look["hair"], look["shirt"]
    pygame.draw.ellipse(s, shirt, pygame.Rect(40, 170, 176, 120))
    pygame.draw.ellipse(s, O, pygame.Rect(40, 170, 176, 120), 8)
    pygame.draw.polygon(s, theme.WHITE, [(108, 175), (148, 175), (128, 210)])
    pygame.draw.circle(s, hair, (128, 120), 70)
    pygame.draw.circle(s, skin, (128, 128), 62)
    pygame.draw.circle(s, O, (128, 128), 62, 7)
    pygame.draw.circle(s, O, (106, 132), 8)
    pygame.draw.circle(s, O, (150, 132), 8)
    pygame.draw.circle(s, theme.WHITE, (109, 129), 3)
    pygame.draw.circle(s, theme.WHITE, (153, 129), 3)
    pygame.draw.circle(s, (255, 150, 140), (94, 152), 9)
    pygame.draw.circle(s, (255, 150, 140), (162, 152), 9)
    pygame.draw.arc(s, O, pygame.Rect(110, 140, 36, 26), math.pi * 1.15, math.pi * 1.85, 6)
    hat_rect = pygame.Rect(60, 52, 136, 76)
    pygame.draw.ellipse(s, hat, hat_rect)
    pygame.draw.rect(s, hat, pygame.Rect(50, 100, 156, 22), border_radius=10)
    pygame.draw.rect(s, lighten(hat, 0.3), pygame.Rect(118, 56, 20, 50), border_radius=8)
    pygame.draw.ellipse(s, O, hat_rect, 7)
    pygame.draw.rect(s, O, pygame.Rect(50, 100, 156, 22), 7, border_radius=10)
    surf = pygame.transform.smoothscale(s, (size, size))
    return _cache.store(key, surf)
