"""
tests/test_chaos.py — Chaos & Fallback Suite.
§5 architecture.md: Asserts zero-impact cart render fallback during infrastructure failure & rehearses rollback drill.
"""

import pytest
from fastapi.testclient import TestClient
from discovery.api.app import create_app
from discovery.worker.nearline_worker import NearlineWorkerEngine
from discovery.worker.guardrail_monitor import GuardrailMonitor
from discovery.config.flags import FeatureFlags


@pytest.fixture
def flags():
    return FeatureFlags({"discovery.enabled": True, "discovery.slot_a.enabled": True})


@pytest.fixture
def worker(flags):
    return NearlineWorkerEngine(flags=flags)


def test_chaos_cache_miss_fallback(worker):
    """Asserts 204 fallback when decision cache is empty or wiped."""
    app = create_app(worker_engine=worker)
    client = TestClient(app)

    # Wipe cache completely
    worker.decision_cache.clear()

    res = client.get("/v1/discovery/slot?user_id=1&cart_id=c1&cart_hash=sig1&slot=A")
    assert res.status_code == 204


def test_chaos_flag_disabled_fallback(worker):
    """Asserts 204 fallback when discovery.enabled is turned off."""
    app = create_app(worker_engine=worker)
    client = TestClient(app)

    worker.flags.update("discovery.enabled", False)

    res = client.get("/v1/discovery/slot?user_id=1&cart_id=c1&cart_hash=sig1&slot=A")
    assert res.status_code == 204


def test_guardrail_cvr_breach_auto_rollback(flags):
    """Rehearses 5-minute automated rollback drill on CVR breach."""
    monitor = GuardrailMonitor(flags=flags)
    assert flags.is_enabled("discovery.enabled") is True

    # Simulate telemetry breach (-0.5% CVR drop)
    metrics = {"checkout_cvr_relative_delta": -0.005}
    is_breached, action = monitor.evaluate_metrics(metrics)

    assert is_breached is True
    assert action == "FULL_ROLLBACK"
    # Verify flag flipped to disabled automatically
    assert flags.is_enabled("discovery.enabled") is False


def test_guardrail_latency_breach_slot_disable(flags):
    """Rehearses automated slot disabling on +85ms p95 latency breach."""
    monitor = GuardrailMonitor(flags=flags)
    assert flags.is_enabled("discovery.slot_a.enabled") is True

    metrics = {"cart_latency_p95_delta_ms": 85.0}
    is_breached, action = monitor.evaluate_metrics(metrics)

    assert is_breached is True
    assert action == "DISABLE_SLOT_A"
    assert flags.is_enabled("discovery.slot_a.enabled") is False
