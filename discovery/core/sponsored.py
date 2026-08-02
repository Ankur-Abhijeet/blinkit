"""
discovery.core.sponsored — CG6 Sponsored Candidate Generator & Quality Floor.
§11 architecture.md & §11 implementation-plan.md: Sponsored candidate generation & relevance floor filter.
"""

from typing import List, Tuple, Optional, Dict
from discovery.core.types import Candidate, CartContext


class SponsoredCandidate(Candidate):
    """Sponsored Brand Candidate with bid and badging metadata."""

    is_sponsored: bool = True
    bid_paise: int = 1000  # Default ₹10 bid per trial
    brand_id: int = 501
    badge_text: str = "Sponsored"


def generate_cg6_sponsored_candidates(
    ctx: CartContext, store_pool: List[Candidate], user_purchased_l1_ids: set[int]
) -> List[SponsoredCandidate]:
    """
    Generates CG6 sponsored candidates for unpurchased L1 categories.
    """
    sponsored = []
    for cand in store_pool:
        if cand.l1_id not in user_purchased_l1_ids and cand.l1_id not in ctx.cart_l1_ids:
            sp_cand = SponsoredCandidate(
                sku_id=cand.sku_id,
                l1_id=cand.l1_id,
                l2_id=cand.l2_id,
                name=cand.name,
                pack=cand.pack,
                price_paise=cand.price_paise,
                mrp_paise=cand.mrp_paise,
                margin_pct=cand.margin_pct,
                velocity_30d=cand.velocity_30d,
                complaint_rate=cand.complaint_rate,
                available_qty=cand.available_qty,
                store_age_days=cand.store_age_days,
                generation_source="CG6",
                is_sponsored=True,
                bid_paise=1500,
                brand_id=cand.l1_id * 10,
                badge_text="Sponsored",
            )
            sponsored.append(sp_cand)
    return sponsored


def filter_sponsored_quality_floor(
    candidate: Candidate, p_add_val: float, min_p_add: float = 0.05
) -> Tuple[bool, Optional[str]]:
    """
    Sponsored Quality Floor Filter (P6-3):
    Sponsored candidates MUST meet minimum organic relevance p_add >= min_p_add (5%).
    Blocks low-relevance ad spam regardless of bid amount.
    """
    if getattr(candidate, "is_sponsored", False):
        if p_add_val < min_p_add:
            return False, f"SPONSORED_QUALITY_FLOOR_REJECT (p_add={p_add_val:.3f} < {min_p_add})"
    return True, None
