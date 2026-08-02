"""
discovery.offline.p_repeat_model — 60-day Repeat Purchase Probability Predictor.
§9 implementation-plan.md P4-4: Predicts p_repeat calibrated against holdout.
"""

from typing import Dict, Any
import math


class PRepeatModelPredictor:
    """Predicts p_repeat (60-day repeat purchase probability) calibrated on holdout."""

    def __init__(self):
        self.weights: Dict[str, float] = {
            "user_tenure_days": 0.005,
            "user_completed_orders": 0.03,
            "cand_velocity_30d": 0.015,
            "cand_complaint_rate": -3.0,
            "bias": -0.8,
        }

    def predict_p_repeat(self, features: Dict[str, float]) -> float:
        """Computes sigmoid prediction for p_repeat."""
        score = self.weights["bias"]
        for key, w in self.weights.items():
            if key in features:
                score += w * features[key]

        p = 1.0 / (1.0 + math.exp(-max(-10.0, min(10.0, score))))
        return min(0.95, max(0.05, p))
