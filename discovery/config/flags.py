"""
discovery.config.flags — Feature Flags & Deterministic Experiment Hashing.
§3.6 & §8.1: Hash assignment allocates users deterministically across Arm A, B, C and 5% holdout.
"""

import hashlib
from typing import Dict, Any, List, Optional


class FeatureFlags:
    """Runtime feature flags container with safe defaults."""

    def __init__(self, overrides: Optional[Dict[str, Any]] = None):
        self._flags: Dict[str, Any] = {
            "discovery.enabled": True,
            "discovery.slot_a.enabled": True,
            "discovery.slot_b.enabled": False,
            "discovery.cities": ["delhi", "gurgaon", "mumbai"],
            "discovery.traffic_pct": 100.0,
            "discovery.arm_split": {"A": 34, "B": 33, "C": 33},
            "discovery.a3.enabled": False,  # Phase 2 AI layer
            "discovery.a4.enabled": True,   # Safety gate
            "discovery.ranker_version": "v0",
            "discovery.f3_price_ceiling_paise": 14900,
            "discovery.blocked_l1": [8881, 8882, 8883, 8884, 8885, 8886],
        }
        if overrides:
            self._flags.update(overrides)

    def get(self, key: str, default: Any = None) -> Any:
        return self._flags.get(key, default)

    def is_enabled(self, key: str) -> bool:
        return bool(self._flags.get(key, False))

    def update(self, key: str, value: Any) -> None:
        self._flags[key] = value


def get_user_experiment_arm(user_id: int, arm_split: Optional[Dict[str, int]] = None) -> str:
    """
    Deterministically assigns a user to an experiment arm:
    - user_id <= 0 -> "EXCLUDED" (Guest sessions EC-P1-09)
    - Hash bucket 95-99 (5%) -> "HOLDOUT" (Long-run counterfactual holdout)
    - Hash bucket 0-94 (95%) -> Arm A (Control), Arm B (Deterministic), Arm C (AI)
    """
    if not user_id or user_id <= 0:
        return "EXCLUDED"

    if arm_split is None:
        arm_split = {"A": 34, "B": 33, "C": 33}

    # MD5 hash modulo 100 for deterministic 0-99 bucket
    hash_key = f"exp_cart_interrupt:{user_id}".encode("utf-8")
    hash_digest = hashlib.md5(hash_key).hexdigest()
    bucket = int(hash_digest, 16) % 100

    # 5% Long-run holdout
    if bucket >= 95:
        return "HOLDOUT"

    # Map bucket 0-94 across A/B/C split
    # Total ratio sum
    total_ratio = arm_split.get("A", 34) + arm_split.get("B", 33) + arm_split.get("C", 33)
    normalized_bucket = (bucket / 95.0) * total_ratio

    thresh_a = arm_split.get("A", 34)
    thresh_b = thresh_a + arm_split.get("B", 33)

    if normalized_bucket < thresh_a:
        return "A"
    elif normalized_bucket < thresh_b:
        return "B"
    else:
        return "C"
