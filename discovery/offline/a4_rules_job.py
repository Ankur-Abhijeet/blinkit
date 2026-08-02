"""
discovery.offline.a4_rules_job — A4 Contextual Safety Rule Generator & F13 Evaluator.
§5.6.4 solution.md & §4.5 eval.md: Contextual safety gate rules. Fails CLOSED.
"""

from typing import List, Set, Tuple, Optional
from discovery.core.types import CartContext, Candidate

# L2 IDs for sensitive signals
PREGNANCY_TEST_L2 = 8801
PAIN_RELIEF_L2 = 8802
ORS_L2 = 8803
FEVER_MED_L2 = 8804
SANITARY_PAD_L2 = 8805
DIABETES_MED_L2 = 8806

# L1 IDs for sensitive candidate categories
BABY_CARE_L1 = 20
CELEBRATORY_L1 = 29
CONFECTIONERY_L1 = 18


def evaluate_a4_safety_rules(
    ctx: CartContext, candidate: Candidate
) -> Tuple[bool, Optional[str]]:
    """
    Evaluates A4 contextual safety rules against (cart x candidate) pair.
    Returns (is_allowed, block_reason_code).
    Fails CLOSED (is_allowed = False on safety violation).
    """
    cart_l2_ids = ctx.cart_l2_ids

    # Rule 1: Pregnancy test + pain relief -> BLOCK Baby Care & Celebratory candidates
    if (PREGNANCY_TEST_L2 in cart_l2_ids or PAIN_RELIEF_L2 in cart_l2_ids) and candidate.l1_id in (BABY_CARE_L1, CELEBRATORY_L1):
        return False, "PREGNANCY_DISTRESS_BLOCK"

    # Rule 2: Illness / Medical urgency (ORS / Fever med) -> BLOCK non-essential celebratory items
    if (ORS_L2 in cart_l2_ids or FEVER_MED_L2 in cart_l2_ids) and candidate.l1_id == CELEBRATORY_L1:
        return False, "MEDICAL_URGENCY_BLOCK"

    # Rule 3: Menstrual discomfort (Sanitary pads + analgesics) -> BLOCK celebratory/gifting
    if SANITARY_PAD_L2 in cart_l2_ids and candidate.l1_id == CELEBRATORY_L1:
        return False, "MENSTRUAL_DISCOMFORT_BLOCK"

    # Rule 4: Diabetes medication in cart -> BLOCK confectionery/high-sugar candidates (EC-P2-16)
    if DIABETES_MED_L2 in cart_l2_ids and candidate.l1_id == CONFECTIONERY_L1:
        return False, "DIABETES_CONFECTIONERY_BLOCK"

    return True, None
