"""
tests/test_monetization.py — Phase 6 Monetization & Sponsored Candidates Test Suite.
§11 architecture.md & §11 implementation-plan.md: Asserts CG6, quality floor filter, bid scoring & CPVT billing.
"""

import pytest
from discovery.core.types import CartContext, CartItem, Candidate
from discovery.core.sponsored import (
    SponsoredCandidate,
    generate_cg6_sponsored_candidates,
    filter_sponsored_quality_floor,
)
from discovery.core.scoring import score_candidates_v1
from discovery.offline.billing_job import CPVTBillingPipeline


def test_cg6_sponsored_candidate_generation():
    ctx = CartContext(
        user_id=1, session_id="s1", cart_id="c1", store_id=1, cart_subtotal_paise=25000,
        cart_items=[CartItem(sku_id=1, l1_id=10, l2_id=101, name="Milk", price_paise=5000)],
    )

    pool = [
        Candidate(
            sku_id=201, l1_id=20, l2_id=201, name="Baby Wipes", pack="80s", price_paise=2000,
            mrp_paise=3000, margin_pct=0.30, velocity_30d=50, complaint_rate=0.01, available_qty=10
        )
    ]

    cg6_list = generate_cg6_sponsored_candidates(ctx, pool, user_purchased_l1_ids={10})
    assert len(cg6_list) == 1
    sp_cand = cg6_list[0]
    assert sp_cand.is_sponsored is True
    assert sp_cand.badge_text == "Sponsored"
    assert sp_cand.bid_paise == 1500


def test_sponsored_quality_floor_filter_rejection():
    """Asserts that low-relevance sponsored items (p_add < 0.05) are blocked regardless of bid."""
    sp_cand = SponsoredCandidate(
        sku_id=999, l1_id=20, l2_id=201, name="Irrelevant Ad Item", pack="1 pc", price_paise=5000,
        mrp_paise=6000, margin_pct=0.30, velocity_30d=10, complaint_rate=0.01, available_qty=10,
        is_sponsored=True, bid_paise=10000  # High ₹100 bid
    )

    # Low relevance p_add = 0.02 (< 0.05 threshold) -> REJECT
    allowed, reason = filter_sponsored_quality_floor(sp_cand, p_add_val=0.02, min_p_add=0.05)
    assert allowed is False
    assert "SPONSORED_QUALITY_FLOOR_REJECT" in reason

    # High relevance p_add = 0.15 (>= 0.05 threshold) -> ALLOW
    allowed_high, reason_high = filter_sponsored_quality_floor(sp_cand, p_add_val=0.15, min_p_add=0.05)
    assert allowed_high is True
    assert reason_high is None


def test_bid_weighted_scoring():
    ctx = CartContext(
        user_id=1, session_id="s1", cart_id="c1", store_id=1, cart_subtotal_paise=25000,
        cart_items=[CartItem(sku_id=1, l1_id=10, l2_id=101, name="Milk", price_paise=5000)],
    )

    organic_cand = Candidate(
        sku_id=101, l1_id=20, l2_id=201, name="Organic Wipes", pack="80s", price_paise=2000, mrp_paise=3000,
        margin_pct=0.20, velocity_30d=50, complaint_rate=0.01, available_qty=10
    )  # margin_paise = 400

    sponsored_cand = SponsoredCandidate(
        sku_id=102, l1_id=20, l2_id=201, name="Sponsored Wipes", pack="80s", price_paise=2000, mrp_paise=3000,
        margin_pct=0.20, velocity_30d=50, complaint_rate=0.01, available_qty=10,
        is_sponsored=True, bid_paise=1000  # bid_paise = 1000, total_value = 1400
    )

    # Both have same p_add and p_repeat
    p_add_map = {101: 0.10, 102: 0.10}
    p_repeat_map = {101: 0.20, 102: 0.20}

    scored = score_candidates_v1(ctx, [organic_cand, sponsored_cand], p_add_map, p_repeat_map)
    assert scored[0][0].sku_id == 102  # Sponsored candidate ranks higher due to total_value (margin + bid)


def test_cpvt_billing_pipeline():
    pipeline = CPVTBillingPipeline()

    record = pipeline.record_verified_trial_add(
        brand_id=50, sku_id=102, user_id=888, cart_id="c888", bid_paise=1500
    )

    assert record.brand_id == 50
    assert record.bid_paise == 1500

    summary = pipeline.compute_brand_invoice_summary(brand_id=50)
    assert summary["total_verified_trials"] == 1
    assert summary["total_revenue_rupees"] == 15.0  # ₹15.00
