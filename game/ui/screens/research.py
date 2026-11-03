"""Research tree screen."""
from __future__ import annotations

import pygame

from game.core.numformat import format_number
from game.rendering import icons
from game.rendering.draw import draw_paragraph, draw_text, panel
from game.ui import theme
from game.ui.screens.base import Screen

CATEGORY_COLORS = {"Production": (90, 170, 90), "Transportation": (230, 150, 50), "Rocket Engineering": (220, 80, 80),
                   "Automation": (120, 130, 230), "Energy Efficiency": (230, 200, 60),
                   "Planetary Expansion": (80, 180, 220), "Advanced Materials": (180, 110, 230)}


class ResearchScreen(Screen):
    nav_id = "research"

    def draw(self, surface, ui, dt):
        game = self.game
        content = self.page_frame(surface, ui, "Research", "flask")
        unlocked, why = game.feature_unlocked("research")
        if not unlocked:
            draw_paragraph(surface, why + ".\n\nResearch lets you spend Research Points (earned from launches, missions "
                                          "and achievements) on permanent technology upgrades.",
                           pygame.Rect(content.x + 40, content.y + 80, content.width - 80, 600), 40, align="center")
            return
        top = pygame.Rect(content.x, content.y, content.width, 90)
        self.card(surface, top)
        surface.blit(icons.icon("rp", 70), (top.x + 16, top.y + 10))
        draw_text(surface, f"{format_number(game.rp)} Research Points", (top.x + 100, top.centery), 40, theme.WHITE,
                  anchor="midleft", outline=3)
        done = len(game.research.done)
        draw_text(surface, f"{done}/{len(game.config.research_list)} done", (top.right - 20, top.centery), 32,
                  theme.GREEN_LIGHT, anchor="midright", outline=2)
        area = pygame.Rect(content.x, content.y + 110, content.width, content.height - 110)
        cats = game.config.research_categories
        card_w = (area.width - 40) // 2
        card_h = 260
        heights = []
        for cat in cats:
            n = sum(1 for r in game.config.research_list if r["category"] == cat)
            heights.append(70 + ((n + 1) // 2) * (card_h + 14))
        y = self.begin_scroll(surface, ui, area, sum(heights) + 20, dt)
        for cat, h in zip(cats, heights):
            color = CATEGORY_COLORS.get(cat, theme.BLUE)
            if y + h > area.top and y < area.bottom:
                hdr = pygame.Rect(area.x, y + 6, area.width - 16, 56)
                panel(surface, hdr, color, (255, 255, 255), radius=20, border=3, shadow=3)
                draw_text(surface, cat, (hdr.x + 20, hdr.centery), 36, theme.WHITE, anchor="midleft", outline=3)
            yy = y + 70
            nodes = [r for r in game.config.research_list if r["category"] == cat]
            for i, node in enumerate(nodes):
                r = pygame.Rect(area.x + (i % 2) * (card_w + 14), yy + (i // 2) * (card_h + 14), card_w, card_h)
                if r.bottom > area.top and r.top < area.bottom:
                    self.draw_node(surface, ui, node, r, color)
            y += h
        self.end_scroll(surface, ui, area)

    def draw_node(self, surface, ui, node, r, color):
        game = self.game
        state = game.research.state(node["id"])
        border = theme.GREEN if state == "done" else (color if state == "available" else (80, 90, 110))
        bg = (40, 70, 60) if state == "done" else ((36, 58, 112) if state == "available" else (40, 44, 60))
        self.card(surface, r, bg, border)
        surface.blit(icons.icon(node.get("icon", "flask"), 70), (r.x + 14, r.y + 14))
        draw_paragraph(surface, node["name"], pygame.Rect(r.x + 94, r.y + 14, r.width - 104, 80), 30, theme.WHITE,
                       kind="title", line_gap=0)
        draw_paragraph(surface, node["description"], pygame.Rect(r.x + 16, r.y + 98, r.width - 32, 80), 24,
                       theme.OFF_WHITE)
        btn = pygame.Rect(r.x + 16, r.bottom - 84, r.width - 32, 70)
        if state == "done":
            ui.button(surface, f"rs:{node['id']}", btn, "Researched", theme.GREEN, size=30, icon="check", icon_size=36)
        elif state == "locked":
            req = ", ".join(game.config.research[q]["name"] for q in node["requires"] if q not in game.research.done)
            draw_paragraph(surface, "Needs: " + req, pygame.Rect(btn.x, btn.y + 4, btn.width, 70), 24, theme.TEXT_DIM)
        else:
            if self.cost_button(surface, ui, f"rs:{node['id']}", btn, "", node["cost"], "rp", color=theme.CYAN):
                if game.research.research(node["id"]):
                    self.app.audio.play("research")
                    self.app.particles.emit("sparkle", r.centerx, r.centery, 30, spread=3.1, speed=400,
                                            life=0.8, size=24, screen=True)
            if node["id"] in ("precision_lathes", "fast_conveyors", "reduced_assembly"):
                self.app.tutorial_target("research_node", btn)
