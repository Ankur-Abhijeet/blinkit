"""
discovery.worker.nearline_worker — Near-line decision worker engine.
§5 architecture.md: Applies core logic, writes decision cache (TTL 15 min) and decision_log.
"""

from typing import Dict, List, Set, Optional, Any
import time
from discovery.core.types import CartContext, Candidate, Decision, DropReason
from discovery.core.candidates import generate_candidates
from discovery.core.filters import filter_candidates
from discovery.core.scoring import score_candidates_v0
from discovery.core.arbitration import arbitrate_slots
from discovery.config.flags import FeatureFlags, get_user_experiment_arm
from discovery.worker.suppression import SuppressionManager
from discovery.offline.rulebook_store import RulebookStore
from discovery.offline.a4_rules_job import evaluate_a4_safety_rules


class NearlineWorkerEngine:
    """Near-line async worker orchestrating decision computation, rulebook applier, and decision cache writes."""

    def __init__(
        self,
        flags: Optional[FeatureFlags] = None,
        suppression_mgr: Optional[SuppressionManager] = None,
        rulebook_store: Optional[RulebookStore] = None,
    ):
        self.flags = flags or FeatureFlags()
        self.suppression_mgr = suppression_mgr or SuppressionManager()
        self.rulebook_store = rulebook_store or RulebookStore()
        # In-memory Decision Cache mock (Key: f"disc:dec:{user_id}:{cart_hash}" -> (Decision, expiry_timestamp))
        self.decision_cache: Dict[str, tuple[Decision, float]] = {}
        # Append-only Decision Log
        self.decision_log: List[Decision] = []

    def get_cached_decision(self, user_id: int, cart_hash: str, now: Optional[float] = None) -> Optional[Decision]:
        """Reads decision from KV cache. Returns None if miss or expired."""
        if now is None:
            now = time.time()
        cache_key = f"disc:dec:{user_id}:{cart_hash}"
        item = self.decision_cache.get(cache_key)
        if not item:
            return None
        decision, expiry = item
        if now > expiry:
            del self.decision_cache[cache_key]
            return None
        return decision

    def process_cart_event(
        self,
        ctx: CartContext,
        store_pool: List[Candidate],
        user_purchased_l1_ids: Set[int],
        blocked_safety_skus: Optional[Set[int]] = None,
        now: Optional[float] = None,
    ) -> Decision:
        """
        Executes near-line decision computation on cart mutation/view.
        Applies flags, arm assignment, filtering, scoring, rulebook applier, and caches result.
        """
        if now is None:
            now = time.time()

        # 1. Evaluate Feature Flags
        if not self.flags.is_enabled("discovery.enabled") or not self.flags.is_enabled("discovery.slot_a.enabled"):
            return self._build_empty_decision(ctx, "flags_disabled")

        # 2. Experiment Arm Assignment
        arm_split = self.flags.get("discovery.arm_split", {"A": 34, "B": 33, "C": 33})
        arm = get_user_experiment_arm(ctx.user_id, arm_split)

        if arm in ("EXCLUDED", "HOLDOUT", "A"):
            # Control A or Holdout -> empty decision (render normal cart)
            return self._build_empty_decision(ctx, f"arm_{arm}", arm=arm)

        # 3. Suppression & Fatigue Counters
        suppressed_l1s = self.suppression_mgr.get_suppressed_l1_ids(ctx.user_id, now=now)
        slot_a_impressions_7d = self.suppression_mgr.get_impressions_7d_count(ctx.user_id, now=now)

        # 4. Candidate Generation & Filtering
        candidates_in = generate_candidates(ctx, store_pool, user_purchased_l1_ids)

        eligible_candidates, drop_reasons = filter_candidates(
            ctx=ctx,
            candidates=candidates_in,
            user_purchased_l1_ids=user_purchased_l1_ids,
            suppressed_l1_ids=suppressed_l1s,
            user_slot_a_impressions_7d=slot_a_impressions_7d,
            blocked_safety_skus=blocked_safety_skus,
        )

        # Apply F13 / A4 contextual safety rules dynamically
        if self.flags.is_enabled("discovery.a4.enabled"):
            safe_candidates = []
            for cand in eligible_candidates:
                is_allowed, block_reason = evaluate_a4_safety_rules(ctx, cand)
                if is_allowed:
                    safe_candidates.append(cand)
                else:
                    drop_reasons.append(DropReason(sku_id=cand.sku_id, filter_id="F13", reason=block_reason or "F13 block"))
            eligible_candidates = safe_candidates

        histogram: Dict[str, int] = {}
        for dr in drop_reasons:
            histogram[dr.filter_id] = histogram.get(dr.filter_id, 0) + 1

        served_cand = None
        reason_code = "GENERIC"
        reason_line = ""
        copy_source = "template"

        if eligible_candidates:
            # 5. Arm C Rulebook Applier vs Arm B Deterministic Order
            rulebook_hit = False
            if arm == "C" and self.flags.is_enabled("discovery.a3.enabled"):
                profile = self.rulebook_store.get_a2_profile(ctx.user_id)
                state_id = profile.state_id if profile else "default"
                cell_entry = self.rulebook_store.lookup_a3_cell_entry(state_id, ctx.cart_sig)

                if cell_entry:
                    # Rulebook Hit: Sort candidates using cell preferred category order
                    pref_order_map = {l1: idx for idx, l1 in enumerate(cell_entry.preferred_category_order)}
                    eligible_candidates.sort(key=lambda c: pref_order_map.get(c.l1_id, 999))
                    served_cand = eligible_candidates[0]
                    reason_code = cell_entry.reason_code_map.get(served_cand.l1_id, "COMPLEMENT")
                    reason_line = cell_entry.copy_bank_map.get(served_cand.l1_id, f"New for you in {served_cand.name}")
                    copy_source = "llm"
                    rulebook_hit = True

            if not rulebook_hit:
                # Cold cell / Rulebook miss / Arm B -> Fall back to Arm B deterministic order
                scored = score_candidates_v0(eligible_candidates)
                top_cand, _ = scored[0]
                served_cand = top_cand
                reason_code = "COMPLEMENT"
                reason_line = f"New for you in {top_cand.name}"
                copy_source = "template"

        decision = Decision(
            user_id=ctx.user_id,
            cart_hash=ctx.cart_sig,
            store_id=ctx.store_id,
            experiment_arm=arm,
            served_candidate=served_cand,
            reason_code=reason_code,
            reason_line=reason_line,
            copy_source=copy_source,
            candidates_in_count=len(candidates_in),
            candidates_eligible_count=len(eligible_candidates),
            drop_reasons=drop_reasons,
            drop_histogram=histogram,
        )

        # 6. Cache Decision Slot A (TTL = 15 minutes = 900s)
        cache_key_a = f"disc:dec:{ctx.user_id}:{ctx.cart_sig}"
        self.decision_cache[cache_key_a] = (decision, now + 900.0)

        # 7. Multi-Slot Arbitration for Slot B
        decision_b = arbitrate_slots(ctx, eligible_candidates, decision)
        cache_key_b = f"disc:dec:{ctx.user_id}:{ctx.cart_sig}:slot_b"
        self.decision_cache[cache_key_b] = (decision_b, now + 900.0)

        # 8. Append to Decision Log
        self.decision_log.append(decision)
        if decision_b.served_candidate:
            self.decision_log.append(decision_b)

        return decision

    def _build_empty_decision(self, ctx: CartContext, reason: str, arm: str = "A") -> Decision:
        return Decision(
            user_id=ctx.user_id,
            cart_hash=ctx.cart_sig,
            store_id=ctx.store_id,
            experiment_arm=arm,
            served_candidate=None,
            reason_code="NONE",
            reason_line="",
            candidates_in_count=0,
            candidates_eligible_count=0,
        )
