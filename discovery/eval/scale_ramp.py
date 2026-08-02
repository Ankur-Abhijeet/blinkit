"""
discovery.eval.scale_ramp — Scale Ramp Orchestrator.
§10 implementation-plan.md: Manages traffic ramp (2% -> 10% -> 25% -> 50% -> 100%) and per-city guardrails.
"""

from typing import Dict, Any, List, Tuple
from discovery.config.flags import FeatureFlags


class ScaleRampOrchestrator:
    """Orchestrates multi-stage traffic ramp and per-city guardrails."""

    STAGES: List[float] = [2.0, 10.0, 25.0, 50.0, 100.0]

    def __init__(self, flags: FeatureFlags):
        self.flags = flags
        self.current_stage_idx: int = 0
        self.ramp_history: List[Dict[str, Any]] = []

    @property
    def current_traffic_pct(self) -> float:
        return self.STAGES[self.current_stage_idx]

    def advance_stage(self, regional_assortment_depth_ok: bool = True) -> Tuple[bool, float]:
        """Advances to next traffic ramp stage if regional assortment depth is verified."""
        if not regional_assortment_depth_ok:
            return False, self.current_traffic_pct

        if self.current_stage_idx < len(self.STAGES) - 1:
            self.current_stage_idx += 1
            new_pct = self.STAGES[self.current_stage_idx]
            self.flags.update("discovery.traffic_pct", new_pct)
            self.ramp_history.append({"stage_idx": self.current_stage_idx, "traffic_pct": new_pct})
            return True, new_pct

        return False, self.current_traffic_pct

    def evaluate_stage_guardrails(
        self, city_cvr_deltas: Dict[str, float], city_latency_deltas: Dict[str, float]
    ) -> Tuple[bool, str]:
        """Evaluates per-city CVR and latency guardrails before stage advancement."""
        for city, cvr_delta in city_cvr_deltas.items():
            if cvr_delta <= -0.003:  # -0.3% CVR breach
                self.flags.update("discovery.traffic_pct", 0.5)  # Drop to smoke test
                return False, f"Per-city CVR breach in {city}: {cvr_delta:.4f}"

        for city, lat_delta in city_latency_deltas.items():
            if lat_delta >= 80.0:  # +80ms p95 latency breach
                return False, f"Per-city latency breach in {city}: {lat_delta:.1f}ms"

        return True, "ALL_CITIES_HEALTHY"
