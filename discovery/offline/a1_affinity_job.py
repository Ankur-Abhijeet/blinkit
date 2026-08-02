"""
discovery.offline.a1_affinity_job — A1 Semantic Affinity calibration harness.
§5.6.1 & eval.md §4.1: Disjoint 70/30 fit/eval split. MAE <= 0.15 required to ship.
"""

from typing import Dict, Tuple, List


def compute_calibration_mae(
    priors: Dict[Tuple[int, int], float],
    observed_lifts: Dict[Tuple[int, int], float],
    eval_pair_keys: List[Tuple[int, int]],
) -> float:
    """
    Computes calibration MAE on held-out A1-EVAL pairs:
    MAE = mean |llm_prior(A,B) - normalized_observed_lift(A,B)|
    """
    if not eval_pair_keys:
        return 0.0

    total_diff = 0.0
    valid_count = 0

    for key in eval_pair_keys:
        if key in priors and key in observed_lifts:
            prior = priors[key]
            lift = observed_lifts[key]
            # Normalize observed lift to [0, 1] range assuming max lift ~3.0
            norm_lift = min(1.0, max(0.0, (lift - 1.0) / 2.0))
            total_diff += abs(prior - norm_lift)
            valid_count += 1

    return total_diff / valid_count if valid_count > 0 else 0.0


def evaluate_a1_calibration_gate(
    calibration_mae: float,
) -> Tuple[str, str]:
    """
    Evaluates Phase 0 Gate 0 decision rules for A1 calibration:
    - MAE <= 0.15 -> Trust LLM priors in zero cells
    - 0.15 < MAE <= 0.30 -> Use LLM priors for candidate generation only
    - MAE > 0.30 -> Do not ship A1
    """
    if calibration_mae <= 0.15:
        return "PASS", "Trust LLM priors in zero cells (scaled by 1 - MAE)"
    elif calibration_mae <= 0.30:
        return "MARGINAL", "Use LLM priors for candidate generation only; do not score"
    else:
        return "FAIL", "Do not ship A1. Fall back to co-occurrence-only CG2."
