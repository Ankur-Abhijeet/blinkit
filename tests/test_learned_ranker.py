"""
tests/test_learned_ranker.py — Learned Ranker ML & IPW Test Suite.
§9 implementation-plan.md P4-3, P4-4, P4-7, P4-8: Asserts IPW training, p_add, p_repeat, and Thompson sampling.
"""

import pytest
from discovery.core.types import CartContext, CartItem, Candidate
from discovery.offline.features_job import extract_candidate_feature_vector
from discovery.offline.p_add_model import PAddModelPredictor
from discovery.offline.p_repeat_model import PRepeatModelPredictor
from discovery.offline.posteriors_job import ThompsonSamplingPosteriors
from discovery.core.scoring import score_candidates_v1


def test_ipw_p_add_training_and_prediction():
    predictor = PAddModelPredictor()

    features = {
        "cand_margin_pct": 0.30,
        "cand_velocity_30d": 40.0,
        "affinity_score": 0.8,
        "cand_complaint_rate": 0.01,
        "cart_item_count": 3.0,
    }

    p_add = predictor.predict_p_add(features)
    assert 0.0 < p_add < 1.0

    # IPW epoch simulation
    samples = [
        {"features": features, "label": 1, "exploration_prob": 0.2},
        {"features": features, "label": 0, "exploration_prob": 0.8},
    ]
    loss = predictor.train_ipw_epoch(samples)
    assert loss > 0.0


def test_p_repeat_prediction():
    predictor = PRepeatModelPredictor()
    features = {
        "user_tenure_days": 60.0,
        "user_completed_orders": 10.0,
        "cand_velocity_30d": 50.0,
        "cand_complaint_rate": 0.01,
    }
    p_repeat = predictor.predict_p_repeat(features)
    assert 0.0 < p_repeat < 1.0


def test_thompson_sampling_posteriors_update():
    ts = ThompsonSamplingPosteriors()
    new_a, new_b = ts.update_posterior(l1_id=20, adds=5, impressions=20)
    assert new_a == 6.0  # 1.0 prior + 5
    assert new_b == 16.0  # 1.0 prior + (20 - 5)

    sample = ts.sample_posterior_mean(l1_id=20)
    assert abs(sample - (6.0 / 22.0)) < 1e-4


def test_score_candidates_v1_learned_ranker():
    ctx = CartContext(
        user_id=1, session_id="s1", cart_id="c1", store_id=1, cart_subtotal_paise=25000,
        cart_items=[CartItem(sku_id=1, l1_id=10, l2_id=101, name="Milk", price_paise=5000)],
    )

    cand1 = Candidate(
        sku_id=101, l1_id=20, l2_id=201, name="Baby Wipes", pack="80s", price_paise=2000, mrp_paise=3000,
        margin_pct=0.30, velocity_30d=50, complaint_rate=0.01, available_qty=10
    )
    cand2 = Candidate(
        sku_id=102, l1_id=25, l2_id=251, name="Dog Food", pack="1kg", price_paise=5000, mrp_paise=6000,
        margin_pct=0.20, velocity_30d=20, complaint_rate=0.01, available_qty=10
    )

    p_add_map = {101: 0.20, 102: 0.10}
    p_repeat_map = {101: 0.50, 102: 0.30}

    scored = score_candidates_v1(ctx, [cand1, cand2], p_add_map, p_repeat_map)
    assert len(scored) == 2
    assert scored[0][0].sku_id == 101  # cand1 scores higher due to p_add and p_repeat
