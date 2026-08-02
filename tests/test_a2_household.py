"""
tests/test_a2_household.py — Unit tests for A2 Household State Profile, Decay & Zeroing.
§5.6.2 & EC-P2-01: 60d decay / 90d revert, 365d dismissal zeroing for Pet/Baby.
"""

import pytest
import time
from discovery.offline.a2_rulebook_job import (
    HouseholdStateProfile,
    apply_a2_decay_and_dismissal_rules,
    generate_a2_rulebook_for_user,
)


def test_a2_profile_generation():
    history = {
        "diaper_count_180d": 4,
        "pet_food_count_180d": 3,
        "fresh_produce_count_30d": 10,
    }
    profile = generate_a2_rulebook_for_user(user_id=101, purchase_history_summary=history)

    assert profile.user_id == 101
    assert profile.infant_present is True
    assert profile.pet == "dog"
    assert profile.cooking_intensity == "high"
    assert profile.confidence >= 0.85
    assert len(profile.state_id) == 12


def test_a2_corroboration_decay_and_revert():
    now = time.time()
    # Profile last corroborated 70 days ago (between 60d and 90d)
    profile_70d = HouseholdStateProfile(
        user_id=102,
        infant_present=True,
        pet="dog",
        confidence=0.85,
        last_corroborated_at=now - (70 * 86400),
    )
    decayed = apply_a2_decay_and_dismissal_rules(profile_70d, now=now)
    assert decayed.confidence == 0.55  # Decayed by 0.3

    # Profile last corroborated 95 days ago (> 90d revert)
    profile_95d = HouseholdStateProfile(
        user_id=103,
        infant_present=True,
        pet="dog",
        confidence=0.85,
        last_corroborated_at=now - (95 * 86400),
    )
    reverted = apply_a2_decay_and_dismissal_rules(profile_95d, now=now)
    assert reverted.pet == "none"
    assert reverted.cooking_intensity == "unknown"
    assert reverted.confidence == 0.0


def test_a2_dismissal_field_zeroing():
    now = time.time()
    profile = HouseholdStateProfile(
        user_id=104,
        infant_present=True,
        toddler_present=True,
        pet="dog",
        confidence=0.90,
        last_corroborated_at=now,
    )

    # User dismisses Baby Care (L1=20) and Pet Care (L1=25) with "not_interested"
    zeroed = apply_a2_decay_and_dismissal_rules(profile, dismissed_l1_ids={20, 25}, now=now)

    assert zeroed.infant_present is False
    assert zeroed.toddler_present is False
    assert zeroed.pet == "none"
