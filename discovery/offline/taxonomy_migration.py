"""
discovery.offline.taxonomy_migration — Zero-Downtime Taxonomy Migration Handler.
§10 architecture.md: Dual-read category re-mapper preserving user history & suppression cooldowns.
"""

from typing import Dict, Tuple, Set, List


class TaxonomyMigrationHandler:
    """Manages category ID remappings during L1/L2 taxonomy reorganizations."""

    def __init__(self):
        # Key: (old_l1_id, old_l2_id) -> (new_l1_id, new_l2_id)
        self._mappings: Dict[Tuple[int, int], Tuple[int, int]] = {}
        # Key: old_l1_id -> new_l1_id
        self._l1_mappings: Dict[int, int] = {}
        self.migration_active: bool = False

    def register_l1_mapping(self, old_l1_id: int, new_l1_id: int) -> None:
        self._l1_mappings[old_l1_id] = new_l1_id
        self.migration_active = True

    def register_mapping(self, old_l1_id: int, old_l2_id: int, new_l1_id: int, new_l2_id: int) -> None:
        self._mappings[(old_l1_id, old_l2_id)] = (new_l1_id, new_l2_id)
        self._l1_mappings[old_l1_id] = new_l1_id
        self.migration_active = True

    def canonicalize_l1_id(self, l1_id: int) -> int:
        """Returns canonical L1 ID (resolving aliases during migration window)."""
        return self._l1_mappings.get(l1_id, l1_id)

    def canonicalize_l1_set(self, l1_ids: Set[int]) -> Set[int]:
        """Maps a set of L1 IDs to their canonical representations."""
        return {self.canonicalize_l1_id(l1) for l1 in l1_ids}

    def canonicalize_l1_l2_pair(self, l1_id: int, l2_id: int) -> Tuple[int, int]:
        """Maps an (l1, l2) pair to canonical pair."""
        return self._mappings.get((l1_id, l2_id), (self.canonicalize_l1_id(l1_id), l2_id))
