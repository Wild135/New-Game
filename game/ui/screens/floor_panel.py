"""Factory Upgrade Panel: details of one floor, bulk upgrades and its manager."""
from __future__ import annotations

import pygame

from game.core.numformat import format_duration, format_number
from game.economy.formulas import milestone_multiplier, next_milestone, previous_milestone_level
from game.rendering import icons
from game.rendering.draw import draw_paragraph, draw_text, progress_bar
from game.ui import theme
from game.ui.screens.base import Screen, rarity_tag


class FloorPanel(Screen):
    kind = "popup"

    def __init__(self, app, floor_id: str, focus_manager: bool = False, **kw):
        super().__init__(app, **kw)
        self.floor_id = floor_id
        self.picking = focus_manager

    def draw(self, surface, ui, dt):
        game = self.game
        fid = self.floor_id
        factory = game.factory
        if fid not in factory.floors:
            self.close()
            return
        fdef = game.config.floors[fid]
        floor = factory.floors[fid]
        stats = game.stats_cache.get(game.current_planet)
        height = 1500 if self.picking else (1000 if fdef["kind"] == "support" else 1300)
        content = self.popup_frame(surface, ui, fdef["name"], (1000, height), icon=fdef.get("icon"))
        if self.picking:
            self.draw_picker(surface, ui, content, dt)
            return
        y = content.y + 4
        draw_text(surface, f"Level {floor.level}", (content.x, y), 48, theme.YELLOW, outline=3)
        workers = factory.worker_count(fid)
        draw_text(surface, f"Workers: {workers}", (content.right, y + 8), 34, theme.OFF_WHITE, anchor="topright", outline=2)
        y += 64
        y += draw_paragraph(surface, fdef["description"], pygame.Rect(content.x, y, content.width, 120), 30) + 12
        # Stats table
        rows = []
        kind = fdef["kind"]
        if kind == "support":
            rows.append(("Bonus", f"x{factory.support_multiplier(fid):.2f} {self.effect_name(fdef['effect'])}"))
        elif stats:
            rate = stats.rate.get(fid, 0.0)
            if kind == "producer":
                comp = factory.component_of(fid)
                rows.append(("Output", f"{format_number(rate)} {game.config.components[comp]['name']}/s"))
                rows.append(("Storage", f"{format_number(floor.storage)} / {format_number(stats.storage_cap.get(fid, 0))}"))
            elif kind == "transport":
                rows.append(("Carry speed", f"{format_number(rate)} items/s"))
            elif kind == "assembly":
                rows.append(("Assembly speed", f"{format_number(rate)} items/s"))
            else:
                rows.append(("Capacity", f"{format_number(stats.capacity)} rockets per launch"))
                rows.append(("Launch window", f"every {stats.interval:.1f}s"))
            rps = stats.stage_rockets.get(fid)
            if rps is not None:
                rows.append(("Supports", f"{format_number(rps)} rockets/s = {game.describe_money(rps * stats.value_per_rocket)}/s"))
            if stats.bottleneck == fid:
                rows.append(("Status", "BOTTLENECK - upgrade me!"))
            elif rps is None and kind == "producer":
                rows.append(("Status", "Not used by the current rocket"))
            else:
                rows.append(("Status", "Automated" if floor.manager_uid else "Manual - tap to work"))
        for label, value in rows:
            draw_text(surface, label, (content.x + 10, y), 32, theme.TEXT_DIM, kind="body")
            color = theme.RED if "BOTTLENECK" in value else theme.WHITE
            draw_text(surface, value, (content.right - 10, y), 32, color, anchor="topright", outline=2,
                      max_width=content.width - 300)
            y += 48
        y += 10
        # Milestone progress
        ms = game.config.support_milestones if kind == "support" else game.config.milestones
        nxt = next_milestone(floor.level, ms)
        if nxt:
            prev = previous_milestone_level(floor.level, ms)
            frac = (floor.level - prev) / max(1, nxt[0] - prev)
            draw_text(surface, f"Next milestone: Lv. {nxt[0]} -> x{format_number(nxt[1])} output", (content.x, y), 32,
                      theme.YELLOW, outline=2)
            draw_text(surface, f"now x{format_number(milestone_multiplier(floor.level, ms))}", (content.right, y), 30,
                      theme.OFF_WHITE, anchor="topright", outline=2)
            y += 44
            progress_bar(surface, pygame.Rect(content.x, y, content.width, 34), frac, theme.YELLOW)
            draw_text(surface, f"{floor.level}/{nxt[0]}", (content.centerx, y + 17), 24, theme.WHITE, anchor="center", outline=2)
            y += 54
        # Buy buttons
        bw = (content.width - 30) // 4
        for i, amount in enumerate(("1", "10", "25", "max")):
            count, cost = game.upgrade_quote(fid, amount)
            r = pygame.Rect(content.x + i * (bw + 10), y, bw, 116)
            label = "MAX" if amount == "max" else f"x{amount}"
            if amount == "max":
                label = f"MAX x{count}"
            enabled = count > 0
            if self.cost_button(surface, ui, f"buy:{fid}:{amount}", r, label, cost, enabled=enabled):
                if game.upgrade_floor(fid, amount):
                    self.app.factory_view.on_upgraded(fid)
        y += 140
        # Manager section
        if kind == "support":
            draw_paragraph(surface, "Support departments work automatically and boost the whole factory.",
                           pygame.Rect(content.x, y, content.width, 100), 30, theme.TEXT_DIM)
            return
        self.card(surface, pygame.Rect(content.x, y, content.width, content.bottom - y))
        inner = pygame.Rect(content.x + 20, y + 16, content.width - 40, content.bottom - y - 32)
        inst = game.managers.get(floor.manager_uid)
        if inst is None:
            draw_text(surface, "No manager", (inner.x, inner.y), 40, theme.WHITE, outline=3)
            draw_paragraph(surface, "Assign a manager to automate this floor. It will keep working even "
                                    "while you are away!", pygame.Rect(inner.x, inner.y + 56, inner.width, 120), 30)
            btn = pygame.Rect(inner.centerx - 220, inner.y + 190, 440, 110)
            if ui.button(surface, f"assign:{fid}", btn, "Assign Manager", theme.GREEN, size=40, icon="manager"):
                self.picking = True
                self.scroll.scroll_to(0)
            self.app.tutorial_target("assign_btn", btn)
            return
        mdef = game.config.managers[inst.def_id]
        portrait = icons.manager_portrait(mdef["look"], 150, self.app.factory_view.hat_color(),
                                          bg=theme.RARITY_COLORS[mdef["rarity"]])
        surface.blit(portrait, (inner.x, inner.y))
        draw_text(surface, game.managers.display_name(inst), (inner.x + 170, inner.y), 40, theme.WHITE, outline=3,
                  max_width=inner.width - 170)
        draw_text(surface, f"{mdef['title']}  -  Lv. {inst.level}", (inner.x + 170, inner.y + 50), 30, theme.OFF_WHITE,
                  kind="body", max_width=inner.width - 170)
        rarity_tag(surface, (inner.x + 170, inner.y + 96), mdef["rarity"])
        yy = inner.y + 165
        draw_text(surface, describe_passive(game, inst), (inner.x, yy), 30, theme.GREEN_LIGHT, kind="body",
                  max_width=inner.width)
        yy += 50
        ability = mdef["active"]
        draw_text(surface, f"Ability: {ability['name']} - {describe_ability(ability)}", (inner.x, yy), 30,
                  theme.YELLOW, kind="body", max_width=inner.width)
        yy += 60
        bw = (inner.width - 20) // 3
        r1 = pygame.Rect(inner.x, yy, bw, 104)
        if inst.active > 0:
            ui.button(surface, f"act:{inst.uid}", r1, "ACTIVE", theme.ORANGE, size=34, sublabel=format_duration(inst.active))
        elif inst.cooldown > 0:
            ui.button(surface, f"act:{inst.uid}", r1, "Cooldown", theme.GREY, size=32, sublabel=format_duration(inst.cooldown))
        elif ui.button(surface, f"act:{inst.uid}", r1, "Activate", theme.PURPLE, size=36, icon=None):
            game.managers.activate(inst.uid)
        r2 = pygame.Rect(inner.x + bw + 10, yy, bw, 104)
        if inst.level < game.config.economy["manager_max_level"]:
            if self.cost_button(surface, ui, f"mup:{inst.uid}", r2, "Level Up", game.managers.upgrade_cost(inst)):
                if game.managers.upgrade(inst.uid):
                    self.app.audio.play("upgrade")
        else:
            ui.button(surface, f"mup:{inst.uid}", r2, "MAX LEVEL", theme.GREY, size=32)
        r3 = pygame.Rect(inner.x + 2 * (bw + 10), yy, bw, 104)
        if ui.button(surface, f"swap:{fid}", r3, "Change", theme.BLUE, size=36):
            self.picking = True
            self.scroll.scroll_to(0)

    def effect_name(self, effect: str) -> str:
        return {"production": "production speed", "value": "rocket value", "logistics": "transport & assembly",
                "rp_gain": "research points"}.get(effect, effect)

    def draw_picker(self, surface, ui, content: pygame.Rect, dt: float) -> None:
        game = self.game
        fid = self.floor_id
        kind = game.config.floors[fid]["kind"]
        draw_text(surface, "Choose a manager", (content.x, content.y), 42, theme.WHITE, outline=3)
        back = pygame.Rect(content.right - 200, content.y - 6, 200, 70)
        if ui.button(surface, f"back:{id(self)}", back, "Back", theme.GREY_DARK, size=34):
            self.picking = False
        area = pygame.Rect(content.x, content.y + 80, content.width, content.height - 220)
        candidates = [m for m in game.managers.instances if game.managers.fits(m, kind)]
        candidates.sort(key=lambda m: (m.planet is not None, -["common", "rare", "epic", "legendary"].index(
            game.config.managers[m.def_id]["rarity"]), -m.level))
        row_h = 150
        y = self.begin_scroll(surface, ui, area, max(1, len(candidates)) * (row_h + 12), dt)
        if not candidates:
            draw_paragraph(surface, "You have no managers that can run this floor. Hire one below!",
                           pygame.Rect(area.x + 20, area.y + 30, area.width - 40, 200), 34, align="center")
        for inst in candidates:
            mdef = game.config.managers[inst.def_id]
            r = pygame.Rect(area.x, y, area.width - 16, row_h)
            if r.bottom > area.top and r.top < area.bottom:
                self.card(surface, r)
                surface.blit(icons.manager_portrait(mdef["look"], 120, self.app.factory_view.hat_color(),
                                                    bg=theme.RARITY_COLORS[mdef["rarity"]]), (r.x + 14, r.y + 15))
                draw_text(surface, f"{game.managers.display_name(inst)}  Lv.{inst.level}", (r.x + 150, r.y + 16), 34,
                          theme.WHITE, outline=2, max_width=r.width - 420)
                draw_text(surface, describe_passive(game, inst), (r.x + 150, r.y + 62), 26, theme.GREEN_LIGHT, kind="body",
                          max_width=r.width - 420)
                where = "Free" if inst.planet is None else f"Working: {game.config.floors[inst.floor]['name']}"
                if inst.planet and inst.planet != game.current_planet:
                    where += f" ({game.config.planets[inst.planet]['name']})"
                draw_text(surface, where, (r.x + 150, r.y + 100), 26, theme.TEXT_DIM, kind="body", max_width=r.width - 420)
                btn = pygame.Rect(r.right - 250, r.y + 30, 230, 90)
                current = inst.uid == game.factory.floors[fid].manager_uid
                if current:
                    if ui.button(surface, f"unassign:{inst.uid}", btn, "Remove", theme.RED, size=34):
                        game.managers.unassign(inst.uid)
                elif ui.button(surface, f"pick:{inst.uid}", btn, "Assign", theme.GREEN, size=36):
                    if game.managers.assign(inst.uid, game.current_planet, fid):
                        self.app.audio.play("unlock")
                        self.picking = False
                if not current and inst.planet is None:
                    self.app.tutorial_target("pick_manager", btn)
            y += row_h + 12
        self.end_scroll(surface, ui, area)
        # quick hire: cheapest compatible common manager
        options = [m for m in game.config.manager_list if m["rarity"] == "common" and game.managers.fits(m["id"], kind)]
        if options:
            best = min(options, key=lambda m: game.managers.hire_cost(m["id"])[0])
            cost, _ = game.managers.hire_cost(best["id"])
            btn = pygame.Rect(content.x, content.bottom - 120, content.width, 116)
            self.app.tutorial_target("hire_quick", btn)
            if self.cost_button(surface, ui, f"quickhire:{fid}", btn, f"Hire {best['name']} ({best['title']})", cost):
                inst = game.managers.hire(best["id"])
                if inst:
                    game.managers.assign(inst.uid, game.current_planet, fid)
                    self.app.audio.play("achievement")
                    self.picking = False


def describe_passive(game, inst) -> str:
    mdef = game.config.managers[inst.def_id]
    strength = game.managers.passive_strength(inst)
    parts = []
    for eff in mdef["passive"]:
        value = game.managers.scale_mult(eff["mult"], strength)
        name = {"rate": "floor speed", "storage": "storage", "value": "rocket value", "all": "factory output",
                "launch_interval": "launch interval"}.get(eff["stat"], eff["stat"])
        if value >= 1:
            parts.append(f"+{(value - 1) * 100:.0f}% {name}")
        else:
            parts.append(f"-{(1 - value) * 100:.0f}% {name}")
    return ", ".join(parts)


def describe_ability(ability: dict) -> str:
    name = {"rate": "floor speed", "all": "whole factory", "value": "rocket value"}.get(ability["stat"], ability["stat"])
    return f"x{ability['mult']:g} {name} for {ability['duration']}s (cooldown {format_duration(ability['cooldown'])})"
