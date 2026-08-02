"""
discovery.core.validator — Deterministic LLM output validator & deny-list checker.
Principle 3 & §5.6.5: Every user-visible string crosses the validator.
"""

import json
import re
from typing import Dict, Any, List, Set, Tuple, Optional

ALLOWED_REASON_CODES: Set[str] = {
    "LIFE_STAGE",
    "COMPLEMENT",
    "OCCASION",
    "ROUTINE_ADJACENT",
    "SEASONAL",
    "GENERIC",
}

# Deny-list patterns: no price/discount claims, no returns/expiry claims, no urgency, no superlatives, no health claims
DENY_LIST_PATTERNS: List[re.Pattern] = [
    re.compile(r"\b(price|cheap|discount|mrp|off|free|deal|save|₹|\d+%\s*off)\b", re.IGNORECASE),
    re.compile(r"\b(return|guarantee|refund|expiry|expires|freshness|warranty)\b", re.IGNORECASE),
    re.compile(r"\b(hurry|last chance|limited|fast|quick|urgent|don't miss)\b", re.IGNORECASE),
    re.compile(r"\b(cure|heal|treat|health|medicine|pharma|remedy)\b", re.IGNORECASE),
    re.compile(r"\b(best|amazing|incredible|ultimate|top-rated|unbeatable)\b", re.IGNORECASE),
]


def validate_reason_line(reason_line: str) -> Tuple[bool, str]:
    """
    Validates reason_line against length limit (<= 40 chars) and deny-list.
    Returns (is_valid, sanitized_or_fallback_line).
    """
    if not reason_line or not isinstance(reason_line, str):
        return False, ""

    clean_line = reason_line.strip()

    if len(clean_line) > 40:
        # Truncate at word boundary if over 40 chars
        words = clean_line[:40].split(" ")
        clean_line = " ".join(words[:-1]) if len(words) > 1 else clean_line[:40]

    for pattern in DENY_LIST_PATTERNS:
        if pattern.search(clean_line):
            return False, f"Line rejected by deny-list pattern: {pattern.pattern}"

    return True, clean_line


def get_template_reason_line(reason_code: str, category_name: str = "") -> str:
    """Returns human-written fallback template for a reason code."""
    templates = {
        "COMPLEMENT": "Pairs with your current basket",
        "LIFE_STAGE": "New essential for your household",
        "OCCASION": "Popular choice for the occasion",
        "ROUTINE_ADJACENT": "Goes well with your usual items",
        "SEASONAL": "Seasonal favorite for you",
        "GENERIC": "Recommended new category pick",
    }
    return templates.get(reason_code, "New category suggestion for you")


def validate_llm_response(
    raw_response_text: str, candidate_whitelist_ids: Set[int]
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Validates LLM raw JSON output contract (§5.6.5).
    Returns (is_valid, parsed_data_dict, error_message).
    """
    try:
        data = json.loads(raw_response_text)
    except Exception as e:
        return False, None, f"JSON parse error: {str(e)}"

    if not isinstance(data, dict) or "ranked" not in data or not isinstance(data["ranked"], list):
        return False, None, "Invalid schema: missing 'ranked' list"

    validated_ranked = []
    for item in data["ranked"]:
        sku_id = item.get("id") or item.get("sku_id")
        if sku_id not in candidate_whitelist_ids:
            # Unknown ID failure -> whole response rejected
            return False, None, f"Unknown candidate ID {sku_id} not in whitelist"

        reason_code = str(item.get("reason_code", "GENERIC")).upper()
        if reason_code not in ALLOWED_REASON_CODES:
            reason_code = "GENERIC"

        raw_line = item.get("reason_line", "")
        valid_line, result_line = validate_reason_line(raw_line)
        if not valid_line:
            # Replace rejected string with templated fallback
            result_line = get_template_reason_line(reason_code)

        validated_ranked.append({
            "sku_id": sku_id,
            "rank": item.get("rank", len(validated_ranked) + 1),
            "reason_code": reason_code,
            "reason_line": result_line,
        })

    return True, {"ranked": validated_ranked}, "Success"
