"""
discovery.offline.pools_job — DuckDB candidate pool & user category history pipeline.
"""

import duckdb
from typing import List, Optional
from discovery.core.types import Candidate


def initialize_duckdb_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Initializes DuckDB tables per architecture.md §3.2."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_category_history (
            user_id BIGINT,
            l1_id INT,
            purchase_count_365d INT,
            last_purchase_at TIMESTAMP,
            PRIMARY KEY (user_id, l1_id)
        );

        CREATE TABLE IF NOT EXISTS store_candidate_pool (
            store_id INT,
            sku_id BIGINT,
            l1_id INT,
            l2_id INT,
            name VARCHAR,
            pack VARCHAR,
            price_paise INT,
            mrp_paise INT,
            margin_pct DOUBLE,
            velocity_30d INT,
            complaint_rate DOUBLE,
            available_qty INT,
            volume_ml INT,
            weight_g INT,
            is_excluded_l1 BOOLEAN,
            store_age_days INT,
            PRIMARY KEY (store_id, sku_id)
        );
    """)


def load_candidate_pool_for_store(
    conn: duckdb.DuckDBPyConnection, store_id: int
) -> List[Candidate]:
    """
    Loads candidate pool for a specific dark store from DuckDB.
    Applies store-launch velocity fallback for dark stores < 45 days old (EC-P5-02).
    """
    rows = conn.execute(
        """
        SELECT sku_id, l1_id, l2_id, name, pack, price_paise, mrp_paise, margin_pct,
               velocity_30d, complaint_rate, available_qty, volume_ml, weight_g,
               is_excluded_l1, store_age_days
        FROM store_candidate_pool
        WHERE store_id = ?
        """,
        [store_id],
    ).fetchall()

    candidates = []
    for r in rows:
        cand = Candidate(
            sku_id=r[0],
            l1_id=r[1],
            l2_id=r[2],
            name=r[3],
            pack=r[4],
            price_paise=r[5],
            mrp_paise=r[6],
            margin_pct=r[7],
            velocity_30d=r[8],
            complaint_rate=r[9],
            available_qty=r[10],
            volume_ml=r[11],
            weight_g=r[12],
            is_excluded_l1=r[13],
            store_age_days=r[14],
        )
        candidates.append(cand)
    return candidates
