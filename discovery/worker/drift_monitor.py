"""
discovery.worker.drift_monitor — Continuous Drift & Rulebook Quality Monitor.
§8 architecture.md: Tracks LLM reject rates, candidate coverage, and copy naturalness drift.
"""

from typing import Dict, Any, List, Tuple
from discovery.config.flags import FeatureFlags


class ContinuousDriftMonitor:
    """Monitors offline rulebooks and live output distributions for quality drift."""

    def __init__(self, flags: FeatureFlags):
        self.flags = flags
        self.alert_history: List[Dict[str, Any]] = []

    def evaluate_drift(
        self,
        llm_reject_rate: float,
        candidate_coverage_pct: float,
        copy_naturalness_score: float,
    ) -> Tuple[bool, str]:
        """
        Evaluates drift metrics against operational bounds:
        - llm_reject_rate >= 0.05 (5%) -> Alert & Disable A3
        - candidate_coverage_pct < 80.0% -> Alert
        - copy_naturalness_score < 0.70 -> Alert

        Returns (has_alert, status_msg).
        """
        alerts = []

        if llm_reject_rate >= 0.05:
            alerts.append(f"LLM Reject Rate Spike: {llm_reject_rate*100:.1f}% >= 5.0%")
            self.flags.update("discovery.a3.enabled", False)

        if candidate_coverage_pct < 80.0:
            alerts.append(f"Candidate Coverage Degradation: {candidate_coverage_pct:.1f}% < 80.0%")

        if copy_naturalness_score < 0.70:
            alerts.append(f"Copy Naturalness Drift: {copy_naturalness_score:.2f} < 0.70")

        if alerts:
            summary = "; ".join(alerts)
            self.alert_history.append({"status": "ALERT", "summary": summary})
            return True, summary

        return False, "HEALTHY"
