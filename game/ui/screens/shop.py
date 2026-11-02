"""Simulated in-game Shop (gems only - no real money)."""
from __future__ import annotations

import pygame

from game.core.numformat import format_duration
from game.rendering import art, icons
from game.rendering.draw import draw_paragraph, draw_text
from game.ui import theme
from game.ui.screens.base import Screen


class ShopScreen(Screen):
    nav_id = "shop"

    def draw(self, surface, ui, dt):
        content = self.page_frame(surface, ui, "Shop", "cart")
        labels = ["Boosts", "Cosmetics", "Free Gems"]
        if self.game.store.enabled:
            labels.append("Store")
        self.tabs(surface, ui, pygame.Rect(content.x, content.y, content.width, 80), labels)
        area = pygame.Rect(content.x, content.y + 100, content.width, content.height - 100)
        if self.tab == 3 and self.game.store.enabled:
            self.draw_store(surface, ui, area, dt)
        elif self.tab == 0:
            self.draw_boosts(surface, ui, area, dt)
        elif self.tab == 1:
            self.draw_cosmetics(surface, ui, area, dt)
        else:
            self.draw_free(surface, ui, area, dt)

    def draw_boosts(self, surface, ui, area, dt):
        game = self.game
        boosts = list(game.config.boosts.values())
        row_h = 190
        y = self.begin_scroll(surface, ui, area, len(boosts) * (row_h + 12) + 160, dt)
        draw_paragraph(surface, "Optional helpers bought with gems. Gems are earned by playing - there are no real-money "
                                "purchases in this game.", pygame.Rect(area.x + 10, y, area.width - 30, 100), 28,
                       theme.TEXT_DIM)
        y += 100
        income = game.total_auto_income()
        for boost in boosts:
            r = pygame.Rect(area.x, y, area.width - 16, row_h)
            if r.bottom > area.top and r.top < area.bottom:
                self.card(surface, r)
                surface.blit(icons.icon(boost["icon"], 120), (r.x + 20, r.y + 34))
                draw_text(surface, boost["name"], (r.x + 170, r.y + 18), 40, theme.WHITE, outline=3)
                desc = boost["description"]
                if "warp_hours" in boost:
                    desc += f" (about {game.describe_money(income * boost['warp_hours'] * 3600)})"
                draw_paragraph(surface, desc, pygame.Rect(r.x + 170, r.y + 70, r.width - 450, 100), 28)
                active = next((b for b in game.shop.boosts if b["id"] == boost["id"]), None)
                if active:
                    draw_text(surface, f"Active: {format_duration(active['remaining'])}", (r.x + 170, r.bottom - 44), 28,
                              theme.YELLOW, outline=2)
                btn = pygame.Rect(r.right - 250, r.y + 44, 230, 104)
                if self.cost_button(surface, ui, f"boost:{boost['id']}", btn, "Buy", boost["cost"], "gems",
                                    color=theme.PURPLE):
                    if game.shop.buy_boost(boost["id"]):
                        self.app.audio.play("coin")
            y += row_h + 12
        self.end_scroll(surface, ui, area)

    def draw_cosmetics(self, surface, ui, area, dt):
        game = self.game
        items = [c for c in game.config.cosmetic_list
                 if c["cost"] > 0 or c.get("requires_legacy") or c.get("store_only")]
        row_h = 150
        y = self.begin_scroll(surface, ui, area, len(items) * (row_h + 10) + 20, dt)
        slot_names = {"paint": "Rocket paint", "decal": "Rocket decal", "exhaust": "Exhaust color",
                      "effect": "Launch effect", "theme": "Factory theme", "hat": "Worker hats"}
        for cos in items:
            r = pygame.Rect(area.x, y, area.width - 16, row_h)
            if r.bottom > area.top and r.top < area.bottom:
                self.card(surface, r)
                self.draw_preview(surface, cos, pygame.Rect(r.x + 14, r.y + 14, 122, 122))
                draw_text(surface, cos["name"], (r.x + 160, r.y + 22), 38, theme.WHITE, outline=3)
                draw_text(surface, slot_names[cos["slot"]], (r.x + 160, r.y + 76), 28, theme.TEXT_DIM, kind="body")
                btn = pygame.Rect(r.right - 250, r.y + 24, 230, 100)
                owned = game.shop.is_owned(cos["id"])
                equipped = game.shop.equipped.get(cos["slot"]) == cos["id"]
                if equipped:
                    ui.button(surface, f"cos:{cos['id']}", btn, "Equipped", theme.GREEN, size=32)
                elif owned:
                    if ui.button(surface, f"cos:{cos['id']}", btn, "Equip", theme.BLUE, size=36):
                        game.shop.equip(cos["id"])
                        self.app.audio.play("click")
                elif cos.get("requires_legacy"):
                    ui.button(surface, f"cos:{cos['id']}", btn, "Legacy", theme.GREY, size=32, sublabel="Space Legacy")
                elif cos.get("store_only"):
                    if ui.button(surface, f"cos:{cos['id']}", btn, "Exclusive", theme.ORANGE, size=32, sublabel="See Store"):
                        self.tab = 3
                        self.scroll.scroll_to(0)
                elif self.cost_button(surface, ui, f"cos:{cos['id']}", btn, "Buy", cos["cost"], "gems", color=theme.PURPLE):
                    if game.shop.buy_cosmetic(cos["id"]):
                        self.app.audio.play("unlock")
            y += row_h + 10
        self.end_scroll(surface, ui, area)

    def draw_store(self, surface, ui, area, dt):
        game = self.game
        store = game.store
        products = store.products
        row_h = 200
        banner_h = 130 if store.test_mode else 20
        y = self.begin_scroll(surface, ui, area, banner_h + len(products) * (row_h + 12) + 40, dt)
        if store.test_mode:
            r = pygame.Rect(area.x, y, area.width - 16, 110)
            self.card(surface, r, (90, 70, 20), theme.YELLOW)
            draw_paragraph(surface, "TEST MODE - purchases are simulated and no real money is charged. "
                                    "Real payments get connected when the game is published on a store.",
                           pygame.Rect(r.x + 20, r.y + 14, r.width - 40, 90), 26, theme.WHITE)
            y += banner_h
        for product in products:
            r = pygame.Rect(area.x, y, area.width - 16, row_h)
            if r.bottom > area.top and r.top < area.bottom:
                owned = product.get("one_time") and product["id"] in store.owned
                special = product.get("one_time")
                self.card(surface, r, (70, 50, 120) if special else (36, 58, 112),
                          theme.GOLD if special else (90, 130, 210))
                surface.blit(icons.icon(product.get("icon", "gem"), 120), (r.x + 20, r.y + 40))
                draw_text(surface, product["name"], (r.x + 170, r.y + 18), 40, theme.WHITE, outline=3,
                          max_width=r.width - 450)
                if product.get("tag"):
                    tag = product["tag"]
                    tw = theme.fonts.get(24).size(tag)[0] + 26
                    trect = pygame.Rect(r.x + 170, r.y + 66, tw, 36)
                    pygame.draw.rect(surface, theme.RED, trect, border_radius=14)
                    draw_text(surface, tag, trect.center, 24, theme.WHITE, anchor="center", outline=2)
                draw_paragraph(surface, product["description"], pygame.Rect(r.x + 170, r.y + 110, r.width - 450, 90), 26)
                btn = pygame.Rect(r.right - 250, r.y + 48, 230, 104)
                if owned:
                    ui.button(surface, f"iap:{product['id']}", btn, "Owned", theme.GREY, size=34, icon="check", icon_size=36)
                elif ui.button(surface, f"iap:{product['id']}", btn, store.price_text(product), theme.GREEN, size=40):
                    self.app.confirm_purchase(product)
            y += row_h + 12
        self.end_scroll(surface, ui, area)

    def draw_preview(self, surface, cos, rect):
        pygame.draw.rect(surface, (20, 30, 60), rect, border_radius=18)
        slot = cos["slot"]
        if slot in ("paint", "decal"):
            accent = tuple(cos.get("color", (225, 60, 60)))
            img = art.rocket_sprite(rect.height - 10, accent=accent if slot == "paint" else (225, 60, 60), fins=3,
                                    decal=cos["id"] if slot == "decal" else "decal_none")
            surface.blit(img, img.get_rect(center=rect.center))
        elif slot == "exhaust":
            surface.blit(pygame.transform.rotate(icons.icon("flame", 100), 180), (rect.x + 11, rect.y + 11))
            pygame.draw.circle(surface, tuple(cos["color"]), rect.center, 26)
        elif slot == "effect":
            surface.blit(icons.icon("star" if "sparkle" in cos["id"] else "gift", 90), (rect.x + 16, rect.y + 16))
        elif slot == "theme":
            pygame.draw.rect(surface, tuple(cos["color"]), rect.inflate(-20, -20), border_radius=12)
            surface.blit(icons.icon("home", 70), (rect.x + 26, rect.y + 26))
        else:
            surface.blit(icons.manager_portrait({"skin": (255, 214, 170), "hair": (90, 60, 40), "shirt": (70, 130, 220)},
                                                110, tuple(cos.get("color", theme.YELLOW))), (rect.x + 6, rect.y + 6))

    def draw_free(self, surface, ui, area, dt):
        game = self.game
        now = self.app.now()
        y = area.y
        cards = [
            ("gift", "Free Gift", "A free gift every 4 hours: gems and credits.",
             "Claim" if game.missions.gift_ready(now) else format_duration(game.missions.gift_time_left(now)),
             game.missions.gift_ready(now), lambda: self.app.open("rewards")),
            ("calendar", "Daily Reward", "Log in every day for a growing streak of rewards.",
             "Claim" if game.missions.can_claim_login(now) else "Tomorrow", game.missions.can_claim_login(now),
             lambda: self.app.open("daily")),
            ("clipboard", "Missions", "Complete missions and daily missions for gems and research.",
             "Open", True, lambda: self.app.open("missions")),
            ("trophy", "Achievements", "Every achievement tier pays out gems.", "Open", True,
             lambda: self.app.open("missions", tab=1)),
        ]
        for icon_name, title, desc, label, enabled, action in cards:
            r = pygame.Rect(area.x, y, area.width - 16, 190)
            self.card(surface, r)
            surface.blit(icons.icon(icon_name, 120), (r.x + 20, r.y + 34))
            draw_text(surface, title, (r.x + 170, r.y + 20), 40, theme.WHITE, outline=3)
            draw_paragraph(surface, desc, pygame.Rect(r.x + 170, r.y + 72, r.width - 450, 100), 28)
            btn = pygame.Rect(r.right - 250, r.y + 44, 230, 104)
            if ui.button(surface, f"free:{title}", btn, label, theme.GREEN if enabled else theme.GREY, size=36):
                action()
            y += 204
