"""
discovery.worker.guardrail_monitor — Automated Guardrail Monitor & Rollback Evaluator.
§8.4 solution.md: Evaluates telemetry metrics every 5 min; flips flags on breach.
"""

from typing import Dict, Any, Tuple
from discovery.config.flags import FeatureFlags


class GuardrailMonitor:
    """Evaluates telemetry metrics against §8.4 auto-rollback triggers."""

    def __init__(self, flags: FeatureFlags):
        self.flags = flags
        self.breach_log: list[Dict[str, Any]] = []

    def evaluate_metrics(self, metrics: Dict[str, float]) -> Tuple[bool, str]:
        """
        Evaluates metrics map against thresholds:
        - checkout_cvr_relative_delta <= -0.003 (-0.3%) -> Full Rollback
        - cart_order_time_delta_sec >= 5.0 -> Full Rollback
        - cart_latency_p95_delta_ms >= 80.0 -> Disable Slot A
        - cancellation_rate_absolute_delta >= 0.005 (+0.5%) -> Full Rollback
        - llm_reject_rate >= 0.05 (5%) -> Disable A3

        Returns (is_breached, action_taken).
        """
        cvr_delta = metrics.get("checkout_cvr_relative_delta", 0.0)
        time_delta = metrics.get("cart_order_time_delta_sec", 0.0)
        latency_delta = metrics.get("cart_latency_p95_delta_ms", 0.0)
        cancellation_delta = metrics.get("cancellation_rate_absolute_delta", 0.0)
        reject_rate = metrics.get("llm_reject_rate", 0.0)

        # 1. Full Rollback Triggers
        if cvr_delta <= -0.003 or time_delta >= 5.0 or cancellation_delta >= 0.005:
            reason = f"Breach detected: CVR delta={cvr_delta:.4f}, time delta={time_delta:.1f}s, cancel delta={cancellation_delta:.4f}"
            self.flags.update("discovery.enabled", False)
            self._log_breach("FULL_ROLLBACK", reason)
            return True, "FULL_ROLLBACK"

        # 2. Disable Slot A Trigger
        if latency_delta >= 80.0:
            reason = f"Latency breach: p95 delta={latency_delta:.1f}ms >= 80ms"
            self.flags.update("discovery.slot_a.enabled", False)
            self._log_breach("DISABLE_SLOT_A", reason)
            return True, "DISABLE_SLOT_A"

        # 3. Disable A3 Trigger
        if reject_rate >= 0.05:
            reason = f"A3 reject rate breach: reject_rate={reject_rate*100:.1f}% >= 5%"
            self.flags.update("discovery.a3.enabled", False)
            self._log_breach("DISABLE_A3", reason)
            return True, "DISABLE_A3"

        return False, "HEALTHY"

    def _log_breach(self, action: str, reason: str) -> None:
        self.breach_log.append({"action": action, "reason": reason})
