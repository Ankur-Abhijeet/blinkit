from typing import List, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict
import uuid


class CartItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    sku_id: int
    l1_id: int
    l2_id: int
    name: str
    price_paise: int


class CartContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: int
    session_id: str
    cart_id: str
    store_id: int
    cart_subtotal_paise: int  # Explicitly post-discount, pre-delivery-fee
    cart_items: List[CartItem] = Field(default_factory=list)
    tenure_days: int = 30
    completed_orders: int = 5
    city_tier: int = 1

    @property
    def item_count(self) -> int:
        return len(self.cart_items)

    @property
    def cart_l1_ids(self) -> set[int]:
        return {item.l1_id for item in self.cart_items}

    @property
    def cart_l2_ids(self) -> set[int]:
        return {item.l2_id for item in self.cart_items}

    @property
    def cart_sku_ids(self) -> set[int]:
        return {item.sku_id for item in self.cart_items}

    @property
    def cart_sig(self) -> str:
        """Returns sorted L1 category set signature + subtotal band."""
        sorted_l1s = ",".join(str(i) for i in sorted(self.cart_l1_ids))
        subtotal_band = self.cart_subtotal_paise // 15000  # ₹150 bands
        return f"l1:[{sorted_l1s}]_band:{subtotal_band}"


class Candidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    sku_id: int
    l1_id: int
    l2_id: int
    name: str
    pack: str
    price_paise: int
    mrp_paise: int
    margin_pct: float
    velocity_30d: int
    complaint_rate: float
    available_qty: int
    volume_ml: int = 0
    weight_g: int = 0
    is_excluded_l1: bool = False
    generation_source: str = "CG1"
    store_age_days: int = 180  # For store-launch exemption (EC-P5-02)


class DropReason(BaseModel):
    model_config = ConfigDict(frozen=True)

    sku_id: int
    filter_id: str
    reason: str


class Decision(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: int
    cart_hash: str
    store_id: int
    experiment_arm: str = "B"
    served_candidate: Optional[Candidate] = None
    reason_code: str = "GENERIC"
    reason_line: str = ""
    copy_source: str = "template"
    candidates_in_count: int = 0
    candidates_eligible_count: int = 0
    drop_reasons: List[DropReason] = Field(default_factory=list)
    drop_histogram: Dict[str, int] = Field(default_factory=dict)
