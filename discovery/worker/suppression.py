"""
discovery.worker.suppression — Suppression Ladder & fatigue counter manager.
§5.4 edgecases.md: Manages impression counters and multi-tier suppression durations.
"""

from typing import Dict, Set, Optional
import time


class SuppressionManager:
    """In-memory KV mock / Valkey wrapper for user suppression counters."""

    def __init__(self):
        # Key: (user_id, l1_id) -> cooldown_until_timestamp
        self._category_cooldowns: Dict[tuple[int, int], float] = {}
        # Key: user_id -> list of impression timestamps in rolling 7d
        self._user_impressions_7d: Dict[int, list[float]] = {}

    def is_l1_suppressed(self, user_id: int, l1_id: int, now: Optional[float] = None) -> bool:
        """Returns True if l1_id category is under active cooldown for user."""
        if now is None:
            now = time.time()
        cooldown_until = self._category_cooldowns.get((user_id, l1_id), 0.0)
        return now < cooldown_until

    def get_suppressed_l1_ids(self, user_id: int, now: Optional[float] = None) -> Set[int]:
        """Returns set of all L1 category IDs under active suppression for user."""
        if now is None:
            now = time.time()
        suppressed = set()
        for (u_id, l1_id), cooldown_until in self._category_cooldowns.items():
            if u_id == user_id and now < cooldown_until:
                suppressed.add(l1_id)
        return suppressed

    def record_dismissal(
        self, user_id: int, l1_id: int, reason_code: str, is_life_stage: bool = False, now: Optional[float] = None
    ) -> float:
        """
        Applies Suppression Ladder rules on explicit user dismissal:
        - "not_now" -> session suppression (1 hour)
        - "too_expensive" -> 90-day price-band suppression
        - "not_interested" -> 180-day category suppression (365d if life-stage Pet/Baby)
        """
        if now is None:
            now = time.time()

        if reason_code == "not_now":
            duration_seconds = 3600  # 1 hour
        elif reason_code == "too_expensive":
            duration_seconds = 90 * 86400  # 90 days
        elif reason_code == "not_interested":
            duration_seconds = 365 * 86400 if is_life_stage else 180 * 86400
        else:
            duration_seconds = 86400  # 1 day default

        cooldown_until = now + duration_seconds
        self._category_cooldowns[(user_id, l1_id)] = cooldown_until
        return cooldown_until

    def record_impression(self, user_id: int, now: Optional[float] = None) -> int:
        """Records a Slot A impression and returns active count in rolling 7 days."""
        if now is None:
            now = time.time()
        history = self._user_impressions_7d.setdefault(user_id, [])
        # Prune older than 7 days (604800 seconds)
        cutoff = now - 604800
        history = [t for t in history if t > cutoff]
        history.append(now)
        self._user_impressions_7d[user_id] = history
        return len(history)

    def get_impressions_7d_count(self, user_id: int, now: Optional[float] = None) -> int:
        if now is None:
            now = time.time()
        history = self._user_impressions_7d.get(user_id, [])
        cutoff = now - 604800
        return sum(1 for t in history if t > cutoff)
