"""
tests/test_arbitration.py — Multi-Slot Arbitration & Diversity Test Suite.
§3.5 solution.md & §7 architecture.md: Slot A exclusion, category diversity, margin/budget rules.
"""

import pytest
from discovery.core.types import CartContext, CartItem, Candidate, Decision
from discovery.core.arbitration import arbitrate_slots


def test_slot_a_active_suppresses_slot_b():
    """Asserts that if Slot A serves a candidate, Slot B is suppressed."""
    ctx = CartContext(
        user_id=1, session_id="s1", cart_id="c1", store_id=1, cart_subtotal_paise=20000,
        cart_items=[CartItem(sku_id=1, l1_id=10, l2_id=101, name="Item", price_paise=5000)],
    )

    cand_a = Candidate(
        sku_id=100, l1_id=20, l2_id=201, name="Slot A Cand", pack="1 pc",
        price_paise=2000, mrp_paise=3000, margin_pct=0.25, velocity_30d=50, complaint_rate=0.01, available_qty=10
    )

    decision_a = Decision(
        user_id=1, cart_hash="sig", store_id=1, experiment_arm="B", served_candidate=cand_a
    )

    decision_b = arbitrate_slots(ctx, eligible_candidates=[cand_a], decision_a=decision_a)
    assert decision_b.served_candidate is None
    assert decision_b.reason_code == "SLOT_A_ACTIVE_EXCLUSION"


def test_slot_b_category_diversity_exclusion():
    """Asserts that Slot B candidate cannot belong to cart L1 categories."""
    ctx = CartContext(
        user_id=2, session_id="s2", cart_id="c2", store_id=1, cart_subtotal_paise=20000,
        cart_items=[CartItem(sku_id=1, l1_id=10, l2_id=101, name="Milk", price_paise=5000)],
    )

    decision_a_empty = Decision(
        user_id=2, cart_hash="sig", store_id=1, experiment_arm="B", served_candidate=None
    )

    cand_same_l1 = Candidate(
        sku_id=101, l1_id=10, l2_id=102, name="Curd (Same L1)", pack="200g",
        price_paise=1500, mrp_paise=2000, margin_pct=0.25, velocity_30d=50, complaint_rate=0.01, available_qty=10
    )
    cand_diff_l1 = Candidate(
        sku_id=201, l1_id=25, l2_id=251, name="Dog Treats (Diff L1)", pack="100g",
        price_paise=2000, mrp_paise=3000, margin_pct=0.25, velocity_30d=50, complaint_rate=0.01, available_qty=10
    )

    decision_b = arbitrate_slots(ctx, eligible_candidates=[cand_same_l1, cand_diff_l1], decision_a=decision_a_empty)
    assert decision_b.served_candidate is not None
    assert decision_b.served_candidate.sku_id == 201  # Diff L1 selected
