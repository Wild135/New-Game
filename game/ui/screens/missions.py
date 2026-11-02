"""Missions, Achievements, Daily login calendar and Free Gift."""
from __future__ import annotations

import math

import pygame

from game.core.numformat import format_duration, format_number
from game.rendering import icons
from game.rendering.draw import draw_paragraph, draw_text, progress_bar
from game.ui import theme
from game.ui.screens.base import Screen


def reward_text(game, reward: dict) -> str:
    parts = []
    if reward.get("gems"):
        parts.append(f"{reward['gems']} gems")
    if reward.get("rp"):
        parts.append(f"{reward['rp']} RP")
    if reward.get("credits"):
        parts.append(game.describe_money(reward["credits"]))
    if reward.get("credits_minutes"):
        parts.append(f"{reward['credits_minutes']} min of income")
    return " + ".join(parts)


def reward_icon(reward: dict) -> str:
    if reward.get("gems"):
        return "gem"
    if reward.get("rp"):
        return "rp"
    return "coin"


class MissionsScreen(Screen):
    def draw(self, surface, ui, dt):
        content = self.page_frame(surface, ui, "Missions", "clipboard")
        self.tabs(surface, ui, pygame.Rect(content.x, content.y, content.width, 80), ["Missions", "Achievements"])
        area = pygame.Rect(content.x, content.y + 100, content.width, content.height - 100)
        if self.tab == 0:
            self.draw_missions(surface, ui, area, dt)
        else:
            self.draw_achievements(surface, ui, area, dt)

    def mission_row(self, surface, ui, uid, r, text, progress, target, reward, claimed, on_claim):
        game = self.game
        self.card(surface, r, border=theme.GREEN if progress >= target and not claimed else (90, 130, 210))
        surface.blit(icons.icon(reward_icon(reward), 80), (r.x + 16, r.y + 20))
        draw_text(surface, text, (r.x + 116, r.y + 16), 34, theme.WHITE, outline=3, max_width=r.width - 400)
        bar = pygame.Rect(r.x + 116, r.y + 66, r.width - 400, 30)
        progress_bar(surface, bar, progress / max(target, 1e-9))
        draw_text(surface, f"{format_number(progress)}/{format_number(target)}", bar.center, 22, theme.WHITE,
                  anchor="center", outline=2)
        draw_text(surface, "Reward: " + reward_text(game, reward), (r.x + 116, r.y + 104), 26, theme.YELLOW, kind="body",
                  max_width=r.width - 400)
        btn = pygame.Rect(r.right - 250, r.y + 26, 230, 96)
        if claimed:
            ui.button(surface, uid, btn, "Claimed", theme.GREY, size=32, icon="check", icon_size=34)
        elif progress >= target:
            if ui.button(surface, uid, btn, "Claim!", theme.ORANGE, size=38):
                if on_claim():
                    self.app.audio.play("achievement")
                    self.app.particles.emit("gem", btn.centerx, btn.centery, 14, spread=math.pi, speed=500,
                                            life=1.0, size=36, gravity=800, screen=True)
        else:
            ui.button(surface, uid, btn, "In progress", theme.GREY_DARK, size=28)

    def draw_missions(self, surface, ui, area, dt):
        game = self.game
        m = game.missions
        m.refresh_daily(self.app.now())
        row_h = 150
        y = self.begin_scroll(surface, ui, area, 70 + row_h + 30 + 70 + len(m.daily) * (row_h + 10) + 40, dt)
        draw_text(surface, f"Main Mission ({min(m.main_index + 1, len(game.config.main_missions))}/"
                           f"{len(game.config.main_missions)})", (area.x + 10, y + 10), 40, theme.WHITE, outline=3)
        y += 70
        mission = m.current_main()
        if mission:
            progress, target = m.mission_progress(mission)
            self.mission_row(surface, ui, "claim_main_screen", pygame.Rect(area.x, y, area.width - 16, row_h),
                             mission["text"], progress, target, mission["reward"], False, m.claim_main)
        else:
            draw_text(surface, "You finished every main mission. Amazing!", (area.x + 10, y + 40), 34, theme.GREEN_LIGHT, outline=2)
        y += row_h + 30
        now = self.app.now()
        import datetime as _dt
        tomorrow = _dt.datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0) + _dt.timedelta(days=1)
        left = tomorrow.timestamp() - now
        draw_text(surface, "Daily Missions", (area.x + 10, y + 10), 40, theme.WHITE, outline=3)
        draw_text(surface, f"New in {format_duration(left)}", (area.right - 30, y + 18), 28, theme.TEXT_DIM,
                  anchor="topright", kind="body")
        y += 70
        for i, entry in enumerate(m.daily):
            ddef = m.daily_def(entry)
            if ddef is None:
                continue
            progress, target = m.daily_progress(entry)
            shown_div = ddef.get("display_div", 1)
            self.mission_row(surface, ui, f"daily:{i}", pygame.Rect(area.x, y, area.width - 16, row_h),
                             m.daily_text(entry), progress / shown_div, target / shown_div, ddef["reward"],
                             entry["claimed"], lambda i=i: m.claim_daily(i))
            y += row_h + 10
        self.end_scroll(surface, ui, area)

    def draw_achievements(self, surface, ui, area, dt):
        game = self.game
        m = game.missions
        achs = game.config.achievement_list
        row_h = 160
        y = self.begin_scroll(surface, ui, area, len(achs) * (row_h + 10) + 20, dt)
        for ach in achs:
            r = pygame.Rect(area.x, y, area.width - 16, row_h)
            if r.bottom > area.top and r.top < area.bottom:
                claimed = m.achievement_claimed[ach["id"]]
                tiers = ach["tiers"]
                reached = m.achievement_reached(ach)
                done_all = claimed >= len(tiers)
                target = tiers[min(claimed, len(tiers) - 1)]
                value = float(game.stats.get(ach["stat"], 0))
                self.card(surface, r, border=theme.GOLD if m.achievement_claimable(ach) else (90, 130, 210))
                surface.blit(icons.icon(ach["icon"], 84), (r.x + 16, r.y + 20))
                stars = "".join("*" for _ in range(claimed))
                draw_text(surface, f"{ach['name']}  {stars}", (r.x + 120, r.y + 14), 34, theme.WHITE, outline=3,
                          max_width=r.width - 400)
                draw_text(surface, f"{ach['category']} - Tier {min(claimed + 1, len(tiers))}/{len(tiers)}",
                          (r.x + 120, r.y + 56), 26, theme.TEXT_DIM, kind="body")
                bar = pygame.Rect(r.x + 120, r.y + 96, r.width - 400, 30)
                progress_bar(surface, bar, 1.0 if done_all else min(1.0, value / target), theme.GOLD)
                draw_text(surface, f"{format_number(min(value, target))}/{format_number(target)}", bar.center, 22,
                          theme.WHITE, anchor="center", outline=2)
                btn = pygame.Rect(r.right - 250, r.y + 30, 230, 96)
                if done_all:
                    ui.button(surface, f"ach:{ach['id']}", btn, "Complete", theme.GREEN, size=32, icon="check", icon_size=34)
                elif reached > claimed:
                    if ui.button(surface, f"ach:{ach['id']}", btn, f"+{ach['rewards'][claimed]}", theme.ORANGE, size=38,
                                 icon="gem", icon_size=44):
                        if m.claim_achievement(ach["id"]):
                            self.app.audio.play("achievement")
                            self.app.particles.emit("gem", btn.centerx, btn.centery, 12, spread=math.pi, speed=500,
                                                    life=1.0, size=34, gravity=800, screen=True)
                else:
                    ui.button(surface, f"ach:{ach['id']}", btn, f"{ach['rewards'][claimed]} gems", theme.GREY_DARK, size=30)
            y += row_h + 10
        self.end_scroll(surface, ui, area)


class DailyRewardScreen(Screen):
    kind = "popup"

    def draw(self, surface, ui, dt):
        game = self.game
        now = self.app.now()
        content = self.popup_frame(surface, ui, "Daily Reward", (980, 1180), icon="calendar")
        rewards = game.config.economy["daily_rewards"]
        can = game.missions.can_claim_login(now)
        today_idx = game.missions.login_reward_index(now)
        draw_paragraph(surface, "Come back every day to keep your streak going. Day 7 has the biggest prize!",
                       pygame.Rect(content.x, content.y, content.width, 90), 30, align="center")
        cw = (content.width - 30) // 4
        for i, reward in enumerate(rewards):
            row, col = divmod(i, 4)
            r = pygame.Rect(content.x + col * (cw + 10), content.y + 110 + row * 270, cw, 250)
            if i == 6:
                r = pygame.Rect(content.x + 3 * (cw + 10), content.y + 380, cw, 250)
            claimed_today = (not can) and i == (today_idx - 1) % len(rewards)
            past = i < today_idx
            is_today = i == today_idx and can
            border = theme.YELLOW if is_today else (theme.GREEN if past or claimed_today else (90, 130, 210))
            self.card(surface, r, (50, 80, 150) if is_today else (36, 58, 112), border)
            draw_text(surface, f"Day {i + 1}", (r.centerx, r.y + 14), 34, theme.WHITE, anchor="midtop", outline=3)
            surface.blit(icons.icon(reward_icon(reward), 100), (r.centerx - 50, r.y + 64))
            draw_text(surface, reward_text(game, reward).replace(" of income", ""), (r.centerx, r.bottom - 40), 24,
                      theme.YELLOW, anchor="midtop", outline=2, max_width=r.width - 10)
            if past or claimed_today:
                surface.blit(icons.icon("check", 70), (r.right - 74, r.y + 4))
        btn = pygame.Rect(content.centerx - 220, content.bottom - 130, 440, 116)
        if can:
            if ui.button(surface, "claim_daily", btn, "Claim!", theme.ORANGE, size=48):
                reward = game.missions.claim_login(now)
                if reward:
                    self.app.audio.play("achievement")
                    self.app.particles.emit("gem", btn.centerx, btn.centery, 20, spread=math.pi, speed=600,
                                            life=1.2, size=40, gravity=800, screen=True)
        else:
            ui.button(surface, "claim_daily", btn, "Come back tomorrow", theme.GREY, size=36)
        streak = game.missions.login_streak
        draw_text(surface, f"Current streak: {streak} day{'s' if streak != 1 else ''}", (content.centerx, btn.y - 20), 30,
                  theme.OFF_WHITE, anchor="midbottom", outline=2)


class RewardsScreen(Screen):
    kind = "popup"

    def draw(self, surface, ui, dt):
        game = self.game
        now = self.app.now()
        content = self.popup_frame(surface, ui, "Free Gift", (900, 900), icon="gift")
        ready = game.missions.gift_ready(now)
        bounce = abs(math.sin(self.age * 4)) * 20 if ready else 0
        surface.blit(icons.icon("gift", 260), (content.centerx - 130, content.y + 20 - bounce))
        gift = game.config.economy["free_gift"]
        draw_text(surface, "Contains: " + reward_text(game, gift), (content.centerx, content.y + 320), 32, theme.YELLOW,
                  anchor="midtop", outline=2, max_width=content.width)
        btn = pygame.Rect(content.centerx - 220, content.bottom - 140, 440, 116)
        if ready:
            if ui.button(surface, "claim_gift", btn, "Open Gift!", theme.ORANGE, size=46):
                if game.missions.claim_gift(now):
                    self.app.audio.play("achievement")
                    self.app.particles.emit("confetti", content.centerx, content.y + 150, 80, spread=math.pi, speed=700,
                                            life=1.6, size=16, gravity=600, screen=True)
        else:
            left = game.missions.gift_time_left(now)
            ui.button(surface, "claim_gift", btn, "Next gift in", theme.GREY, size=34, sublabel=format_duration(left))
            draw_paragraph(surface, "A new gift arrives every 4 hours.", pygame.Rect(content.x, content.y + 400,
                                                                                    content.width, 80), 30, align="center")
