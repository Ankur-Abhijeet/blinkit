"""
tests/test_eval_metrics.py — Statistical Evaluation & Decision Rule Test Suite.
§8 solution.md & §8.3 eval.md: Z-test calculations and Arm C vs Arm B decision rules.
"""

import pytest
from discovery.eval.experiment_analysis import (
    ArmMetrics,
    calculate_two_proportion_z_test,
    evaluate_experiment_results,
)


def test_two_proportion_z_test_statistically_significant_lift():
    control = ArmMetrics(
        arm_name="A", total_carts=10000, completed_orders=1500, total_aov_paise=300000000,
        new_category_adds=200, total_cart_order_seconds=120000.0, cancelled_orders=100
    )
    treatment = ArmMetrics(
        arm_name="B", total_carts=10000, completed_orders=1650, total_aov_paise=330000000,
        new_category_adds=380, total_cart_order_seconds=118000.0, cancelled_orders=95
    )

    z, p_val, is_sig = calculate_two_proportion_z_test(control, treatment)
    assert z > 2.0
    assert p_val < 0.05
    assert is_sig is True


def test_evaluate_experiment_results_keep_a3():
    arm_a = ArmMetrics(arm_name="A", total_carts=10000, completed_orders=1500, total_aov_paise=300, new_category_adds=200, total_cart_order_seconds=100, cancelled_orders=100)
    arm_b = ArmMetrics(arm_name="B", total_carts=10000, completed_orders=1650, total_aov_paise=320, new_category_adds=350, total_cart_order_seconds=100, cancelled_orders=90)
    arm_c = ArmMetrics(arm_name="C", total_carts=10000, completed_orders=1800, total_aov_paise=340, new_category_adds=450, total_cart_order_seconds=95, cancelled_orders=85)
    holdout = ArmMetrics(arm_name="H", total_carts=500, completed_orders=75, total_aov_paise=15, new_category_adds=10, total_cart_order_seconds=5, cancelled_orders=5)

    results = evaluate_experiment_results(arm_a, arm_b, arm_c, holdout)
    assert results["b_vs_a_significant"] is True
    assert results["c_vs_b_significant"] is True
    assert results["a3_keep_decision"] == "KEEP_A3"
