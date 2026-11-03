"""Planet Selection screen."""
from __future__ import annotations

import pygame

from game.rendering import art
from game.rendering.draw import draw_paragraph, draw_text
from game.ui import theme
from game.ui.screens.base import Screen


class PlanetsScreen(Screen):
    nav_id = "expansion"

    def draw(self, surface, ui, dt):
        game = self.game
        content = self.page_frame(surface, ui, "Planets", "planet")
        unlocked, why = game.feature_unlocked("planets")
        if not unlocked:
            draw_paragraph(surface, why + ".\n\nEach planet has its own factory, special resource, exclusive rocket "
                                          "and a gameplay twist. Rockets launched there are worth much more!",
                           pygame.Rect(content.x + 40, content.y + 80, content.width - 80, 600), 40, align="center")
            return
        planets = game.config.planet_list
        row_h = 300
        y = self.begin_scroll(surface, ui, content, len(planets) * (row_h + 14) + 20, dt)
        next_locked = game.next_locked_planet()
        for planet in planets:
            pid = planet["id"]
            r = pygame.Rect(content.x, y, content.width - 16, row_h)
            if r.bottom > content.top and r.top < content.bottom:
                owned = pid in game.factories
                current = pid == game.current_planet
                self.card(surface, r, border=theme.GREEN if current else (90, 130, 210))
                sphere = art.planet_sphere(tuple(planet["theme"]["planet"]), 100, ring=pid in ("titan", "kepler"), seed=pid)
                if not owned:
                    sphere = sphere.copy()
                    sphere.fill((90, 90, 110, 255), special_flags=pygame.BLEND_RGBA_MULT)
                surface.blit(sphere, sphere.get_rect(center=(r.x + 140, r.centery)))
                draw_text(surface, planet["name"], (r.x + 270, r.y + 16), 44, theme.WHITE, outline=3)
                draw_text(surface, planet["trait"], (r.x + 270, r.y + 68), 30, theme.YELLOW, outline=2,
                          max_width=r.width - 520)
                draw_paragraph(surface, planet["description"], pygame.Rect(r.x + 270, r.y + 110, r.width - 540, 110), 26)
                special = planet.get("special")
                extra = f"Rocket value x{planet['value_mult']:g}"
                if special:
                    extra += f"  |  Resource: {game.config.components[special]['name']}"
                draw_text(surface, extra, (r.x + 270, r.bottom - 48), 26, theme.GREEN_LIGHT, kind="body",
                          max_width=r.width - 300)
                btn = pygame.Rect(r.right - 250, r.y + 90, 230, 110)
                if current:
                    ui.button(surface, f"pl:{pid}", btn, "Here", theme.GREEN, size=36, icon="check", icon_size=40)
                elif owned:
                    if ui.button(surface, f"pl:{pid}", btn, "Travel", theme.BLUE, size=38):
                        game.switch_planet(pid)
                        self.app.audio.play("whoosh")
                        self.app.factory_view.scroll.scroll_to(0)
                        self.close()
                elif pid == next_locked:
                    if self.cost_button(surface, ui, f"pl:{pid}", btn, "Unlock", game.planet_unlock_cost(pid),
                                        color=theme.ORANGE):
                        if game.unlock_planet(pid):
                            self.app.audio.play("unlock")
                            self.app.hud.toast(f"Welcome to {planet['name']}!")
                else:
                    ui.button(surface, f"pl:{pid}", btn, "Locked", theme.GREY, size=34,
                              sublabel=game.describe_money(game.planet_unlock_cost(pid)))
            y += row_h + 14
        self.end_scroll(surface, ui, content)
