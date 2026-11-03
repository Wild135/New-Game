"""Original sound effects and music, synthesised with numpy.

No external audio files are needed, so there are no licensing concerns.
``tools/generate_assets.py`` can also write these sounds to WAV files.
"""
from __future__ import annotations

import math

import numpy as np

RATE = 22050


def _env(n: int, attack: float = 0.01, release: float = 0.2) -> np.ndarray:
    t = np.arange(n) / RATE
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    total = n / RATE
    r = np.clip((total - t) / max(release, 1e-4), 0, 1)
    return a * r


def _tone(freq, dur, wave="sine", vol=0.5, attack=0.005, release=0.1, slide=0.0):
    n = int(RATE * dur)
    t = np.arange(n) / RATE
    f = freq + slide * t / max(dur, 1e-4)
    phase = 2 * np.pi * np.cumsum(f) / RATE
    if wave == "square":
        sig = np.sign(np.sin(phase)) * 0.6
    elif wave == "tri":
        sig = 2 / np.pi * np.arcsin(np.sin(phase))
    elif wave == "saw":
        sig = 2 * ((phase / (2 * np.pi)) % 1) - 1
    else:
        sig = np.sin(phase)
    return sig * _env(n, attack, release) * vol


def _noise(dur, vol=0.5, attack=0.01, release=0.3, lowpass=0.0, seed=1):
    n = int(RATE * dur)
    rng = np.random.default_rng(seed)
    sig = rng.uniform(-1, 1, n)
    if lowpass > 0:
        # simple one-pole low pass filter
        alpha = lowpass
        out = np.empty_like(sig)
        acc = 0.0
        for i in range(n):
            acc += alpha * (sig[i] - acc)
            out[i] = acc
        sig = out / max(1e-6, np.max(np.abs(out)))
    return sig * _env(n, attack, release) * vol


def _concat(*parts):
    return np.concatenate(parts)


def _mix(length, *layers):
    out = np.zeros(length)
    for start, sig in layers:
        s = int(start * RATE)
        e = min(length, s + len(sig))
        out[s:e] += sig[: e - s]
    return out


def _to_int16(sig: np.ndarray) -> np.ndarray:
    peak = np.max(np.abs(sig)) or 1.0
    if peak > 1:
        sig = sig / peak
    return (sig * 32000).astype(np.int16)


def sfx_library() -> dict[str, np.ndarray]:
    lib: dict[str, np.ndarray] = {}
    lib["click"] = _tone(900, 0.05, "sine", 0.5, release=0.04, slide=-300)
    lib["tap"] = _concat(_tone(520, 0.04, "tri", 0.45, release=0.03), _tone(780, 0.05, "tri", 0.35, release=0.04))
    coin = _mix(int(RATE * 0.3), (0, _tone(1318, 0.08, "square", 0.25, release=0.06)),
                (0.07, _tone(1760, 0.2, "square", 0.25, release=0.18)))
    lib["coin"] = coin
    up = np.zeros(int(RATE * 0.45))
    for i, f in enumerate((523, 659, 784, 1046)):
        up = _mix(len(up), (0, up), (i * 0.07, _tone(f, 0.16, "tri", 0.4, release=0.12)))
    lib["upgrade"] = up
    lib["conveyor"] = _noise(0.25, 0.25, 0.02, 0.1, lowpass=0.05, seed=3)
    lib["machine"] = _mix(int(RATE * 0.3), (0, _tone(110, 0.3, "saw", 0.25, release=0.1)),
                          (0, _noise(0.3, 0.12, lowpass=0.1, seed=5)))
    lib["assembly"] = _mix(int(RATE * 0.35), (0, _tone(300, 0.08, "square", 0.25)), (0.12, _tone(300, 0.08, "square", 0.25)),
                           (0.2, _noise(0.12, 0.3, 0.001, 0.1, seed=9)))
    lib["countdown"] = _tone(880, 0.18, "sine", 0.45, release=0.15)
    lib["ignition"] = _mix(int(RATE * 0.8), (0, _noise(0.8, 0.6, 0.01, 0.5, lowpass=0.08, seed=11)),
                           (0, _tone(70, 0.8, "saw", 0.35, release=0.5)))
    rumble = _noise(2.4, 0.7, 0.05, 1.6, lowpass=0.03, seed=13)
    lib["launch"] = _mix(len(rumble), (0, rumble), (0, _tone(60, 2.4, "saw", 0.3, 0.05, 1.5, slide=40)))
    ach = np.zeros(int(RATE * 0.8))
    for i, f in enumerate((784, 988, 1175, 1568)):
        ach = _mix(len(ach), (0, ach), (i * 0.09, _tone(f, 0.35, "tri", 0.35, release=0.3)))
    lib["achievement"] = ach
    lib["ability"] = _mix(int(RATE * 0.6), (0, _tone(300, 0.6, "saw", 0.3, 0.01, 0.3, slide=900)),
                          (0, _tone(600, 0.6, "sine", 0.2, 0.01, 0.3, slide=1200)))
    res = np.zeros(int(RATE * 0.7))
    for i, f in enumerate((660, 880, 660, 1320)):
        res = _mix(len(res), (0, res), (i * 0.1, _tone(f, 0.2, "sine", 0.35, release=0.15)))
    lib["research"] = res
    lib["error"] = _concat(_tone(220, 0.1, "square", 0.25), _tone(180, 0.15, "square", 0.25))
    lib["whoosh"] = _noise(0.35, 0.35, 0.1, 0.2, lowpass=0.2, seed=17)
    lib["unlock"] = _mix(int(RATE * 0.9), (0, _tone(392, 0.25, "tri", 0.4)), (0.15, _tone(523, 0.25, "tri", 0.4)),
                         (0.3, _tone(784, 0.5, "tri", 0.4, release=0.4)))
    return {k: _to_int16(v) for k, v in lib.items()}


def music_track(seconds_per_bar: float = 2.0, bars: int = 16) -> np.ndarray:
    """A friendly, futuristic loop: pads, arpeggio, bass and soft drums."""
    total = int(RATE * seconds_per_bar * bars)
    out = np.zeros(total)
    # Chord progression (I - vi - IV - V style) in C major, as MIDI notes.
    progression = [(48, 52, 55, 59), (45, 48, 52, 55), (41, 45, 48, 52), (43, 47, 50, 53)]

    def midi(n):
        return 440.0 * 2 ** ((n - 69) / 12)
    beat = seconds_per_bar / 4
    for bar in range(bars):
        chord = progression[bar % 4]
        start = bar * seconds_per_bar
        # warm pad
        for note in chord[1:]:
            pad = _tone(midi(note + 12), seconds_per_bar, "tri", 0.06, attack=0.3, release=0.4)
            out = _mix(total, (0, out), (start, pad))
        # bass on beats 1 and 3
        for b in (0, 2):
            out = _mix(total, (0, out), (start + b * beat, _tone(midi(chord[0] - 12), beat * 1.6, "tri", 0.22, release=0.2)))
        # arpeggio of 8th notes
        arp = [chord[0] + 24, chord[1] + 24, chord[2] + 24, chord[3] + 24, chord[2] + 24, chord[1] + 24, chord[3] + 24, chord[2] + 36]
        for i, note in enumerate(arp):
            if bar >= 2 or i % 2 == 0:
                out = _mix(total, (0, out), (start + i * beat / 2, _tone(midi(note), beat * 0.45, "square", 0.035, release=0.12)))
        # drums from bar 4
        if bar >= 4:
            for b in range(4):
                kick = _tone(120, 0.18, "sine", 0.35, 0.001, 0.15, slide=-80)
                out = _mix(total, (0, out), (start + b * beat, kick))
                hat = _noise(0.05, 0.05, 0.001, 0.04, seed=bar * 4 + b)
                out = _mix(total, (0, out), (start + b * beat + beat / 2, hat))
            snare = _noise(0.16, 0.12, 0.001, 0.14, seed=99 + bar)
            out = _mix(total, (0, out), (start + beat, snare), (start + 3 * beat, snare))
    # gentle fade at loop edges to avoid clicks
    fade = int(RATE * 0.02)
    out[:fade] *= np.linspace(0, 1, fade)
    out[-fade:] *= np.linspace(1, 0, fade)
    return _to_int16(out * 0.9)


def write_wav(path, samples: np.ndarray) -> None:
    import wave
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(samples.tobytes())


def duration(samples: np.ndarray) -> float:
    return len(samples) / RATE


__all__ = ["sfx_library", "music_track", "write_wav", "RATE", "duration", "math"]
