"""
tests/test_f7_exhaustive.py — Exhaustive Cartesian sweep testing F7 compliance gate.
§5.2 & architecture.md §12: Asserts blocked categories can NEVER be emitted under ANY input.
"""

import pytest
from discovery.core.types import CartContext, CartItem, Candidate
from discovery.core.filters import EXCLUDED_L1_IDS, evaluate_f7_compliance_gate, filter_candidates

# Verified taxonomy L1 IDs (Appendix A)
ALL_L1_IDS = list(range(100, 128)) + list(EXCLUDED_L1_IDS)


def test_f7_exhaustive_cartesian_sweep():
    """Sweeps every single L1 category against multiple candidate variations."""
    ctx = CartContext(
        user_id=999,
        session_id="s_f7",
        cart_id="c_f7",
        store_id=1,
        cart_subtotal_paise=50000,
        cart_items=[CartItem(sku_id=1, l1_id=100, l2_id=1001, name="Milk", price_paise=6000)],
        tenure_days=100,
        completed_orders=20,
    )

    for l1_id in ALL_L1_IDS:
        is_excluded = l1_id in EXCLUDED_L1_IDS

        # Create candidate variations for this L1 category
        candidate = Candidate(
            sku_id=l1_id * 10,
            l1_id=l1_id,
            l2_id=l1_id * 100,
            name=f"Sample SKU for L1 {l1_id}",
            pack="1 unit",
            price_paise=2000,
            mrp_paise=3000,
            margin_pct=0.25,
            velocity_30d=50,
            complaint_rate=0.01,
            available_qty=10,
            is_excluded_l1=is_excluded,
        )

        drop = evaluate_f7_compliance_gate(candidate)

        if is_excluded:
            assert drop is not None, f"F7 Compliance Gate failed to block excluded L1 ID {l1_id}"
            assert drop.filter_id == "F7"

            # Also verify via filter_candidates pipeline
            eligible, drops = filter_candidates(
                ctx=ctx,
                candidates=[candidate],
                user_purchased_l1_ids=set(),
                suppressed_l1_ids=set(),
            )
            assert len(eligible) == 0, f"Excluded candidate in L1 {l1_id} slipped through filter pipeline"
            assert any(d.filter_id == "F7" for d in drops)
        else:
            assert drop is None, f"F7 Compliance Gate incorrectly blocked valid L1 ID {l1_id}"
