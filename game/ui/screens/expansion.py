"""Expansion (floors, workforce, planets shortcut) and Space Legacy prestige screens."""
from __future__ import annotations

import math

import pygame

from game.core.numformat import format_number
from game.prestige.prestige_system import KEEPS, RESETS
from game.rendering import icons
from game.rendering.draw import draw_paragraph, draw_text
from game.ui import theme
from game.ui.screens.base import ConfirmDialog, Screen


class ExpansionScreen(Screen):
    nav_id = "expansion"

    def draw(self, surface, ui, dt):
        content = self.page_frame(surface, ui, "Expansion", "map")
        self.tabs(surface, ui, pygame.Rect(content.x, content.y, content.width, 80),
                  ["Floors", "Workforce", "Planets", "Legacy"])
        area = pygame.Rect(content.x, content.y + 100, content.width, content.height - 100)
        if self.tab == 0:
            self.draw_floors(surface, ui, area, dt)
        elif self.tab == 1:
            self.draw_workforce(surface, ui, area, dt)
        elif self.tab == 2:
            self.app.open("planets")
            self.tab = 0
        else:
            self.app.open("prestige")
            self.tab = 0

    def draw_floors(self, surface, ui, area, dt):
        game = self.game
        factory = game.factory
        ids = [f for f in factory.ordered_floor_ids()]
        row_h = 170
        y = self.begin_scroll(surface, ui, area, len(ids) * (row_h + 10) + 20, dt)
        for fid in ids:
            fdef = game.config.floors[fid]
            floor = factory.floors[fid]
            r = pygame.Rect(area.x, y, area.width - 16, row_h)
            if r.bottom > area.top and r.top < area.bottom:
                self.card(surface, r, border=theme.GREEN if floor.level > 0 else (90, 130, 210))
                surface.blit(icons.icon(fdef.get("icon", "gear"), 100), (r.x + 16, r.y + 34))
                draw_text(surface, fdef["name"], (r.x + 140, r.y + 16), 36, theme.WHITE, outline=3, max_width=r.width - 420)
                draw_paragraph(surface, fdef["description"], pygame.Rect(r.x + 140, r.y + 60, r.width - 420, 100), 24)
                btn = pygame.Rect(r.right - 250, r.y + 34, 230, 100)
                if floor.level > 0:
                    if ui.button(surface, f"exf:{fid}", btn, f"Lv. {floor.level}", theme.BLUE, size=36, sublabel="Details"):
                        self.app.open_floor_panel(fid)
                elif self.cost_button(surface, ui, f"exf:{fid}", btn, "Unlock", factory.unlock_cost(fid, game.cost_mult()),
                                      color=theme.ORANGE):
                    if game.unlock_floor(fid):
                        self.app.audio.play("unlock")
            y += row_h + 10
        self.end_scroll(surface, ui, area)

    def draw_workforce(self, surface, ui, area, dt):
        game = self.game
        factory = game.factory
        items = game.config.workforce_list
        row_h = 190
        y = self.begin_scroll(surface, ui, area, len(items) * (row_h + 10) + 140, dt)
        draw_paragraph(surface, f"Upgrades for your {game.config.planets[game.current_planet]['name']} crew. Each "
                                "planet's workforce is trained separately.",
                       pygame.Rect(area.x + 10, y, area.width - 30, 100), 28, theme.TEXT_DIM)
        y += 100
        for wdef in items:
            level = factory.workforce[wdef["id"]]
            r = pygame.Rect(area.x, y, area.width - 16, row_h)
            if r.bottom > area.top and r.top < area.bottom:
                self.card(surface, r)
                surface.blit(icons.icon(wdef["icon"], 110), (r.x + 16, r.y + 40))
                draw_text(surface, f"{wdef['name']}  Lv. {level}/{wdef['max_level']}", (r.x + 150, r.y + 18), 36,
                          theme.WHITE, outline=3, max_width=r.width - 420)
                draw_paragraph(surface, wdef["description"], pygame.Rect(r.x + 150, r.y + 66, r.width - 420, 60), 26)
                total = wdef["per_level"] * level * 100
                draw_text(surface, f"Current bonus: +{total:.0f}%", (r.x + 150, r.bottom - 46), 28, theme.GREEN_LIGHT,
                          outline=2)
                btn = pygame.Rect(r.right - 250, r.y + 44, 230, 104)
                if level >= wdef["max_level"]:
                    ui.button(surface, f"wf:{wdef['id']}", btn, "MAX", theme.GREY, size=36)
                elif self.cost_button(surface, ui, f"wf:{wdef['id']}", btn, "Upgrade", game.workforce_cost(wdef["id"])):
                    if game.buy_workforce(wdef["id"]):
                        self.app.audio.play("upgrade")
            y += row_h + 10
        self.end_scroll(surface, ui, area)


class PrestigeScreen(Screen):
    nav_id = "expansion"

    def draw(self, surface, ui, dt):
        game = self.game
        content = self.page_frame(surface, ui, "Space Legacy", "star")
        unlocked, why = game.feature_unlocked("prestige")
        if not unlocked:
            draw_paragraph(surface, why + ".\n\nSpace Legacy lets you restart your empire in exchange for Legacy Stars "
                                          "that permanently boost every future run.",
                           pygame.Rect(content.x + 40, content.y + 80, content.width - 80, 600), 40, align="center")
            return
        p = game.prestige
        upgrades = list(game.config.legacy_upgrades.values())
        y = self.begin_scroll(surface, ui, content, 800 + len(upgrades) * 170, dt)
        top = pygame.Rect(content.x, y, content.width - 16, 340)
        self.card(surface, top, (60, 50, 110), theme.GOLD)
        surface.blit(icons.icon("star", 120), (top.x + 20, top.y + 20))
        draw_text(surface, f"{format_number(p.stars)} Legacy Stars", (top.x + 160, top.y + 24), 48, theme.GOLD, outline=4)
        draw_text(surface, f"Unspent stars boost production: x{p.star_multiplier():.2f}", (top.x + 160, top.y + 84), 30,
                  theme.WHITE, kind="body")
        est = p.estimated_stars()
        draw_text(surface, f"Reset now for +{format_number(est)} stars", (top.x + 160, top.y + 130), 36,
                  theme.GREEN_LIGHT if est else theme.TEXT_DIM, outline=3)
        draw_text(surface, f"This run earned {game.describe_money(game.run_earned)}", (top.x + 160, top.y + 176), 28,
                  theme.OFF_WHITE, kind="body")
        ok, reason = p.can_prestige()
        btn = pygame.Rect(top.centerx - 260, top.bottom - 104, 520, 90)
        if ok:
            if ui.button(surface, "do_prestige", btn, f"Reset for {format_number(est)} stars", theme.GOLD, size=38):
                self.app.push(ConfirmDialog(
                    self.app, "Space Legacy?",
                    f"You will gain {format_number(est)} Legacy Stars. Credits, floors, planets and rockets reset. "
                    "Gems, managers, research and achievements are kept.", self.do_prestige, "Reset!", danger=True))
        else:
            ui.button(surface, "do_prestige", btn, "Not yet", theme.GREY, size=34)
            draw_text(surface, reason, (top.centerx + 60, btn.y - 2), 24, theme.TEXT_DIM, anchor="midbottom", kind="body",
                      max_width=top.width - 200)
        y += 360
        half = (content.width - 40) // 2
        for i, (title, items, color) in enumerate((("What resets", RESETS, theme.RED), ("What you keep", KEEPS, theme.GREEN))):
            r = pygame.Rect(content.x + i * (half + 10), y, half, 400)
            self.card(surface, r, border=color)
            draw_text(surface, title, (r.x + 20, r.y + 16), 34, theme.WHITE, outline=3)
            yy = r.y + 66
            for item in items:
                yy += draw_paragraph(surface, "- " + item, pygame.Rect(r.x + 20, yy, r.width - 40, 80), 24) + 4
        y += 420
        draw_text(surface, "Legacy Upgrades", (content.x + 10, y), 40, theme.WHITE, outline=3)
        y += 60
        for u in upgrades:
            level = p.levels[u["id"]]
            r = pygame.Rect(content.x, y, content.width - 16, 160)
            if r.bottom > content.top and r.top < content.bottom:
                self.card(surface, r)
                surface.blit(icons.icon(u["icon"], 100), (r.x + 16, r.y + 30))
                draw_text(surface, f"{u['name']}  Lv. {level}/{u['max_level']}", (r.x + 140, r.y + 20), 34, theme.WHITE,
                          outline=3, max_width=r.width - 420)
                draw_paragraph(surface, u["description"], pygame.Rect(r.x + 140, r.y + 66, r.width - 420, 80), 26)
                btn = pygame.Rect(r.right - 250, r.y + 30, 230, 100)
                if level >= u["max_level"]:
                    ui.button(surface, f"lg:{u['id']}", btn, "MAX", theme.GREY, size=34)
                elif self.cost_button(surface, ui, f"lg:{u['id']}", btn, "Buy", p.upgrade_cost(u["id"]), "stars",
                                      color=theme.GOLD):
                    if p.buy_upgrade(u["id"]):
                        self.app.audio.play("upgrade")
            y += 170
        self.end_scroll(surface, ui, content)

    def do_prestige(self):
        stars = self.game.prestige.prestige()
        if stars:
            self.app.audio.play("launch")
            self.app.factory_view.scroll.scroll_to(0)
            self.app.particles.emit("star", theme.WIDTH / 2, theme.HEIGHT / 2, 60, spread=math.pi, speed=900, life=1.8,
                                    size=44, gravity=300, screen=True)
            self.app.hud.toast(f"Space Legacy! +{format_number(stars)} stars")
            self.app.save_now()
