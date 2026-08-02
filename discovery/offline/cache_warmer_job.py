"""
discovery.offline.cache_warmer_job — Cache Warmer Job.
§5.6.6 solution.md & §6 architecture.md: Pre-populates top ~50k rulebook decisions into cache.
"""

from typing import List, Dict
import time
from discovery.offline.rulebook_store import RulebookStore
from discovery.offline.a3_rulebook_job import A3CellRulebookEntry


def warm_decision_cache(
    rulebook_store: RulebookStore,
    top_cells: List[tuple[str, str]],
    target_cache: Dict[str, Any],
    now: Optional[float] = None,
) -> int:
    """
    Warms target decision cache with pre-computed rulebook decisions for high-frequency cells.
    Returns count of warmed cache keys.
    """
    if now is None:
        now = time.time()

    warmed_count = 0
    for state_id, cart_sig in top_cells:
        entry = rulebook_store.lookup_a3_cell_entry(state_id, cart_sig)
        if entry:
            cache_key = f"disc:llm:{state_id}:{cart_sig}"
            target_cache[cache_key] = (entry.model_dump(), now + 604800.0)  # 7-day TTL
            warmed_count += 1
    return warmed_count
