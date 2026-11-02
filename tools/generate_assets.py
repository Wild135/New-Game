"""Exports the game's procedurally generated art and audio to files.

The game draws its artwork and synthesises its sounds in code, so it works
without these files.  This tool writes them out so you can view, edit or
replace them:

* assets/audio/*.wav            sound effects and music (used by the game if present)
* assets/images/*.png           logo, rockets, icons, planets, app icon
* assets/sprites/workers/*.png  worker animation frames
* assets/images/icon.ico        Windows executable icon

Usage:  python tools/generate_assets.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from game.audio import synth  # noqa: E402
from game.core.config import GameConfig  # noqa: E402
from game.paths import resource_path  # noqa: E402


def main(audio: bool = True) -> None:
    pygame.init()
    pygame.display.set_mode((8, 8))
    from game.rendering import art, icons

    images = resource_path("assets", "images")
    sprites = resource_path("assets", "sprites", "workers")
    audio_dir = resource_path("assets", "audio")
    for folder in (images, sprites, audio_dir):
        folder.mkdir(parents=True, exist_ok=True)

    cfg = GameConfig()
    pygame.image.save(art.logo(900), str(images / "logo.png"))
    for rocket in cfg.rocket_list:
        surf = art.rocket_sprite(400, tuple(rocket["colors"]["body"]), tuple(rocket["colors"]["accent"]), rocket["fins"])
        pygame.image.save(surf, str(images / f"rocket_{rocket['id']}.png"))
    for planet in cfg.planet_list:
        surf = art.planet_sphere(tuple(planet["theme"]["planet"]), 120, ring=planet["id"] in ("titan", "kepler"),
                                 seed=planet["id"])
        pygame.image.save(surf, str(images / f"planet_{planet['id']}.png"))
    for name in icons.DRAWERS:
        pygame.image.save(icons.icon(name, 128), str(images / f"icon_{name}.png"))
    for state in ("idle", "walk", "work", "carry", "celebrate", "inspect"):
        for frame in range(8):
            pygame.image.save(art.worker_frame(state, frame), str(sprites / f"{state}_{frame}.png"))
    app_icon = pygame.Surface((256, 256), pygame.SRCALPHA)
    pygame.draw.circle(app_icon, (40, 70, 160), (128, 128), 124)
    rocket = art.rocket_sprite(220, fins=3)
    app_icon.blit(rocket, rocket.get_rect(center=(128, 128)))
    png_path = images / "icon.png"
    pygame.image.save(app_icon, str(png_path))
    _write_ico(png_path, images / "icon.ico")
    if audio:
        for name, samples in synth.sfx_library().items():
            synth.write_wav(audio_dir / f"{name}.wav", samples)
        synth.write_wav(audio_dir / "music.wav", synth.music_track())
    print(f"Assets written to {resource_path('assets')}")


def _write_ico(png_path, ico_path) -> None:
    """Write a .ico file that embeds the 256x256 PNG (supported since Windows Vista)."""
    import struct
    data = png_path.read_bytes()
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(data), 6 + 16)
    ico_path.write_bytes(header + entry + data)


if __name__ == "__main__":
    main(audio="--no-audio" not in sys.argv)
