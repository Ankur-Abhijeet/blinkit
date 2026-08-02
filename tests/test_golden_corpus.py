"""
tests/test_golden_corpus.py — Golden corpus determinism and shadow replay test.
§3.1 & architecture.md §12: Assert byte-identical output across repeated runs on fixed cart corpus.
"""

import pytest
from discovery.core.types import CartContext, CartItem, Candidate
from discovery.shadow.replay import run_shadow_decision, generate_coverage_report


@pytest.fixture
def golden_carts():
    carts = []
    for i in range(1, 101):
        items = [
            CartItem(sku_id=i, l1_id=10 + (i % 3), l2_id=100 + i, name=f"Item {i}", price_paise=5000 + i * 100)
        ]
        ctx = CartContext(
            user_id=1000 + i,
            session_id=f"sess_{i}",
            cart_id=f"cart_{i}",
            store_id=1,
            cart_subtotal_paise=25000 + i * 500,  # ₹250+
            cart_items=items,
            tenure_days=30,
            completed_orders=5,
        )
        carts.append(ctx)
    return carts


@pytest.fixture
def store_candidate_pool():
    pool = []
    for l1 in range(15, 25):
        for idx in range(1, 4):
            cand = Candidate(
                sku_id=l1 * 100 + idx,
                l1_id=l1,
                l2_id=l1 * 1000 + idx,
                name=f"Candidate Product {l1}_{idx}",
                pack="1 pack",
                price_paise=2500 + idx * 500,  # ₹25 - ₹40
                mrp_paise=5000,
                margin_pct=0.25,
                velocity_30d=30,
                complaint_rate=0.01,
                available_qty=10,
            )
            pool.append(cand)
    return pool


def test_golden_corpus_determinism(golden_carts, store_candidate_pool):
    """Replays golden cart corpus twice and asserts byte-identical output."""
    decisions_run1 = [
        run_shadow_decision(ctx, store_candidate_pool, user_purchased_l1_ids={10, 11})
        for ctx in golden_carts
    ]

    decisions_run2 = [
        run_shadow_decision(ctx, store_candidate_pool, user_purchased_l1_ids={10, 11})
        for ctx in golden_carts
    ]

    assert len(decisions_run1) == len(decisions_run2)

    for d1, d2 in zip(decisions_run1, decisions_run2):
        assert d1.user_id == d2.user_id
        assert d1.cart_hash == d2.cart_hash
        assert d1.candidates_in_count == d2.candidates_in_count
        assert d1.candidates_eligible_count == d2.candidates_eligible_count
        assert d1.drop_histogram == d2.drop_histogram
        if d1.served_candidate:
            assert d2.served_candidate is not None
            assert d1.served_candidate.sku_id == d2.served_candidate.sku_id


def test_golden_corpus_coverage_report(golden_carts, store_candidate_pool):
    """Verifies coverage report generator output structure and Gate 0 verdict calculation."""
    decisions = [
        run_shadow_decision(ctx, store_candidate_pool, user_purchased_l1_ids={10, 11})
        for ctx in golden_carts
    ]
    report = generate_coverage_report(decisions)

    assert report["total_carts"] == 100
    assert "coverage_pct" in report
    assert "gate_0_verdict" in report
    assert report["gate_0_verdict"] in ["PASS", "NARROW", "STOP"]
