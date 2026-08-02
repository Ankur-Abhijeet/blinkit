"""
discovery.offline.features_job — Feature Engineering Pipeline for Learned Ranker.
§13.4 architecture.md & §9 implementation-plan.md: Single feature definition for p_add and p_repeat.
"""

from typing import Dict, Any
from discovery.core.types import CartContext, Candidate


def extract_candidate_feature_vector(
    ctx: CartContext, candidate: Candidate, affinity_score: float = 0.5
) -> Dict[str, float]:
    """
    Extracts numerical feature vector for a (CartContext, Candidate) pair.
    Used by both p_add and p_repeat models.
    """
    return {
        "user_tenure_days": float(ctx.tenure_days),
        "user_completed_orders": float(ctx.completed_orders),
        "user_city_tier": float(ctx.city_tier),
        "cart_subtotal_rupees": float(ctx.cart_subtotal_paise) / 100.0,
        "cart_item_count": float(len(ctx.cart_items)),
        "cand_price_rupees": float(candidate.price_paise) / 100.0,
        "cand_margin_pct": float(candidate.margin_pct),
        "cand_velocity_30d": float(candidate.velocity_30d),
        "cand_complaint_rate": float(candidate.complaint_rate),
        "affinity_score": float(affinity_score),
    }
