"""
discovery.offline.posteriors_job — Nightly Beta Posteriors & Thompson Sampling.
§9 implementation-plan.md P4-7/P4-8: Nightly Beta updates (alpha, beta) for multi-armed bandit exploration.
"""

from typing import Dict, Tuple
import math


class ThompsonSamplingPosteriors:
    """Manages Beta distribution posteriors for category arms."""

    def __init__(self):
        # Key: l1_id -> (alpha, beta)
        self.posteriors: Dict[int, Tuple[float, float]] = {}

    def update_posterior(self, l1_id: int, adds: int, impressions: int) -> Tuple[float, float]:
        """
        Updates Beta(alpha, beta) parameters:
        alpha = prior_alpha + adds
        beta = prior_beta + (impressions - adds)
        """
        prior_a, prior_b = self.posteriors.get(l1_id, (1.0, 1.0))
        new_a = prior_a + adds
        new_b = prior_b + max(0, impressions - adds)
        self.posteriors[l1_id] = (new_a, new_b)
        return new_a, new_b

    def sample_posterior_mean(self, l1_id: int) -> float:
        """Returns mean of Beta distribution alpha / (alpha + beta) as deterministic sample."""
        a, b = self.posteriors.get(l1_id, (1.0, 1.0))
        return a / (a + b)
