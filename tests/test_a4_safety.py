"""
tests/test_a4_safety.py — A4 Contextual Safety Gate (F13) Red-Team Harm Suite.
§5.6.4 solution.md & §4.5 eval.md: Asserts 100% block recall on sensitive harm contexts.
"""

import pytest
from discovery.core.types import CartContext, CartItem, Candidate
from discovery.offline.a4_rules_job import (
    evaluate_a4_safety_rules,
    PREGNANCY_TEST_L2,
    PAIN_RELIEF_L2,
    ORS_L2,
    DIABETES_MED_L2,
    BABY_CARE_L1,
    CELEBRATORY_L1,
    CONFECTIONERY_L1,
)


def test_a4_pregnancy_distress_harm_context():
    """Context: Pregnancy test + Pain relief in cart. MUST block Baby Care & Celebratory."""
    ctx = CartContext(
        user_id=777,
        session_id="s777",
        cart_id="c777",
        store_id=1,
        cart_subtotal_paise=30000,
        cart_items=[
            CartItem(sku_id=10, l1_id=88, l2_id=PREGNANCY_TEST_L2, name="Pregnancy Test", price_paise=15000),
            CartItem(sku_id=11, l1_id=88, l2_id=PAIN_RELIEF_L2, name="Pain Relief Tablet", price_paise=5000),
        ],
    )

    baby_candidate = Candidate(
        sku_id=2001, l1_id=BABY_CARE_L1, l2_id=2001, name="Baby Lotion", pack="100ml",
        price_paise=2500, mrp_paise=3000, margin_pct=0.3, velocity_30d=50, complaint_rate=0.01, available_qty=10
    )

    allowed, reason = evaluate_a4_safety_rules(ctx, baby_candidate)
    assert allowed is False
    assert reason == "PREGNANCY_DISTRESS_BLOCK"


def test_a4_medical_urgency_harm_context():
    """Context: ORS late night in cart. MUST block non-essential celebratory candidates."""
    ctx = CartContext(
        user_id=778,
        session_id="s778",
        cart_id="c778",
        store_id=1,
        cart_subtotal_paise=20000,
        cart_items=[CartItem(sku_id=12, l1_id=88, l2_id=ORS_L2, name="ORS Liquid", price_paise=4000)],
    )

    celeb_candidate = Candidate(
        sku_id=2901, l1_id=CELEBRATORY_L1, l2_id=2901, name="Party Popper", pack="1 pc",
        price_paise=2000, mrp_paise=3000, margin_pct=0.3, velocity_30d=50, complaint_rate=0.01, available_qty=10
    )

    allowed, reason = evaluate_a4_safety_rules(ctx, celeb_candidate)
    assert allowed is False
    assert reason == "MEDICAL_URGENCY_BLOCK"


def test_a4_diabetes_confectionery_exclusion():
    """Context: Diabetes medication in cart. MUST block confectionery candidates."""
    ctx = CartContext(
        user_id=779,
        session_id="s779",
        cart_id="c779",
        store_id=1,
        cart_subtotal_paise=40000,
        cart_items=[CartItem(sku_id=13, l1_id=88, l2_id=DIABETES_MED_L2, name="Diabetes Care Tablet", price_paise=12000)],
    )

    candy_candidate = Candidate(
        sku_id=1801, l1_id=CONFECTIONERY_L1, l2_id=1801, name="Chocolate Bar", pack="50g",
        price_paise=1500, mrp_paise=2000, margin_pct=0.3, velocity_30d=50, complaint_rate=0.01, available_qty=10
    )

    allowed, reason = evaluate_a4_safety_rules(ctx, candy_candidate)
    assert allowed is False
    assert reason == "DIABETES_CONFECTIONERY_BLOCK"


def test_a4_benign_control_allowed():
    """Context: Ordinary grocery cart (Milk + Bread). MUST allow valid candidates."""
    ctx = CartContext(
        user_id=780,
        session_id="s780",
        cart_id="c780",
        store_id=1,
        cart_subtotal_paise=25000,
        cart_items=[CartItem(sku_id=1, l1_id=10, l2_id=101, name="Milk 1L", price_paise=6000)],
    )

    cand_valid = Candidate(
        sku_id=2001, l1_id=BABY_CARE_L1, l2_id=2001, name="Baby Wipes", pack="80s",
        price_paise=2500, mrp_paise=3000, margin_pct=0.3, velocity_30d=50, complaint_rate=0.01, available_qty=10
    )

    allowed, reason = evaluate_a4_safety_rules(ctx, cand_valid)
    assert allowed is True
    assert reason is None
