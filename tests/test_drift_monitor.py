"""
tests/test_drift_monitor.py — Continuous Drift Monitor Test Suite.
§8 architecture.md: Asserts alert triggering and auto-disabling on drift spikes.
"""

import pytest
from discovery.config.flags import FeatureFlags
from discovery.worker.drift_monitor import ContinuousDriftMonitor


def test_drift_monitor_llm_reject_spike_triggers_a3_disable():
    flags = FeatureFlags({"discovery.a3.enabled": True})
    monitor = ContinuousDriftMonitor(flags=flags)

    # Normal healthy evaluation
    has_alert, msg = monitor.evaluate_drift(
        llm_reject_rate=0.01, candidate_coverage_pct=95.0, copy_naturalness_score=0.85
    )
    assert has_alert is False
    assert flags.is_enabled("discovery.a3.enabled") is True

    # Drift evaluation with reject rate spike (6% >= 5%)
    has_alert, msg = monitor.evaluate_drift(
        llm_reject_rate=0.06, candidate_coverage_pct=95.0, copy_naturalness_score=0.85
    )
    assert has_alert is True
    assert "LLM Reject Rate Spike" in msg
    assert flags.is_enabled("discovery.a3.enabled") is False
