"""
tests/test_taxonomy_migration.py — Taxonomy Migration & Dual-Read Alias Test Suite.
§10 architecture.md: Asserts zero-downtime category re-mapping preserving user history.
"""

import pytest
from discovery.offline.taxonomy_migration import TaxonomyMigrationHandler


def test_l1_taxonomy_migration_canonicalization():
    handler = TaxonomyMigrationHandler()
    # Migration: Old L1=99 (Legacy Snacks) -> New L1=15 (Packaged Foods)
    handler.register_l1_mapping(old_l1_id=99, new_l1_id=15)

    assert handler.canonicalize_l1_id(99) == 15
    assert handler.canonicalize_l1_id(10) == 10  # Unmapped ID remains unchanged

    user_history_l1s = {10, 11, 99}
    canonical_set = handler.canonicalize_l1_set(user_history_l1s)
    assert canonical_set == {10, 11, 15}


def test_l1_l2_pair_taxonomy_migration():
    handler = TaxonomyMigrationHandler()
    # Migration: Old (88, 8801) -> New (20, 2001)
    handler.register_mapping(old_l1_id=88, old_l2_id=8801, new_l1_id=20, new_l2_id=2001)

    assert handler.canonicalize_l1_l2_pair(88, 8801) == (20, 2001)
    assert handler.canonicalize_l1_l2_pair(10, 101) == (10, 101)
