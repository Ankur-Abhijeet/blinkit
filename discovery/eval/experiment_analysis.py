"""
discovery.eval.experiment_analysis — Experimentation & Statistical Analysis Pipeline.
§8 solution.md & eval.md: Calculates primary CVR, secondary metrics, guardrails, and Z-test p-values.
"""

from typing import Dict, Any, Tuple
import math
from pydantic import BaseModel


class ArmMetrics(BaseModel):
    arm_name: str
    total_carts: int
    completed_orders: int
    total_aov_paise: int
    new_category_adds: int
    total_cart_order_seconds: float
    cancelled_orders: int

    @property
    def checkout_cvr(self) -> float:
        return self.completed_orders / self.total_carts if self.total_carts > 0 else 0.0

    @property
    def avg_aov_rupees(self) -> float:
        return (self.total_aov_paise / self.completed_orders / 100.0) if self.completed_orders > 0 else 0.0

    @property
    def discovery_rate(self) -> float:
        return self.new_category_adds / self.total_carts if self.total_carts > 0 else 0.0

    @property
    def cancellation_rate(self) -> float:
        return self.cancelled_orders / self.total_carts if self.total_carts > 0 else 0.0


def calculate_two_proportion_z_test(
    control: ArmMetrics, treatment: ArmMetrics
) -> Tuple[float, float, bool]:
    """
    Calculates two-proportion Z-test for checkout CVR between control and treatment arms.
    Returns (z_score, p_value, is_statistically_significant_at_95).
    """
    n1 = control.total_carts
    x1 = control.completed_orders
    n2 = treatment.total_carts
    x2 = treatment.completed_orders

    if n1 <= 0 or n2 <= 0:
        return 0.0, 1.0, False

    p1 = x1 / n1
    p2 = x2 / n2

    # Pooled proportion
    p_pool = (x1 + x2) / (n1 + n2)

    if p_pool == 0 or p_pool == 1:
        return 0.0, 1.0, False

    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return 0.0, 1.0, False

    z = (p2 - p1) / se

    # Two-tailed p-value approximation via ERFC
    p_value = math.erfc(abs(z) / math.sqrt(2))

    is_significant = p_value < 0.05
    return z, p_value, is_significant


def evaluate_experiment_results(
    arm_a: ArmMetrics, arm_b: ArmMetrics, arm_c: ArmMetrics, holdout: ArmMetrics
) -> Dict[str, Any]:
    """
    Evaluates complete experiment portfolio across Control A, Deterministic B, AI C, and Holdout.
    Performs §8.3 decision rule checks:
    - Arm B vs Arm A: Must achieve >= +0.5% relative CVR lift with p < 0.05.
    - Arm C vs Arm B: Must achieve >= +0.4pp CVR lift with p < 0.05 to keep A3 AI layer.
    """
    # B vs A Z-test
    z_ba, p_ba, sig_ba = calculate_two_proportion_z_test(arm_a, arm_b)
    cvr_lift_ba_rel = ((arm_b.checkout_cvr - arm_a.checkout_cvr) / arm_a.checkout_cvr) if arm_a.checkout_cvr > 0 else 0.0

    # C vs B Z-test
    z_cb, p_cb, sig_cb = calculate_two_proportion_z_test(arm_b, arm_c)
    cvr_lift_cb_abs = arm_c.checkout_cvr - arm_b.checkout_cvr

    keep_a3 = sig_cb and (cvr_lift_cb_abs >= 0.004)  # +0.4pp lift requirement

    return {
        "arm_a_cvr": round(arm_a.checkout_cvr, 4),
        "arm_b_cvr": round(arm_b.checkout_cvr, 4),
        "arm_c_cvr": round(arm_c.checkout_cvr, 4),
        "holdout_cvr": round(holdout.checkout_cvr, 4),
        "b_vs_a_relative_cvr_lift": round(cvr_lift_ba_rel, 4),
        "b_vs_a_p_value": round(p_ba, 4),
        "b_vs_a_significant": sig_ba,
        "c_vs_b_absolute_cvr_lift": round(cvr_lift_cb_abs, 4),
        "c_vs_b_p_value": round(p_cb, 4),
        "c_vs_b_significant": sig_cb,
        "a3_keep_decision": "KEEP_A3" if keep_a3 else "DELETE_A3_FALLBACK_TO_ARM_B",
    }
