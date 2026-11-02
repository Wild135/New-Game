"""Manager Collection, Recruitment and Manager Details screens."""
from __future__ import annotations

import pygame

from game.core.numformat import format_duration
from game.rendering import icons
from game.rendering.draw import draw_paragraph, draw_text
from game.ui import theme
from game.ui.screens.base import Screen, rarity_tag
from game.ui.screens.floor_panel import describe_ability, describe_passive

RARITY_ORDER = ["common", "rare", "epic", "legendary"]


class ManagersScreen(Screen):
    nav_id = "managers"

    def draw(self, surface, ui, dt):
        game = self.game
        content = self.page_frame(surface, ui, "Managers", "manager")
        self.tabs(surface, ui, pygame.Rect(content.x, content.y, content.width, 80),
                  [f"My Team ({len(game.managers.instances)})", "Recruit"])
        area = pygame.Rect(content.x, content.y + 100, content.width, content.height - 100)
        if self.tab == 0:
            self.draw_team(surface, ui, area, dt)
        else:
            self.draw_recruit(surface, ui, area, dt)

    def draw_team(self, surface, ui, area, dt):
        game = self.game
        insts = sorted(game.managers.instances, key=lambda m: (
            -RARITY_ORDER.index(game.config.managers[m.def_id]["rarity"]), m.planet is None, m.uid))
        row_h = 170
        y = self.begin_scroll(surface, ui, area, max(1, len(insts)) * (row_h + 12) + 20, dt)
        if not insts:
            draw_paragraph(surface, "You have not hired anyone yet. Open the Recruit tab to hire your first manager "
                                    "and automate a floor!", pygame.Rect(area.x + 40, area.y + 60, area.width - 80, 300),
                           38, align="center")
        for inst in insts:
            mdef = game.config.managers[inst.def_id]
            r = pygame.Rect(area.x, y, area.width - 16, row_h)
            if r.bottom > area.top and r.top < area.bottom:
                self.card(surface, r, border=theme.RARITY_COLORS[mdef["rarity"]])
                surface.blit(icons.manager_portrait(mdef["look"], 140, self.app.factory_view.hat_color(),
                                                    bg=theme.RARITY_COLORS[mdef["rarity"]]), (r.x + 14, r.y + 15))
                draw_text(surface, game.managers.display_name(inst), (r.x + 170, r.y + 14), 38, theme.WHITE, outline=3,
                          max_width=r.width - 420)
                draw_text(surface, f"{mdef['title']} - Lv. {inst.level}", (r.x + 170, r.y + 60), 28, theme.OFF_WHITE,
                          kind="body", max_width=r.width - 420)
                if inst.planet:
                    where = f"{game.config.floors[inst.floor]['name']} ({game.config.planets[inst.planet]['name']})"
                    color = theme.GREEN_LIGHT
                else:
                    where, color = "Not assigned", theme.ORANGE
                draw_text(surface, where, (r.x + 170, r.y + 104), 28, color, kind="body", max_width=r.width - 420)
                if inst.active > 0:
                    draw_text(surface, f"ACTIVE {format_duration(inst.active)}", (r.right - 30, r.y + 18), 26,
                              theme.YELLOW, anchor="topright", outline=2)
                btn = pygame.Rect(r.right - 240, r.y + 60, 220, 90)
                if ui.button(surface, f"detail:{inst.uid}", btn, "Details", theme.BLUE, size=34):
                    self.app.push(ManagerDetail(self.app, inst.uid))
            y += row_h + 12
        self.end_scroll(surface, ui, area)

    def draw_recruit(self, surface, ui, area, dt):
        game = self.game
        defs = sorted(game.config.manager_list, key=lambda m: RARITY_ORDER.index(m["rarity"]))
        row_h = 230
        y = self.begin_scroll(surface, ui, area, len(defs) * (row_h + 12) + 20, dt)
        for mdef in defs:
            r = pygame.Rect(area.x, y, area.width - 16, row_h)
            if r.bottom > area.top and r.top < area.bottom:
                self.card(surface, r, border=theme.RARITY_COLORS[mdef["rarity"]])
                surface.blit(icons.manager_portrait(mdef["look"], 150, self.app.factory_view.hat_color(),
                                                    bg=theme.RARITY_COLORS[mdef["rarity"]]), (r.x + 14, r.y + 18))
                draw_text(surface, f"{mdef['name']} - {mdef['title']}", (r.x + 180, r.y + 14), 36, theme.WHITE,
                          outline=3, max_width=r.width - 200)
                rarity_tag(surface, (r.x + 180, r.y + 60), mdef["rarity"])
                slot = {"producer": "Production floors", "transport": "Transport", "assembly": "Assembly",
                        "launch": "Launchpad", "any": "Any floor"}[mdef["slot"]]
                draw_text(surface, f"Runs: {slot}", (r.x + 330, r.y + 64), 28, theme.OFF_WHITE, kind="body")
                fake = type("I", (), {"def_id": mdef["id"], "level": 1})()
                draw_text(surface, describe_passive(game, fake), (r.x + 180, r.y + 110), 26, theme.GREEN_LIGHT,
                          kind="body", max_width=r.width - 450)
                draw_text(surface, f"{mdef['active']['name']}: {describe_ability(mdef['active'])}", (r.x + 180, r.y + 150),
                          24, theme.YELLOW, kind="body", max_width=r.width - 450)
                owned = game.managers.hired_count(def_id=mdef["id"])
                if owned:
                    draw_text(surface, f"Hired: {owned}", (r.x + 180, r.y + 186), 24, theme.TEXT_DIM, kind="body")
                cost, currency = game.managers.hire_cost(mdef["id"])
                btn = pygame.Rect(r.right - 260, r.y + 110, 240, 100)
                ok, reason = game.managers.can_hire(mdef["id"])
                unique_taken = mdef.get("unique") and owned
                if unique_taken:
                    ui.button(surface, f"hire:{mdef['id']}", btn, "Hired", theme.GREY, size=36)
                elif self.cost_button(surface, ui, f"hire:{mdef['id']}", btn, "Hire", cost, currency):
                    inst = game.managers.hire(mdef["id"])
                    if inst:
                        self.app.audio.play("achievement")
                        self.app.hud.toast(f"{game.managers.display_name(inst)} joined your team!")
                        self.app.push(ManagerDetail(self.app, inst.uid))
                if mdef["id"] == "alex":
                    self.app.tutorial_target("recruit_alex", btn)
            y += row_h + 12
        self.end_scroll(surface, ui, area)


class ManagerDetail(Screen):
    kind = "popup"

    def __init__(self, app, uid: str, **kw):
        super().__init__(app, **kw)
        self.uid = uid

    def draw(self, surface, ui, dt):
        game = self.game
        inst = game.managers.get(self.uid)
        if inst is None:
            self.close()
            return
        mdef = game.config.managers[inst.def_id]
        content = self.popup_frame(surface, ui, game.managers.display_name(inst), (1000, 1500))
        portrait = icons.manager_portrait(mdef["look"], 260, self.app.factory_view.hat_color(),
                                          bg=theme.RARITY_COLORS[mdef["rarity"]])
        surface.blit(portrait, (content.centerx - 130, content.y))
        y = content.y + 270
        draw_text(surface, mdef["title"], (content.centerx, y), 40, theme.WHITE, anchor="midtop", outline=3)
        y += 52
        tag_w = theme.fonts.get(24).size(mdef["rarity"].upper())[0] + 28
        rarity_tag(surface, (content.centerx - tag_w // 2, y), mdef["rarity"])
        y += 60
        draw_text(surface, f"Level {inst.level} / {game.config.economy['manager_max_level']}", (content.centerx, y), 36,
                  theme.YELLOW, anchor="midtop", outline=3)
        y += 60
        draw_text(surface, "Passive: " + describe_passive(game, inst), (content.x, y), 30, theme.GREEN_LIGHT,
                  kind="body", max_width=content.width)
        y += 50
        ability = mdef["active"]
        y += draw_paragraph(surface, f"Active - {ability['name']}: {describe_ability(ability)}",
                            pygame.Rect(content.x, y, content.width, 100), 30, theme.YELLOW) + 10
        if inst.planet:
            where = f"Working at {game.config.floors[inst.floor]['name']} on {game.config.planets[inst.planet]['name']}"
        else:
            where = "Not assigned. Tap a floor's manager slot to assign."
        y += draw_paragraph(surface, where, pygame.Rect(content.x, y, content.width, 100), 30, theme.OFF_WHITE) + 20
        bw = (content.width - 20) // 2
        r1 = pygame.Rect(content.x, y, bw, 110)
        if inst.level < game.config.economy["manager_max_level"]:
            if self.cost_button(surface, ui, f"mlv:{inst.uid}", r1, "Level Up", game.managers.upgrade_cost(inst)):
                if game.managers.upgrade(inst.uid):
                    self.app.audio.play("upgrade")
        else:
            ui.button(surface, f"mlv:{inst.uid}", r1, "MAX LEVEL", theme.GREY, size=34)
        r2 = pygame.Rect(content.x + bw + 20, y, bw, 110)
        if inst.active > 0:
            ui.button(surface, f"mact:{inst.uid}", r2, "ACTIVE", theme.ORANGE, size=34, sublabel=format_duration(inst.active))
        elif inst.cooldown > 0:
            ui.button(surface, f"mact:{inst.uid}", r2, "Cooldown", theme.GREY, size=34, sublabel=format_duration(inst.cooldown))
        elif ui.button(surface, f"mact:{inst.uid}", r2, "Activate", theme.PURPLE, size=36):
            game.managers.activate(inst.uid)
        y += 130
        if inst.planet:
            r3 = pygame.Rect(content.x, y, content.width, 100)
            if ui.button(surface, f"munassign:{inst.uid}", r3, "Remove from floor", theme.RED, size=36):
                game.managers.unassign(inst.uid)
        else:
            # Offer every compatible free floor in the current factory
            kinds = []
            for fid in game.factory.ordered_floor_ids():
                floor = game.factory.floors[fid]
                if floor.level > 0 and game.managers.fits(inst, game.config.floors[fid]["kind"]):
                    kinds.append(fid)
            draw_text(surface, "Assign to:", (content.x, y), 34, theme.WHITE, outline=2)
            y += 50
            for fid in kinds[:6]:
                r = pygame.Rect(content.x, y, content.width, 80)
                occupied = game.factory.floors[fid].manager_uid is not None
                label = game.config.floors[fid]["name"] + (" (replace)" if occupied else "")
                if ui.button(surface, f"massign:{inst.uid}:{fid}", r, label, theme.BLUE if occupied else theme.GREEN, size=32):
                    if game.managers.assign(inst.uid, game.current_planet, fid):
                        self.app.audio.play("unlock")
                y += 92
                if y > content.bottom - 80:
                    break
