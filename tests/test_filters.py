"""
tests/test_filters.py — Unit tests for hard eligibility filters F1–F14.
"""

import pytest
from discovery.core.types import CartContext, CartItem, Candidate
from discovery.core.filters import (
    evaluate_f1_new_category_gate,
    evaluate_f2_inventory_gate,
    evaluate_f3_price_ceiling_gate,
    evaluate_f4_basket_conflict_gate,
    evaluate_f5_recency_suppression_gate,
    evaluate_f6_fatigue_gate,
    evaluate_f7_compliance_gate,
    evaluate_f8_cold_cart_gate,
    evaluate_f9_logistics_gate,
    evaluate_f10_margin_gate,
    evaluate_f11_quality_gate,
    evaluate_f12_latency_gate,
    evaluate_f13_semantic_safety_gate,
    evaluate_f14_tenure_gate,
    filter_candidates,
)


@pytest.fixture
def sample_cart_context():
    return CartContext(
        user_id=1001,
        session_id="sess_123",
        cart_id="cart_456",
        store_id=50,
        cart_subtotal_paise=20000,  # ₹200 post-discount
        cart_items=[
            CartItem(sku_id=1, l1_id=10, l2_id=101, name="Milk 1L", price_paise=6000),
            CartItem(sku_id=2, l1_id=10, l2_id=102, name="Bread 400g", price_paise=4000),
        ],
        tenure_days=30,
        completed_orders=5,
    )


@pytest.fixture
def valid_candidate():
    return Candidate(
        sku_id=501,
        l1_id=20,  # Unpurchased L1
        l2_id=201,
        name="Diaper Rash Cream",
        pack="50 g",
        price_paise=12900,  # ₹129 (<= min(149, 0.15*200) = 149 => ₹14900 paise)
        mrp_paise=15000,
        margin_pct=0.35,  # 35% margin
        velocity_30d=50,
        complaint_rate=0.01,
        available_qty=10,
        volume_ml=100,
        weight_g=100,
        is_excluded_l1=False,
    )


def test_f1_new_category_gate(valid_candidate):
    purchased_l1s = {10, 11}  # L1=20 is unpurchased
    assert evaluate_f1_new_category_gate(valid_candidate, purchased_l1s) is None

    purchased_l1s_with_cand = {10, 20}
    drop = evaluate_f1_new_category_gate(valid_candidate, purchased_l1s_with_cand)
    assert drop is not None
    assert drop.filter_id == "F1"


def test_f2_inventory_gate(valid_candidate):
    cand_in_stock = Candidate(**{**valid_candidate.model_dump(), "available_qty": 3})
    assert evaluate_f2_inventory_gate(cand_in_stock) is None

    cand_low_stock = Candidate(**{**valid_candidate.model_dump(), "available_qty": 2})
    drop = evaluate_f2_inventory_gate(cand_low_stock)
    assert drop is not None
    assert drop.filter_id == "F2"


def test_f3_price_ceiling_gate(valid_candidate, sample_cart_context):
    # subtotal = ₹200 (20000 paise). 15% of 20000 = 3000 paise (₹30). min(14900, 3000) = 3000 paise
    cand_cheap = Candidate(**{**valid_candidate.model_dump(), "price_paise": 2900})
    assert evaluate_f3_price_ceiling_gate(cand_cheap, sample_cart_context.cart_subtotal_paise) is None

    cand_expensive = Candidate(**{**valid_candidate.model_dump(), "price_paise": 3500})
    drop = evaluate_f3_price_ceiling_gate(cand_expensive, sample_cart_context.cart_subtotal_paise)
    assert drop is not None
    assert drop.filter_id == "F3"


def test_f4_basket_conflict_gate(valid_candidate, sample_cart_context):
    assert evaluate_f4_basket_conflict_gate(valid_candidate, sample_cart_context) is None

    # Basket conflict on sku_id
    cand_conflict_sku = Candidate(**{**valid_candidate.model_dump(), "sku_id": 1})
    assert evaluate_f4_basket_conflict_gate(cand_conflict_sku, sample_cart_context).filter_id == "F4"

    # Basket conflict on l2_id
    cand_conflict_l2 = Candidate(**{**valid_candidate.model_dump(), "l2_id": 101})
    assert evaluate_f4_basket_conflict_gate(cand_conflict_l2, sample_cart_context).filter_id == "F4"


def test_f7_compliance_gate(valid_candidate):
    assert evaluate_f7_compliance_gate(valid_candidate) is None

    # Excluded L1
    cand_excluded = Candidate(**{**valid_candidate.model_dump(), "l1_id": 8881})
    drop = evaluate_f7_compliance_gate(cand_excluded)
    assert drop is not None
    assert drop.filter_id == "F7"


def test_f8_cold_cart_gate():
    warm_cart = CartContext(
        user_id=1, session_id="s", cart_id="c", store_id=1,
        cart_subtotal_paise=15000, cart_items=[CartItem(sku_id=1, l1_id=1, l2_id=1, name="a", price_paise=15000)]
    )
    assert evaluate_f8_cold_cart_gate(warm_cart) is None

    cold_cart = CartContext(
        user_id=1, session_id="s", cart_id="c", store_id=1,
        cart_subtotal_paise=4000, cart_items=[CartItem(sku_id=1, l1_id=1, l2_id=1, name="a", price_paise=4000)]
    )
    assert evaluate_f8_cold_cart_gate(cold_cart).filter_id == "F8"


def test_f14_tenure_gate():
    tenured_user = CartContext(
        user_id=1, session_id="s", cart_id="c", store_id=1, cart_subtotal_paise=20000,
        tenure_days=15, completed_orders=3
    )
    assert evaluate_f14_tenure_gate(tenured_user) is None

    new_user = CartContext(
        user_id=1, session_id="s", cart_id="c", store_id=1, cart_subtotal_paise=20000,
        tenure_days=5, completed_orders=1
    )
    drop = evaluate_f14_tenure_gate(new_user)
    assert drop is not None
    assert drop.filter_id == "F14"


def test_filter_candidates_end_to_end(sample_cart_context, valid_candidate):
    # Candidate priced at ₹25 (2500 paise) to pass F3 (ceiling is 15% of ₹200 = ₹30)
    cand_valid = Candidate(**{**valid_candidate.model_dump(), "price_paise": 2500})
    eligible, drops = filter_candidates(
        ctx=sample_cart_context,
        candidates=[cand_valid],
        user_purchased_l1_ids={10},
        suppressed_l1_ids=set(),
    )
    assert len(eligible) == 1
    assert len(drops) == 0
    assert eligible[0].sku_id == cand_valid.sku_id
