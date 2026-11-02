import math

import pytest

from game.core.numformat import MAX_VALUE, clamp_big, format_duration, format_money, format_number
from game.economy.formulas import (bulk_cost, legacy_stars_for, leveled_output, max_affordable,
                                   milestone_multiplier, next_milestone, upgrade_cost)


@pytest.mark.parametrize("value,expected", [
    (0, "0"), (5, "5"), (999, "999"), (1000, "1K"), (1500, "1.5K"), (1_000_000, "1M"),
    (2_400_000, "2.4M"), (1_000_000_000, "1B"), (12_600_000_000, "12.6B"), (1e12, "1T"),
    (1e15, "1Qa"), (143_000_000, "143M"), (2.5, "2.5"), (999_999, "1M"),
])
def test_format_number(value, expected):
    assert format_number(value) == expected


def test_format_huge_and_negative_values():
    assert format_number(1e36) == "1aa"
    assert format_number(-1500) == "-1.5K"
    assert format_number(float("inf")).endswith("e300") or format_number(float("inf"))
    assert format_number(float("nan")) == "0"
    assert format_number(1e300)  # never crashes
    assert "e" in format_number(12345, scientific=True)


def test_clamp_and_money_format():
    assert clamp_big(1e305) == MAX_VALUE
    assert clamp_big(float("nan")) == 0.0
    assert format_money(2_400_000) == "$2.4M"


def test_format_duration():
    assert format_duration(5) == "5s"
    assert format_duration(65) == "1m 05s"
    assert format_duration(4 * 3600 + 32 * 60) == "4h 32m"
    assert format_duration(-10) == "0s"
    assert format_duration(90000) == "1d 1h"


def test_upgrade_cost_growth():
    assert upgrade_cost(10, 1.15, 1) == 10
    assert math.isclose(upgrade_cost(10, 1.15, 2), 11.5)
    assert upgrade_cost(10, 1.15, 0) == 10  # clamps invalid levels


def test_bulk_cost_matches_sum():
    total = sum(upgrade_cost(8, 1.12, lvl) for lvl in range(5, 15))
    assert math.isclose(bulk_cost(8, 1.12, 5, 10), total, rel_tol=1e-9)
    assert bulk_cost(8, 1.12, 5, 0) == 0
    assert bulk_cost(5, 1.0, 1, 4) == 20


def test_max_affordable_exact():
    base, growth = 8, 1.12
    for money in (0, 7.9, 8, 100, 12345.6, 1e9):
        n = max_affordable(base, growth, 3, money)
        assert bulk_cost(base, growth, 3, n) <= money
        assert bulk_cost(base, growth, 3, n + 1) > money
    assert max_affordable(base, growth, 3, 1e30, limit=25) == 25


def test_huge_costs_do_not_overflow():
    assert upgrade_cost(1e10, 1.2, 100000) == MAX_VALUE
    assert bulk_cost(1e10, 1.2, 5000, 100) == MAX_VALUE


def test_milestones():
    ms = [[10, 2], [25, 3], [50, 5], [100, 10]]
    assert milestone_multiplier(9, ms) == 1
    assert milestone_multiplier(10, ms) == 2
    assert milestone_multiplier(99, ms) == 5
    assert milestone_multiplier(150, ms) == 10
    assert next_milestone(30, ms) == (50, 5)
    assert next_milestone(100, ms) is None
    assert leveled_output(1.0, 10, ms) == 20
    assert leveled_output(1.0, 0, ms) == 0


def test_legacy_stars():
    assert legacy_stars_for(0, 1e10, 10, 0.5) == 0
    assert legacy_stars_for(1e10, 1e10, 10, 0.5) == 10
    assert legacy_stars_for(4e10, 1e10, 10, 0.5) == 20
