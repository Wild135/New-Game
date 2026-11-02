"""Rocket Collection, Rocket Details and customisation."""
from __future__ import annotations

import pygame

from game.rendering import art
from game.rendering.draw import draw_paragraph, draw_text
from game.ui import theme
from game.ui.screens.base import Screen


def rocket_preview(game, rocket_id: str, height: int) -> pygame.Surface:
    rdef = game.config.rockets[rocket_id]
    paint = game.shop.equipped_item("paint")
    accent = tuple(rdef["colors"]["accent"]) if paint["id"] == "paint_classic" else tuple(paint["color"])
    return art.rocket_sprite(height, tuple(rdef["colors"]["body"]), accent, rdef["fins"],
                             game.shop.equipped.get("decal", "decal_none"))


class RocketsScreen(Screen):
    nav_id = "rockets"

    def draw(self, surface, ui, dt):
        content = self.page_frame(surface, ui, "Rockets", "rocket")
        self.tabs(surface, ui, pygame.Rect(content.x, content.y, content.width, 80), ["Fleet", "Customize"])
        area = pygame.Rect(content.x, content.y + 100, content.width, content.height - 100)
        if self.tab == 0:
            self.draw_fleet(surface, ui, area, dt)
        else:
            self.draw_customize(surface, ui, area, dt)

    def draw_fleet(self, surface, ui, area, dt):
        game = self.game
        rockets = game.config.rocket_list
        row_h = 250
        y = self.begin_scroll(surface, ui, area, len(rockets) * (row_h + 12) + 20, dt)
        factory = game.factory
        for rdef in rockets:
            rid = rdef["id"]
            r = pygame.Rect(area.x, y, area.width - 16, row_h)
            if r.bottom > area.top and r.top < area.bottom:
                unlocked = rid in game.unlocked_rockets
                selected = factory.rocket_id == rid
                self.card(surface, r, border=theme.GREEN if selected else (90, 130, 210))
                img = rocket_preview(game, rid, 200)
                if not unlocked:
                    img = img.copy()
                    img.fill((60, 60, 80, 255), special_flags=pygame.BLEND_RGBA_MULT)
                surface.blit(img, img.get_rect(center=(r.x + 100, r.centery)))
                draw_text(surface, rdef["name"], (r.x + 210, r.y + 14), 40, theme.WHITE, outline=3)
                value = rdef["value"] * game.config.planets[game.current_planet]["value_mult"] * game.global_mods_cached.m("value")
                draw_text(surface, f"Value: {game.describe_money(value)} each", (r.x + 210, r.y + 62), 30,
                          theme.YELLOW, outline=2)
                parts = ", ".join(f"{int(v)} {game.config.components[c]['name']}" for c, v in factory.resolved_recipe(rid).items()) \
                    if not rdef.get("planet") or rdef["planet"] == game.current_planet else \
                    ", ".join(f"{int(v)} {c}" for c, v in rdef["recipe"].items())
                draw_paragraph(surface, "Needs: " + parts, pygame.Rect(r.x + 210, r.y + 102, r.width - 470, 80), 26)
                if rdef.get("bonus"):
                    draw_text(surface, rdef["description"].split("Bonus:")[-1].strip() if "Bonus" in rdef["description"] else "",
                              (r.x + 210, r.bottom - 44), 26, theme.GREEN_LIGHT, kind="body", max_width=r.width - 470)
                btn = pygame.Rect(r.right - 250, r.y + 70, 230, 110)
                if selected:
                    ui.button(surface, f"rk:{rid}", btn, "Building", theme.GREEN, size=34, icon="check", icon_size=40)
                elif unlocked:
                    can, reason = factory.can_build(rid)
                    if ui.button(surface, f"rk:{rid}", btn, "Build" if can else "Locked", theme.BLUE if can else theme.GREY,
                                 size=36, sublabel=None if can else reason[:18]):
                        if game.select_rocket(rid):
                            self.app.audio.play("unlock")
                else:
                    missing = game.rocket_requirements(rid)
                    if missing:
                        ui.button(surface, f"rk:{rid}", btn, "Locked", theme.GREY, size=34, sublabel=missing[:20])
                    elif self.cost_button(surface, ui, f"rk:{rid}", btn, "Unlock", rdef["unlock_cost"], color=theme.ORANGE):
                        if game.unlock_rocket(rid):
                            self.app.audio.play("unlock")
                            self.app.particles.emit("confetti", r.centerx, r.centery + self.app.factory_view.scroll.offset,
                                                    40, spread=3.1, speed=500, life=1.2, size=14, gravity=400)
                            self.app.push(RocketDetail(self.app, rid))
                if ui.region(f"rkinfo:{rid}", pygame.Rect(r.x, r.y, r.width - 270, r.height)):
                    self.app.push(RocketDetail(self.app, rid))
            y += row_h + 12
        self.end_scroll(surface, ui, area)

    def draw_customize(self, surface, ui, area, dt):
        game = self.game
        preview = rocket_preview(game, game.factory.rocket_id, 330)
        self.card(surface, pygame.Rect(area.x, area.y, area.width - 16, 380))
        surface.blit(preview, preview.get_rect(center=(area.x + 200, area.y + 190)))
        draw_paragraph(surface, "Cosmetics change how your rockets, launches and factory look. They never change the "
                                "economy. Buy new styles in the Shop with gems.",
                       pygame.Rect(area.x + 380, area.y + 30, area.width - 420, 300), 30)
        sub = pygame.Rect(area.x, area.y + 400, area.width, area.height - 400)
        slots = [("paint", "Paint"), ("decal", "Decals"), ("exhaust", "Exhaust"), ("effect", "Launch Effect"),
                 ("theme", "Factory Theme"), ("hat", "Hard Hats")]
        rows = []
        for slot, title in slots:
            items = [c for c in game.config.cosmetic_list if c["slot"] == slot]
            rows.append((slot, title, items))
        height = sum(70 + ((len(items) + 2) // 3) * 120 for _, _, items in rows)
        y = self.begin_scroll(surface, ui, sub, height + 20, dt)
        for slot, title, items in rows:
            draw_text(surface, title, (sub.x + 10, y + 14), 38, theme.WHITE, outline=3)
            y += 70
            bw = (sub.width - 40) // 3
            for i, cos in enumerate(items):
                r = pygame.Rect(sub.x + (i % 3) * (bw + 10), y + (i // 3) * 120, bw, 104)
                owned = game.shop.is_owned(cos["id"])
                equipped = game.shop.equipped.get(slot) == cos["id"]
                color = tuple(cos.get("color", theme.BLUE)) if "color" in cos else theme.BLUE
                label = cos["name"]
                if equipped:
                    ui.button(surface, f"eq:{cos['id']}", r, label, theme.GREEN, size=28, sublabel="Equipped")
                elif owned:
                    if ui.button(surface, f"eq:{cos['id']}", r, label, color, size=28, sublabel="Equip"):
                        game.shop.equip(cos["id"])
                        self.app.audio.play("click")
                else:
                    if ui.button(surface, f"eq:{cos['id']}", r, label, theme.GREY_DARK, size=28,
                                 sublabel="In Shop" if not cos.get("requires_legacy") else "Legacy"):
                        self.app.open("shop", tab=1)
            y += ((len(items) + 2) // 3) * 120
        self.end_scroll(surface, ui, sub)


class RocketDetail(Screen):
    kind = "popup"

    def __init__(self, app, rocket_id: str, **kw):
        super().__init__(app, **kw)
        self.rocket_id = rocket_id

    def draw(self, surface, ui, dt):
        game = self.game
        rdef = game.config.rockets[self.rocket_id]
        content = self.popup_frame(surface, ui, rdef["name"], (960, 1300), icon="rocket")
        img = rocket_preview(game, self.rocket_id, 420)
        surface.blit(img, img.get_rect(midtop=(content.x + 170, content.y + 10)))
        x = content.x + 360
        y = content.y + 10
        draw_paragraph(surface, rdef["description"], pygame.Rect(x, y, content.right - x, 200), 30)
        y += 200
        rows = [("Base value", game.describe_money(rdef["value"])),
                ("Parts per rocket", str(int(sum(rdef["recipe"].values())))),
                ("Research per launch", f"{rdef['rp']:.1f} RP"),
                ("Built on", game.config.planets[rdef["planet"]]["name"] if rdef.get("planet") else "Any planet")]
        if rdef.get("research"):
            rows.append(("Requires", game.config.research[rdef["research"]]["name"]))
        for label, value in rows:
            draw_text(surface, label, (x, y), 28, theme.TEXT_DIM, kind="body")
            draw_text(surface, value, (content.right, y), 30, theme.WHITE, anchor="topright", outline=2)
            y += 46
        y = content.y + 470
        draw_text(surface, "Recipe", (content.x, y), 38, theme.WHITE, outline=3)
        y += 56
        for comp, amount in rdef["recipe"].items():
            name = comp
            if comp == "special":
                planet = game.config.planets.get(rdef.get("planet") or "earth")
                name = game.config.components[planet["special"]]["name"] if planet and planet.get("special") else comp
            elif comp in game.config.components:
                name = game.config.components[comp]["name"]
            draw_text(surface, f"{int(amount)} x {name}", (content.x + 20, y), 32, theme.OFF_WHITE, outline=2)
            y += 46
        status = "Unlocked" if self.rocket_id in game.unlocked_rockets else (game.rocket_requirements(self.rocket_id) or
                                                                             f"Unlock for {game.describe_money(rdef['unlock_cost'])}")
        draw_text(surface, status, (content.centerx, content.bottom - 150), 34, theme.YELLOW, anchor="center", outline=3)
        ok = pygame.Rect(content.centerx - 160, content.bottom - 110, 320, 100)
        if ui.button(surface, f"ok:{id(self)}", ok, "OK", theme.GREEN, size=40):
            self.close()
