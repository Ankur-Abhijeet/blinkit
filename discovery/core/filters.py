"""
discovery.core.filters — Binary eligibility filters F1–F14.
Principle 3: Pure predicates, short-circuit execution, complete drop-reason logging.
"""

from typing import List, Set, Tuple, Optional
from discovery.core.types import CartContext, Candidate, DropReason

# F7 Hard-coded Exclusion List (Non-negotiable compliance boundaries)
# L1 IDs: Paan Corner (8881), Sexual Wellness (8882), Health & Pharma (8883), Alcohol (8884), E-Gift Cards (8885), Print Store (8886)
EXCLUDED_L1_IDS: Set[int] = {8881, 8882, 8883, 8884, 8885, 8886}


def evaluate_f1_new_category_gate(
    candidate: Candidate, user_purchased_l1_ids: Set[int]
) -> Optional[DropReason]:
    """F1: Zero purchases in candidate's L1 category in trailing 365 days."""
    if candidate.l1_id in user_purchased_l1_ids:
        return DropReason(
            sku_id=candidate.sku_id,
            filter_id="F1",
            reason=f"User already purchased in L1 category {candidate.l1_id} in 365d",
        )
    return None


def evaluate_f2_inventory_gate(candidate: Candidate) -> Optional[DropReason]:
    """F2: Real-time inventory available_qty >= 3."""
    if candidate.available_qty < 3:
        return DropReason(
            sku_id=candidate.sku_id,
            filter_id="F2",
            reason=f"Insufficient inventory buffer ({candidate.available_qty} < 3)",
        )
    return None


def evaluate_f3_price_ceiling_gate(
    candidate: Candidate, cart_subtotal_paise: int
) -> Optional[DropReason]:
    """F3: price <= min(₹149, 0.15 * cart_subtotal_paise). Subtotal is post-discount."""
    ceiling_paise = min(14900, int(0.15 * cart_subtotal_paise))
    if candidate.price_paise > ceiling_paise:
        return DropReason(
            sku_id=candidate.sku_id,
            filter_id="F3",
            reason=f"Price ₹{candidate.price_paise/100:.2f} exceeds ceiling ₹{ceiling_paise/100:.2f}",
        )
    return None


def evaluate_f4_basket_conflict_gate(
    candidate: Candidate, ctx: CartContext
) -> Optional[DropReason]:
    """F4: Not in cart, not same L2, not same variant/name as cart item."""
    if candidate.sku_id in ctx.cart_sku_ids:
        return DropReason(
            sku_id=candidate.sku_id,
            filter_id="F4",
            reason="SKU already in cart",
        )
    if candidate.l2_id in ctx.cart_l2_ids:
        return DropReason(
            sku_id=candidate.sku_id,
            filter_id="F4",
            reason=f"Cart already contains item in same L2 category {candidate.l2_id}",
        )
    cand_name_norm = candidate.name.strip().lower()
    for item in ctx.cart_items:
        if cand_name_norm == item.name.strip().lower():
            return DropReason(
                sku_id=candidate.sku_id,
                filter_id="F4",
                reason=f"Cart contains matching item name '{item.name}'",
            )
    return None


def evaluate_f5_recency_suppression_gate(
    candidate: Candidate, suppressed_l1_ids: Set[int]
) -> Optional[DropReason]:
    """F5: Suppression Ladder check."""
    if candidate.l1_id in suppressed_l1_ids:
        return DropReason(
            sku_id=candidate.sku_id,
            filter_id="F5",
            reason=f"L1 category {candidate.l1_id} is under recency/dismissal suppression",
        )
    return None


def evaluate_f6_fatigue_gate(
    user_slot_a_impressions_7d: int
) -> Optional[DropReason]:
    """F6: Max 3 Slot A impressions per user per 7 days."""
    if user_slot_a_impressions_7d >= 3:
        return DropReason(
            sku_id=0,
            filter_id="F6",
            reason=f"User 7d fatigue limit reached ({user_slot_a_impressions_7d} >= 3)",
        )
    return None


def evaluate_f7_compliance_gate(candidate: Candidate) -> Optional[DropReason]:
    """F7: Hard-exclude Paan Corner, Sexual Wellness, Health & Pharma, alcohol, E-Gift Cards, Print Store."""
    if candidate.is_excluded_l1 or candidate.l1_id in EXCLUDED_L1_IDS:
        return DropReason(
            sku_id=candidate.sku_id,
            filter_id="F7",
            reason=f"Category {candidate.l1_id} is strictly excluded under F7 COMPLIANCE_GATE",
        )
    return None


def evaluate_f8_cold_cart_gate(ctx: CartContext) -> Optional[DropReason]:
    """F8: cart_subtotal >= ₹149 AND item_count >= 1."""
    if ctx.cart_subtotal_paise < 14900 or ctx.item_count < 1:
        return DropReason(
            sku_id=0,
            filter_id="F8",
            reason=f"Cart subtotal ₹{ctx.cart_subtotal_paise/100:.2f} or items {ctx.item_count} below cold-cart threshold",
        )
    return None


def evaluate_f9_logistics_gate(candidate: Candidate) -> Optional[DropReason]:
    """F9: Volume and weight within rider bag limits (≤ 5kg, ≤ 5L)."""
    if candidate.weight_g > 5000 or candidate.volume_ml > 5000:
        return DropReason(
            sku_id=candidate.sku_id,
            filter_id="F9",
            reason=f"Candidate weight {candidate.weight_g}g or volume {candidate.volume_ml}ml exceeds rider limit",
        )
    return None


def evaluate_f10_margin_gate(candidate: Candidate) -> Optional[DropReason]:
    """F10: Contribution margin >= 15%."""
    if candidate.margin_pct < 0.15:
        return DropReason(
            sku_id=candidate.sku_id,
            filter_id="F10",
            reason=f"Contribution margin {candidate.margin_pct*100:.1f}% below 15% threshold",
        )
    return None


def evaluate_f11_quality_gate(candidate: Candidate) -> Optional[DropReason]:
    """
    F11: Store velocity >= 20 units/30d (or dark store age < 45d exemption)
    AND complaint_rate <= 5%.
    """
    is_new_store = candidate.store_age_days < 45
    velocity_pass = candidate.velocity_30d >= 20 or is_new_store
    if not velocity_pass:
        return DropReason(
            sku_id=candidate.sku_id,
            filter_id="F11",
            reason=f"Velocity {candidate.velocity_30d} below 20 units/30d for mature store ({candidate.store_age_days}d old)",
        )
    if candidate.complaint_rate > 0.05:
        return DropReason(
            sku_id=candidate.sku_id,
            filter_id="F11",
            reason=f"Complaint rate {candidate.complaint_rate*100:.1f}% exceeds 5.0% threshold",
        )
    return None


def evaluate_f12_latency_gate(elapsed_ms: float) -> Optional[DropReason]:
    """F12: Budget cap at 40ms."""
    if elapsed_ms > 40.0:
        return DropReason(
            sku_id=0,
            filter_id="F12",
            reason=f"Ranker runtime {elapsed_ms:.1f}ms exceeded 40ms budget cap",
        )
    return None


def evaluate_f13_semantic_safety_gate(
    candidate: Candidate, blocked_safety_skus: Set[int]
) -> Optional[DropReason]:
    """F13: Near-line semantic safety check (fails closed)."""
    if candidate.sku_id in blocked_safety_skus:
        return DropReason(
            sku_id=candidate.sku_id,
            filter_id="F13",
            reason="Blocked by F13 SEMANTIC_SAFETY_GATE context evaluation",
        )
    return None


def evaluate_f14_tenure_gate(ctx: CartContext) -> Optional[DropReason]:
    """F14: completed_orders >= 3 AND tenure_days >= 14."""
    if ctx.completed_orders < 3 or ctx.tenure_days < 14:
        return DropReason(
            sku_id=0,
            filter_id="F14",
            reason=f"User tenure ({ctx.tenure_days}d, {ctx.completed_orders} orders) below F14 gate (14d, 3 orders)",
        )
    return None


def filter_candidates(
    ctx: CartContext,
    candidates: List[Candidate],
    user_purchased_l1_ids: Set[int],
    suppressed_l1_ids: Set[int],
    user_slot_a_impressions_7d: int = 0,
    blocked_safety_skus: Optional[Set[int]] = None,
    elapsed_ms: float = 0.0,
) -> Tuple[List[Candidate], List[DropReason]]:
    """
    Applies short-circuit evaluation of hard filters F1–F14 in order.
    Returns (eligible_candidates, list_of_drop_reasons).
    """
    if blocked_safety_skus is None:
        blocked_safety_skus = set()

    # Context-level gates evaluated first
    cold_cart_drop = evaluate_f8_cold_cart_gate(ctx)
    if cold_cart_drop:
        return [], [cold_cart_drop]

    fatigue_drop = evaluate_f6_fatigue_gate(user_slot_a_impressions_7d)
    if fatigue_drop:
        return [], [fatigue_drop]

    tenure_drop = evaluate_f14_tenure_gate(ctx)
    if tenure_drop:
        return [], [tenure_drop]

    latency_drop = evaluate_f12_latency_gate(elapsed_ms)
    if latency_drop:
        return [], [latency_drop]

    eligible = []
    drop_reasons = []

    for cand in candidates:
        # F7 Compliance Gate (Checked first per candidate for maximum safety)
        drop = evaluate_f7_compliance_gate(cand)
        if not drop:
            drop = evaluate_f1_new_category_gate(cand, user_purchased_l1_ids)
        if not drop:
            drop = evaluate_f2_inventory_gate(cand)
        if not drop:
            drop = evaluate_f3_price_ceiling_gate(cand, ctx.cart_subtotal_paise)
        if not drop:
            drop = evaluate_f4_basket_conflict_gate(cand, ctx)
        if not drop:
            drop = evaluate_f5_recency_suppression_gate(cand, suppressed_l1_ids)
        if not drop:
            drop = evaluate_f9_logistics_gate(cand)
        if not drop:
            drop = evaluate_f10_margin_gate(cand)
        if not drop:
            drop = evaluate_f11_quality_gate(cand)
        if not drop:
            drop = evaluate_f13_semantic_safety_gate(cand, blocked_safety_skus)

        if drop:
            drop_reasons.append(drop)
        else:
            eligible.append(cand)

    return eligible, drop_reasons
