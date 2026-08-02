"""
tests/test_rulebook_store.py — Rulebook Store Versioning & Arm C Applier Integration.
"""

import pytest
from discovery.offline.rulebook_store import RulebookStore
from discovery.offline.a3_rulebook_job import generate_a3_cell_rulebook
from discovery.offline.a2_rulebook_job import HouseholdStateProfile
from discovery.worker.nearline_worker import NearlineWorkerEngine
from discovery.core.types import CartContext, CartItem, Candidate
from discovery.config.flags import FeatureFlags


def test_rulebook_store_versioning_and_rollback():
    store = RulebookStore()

    entry_v1 = generate_a3_cell_rulebook(
        state_id="hh_01",
        cart_sig="sig_01",
        candidate_l1_ids=[20, 25],
        affinity_reason_map={20: "LIFE_STAGE"},
        raw_copy_lines={20: "Goes with wipes"},
    )
    store.publish_a3_rulebook([entry_v1], version="v1.0")
    assert store.active_version == "v1.0"
    assert store.lookup_a3_cell_entry("hh_01", "sig_01").copy_bank_map[20] == "Goes with wipes"

    entry_v2 = generate_a3_cell_rulebook(
        state_id="hh_01",
        cart_sig="sig_01",
        candidate_l1_ids=[25, 20],
        affinity_reason_map={25: "COMPLEMENT"},
        raw_copy_lines={25: "New pet essential"},
    )
    store.publish_a3_rulebook([entry_v2], version="v2.0")
    assert store.active_version == "v2.0"
    assert store.lookup_a3_cell_entry("hh_01", "sig_01").copy_bank_map[25] == "New pet essential"

    # Rollback to v1.0
    assert store.rollback_to_version("v1.0") is True
    assert store.active_version == "v1.0"
    assert store.lookup_a3_cell_entry("hh_01", "sig_01").copy_bank_map[20] == "Goes with wipes"


def test_arm_c_rulebook_hit_vs_cold_cell_fallback():
    store = RulebookStore()

    # Save A2 profile for user 888
    profile = HouseholdStateProfile(user_id=888, infant_present=True)
    store.save_a2_profile(profile)

    ctx = CartContext(
        user_id=888,
        session_id="s888",
        cart_id="c888",
        store_id=1,
        cart_subtotal_paise=25000,
        cart_items=[CartItem(sku_id=1, l1_id=10, l2_id=101, name="Milk", price_paise=5000)],
    )

    # Publish rulebook entry for (state_id, cart_sig)
    entry = generate_a3_cell_rulebook(
        state_id=profile.state_id,
        cart_sig=ctx.cart_sig,
        candidate_l1_ids=[20, 25],
        affinity_reason_map={20: "LIFE_STAGE", 25: "COMPLEMENT"},
        raw_copy_lines={20: "Goes with the wipes you buy", 25: "Pet care essential"},
    )
    store.publish_a3_rulebook([entry], version="v1.0")

    flags = FeatureFlags({
        "discovery.enabled": True,
        "discovery.slot_a.enabled": True,
        "discovery.a3.enabled": True,
        "discovery.arm_split": {"A": 0, "B": 0, "C": 100},  # Force Arm C
    })

    worker = NearlineWorkerEngine(flags=flags, rulebook_store=store)

    candidate_pool = [
        Candidate(sku_id=2001, l1_id=20, l2_id=2001, name="Baby Wipes", pack="80s", price_paise=2000, mrp_paise=3000, margin_pct=0.3, velocity_30d=50, complaint_rate=0.01, available_qty=10),
        Candidate(sku_id=2501, l1_id=25, l2_id=2501, name="Dog Treats", pack="100g", price_paise=1500, mrp_paise=2000, margin_pct=0.3, velocity_30d=50, complaint_rate=0.01, available_qty=10),
    ]

    # Rulebook HIT test
    decision_hit = worker.process_cart_event(ctx, candidate_pool, user_purchased_l1_ids={10})
    assert decision_hit.experiment_arm == "C"
    assert decision_hit.served_candidate is not None
    assert decision_hit.copy_source == "llm"
    assert decision_hit.reason_line == "Goes with the wipes you buy"

    # Cold Cell / Rulebook MISS test (using user 999 with no published rulebook cell)
    ctx_cold = CartContext(
        user_id=999,
        session_id="s999",
        cart_id="c999",
        store_id=1,
        cart_subtotal_paise=25000,
        cart_items=[CartItem(sku_id=1, l1_id=10, l2_id=101, name="Milk", price_paise=5000)],
    )
    decision_cold = worker.process_cart_event(ctx_cold, candidate_pool, user_purchased_l1_ids={10})
    assert decision_cold.experiment_arm == "C"
    assert decision_cold.served_candidate is not None
    assert decision_cold.copy_source == "template"  # Cold cell fallback to Arm B template
