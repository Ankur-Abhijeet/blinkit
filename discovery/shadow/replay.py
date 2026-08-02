"""
discovery.shadow.replay — Shadow batch replay engine and Appendix C coverage report generator.
Principle 3: Pure core execution, zero state modification.
"""

from typing import List, Dict, Set, Tuple
from discovery.core.types import CartContext, Candidate, Decision
from discovery.core.candidates import generate_candidates
from discovery.core.filters import filter_candidates
from discovery.core.scoring import score_candidates_v0


def run_shadow_decision(
    ctx: CartContext,
    store_pool: List[Candidate],
    user_purchased_l1_ids: Set[int],
    suppressed_l1_ids: Set[int] = None,
    user_slot_a_impressions_7d: int = 0,
) -> Decision:
    """
    Executes a single shadow decision over a cart context using discovery-core.
    Produces full drop-reason logging without writing to cache or serving users.
    """
    if suppressed_l1_ids is None:
        suppressed_l1_ids = set()
    # 1. Candidate Generation
    candidates_in = generate_candidates(ctx, store_pool, user_purchased_l1_ids)

    # 2. Hard Filtering (F1–F14)
    eligible_candidates, drop_reasons = filter_candidates(
        ctx=ctx,
        candidates=candidates_in,
        user_purchased_l1_ids=user_purchased_l1_ids,
        suppressed_l1_ids=suppressed_l1_ids,
        user_slot_a_impressions_7d=user_slot_a_impressions_7d,
    )

    # Build drop reason histogram
    histogram: Dict[str, int] = {}
    for dr in drop_reasons:
        histogram[dr.filter_id] = histogram.get(dr.filter_id, 0) + 1

    served_cand = None
    reason_code = "GENERIC"
    reason_line = ""

    if eligible_candidates:
        # 3. Scoring (v0 Rules Baseline)
        scored = score_candidates_v0(eligible_candidates)
        top_cand, _ = scored[0]
        served_cand = top_cand
        reason_code = "COMPLEMENT"
        reason_line = f"New for you in {top_cand.name}"

    decision = Decision(
        user_id=ctx.user_id,
        cart_hash=ctx.cart_sig,
        store_id=ctx.store_id,
        experiment_arm="B",
        served_candidate=served_cand,
        reason_code=reason_code,
        reason_line=reason_line,
        candidates_in_count=len(candidates_in),
        candidates_eligible_count=len(eligible_candidates),
        drop_reasons=drop_reasons,
        drop_histogram=histogram,
    )

    return decision


def generate_coverage_report(
    decisions: List[Decision],
) -> Dict[str, any]:
    """
    Generates Appendix C Coverage Report & Drop Histogram from batch replay decisions.
    """
    total_carts = len(decisions)
    if total_carts == 0:
        return {
            "total_carts": 0,
            "eligible_carts": 0,
            "coverage_pct": 0.0,
            "gate_0_verdict": "FAIL",
            "drop_histogram": {},
        }

    eligible_carts = sum(1 for d in decisions if d.candidates_eligible_count > 0)
    coverage_pct = (eligible_carts / total_carts) * 100.0

    aggregated_histogram: Dict[str, int] = {}
    for d in decisions:
        for filter_id, count in d.drop_histogram.items():
            aggregated_histogram[filter_id] = (
                aggregated_histogram.get(filter_id, 0) + count
            )

    verdict = "PASS" if coverage_pct >= 60.0 else ("NARROW" if coverage_pct >= 40.0 else "STOP")

    return {
        "total_carts": total_carts,
        "eligible_carts": eligible_carts,
        "coverage_pct": round(coverage_pct, 2),
        "gate_0_verdict": verdict,
        "drop_histogram": aggregated_histogram,
    }
