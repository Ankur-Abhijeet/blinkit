"""
tests/test_api_slot.py — Integration tests for GET /v1/discovery/slot endpoint.
"""

import pytest
from fastapi.testclient import TestClient
from discovery.api.app import create_app
from discovery.worker.nearline_worker import NearlineWorkerEngine
from discovery.core.types import CartContext, CartItem, Candidate
from discovery.config.flags import FeatureFlags


@pytest.fixture
def worker_engine():
    flags = FeatureFlags({"discovery.enabled": True, "discovery.slot_a.enabled": True})
    engine = NearlineWorkerEngine(flags=flags)
    return engine


@pytest.fixture
def test_client(worker_engine):
    app = create_app(worker_engine=worker_engine)
    return TestClient(app)


def test_api_healthz(test_client):
    res = test_client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_api_slot_cache_hit(test_client, worker_engine):
    ctx = CartContext(
        user_id=555,
        session_id="s555",
        cart_id="c555",
        store_id=1,
        cart_subtotal_paise=25000,
        cart_items=[CartItem(sku_id=1, l1_id=10, l2_id=101, name="Milk", price_paise=5000)],
    )
    store_pool = [
        Candidate(
            sku_id=999,
            l1_id=20,
            l2_id=201,
            name="Diaper Cream",
            pack="50g",
            price_paise=2500,
            mrp_paise=3000,
            margin_pct=0.3,
            velocity_30d=50,
            complaint_rate=0.01,
            available_qty=10,
        )
    ]

    # Populate near-line worker cache
    decision = worker_engine.process_cart_event(ctx, store_pool, user_purchased_l1_ids={10})
    assert decision.served_candidate is not None

    # Call API prefetch endpoint
    res = test_client.get(
        f"/v1/discovery/slot?user_id=555&cart_id=c555&cart_hash={ctx.cart_sig}&slot=A"
    )
    assert res.status_code == 200
    data = res.json()
    assert data["sku_id"] == 999
    assert data["product_name"] == "Diaper Cream"
    assert data["price_paise"] == 2500


def test_api_slot_cache_miss_returns_204(test_client):
    # Miss on unknown cart_hash -> 204 No Content
    res = test_client.get("/v1/discovery/slot?user_id=555&cart_id=c555&cart_hash=unknown_hash&slot=A")
    assert res.status_code == 204


def test_api_slot_disabled_flag_returns_204(worker_engine):
    # Turn off discovery flag
    worker_engine.flags.update("discovery.enabled", False)
    app = create_app(worker_engine=worker_engine)
    client = TestClient(app)

    res = client.get("/v1/discovery/slot?user_id=555&cart_id=c555&cart_hash=any_hash&slot=A")
    assert res.status_code == 204
