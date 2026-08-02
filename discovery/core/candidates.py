"""
discovery.core.candidates — Pure Candidate Generation (CG1 & CG5).
Principle 3: Pure logic, zero I/O.
"""

from typing import List, Set
from discovery.core.types import CartContext, Candidate


def generate_cg1_candidates(
    pool: List[Candidate],
    user_purchased_l1_ids: Set[int],
) -> List[Candidate]:
    """
    CG1: New-category candidate pool.
    Filters the store candidate pool to SKUs in L1 categories the user has NEVER purchased in 365d.
    """
    cg1_candidates = []
    for candidate in pool:
        if candidate.l1_id not in user_purchased_l1_ids:
            # Tag with CG1 generation source
            cg1_cand = Candidate(**{**candidate.model_dump(), "generation_source": "CG1"})
            cg1_candidates.append(cg1_cand)
    return cg1_candidates


def generate_cg5_candidates(
    pool: List[Candidate],
    user_purchased_l1_ids: Set[int],
) -> List[Candidate]:
    """
    CG5: Smallest-pack pool.
    Per unpurchased L1 category, select the cheapest / smallest-pack available SKUs above quality floor.
    """
    cg1_candidates = generate_cg1_candidates(pool, user_purchased_l1_ids)

    # Group by L1 category and sort by price ascending
    by_l1 = {}
    for cand in cg1_candidates:
        by_l1.setdefault(cand.l1_id, []).append(cand)

    cg5_selected = []
    for l1_id, cands in by_l1.items():
        # Sort by price_paise ascending (cheapest / smallest pack)
        sorted_cands = sorted(cands, key=lambda c: c.price_paise)
        # Select top 3 cheapest per unpurchased L1
        for cand in sorted_cands[:3]:
            cg5_cand = Candidate(**{**cand.model_dump(), "generation_source": "CG5"})
            cg5_selected.append(cg5_cand)

    return cg5_selected


def generate_candidates(
    ctx: CartContext,
    store_pool: List[Candidate],
    user_purchased_l1_ids: Set[int],
) -> List[Candidate]:
    """
    Combines candidate generation pools (CG1 base pool + CG5 smallest pack pool).
    Returns deduplicated list of candidates.
    """
    cg1 = generate_cg1_candidates(store_pool, user_purchased_l1_ids)
    cg5 = generate_cg5_candidates(store_pool, user_purchased_l1_ids)

    # Deduplicate by sku_id preserving order
    seen_skus = set()
    combined = []
    for cand in cg1 + cg5:
        if cand.sku_id not in seen_skus:
            seen_skus.add(cand.sku_id)
            combined.append(cand)

    return combined
