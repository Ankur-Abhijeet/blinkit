"""
discovery.core.events — Event Schema definitions (§7 solution.md & P0-11).
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class BaseEvent(BaseModel):
    user_id: int
    session_id: str
    cart_id: str
    store_id: int
    experiment_arm: str = "B"
    ranker_version: str = "v0"
    timestamp: float = 0.0


class InterruptEligibleEvent(BaseEvent):
    """Fires even when nothing renders. The primary debugging surface."""
    event_type: str = "interrupt_eligible"
    candidate_count: int
    drop_reasons: List[Dict[str, Any]]  # List of {filter_id, count}


class InterruptImpressionEvent(BaseEvent):
    """Fires on impression render. Denominator for CTR and FPNC attribution."""
    event_type: str = "interrupt_impression"
    slot: str  # Slot A or Slot B
    sku_id: int
    l1_category: int
    score: float
    is_exploration: bool
    price_paise: int
    cart_subtotal_paise: int
    reason_code: str
    copy_source: str  # llm | template
    llm_rank: Optional[int] = None
    deterministic_rank: Optional[int] = None


class LLMRerankEvent(BaseEvent):
    """A3 model performance and Kendall-tau reorder distance."""
    event_type: str = "llm_rerank"
    model_id: str
    cache_hit: bool
    latency_ms: float
    input_tokens: int
    output_tokens: int
    reorder_distance: float


class LLMRejectEvent(BaseEvent):
    """Validator rejections. Rising rate signals prompt/model drift."""
    event_type: str = "llm_reject"
    stage: str  # A1 | A2 | A3 | A4
    reason: str  # unknown_id | schema | denylist | timeout | added_id
    fell_back_to: str


class SafetyBlockEvent(BaseEvent):
    """F13 contextual safety blocks."""
    event_type: str = "safety_block"
    cart_signature: str
    candidate_l2: int
    reason_code: str


class InterruptAddEvent(BaseEvent):
    """Primary conversion event."""
    event_type: str = "interrupt_add"
    sku_id: int
    l1_category: int
    price_paise: int
    time_to_add_ms: float


class InterruptDismissEvent(BaseEvent):
    """Negative signal for ranker."""
    event_type: str = "interrupt_dismiss"
    sku_id: int
    reason_code: str


class FirstPurchaseNewCategoryEvent(BaseEvent):
    """Goal metric event."""
    event_type: str = "first_purchase_new_category"
    l1_category: int
    attributed_slot: Optional[str] = None
    days_since_impression: Optional[int] = None
