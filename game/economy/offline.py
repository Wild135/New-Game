"""Offline earnings.

When the game starts again we know how long the player was away.  Instead of
simulating every tick (slow), we use the factory's steady-state throughput:
the slowest automated stage decides how many rockets per second are launched.

Rules:
* Only floors run by a manager work offline (tapping needs a player).
* Time is capped (8 hours by default, research raises it).
* An efficiency factor applies (research raises it).
* Temporary boosts only count for the part of the absence they were active.
* Manager abilities and boost timers tick down by the elapsed time.

NOTE: A fully offline game trusts the device clock.  We block negative time
and cap the reward, but a determined player can still change their clock.
This cannot be made completely tamper-proof without an online server.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from game.core.numformat import clamp_big
from game.factories.factory import Factory

if TYPE_CHECKING:  # pragma: no cover
    from game.core.game import Game, OfflineReport


def compute_offline(game: "Game", elapsed: float) -> "OfflineReport":
    from game.core.game import OfflineReport

    report = OfflineReport(seconds_away=max(0.0, elapsed))
    if elapsed <= 0:
        return report
    cap = game.offline_cap_seconds()
    counted = min(elapsed, cap)
    report.capped = elapsed > cap
    report.seconds_counted = counted
    efficiency = game.offline_efficiency()

    base_global = game.global_modifiers(include_temporary=False)
    # Boosted portion: income multiplier while boosts were still running.
    segments: list[tuple[float, float]] = []   # (seconds, value multiplier)
    remaining_boosts = sorted(game.shop.boosts, key=lambda b: b["remaining"])
    start = 0.0
    for i, boost in enumerate(remaining_boosts):
        end = min(counted, boost["remaining"])
        if end > start:
            mult = 1.0
            for other in remaining_boosts[i:]:
                if other["stat"] == "value":
                    mult *= other["mult"]
            segments.append((end - start, mult))
            start = end
    if counted > start:
        segments.append((counted - start, 1.0))

    for pid in game.factories:
        stats = game.factory_stats(pid, include_temporary=False, global_mods=base_global)
        rockets_per_second = stats.auto_rocket_rate
        if rockets_per_second <= 0:
            continue
        # Rockets leave in batches, one batch per launch window.
        batch = max(1.0, rockets_per_second * stats.interval)
        rp_per_batch = Factory.rp_for_launch(batch, stats)
        for seconds, value_mult in segments:
            rockets = rockets_per_second * seconds * efficiency
            report.rockets += rockets
            report.money = clamp_big(report.money + rockets * stats.value_per_rocket * value_mult)
            report.rp += rockets / batch * rp_per_batch

    # Timers keep counting while away.
    game.managers.tick(elapsed)
    game.shop.tick(elapsed)
    for factory in game.factories.values():
        for floor in factory.floors.values():
            floor.manual_time = 0.0
    report.rockets = float(int(report.rockets))
    return report
