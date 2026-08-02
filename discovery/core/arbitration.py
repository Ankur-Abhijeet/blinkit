"""
discovery.core.arbitration — Multi-Slot Arbitrator & Optimization Engine.
§3.5 solution.md & §7 architecture.md: Slot A exclusion, category diversity, and margin/budget optimization.
"""

from typing import List, Optional, Set
from discovery.core.types import CartContext, Candidate, Decision


def arbitrate_slots(
    ctx: CartContext,
    eligible_candidates: List[Candidate],
    decision_a: Decision,
    max_budget_paise: int = 100000,
) -> Decision:
    """
    Arbitrates multi-slot candidate selection for Slot B (Inline Strip / Cross-sell drawer):
    1. Slot A Exclusion: If Slot A served a candidate, Slot B is suppressed (returns empty decision).
    2. Category Diversity: Slot B candidate cannot belong to cart L1s or Slot A L1.
    3. Margin & Budget: Margin pct >= 15% and price fits within promotional budget.
    """
    # 1. Slot A Exclusion Rule (§3.5)
    if decision_a.served_candidate is not None:
        return Decision(
            user_id=ctx.user_id,
            cart_hash=ctx.cart_sig,
            store_id=ctx.store_id,
            experiment_arm=decision_a.experiment_arm,
            served_candidate=None,
            reason_code="SLOT_A_ACTIVE_EXCLUSION",
            reason_line="",
            candidates_in_count=len(eligible_candidates),
            candidates_eligible_count=0,
        )

    # 2. Category Diversity Exclusions
    excluded_l1_ids: Set[int] = set(ctx.cart_l1_ids)

    slot_b_candidates = []
    for cand in eligible_candidates:
        if cand.l1_id in excluded_l1_ids:
            continue
        # 3. Margin & Budget Optimization
        if cand.margin_pct < 0.15:
            continue
        if cand.price_paise > max_budget_paise:
            continue
        slot_b_candidates.append(cand)

    served_b = None
    reason_code = "NONE"
    reason_line = ""

    if slot_b_candidates:
        # Select top Slot B candidate
        served_b = slot_b_candidates[0]
        reason_code = "DRAWER_COMPLEMENT"
        reason_line = f"Frequently bought with your cart: {served_b.name}"

    return Decision(
        user_id=ctx.user_id,
        cart_hash=ctx.cart_sig,
        store_id=ctx.store_id,
        experiment_arm=decision_a.experiment_arm,
        served_candidate=served_b,
        reason_code=reason_code,
        reason_line=reason_line,
        candidates_in_count=len(eligible_candidates),
        candidates_eligible_count=len(slot_b_candidates),
    )
