"""Main mission chain, daily missions, daily login rewards, free gifts and achievements.

Everything is calculated from the lifetime statistics in ``game.stats`` so it is
tracked automatically.  Each reward can only be claimed once: the claim
functions advance an index or record the claim before paying out.
"""
from __future__ import annotations

import datetime as _dt
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from game.core.game import Game


def today_str(now: float) -> str:
    return _dt.date.fromtimestamp(now).isoformat()


class MissionSystem:
    def __init__(self, game: "Game"):
        self.game = game
        self.cfg = game.config
        self.main_index = 0
        self.daily_date = ""
        self.daily: list[dict] = []          # [{id, target, claimed}]
        self.daily_base: dict[str, float] = {}
        self.login_streak = 0
        self.last_login_claim = ""
        self.next_gift_time = 0.0
        self.achievement_claimed: dict[str, int] = {a["id"]: 0 for a in self.cfg.achievement_list}
        self.achievement_notified: dict[str, int] = {a["id"]: 0 for a in self.cfg.achievement_list}
        self._main_notified = -1

    # ------------------------------------------------------------------ main chain
    def current_main(self) -> dict | None:
        if self.main_index < len(self.cfg.main_missions):
            return self.cfg.main_missions[self.main_index]
        return None

    def mission_progress(self, mission: dict) -> tuple[float, float]:
        game = self.game
        target = float(mission["target"])
        mtype = mission["type"]
        if mtype == "stat":
            return min(target, float(game.stats.get(mission["stat"], 0))), target
        if mtype == "floor_level":
            return min(target, float(game.max_floor_level(mission.get("floor")))), target
        if mtype == "planet":
            return (1.0 if mission["planet"] in game.factories else 0.0), 1.0
        if mtype == "rocket":
            return (1.0 if mission["rocket"] in game.unlocked_rockets else 0.0), 1.0
        return 0.0, target

    def main_complete(self) -> bool:
        mission = self.current_main()
        if mission is None:
            return False
        progress, target = self.mission_progress(mission)
        return progress >= target

    def claim_main(self) -> bool:
        mission = self.current_main()
        if mission is None or not self.main_complete():
            return False
        self.main_index += 1          # advance first so it can never be claimed twice
        self.game.grant_reward(mission["reward"], source=mission["text"])
        self.game.emit("mission_claimed", text=mission["text"])
        return True

    # ------------------------------------------------------------------ daily
    def refresh_daily(self, now: float) -> None:
        date = today_str(now)
        if date == self.daily_date:
            return
        if self.daily_date and date < self.daily_date:
            return  # clock went backwards: keep the current day's missions
        self.daily_date = date
        rng = random.Random(date)
        picks = rng.sample(self.cfg.daily_pool, k=min(3, len(self.cfg.daily_pool)))
        self.daily = []
        for pick in picks:
            target = rng.choice(pick["targets"])
            self.daily.append({"id": pick["id"], "target": target, "claimed": False})
        self.daily_base = {k: float(v) for k, v in self.game.stats.items()}

    def daily_def(self, entry: dict) -> dict | None:
        for pick in self.cfg.daily_pool:
            if pick["id"] == entry["id"]:
                return pick
        return None

    def daily_progress(self, entry: dict) -> tuple[float, float]:
        ddef = self.daily_def(entry)
        if ddef is None:
            return 0.0, 1.0
        stat = ddef["stat"]
        value = float(self.game.stats.get(stat, 0)) - self.daily_base.get(stat, 0.0)
        return max(0.0, min(value, entry["target"])), float(entry["target"])

    def daily_text(self, entry: dict) -> str:
        ddef = self.daily_def(entry)
        if ddef is None:
            return "Unknown mission"
        shown = entry["target"] // ddef.get("display_div", 1)
        return ddef["text"].replace("{n}", str(int(shown)))

    def claim_daily(self, index: int) -> bool:
        if not 0 <= index < len(self.daily):
            return False
        entry = self.daily[index]
        progress, target = self.daily_progress(entry)
        if entry["claimed"] or progress < target:
            return False
        entry["claimed"] = True
        ddef = self.daily_def(entry)
        if ddef:
            self.game.grant_reward(ddef["reward"], source="Daily mission")
        return True

    # ------------------------------------------------------------------ login calendar
    def can_claim_login(self, now: float) -> bool:
        today = today_str(now)
        return today > self.last_login_claim  # ISO dates compare correctly as strings

    def login_reward_index(self, now: float) -> int:
        """Which day of the 7-day calendar would be claimed today."""
        today = _dt.date.fromtimestamp(now)
        yesterday = (today - _dt.timedelta(days=1)).isoformat()
        streak = self.login_streak if self.last_login_claim == yesterday else 0
        return streak % len(self.cfg.economy["daily_rewards"])

    def claim_login(self, now: float) -> dict | None:
        if not self.can_claim_login(now):
            return None
        index = self.login_reward_index(now)
        today = _dt.date.fromtimestamp(now)
        yesterday = (today - _dt.timedelta(days=1)).isoformat()
        self.login_streak = (self.login_streak + 1) if self.last_login_claim == yesterday else 1
        self.last_login_claim = today.isoformat()
        reward = self.cfg.economy["daily_rewards"][index]
        self.game.grant_reward(reward, source="Daily reward")
        return reward

    # ------------------------------------------------------------------ free gift
    def gift_ready(self, now: float) -> bool:
        period = self.cfg.economy["free_gift_hours"] * 3600
        if self.next_gift_time - now > period:
            self.next_gift_time = now + period  # clock moved backwards - cap the wait
        return now >= self.next_gift_time

    def gift_time_left(self, now: float) -> float:
        return max(0.0, self.next_gift_time - now)

    def claim_gift(self, now: float) -> bool:
        if not self.gift_ready(now):
            return False
        self.next_gift_time = now + self.cfg.economy["free_gift_hours"] * 3600
        self.game.grant_reward(self.cfg.economy["free_gift"], source="Free gift")
        return True

    # ------------------------------------------------------------------ achievements
    def achievement_reached(self, ach: dict) -> int:
        value = float(self.game.stats.get(ach["stat"], 0))
        return sum(1 for tier in ach["tiers"] if value >= tier)

    def achievement_claimable(self, ach: dict) -> bool:
        return self.achievement_reached(ach) > self.achievement_claimed[ach["id"]]

    def claim_achievement(self, ach_id: str) -> bool:
        ach = self.cfg.achievements[ach_id]
        claimed = self.achievement_claimed[ach_id]
        if self.achievement_reached(ach) <= claimed:
            return False
        self.achievement_claimed[ach_id] = claimed + 1
        self.game.grant_reward({"gems": ach["rewards"][claimed]}, source=ach["name"])
        return True

    def claimable_count(self, now: float) -> int:
        count = sum(1 for a in self.cfg.achievement_list if self.achievement_claimable(a))
        count += sum(1 for i, d in enumerate(self.daily)
                     if not d["claimed"] and self.daily_progress(d)[0] >= d["target"])
        if self.main_complete():
            count += 1
        return count

    def check_notifications(self) -> None:
        """Emit one-time events when a mission or achievement becomes claimable."""
        for ach in self.cfg.achievement_list:
            reached = self.achievement_reached(ach)
            if reached > self.achievement_notified[ach["id"]]:
                self.achievement_notified[ach["id"]] = reached
                self.game.emit("achievement", name=ach["name"], tier=reached)
        if self.main_complete() and self._main_notified != self.main_index:
            self._main_notified = self.main_index
            mission = self.current_main()
            self.game.emit("mission_complete", text=mission["text"] if mission else "")

    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {"main_index": self.main_index, "daily_date": self.daily_date, "daily": self.daily,
                "daily_base": self.daily_base, "login_streak": self.login_streak,
                "last_login_claim": self.last_login_claim, "next_gift_time": self.next_gift_time,
                "achievement_claimed": self.achievement_claimed,
                "achievement_notified": self.achievement_notified}

    def load(self, data: dict) -> None:
        self.main_index = max(0, int(data.get("main_index", 0)))
        self.daily_date = str(data.get("daily_date", ""))
        self.daily = [d for d in data.get("daily", []) if isinstance(d, dict) and "id" in d]
        self.daily_base = {k: float(v) for k, v in data.get("daily_base", {}).items()}
        self.login_streak = max(0, int(data.get("login_streak", 0)))
        self.last_login_claim = str(data.get("last_login_claim", ""))
        self.next_gift_time = float(data.get("next_gift_time", 0.0))
        for key in ("achievement_claimed", "achievement_notified"):
            stored = data.get(key, {})
            target = getattr(self, key)
            for aid in target:
                tiers = len(self.cfg.achievements[aid]["tiers"])
                target[aid] = max(0, min(int(stored.get(aid, 0)), tiers))
        # Already-notified achievements should never re-announce.
        for aid in self.achievement_notified:
            self.achievement_notified[aid] = max(self.achievement_notified[aid],
                                                 self.achievement_claimed[aid])
        self._main_notified = -1
