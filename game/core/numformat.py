"""Number and time formatting helpers.

Idle games deal with huge numbers.  We store money as Python floats, which can
hold values up to about 1.8e308.  ``clamp_big`` keeps every value safely below
that limit so nothing can ever overflow to ``inf``.
"""
from __future__ import annotations

import math
import string

# The biggest value the economy is allowed to reach.  Far beyond anything a
# player will see in normal play, but still a safe distance from float overflow.
MAX_VALUE = 1e300

_BASE_SUFFIXES = ["", "K", "M", "B", "T", "Qa", "Qi", "Sx", "Sp", "Oc", "No", "Dc"]


def _build_suffixes() -> list[str]:
    suffixes = list(_BASE_SUFFIXES)
    # After "Dc" (1e33) we continue with aa, ab, ac ... like many idle games.
    letters = string.ascii_lowercase
    for first in letters:
        for second in letters:
            suffixes.append(first + second)
            if len(suffixes) * 3 > 310:
                return suffixes
    return suffixes


SUFFIXES = _build_suffixes()


def clamp_big(value: float) -> float:
    """Clamp a value into the safe range [-MAX_VALUE, MAX_VALUE] and remove NaN."""
    if value != value:  # NaN check
        return 0.0
    if value > MAX_VALUE:
        return MAX_VALUE
    if value < -MAX_VALUE:
        return -MAX_VALUE
    return value


def format_number(value: float, decimals: int = 2, scientific: bool = False) -> str:
    """Format a number compactly: 1500 -> '1.5K', 2_400_000 -> '2.4M'."""
    value = clamp_big(float(value))
    if value < 0:
        return "-" + format_number(-value, decimals, scientific)
    if value < 1000:
        if value == int(value):
            return str(int(value))
        if value < 10:
            return f"{value:.2f}".rstrip("0").rstrip(".")
        return f"{value:.1f}".rstrip("0").rstrip(".")
    exponent = int(math.floor(math.log10(value)))
    if scientific:
        mantissa = value / (10 ** exponent)
        return f"{mantissa:.{decimals}f}e{exponent}"
    group = exponent // 3
    if group >= len(SUFFIXES):
        mantissa = value / (10 ** exponent)
        return f"{mantissa:.{decimals}f}e{exponent}"
    scaled = value / (1000 ** group)
    # Rounding can push 999.995 up to 1000.00 - move to the next suffix then.
    if round(scaled, decimals) >= 1000 and group + 1 < len(SUFFIXES):
        group += 1
        scaled = value / (1000 ** group)
    if scaled >= 100:
        text = f"{scaled:.{max(0, decimals - 1)}f}"
    else:
        text = f"{scaled:.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text + SUFFIXES[group]


def format_money(value: float, scientific: bool = False) -> str:
    return "$" + format_number(value, scientific=scientific)


def format_rate(value: float, scientific: bool = False) -> str:
    return format_number(value, scientific=scientific) + "/s"


def format_duration(seconds: float) -> str:
    """Human readable duration: 4h 32m, 5m 03s, 12s."""
    seconds = max(0, int(seconds))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"
