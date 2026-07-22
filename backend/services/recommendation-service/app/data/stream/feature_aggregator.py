"""Sliding-Window Feature Aggregator — Flink-style real-time feature computation.

工业界对标: Flink SQL 滑动窗口 → Redis/HBase → Feature Store Serving

Window sizes:
  5min:  实时CTR, 实时热度
  1h:    短期兴趣, session特征
  6h:    中期趋势
  24h:   日活统计
  7d:    周趋势 (from ClickHouse)

Features computed:
  - realtime_ctr: clicks / impressions (per user, per recall_source)
  - dwell_avg: 平均停留时长
  - hot_score_5min: 5分钟内内容热度 (like * 3 + view)
  - interest_shift: 最近1h vs 24h的tag分布变化
  - active_users_1h: 1小时活跃用户数 (全局)
"""
import logging
import time
from collections import defaultdict
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class Window:
    """A single time window bucket. Stores events and computes aggregates."""

    def __init__(self, max_events: int = 10000):
        self.events: List[Dict] = []
        self.max_events = max_events
        # Aggregates
        self._counts: Dict[str, int] = defaultdict(int)  # event_type → count
        self._dwell_sum: float = 0.0
        self._like_count: int = 0
        self._view_count: int = 0
        self._user_set: set = set()

    def add(self, event: dict):
        self.events.append(event)
        if len(self.events) > self.max_events:
            self.events.pop(0)

        etype = event.get("event_type", "")
        self._counts[etype] += 1
        self._user_set.add(event.get("user_id", ""))

        if etype == "like":
            self._like_count += 1
            self._view_count += 1
        elif etype in ("click", "impression"):
            self._view_count += 1

        dwell = event.get("dwell_ms", 0)
        if dwell > 0:
            self._dwell_sum += dwell

    @property
    def ctr(self) -> float:
        """Click-through rate within this window."""
        views = self._counts.get("impression", 0) + self._counts.get("click", 0)
        clicks = self._counts.get("click", 0) + self._counts.get("like", 0)
        return clicks / max(views, 1)

    @property
    def engagement_rate(self) -> float:
        return self._like_count / max(self._view_count, 1)

    @property
    def avg_dwell_ms(self) -> float:
        n = self._counts.get("click", 0) + self._counts.get("like", 0)
        return self._dwell_sum / max(n, 1)

    @property
    def unique_users(self) -> int:
        return len(self._user_set)

    @property
    def total_events(self) -> int:
        return len(self.events)


class RealTimeFeatureSet:
    """Complete real-time feature snapshot for a user at request time."""

    def __init__(self):
        self.realtime_ctr: float = 0.0
        self.realtime_ctr_1h: float = 0.0
        self.dwell_avg_5min: float = 0.0
        self.hot_score_5min: float = 0.0
        self.interest_shift: float = 0.0   # 1h vs 24h tag cosine similarity
        self.active_users_1h: int = 0
        self.user_views_1h: int = 0
        self.user_likes_1h: int = 0
        self.user_views_24h: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "realtime_ctr": round(self.realtime_ctr, 4),
            "realtime_ctr_1h": round(self.realtime_ctr_1h, 4),
            "dwell_avg_5min": round(self.dwell_avg_5min, 1),
            "hot_score_5min": round(self.hot_score_5min, 4),
            "interest_shift": round(self.interest_shift, 4),
            "active_users_1h": self.active_users_1h,
            "user_views_1h": self.user_views_1h,
            "user_likes_1h": self.user_likes_1h,
            "user_views_24h": self.user_views_24h,
        }


class WindowAggregator:
    """Flink-style sliding window feature aggregator.

    Maintains multiple time windows and computes features on demand.
    Production: replace with Flink SQL job using Kafka source.
    Development: in-memory windows with Redis backup.
    """

    def __init__(self, redis_client=None):
        self.redis = redis_client
        self._windows: Dict[str, Window] = {
            "5min": Window(max_events=2000),
            "1h": Window(max_events=50000),
            "6h": Window(max_events=200000),
            "24h": Window(max_events=500000),
        }
        self._last_prune: Dict[str, float] = defaultdict(lambda: time.time())

    def add_event(self, event: dict):
        """Add an event to all relevant windows."""
        for window in self._windows.values():
            window.add(event)

    def get_features(self, user_id: str) -> RealTimeFeatureSet:
        """Compute real-time features for a user."""
        fs = RealTimeFeatureSet()

        w5 = self._windows["5min"]
        w1h = self._windows["1h"]
        w24h = self._windows["24h"]

        fs.realtime_ctr = w5.ctr
        fs.realtime_ctr_1h = w1h.ctr
        fs.dwell_avg_5min = w5.avg_dwell_ms
        fs.hot_score_5min = (w5._like_count * 3 + w5._view_count) / max(w5.total_events, 1)
        fs.active_users_1h = w1h.unique_users

        # Per-user counts (from window events)
        for e in w1h.events:
            if e.get("user_id") == user_id:
                if e.get("event_type") in ("click", "impression"):
                    fs.user_views_1h += 1
                if e.get("event_type") == "like":
                    fs.user_likes_1h += 1
        for e in w24h.events:
            if e.get("user_id") == user_id and e.get("event_type") in ("click", "impression"):
                fs.user_views_24h += 1

        # Interest shift: compare 1h vs 24h tag distribution
        if w1h.total_events > 50 and w24h.total_events > 200:
            # Simplified: compare event type distribution
            overlap = sum(
                min(w1h._counts.get(k, 0), w24h._counts.get(k, 0))
                for k in set(w1h._counts) | set(w24h._counts)
            )
            total = max(w1h.total_events + w24h.total_events, 1)
            fs.interest_shift = 1.0 - overlap / total

        return fs

    def prune_windows(self):
        """Clean up old events beyond window size (called periodically)."""
        now = time.time()
        window_seconds = {"5min": 300, "1h": 3600, "6h": 21600, "24h": 86400}

        for name, window in self._windows.items():
            cutoff = now - window_seconds[name]
            # Remove events older than the window
            window.events = [e for e in window.events
                            if e.get("event_time", 0) > cutoff]
            # Recompute aggregates
            window._counts.clear()
            window._user_set.clear()
            window._dwell_sum = 0.0
            window._like_count = 0
            window._view_count = 0
            for e in window.events:
                window.add(e)
            self._last_prune[name] = now
