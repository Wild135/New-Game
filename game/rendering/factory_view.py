"""Draws the main factory screen: sky + launchpad + scrolling factory floors.

The view reads the game state every frame and never changes it directly - it
asks the ``Game`` object to perform actions (upgrade, tap, launch ...).
"""
from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import pygame

from game.core.numformat import format_number
from game.rendering import art, icons
from game.rendering.draw import (darken, overlay, draw_text, lighten, panel, progress_bar, soft_glow)
from game.ui import theme
from game.ui.widgets import ScrollArea

if TYPE_CHECKING:  # pragma: no cover
    from game.app import App

SKY_H = 760
FLOOR_H = 300
PAD_ROW_H = 250
GROUND_Y = SKY_H - 70          # world y where the concrete starts
PAD_X = 720                    # rocket centre x
ROCKET_H = 300
SHAFT_X = 18


class LaunchAnim:
    def __init__(self) -> None:
        self.phase = "idle"      # idle | ignite | liftoff | arrive
        self.t = 0.0
        self.rocket_y = 0.0
        self.revenue = 0.0
        self.count = 0.0


class FactoryView:
    def __init__(self, app: "App"):
        self.app = app
        self.scroll = ScrollArea()
        self.launch = LaunchAnim()
        self.time = 0.0
        self.floaters: list[dict] = []
        self.clouds = [[random.uniform(0, 1080), random.uniform(260, 520), random.uniform(140, 240),
                        random.uniform(8, 20)] for _ in range(5)]
        self.shake = 0.0
        self.layout: list[tuple[str, int, int]] = []   # (floor_id, world_y, height)
        self.flash: dict[str, float] = {}               # floor_id -> upgrade flash timer
        self.highlight_rects: dict[str, pygame.Rect] = {}  # for the tutorial

    # ------------------------------------------------------------------ helpers
    @property
    def game(self):
        return self.app.game

    def floor_order(self) -> list[str]:
        factory = self.game.factory
        ids = [fid for fid in factory.ordered_floor_ids()]
        return ids  # launchpad first (rendered as the control row)

    def build_layout(self) -> int:
        y = SKY_H
        self.layout = []
        for fid in self.floor_order():
            h = PAD_ROW_H if self.game.config.floors[fid]["kind"] == "launch" else FLOOR_H
            self.layout.append((fid, y, h))
            y += h
        return y + 60

    def world_to_screen(self, y: float) -> float:
        return y - self.scroll.offset

    def add_floater(self, text: str, x: float, y_world: float, color=theme.YELLOW, size: int = 54,
                    icon: str | None = None) -> None:
        self.floaters.append({"text": text, "x": x, "y": y_world, "life": 1.6, "color": color,
                              "size": size, "icon": icon})

    def floor_screen_center(self, fid: str) -> tuple[int, int] | None:
        for lid, y, h in self.layout:
            if lid == fid:
                return 470, int(self.world_to_screen(y + h / 2))
        return None

    # ------------------------------------------------------------------ events
    def on_launch(self, count: float, revenue: float) -> None:
        anims = self.game.settings.get("launch_animations", True)
        x, y = PAD_X, GROUND_Y - ROCKET_H * 0.5
        self.add_floater("+" + self.game.describe_money(revenue), x, y - 60, theme.YELLOW, 64, "coin")
        if count > 1:
            self.add_floater(f"x{format_number(count)} rockets", x, y + 10, theme.WHITE, 40)
        self.app.particles.emit("coin", x, y, 10, spread=1.2, speed=520, life=1.0, size=40, gravity=900)
        if anims and self.launch.phase in ("idle", "arrive"):
            self.launch.phase = "ignite"
            self.launch.t = 0.0
            self.launch.rocket_y = 0.0
            self.app.audio.play("ignition")
        else:
            self.app.audio.play("coin")

    def skip_launch(self) -> None:
        if self.launch.phase in ("ignite", "liftoff"):
            self.launch.phase = "arrive"
            self.launch.t = 0.0

    # ------------------------------------------------------------------ update
    def update(self, dt: float) -> None:
        self.time += dt
        for c in self.clouds:
            c[0] += c[3] * dt
            if c[0] > 1180:
                c[0] = -c[2]
        for f in self.floaters:
            f["life"] -= dt
            f["y"] -= 70 * dt
        self.floaters = [f for f in self.floaters if f["life"] > 0]
        for k in list(self.flash):
            self.flash[k] -= dt
            if self.flash[k] <= 0:
                del self.flash[k]
        self.shake = max(0.0, self.shake - dt * 2)
        la = self.launch
        la.t += dt
        ps = self.app.particles
        exhaust = self.exhaust_color()
        effect = self.game.shop.equipped.get("effect", "effect_smoke")
        base_y = GROUND_Y - 30
        if la.phase == "ignite":
            for _ in range(2):
                ps.emit("smoke", PAD_X + random.uniform(-60, 60), base_y, 2, spread=0.9, speed=260,
                        angle=math.pi / 2 + random.choice((-1, 1)) * 1.2, life=1.4, size=40)
            ps.emit("fire", PAD_X, base_y - 10, 3, spread=0.3, speed=180, angle=math.pi / 2, life=0.35,
                    size=34, color=exhaust)
            self.shake = 0.4
            if la.t > 0.7:
                la.phase, la.t = "liftoff", 0.0
                self.app.audio.play("launch")
                if effect in ("effect_confetti", "effect_galaxy"):
                    ps.emit("confetti", PAD_X, base_y - 100, 60, spread=1.4, speed=700, life=1.8, size=16, gravity=600)
        elif la.phase == "liftoff":
            la.rocket_y = 120 * la.t ** 2 + 40 * la.t
            ry = GROUND_Y - la.rocket_y
            ps.emit("fire", PAD_X, ry - 8, 3, spread=0.25, speed=260, angle=math.pi / 2, life=0.35, size=36,
                    color=exhaust)
            ps.emit("smoke", PAD_X, ry + 10, 2, spread=0.4, speed=90, angle=math.pi / 2, life=1.6, size=30)
            if effect in ("effect_sparkle", "effect_galaxy"):
                ps.emit("sparkle", PAD_X, ry + 20, 3, spread=0.8, speed=160, angle=math.pi / 2, life=1.0, size=24)
            self.shake = max(self.shake, 0.25)
            if la.rocket_y > GROUND_Y + 600:
                la.phase, la.t = "arrive", 0.0
        elif la.phase == "arrive":
            if la.t > 0.8:
                la.phase, la.t = "idle", 0.0

    def exhaust_color(self):
        cos = self.game.shop.equipped_item("exhaust")
        return tuple(cos.get("color", (255, 170, 40)))

    # ------------------------------------------------------------------ drawing
    def draw(self, surface: pygame.Surface, ui, dt: float) -> None:
        game = self.game
        content_h = self.build_layout()
        self.scroll.update(ui, pygame.Rect(0, 0, theme.WIDTH, theme.HEIGHT - theme.NAV_H), content_h, dt)
        shake_x = math.sin(self.time * 70) * 6 * self.shake if self.shake else 0
        self.highlight_rects = {}
        self.draw_sky(surface, ui, shake_x)
        for fid, y, h in self.layout:
            sy = self.world_to_screen(y)
            if sy > theme.HEIGHT or sy + h < 0:
                continue
            kind = game.config.floors[fid]["kind"]
            floor = game.factory.floors[fid]
            if floor.level <= 0:
                self.draw_locked(surface, ui, fid, int(sy), h)
            elif kind == "launch":
                self.draw_pad_row(surface, ui, fid, int(sy), h)
            else:
                self.draw_floor(surface, ui, fid, int(sy), h)
        self.draw_shaft(surface)
        bottom = self.world_to_screen(content_h - 60)
        if bottom < theme.HEIGHT:
            pygame.draw.rect(surface, (90, 62, 46), pygame.Rect(0, bottom, theme.WIDTH, theme.HEIGHT - bottom + 10))
        self.app.particles.draw(surface, self.scroll.offset)
        for f in self.floaters:
            alpha = min(1.0, f["life"] / 0.5)
            y = self.world_to_screen(f["y"])
            r = draw_text(surface, f["text"], (f["x"], y), f["size"], f["color"], anchor="center",
                          outline=5)
            if f["icon"] and alpha > 0.2:
                ic = icons.icon(f["icon"], f["size"])
                surface.blit(ic, (r.left - f["size"] - 6, r.centery - f["size"] // 2))

    # ---------------------------------------------------------------- sky
    def draw_sky(self, surface: pygame.Surface, ui, shake_x: float) -> None:
        game = self.game
        planet = game.config.planets[game.current_planet]
        theme_item = game.shop.equipped_item("theme")
        title = f"{planet['name']} Factory" if game.current_planet != "earth" else "Rocket Factory 1"
        sky = art.sky_scene(planet["theme"], planet["id"], theme.WIDTH, SKY_H, title,
                            tuple(theme_item.get("color", (50, 90, 170))))
        top = self.world_to_screen(0)
        cam = 0.0
        if self.launch.phase == "liftoff":
            cam = min(1.0, self.launch.t / 0.8) * 70 * max(0.0, 1 - max(0.0, self.launch.t - 1.4) / 1.0)
        if top + SKY_H < 0:
            return
        if top + cam > 0:
            pygame.draw.rect(surface, planet["theme"]["sky_top"], pygame.Rect(0, 0, theme.WIDTH, top + cam + 2))
        surface.blit(sky, (shake_x, top + cam))
        for cx, cy, cw, _ in self.clouds:
            if sum(planet["theme"]["sky_top"]) > 150:
                surface.blit(art.cloud(int(cw)), (cx, top + cy * 0.6 + cam * 0.5))
        # Launch towers + rocket
        tower_h = 380
        ty = top + GROUND_Y - tower_h + cam
        surface.blit(art.launch_tower(tower_h), (PAD_X - 210 + shake_x, ty))
        surface.blit(art.launch_tower(tower_h), (PAD_X + 120 + shake_x, ty))
        for i, lx in enumerate((PAD_X - 165, PAD_X + 165)):
            on = (int(self.time * 2) + i) % 2 == 0
            glow = soft_glow(26, (255, 220, 120) if on else (255, 120, 80), 160)
            surface.blit(glow, (lx - 26 + shake_x, ty - 6))
        # pad base
        pad_rect = pygame.Rect(PAD_X - 170, top + GROUND_Y - 34 + cam, 340, 44)
        pygame.draw.rect(surface, (70, 80, 110), pad_rect.move(shake_x, 0), border_radius=10)
        pygame.draw.rect(surface, (120, 140, 200), pygame.Rect(pad_rect.x + 20 + shake_x, pad_rect.y + 6, 300, 14), border_radius=6)
        pygame.draw.rect(surface, theme.OUTLINE, pad_rect.move(shake_x, 0), 4, border_radius=10)
        for i in range(6):
            lx = pad_rect.x + 30 + i * 56 + shake_x
            col = theme.YELLOW if int(self.time * 4 + i) % 3 else (255, 255, 200)
            pygame.draw.circle(surface, col, (int(lx), pad_rect.bottom - 8), 6)
        factory = game.factory
        rocket = self.current_rocket_sprite()
        la = self.launch
        base = top + GROUND_Y - 22 + cam
        rocket_rect = rocket.get_rect(midbottom=(PAD_X + shake_x, base))
        has_ready = factory.ready >= 1
        if la.phase in ("ignite", "liftoff"):
            rect = rocket.get_rect(midbottom=(PAD_X + shake_x, base - la.rocket_y))
            surface.blit(rocket, rect)
        elif la.phase == "arrive":
            rise = min(1.0, la.t / 0.8)
            ghost = rocket.copy()
            if not has_ready:
                ghost.set_alpha(90)
            clip = pygame.Rect(0, 0, theme.WIDTH, base)
            surface.set_clip(clip)
            surface.blit(ghost, rocket.get_rect(midbottom=(PAD_X, base + (1 - rise) * ROCKET_H)))
            surface.set_clip(None)
        else:
            if has_ready:
                surface.blit(rocket, rocket_rect)
            else:
                ghost = rocket.copy()
                ghost.set_alpha(80)
                surface.blit(ghost, rocket_rect)
                # Assembly progress hologram
                progress = factory.assembly_progress
                bar = pygame.Rect(PAD_X - 110, rocket_rect.centery - 18, 220, 36)
                progress_bar(surface, bar, progress, theme.CYAN)
                draw_text(surface, "Assembling", (PAD_X, bar.y - 6), 30, theme.WHITE, anchor="midbottom", outline=3)
        # Ready count + countdown
        if has_ready and la.phase == "idle":
            tag = pygame.Rect(0, 0, 150, 50)
            tag.midbottom = (PAD_X, rocket_rect.top + 10)
            panel(surface, tag, theme.NAVY, theme.GREEN, radius=20, border=3, shadow=4)
            draw_text(surface, f"x{format_number(math.floor(factory.ready))} ready", tag.center, 28,
                      theme.GREEN_LIGHT, anchor="center", outline=2)
        countdown = None
        stats = game.stats_cache.get(game.current_planet)
        pad = factory.floors["launchpad"]
        if factory.countdown > 0:
            countdown = math.ceil(factory.countdown)
        elif pad.manager_uid and stats and has_ready and stats.interval >= 3:
            remaining = stats.interval - factory.pad_timer
            if remaining <= 3:
                countdown = max(1, math.ceil(remaining))
        if countdown and la.phase == "idle":
            pulse = 1 + 0.15 * math.sin(self.time * 12)
            draw_text(surface, str(countdown), (PAD_X, rocket_rect.centery), int(110 * pulse), theme.YELLOW,
                      anchor="center", outline=8)
            if getattr(self, "_last_count", None) != countdown:
                self.app.audio.play("countdown")
            self._last_count = countdown
        else:
            self._last_count = None
        sky_hit = pygame.Rect(PAD_X - 170, top + GROUND_Y - ROCKET_H - 60, 340, ROCKET_H + 60)
        self.highlight_rects["rocket"] = sky_hit
        if ui.region("sky_rocket", sky_hit):
            if la.phase in ("ignite", "liftoff"):
                self.skip_launch()
            elif not pad.manager_uid:
                if game.manual_launch():
                    self.app.audio.play("tap")
            else:
                self.app.open_floor_panel("launchpad")
        self.app.draw_world_overlay(surface, ui, top)

    def current_rocket_sprite(self) -> pygame.Surface:
        game = self.game
        rdef = game.config.rockets[game.factory.rocket_id]
        paint = game.shop.equipped_item("paint")
        decal = game.shop.equipped.get("decal", "decal_none")
        accent = tuple(paint.get("color", rdef["colors"]["accent"]))
        if paint["id"] == "paint_classic":
            accent = tuple(rdef["colors"]["accent"])
        return art.rocket_sprite(int(ROCKET_H * min(1.15, 0.8 + rdef["height"] * 0.2)),
                                 tuple(rdef["colors"]["body"]), accent, rdef["fins"], decal)

    # ---------------------------------------------------------------- shaft / elevator
    def draw_shaft(self, surface: pygame.Surface) -> None:
        if not self.layout:
            return
        first_y = self.world_to_screen(self.layout[0][1])
        unlocked = [(fid, y, h) for fid, y, h in self.layout if self.game.factory.floors[fid].level > 0]
        last = unlocked[-1]
        last_y = self.world_to_screen(last[1] + last[2])
        top = max(-40, first_y + 10)
        bottom = min(theme.HEIGHT + 40, last_y - 10)
        if bottom <= top:
            return
        shaft = art.elevator_shaft(int(last_y - first_y - 20))
        surface.blit(shaft, (SHAFT_X, first_y + 10))
        # floor number badges
        for n, (fid, y, h) in enumerate(unlocked, start=1):
            sy = self.world_to_screen(y)
            badge = pygame.Rect(SHAFT_X + 14, sy + h // 2 - 46, 92, 92)
            if badge.bottom < 0 or badge.top > theme.HEIGHT:
                continue
            panel(surface, badge, (40, 60, 110), (130, 160, 220), radius=16, border=4, shadow=4)
            draw_text(surface, str(n), (badge.centerx, badge.centery - 8), 46, theme.WHITE, anchor="center", outline=3)
            ic = icons.icon("arrow_up", 26)
            surface.blit(ic, (badge.centerx - 13, badge.bottom - 32))
        # Elevator car moving between the top and bottom unlocked production floors
        transport = self.game.factory.floors["transport"]
        active = transport.manager_uid is not None or transport.manual_time > 0
        span = last_y - first_y - 200
        if span > 0:
            phase = (self.time * (0.12 if active else 0.0)) % 2
            frac = phase if phase < 1 else 2 - phase
            frac = 0.5 - 0.5 * math.cos(frac * math.pi)
            cy = first_y + 60 + frac * span
            car = pygame.Rect(SHAFT_X + 22, cy, 76, 84)
            if -100 < cy < theme.HEIGHT:
                pygame.draw.rect(surface, (230, 190, 60), car, border_radius=10)
                pygame.draw.rect(surface, (180, 140, 30), car.inflate(-16, -40).move(0, 8), border_radius=6)
                crate = icons.icon("crate", 46)
                surface.blit(crate, (car.centerx - 23, car.y + 20))
                pygame.draw.rect(surface, theme.OUTLINE, car, 4, border_radius=10)
                pygame.draw.line(surface, (40, 40, 50), (car.centerx, max(0, first_y)), (car.centerx, car.y), 4)

    # ---------------------------------------------------------------- floors
    def floor_badges(self, surface, ui, fid: str, sy: int, h: int) -> None:
        """Title badge, manager slot, rate badge and upgrade button shared by all floors."""
        game = self.game
        fdef = game.config.floors[fid]
        floor = game.factory.floors[fid]
        stats = game.stats_cache.get(game.current_planet)
        # Title
        title = pygame.Rect(165, sy + 28, 360, 92)
        panel(surface, title, (28, 42, 80), (110, 150, 220), radius=26, border=4, shadow=5)
        ic = icons.icon(fdef.get("icon", "gear"), 62)
        surface.blit(ic, (title.x + 12, title.centery - 31))
        draw_text(surface, fdef["name"], (title.x + 84, title.y + 12), 36, theme.WHITE, outline=3, max_width=264)
        draw_text(surface, f"Lv. {floor.level}", (title.x + 84, title.y + 50), 32, theme.OFF_WHITE, outline=3)
        if ui.region(f"title:{fid}", title):
            self.app.open_floor_panel(fid)
        self.highlight_rects[f"title:{fid}"] = title
        # Manager slot
        if fdef["kind"] != "support":
            slot = pygame.Rect(title.right + 12, sy + 34, 80, 80)
            inst = game.managers.get(floor.manager_uid)
            if inst:
                mdef = game.config.managers[inst.def_id]
                pygame.draw.circle(surface, theme.RARITY_COLORS[mdef["rarity"]], slot.center, 42)
                portrait = icons.manager_portrait(mdef["look"], 80, self.hat_color())
                surface.blit(portrait, slot)
                pygame.draw.circle(surface, theme.OUTLINE, slot.center, 42, 4)
                if inst.active > 0:
                    glow = soft_glow(60, (255, 230, 100), 150)
                    surface.blit(glow, (slot.centerx - 60, slot.centery - 60), special_flags=pygame.BLEND_RGBA_ADD)
                elif inst.cooldown <= 0:
                    pygame.draw.circle(surface, theme.GREEN, (slot.right - 6, slot.y + 8), 14)
                    pygame.draw.circle(surface, theme.OUTLINE, (slot.right - 6, slot.y + 8), 14, 3)
                    draw_text(surface, "!", (slot.right - 6, slot.y + 9), 22, theme.WHITE, anchor="center")
                if ui.region(f"mgr:{fid}", slot.inflate(10, 10)):
                    if inst.cooldown <= 0 and game.managers.activate(inst.uid):
                        pass
                    else:
                        self.app.open_floor_panel(fid)
            else:
                pygame.draw.circle(surface, (40, 55, 95), slot.center, 40)
                pygame.draw.circle(surface, (130, 160, 220), slot.center, 40, 4)
                surface.blit(icons.icon("manager", 54), (slot.centerx - 27, slot.centery - 32))
                plus = icons.icon("plus", 26)
                pygame.draw.circle(surface, theme.GREEN, (slot.right - 8, slot.bottom - 8), 17)
                surface.blit(plus, (slot.right - 21, slot.bottom - 21))
                self.highlight_rects[f"mgr:{fid}"] = slot
                if ui.region(f"mgr:{fid}", slot.inflate(10, 10)):
                    self.app.open_floor_panel(fid, focus_manager=True)
        # Rate badge ($/s this stage could support)
        rate_rect = pygame.Rect(theme.WIDTH - 312, sy + 32, 290, 70)
        if fdef["kind"] == "support":
            text = f"x{game.factory.support_multiplier(fid):.2f}"
            border = theme.PURPLE
            arrow_color = theme.PURPLE
        else:
            value = 0.0
            if stats:
                value = stats.stage_rockets.get(fid, 0.0) * stats.value_per_rocket
            needed = stats is not None and (fid in stats.stage_rockets)
            text = game.describe_money(value) + "/s" if needed else "Not needed"
            bott = stats is not None and stats.bottleneck == fid
            border = theme.RED if bott else theme.GREEN
            arrow_color = theme.RED if bott else theme.GREEN_LIGHT
        panel(surface, rate_rect, (20, 34, 64), border, radius=22, border=4, shadow=4)
        surface.blit(icons.icon("arrow_up", 40) if arrow_color != theme.RED else icons.icon("bolt", 40),
                     (rate_rect.x + 14, rate_rect.centery - 20))
        draw_text(surface, text, (rate_rect.x + 64, rate_rect.centery), 36, theme.WHITE, anchor="midleft",
                  outline=3, max_width=rate_rect.width - 74)
        if fdef["kind"] != "support" and stats and stats.bottleneck == fid:
            tag = pygame.Rect(rate_rect.x + 30, rate_rect.bottom - 4, 230, 34)
            pygame.draw.rect(surface, theme.RED, tag, border_radius=14)
            pygame.draw.rect(surface, theme.OUTLINE, tag, 3, border_radius=14)
            draw_text(surface, "BOTTLENECK", tag.center, 26, theme.WHITE, anchor="center")
        # Upgrade button
        amount = game.settings.get("buy_amount", "1")
        count, cost = game.upgrade_quote(fid, amount)
        btn = pygame.Rect(theme.WIDTH - 290, sy + 128, 268, 112)
        affordable = count > 0 and cost <= game.credits
        label = "Upgrade" if amount == "1" else f"Upgrade x{count}"
        if count <= 0:
            label = "MAX"
        if ui.button(surface, f"upg:{fid}", btn, label, theme.GREEN if affordable else (110, 150, 110),
                     size=38, sublabel=game.describe_money(cost) if count else "", disabled=False):
            if game.upgrade_floor(fid, amount):
                self.on_upgraded(fid)
            else:
                self.app.audio.play("error")
        self.highlight_rects[f"upg:{fid}"] = btn
        if affordable:
            bob = int(math.sin(self.time * 5) * 5)
            surface.blit(icons.icon("arrow_up", 40), (btn.right - 30, btn.y - 34 + bob))

    def on_upgraded(self, fid: str) -> None:
        self.flash[fid] = 0.5
        self.app.audio.play("upgrade")
        center = self.floor_screen_center(fid)
        if center:
            for lid, y, h in self.layout:
                if lid == fid:
                    self.app.particles.emit("star", theme.WIDTH - 160, y + 170, 10, spread=math.pi, speed=380,
                                            life=0.7, size=30)
                    self.add_floater(f"Lv. {self.game.factory.floors[fid].level}", theme.WIDTH - 160, y + 120,
                                     theme.GREEN_LIGHT, 50)

    def hat_color(self):
        return tuple(self.game.shop.equipped_item("hat").get("color", theme.YELLOW))

    def floor_active(self, fid: str) -> tuple[bool, float]:
        floor = self.game.factory.floors[fid]
        active = floor.manager_uid is not None or floor.manual_time > 0
        busy = floor.flow > 1e-6 or self.game.config.floors[fid]["kind"] == "support"
        return active, (1.0 if (active and busy) else 0.0)

    def draw_floor(self, surface, ui, fid: str, sy: int, h: int) -> None:
        game = self.game
        fdef = game.config.floors[fid]
        kind = fdef["kind"]
        floor = game.factory.floors[fid]
        wall = tuple(darken(game.shop.equipped_item("theme").get("color", (50, 90, 170)), 0.0))
        surface.blit(art.floor_background(theme.WIDTH, h, wall, kind), (0, sy))
        active, speed = self.floor_active(fid)
        t = self.time
        hat = self.hat_color()
        plat_y = sy + h - 52  # feet line
        # Background click = tap / open panel
        machine_area = pygame.Rect(150, sy + 18, theme.WIDTH - 470, h - 36)
        self.highlight_rects[f"floor:{fid}"] = machine_area
        # Register the background tap area first so badges/buttons drawn later sit on top of it.
        floor_clicked = ui.region(f"floor:{fid}", machine_area)
        if kind == "producer":
            self.draw_producer(surface, fid, sy, plat_y, speed, hat)
        elif kind == "transport":
            self.draw_transport(surface, sy, plat_y, speed, hat)
        elif kind == "assembly":
            self.draw_assembly(surface, sy, plat_y, speed, hat)
        else:
            self.draw_support(surface, fid, sy, plat_y, hat)
        if fid in self.flash:
            level = int(self.flash[fid] / 0.5 * 6) * 20       # 6 cached brightness steps
            if level > 0:
                surface.blit(overlay((theme.WIDTH, h), (255, 255, 200, level)), (0, sy))
        # Manual mode hints
        if kind in ("producer", "transport", "assembly") and floor.manager_uid is None:
            if floor.manual_time > 0:
                frac = floor.manual_time / game.config.economy["manual_max_seconds"]
                bar = pygame.Rect(200, sy + h - 40, 300, 22)
                progress_bar(surface, bar, frac, theme.YELLOW)
            else:
                pulse = 1 + 0.1 * math.sin(t * 8)
                cx, cy = machine_area.centerx + 40, sy + 175
                draw_text(surface, "TAP!", (cx, cy), int(64 * pulse), theme.YELLOW, anchor="center", outline=6)
                hand_y = cy + 50 + int(math.sin(t * 8) * 8)
                pygame.draw.circle(surface, (255, 220, 180), (cx + 70, hand_y), 22)
                pygame.draw.circle(surface, theme.OUTLINE, (cx + 70, hand_y), 22, 4)
        self.floor_badges(surface, ui, fid, sy, h)
        # Storage meter for producers
        if kind == "producer":
            stats = game.stats_cache.get(game.current_planet)
            cap = stats.storage_cap.get(fid, 1.0) if stats else 1.0
            bar = pygame.Rect(540, sy + 134, 210, 18)
            full = floor.storage >= cap * 0.98
            progress_bar(surface, bar, floor.storage / max(cap, 1e-9), theme.ORANGE if full else theme.CYAN)
            draw_text(surface, "FULL" if full else "Storage", (bar.centerx, bar.centery), 18, theme.WHITE,
                      anchor="center", outline=2)
        if floor_clicked:
            if kind in ("producer", "transport", "assembly") and floor.manager_uid is None:
                if game.tap_floor(fid):
                    self.app.audio.play("tap")
                    mx, my = ui.pointer.pos
                    self.app.particles.emit("sparkle", mx, my + self.scroll.offset, 8, spread=math.pi, speed=260,
                                            life=0.5, size=22)
            else:
                self.app.open_floor_panel(fid)

    def _worker(self, surface, state, x, feet_y, speed, hat, flip=False, offset=0.0):
        if speed <= 0 and state not in ("idle", "celebrate"):
            state = "idle"
        rate = 8 if state != "idle" else 3
        frame = int((self.time + offset) * rate) % 8
        img = art.worker_frame(state, frame, hat, flip)
        surface.blit(img, (x - img.get_width() // 2, feet_y - img.get_height()))

    def draw_producer(self, surface, fid, sy, plat_y, speed, hat):
        game = self.game
        comp = game.factory.component_of(fid)
        ccol = tuple(game.config.components.get(comp, {}).get("color", (220, 70, 70)))
        fcol = tuple(game.config.floors[fid]["color"])
        t = self.time
        # Machine body
        m = pygame.Rect(300, plat_y - 120, 170, 120)
        pygame.draw.rect(surface, (90, 100, 140), m.move(0, 6), border_radius=16)
        pygame.draw.rect(surface, lighten(fcol, 0.15), m, border_radius=16)
        pygame.draw.rect(surface, darken(fcol, 0.2), pygame.Rect(m.x, m.y + 100, m.width, 50), border_radius=12)
        win = pygame.Rect(m.x + 34, m.y + 16, 102, 56)
        pygame.draw.rect(surface, (40, 30, 30), win, border_radius=10)
        flick = 0.6 + 0.4 * abs(math.sin(t * 9)) if speed else 0.0
        inner = win.inflate(-14, -14)
        pygame.draw.rect(surface, (int(120 + 120 * flick), int(60 + 70 * flick), 30), inner, border_radius=8)
        if speed:
            for i in range(3):
                fx = inner.x + 14 + i * 30
                fh = 10 + int(abs(math.sin(t * 10 + i)) * 16)
                pygame.draw.polygon(surface, (255, 220, 90), [(fx - 8, inner.bottom), (fx + 8, inner.bottom), (fx, inner.bottom - fh)])
            surface.blit(soft_glow(50, (255, 160, 60), int(60 * flick)), (win.centerx - 50, win.centery - 50),
                         special_flags=pygame.BLEND_RGBA_ADD)
        pygame.draw.rect(surface, theme.OUTLINE, win, 4, border_radius=10)
        pygame.draw.rect(surface, theme.OUTLINE, m, 5, border_radius=16)
        # lights on machine
        for i in range(3):
            on = speed and int(t * 5 + i) % 3 == 0
            pygame.draw.circle(surface, theme.GREEN_LIGHT if on else (60, 90, 60), (m.x + 40 + i * 45, m.y + 96), 9)
        # piston
        py = m.y - 30 + (math.sin(t * 7) * 10 if speed else 0)
        pygame.draw.rect(surface, (150, 155, 170), pygame.Rect(m.centerx - 14, m.y - 36, 28, 40))
        pygame.draw.rect(surface, (90, 95, 110), pygame.Rect(m.centerx - 36, py, 72, 26), border_radius=6)
        pygame.draw.rect(surface, theme.OUTLINE, pygame.Rect(m.centerx - 36, py, 72, 26), 4, border_radius=6)
        # Conveyor to the right
        self.draw_conveyor(surface, pygame.Rect(470, plat_y - 46, 300, 30), speed, ccol,
                           "parts" if comp == "parts" else "can")
        # control panel + workers
        panel_rect = pygame.Rect(196, plat_y - 96, 70, 96)
        pygame.draw.rect(surface, (70, 80, 110), panel_rect, border_radius=10)
        pygame.draw.rect(surface, (90, 220, 255) if speed else (60, 80, 100), panel_rect.inflate(-20, -60).move(0, -20), border_radius=6)
        pygame.draw.rect(surface, theme.OUTLINE, panel_rect, 4, border_radius=10)
        self._worker(surface, "work", 250, plat_y + 6, speed, hat, flip=False)
        self._worker(surface, "inspect", 700, plat_y + 6, speed, hat, flip=True, offset=0.4)

    def draw_conveyor(self, surface, rect: pygame.Rect, speed: float, color, item_kind: str):
        t = self.time
        pygame.draw.rect(surface, (60, 66, 90), rect, border_radius=14)
        pygame.draw.rect(surface, (40, 44, 64), rect.inflate(-10, -12), border_radius=10)
        offset = (t * 90 * speed) % 40
        for x in range(int(rect.x + 12 - 40 + offset), rect.right - 10, 40):
            if x > rect.x + 6:
                pygame.draw.circle(surface, (150, 160, 190), (x, rect.centery), 7)
                pygame.draw.circle(surface, theme.OUTLINE, (x, rect.centery), 7, 2)
        pygame.draw.rect(surface, theme.OUTLINE, rect, 4, border_radius=14)
        for leg in (rect.x + 30, rect.right - 30):
            pygame.draw.rect(surface, (80, 86, 110), pygame.Rect(leg - 6, rect.bottom, 12, 18))
        item = art.component_item(color, "parts" if item_kind == "parts" else "can", 50)
        spacing = 100
        shift = (t * 70 * speed) % spacing
        for x in range(int(rect.x - spacing + shift), rect.right - 30, spacing):
            if x >= rect.x - 4:
                surface.blit(item, (x, rect.y - 46))

    def draw_transport(self, surface, sy, plat_y, speed, hat):
        t = self.time
        stats = self.game.stats_cache.get(self.game.current_planet)
        comps = list(stats.recipe.keys()) if stats else ["parts"]
        belt = pygame.Rect(240, plat_y - 60, 520, 34)
        pygame.draw.rect(surface, (60, 66, 90), belt, border_radius=16)
        pygame.draw.rect(surface, theme.OUTLINE, belt, 4, border_radius=16)
        shift = (t * 80 * speed) % 120
        for x in range(int(belt.x - 120 + shift), belt.right - 40, 120):
            if x > belt.x:
                arrow = [(x, belt.centery - 10), (x + 26, belt.centery), (x, belt.centery + 10)]
                pygame.draw.polygon(surface, theme.YELLOW, arrow)
        for i, x in enumerate(range(int(belt.x - 170 + (t * 70 * speed) % 170), belt.right - 40, 170)):
            if x >= belt.x - 6:
                comp = comps[i % len(comps)]
                ccol = tuple(self.game.config.components.get(comp, {}).get("color", (200, 80, 80)))
                kind = "parts" if comp == "parts" else ("nose" if i % 2 else "can")
                surface.blit(art.component_item(ccol, kind, 56), (x, belt.y - 54))
        # worker pushing a cart back and forth
        cycle = (t * 0.25 * (1 if speed else 0)) % 2
        frac = cycle if cycle < 1 else 2 - cycle
        x = 230 + frac * 260
        flip = cycle >= 1
        cart = pygame.Rect(0, 0, 120, 50)
        cart.midbottom = (x + (70 if not flip else -70), plat_y - 8)
        pygame.draw.rect(surface, (230, 235, 245), cart, border_radius=10)
        pygame.draw.rect(surface, theme.OUTLINE, cart, 4, border_radius=10)
        for wx in (cart.x + 22, cart.right - 22):
            pygame.draw.circle(surface, (60, 60, 70), (wx, cart.bottom + 2), 12)
        if not flip:
            surface.blit(art.component_item((220, 70, 70), "parts", 44), (cart.x + 12, cart.y - 34))
            surface.blit(art.component_item((220, 70, 70), "nose", 44), (cart.x + 60, cart.y - 34))
        self._worker(surface, "walk", x, plat_y + 6, speed, hat, flip=flip)

    def draw_assembly(self, surface, sy, plat_y, speed, hat):
        t = self.time
        line = pygame.Rect(260, plat_y - 40, 480, 34)
        pygame.draw.rect(surface, (60, 66, 90), line, border_radius=14)
        for x in range(line.x + 20, line.right - 10, 44):
            pygame.draw.circle(surface, (150, 160, 190), (x, line.centery), 8)
        pygame.draw.rect(surface, theme.OUTLINE, line, 4, border_radius=14)
        rocket = pygame.transform.rotate(self.current_rocket_sprite(), -90)
        scale = 190 / max(1, rocket.get_width())
        rocket = pygame.transform.smoothscale(rocket, (int(rocket.get_width() * scale), int(rocket.get_height() * scale)))
        rr = rocket.get_rect(midbottom=(line.centerx, line.y + 4))
        surface.blit(rocket, rr)
        for side in (-1, 1):
            base = (line.centerx + side * 210, line.y)
            ang = math.sin(t * 4 + side) * 0.5 if speed else 0.2
            elbow = (base[0] + math.sin(ang) * 30 * side, base[1] - 90)
            hand = (elbow[0] - side * (60 + math.cos(t * 4) * 10 * speed), elbow[1] + 40 + math.sin(t * 6) * 10 * speed)
            pygame.draw.rect(surface, (70, 80, 110), pygame.Rect(base[0] - 30, base[1] - 20, 60, 24), border_radius=6)
            for a, b, w in ((base, elbow, 26), (elbow, hand, 20)):
                pygame.draw.line(surface, theme.OUTLINE, a, b, w + 8)
                pygame.draw.line(surface, (250, 190, 40), a, b, w)
            for jp in (base, elbow):
                pygame.draw.circle(surface, (90, 95, 110), (int(jp[0]), int(jp[1])), 16)
                pygame.draw.circle(surface, theme.OUTLINE, (int(jp[0]), int(jp[1])), 16, 4)
            pygame.draw.circle(surface, (200, 205, 220), (int(hand[0]), int(hand[1])), 12)
            if speed and int(t * 6 + side) % 4 == 0:
                surface.blit(soft_glow(26, (255, 240, 150), 200), (hand[0] - 26, hand[1] - 26), special_flags=pygame.BLEND_RGBA_ADD)
        self._worker(surface, "inspect", 205, plat_y + 6, speed, hat)
        self._worker(surface, "work", 760, plat_y + 6, speed, hat, flip=True, offset=0.3)
        # Progress bar for the rocket being assembled
        bar = pygame.Rect(line.centerx - 120, line.bottom + 4, 240, 18)
        progress_bar(surface, bar, self.game.factory.assembly_progress if self.game.factory.ready < 1 else 1.0, theme.GREEN)

    def draw_support(self, surface, fid, sy, plat_y, hat):
        t = self.time
        fcol = tuple(self.game.config.floors[fid]["color"])
        if fid == "robotics":
            for i in range(3):
                x = 260 + ((t * 40 + i * 160) % 480)
                bob = abs(math.sin(t * 6 + i)) * 8
                surface.blit(icons.icon("robot", 96), (x, plat_y - 100 - bob))
        elif fid == "propulsion":
            stand = pygame.Rect(400, plat_y - 160, 120, 160)
            pygame.draw.rect(surface, (90, 95, 120), stand, border_radius=10)
            pygame.draw.rect(surface, theme.OUTLINE, stand, 4, border_radius=10)
            surface.blit(icons.icon("engine", 120), (stand.right - 10, plat_y - 130))
            flame = icons.icon("flame", 90 + int(math.sin(t * 20) * 10))
            surface.blit(pygame.transform.rotate(flame, 90), (stand.right + 100, plat_y - 120))
        elif fid == "orbital":
            dish = pygame.transform.rotate(icons.icon("satellite", 140), math.sin(t) * 20)
            surface.blit(dish, dish.get_rect(center=(440, plat_y - 90)))
            for i in range(3):
                scr = pygame.Rect(560 + i * 70, plat_y - 120, 60, 48)
                pygame.draw.rect(surface, (30, 40, 60), scr, border_radius=6)
                pygame.draw.rect(surface, (80, 220, 255) if int(t * 3 + i) % 2 else (60, 160, 200), scr.inflate(-10, -10))
        else:
            for i in range(3):
                x = 330 + i * 120
                bubble = int((t * 40 + i * 20) % 40)
                surface.blit(icons.icon("flask", 90), (x, plat_y - 100))
                pygame.draw.circle(surface, lighten(fcol, 0.4), (x + 45, plat_y - 100 - bubble), 6)
            surface.blit(soft_glow(60, fcol, 160), (660, plat_y - 150), special_flags=pygame.BLEND_RGBA_ADD)
        self._worker(surface, "inspect", 230, plat_y + 6, 1, hat)

    def draw_pad_row(self, surface, ui, fid: str, sy: int, h: int) -> None:
        game = self.game
        factory = game.factory
        wall = tuple(game.shop.equipped_item("theme").get("color", (50, 90, 170)))
        surface.blit(art.floor_background(theme.WIDTH, h, darken(wall, 0.25), "launch"), (0, sy))
        plat_y = sy + h - 52
        stats = game.stats_cache.get(game.current_planet)
        floor = factory.floors[fid]
        # Mission control desk with screens
        desk = pygame.Rect(530, plat_y - 60, 200, 60)
        pygame.draw.rect(surface, (70, 80, 110), desk, border_radius=10)
        pygame.draw.rect(surface, theme.OUTLINE, desk, 4, border_radius=10)
        for i in range(3):
            scr = pygame.Rect(536 + i * 64, plat_y - 112, 58, 48)
            pygame.draw.rect(surface, (20, 30, 50), scr, border_radius=6)
            col = theme.GREEN_LIGHT if factory.ready >= 1 else (90, 140, 200)
            pygame.draw.rect(surface, col, scr.inflate(-12, -12), border_radius=4)
            pygame.draw.rect(surface, theme.OUTLINE, scr, 3, border_radius=6)
        self._worker(surface, "work" if factory.ready >= 1 else "idle", 735, plat_y + 6, 1, self.hat_color(), flip=True)
        self.floor_badges(surface, ui, fid, sy, h)
        if stats:
            info = f"{format_number(stats.capacity)} per launch | every {stats.interval:.1f}s"
            draw_text(surface, info, (176, sy + 124), 28, theme.OFF_WHITE, outline=2, max_width=340)
        if floor.manager_uid is None:
            btn = pygame.Rect(180, sy + 168, 160, 64)
            ready = factory.ready >= 1 and factory.countdown <= 0
            self.highlight_rects["launch_btn"] = btn
            if ui.button(surface, "launch_btn", btn, "LAUNCH", theme.RED if ready else theme.GREY, size=34,
                         disabled=not ready):
                if game.manual_launch():
                    self.app.audio.play("tap")
        else:
            bar = pygame.Rect(180, sy + 186, 240, 24)
            frac = min(1.0, factory.pad_timer / stats.interval) if stats else 0.0
            progress_bar(surface, bar, frac, theme.CYAN)
            draw_text(surface, "AUTO", (bar.right + 14, bar.centery), 30, theme.GREEN_LIGHT, anchor="midleft", outline=3)

    def draw_locked(self, surface, ui, fid: str, sy: int, h: int) -> None:
        game = self.game
        fdef = game.config.floors[fid]
        factory = game.factory
        bg = art.floor_background(theme.WIDTH, h, (70, 72, 85), "locked")
        surface.blit(bg, (0, sy))
        surface.blit(overlay((theme.WIDTH - 160, h - 36), (10, 10, 20, 120)), (150, sy + 18))
        for x in range(150, theme.WIDTH, 80):
            pygame.draw.polygon(surface, theme.YELLOW, [(x, sy + h - 30), (x + 40, sy + h - 30), (x + 20, sy + h - 18), (x - 20, sy + h - 18)])
        surface.blit(icons.icon("lock", 90), (190, sy + 60))
        draw_text(surface, fdef["name"], (300, sy + 60), 44, theme.WHITE, outline=4, max_width=440)
        needed_by = [r["name"] for r in game.config.rocket_list
                     if game.config.component_for(fdef.get("component", ""), factory.planet_id) in factory.resolved_recipe(r["id"])
                     and (not r.get("planet") or r["planet"] == factory.planet_id)] if fdef["kind"] == "producer" else []
        desc = ("Needed by: " + ", ".join(needed_by[:2])) if needed_by else fdef["description"]
        lines = desc[:70] + ("..." if len(desc) > 70 else "")
        draw_text(surface, lines, (300, sy + 116), 26, theme.OFF_WHITE, kind="body", max_width=440)
        cost = factory.unlock_cost(fid, game.cost_mult())
        btn = pygame.Rect(theme.WIDTH - 300, sy + 96, 276, 112)
        self.highlight_rects[f"unlock:{fid}"] = btn
        if ui.button(surface, f"unlock:{fid}", btn, "Unlock", theme.ORANGE if cost <= game.credits else theme.GREY,
                     size=40, sublabel=game.describe_money(cost)):
            if game.unlock_floor(fid):
                self.app.audio.play("unlock")
                self.app.particles.emit("confetti", 540, sy + self.scroll.offset + 150, 60, spread=math.pi,
                                        speed=600, life=1.4, size=16, gravity=500)
            else:
                self.app.audio.play("error")
