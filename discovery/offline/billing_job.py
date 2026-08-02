"""
discovery.offline.billing_job — CPVT (Cost-Per-Verified-Trial) Billing Pipeline.
§11 implementation-plan.md P6-4: Emits brand billing audit logs on verified trial adds.
"""

from typing import Dict, Any, List, Optional
import time
from pydantic import BaseModel, Field


class CPVTBillingRecord(BaseModel):
    record_id: str
    brand_id: int
    sku_id: int
    user_id: int
    cart_id: str
    bid_paise: int
    timestamp: float = Field(default_factory=time.time)


class CPVTBillingPipeline:
    """Processes verified trial add events and generates billable audit log records."""

    def __init__(self):
        self.billing_ledger: List[CPVTBillingRecord] = []

    def record_verified_trial_add(
        self,
        brand_id: int,
        sku_id: int,
        user_id: int,
        cart_id: str,
        bid_paise: int,
        now: Optional[float] = None,
    ) -> CPVTBillingRecord:
        """Emits billable CPVT invoice record for brand."""
        if now is None:
            now = time.time()

        record = CPVTBillingRecord(
            record_id=f"cpvt_{brand_id}_{user_id}_{int(now)}",
            brand_id=brand_id,
            sku_id=sku_id,
            user_id=user_id,
            cart_id=cart_id,
            bid_paise=bid_paise,
            timestamp=now,
        )
        self.billing_ledger.append(record)
        return record

    def compute_brand_invoice_summary(self, brand_id: int) -> Dict[str, Any]:
        """Calculates total billable trial conversions and revenue in rupees for a brand."""
        brand_records = [r for r in self.billing_ledger if r.brand_id == brand_id]
        total_trials = len(brand_records)
        total_revenue_rupees = sum(r.bid_paise for r in brand_records) / 100.0

        return {
            "brand_id": brand_id,
            "total_verified_trials": total_trials,
            "total_revenue_rupees": round(total_revenue_rupees, 2),
        }
