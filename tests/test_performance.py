"""
tests/test_performance.py — Performance & Sub-Millisecond Benchmark Suite.
Principle 1 & §5 architecture.md: Core logic execution < 1ms, cache read < 5ms.
"""

import pytest
import time
from discovery.core.types import CartContext, CartItem, Candidate
from discovery.worker.nearline_worker import NearlineWorkerEngine
from discovery.config.flags import FeatureFlags


def test_core_decision_processing_latency():
    """Asserts that nearline worker processes cart events in under 2ms per cart."""
    flags = FeatureFlags({"discovery.enabled": True, "discovery.traffic_pct": 100.0, "discovery.arm_split": {"A": 0, "B": 100, "C": 0}})
    worker = NearlineWorkerEngine(flags=flags)

    ctx = CartContext(
        user_id=1, session_id="s1", cart_id="c1", store_id=1, cart_subtotal_paise=30000,
        cart_items=[CartItem(sku_id=1, l1_id=10, l2_id=101, name="Milk", price_paise=5000)],
        tenure_days=30, completed_orders=5
    )

    candidate_pool = [
        Candidate(
            sku_id=100 + i, l1_id=20 + (i % 5), l2_id=200 + i, name=f"Candidate {i}", pack="100g",
            price_paise=2000, mrp_paise=3000, margin_pct=0.25, velocity_30d=50, complaint_rate=0.01, available_qty=10
        )
        for i in range(50)
    ]

    start_time = time.perf_counter()
    iterations = 100
    for _ in range(iterations):
        worker.process_cart_event(ctx, candidate_pool, user_purchased_l1_ids={10})
    total_time_ms = (time.perf_counter() - start_time) * 1000.0
    avg_latency_ms = total_time_ms / iterations

    assert avg_latency_ms < 2.0, f"Core decision latency too high: {avg_latency_ms:.3f}ms >= 2ms"
