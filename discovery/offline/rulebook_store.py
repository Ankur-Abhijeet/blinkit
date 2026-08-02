"""
discovery.offline.rulebook_store — Versioned Rulebook Repository & Applier.
§6 architecture.md: Manages versioned rulebooks, rollback pointers, and deterministic nearline lookup.
"""

from typing import Dict, Any, Optional, List
import time
from discovery.offline.a3_rulebook_job import A3CellRulebookEntry
from discovery.offline.a2_rulebook_job import HouseholdStateProfile


class RulebookStore:
    """Versioned Rulebook Repository supporting publication, rollback, and fast lookup."""

    def __init__(self):
        # Key: (version, state_id, cart_sig) -> A3CellRulebookEntry
        self._a3_entries: Dict[tuple[str, str, str], A3CellRulebookEntry] = {}
        # Key: user_id -> HouseholdStateProfile
        self._a2_profiles: Dict[int, HouseholdStateProfile] = {}
        # Active published version pointer
        self.active_version: str = "v1.0"
        self.version_history: List[str] = ["v1.0"]

    def publish_a3_rulebook(self, entries: List[A3CellRulebookEntry], version: str) -> bool:
        """Publishes a new versioned A3 rulebook after pre-publication validation."""
        for entry in entries:
            key = (version, entry.state_id, entry.cart_sig)
            self._a3_entries[key] = entry

        if version not in self.version_history:
            self.version_history.append(version)
        self.active_version = version
        return True

    def rollback_to_version(self, target_version: str) -> bool:
        """Rolls back active version pointer to last-known-good version."""
        if target_version in self.version_history:
            self.active_version = target_version
            return True
        return False

    def save_a2_profile(self, profile: HouseholdStateProfile) -> None:
        """Saves a daily A2 household state profile."""
        self._a2_profiles[profile.user_id] = profile

    def get_a2_profile(self, user_id: int) -> Optional[HouseholdStateProfile]:
        return self._a2_profiles.get(user_id)

    def lookup_a3_cell_entry(
        self, state_id: str, cart_sig: str, version: Optional[str] = None
    ) -> Optional[A3CellRulebookEntry]:
        """
        Looks up A3 cell rulebook entry for active version.
        Returns None on cold cell / rulebook miss -> triggers fallback to Arm B deterministic order.
        """
        ver = version or self.active_version
        key = (ver, state_id, cart_sig)
        return self._a3_entries.get(key)
