"""
tests.test_catalog_reachability — Automated Test Suite for 1,100 Catalog Reachability.
"""

from discovery.eval.evaluate_catalog_reachability import evaluate_catalog_reachability


def test_catalog_reachability_metrics():
    """Verifies that the recommendation engine achieves >= 75% SKU reachability and >= 90% category coverage."""
    metrics = evaluate_catalog_reachability(num_sessions=1000)
    assert metrics["sku_coverage_pct"] >= 75.0, f"Expected SKU coverage >= 75%, got {metrics['sku_coverage_pct']}%"
    assert metrics["l1_coverage_pct"] >= 90.0, f"Expected L1 Category coverage >= 90%, got {metrics['l1_coverage_pct']}%"
    assert metrics["unique_skus_recommended"] > 700, f"Expected > 700 unique SKUs, got {metrics['unique_skus_recommended']}"
