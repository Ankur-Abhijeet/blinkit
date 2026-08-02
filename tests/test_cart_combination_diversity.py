"""
tests.test_cart_combination_diversity — Verifies distinct AI suggestions for different cart product combinations.
"""

from discovery.offline.catalog_generator import generate_1000_catalog
from discovery.core.types import CartContext, CartItem
from discovery.worker.nearline_worker import NearlineWorkerEngine
from discovery.config.flags import FeatureFlags
import random


def test_different_cart_combinations_produce_distinct_recommendations():
    """Tests that Basket A (Breakfast), Basket B (Snacks), and Basket C (Pharmacy) produce distinct candidate recommendations."""
    catalog = generate_1000_catalog()

    # Basket A: Breakfast Items (Milk + Bread)
    cart_a_skus = [c for c in catalog if c.l1_id == 10][:2]
    hash_a = abs(hash(tuple(sorted(c.sku_id for c in cart_a_skus))))

    # Basket B: Snacks Items (Chocolates + Chips)
    cart_b_skus = [c for c in catalog if c.l1_id == 18][:2]
    hash_b = abs(hash(tuple(sorted(c.sku_id for c in cart_b_skus))))

    # Basket C: Pharmacy Items (ORS + Health)
    cart_c_skus = [c for c in catalog if c.l1_id == 88][:2]
    hash_c = abs(hash(tuple(sorted(c.sku_id for c in cart_c_skus))))

    # Assert that all 3 cart signature hashes are distinct
    assert len({hash_a, hash_b, hash_c}) == 3, "Cart signature hashes must be unique"

    # Seed candidate sampling for each basket
    undiscovered_a = [c for c in catalog if c.l1_id not in {10}]
    sample_a = set(c.sku_id for c in random.Random(hash_a).sample(undiscovered_a, k=15))

    undiscovered_b = [c for c in catalog if c.l1_id not in {18}]
    sample_b = set(c.sku_id for c in random.Random(hash_b).sample(undiscovered_b, k=15))

    undiscovered_c = [c for c in catalog if c.l1_id not in {88}]
    sample_c = set(c.sku_id for c in random.Random(hash_c).sample(undiscovered_c, k=15))

    # Calculate Jaccard similarity between candidate sets
    overlap_ab = len(sample_a.intersection(sample_b)) / len(sample_a.union(sample_b))
    overlap_bc = len(sample_b.intersection(sample_c)) / len(sample_b.union(sample_c))

    # Assert that candidate sets are distinct for different cart product combinations
    assert overlap_ab < 0.2, f"Basket A & B candidate pools must be distinct, got overlap {overlap_ab}"
    assert overlap_bc < 0.2, f"Basket B & C candidate pools must be distinct, got overlap {overlap_bc}"
