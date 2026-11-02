"""Settings, Statistics, How-to-Play and Offline Earnings screens."""
from __future__ import annotations

import math

import pygame

from game.core.numformat import format_duration, format_number
from game.rendering import icons
from game.rendering.draw import draw_paragraph, draw_text, progress_bar
from game.ui import theme
from game.ui.screens.base import ConfirmDialog, MessageDialog, Screen

HELP_PAGES = [
    ("Welcome!", "rocket", "You run a rocket company. Your factory turns raw metal into rockets and launches them for "
                           "money. Grow from one tiny factory into an interplanetary empire!"),
    ("The production chain", "gear", "Parts Production makes components. Transport carries them to Assembly. Assembly "
                                     "builds rockets. The Launchpad launches them and you get paid."),
    ("Bottlenecks", "bolt", "The slowest floor limits everything. Each floor shows how much money per second it could "
                            "support. The one marked BOTTLENECK is the one to upgrade next."),
    ("Tapping & managers", "manager", "Floors without a manager only work while you tap them. Hire managers to automate "
                                      "floors - automated floors keep earning even while you are away."),
    ("Upgrades & milestones", "arrow_up", "Upgrading raises a floor's level. Levels 10, 25, 50, 100 and beyond give big "
                                          "output multipliers. Use the Buy x1/x10/x25/MAX button to buy in bulk."),
    ("Rockets & floors", "engine", "Better rockets are worth far more but need new components. Unlock Engine "
                                   "Manufacturing, Fuel Systems and more from the factory or the Expansion menu."),
    ("Research", "flask", "Launches, missions and achievements give Research Points. Spend them on permanent technology "
                          "in the Research menu."),
    ("Planets", "planet", "Each planet has its own factory, a special resource, an exclusive rocket and a gameplay "
                          "twist. Rockets there sell for much more."),
    ("Space Legacy", "star", "Later you can reset your run for Legacy Stars. Stars permanently boost production and buy "
                             "powerful Legacy upgrades."),
    ("Offline earnings", "moon", "When you come back you receive what your automated lines produced (up to 8 hours, more "
                                 "with research)."),
]


class SettingsScreen(Screen):
    def draw(self, surface, ui, dt):
        game = self.game
        s = game.settings
        content = self.page_frame(surface, ui, "Settings", "settings")
        y = self.begin_scroll(surface, ui, content, 1700, dt)
        audio = self.app.audio
        for key, label in (("master_volume", "Master volume"), ("music_volume", "Music volume"),
                           ("sfx_volume", "Sound effects volume")):
            draw_text(surface, label, (content.x + 20, y + 10), 36, theme.WHITE, outline=3)
            draw_text(surface, f"{int(s[key] * 100)}%", (content.right - 30, y + 10), 34, theme.OFF_WHITE,
                      anchor="topright", outline=2)
            new = ui.slider(surface, f"sl:{key}", pygame.Rect(content.x + 40, y + 70, content.width - 100, 28), s[key])
            if new != s[key]:
                s[key] = round(new, 2)
                audio.apply_volumes()
            y += 130
        toggles = [("muted", "Mute all audio"), ("launch_animations", "Launch animations"),
                   ("scientific", "Scientific number format"), ("show_fps", "Show FPS counter")]
        for key, label in toggles:
            draw_text(surface, label, (content.x + 20, y + 22), 36, theme.WHITE, outline=3)
            new = ui.toggle(surface, f"tg:{key}", pygame.Rect(content.right - 170, y + 10, 140, 64), bool(s[key]))
            if new != s[key]:
                s[key] = new
                audio.apply_volumes()
            y += 100
        y += 20
        bw = (content.width - 30) // 2
        buttons = [("How to Play", theme.BLUE, lambda: self.app.push(HelpScreen(self.app))),
                   ("Statistics", theme.BLUE, lambda: self.app.open("statistics")),
                   ("Achievements", theme.BLUE, lambda: self.app.open("missions", tab=1)),
                   ("Replay Tutorial", theme.BLUE, self.replay_tutorial),
                   ("Save Now", theme.GREEN, self.save),
                   ("Credits", theme.BLUE, self.credits),
                   ("Main Menu", theme.GREY_DARK, self.main_menu),
                   ("Reset Progress", theme.RED, self.reset)]
        for i, (label, color, action) in enumerate(buttons):
            r = pygame.Rect(content.x + (i % 2) * (bw + 10), y + (i // 2) * 120, bw, 100)
            if ui.button(surface, f"set:{label}", r, label, color, size=36):
                action()
        y += ((len(buttons) + 1) // 2) * 120 + 20
        path = str(self.app.saves.path)
        draw_paragraph(surface, f"Save file: {path}", pygame.Rect(content.x + 20, y, content.width - 40, 120), 24,
                       theme.TEXT_DIM)
        self.end_scroll(surface, ui, content)

    def save(self):
        if self.app.save_now():
            self.app.hud.toast("Game saved!")

    def replay_tutorial(self):
        self.game.tutorial["done"] = False
        self.game.tutorial["step"] = 0
        self.app.tutorial.restart()
        self.close()

    def credits(self):
        self.app.push(MessageDialog(
            self.app, "Credits",
            "Rocket Empire: Idle Space Tycoon\nAll art, sound and music are original and generated in code.\n"
            "Fonts: Lilita One and Fredoka (SIL Open Font License).\nBuilt with Python and pygame-ce.", icon="star"))

    def main_menu(self):
        self.app.save_now()
        self.app.go_to_menu()

    def reset(self):
        def really():
            self.app.reset_progress()
        self.app.push(ConfirmDialog(self.app, "Reset everything?",
                                    "This deletes ALL progress, including gems, managers and Legacy Stars. "
                                    "This cannot be undone!", really, "Delete", danger=True))


class HelpScreen(Screen):
    kind = "popup"

    def draw(self, surface, ui, dt):
        page = max(0, min(self.tab, len(HELP_PAGES) - 1))
        title, icon_name, text = HELP_PAGES[page]
        content = self.popup_frame(surface, ui, "How to Play", (940, 1100), icon="question")
        surface.blit(icons.icon(icon_name, 200), (content.centerx - 100, content.y + 10))
        draw_text(surface, title, (content.centerx, content.y + 230), 46, theme.YELLOW, anchor="midtop", outline=4)
        draw_paragraph(surface, text, pygame.Rect(content.x + 20, content.y + 310, content.width - 40, 400), 36,
                       align="center")
        draw_text(surface, f"{page + 1} / {len(HELP_PAGES)}", (content.centerx, content.bottom - 150), 32,
                  theme.OFF_WHITE, anchor="center", outline=2)
        prev = pygame.Rect(content.x, content.bottom - 110, 260, 100)
        nxt = pygame.Rect(content.right - 260, content.bottom - 110, 260, 100)
        if page > 0 and ui.button(surface, "help_prev", prev, "Back", theme.GREY_DARK, size=38):
            self.tab -= 1
        if page < len(HELP_PAGES) - 1:
            if ui.button(surface, "help_next", nxt, "Next", theme.GREEN, size=38):
                self.tab += 1
        elif ui.button(surface, "help_next", nxt, "Done", theme.GREEN, size=38):
            self.close()


class StatisticsScreen(Screen):
    def draw(self, surface, ui, dt):
        game = self.game
        st = game.stats
        content = self.page_frame(surface, ui, "Statistics", "chart")
        y = self.begin_scroll(surface, ui, content, 2000, dt)
        stats = game.stats_cache.get(game.current_planet)
        # Production chain analysis
        box = pygame.Rect(content.x, y, content.width - 16, 120 + len(stats.stage_rockets) * 76 if stats else 200)
        self.card(surface, box)
        draw_text(surface, f"Production chain - {game.config.planets[game.current_planet]['name']}",
                  (box.x + 20, box.y + 16), 36, theme.WHITE, outline=3)
        draw_text(surface, f"Building: {game.config.rockets[game.factory.rocket_id]['name']}", (box.x + 20, box.y + 62),
                  28, theme.OFF_WHITE, kind="body")
        if stats:
            best = max(stats.stage_rockets.values()) or 1.0
            yy = box.y + 110
            for fid, rps in stats.stage_rockets.items():
                name = game.config.floors[fid]["name"] if fid in game.config.floors else fid
                draw_text(surface, name, (box.x + 20, yy + 4), 28, theme.WHITE, kind="body", max_width=320)
                bar = pygame.Rect(box.x + 350, yy, box.width - 620, 34)
                color = theme.RED if fid == stats.bottleneck else theme.GREEN
                progress_bar(surface, bar, rps / best, color)
                draw_text(surface, game.describe_money(rps * stats.value_per_rocket) + "/s", (box.right - 20, yy + 2), 28,
                          theme.WHITE, anchor="topright", outline=2)
                yy += 76
        y = box.bottom + 20
        rows = [("Income now", game.describe_money(game.total_income()) + "/s"),
                ("Automated income", game.describe_money(game.total_auto_income()) + "/s"),
                ("Best income", game.describe_money(st["best_income"]) + "/s"),
                ("Total earned", game.describe_money(st["total_earned"])),
                ("Earned this run", game.describe_money(game.run_earned)),
                ("Rockets launched", format_number(st["rockets_launched"])),
                ("Components made", format_number(st["components_made"])),
                ("Upgrades bought", format_number(st["upgrades_bought"])),
                ("Managers hired", format_number(st["managers_hired"])),
                ("Abilities used", format_number(st["abilities_used"])),
                ("Research done", f"{len(game.research.done)}/{len(game.config.research_list)}"),
                ("Planets", f"{len(game.factories)}/{len(game.config.planet_list)}"),
                ("Rockets unlocked", f"{len(game.unlocked_rockets)}/{len(game.config.rocket_list)}"),
                ("Space Legacy resets", format_number(st["prestiges"])),
                ("Legacy Stars (total)", format_number(game.prestige.total_stars)),
                ("Research Points earned", format_number(st["rp_earned"])),
                ("Gems earned", format_number(st["gems_earned"])),
                ("Floor taps", format_number(st["taps"])),
                ("Time played", format_duration(st["seconds_played"])),
                ("Offline cap", format_duration(game.offline_cap_seconds())),
                ("Offline efficiency", f"{game.offline_efficiency() * 100:.0f}%")]
        box = pygame.Rect(content.x, y, content.width - 16, 40 + len(rows) * 56)
        self.card(surface, box)
        yy = box.y + 20
        for label, value in rows:
            draw_text(surface, label, (box.x + 24, yy), 30, theme.TEXT_DIM, kind="body")
            draw_text(surface, value, (box.right - 24, yy), 32, theme.WHITE, anchor="topright", outline=2)
            yy += 56
        self.end_scroll(surface, ui, content)


class OfflineScreen(Screen):
    kind = "popup"

    def draw(self, surface, ui, dt):
        game = self.game
        report = game.pending_offline
        if report is None:
            self.close()
            return
        content = self.popup_frame(surface, ui, "Welcome Back!", (920, 1060), closable=False, icon="moon")
        bounce = math.sin(self.age * 3) * 8
        surface.blit(icons.icon("coin", 190), (content.centerx - 95, content.y + bounce))
        y = content.y + 230
        rows = [("Time away", format_duration(report.seconds_away)),
                ("Time counted", format_duration(report.seconds_counted) + (" (cap)" if report.capped else "")),
                ("Rockets launched", format_number(report.rockets)),
                ("Research Points", format_number(report.rp))]
        for label, value in rows:
            draw_text(surface, label, (content.x + 30, y), 34, theme.TEXT_DIM, kind="body")
            draw_text(surface, value, (content.right - 30, y), 36, theme.WHITE, anchor="topright", outline=2)
            y += 60
        draw_text(surface, "Money earned", (content.centerx, y + 20), 36, theme.OFF_WHITE, anchor="midtop", outline=2)
        draw_text(surface, game.describe_money(report.money), (content.centerx, y + 70), 80, theme.YELLOW,
                  anchor="midtop", outline=6)
        if report.capped:
            draw_text(surface, "Research 'Extended Shifts' to stay away longer!", (content.centerx, y + 170), 26,
                      theme.TEXT_DIM, anchor="midtop", kind="body")
        btn = pygame.Rect(content.centerx - 220, content.bottom - 130, 440, 116)
        if ui.button(surface, "collect_offline", btn, "Collect", theme.GREEN, size=50):
            collected = game.collect_offline()
            if collected:
                self.app.audio.play("coin")
                self.app.particles.emit("coin", btn.centerx, btn.centery, 30, spread=math.pi, speed=700, life=1.2,
                                        size=44, gravity=900, screen=True)
            self.close()
