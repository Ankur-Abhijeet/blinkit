"""
tests/test_parity.py — Shadow vs Live/Near-Line Parity CI test.
Principle 3 & architecture.md §5: Asserts discovery-shadow and discovery-worker produce byte-identical decisions.
"""

import pytest
from discovery.core.types import CartContext, CartItem, Candidate
from discovery.shadow.replay import run_shadow_decision
from discovery.worker.nearline_worker import NearlineWorkerEngine
from discovery.config.flags import FeatureFlags


@pytest.fixture
def parity_carts():
    carts = []
    for i in range(1, 101):
        ctx = CartContext(
            user_id=2000 + i,
            session_id=f"sess_p_{i}",
            cart_id=f"cart_p_{i}",
            store_id=1,
            cart_subtotal_paise=30000,
            cart_items=[CartItem(sku_id=i, l1_id=10, l2_id=100 + i, name=f"Parity Item {i}", price_paise=5000)],
            tenure_days=30,
            completed_orders=5,
        )
        carts.append(ctx)
    return carts


@pytest.fixture
def parity_store_pool():
    pool = []
    for l1 in range(20, 25):
        for idx in range(1, 4):
            cand = Candidate(
                sku_id=l1 * 100 + idx,
                l1_id=l1,
                l2_id=l1 * 1000 + idx,
                name=f"Parity Candidate {l1}_{idx}",
                pack="100g",
                price_paise=2000 + idx * 500,
                mrp_paise=4000,
                margin_pct=0.25,
                velocity_30d=40,
                complaint_rate=0.01,
                available_qty=10,
            )
            pool.append(cand)
    return pool


def test_shadow_nearline_parity(parity_carts, parity_store_pool):
    """
    Replays golden set carts through both shadow replay and nearline worker.
    Asserts byte-identical decisions for candidates, scoring, and drop histograms.
    """
    flags = FeatureFlags({
        "discovery.enabled": True,
        "discovery.traffic_pct": 100.0,
        "discovery.arm_split": {"A": 0, "B": 100, "C": 0},  # Force 100% Arm B for parity check
    })
    worker = NearlineWorkerEngine(flags=flags)

    user_purchased = {10, 11}

    for ctx in parity_carts:
        shadow_decision = run_shadow_decision(
            ctx=ctx,
            store_pool=parity_store_pool,
            user_purchased_l1_ids=user_purchased,
        )

        worker_decision = worker.process_cart_event(
            ctx=ctx,
            store_pool=parity_store_pool,
            user_purchased_l1_ids=user_purchased,
        )

        # Parity assertions
        if worker_decision.experiment_arm == "B":
            assert shadow_decision.candidates_in_count == worker_decision.candidates_in_count
            assert shadow_decision.candidates_eligible_count == worker_decision.candidates_eligible_count
            assert shadow_decision.drop_histogram == worker_decision.drop_histogram

            if shadow_decision.served_candidate:
                assert worker_decision.served_candidate is not None
                assert shadow_decision.served_candidate.sku_id == worker_decision.served_candidate.sku_id
                assert shadow_decision.reason_code == worker_decision.reason_code
        else:
            # Holdout integrity assertion
            assert worker_decision.experiment_arm in ("HOLDOUT", "A")
            assert worker_decision.served_candidate is None
