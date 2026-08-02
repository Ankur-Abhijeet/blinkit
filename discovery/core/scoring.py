"""
discovery.core.scoring — Baseline and learned scoring engines.
"""

from typing import List, Tuple, Optional, Dict
from discovery.core.types import CartContext, Candidate


def score_candidates_v0(
    candidates: List[Candidate],
    active_occasion_l1_ids: set[int] = None,
    affinity_lift_map: Dict[int, float] = None,
    segment_adoption_map: Dict[int, float] = None,
) -> List[Tuple[Candidate, float]]:
    """
    v0 Rules Baseline Priority Scoring.
    Priority Tuple = (
        is_occasion_active(c),
        affinity_lift(c),
        segment_adoption_rate(c),
        -price_paise(c),
        -sku_id(c) # Deterministic tiebreak
    )
    Returns list of (candidate, score_value) sorted by priority descending.
    """
    if active_occasion_l1_ids is None:
        active_occasion_l1_ids = set()
    if affinity_lift_map is None:
        affinity_lift_map = {}
    if segment_adoption_map is None:
        segment_adoption_map = {}

    scored = []
    for cand in candidates:
        is_occasion = 1.0 if cand.l1_id in active_occasion_l1_ids else 0.0
        affinity_lift = affinity_lift_map.get(cand.l1_id, 1.0)
        segment_rate = segment_adoption_map.get(cand.l1_id, 0.0)

        # Composite score value for logging / ranking
        score_val = (is_occasion * 100.0) + (affinity_lift * 10.0) + segment_rate + (1.0 / (cand.price_paise + 1))

        sort_key = (
            is_occasion,
            affinity_lift,
            segment_rate,
            -cand.price_paise,
            -cand.sku_id,  # Deterministic tiebreak
        )
        scored.append((cand, score_val, sort_key))

    # Sort descending by sort_key
    scored.sort(key=lambda item: item[2], reverse=True)

    return [(cand, score_val) for cand, score_val, _ in scored]


def score_candidates_v1(
    ctx: CartContext,
    candidates: List[Candidate],
    p_add_map: Optional[Dict[int, float]] = None,
    p_repeat_map: Optional[Dict[int, float]] = None,
    ts_map: Optional[Dict[int, float]] = None,
    bid_paise_map: Optional[Dict[int, float]] = None,
) -> List[Tuple[Candidate, float]]:
    """
    Learned Ranker Scoring Engine v1 with Brand Bid Term:
    S(c) = p_add(c) * p_repeat(c) * (margin_paise(c) + bid_paise(c)) * thompson_sample(c)
    """
    if p_add_map is None:
        p_add_map = {}
    if p_repeat_map is None:
        p_repeat_map = {}
    if ts_map is None:
        ts_map = {}
    if bid_paise_map is None:
        bid_paise_map = {}

    scored: List[Tuple[Candidate, float]] = []

    for cand in candidates:
        p_add = p_add_map.get(cand.sku_id, 0.10)
        p_repeat = p_repeat_map.get(cand.sku_id, 0.25)
        margin_paise = cand.price_paise * cand.margin_pct
        bid_paise = getattr(cand, "bid_paise", bid_paise_map.get(cand.sku_id, 0.0))

        total_value_paise = margin_paise + bid_paise
        ts_sample = ts_map.get(cand.l1_id, 0.50)

        # Total expected value score
        score = p_add * p_repeat * total_value_paise * ts_sample
        scored.append((cand, round(score, 4)))

    # Sort descending by score
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
