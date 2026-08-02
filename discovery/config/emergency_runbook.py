"""
discovery.config.emergency_runbook — Emergency Operations CLI & Kill Switches.
§8.4 & §12.3 architecture.md: Instant one-command kill switch, cache flush, and rulebook rollback.
"""

from typing import Dict, Any, Optional
from discovery.config.flags import FeatureFlags
from discovery.offline.rulebook_store import RulebookStore
from discovery.worker.nearline_worker import NearlineWorkerEngine


class EmergencyOperationsRunbook:
    """Operational runbook handler for manual emergency interventions."""

    def __init__(self, flags: FeatureFlags, rulebook_store: RulebookStore, worker_engine: NearlineWorkerEngine):
        self.flags = flags
        self.rulebook_store = rulebook_store
        self.worker_engine = worker_engine
        self.audit_log: list[Dict[str, Any]] = []

    def kill_all_interrupts(self, reason: str = "Manual Emergency Kill Switch") -> bool:
        """Instantly disables all discovery interrupts globally across all slots."""
        self.flags.update("discovery.enabled", False)
        self.flags.update("discovery.slot_a.enabled", False)
        self.flags.update("discovery.slot_b.enabled", False)
        self._log_action("KILL_ALL", reason)
        return True

    def rollback_rulebook_version(self, target_version: str, reason: str = "Rulebook Rollback") -> bool:
        """Rolls back published rulebook version in RulebookStore."""
        success = self.rulebook_store.rollback_to_version(target_version)
        if success:
            self._log_action("ROLLBACK_RULEBOOK", f"Version: {target_version}, Reason: {reason}")
        return success

    def flush_decision_cache(self, reason: str = "Manual Cache Flush") -> int:
        """Flushes nearline worker decision cache."""
        flushed_count = len(self.worker_engine.decision_cache)
        self.worker_engine.decision_cache.clear()
        self._log_action("FLUSH_CACHE", f"Flushed {flushed_count} keys. Reason: {reason}")
        return flushed_count

    def _log_action(self, action: str, details: str) -> None:
        self.audit_log.append({"action": action, "details": details})


def main():
    print("==================================================================")
    print(" THE CART INTERRUPT MVP — PHASE 4 EMERGENCY RUNBOOK CLI")
    print("==================================================================")
    flags = FeatureFlags()
    store = RulebookStore()
    worker = NearlineWorkerEngine(flags=flags, rulebook_store=store)

    runbook = EmergencyOperationsRunbook(flags=flags, rulebook_store=store, worker_engine=worker)
    runbook.kill_all_interrupts("Operational Drill Test")

    print(f"Global Discovery Enabled: {flags.is_enabled('discovery.enabled')}")
    print(f"Slot A Enabled:           {flags.is_enabled('discovery.slot_a.enabled')}")
    print(f"Audit Log:                {runbook.audit_log}")
    print("==================================================================")


if __name__ == "__main__":
    main()
