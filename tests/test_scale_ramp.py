"""
tests/test_scale_ramp.py — Scale Ramp & Gate 5 Repeat Rate Test Suite.
§10 implementation-plan.md: Asserts scale ramp stage progression, per-city guardrails, and Gate 5 repeat rate veto.
"""

import pytest
from discovery.config.flags import FeatureFlags
from discovery.eval.scale_ramp import ScaleRampOrchestrator
from discovery.eval.repeat_rate_eval import evaluate_gate_5_repeat_rate


def test_scale_ramp_advancement():
    flags = FeatureFlags({"discovery.traffic_pct": 2.0})
    orchestrator = ScaleRampOrchestrator(flags=flags)

    assert orchestrator.current_traffic_pct == 2.0

    # Advance 2% -> 10%
    ok, new_pct = orchestrator.advance_stage(regional_assortment_depth_ok=True)
    assert ok is True
    assert new_pct == 10.0
    assert flags.get("discovery.traffic_pct") == 10.0

    # Advance 10% -> 25%
    ok, new_pct = orchestrator.advance_stage(regional_assortment_depth_ok=True)
    assert ok is True
    assert new_pct == 25.0


def test_scale_ramp_per_city_guardrail_breach():
    flags = FeatureFlags({"discovery.traffic_pct": 25.0})
    orchestrator = ScaleRampOrchestrator(flags=flags)

    city_cvrs = {"delhi": 0.001, "mumbai": -0.004}  # Mumbai breaches -0.3%
    city_lats = {"delhi": 20.0, "mumbai": 30.0}

    ok, msg = orchestrator.evaluate_stage_guardrails(city_cvrs, city_lats)
    assert ok is False
    assert "Per-city CVR breach in mumbai" in msg
    assert flags.get("discovery.traffic_pct") == 0.5  # Paused / dropped traffic


def test_gate_5_repeat_rate_cleared():
    res = evaluate_gate_5_repeat_rate(total_converts=1000, repeating_converts_60d=300)
    assert res["repeat_rate"] == 0.30
    assert res["threshold_cleared"] is True
    assert res["gate_5_verdict"] == "SHIP_TO_100_PERCENT"


def test_gate_5_repeat_rate_veto():
    # Only 15% repeat rate (< 25% threshold)
    res = evaluate_gate_5_repeat_rate(total_converts=1000, repeating_converts_60d=150)
    assert res["repeat_rate"] == 0.15
    assert res["threshold_cleared"] is False
    assert res["gate_5_verdict"] == "REJECT_SCALE_DISCOUNT_ENGINE_VETO"
