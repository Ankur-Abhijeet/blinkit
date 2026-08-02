"""
discovery.offline.a3_rulebook_job — A3 Ordering & Copy Rulebook Generator.
§5.6.3 solution.md & §13.0 architecture.md: Offline cell rulebook generator with pre-publication validation.
"""

from typing import Dict, Any, List, Set, Optional
from pydantic import BaseModel
from discovery.core.validator import validate_reason_line, get_template_reason_line


class A3CellRulebookEntry(BaseModel):
    state_id: str
    cart_sig: str
    preferred_category_order: List[int]  # Ranked L1 IDs
    reason_code_map: Dict[int, str]      # L1 ID -> reason_code
    copy_bank_map: Dict[int, str]         # L1 ID -> reason_line
    version: str = "v1.0"


def generate_a3_cell_rulebook(
    state_id: str,
    cart_sig: str,
    candidate_l1_ids: List[int],
    affinity_reason_map: Optional[Dict[int, str]] = None,
    raw_copy_lines: Optional[Dict[int, str]] = None,
) -> A3CellRulebookEntry:
    """
    Generates an A3 rulebook entry for a (state_id, cart_sig) cell.
    Applies pre-publication validation on all copy lines.
    """
    if affinity_reason_map is None:
        affinity_reason_map = {}
    if raw_copy_lines is None:
        raw_copy_lines = {}

    # Order candidates by preference: affinity > CG1 > CG5
    preferred_order = sorted(candidate_l1_ids, key=lambda l1: affinity_reason_map.get(l1) is not None, reverse=True)

    reason_codes = {}
    validated_copy_bank = {}

    for l1_id in candidate_l1_ids:
        reason_code = affinity_reason_map.get(l1_id, "COMPLEMENT")
        reason_codes[l1_id] = reason_code

        raw_line = raw_copy_lines.get(l1_id, "")
        is_valid, clean_line = validate_reason_line(raw_line)

        if not is_valid or not clean_line:
            # Pre-publication fallback to validated template
            clean_line = get_template_reason_line(reason_code)

        validated_copy_bank[l1_id] = clean_line

    return A3CellRulebookEntry(
        state_id=state_id,
        cart_sig=cart_sig,
        preferred_category_order=preferred_order,
        reason_code_map=reason_codes,
        copy_bank_map=validated_copy_bank,
    )
