"""Heads-up display: resource bar, mission panel, side buttons, bottom navigation."""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from game.core.numformat import format_number
from game.rendering import art, icons
from game.rendering.draw import darken, draw_text, gradient_surface, panel, progress_bar
from game.ui import theme

if TYPE_CHECKING:  # pragma: no cover
    from game.app import App

NAV_ITEMS = [("shop", "Shop", "cart"), ("managers", "Managers", "manager"), ("rockets", "Rockets", "rocket"),
             ("research", "Research", "flask"), ("expansion", "Expansion", "map")]
BUY_AMOUNTS = ["1", "10", "25", "max"]


class HUD:
    def __init__(self, app: "App"):
        self.app = app
        self.display_credits = 0.0
        self.toasts: list[dict] = []
        self.highlight_rects: dict[str, pygame.Rect] = {}

    @property
    def game(self):
        return self.app.game

    def toast(self, text: str, color=theme.WHITE) -> None:
        if self.toasts and self.toasts[-1]["text"] == text:
            self.toasts[-1]["life"] = 2.5
            return
        self.toasts.append({"text": text, "life": 2.5, "color": color})
        self.toasts = self.toasts[-3:]

    def update(self, dt: float) -> None:
        target = self.game.credits
        # Smoothly count towards the real value for a satisfying ticking effect.
        if abs(target - self.display_credits) < 1e-9 or target < self.display_credits:
            self.display_credits = target
        else:
            self.display_credits += (target - self.display_credits) * min(1.0, dt * 8)
            if target - self.display_credits < max(0.01, target * 1e-4):
                self.display_credits = target
        for t in self.toasts:
            t["life"] -= dt
        self.toasts = [t for t in self.toasts if t["life"] > 0]

    # ------------------------------------------------------------------ top bar
    def draw_top_bar(self, surface: pygame.Surface, ui) -> None:
        game = self.game
        bar = pygame.Rect(0, 0, theme.WIDTH, theme.TOP_BAR_H)
        shade = gradient_surface(bar.size, (10, 20, 50), (10, 20, 50))
        shade = shade.copy()
        shade.set_alpha(150)
        surface.blit(shade, bar)
        if ui.icon_button(surface, "settings", pygame.Rect(16, 14, 96, 92), "settings"):
            self.app.open("settings")
        sci = game.settings.get("scientific", False)
        pills = [
            ("coin", format_number(self.display_credits, scientific=sci), pygame.Rect(130, 20, 320, 80), "shop_boosts"),
            ("gem", format_number(game.gems, scientific=sci), pygame.Rect(470, 20, 280, 80), "shop_free"),
            ("rp", format_number(game.rp, scientific=sci), pygame.Rect(770, 20, 294, 80), "research"),
        ]
        for icon_name, text, rect, target in pills:
            panel(surface, rect, (16, 28, 60), (70, 100, 160), radius=30, border=3, shadow=4)
            ic = icons.icon(icon_name, 92)
            surface.blit(ic, (rect.x - 22, rect.centery - 46))
            draw_text(surface, text, (rect.x + 78 + (rect.width - 150) // 2, rect.centery), 46, theme.WHITE,
                      anchor="center", outline=3, max_width=rect.width - 150)
            plus = pygame.Rect(rect.right - 66, rect.y + 10, 58, 58)
            if ui.button(surface, f"plus:{icon_name}", plus, "", theme.GREEN, icon="plus", icon_size=34, radius=14):
                if target == "research":
                    self.app.open("research")
                elif target == "shop_free":
                    self.app.open("shop", tab=3 if game.store.enabled else 2)
                else:
                    self.app.open("shop", tab=0)

    # ------------------------------------------------------------------ world overlay (scrolls with the sky)
    def draw_world_overlay(self, surface: pygame.Surface, ui, top: float) -> None:
        game = self.game
        surface.blit(art.logo(330), (8, top + 112))
        # Mission panel
        mission = game.missions.current_main()
        mrect = pygame.Rect(340, top + 128, 520, 112)
        self.highlight_rects["mission"] = mrect
        panel(surface, mrect, (24, 40, 84), (110, 150, 230), radius=26, border=4, shadow=6)
        surface.blit(icons.icon("rocket", 84), (mrect.x + 10, mrect.y + 14))
        if mission:
            progress, target = game.missions.mission_progress(mission)
            draw_text(surface, mission["text"], (mrect.x + 100, mrect.y + 14), 34, theme.WHITE, outline=3,
                      max_width=310)
            bar = pygame.Rect(mrect.x + 100, mrect.y + 66, 300, 30)
            progress_bar(surface, bar, progress / target)
            draw_text(surface, f"{format_number(progress)}/{format_number(target)}", bar.center, 24,
                      theme.WHITE, anchor="center", outline=2)
            complete = progress >= target
            chest = pygame.Rect(mrect.right - 104, mrect.y + 10, 92, 92)
            if complete:
                bounce = abs(math.sin(ui.time * 5)) * 10
                chest = chest.move(0, -bounce)
                if ui.button(surface, "claim_main", chest, "Claim", theme.ORANGE, size=28, icon=None):
                    if game.missions.claim_main():
                        self.app.audio.play("achievement")
                        self.app.particles.emit("gem", mrect.centerx, mrect.centery + self.app.factory_view.scroll.offset,
                                                12, spread=math.pi, speed=420, life=1.0, size=36, gravity=700)
            else:
                surface.blit(icons.icon("gift", 84), (chest.x + 4, chest.y + 4))
                if ui.region("mission_panel", mrect):
                    self.app.open("missions")
        else:
            draw_text(surface, "All missions complete!", (mrect.x + 100, mrect.centery), 32, theme.WHITE,
                      anchor="midleft", outline=3)
        # Side buttons
        now = self.app.now()
        side = [("missions", "Missions", "clipboard", game.missions.claimable_count(now) > 0),
                ("rewards", "Rewards", "gift", game.missions.gift_ready(now)),
                ("daily", "Daily", "calendar", game.missions.can_claim_login(now)),
                ("planets", "Planets", "planet", False)]
        for i, (target, label, icon_name, badge) in enumerate(side):
            rect = pygame.Rect(theme.WIDTH - 140, top + 130 + i * 128, 124, 118)
            self.highlight_rects[f"side:{target}"] = rect
            if ui.icon_button(surface, f"side:{target}", rect, icon_name, label, badge=badge, label_size=28):
                self.app.open(target)

    # ------------------------------------------------------------------ bottom
    def draw_bottom(self, surface: pygame.Surface, ui, selected: str | None, page_open: bool = False) -> None:
        game = self.game
        nav = pygame.Rect(0, theme.HEIGHT - theme.NAV_H, theme.WIDTH, theme.NAV_H)
        surface.blit(gradient_surface(nav.size, (40, 60, 120), (16, 26, 60)), nav)
        pygame.draw.line(surface, (120, 160, 230), (0, nav.y), (theme.WIDTH, nav.y), 4)
        width = theme.WIDTH / len(NAV_ITEMS)
        shop_badge = False
        for i, (target, label, icon_name) in enumerate(NAV_ITEMS):
            rect = pygame.Rect(int(i * width) + 8, nav.y + 18, int(width) - 16, nav.height - 36)
            badge = False
            if target == "managers":
                badge = self.idle_floor_without_manager() and self.can_afford_cheapest_manager()
            elif target == "research":
                badge = game.feature_unlocked("research")[0] and self.research_affordable()
            elif target == "shop":
                badge = shop_badge or game.missions.gift_ready(self.app.now())
            self.highlight_rects[f"nav:{target}"] = rect
            if ui.icon_button(surface, f"nav:{target}", rect, icon_name, label, badge=badge,
                              selected=(selected == target), label_size=32):
                self.app.open(target)
        if page_open:
            return
        # Buy amount toggle + income pill floating above the nav bar
        amount = game.settings.get("buy_amount", "1")
        brect = pygame.Rect(theme.WIDTH - 196, nav.y - 96, 180, 82)
        label = "MAX" if amount == "max" else f"x{amount}"
        self.highlight_rects["buy_amount"] = brect
        if ui.button(surface, "buy_amount", brect, f"Buy {label}", theme.BLUE, size=36):
            idx = (BUY_AMOUNTS.index(amount) + 1) % len(BUY_AMOUNTS)
            game.settings["buy_amount"] = BUY_AMOUNTS[idx]
        income = game.total_income()
        irect = pygame.Rect(16, nav.y - 90, 380, 72)
        panel(surface, irect, (16, 28, 60), (90, 200, 90), radius=30, border=3, shadow=4)
        surface.blit(icons.icon("coin", 56), (irect.x + 10, irect.centery - 28))
        draw_text(surface, game.describe_money(income) + "/s", (irect.x + 76, irect.centery), 38,
                  theme.GREEN_LIGHT, anchor="midleft", outline=3, max_width=290)
        if ui.region("income_pill", irect):
            self.app.open("statistics")
        # Active boosts indicator
        x = irect.right + 12
        for boost in game.shop.boosts:
            r = pygame.Rect(x, nav.y - 86, 64, 64)
            panel(surface, r, (60, 40, 110), theme.YELLOW, radius=18, border=3, shadow=3)
            surface.blit(icons.icon("bolt", 44), (r.x + 10, r.y + 6))
            mins = int(boost["remaining"] // 60)
            draw_text(surface, f"{mins}m", (r.centerx, r.bottom - 4), 22, theme.WHITE, anchor="midbottom", outline=2)
            x += 72

    def idle_floor_without_manager(self) -> bool:
        factory = self.game.factory
        for fid, floor in factory.floors.items():
            if floor.level > 0 and floor.manager_uid is None and self.game.config.floors[fid]["kind"] != "support":
                return True
        return False

    def can_afford_cheapest_manager(self) -> bool:
        game = self.game
        for mdef in game.config.manager_list:
            if mdef["rarity"] == "common":
                cost, _ = game.managers.hire_cost(mdef["id"])
                if game.credits >= cost:
                    return True
        free = [m for m in game.managers.instances if m.planet is None]
        return bool(free)

    def research_affordable(self) -> bool:
        game = self.game
        return any(game.research.state(r["id"]) == "available" and game.rp >= r["cost"]
                   for r in game.config.research_list)

    def draw_toasts(self, surface: pygame.Surface, menu_open: bool = False) -> None:
        # Over the factory: above the bottom bar. With a menu open: over the top bar so buttons stay visible.
        y = 24 if menu_open else theme.HEIGHT - theme.NAV_H - 190 - 80 * (len(self.toasts) - 1)
        for t in self.toasts:
            alpha = min(1.0, t["life"] / 0.4)
            font_size = 36
            w = theme.fonts.get(font_size).size(t["text"])[0] + 60
            rect = pygame.Rect(0, 0, min(theme.WIDTH - 60, w), 70)
            rect.midtop = (theme.WIDTH // 2, y)
            panel(surface, rect, darken(theme.NAVY, 0.2), theme.YELLOW, radius=30, border=3, shadow=4,
                  alpha=int(255 * alpha))
            draw_text(surface, t["text"], rect.center, font_size, t["color"], anchor="center", outline=3,
                      max_width=rect.width - 30)
            y += 80
