"""
tests/test_emergency_runbook.py — Emergency Operations Runbook Test Suite.
§8.4 & §12.3 architecture.md: Emergency kill switch, decision cache flush, and rulebook rollback.
"""

import pytest
from discovery.config.flags import FeatureFlags
from discovery.offline.rulebook_store import RulebookStore
from discovery.offline.a3_rulebook_job import generate_a3_cell_rulebook
from discovery.worker.nearline_worker import NearlineWorkerEngine
from discovery.config.emergency_runbook import EmergencyOperationsRunbook


def test_emergency_kill_all_interrupts():
    flags = FeatureFlags({"discovery.enabled": True, "discovery.slot_a.enabled": True})
    store = RulebookStore()
    worker = NearlineWorkerEngine(flags=flags, rulebook_store=store)

    runbook = EmergencyOperationsRunbook(flags=flags, rulebook_store=store, worker_engine=worker)

    assert flags.is_enabled("discovery.enabled") is True
    runbook.kill_all_interrupts(reason="System anomaly detected")

    assert flags.is_enabled("discovery.enabled") is False
    assert flags.is_enabled("discovery.slot_a.enabled") is False
    assert runbook.audit_log[0]["action"] == "KILL_ALL"


def test_emergency_rulebook_rollback_and_cache_flush():
    flags = FeatureFlags({"discovery.enabled": True})
    store = RulebookStore()
    worker = NearlineWorkerEngine(flags=flags, rulebook_store=store)

    # Publish v1.0 and v2.0
    entry_v1 = generate_a3_cell_rulebook("state1", "sig1", [20], raw_copy_lines={20: "v1 copy"})
    entry_v2 = generate_a3_cell_rulebook("state1", "sig1", [20], raw_copy_lines={20: "v2 copy"})

    store.publish_a3_rulebook([entry_v1], "v1.0")
    store.publish_a3_rulebook([entry_v2], "v2.0")

    # Populate cache item
    worker.decision_cache["key1"] = (None, 9999999999.0)
    assert len(worker.decision_cache) == 1

    runbook = EmergencyOperationsRunbook(flags=flags, rulebook_store=store, worker_engine=worker)

    # Flush cache
    flushed = runbook.flush_decision_cache("Emergency flush test")
    assert flushed == 1
    assert len(worker.decision_cache) == 0

    # Rollback rulebook
    rolled_back = runbook.rollback_rulebook_version("v1.0", "Rollback v2.0 anomaly")
    assert rolled_back is True
    assert store.active_version == "v1.0"
