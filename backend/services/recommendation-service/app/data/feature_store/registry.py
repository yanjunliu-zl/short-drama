"""Feature Registry — 统一特征定义 (Feast FeatureView 对标)。

工业界对标: Feast FeatureRepo → FeatureView → FeatureService

特征分类:
  - user_static: 用户静态画像 (注册时间, 偏好, 历史总量)
  - user_realtime: 用户实时特征 (最近1h/6h/24h行为, CTR, dwell)
  - user_sequence: 用户行为序列 (DIN输入的最近50个item embedding)
  - item_static: 内容静态特征 (类型, 标签, 作者, 发布时间)
  - item_dynamic: 内容动态特征 (实时热度, 实时CTR, 最近N天趋势)
  - context: 上下文特征 (时间, 设备, 网络, session)
  - cross: 交叉特征 (用户tag × item tag, 用户类型 × 内容类型)

所有特征定义在此注册，保证在线/离线一致性。
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class FeatureType(str, Enum):
    FLOAT = "float"
    INT = "int"
    STRING = "string"
    CATEGORICAL = "categorical"
    SEQUENCE = "sequence"
    EMBEDDING = "embedding"


class FeatureDomain(str, Enum):
    USER = "user"
    ITEM = "item"
    CONTEXT = "context"
    CROSS = "cross"


@dataclass
class FeatureDefinition:
    """Single feature definition — name, type, source, refresh policy."""
    name: str
    dtype: FeatureType
    domain: FeatureDomain
    description: str = ""
    online_store: str = "redis"        # Where to serve online
    offline_store: str = "clickhouse"  # Where to store for training
    refresh_cadence: str = "realtime"  # realtime / hourly / daily
    default_value: Any = 0.0
    tags: List[str] = field(default_factory=list)


# ── Complete Feature Registry ──

class FeatureRegistry:
    """Unified feature catalog — single source of truth for all features."""

    FEATURES: List[FeatureDefinition] = [
        # ===== User Static =====
        FeatureDefinition("user_total_views", FeatureType.INT, FeatureDomain.USER,
                          "用户历史总浏览数", refresh_cadence="hourly", default_value=0),
        FeatureDefinition("user_total_likes", FeatureType.INT, FeatureDomain.USER,
                          "用户历史总点赞数", refresh_cadence="hourly", default_value=0),
        FeatureDefinition("user_total_shares", FeatureType.INT, FeatureDomain.USER,
                          "用户历史总分享数", refresh_cadence="hourly", default_value=0),
        FeatureDefinition("user_tag_diversity", FeatureType.INT, FeatureDomain.USER,
                          "用户浏览过的独特标签数", refresh_cadence="daily", default_value=0),
        FeatureDefinition("user_favorite_genre", FeatureType.CATEGORICAL, FeatureDomain.USER,
                          "用户最偏好类型", refresh_cadence="daily", default_value=""),
        FeatureDefinition("user_favorite_tags", FeatureType.SEQUENCE, FeatureDomain.USER,
                          "用户偏好标签top-5", refresh_cadence="daily", default_value=[]),
        FeatureDefinition("user_favorite_authors", FeatureType.SEQUENCE, FeatureDomain.USER,
                          "用户偏好作者top-3", refresh_cadence="daily", default_value=[]),
        FeatureDefinition("user_recency_days", FeatureType.INT, FeatureDomain.USER,
                          "距上次活跃天数", refresh_cadence="realtime", default_value=999),
        FeatureDefinition("user_preferred_hour", FeatureType.INT, FeatureDomain.USER,
                          "用户活跃高峰时段(0-23)", refresh_cadence="hourly", default_value=12),

        # ===== User Realtime =====
        FeatureDefinition("user_realtime_ctr", FeatureType.FLOAT, FeatureDomain.USER,
                          "用户5分钟实时CTR", refresh_cadence="realtime", default_value=0.0),
        FeatureDefinition("user_ctr_1h", FeatureType.FLOAT, FeatureDomain.USER,
                          "用户1小时CTR", refresh_cadence="realtime", default_value=0.0),
        FeatureDefinition("user_views_1h", FeatureType.INT, FeatureDomain.USER,
                          "用户1小时浏览数", refresh_cadence="realtime", default_value=0),
        FeatureDefinition("user_likes_1h", FeatureType.INT, FeatureDomain.USER,
                          "用户1小时点赞数", refresh_cadence="realtime", default_value=0),
        FeatureDefinition("user_views_24h", FeatureType.INT, FeatureDomain.USER,
                          "用户24小时浏览数", refresh_cadence="realtime", default_value=0),
        FeatureDefinition("user_dwell_avg_5min", FeatureType.FLOAT, FeatureDomain.USER,
                          "用户5分钟平均停留时长(ms)", refresh_cadence="realtime", default_value=0.0),
        FeatureDefinition("user_is_active_session", FeatureType.INT, FeatureDomain.USER,
                          "当前是否活跃session(5min)", refresh_cadence="realtime", default_value=0),

        # ===== User Sequence =====
        FeatureDefinition("user_behavior_sequence", FeatureType.SEQUENCE, FeatureDomain.USER,
                          "用户最近50个item embedding (DIN输入)", "redis", "clickhouse", "realtime", []),
        FeatureDefinition("user_search_history", FeatureType.SEQUENCE, FeatureDomain.USER,
                          "用户最近搜索query", refresh_cadence="realtime", default_value=[]),

        # ===== Item Static =====
        FeatureDefinition("item_genre", FeatureType.CATEGORICAL, FeatureDomain.ITEM,
                          "内容类型", refresh_cadence="daily", default_value=""),
        FeatureDefinition("item_tags", FeatureType.SEQUENCE, FeatureDomain.ITEM,
                          "内容标签", refresh_cadence="daily", default_value=[]),
        FeatureDefinition("item_author", FeatureType.CATEGORICAL, FeatureDomain.ITEM,
                          "内容作者", refresh_cadence="daily", default_value=""),
        FeatureDefinition("item_created_days", FeatureType.INT, FeatureDomain.ITEM,
                          "内容发布天数", refresh_cadence="hourly", default_value=30),

        # ===== Item Dynamic =====
        FeatureDefinition("item_realtime_ctr", FeatureType.FLOAT, FeatureDomain.ITEM,
                          "内容5分钟实时CTR", refresh_cadence="realtime", default_value=0.0),
        FeatureDefinition("item_hot_score_5min", FeatureType.FLOAT, FeatureDomain.ITEM,
                          "内容5分钟热度分", refresh_cadence="realtime", default_value=0.0),
        FeatureDefinition("item_views_1h", FeatureType.INT, FeatureDomain.ITEM,
                          "内容1小时浏览数", refresh_cadence="realtime", default_value=0),
        FeatureDefinition("item_views_24h", FeatureType.INT, FeatureDomain.ITEM,
                          "内容24小时浏览数", refresh_cadence="realtime", default_value=0),
        FeatureDefinition("item_view_count", FeatureType.INT, FeatureDomain.ITEM,
                          "内容总浏览数", refresh_cadence="hourly", default_value=0),
        FeatureDefinition("item_like_count", FeatureType.INT, FeatureDomain.ITEM,
                          "内容总点赞数", refresh_cadence="hourly", default_value=0),

        # ===== Context =====
        FeatureDefinition("hour_of_day", FeatureType.INT, FeatureDomain.CONTEXT,
                          "当前小时(0-23)", refresh_cadence="realtime", default_value=0),
        FeatureDefinition("day_of_week", FeatureType.INT, FeatureDomain.CONTEXT,
                          "星期几(1-7)", refresh_cadence="realtime", default_value=1),
        FeatureDefinition("is_weekend", FeatureType.INT, FeatureDomain.CONTEXT,
                          "是否周末", refresh_cadence="realtime", default_value=0),

        # ===== Cross =====
        FeatureDefinition("tag_match_count", FeatureType.INT, FeatureDomain.CROSS,
                          "用户偏好标签∩内容标签数", refresh_cadence="realtime", default_value=0),
        FeatureDefinition("genre_match", FeatureType.INT, FeatureDomain.CROSS,
                          "用户偏好类型是否匹配", refresh_cadence="realtime", default_value=0),
        FeatureDefinition("author_match", FeatureType.INT, FeatureDomain.CROSS,
                          "用户偏好作者是否匹配", refresh_cadence="realtime", default_value=0),
    ]

    @classmethod
    def get_online_features(cls) -> List[str]:
        """Features available for online serving (Redis)."""
        return [f.name for f in cls.FEATURES
                if f.refresh_cadence in ("realtime", "hourly")]

    @classmethod
    def get_offline_features(cls) -> List[str]:
        """Features available for offline training (ClickHouse)."""
        return [f.name for f in cls.FEATURES]

    @classmethod
    def get_training_features(cls) -> List[str]:
        """Features used in the Wide&Deep training sample."""
        return [
            "user_total_views", "user_total_likes", "user_tag_diversity",
            "user_realtime_ctr", "user_ctr_1h", "user_dwell_avg_5min",
            "item_view_count", "item_like_count", "item_realtime_ctr",
            "item_hot_score_5min", "item_created_days",
            "tag_match_count", "genre_match", "author_match",
            "hour_of_day", "day_of_week", "is_weekend",
            "user_views_1h", "user_views_24h", "item_views_1h", "item_views_24h",
        ]

    @classmethod
    def by_domain(cls, domain: FeatureDomain) -> List[FeatureDefinition]:
        return [f for f in cls.FEATURES if f.domain == domain]
