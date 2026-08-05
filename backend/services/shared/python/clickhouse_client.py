"""
ClickHouse Client — OLAP analytics for user behavior, training data, search funnel.

Usage:
    from clickhouse_client import get_clickhouse_client, ClickHouseClient
    ch = await get_clickhouse_client()
    await ch.insert_event("view", user_id="1", item_id="case-001")
    samples = await ch.get_training_samples(limit=100000)
"""
import asyncio
import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ClickHouseClient:
    """Async ClickHouse client for analytics and training data."""

    def __init__(self, host: str = "", port: int = 8123,
                 user: str = "default", password: str = "",
                 database: str = "shortdrama"):
        self.host = host or os.getenv("CLICKHOUSE_HOST", "clickhouse")
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self._client = None
        self._initialized = False

    async def _init(self):
        if self._initialized:
            return
        try:
            import httpx
            base = f"http://{self.host}:{self.port}"
            params = {"user": self.user, "database": self.database}
            if self.password:
                params["password"] = self.password
            self._client = httpx.AsyncClient(base_url=base, params=params, timeout=30.0)
            self._initialized = True
        except Exception:
            pass

    async def query(self, sql: str) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return rows as dicts."""
        await self._init()
        if not self._client:
            return []
        try:
            resp = await self._client.post("/", content=sql + " FORMAT JSONEachRow")
            if resp.status_code == 200:
                lines = resp.text.strip().split("\n")
                import json
                return [json.loads(line) for line in lines if line]
        except Exception as e:
            logger.debug(f"ClickHouse query failed: {e}")
        return []

    async def execute(self, sql: str):
        """Execute DDL/DML statement."""
        await self._init()
        if not self._client:
            return
        try:
            await self._client.post("/", content=sql)
        except Exception as e:
            logger.debug(f"ClickHouse execute failed: {e}")

    # ---- User Events ----

    async def insert_event(self, event_type: str, user_id: str = "",
                           item_id: str = "", query: str = "",
                           recall_source: str = "", position: int = 0,
                           dwell_ms: int = 0, session_id: str = "",
                           metadata: dict = None):
        """Insert a user behavior event."""
        import json
        sql = (
            f"INSERT INTO {self.database}.user_events "
            f"(event_type, user_id, item_id, query, recall_source, "
            f"position, dwell_ms, session_id, metadata) VALUES ("
            f"'{event_type}','{user_id}','{item_id}','{query}','{recall_source}',"
            f"{position},{dwell_ms},'{session_id}','{json.dumps(metadata or {}, ensure_ascii=False)}')"
        )
        await self.execute(sql)

    async def insert_events_batch(self, rows: List[tuple]):
        """Batch insert events for performance."""
        if not rows:
            return
        import json
        values = []
        for row in rows:
            evt = {
                "event_type": row[0], "user_id": row[1], "item_id": row[2],
                "query": row[3], "recall_source": row[4], "position": row[5],
                "dwell_ms": row[6], "session_id": row[7],
                "metadata": json.dumps(row[8] if len(row) > 8 else {}, ensure_ascii=False),
            }
            values.append(
                f"('{evt['event_type']}','{evt['user_id']}','{evt['item_id']}',"
                f"'{evt['query']}','{evt['recall_source']}',{evt['position']},"
                f"{evt['dwell_ms']},'{evt['session_id']}','{evt['metadata']}')"
            )
        sql = f"INSERT INTO {self.database}.user_events VALUES {','.join(values)}"
        await self.execute(sql)

    # ---- Search Funnel ----

    async def get_search_funnel(self, query: str = "",
                                 days: int = 7) -> Dict[str, Any]:
        """Get search funnel stats from materialized view."""
        cond = f"AND query = '{query}'" if query else ""
        sql = (
            f"SELECT sum(impressions) AS imp, sum(clicks) AS clk, "
            f"sum(unique_searchers) AS users "
            f"FROM {self.database}.search_funnel_hourly "
            f"WHERE date >= today() - {days} {cond}"
        )
        rows = await self.query(sql)
        if rows:
            r = rows[0]
            imp = int(r.get("imp", 0))
            clk = int(r.get("clk", 0))
            return {"impressions": imp, "clicks": clk,
                    "ctr": round(clk / max(imp, 1), 4), "users": int(r.get("users", 0))}
        return {"impressions": 0, "clicks": 0, "ctr": 0.0, "users": 0}

    # ---- LLM Usage ----

    async def insert_llm_usage(self, service: str, model: str, endpoint: str,
                               user_id: str, tokens_in: int, tokens_out: int,
                               duration_ms: int, cost_rmb: float, cache_hit: bool = False):
        await self.execute(
            f"INSERT INTO {self.database}.llm_usage VALUES ("
            f"now64(3),'{service}','{model}','{endpoint}','{user_id}',"
            f"{tokens_in},{tokens_out},{duration_ms},{cost_rmb},{1 if cache_hit else 0})"
        )

    async def get_cost_report(self, days: int = 7) -> List[Dict]:
        """Get LLM cost breakdown by service and model."""
        return await self.query(
            f"SELECT service_name, model_name, count() AS calls, "
            f"sum(tokens_in) AS tok_in, sum(tokens_out) AS tok_out, "
            f"sum(cost_rmb) AS total_cost, sum(cache_hit) AS cache_hits "
            f"FROM {self.database}.llm_usage "
            f"WHERE event_time >= now() - INTERVAL {days} DAY "
            f"GROUP BY service_name, model_name ORDER BY total_cost DESC"
        )

    # ---- Training Data ----

    async def insert_training_samples(self, samples: List[tuple]):
        """Insert pre-computed training samples."""
        if not samples:
            return
        values = []
        for user_id, item_id, label, features in samples:
            feat_str = "[" + ",".join(str(f) for f in features) + "]"
            values.append(f"('{user_id}','{item_id}',{label},{feat_str},'train')")
        sql = f"INSERT INTO {self.database}.training_samples VALUES {','.join(values)}"
        await self.execute(sql)

    async def get_training_samples(self, split: str = "train",
                                   limit: int = 100000) -> List[Dict]:
        """Get training samples from ClickHouse."""
        return await self.query(
            f"SELECT user_id, item_id, label, features "
            f"FROM {self.database}.training_samples "
            f"WHERE split = '{split}' "
            f"ORDER BY sample_time DESC LIMIT {limit}"
        )


# Global singleton
_clickhouse_client: Optional[ClickHouseClient] = None


async def get_clickhouse_client() -> ClickHouseClient:
    global _clickhouse_client
    if _clickhouse_client is None:
        _clickhouse_client = ClickHouseClient()
    return _clickhouse_client
