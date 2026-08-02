"""
discovery.shadow.stream — Stream tap consumer (P0-10).
Taps cart.mutated events in near-line stream, runs core, emits metrics, writes NOTHING to cache/users.
"""

from typing import Dict, Any, List, Set
from discovery.core.types import CartContext, Candidate
from discovery.shadow.replay import run_shadow_decision
from discovery.core.events import InterruptEligibleEvent


class ShadowStreamTap:
    """Stream tap runner for Phase 0 shadow execution."""

    def __init__(self, store_pool_map: Dict[int, List[Candidate]]):
        self.store_pool_map = store_pool_map
        self.emitted_events: List[Dict[str, Any]] = []

    def handle_cart_mutated(
        self,
        ctx: CartContext,
        user_purchased_l1_ids: Set[int],
        suppressed_l1_ids: Set[int] = None,
    ) -> InterruptEligibleEvent:
        """
        Handles incoming cart.mutated stream payload.
        Executes discovery-core in shadow mode and emits metrics event.
        """
        if suppressed_l1_ids is None:
            suppressed_l1_ids = set()

        store_pool = self.store_pool_map.get(ctx.store_id, [])

        decision = run_shadow_decision(
            ctx=ctx,
            store_pool=store_pool,
            user_purchased_l1_ids=user_purchased_l1_ids,
            suppressed_l1_ids=suppressed_l1_ids,
        )

        # Convert drop histogram for event payload
        drop_reasons_summary = [
            {"filter_id": fid, "count": cnt} for fid, cnt in decision.drop_histogram.items()
        ]

        event = InterruptEligibleEvent(
            user_id=ctx.user_id,
            session_id=ctx.session_id,
            cart_id=ctx.cart_id,
            store_id=ctx.store_id,
            candidate_count=decision.candidates_in_count,
            drop_reasons=drop_reasons_summary,
        )

        self.emitted_events.append(event.model_dump())
        return event
