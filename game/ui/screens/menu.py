"""Loading screen and Main Menu (full-screen scenes)."""
from __future__ import annotations

import math

import pygame

from game.rendering import art
from game.rendering.draw import draw_text, progress_bar
from game.ui import theme

EARTH_THEME = {"sky_top": [40, 70, 160], "sky_bottom": [130, 190, 250], "ground": [110, 80, 60],
               "hills": [70, 140, 110], "planet": [200, 200, 210]}


def draw_backdrop(surface: pygame.Surface, t: float) -> None:
    sky = art.sky_scene(EARTH_THEME, "menu", theme.WIDTH, theme.HEIGHT, "Rocket Empire HQ", (50, 90, 170))
    surface.blit(sky, (0, 0))
    for i in range(4):
        x = (t * (14 + i * 5) + i * 300) % (theme.WIDTH + 300) - 300
        surface.blit(art.cloud(200 + i * 30), (x, 300 + i * 160))
    tower_h = 420
    gy = theme.HEIGHT - 70
    surface.blit(art.launch_tower(tower_h), (560, gy - tower_h))
    surface.blit(art.launch_tower(tower_h), (900, gy - tower_h))
    rocket = art.rocket_sprite(360, fins=4)
    surface.blit(rocket, rocket.get_rect(midbottom=(775, gy - 20 + math.sin(t * 2) * 4)))


class LoadingScene:
    def __init__(self, app):
        self.app = app
        self.progress = 0.0
        self.t = 0.0

    def draw(self, surface: pygame.Surface, ui, dt: float, label: str) -> None:
        self.t += dt
        surface.fill((20, 34, 80))
        logo = art.logo(760)
        surface.blit(logo, logo.get_rect(center=(theme.WIDTH // 2, 640)))
        bar = pygame.Rect(140, 1180, theme.WIDTH - 280, 60)
        progress_bar(surface, bar, self.progress, theme.GREEN)
        draw_text(surface, label, (theme.WIDTH // 2, bar.bottom + 30), 40, theme.WHITE, anchor="midtop", outline=3)
        rocket = art.rocket_sprite(160)
        rocket = pygame.transform.rotate(rocket, -90)
        surface.blit(rocket, rocket.get_rect(center=(bar.x + bar.width * self.progress, bar.y - 70)))


class MainMenu:
    def __init__(self, app):
        self.app = app
        self.t = 0.0

    def draw(self, surface: pygame.Surface, ui, dt: float) -> None:
        self.t += dt
        draw_backdrop(surface, self.t)
        logo = art.logo(820)
        bob = math.sin(self.t * 1.5) * 10
        surface.blit(logo, logo.get_rect(center=(theme.WIDTH // 2, 420 + bob)))
        has_save = self.app.has_save
        play = pygame.Rect(theme.WIDTH // 2 - 280, 820, 560, 150)
        if ui.button(surface, "menu_play", play, "CONTINUE" if has_save else "PLAY", theme.GREEN, size=66):
            self.app.start_game()
        bw = 400
        items = [("How to Play", self.help), ("Settings", self.settings), ("Quit", self.app.quit)]
        for i, (label, action) in enumerate(items):
            r = pygame.Rect(theme.WIDTH // 2 - bw // 2, 1020 + i * 130, bw, 106)
            if ui.button(surface, f"menu:{label}", r, label, theme.BLUE if label != "Quit" else theme.GREY_DARK, size=44):
                action()
        draw_text(surface, "v1.0  -  Offline single-player  -  No ads, no real-money purchases",
                  (theme.WIDTH // 2, theme.HEIGHT - 30), 26, theme.WHITE, anchor="midbottom", kind="body", outline=2)

    def help(self):
        from game.ui.screens.settings import HelpScreen
        self.app.push(HelpScreen(self.app))

    def settings(self):
        self.app.start_game()
        self.app.open("settings")
