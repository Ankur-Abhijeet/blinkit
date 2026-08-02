"""
discovery.eval.repeat_rate_eval — 60-Day Category Repeat Rate Evaluator for Gate 5.
§10 implementation-plan.md Gate 5: Asserts 60-day repeat rate >= 25% among converts.
"""

from typing import Dict, Any


def evaluate_gate_5_repeat_rate(
    total_converts: int, repeating_converts_60d: int
) -> Dict[str, Any]:
    """
    Evaluates 60-day repeat purchase rate among converted users.
    Threshold: repeat_rate >= 0.25 (25%).
    If repeat_rate < 0.25 -> Vetoes scale (identifies discount engine rather than discovery engine).
    """
    if total_converts <= 0:
        return {
            "total_converts": 0,
            "repeat_rate": 0.0,
            "threshold_cleared": False,
            "gate_5_verdict": "REJECT_INSUFFICIENT_DATA",
        }

    repeat_rate = repeating_converts_60d / total_converts
    threshold_cleared = repeat_rate >= 0.25

    return {
        "total_converts": total_converts,
        "repeating_converts_60d": repeating_converts_60d,
        "repeat_rate": round(repeat_rate, 4),
        "threshold_cleared": threshold_cleared,
        "gate_5_verdict": "SHIP_TO_100_PERCENT" if threshold_cleared else "REJECT_SCALE_DISCOUNT_ENGINE_VETO",
    }
