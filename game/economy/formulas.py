"""Pure economy formulas (no game state, easy to unit test).

Upgrade Cost  = Base Cost * Growth ^ (Level - 1)
Output        = Base Output * Level * Milestone Multiplier * (other multipliers)
"""
from __future__ import annotations

import math

from game.core.numformat import MAX_VALUE, clamp_big


def upgrade_cost(base_cost: float, growth: float, level: int) -> float:
    """Cost to go from ``level`` to ``level + 1``."""
    if level < 1:
        level = 1
    try:
        return clamp_big(base_cost * growth ** (level - 1))
    except OverflowError:
        return MAX_VALUE


def bulk_cost(base_cost: float, growth: float, level: int, count: int) -> float:
    """Total cost of buying ``count`` levels starting at ``level``.

    Uses the geometric series sum so it is exact and fast even for x1000.
    """
    if count <= 0:
        return 0.0
    first = upgrade_cost(base_cost, growth, level)
    if growth == 1:
        return clamp_big(first * count)
    try:
        return clamp_big(first * (growth ** count - 1) / (growth - 1))
    except OverflowError:
        return MAX_VALUE


def max_affordable(base_cost: float, growth: float, level: int, money: float,
                   limit: int | None = None) -> int:
    """Largest number of levels that can be bought with ``money``.

    Solves the geometric series for ``count`` and then corrects for floating
    point rounding so that the result is always affordable.
    """
    if money <= 0:
        return 0
    first = upgrade_cost(base_cost, growth, level)
    if first <= 0 or first > money:
        return 0
    if growth == 1:
        count = int(money // first)
    else:
        value = money * (growth - 1) / first + 1
        count = int(math.floor(math.log(value) / math.log(growth)))
    if limit is not None:
        count = min(count, limit)
    count = max(count, 0)
    # Floating point safety: step down until affordable, then try one more.
    while count > 0 and bulk_cost(base_cost, growth, level, count) > money:
        count -= 1
    while (limit is None or count < limit) and \
            bulk_cost(base_cost, growth, level, count + 1) <= money:
        count += 1
    return count


def milestone_multiplier(level: int, milestones: list[list[float]]) -> float:
    """Total milestone multiplier for a level.

    ``milestones`` is a sorted list of ``[level, total_multiplier]`` pairs, for
    example ``[[10, 2], [25, 3]]`` means level 10+ gives x2 and level 25+ gives x3.
    """
    mult = 1.0
    for req_level, value in milestones:
        if level >= req_level:
            mult = float(value)
        else:
            break
    return mult


def next_milestone(level: int, milestones: list[list[float]]) -> tuple[int, float] | None:
    """Return the next ``(level, multiplier)`` milestone, or ``None`` if maxed."""
    for req_level, value in milestones:
        if level < req_level:
            return int(req_level), float(value)
    return None


def previous_milestone_level(level: int, milestones: list[list[float]]) -> int:
    prev = 0
    for req_level, _ in milestones:
        if level >= req_level:
            prev = int(req_level)
    return prev


def leveled_output(base: float, level: int, milestones: list[list[float]]) -> float:
    """Base output scaled by level and milestone multiplier."""
    if level <= 0:
        return 0.0
    return clamp_big(base * level * milestone_multiplier(level, milestones))


def legacy_stars_for(run_earnings: float, divisor: float, scale: float, exponent: float) -> int:
    """Prestige formula: stars = floor(scale * (earnings / divisor) ^ exponent)."""
    if run_earnings <= 0:
        return 0
    return int(math.floor(scale * (run_earnings / divisor) ** exponent))
