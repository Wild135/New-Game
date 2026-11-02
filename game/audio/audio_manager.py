"""Plays sound effects and music with master/music/sfx volume and mute.

If the computer has no audio device the game still runs silently.
WAV files in assets/audio are used when present; otherwise sounds are
synthesised at startup (see synth.py).
"""
from __future__ import annotations

import time

import pygame

from game.paths import resource_path

try:
    import numpy as np  # noqa: F401
    from game.audio import synth
    HAVE_NUMPY = True
except ImportError:  # pragma: no cover - numpy is a dependency
    HAVE_NUMPY = False


class AudioManager:
    def __init__(self, settings: dict):
        self.settings = settings
        self.enabled = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.music: pygame.mixer.Sound | None = None
        self.music_channel: pygame.mixer.Channel | None = None
        self._last_play: dict[str, float] = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=synth.RATE if HAVE_NUMPY else 22050, size=-16, channels=1, buffer=512)
            pygame.mixer.set_num_channels(24)
            self.enabled = True
        except pygame.error:
            self.enabled = False

    def load(self) -> None:
        if not self.enabled:
            return
        audio_dir = resource_path("assets", "audio")
        library = synth.sfx_library() if HAVE_NUMPY else {}
        for name, samples in library.items():
            wav = audio_dir / f"{name}.wav"
            try:
                if wav.exists():
                    self.sounds[name] = pygame.mixer.Sound(str(wav))
                else:
                    self.sounds[name] = pygame.sndarray.make_sound(self._shape(samples))
            except (pygame.error, ValueError):
                continue
        try:
            music_file = audio_dir / "music.wav"
            if music_file.exists():
                self.music = pygame.mixer.Sound(str(music_file))
            elif HAVE_NUMPY:
                self.music = pygame.sndarray.make_sound(self._shape(synth.music_track()))
        except (pygame.error, ValueError):
            self.music = None

    @staticmethod
    def _shape(samples):
        """Match the mixer's channel count (mono or stereo)."""
        init = pygame.mixer.get_init()
        channels = init[2] if init else 1
        if channels == 2:
            import numpy as np
            return np.ascontiguousarray(np.column_stack([samples, samples]))
        return samples

    # ------------------------------------------------------------------
    def _volume(self, kind: str) -> float:
        s = self.settings
        if s.get("muted"):
            return 0.0
        return float(s.get("master_volume", 0.8)) * float(s.get(f"{kind}_volume", 0.8))

    def play(self, name: str, volume: float = 1.0, min_gap: float = 0.04) -> None:
        if not self.enabled or name not in self.sounds:
            return
        now = time.monotonic()
        if now - self._last_play.get(name, 0.0) < min_gap:
            return  # avoid stacking the same sound many times per frame
        self._last_play[name] = now
        vol = self._volume("sfx") * volume
        if vol <= 0:
            return
        sound = self.sounds[name]
        channel = sound.play()
        if channel:
            channel.set_volume(vol)

    def start_music(self) -> None:
        if not self.enabled or self.music is None:
            return
        if self.music_channel is None or not self.music_channel.get_busy():
            self.music_channel = self.music.play(loops=-1, fade_ms=1500)
        self.apply_volumes()

    def apply_volumes(self) -> None:
        if self.music_channel:
            self.music_channel.set_volume(self._volume("music") * 0.6)

    def stop(self) -> None:
        if self.enabled:
            pygame.mixer.stop()
