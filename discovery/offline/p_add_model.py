"""
discovery.offline.p_add_model — Inverse-Propensity Weighted p_add Predictor.
§9 implementation-plan.md P4-3: Predicts p_add with IPW correction (1 / e(c)).
"""

from typing import Dict, Any, List
import math


class PAddModelPredictor:
    """Predicts p_add (probability of add-to-cart) with IPW selection-bias correction."""

    def __init__(self):
        # Linear feature weights for p_add model
        self.weights: Dict[str, float] = {
            "cand_margin_pct": 0.5,
            "cand_velocity_30d": 0.02,
            "affinity_score": 1.2,
            "cand_complaint_rate": -2.0,
            "cart_item_count": 0.05,
            "bias": -1.0,
        }

    def predict_p_add(self, features: Dict[str, float]) -> float:
        """Computes sigmoid prediction for p_add."""
        score = self.weights["bias"]
        for key, w in self.weights.items():
            if key in features:
                score += w * features[key]

        # Sigmoid activation
        p = 1.0 / (1.0 + math.exp(-max(-10.0, min(10.0, score))))
        return min(0.99, max(0.01, p))

    def train_ipw_epoch(self, samples: List[Dict[str, Any]]) -> float:
        """
        Simulates IPW training step.
        Each sample contains: {"features": dict, "label": 0/1, "exploration_prob": float}
        Loss weight = 1.0 / exploration_prob (Inverse-Propensity Weighting).
        """
        total_ipw_loss = 0.0
        for sample in samples:
            features = sample["features"]
            label = sample["label"]
            prob = sample.get("exploration_prob", 0.5)

            # IPW weight = 1 / prob
            ipw_weight = 1.0 / max(0.05, prob)

            pred = self.predict_p_add(features)
            loss = - (label * math.log(pred) + (1 - label) * math.log(1 - pred))
            total_ipw_loss += loss * ipw_weight

        return total_ipw_loss / max(1, len(samples))
