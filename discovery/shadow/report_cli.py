"""
discovery.shadow.report_cli — Command Line Tool to run shadow replay and print Appendix C report.
Usage: python -m discovery.shadow.report_cli
"""

import json
from typing import List, Tuple, Dict
from discovery.core.types import CartContext, CartItem, Candidate
from discovery.shadow.replay import run_shadow_decision, generate_coverage_report


def build_synthetic_corpus() -> Tuple[List[CartContext], List[Candidate]]:
    """Generates synthetic 1,000 cart corpus and store candidate pool for audit."""
    carts = []
    for i in range(1, 1001):
        items = [
            CartItem(
                sku_id=i,
                l1_id=10 + (i % 4),
                l2_id=100 + i,
                name=f"Grocery Staple {i}",
                price_paise=4000 + (i % 10) * 1000,
            )
        ]
        ctx = CartContext(
            user_id=1000 + i,
            session_id=f"sess_{i}",
            cart_id=f"cart_{i}",
            store_id=50,
            cart_subtotal_paise=20000 + (i % 20) * 1000,  # ₹200–₹400
            cart_items=items,
            tenure_days=30,
            completed_orders=5,
        )
        carts.append(ctx)

    pool = []
    # 28 L1 categories
    for l1 in range(1, 29):
        # Exclude F7 categories: 8881..8886 are mapped separately
        for idx in range(1, 4):
            cand = Candidate(
                sku_id=l1 * 100 + idx,
                l1_id=l1,
                l2_id=l1 * 1000 + idx,
                name=f"Category {l1} SKU {idx}",
                pack="100g",
                price_paise=2500 + idx * 500,  # ₹25–₹40 (passes F3 ceiling)
                mrp_paise=5000,
                margin_pct=0.25,
                velocity_30d=35,
                complaint_rate=0.01,
                available_qty=15,
                store_age_days=180,
            )
            pool.append(cand)

    return carts, pool


def main():
    print("==================================================================")
    print(" THE CART INTERRUPT MVP — PHASE 0 SHADOW COVERAGE REPORT AUDIT")
    print("==================================================================")
    carts, pool = build_synthetic_corpus()

    decisions = [
        run_shadow_decision(ctx, pool, user_purchased_l1_ids={10, 11, 12})
        for ctx in carts
    ]

    report = generate_coverage_report(decisions)

    print(f"Total Carts Evaluated: {report['total_carts']}")
    print(f"Eligible Carts (>=1 candidate): {report['eligible_carts']}")
    print(f"Coverage Percentage: {report['coverage_pct']}%")
    print(f"Gate 0 Exit Verdict: {report['gate_0_verdict']}")
    print("\nDrop Reason Histogram (Top Filter Exclusions):")
    print("------------------------------------------------------------------")
    for filter_id, count in sorted(report['drop_histogram'].items(), key=lambda x: x[1], reverse=True):
        print(f"  Filter {filter_id:5s} : {count} drops")
    print("==================================================================")


if __name__ == "__main__":
    main()
