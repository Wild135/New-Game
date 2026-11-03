"""Colours, fonts and layout constants shared by all screens."""
from __future__ import annotations

import pygame

from game.paths import resource_path

# The game is designed for a 1080 x 1920 portrait canvas.  The window can be
# any size - the canvas is scaled to fit (with letterboxing if needed).
WIDTH, HEIGHT = 1080, 1920
TOP_BAR_H = 118
NAV_H = 196
SAFE_MARGIN = 18

# Palette ---------------------------------------------------------------
NAVY = (22, 36, 74)
NAVY_DARK = (12, 22, 50)
NAVY_LIGHT = (44, 70, 130)
PANEL = (30, 50, 98)
PANEL_LIGHT = (58, 92, 160)
PANEL_BORDER = (120, 170, 240)
WHITE = (255, 255, 255)
OFF_WHITE = (236, 242, 255)
TEXT_DIM = (170, 190, 225)
BLACK = (0, 0, 0)
OUTLINE = (16, 24, 52)
GREEN = (98, 210, 60)
GREEN_DARK = (40, 140, 30)
GREEN_LIGHT = (160, 240, 100)
RED = (235, 70, 60)
RED_DARK = (160, 30, 30)
YELLOW = (255, 205, 40)
YELLOW_DARK = (210, 140, 10)
ORANGE = (255, 150, 40)
PURPLE = (170, 90, 255)
CYAN = (70, 200, 255)
BLUE = (60, 130, 240)
BLUE_DARK = (30, 70, 160)
GREY = (130, 140, 160)
GREY_DARK = (80, 88, 105)
GOLD = (255, 200, 60)

RARITY_COLORS = {"common": (150, 170, 190), "rare": (70, 150, 255),
                 "epic": (190, 90, 255), "legendary": (255, 190, 40)}

FONT_TITLE = "assets/fonts/LilitaOne-Regular.ttf"
FONT_BODY = "assets/fonts/Fredoka.ttf"


class Fonts:
    """Caches pygame Font objects by (kind, size)."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, int], pygame.font.Font] = {}
        self._paths = {"title": resource_path(FONT_TITLE), "body": resource_path(FONT_BODY)}

    def reset(self) -> None:
        """Forget cached fonts (needed after pygame.quit()/init())."""
        self._cache.clear()

    def get(self, size: int, kind: str = "title") -> pygame.font.Font:
        key = (kind, size)
        font = self._cache.get(key)
        if font is None:
            path = self._paths.get(kind)
            try:
                font = pygame.font.Font(str(path), size)
            except (FileNotFoundError, OSError):
                font = pygame.font.Font(None, int(size * 1.3))
            self._cache[key] = font
        return font


fonts = Fonts()
