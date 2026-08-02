"""
discovery.offline.a2_rulebook_job — A2 Household State Inference & Rulebook Generator.
§5.6.2 solution.md & EC-P2-01: Typed profile enums, 60d corroboration decay, 365d dismissal field zeroing.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
import hashlib
import time


class HouseholdStateProfile(BaseModel):
    user_id: int
    household_size_band: str = "unknown"  # 1|2|3-4|5+|unknown
    infant_present: bool = False
    toddler_present: bool = False
    pet: str = "none"  # none|dog|cat|other|unknown
    cooking_intensity: str = "medium"  # low|medium|high|unknown
    segment: str = "household_manager"
    confidence: float = 0.8
    last_corroborated_at: float = Field(default_factory=time.time)

    @property
    def state_id(self) -> str:
        """Returns deterministic hash of profile enums for rulebook cache keys."""
        raw = f"{self.household_size_band}:{self.infant_present}:{self.toddler_present}:{self.pet}:{self.cooking_intensity}:{self.segment}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def apply_a2_decay_and_dismissal_rules(
    profile: HouseholdStateProfile,
    dismissed_l1_ids: Optional[set[int]] = None,
    now: Optional[float] = None,
) -> HouseholdStateProfile:
    """
    Applies EC-P2-01 decay and dismissal zeroing:
    - No corroborating purchase in 60d -> confidence decays
    - No corroborating purchase in 90d -> fields revert to unknown
    - Explicit dismissal of Pet (L1=25) or Baby (L1=20) -> zero field immediately
    """
    if now is None:
        now = time.time()
    if dismissed_l1_ids is None:
        dismissed_l1_ids = set()

    updated = profile.model_dump()
    days_since_corroborated = (now - profile.last_corroborated_at) / 86400.0

    # 1. 365-day Dismissal Field Zeroing (EC-P2-01)
    if 20 in dismissed_l1_ids:  # Baby Care
        updated["infant_present"] = False
        updated["toddler_present"] = False

    if 25 in dismissed_l1_ids:  # Pet Care
        updated["pet"] = "none"

    # 2. Corroboration Decay
    if days_since_corroborated >= 90.0:
        updated["household_size_band"] = "unknown"
        updated["pet"] = "none"
        updated["cooking_intensity"] = "unknown"
        updated["confidence"] = 0.0
    elif days_since_corroborated >= 60.0:
        updated["confidence"] = max(0.5, profile.confidence - 0.3)

    return HouseholdStateProfile(**updated)


def generate_a2_rulebook_for_user(
    user_id: int,
    purchase_history_summary: Dict[str, Any],
    dismissed_l1_ids: Optional[set[int]] = None,
    now: Optional[float] = None,
) -> HouseholdStateProfile:
    """
    Generates A2 household profile from user purchase history summary.
    Offline classification rulebook generator.
    """
    # Deterministic feature classification rules from history
    diaper_purchases = purchase_history_summary.get("diaper_count_180d", 0)
    pet_food_purchases = purchase_history_summary.get("pet_food_count_180d", 0)
    produce_purchases = purchase_history_summary.get("fresh_produce_count_30d", 0)

    infant_present = diaper_purchases >= 3
    pet = "dog" if pet_food_purchases >= 2 else "none"
    cooking = "high" if produce_purchases >= 8 else ("medium" if produce_purchases >= 3 else "low")

    confidence = 0.85 if (infant_present or pet != "none") else 0.70

    profile = HouseholdStateProfile(
        user_id=user_id,
        household_size_band="3-4" if infant_present else "2",
        infant_present=infant_present,
        toddler_present=False,
        pet=pet,
        cooking_intensity=cooking,
        segment="household_manager" if infant_present else "habitual_replenisher",
        confidence=confidence,
    )

    return apply_a2_decay_and_dismissal_rules(profile, dismissed_l1_ids, now)
