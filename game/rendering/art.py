"""Procedurally drawn cartoon artwork (all original).

Everything is drawn with pygame primitives at 2x size and smooth-scaled down
for clean edges, then cached so it is only drawn once.
"""
from __future__ import annotations

import math
import random

import pygame

from game.rendering import icons
from game.rendering.draw import LRU, _fast, darken, gradient_surface, lighten, mix, text_surface
from game.ui import theme

O = theme.OUTLINE
_cache = LRU(300)


def _cached(key, builder):
    surf = _cache.fetch(key)
    if surf is None:
        surf = _cache.store(key, _fast(builder()))
    return surf


# ===================================================================== rockets
def rocket_sprite(height: int, body=(245, 245, 250), accent=(225, 60, 60), fins: int = 3,
                  decal: str = "decal_none", width_ratio: float = 0.34) -> pygame.Surface:
    key = ("rocket", height, tuple(body), tuple(accent), fins, decal, width_ratio)
    return _cached(key, lambda: _draw_rocket(height, body, accent, fins, decal, width_ratio))


def _draw_rocket(height, body, accent, fins, decal, width_ratio):
    S = 2
    H = height * S
    W = int(H * width_ratio)
    fin_w = int(W * 0.55)
    total_w = W + fin_w * 2
    surf = pygame.Surface((total_w, H), pygame.SRCALPHA)
    cx = total_w // 2
    body_top = int(H * 0.05)
    body_bottom = int(H * 0.86)
    lw = max(4, H // 90)
    # Fins (behind body)
    fin_top = int(H * 0.58)
    for side in (-1, 1):
        pts = [(cx + side * W * 0.42, fin_top), (cx + side * (W * 0.5 + fin_w), body_bottom + H * 0.05),
               (cx + side * (W * 0.5 + fin_w * 0.75), body_bottom + H * 0.09), (cx + side * W * 0.4, body_bottom)]
        pygame.draw.polygon(surf, accent, pts)
        pygame.draw.polygon(surf, darken(accent, 0.25), [pts[0], pts[1], (cx + side * W * 0.5, fin_top + H * 0.12)])
        pygame.draw.polygon(surf, O, pts, lw)
    # Nozzle
    nozzle = [(cx - W * 0.28, body_bottom - 4), (cx + W * 0.28, body_bottom - 4), (cx + W * 0.38, H * 0.97),
              (cx - W * 0.38, H * 0.97)]
    pygame.draw.polygon(surf, (110, 115, 130), nozzle)
    pygame.draw.polygon(surf, (150, 155, 170), [nozzle[0], (cx, body_bottom - 4), (cx - W * 0.1, H * 0.97), nozzle[3]])
    pygame.draw.polygon(surf, O, nozzle, lw)
    # Body: a capsule shape (cylinder + ogive nose)
    nose_h = int(H * 0.27)
    body_rect = pygame.Rect(cx - W // 2, body_top + nose_h - W // 4, W, body_bottom - body_top - nose_h + W // 4)
    pygame.draw.rect(surf, body, body_rect, border_radius=W // 3)
    nose_pts = []
    for i in range(25):
        t = i / 24
        y = body_top + nose_h * t
        half = (W / 2) * math.sin(t * math.pi / 2) ** 0.8
        nose_pts.append((cx + half, y))
    nose_pts = nose_pts + [(cx - x + cx - cx, y) for (x, y) in []]
    left = [(2 * cx - x, y) for (x, y) in reversed(nose_pts)]
    nose_poly = nose_pts + [(cx + W / 2, body_top + nose_h + 4), (cx - W / 2, body_top + nose_h + 4)] + left
    pygame.draw.polygon(surf, accent, nose_poly)
    # Shading stripes on the body
    shade = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    pygame.draw.rect(shade, (*darken(body, 0.18), 255),
                     pygame.Rect(cx + W * 0.18, body_rect.top + 10, W * 0.3, body_rect.height - 20), border_radius=W // 4)
    pygame.draw.rect(shade, (255, 255, 255, 140),
                     pygame.Rect(cx - W * 0.36, body_rect.top + 30, W * 0.12, body_rect.height - 60), border_radius=W // 8)
    surf.blit(shade, (0, 0))
    # Bands
    band_y = int(body_top + nose_h + (body_bottom - body_top - nose_h) * 0.62)
    pygame.draw.rect(surf, accent, pygame.Rect(cx - W // 2, band_y, W, int(H * 0.05)))
    pygame.draw.rect(surf, darken(body, 0.35), pygame.Rect(cx - W // 2, body_top + nose_h, W, lw))
    # Decals
    if decal == "decal_stars":
        for (dx, dy) in ((-0.15, 0.48), (0.12, 0.56), (-0.05, 0.68)):
            st = icons.icon("star", int(W * 0.22))
            surf.blit(st, st.get_rect(center=(cx + W * dx, H * dy)))
    elif decal == "decal_stripes":
        for off in (-0.12, 0.08):
            pygame.draw.rect(surf, accent, pygame.Rect(cx + W * off, body_top + nose_h + 8, W * 0.06, band_y - body_top - nose_h - 8))
    elif decal == "decal_bolt":
        b = icons.icon("bolt", int(W * 0.5))
        surf.blit(b, b.get_rect(center=(cx, int(H * 0.56))))
    # Window
    wr = int(W * 0.24)
    wy = int(body_top + nose_h + wr * 1.4)
    pygame.draw.circle(surf, (180, 190, 210), (cx, wy), wr + lw * 2)
    pygame.draw.circle(surf, (60, 160, 240), (cx, wy), wr)
    pygame.draw.circle(surf, (150, 220, 255), (cx - wr // 3, wy - wr // 3), wr // 3)
    pygame.draw.circle(surf, O, (cx, wy), wr + lw * 2, lw)
    # Outlines
    pygame.draw.rect(surf, O, body_rect, lw, border_radius=W // 3)
    pygame.draw.lines(surf, O, False, nose_poly[:25], lw)
    pygame.draw.lines(surf, O, False, left, lw)
    if fins >= 4:
        mid = [(cx - W * 0.07, fin_top + H * 0.08), (cx + W * 0.07, fin_top + H * 0.08), (cx + W * 0.08, body_bottom + H * 0.08),
               (cx - W * 0.08, body_bottom + H * 0.08)]
        pygame.draw.polygon(surf, darken(accent, 0.1), mid)
        pygame.draw.polygon(surf, O, mid, lw)
    return pygame.transform.smoothscale(surf, (total_w // S, H // S))


# ===================================================================== workers
WORKER_W, WORKER_H = 84, 124


def worker_frame(state: str, frame: int, hat=theme.YELLOW, flip: bool = False,
                 skin=(255, 214, 170), coat=(245, 245, 250)) -> pygame.Surface:
    key = ("worker", state, frame, tuple(hat), flip, tuple(skin), tuple(coat))

    def build():
        surf = _draw_worker(state, frame / 8.0, hat, skin, coat)
        return pygame.transform.flip(surf, True, False) if flip else surf
    return _cached(key, build)


def _draw_worker(state: str, t: float, hat, skin, coat) -> pygame.Surface:
    S = 2
    w, h = WORKER_W * S, WORKER_H * S
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w // 2
    lw = 5
    ang = t * 2 * math.pi
    bob = 0
    leg_a = leg_b = 0.0
    arm_l = arm_r = 0.3
    carry = state == "carry"
    if state in ("walk", "carry"):
        leg_a = math.sin(ang) * 0.5
        leg_b = -leg_a
        bob = abs(math.sin(ang)) * 6
        arm_l, arm_r = 0.3 + math.sin(ang) * 0.5, 0.3 - math.sin(ang) * 0.5
    elif state == "work":
        arm_r = -0.9 + math.sin(ang) * 0.6
        arm_l = 0.2
        bob = abs(math.sin(ang)) * 3
    elif state == "celebrate":
        arm_l = arm_r = -2.4 + math.sin(ang) * 0.3
        bob = -abs(math.sin(ang)) * 22
    elif state == "inspect":
        arm_r = -0.5
        arm_l = -0.6
        bob = math.sin(ang) * 2
    else:  # idle
        bob = math.sin(ang) * 3
    base_y = h - 18 + bob
    hip_y = base_y - 56
    # Legs
    for i, la in enumerate((leg_a, leg_b)):
        hx = cx - 14 + i * 28
        fx = hx + math.sin(la) * 36
        fy = base_y
        pygame.draw.line(s, (60, 80, 140), (hx, hip_y), (fx, fy - 6), 20)
        pygame.draw.ellipse(s, (60, 50, 50), pygame.Rect(fx - 16, fy - 14, 34, 18))
    # Body (coat)
    body = pygame.Rect(cx - 36, hip_y - 66, 72, 84)
    pygame.draw.rect(s, coat, body, border_radius=26)
    pygame.draw.rect(s, (60, 120, 220), pygame.Rect(cx - 30, hip_y - 6, 60, 18), border_radius=8)
    pygame.draw.line(s, darken(coat, 0.2), (cx, body.top + 10), (cx, body.bottom - 10), 3)
    pygame.draw.rect(s, O, body, lw, border_radius=26)
    # Arms
    shoulder_y = body.top + 18
    for side, a in ((-1, arm_l), (1, arm_r)):
        sx = cx + side * 32
        ex = sx + side * math.sin(a + 0.2) * 40
        ey = shoulder_y + math.cos(a + 0.2) * 40
        if carry:
            ex, ey = cx + side * 26, shoulder_y + 26
        pygame.draw.line(s, O, (sx, shoulder_y), (ex, ey), 22)
        pygame.draw.line(s, coat, (sx, shoulder_y), (ex, ey), 14)
        pygame.draw.circle(s, skin, (int(ex), int(ey)), 10)
        pygame.draw.circle(s, O, (int(ex), int(ey)), 10, 4)
    if carry:
        box = pygame.Rect(cx - 30, shoulder_y + 4, 60, 44)
        pygame.draw.rect(s, (225, 165, 90), box, border_radius=6)
        pygame.draw.line(s, darken((225, 165, 90), 0.3), (box.left + 6, box.centery), (box.right - 6, box.centery), 5)
        pygame.draw.rect(s, O, box, lw, border_radius=6)
    if state == "inspect":
        clip = pygame.Rect(cx - 6, shoulder_y + 6, 40, 50)
        pygame.draw.rect(s, (210, 160, 100), clip, border_radius=4)
        pygame.draw.rect(s, theme.WHITE, clip.inflate(-10, -12), border_radius=3)
        pygame.draw.rect(s, O, clip, 4, border_radius=4)
    # Head
    head_c = (cx, body.top - 34)
    pygame.draw.circle(s, skin, head_c, 42)
    pygame.draw.circle(s, O, head_c, 42, lw)
    blink = state == "idle" and t > 0.9
    for side in (-1, 1):
        ex = head_c[0] + side * 15
        if blink:
            pygame.draw.line(s, O, (ex - 6, head_c[1] + 6), (ex + 6, head_c[1] + 6), 4)
        else:
            pygame.draw.circle(s, O, (ex, head_c[1] + 6), 6)
            pygame.draw.circle(s, theme.WHITE, (ex + 2, head_c[1] + 3), 2)
    pygame.draw.circle(s, (255, 150, 140), (head_c[0] - 26, head_c[1] + 18), 7)
    pygame.draw.circle(s, (255, 150, 140), (head_c[0] + 26, head_c[1] + 18), 7)
    if state == "celebrate":
        pygame.draw.ellipse(s, O, pygame.Rect(head_c[0] - 10, head_c[1] + 16, 20, 16))
    else:
        pygame.draw.arc(s, O, pygame.Rect(head_c[0] - 10, head_c[1] + 10, 20, 14), math.pi * 1.1, math.pi * 1.9, 4)
    # Hard hat
    hat_rect = pygame.Rect(head_c[0] - 40, head_c[1] - 52, 80, 56)
    pygame.draw.ellipse(s, hat, hat_rect)
    pygame.draw.rect(s, hat, pygame.Rect(head_c[0] - 48, head_c[1] - 14, 96, 14), border_radius=7)
    pygame.draw.rect(s, lighten(hat, 0.35), pygame.Rect(head_c[0] - 6, head_c[1] - 50, 12, 34), border_radius=5)
    pygame.draw.ellipse(s, O, hat_rect, lw)
    pygame.draw.rect(s, O, pygame.Rect(head_c[0] - 48, head_c[1] - 14, 96, 14), lw, border_radius=7)
    return pygame.transform.smoothscale(s, (WORKER_W, WORKER_H))


# ===================================================================== backgrounds
def sky_scene(theme_colors: dict, planet_id: str, width: int, height: int, title: str,
              factory_theme: tuple) -> pygame.Surface:
    key = ("sky", planet_id, width, height, title, factory_theme)
    return _cached(key, lambda: _draw_sky(theme_colors, planet_id, width, height, title, factory_theme))


def _draw_sky(tc: dict, planet_id: str, w: int, h: int, title: str, ftheme: tuple) -> pygame.Surface:
    s = pygame.Surface((w, h))
    s.blit(gradient_surface((w, h), tc["sky_top"], tc["sky_bottom"]), (0, 0))
    rng = random.Random(planet_id)
    dark = sum(tc["sky_top"]) < 150
    for _ in range(140 if dark else 50):
        x, y = rng.randrange(w), rng.randrange(int(h * 0.7))
        a = rng.randint(90, 255) if dark else rng.randint(40, 120)
        r = rng.choice((1, 1, 2, 2, 3))
        pygame.draw.circle(s, mix(tc["sky_top"], (255, 255, 255), a / 255), (x, y), r)
    # Distant planet/moon in the sky
    pc = tc.get("planet", (200, 200, 210))
    pr = 62
    pygame.draw.circle(s, darken(pc, 0.15), (850, 190), pr)
    pygame.draw.circle(s, lighten(pc, 0.2), (838, 178), pr - 10)
    for (dx, dy, rr) in ((-20, -10, 12), (18, 20, 9), (10, -30, 7)):
        pygame.draw.circle(s, darken(pc, 0.1), (850 + dx, 190 + dy), rr)
    # Mountains
    horizon = int(h * 0.74)
    for layer, (col, amp, base) in enumerate(((mix(tc["hills"], tc["sky_bottom"], 0.55), 120, horizon - 40),
                                              (mix(tc["hills"], tc["sky_bottom"], 0.25), 90, horizon - 5),
                                              (tc["hills"], 50, horizon + 25))):
        pts = [(0, h)]
        x = 0
        lr = random.Random(planet_id + str(layer))
        while x <= w + 60:
            pts.append((x, base - lr.randint(0, amp)))
            x += lr.randint(70, 160)
        pts.append((w, h))
        pygame.draw.polygon(s, col, pts)
        if layer == 0:
            # Snowy caps on the far mountains (Earth-like planets only)
            if planet_id == "earth":
                for px, py in pts[1:-1]:
                    if py < base - amp * 0.6:
                        pygame.draw.polygon(s, (240, 245, 255), [(px, py), (px - 22, py + 26), (px + 22, py + 26)])
    # Trees / rocks on the near hills
    tr = random.Random(planet_id + "trees")
    for _ in range(18):
        x = tr.randrange(0, w)
        y = horizon + 30 + tr.randrange(0, 40)
        if planet_id == "earth":
            pygame.draw.circle(s, darken(tc["hills"], 0.25), (x, y), tr.randint(14, 24))
            pygame.draw.circle(s, darken(tc["hills"], 0.1), (x - 5, y - 6), tr.randint(8, 14))
        else:
            pygame.draw.ellipse(s, darken(tc["ground"], 0.15), pygame.Rect(x, y, tr.randint(20, 46), tr.randint(12, 22)))
    # Ground strip / concrete platform
    ground_top = h - 70
    pygame.draw.rect(s, (150, 160, 175), pygame.Rect(0, ground_top, w, 70))
    pygame.draw.rect(s, (185, 195, 210), pygame.Rect(0, ground_top, w, 14))
    for x in range(0, w, 120):
        pygame.draw.line(s, (130, 140, 155), (x, ground_top + 14), (x, h), 3)
    # Factory building (left)
    _draw_building(s, title, ftheme, ground_top)
    return s


def _draw_building(s: pygame.Surface, title: str, ftheme: tuple, ground_top: int) -> None:
    wall = (205, 212, 225)
    roof_color = ftheme
    b = pygame.Rect(-20, ground_top - 330, 470, 330)
    pygame.draw.rect(s, wall, b, border_radius=10)
    pygame.draw.rect(s, darken(wall, 0.12), pygame.Rect(b.x, b.y + 150, b.width, 180))
    # upper floor
    up = pygame.Rect(40, b.y - 90, 320, 100)
    pygame.draw.rect(s, lighten(wall, 0.1), up, border_radius=8)
    pygame.draw.rect(s, O, up, 4, border_radius=8)
    for i in range(3):
        win = pygame.Rect(62 + i * 100, up.y + 18, 80, 60)
        pygame.draw.rect(s, (60, 110, 180), win, border_radius=6)
        pygame.draw.rect(s, (130, 190, 240), win.inflate(-30, -30).move(-8, -8), border_radius=4)
        pygame.draw.rect(s, O, win, 4, border_radius=6)
    # yellow trim (the reference has a yellow roof edge)
    pygame.draw.rect(s, theme.YELLOW, pygame.Rect(b.x, b.y - 4, b.width + 10, 26), border_radius=8)
    pygame.draw.rect(s, O, pygame.Rect(b.x, b.y - 4, b.width + 10, 26), 4, border_radius=8)
    for i in range(4):
        win = pygame.Rect(10 + i * 105, b.y + 46, 86, 76)
        pygame.draw.rect(s, (50, 95, 165), win, border_radius=6)
        pygame.draw.line(s, (130, 190, 240), (win.x + 10, win.bottom - 10), (win.right - 20, win.y + 10), 6)
        pygame.draw.rect(s, O, win, 4, border_radius=6)
    pygame.draw.rect(s, O, b, 5, border_radius=10)
    # sign
    sign = pygame.Rect(150, b.y + 160, 280, 110)
    pygame.draw.rect(s, (40, 50, 75), sign, border_radius=14)
    pygame.draw.rect(s, (100, 110, 140), sign, 6, border_radius=14)
    words = title.upper().split(" ")
    line1 = " ".join(words[:-1]) if len(words) > 1 else title.upper()
    line2 = words[-1] if len(words) > 1 else ""
    t1 = text_surface(line1, 40 if len(line1) < 14 else 32, theme.WHITE)
    s.blit(t1, t1.get_rect(center=(sign.centerx, sign.centery - (20 if line2 else 0))))
    if line2:
        t2 = text_surface(line2, 40, theme.WHITE)
        s.blit(t2, t2.get_rect(center=(sign.centerx, sign.centery + 24)))
    # garage door
    door = pygame.Rect(20, ground_top - 120, 110, 120)
    pygame.draw.rect(s, (150, 160, 180), door)
    for y in range(door.y + 12, door.bottom, 18):
        pygame.draw.line(s, (120, 130, 150), (door.x, y), (door.right, y), 3)
    pygame.draw.rect(s, O, door, 4)
    # satellite dish on the roof
    pygame.draw.line(s, (90, 95, 110), (380, up.y + 40), (410, up.y - 30), 10)
    dish = pygame.Rect(360, up.y - 110, 130, 110)
    pygame.draw.ellipse(s, (215, 220, 235), dish)
    pygame.draw.ellipse(s, O, dish, 5)
    pygame.draw.ellipse(s, (170, 180, 200), dish.inflate(-50, -50))
    pygame.draw.line(s, O, dish.center, (dish.centerx + 40, dish.y - 10), 5)


def launch_tower(height: int) -> pygame.Surface:
    return _cached(("tower", height), lambda: _draw_tower(height))


def _draw_tower(height: int) -> pygame.Surface:
    w = 90
    s = pygame.Surface((w, height), pygame.SRCALPHA)
    steel = (200, 70, 50)
    dark = (50, 55, 75)
    pygame.draw.rect(s, dark, pygame.Rect(8, 30, 12, height - 30))
    pygame.draw.rect(s, dark, pygame.Rect(w - 20, 30, 12, height - 30))
    y = 40
    while y < height - 10:
        pygame.draw.line(s, dark, (14, y), (w - 14, y + 50), 6)
        pygame.draw.line(s, dark, (w - 14, y), (14, y + 50), 6)
        pygame.draw.line(s, dark, (14, y), (w - 14, y), 6)
        y += 50
    pygame.draw.rect(s, steel, pygame.Rect(0, 24, w, 18), border_radius=4)
    pygame.draw.rect(s, O, pygame.Rect(0, 24, w, 18), 3, border_radius=4)
    pygame.draw.rect(s, (60, 60, 70), pygame.Rect(w // 2 - 22, 0, 44, 26), border_radius=4)
    return s


def floor_background(width: int, height: int, wall: tuple, kind: str) -> pygame.Surface:
    return _cached(("floorbg", width, height, wall, kind), lambda: _draw_floor_bg(width, height, wall, kind))


def _draw_floor_bg(w: int, h: int, wall: tuple, kind: str) -> pygame.Surface:
    s = pygame.Surface((w, h))
    dirt = (112, 78, 58)
    s.fill(dirt)
    rng = random.Random(kind)
    for _ in range(40):
        x, y = rng.randrange(w), rng.randrange(h)
        pygame.draw.circle(s, darken(dirt, 0.2), (x, y), rng.randint(3, 8))
    room = pygame.Rect(150, 18, w - 160, h - 36)
    s.blit(gradient_surface(room.size, lighten(wall, 0.2), darken(wall, 0.15)), room)
    # wall panels
    for x in range(room.x, room.right, 130):
        pygame.draw.line(s, darken(wall, 0.25), (x, room.y + 40), (x, room.bottom - 40), 3)
        for yy in (room.y + 56, room.bottom - 56):
            pygame.draw.circle(s, darken(wall, 0.3), (x + 10, yy), 3)
    # ceiling pipes
    pygame.draw.rect(s, (70, 80, 110), pygame.Rect(room.x, room.y, room.width, 30))
    pygame.draw.rect(s, (110, 150, 210), pygame.Rect(room.x, room.y + 8, room.width, 12))
    pygame.draw.line(s, (170, 200, 240), (room.x, room.y + 10), (room.right, room.y + 10), 3)
    for x in range(room.x + 60, room.right, 220):
        pygame.draw.rect(s, (80, 90, 120), pygame.Rect(x, room.y + 4, 20, 22))
    # ceiling lights
    for x in range(room.x + 230, room.right - 100, 300):
        pygame.draw.rect(s, (230, 235, 210), pygame.Rect(x, room.y + 34, 110, 14), border_radius=7)
        glow = pygame.Surface((200, 80), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (255, 250, 200, 40), glow.get_rect())
        s.blit(glow, (x - 45, room.y + 40))
    # floor platform
    plat = pygame.Rect(room.x, room.bottom - 34, room.width, 34)
    pygame.draw.rect(s, (215, 205, 190), plat)
    pygame.draw.rect(s, (170, 160, 145), pygame.Rect(plat.x, plat.y + 22, plat.width, 12))
    pygame.draw.line(s, (240, 235, 220), (plat.x, plat.y + 3), (plat.right, plat.y + 3), 3)
    # dark frame
    pygame.draw.rect(s, (40, 46, 66), room, 6)
    return s


def elevator_shaft(height: int) -> pygame.Surface:
    return _cached(("shaft", height), lambda: _draw_shaft(height))


def _draw_shaft(height: int) -> pygame.Surface:
    w = 120
    s = pygame.Surface((w, height), pygame.SRCALPHA)
    pygame.draw.rect(s, (55, 70, 110), pygame.Rect(0, 0, w, height), border_radius=18)
    pygame.draw.rect(s, (35, 45, 80), pygame.Rect(18, 0, w - 36, height))
    for x in (30, w - 30):
        pygame.draw.line(s, (120, 140, 190), (x, 0), (x, height), 6)
    pygame.draw.rect(s, (25, 30, 55), pygame.Rect(0, 0, w, height), 6, border_radius=18)
    return s


def component_item(component_color: tuple, kind: str, size: int = 46) -> pygame.Surface:
    return _cached(("item", tuple(component_color), kind, size), lambda: _draw_item(component_color, kind, size))


def _draw_item(color, kind, size):
    S = 2
    z = size * S
    s = pygame.Surface((z, z), pygame.SRCALPHA)
    if kind == "parts":
        # rocket body segment (white with red cap)
        body = pygame.Rect(z * 0.15, z * 0.25, z * 0.7, z * 0.62)
        pygame.draw.rect(s, (240, 240, 245), body, border_radius=12)
        pygame.draw.rect(s, color, pygame.Rect(body.x, body.y, body.width, z * 0.18), border_top_left_radius=12, border_top_right_radius=12)
        pygame.draw.rect(s, (180, 185, 200), pygame.Rect(body.x + 8, body.bottom - 18, body.width - 16, 8))
        pygame.draw.rect(s, O, body, 5, border_radius=12)
    elif kind == "nose":
        pts = [(z * 0.5, z * 0.08), (z * 0.85, z * 0.88), (z * 0.15, z * 0.88)]
        pygame.draw.polygon(s, color, pts)
        pygame.draw.polygon(s, lighten(color, 0.3), [(z * 0.5, z * 0.08), (z * 0.4, z * 0.88), (z * 0.15, z * 0.88)])
        pygame.draw.polygon(s, O, pts, 5)
    elif kind == "box":
        r = pygame.Rect(z * 0.12, z * 0.2, z * 0.76, z * 0.66)
        pygame.draw.rect(s, (225, 165, 90), r, border_radius=8)
        pygame.draw.rect(s, color, pygame.Rect(r.x, r.centery - 8, r.width, 16))
        pygame.draw.rect(s, O, r, 5, border_radius=8)
    else:  # generic glowing canister
        r = pygame.Rect(z * 0.25, z * 0.1, z * 0.5, z * 0.8)
        pygame.draw.rect(s, color, r, border_radius=20)
        pygame.draw.rect(s, lighten(color, 0.5), pygame.Rect(r.x + 10, r.y + 16, 12, r.height - 32), border_radius=6)
        pygame.draw.rect(s, (90, 95, 110), pygame.Rect(r.x - 4, r.y, r.width + 8, 14), border_radius=6)
        pygame.draw.rect(s, (90, 95, 110), pygame.Rect(r.x - 4, r.bottom - 14, r.width + 8, 14), border_radius=6)
        pygame.draw.rect(s, O, r, 5, border_radius=20)
    return pygame.transform.smoothscale(s, (size, size))


def cloud(width: int) -> pygame.Surface:
    return _cached(("cloud", width), lambda: _draw_cloud(width))


def _draw_cloud(width: int) -> pygame.Surface:
    h = width // 2
    s = pygame.Surface((width, h), pygame.SRCALPHA)
    for (fx, fy, fr) in ((0.3, 0.6, 0.22), (0.5, 0.45, 0.28), (0.72, 0.6, 0.2), (0.5, 0.7, 0.24)):
        pygame.draw.circle(s, (255, 255, 255, 235), (int(width * fx), int(h * fy)), int(width * fr))
    pygame.draw.ellipse(s, (215, 230, 250, 200), pygame.Rect(width * 0.12, h * 0.68, width * 0.76, h * 0.3))
    return s


def logo(width: int) -> pygame.Surface:
    return _cached(("logo", width), lambda: _draw_logo(width))


def _draw_logo(width: int) -> pygame.Surface:
    h = int(width * 0.62)
    s = pygame.Surface((width, h), pygame.SRCALPHA)
    # swoosh
    pygame.draw.arc(s, theme.ORANGE, pygame.Rect(width * 0.05, h * 0.05, width * 0.9, h * 0.8), 0.2, 2.6, 14)
    t1 = text_surface("ROCKET", int(width * 0.2), theme.WHITE, outline=7, outline_color=(20, 40, 110), shadow=True)
    t2 = text_surface("EMPIRE", int(width * 0.2), theme.WHITE, outline=7, outline_color=(20, 40, 110), shadow=True)
    s.blit(t1, t1.get_rect(midtop=(width * 0.46, h * 0.1)))
    s.blit(t2, t2.get_rect(midtop=(width * 0.52, h * 0.36)))
    ribbon = pygame.Rect(width * 0.1, h * 0.72, width * 0.8, h * 0.2)
    pygame.draw.rect(s, (30, 60, 140), ribbon, border_radius=int(h * 0.1))
    pygame.draw.rect(s, (120, 180, 255), ribbon, 4, border_radius=int(h * 0.1))
    t3 = text_surface("IDLE SPACE TYCOON", int(width * 0.075), theme.WHITE)
    s.blit(t3, t3.get_rect(center=ribbon.center))
    r = rocket_sprite(int(h * 0.42), fins=3)
    r = pygame.transform.rotate(r, -35)
    s.blit(r, r.get_rect(center=(width * 0.86, h * 0.18)))
    return s


def planet_sphere(color: tuple, radius: int, ring: bool = False, seed: str = "") -> pygame.Surface:
    return _cached(("sphere", tuple(color), radius, ring, seed), lambda: _draw_sphere(color, radius, ring, seed))


def _draw_sphere(color, radius, ring, seed):
    S = 2
    r = radius * S
    size = r * 2 + (r if ring else 0) + 20
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    c = (size // 2, size // 2)
    if ring:
        pygame.draw.ellipse(s, (*lighten(color, 0.4), 255), pygame.Rect(c[0] - r * 1.5, c[1] - r * 0.3, r * 3, r * 0.6), 10)
    pygame.draw.circle(s, darken(color, 0.25), c, r)
    pygame.draw.circle(s, color, (c[0] - r // 8, c[1] - r // 8), int(r * 0.88))
    rng = random.Random(seed)
    for _ in range(6):
        ang = rng.random() * math.tau
        dist = rng.random() * r * 0.6
        pygame.draw.circle(s, mix(color, (255, 255, 255), 0.25) if rng.random() < 0.5 else darken(color, 0.12),
                           (int(c[0] + math.cos(ang) * dist), int(c[1] + math.sin(ang) * dist)), int(r * rng.uniform(0.08, 0.22)))
    pygame.draw.circle(s, (255, 255, 255, 90), (c[0] - r // 3, c[1] - r // 3), r // 5)
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), c, r)
    body = s.copy()
    body.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    out = pygame.Surface((size, size), pygame.SRCALPHA)
    if ring:
        out.blit(s, (0, 0))
        out.blit(body, (0, 0))
        front = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.arc(front, (*lighten(color, 0.4), 255), pygame.Rect(c[0] - r * 1.5, c[1] - r * 0.3, r * 3, r * 0.6), math.pi, math.tau, 10)
        out.blit(front, (0, 0))
    else:
        out.blit(body, (0, 0))
    pygame.draw.circle(out, O, c, r, 6)
    return pygame.transform.smoothscale(out, (size // S, size // S))
