"""A small pooled particle system (smoke, fire, sparks, coins, confetti).

Particles are stored in plain lists and recycled, so launches do not create
garbage every frame.  Sprites are pre-rendered and cached.
"""
from __future__ import annotations

import math
import random

import pygame

from game.rendering import icons
from game.rendering.draw import circle_surface, soft_glow

MAX_PARTICLES = 700


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "size", "grow", "color", "kind",
                 "gravity", "drag", "spin", "angle", "alive", "screen")

    def __init__(self) -> None:
        self.alive = False


class ParticleSystem:
    def __init__(self) -> None:
        self.pool = [Particle() for _ in range(MAX_PARTICLES)]
        self.cursor = 0
        self.rng = random.Random(7)

    def _next(self) -> Particle:
        for _ in range(MAX_PARTICLES):
            p = self.pool[self.cursor]
            self.cursor = (self.cursor + 1) % MAX_PARTICLES
            if not p.alive:
                return p
        # Pool full: recycle the oldest slot.
        p = self.pool[self.cursor]
        self.cursor = (self.cursor + 1) % MAX_PARTICLES
        return p

    def emit(self, kind: str, x: float, y: float, count: int = 1, spread: float = 1.0,
             color=(255, 255, 255), speed: float = 200, angle: float = -math.pi / 2,
             life: float = 1.0, size: float = 16, gravity: float = 0.0, screen: bool = False) -> None:
        rng = self.rng
        for _ in range(count):
            p = self._next()
            a = angle + rng.uniform(-spread, spread)
            v = speed * rng.uniform(0.5, 1.2)
            p.x, p.y = x + rng.uniform(-6, 6), y + rng.uniform(-6, 6)
            p.vx, p.vy = math.cos(a) * v, math.sin(a) * v
            p.life = p.max_life = life * rng.uniform(0.7, 1.3)
            p.size = size * rng.uniform(0.7, 1.3)
            p.grow = 0.0
            p.color = color
            p.kind = kind
            p.gravity = gravity
            p.drag = 0.0
            p.spin = rng.uniform(-6, 6)
            p.angle = rng.uniform(0, 360)
            p.alive = True
            p.screen = screen
            if kind == "smoke":
                p.grow = size * 2.2
                p.drag = 1.6
            elif kind == "fire":
                p.grow = -size * 0.8
                p.drag = 1.0
            elif kind == "confetti":
                p.drag = 1.2
                p.color = rng.choice([(255, 80, 80), (255, 210, 60), (90, 200, 255), (120, 230, 120), (220, 120, 255)])
            elif kind == "sparkle":
                p.drag = 2.0
                p.color = rng.choice([(255, 120, 120), (255, 220, 90), (120, 255, 160), (120, 200, 255), (230, 140, 255)])

    def update(self, dt: float) -> None:
        for p in self.pool:
            if not p.alive:
                continue
            p.life -= dt
            if p.life <= 0:
                p.alive = False
                continue
            if p.drag:
                f = max(0.0, 1 - p.drag * dt)
                p.vx *= f
                p.vy *= f
            p.vy += p.gravity * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.size = max(1.0, p.size + p.grow * dt)
            p.angle += p.spin * 60 * dt

    def active_count(self) -> int:
        return sum(1 for p in self.pool if p.alive)

    def clear(self) -> None:
        for p in self.pool:
            p.alive = False

    def draw(self, surface: pygame.Surface, offset_y: float = 0.0, screen_layer: bool = False) -> None:
        for p in self.pool:
            if not p.alive or p.screen != screen_layer:
                continue
            y = p.y - (0 if p.screen else offset_y)
            if y < -200 or y > surface.get_height() + 200:
                continue
            t = p.life / p.max_life
            size = int(p.size)
            # Quantize size/alpha so the sprite cache stays small.
            q = max(4, size // 4 * 4)
            ta = round(t * 8) / 8
            if p.kind == "smoke":
                shade = int(200 + 55 * ta)
                surf = circle_surface(q // 2, (shade, shade, shade), int(200 * ta))
                surface.blit(surf, (p.x - q / 2, y - q / 2))
            elif p.kind == "fire":
                size = q
                glow = soft_glow(max(4, size), p.color, int(220 * ta))
                surface.blit(glow, (p.x - size, y - size), special_flags=pygame.BLEND_RGBA_ADD)
            elif p.kind == "coin":
                ic = icons.icon("coin", max(8, size))
                surface.blit(ic, (p.x - size / 2, y - size / 2))
            elif p.kind == "gem":
                ic = icons.icon("gem", max(8, size))
                surface.blit(ic, (p.x - size / 2, y - size / 2))
            elif p.kind == "star":
                ic = icons.icon("star", max(8, size))
                surface.blit(ic, (p.x - size / 2, y - size / 2))
            elif p.kind == "confetti":
                w = max(3, size // 2)
                h = max(2, int(size / 3 * abs(math.sin(math.radians(p.angle)))) + 1)
                pygame.draw.rect(surface, p.color, pygame.Rect(p.x, y, w, h))
            else:  # sparkle / generic dot
                surf = circle_surface(max(2, q // 3), p.color, int(255 * ta))
                surface.blit(surf, (p.x - size / 3, y - size / 3))
