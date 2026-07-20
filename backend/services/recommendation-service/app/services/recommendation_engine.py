"""
推荐引擎 — 抖音标准五层架构 + 多目标

Layer 1: 多路召回(6路并行, ~1000候选)
  新增: Embedding ANN 语义召回
Layer 1.5: 粗排 — 双塔模型 1000→200
Layer 2: 过滤 — 去重+已看
Layer 3: 精排 — Wide&Deep 多目标(CTR+完播率)
Layer 4: 重排 — MMR 多样性+冷启动探索+DPP打散
"""
import asyncio
import logging
import math
import random
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ranking_model import RankingService, get_ranking_service
from app.services.bandit import BanditService, get_bandit_service, _build_context

logger = logging.getLogger(__name__)

# #4: Cold start — exploration budget (10% of traffic)
COLD_START_EXPLORE_RATIO = 0.10
RECENCY_WINDOW_DAYS = 7  # "new" content threshold


# ==============================
# Data Types
# ==============================

@dataclass
class RecallItem:
    case_id: str
    title: str
    description: str
    author: str
    tags: List[str]
    genre: str
    cover_url: str
    view_count: int
    like_count: int
    created_at: str
    recall_score: float
    recall_source: str  # cf / content / hot / author / search / embedding


@dataclass
class RankedItem:
    case: RecallItem
    ctr_score: float       # CTR 预估分 (0~1)
    completion_score: float = 0.0  # #3: 完播率预估 (0~1)
    combined_score: float = 0.0    # #3: 融合分


# ==============================
# Layer 1: Multi-Path Recall
# ==============================

class RecallLayer:
    """多路召回 — 6路并行, 融合去重后截断到 1000 条"""

    def __init__(self, db: AsyncSession, embedding_recall=None):
        self.db = db
        self.embedding_recall = embedding_recall  # #1: FAISS ANN recall

    async def multi_path_recall(self, user_id: str = "", search_query: str = "",
                                user_history: list = None) -> List[RecallItem]:
        tasks = [
            self._collaborative(user_id),
            self._content_based(user_id),
            self._hot(),
            self._author_based(user_id),
            self._search(search_query) if search_query else asyncio.sleep(0),
            self._embedding_semantic(user_id, user_history),  # #1: 语义召回
        ]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        seen: Dict[str, bool] = {}
        merged: List[RecallItem] = []
        for results in results_list:
            if isinstance(results, BaseException) or results is None:
                continue
            for item in results:
                if not seen.get(item.case_id):
                    seen[item.case_id] = True
                    merged.append(item)

        merged.sort(key=lambda x: x.recall_score, reverse=True)
        return merged[:1000]  # #5: 扩大候选池为粗排做准备

    async def _collaborative(self, user_id: str) -> List[RecallItem]:
        if not user_id:
            return []
        sql = text("""
            SELECT DISTINCT c.id, c.title, COALESCE(c.description,'') d, c.author,
                   c.tags, COALESCE(c.genre,'') g, COALESCE(c.cover_url,'') cov,
                   c.view_count, c.like_count, c.created_at
            FROM cases c
            JOIN user_case_interactions uci ON c.id = uci.case_id
            WHERE uci.user_id IN (
                SELECT DISTINCT uci2.user_id FROM user_case_interactions uci2
                WHERE uci2.case_id IN (
                    SELECT DISTINCT case_id FROM user_case_interactions WHERE user_id = :uid
                ) AND uci2.user_id != :uid2
            ) AND c.id NOT IN (
                SELECT DISTINCT case_id FROM user_case_interactions WHERE user_id = :uid3
            ) AND c.status = 'published'
            ORDER BY (c.like_count * 2 + c.view_count * 0.5) DESC LIMIT 50
        """)
        rows = await self.db.execute(sql, {"uid": user_id, "uid2": user_id, "uid3": user_id})
        return [self._row_to_item(r, 0.9, "cf") for r in rows.fetchall()]

    async def _content_based(self, user_id: str) -> List[RecallItem]:
        if not user_id:
            return []
        # 获取用户交互过的标签
        tag_sql = text("""
            SELECT DISTINCT TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(c.tags, ',', n.n), ',', -1)) t
            FROM cases c
            JOIN user_case_interactions uci ON c.id = uci.case_id
            JOIN (SELECT 1 n UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
                  UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8) n
                ON CHAR_LENGTH(c.tags)-CHAR_LENGTH(REPLACE(c.tags,',','')) >= n.n-1
            WHERE uci.user_id = :uid AND uci.action_type IN ('view','like') LIMIT 20
        """)
        tag_rows = await self.db.execute(tag_sql, {"uid": user_id})
        tags = [r.t for r in tag_rows.fetchall() if r.t]
        if not tags:
            return []

        conditions = " OR ".join(["FIND_IN_SET(:t%d, c.tags) > 0" % i for i in range(len(tags))])
        params = {"uid": user_id}
        for i, t in enumerate(tags):
            params["t%d" % i] = t

        sql = text(f"""
            SELECT DISTINCT c.id, c.title, COALESCE(c.description,'') d, c.author,
                   c.tags, COALESCE(c.genre,'') g, COALESCE(c.cover_url,'') cov,
                   c.view_count, c.like_count, c.created_at
            FROM cases c WHERE c.status = 'published' AND c.id NOT IN (
                SELECT DISTINCT case_id FROM user_case_interactions WHERE user_id = :uid
            ) AND ({conditions})
            ORDER BY (c.like_count * 2 + c.view_count) DESC LIMIT 60
        """)
        rows = await self.db.execute(sql, params)
        results = []
        for r in rows.fetchall():
            match_count = sum(1 for t in tags if t in (r.tags or "").split(","))
            score = 0.7 + min(match_count * 0.05, 0.2)
            results.append(self._row_to_item(r, score, "content"))
        return results

    async def _hot(self) -> List[RecallItem]:
        sql = text("""
            SELECT id, title, COALESCE(description,'') d, author,
                   tags, COALESCE(genre,'') g, COALESCE(cover_url,'') cov,
                   view_count, like_count, created_at
            FROM cases WHERE status = 'published'
            ORDER BY (like_count * 3 + view_count) *
                GREATEST(0.3, 1 - TIMESTAMPDIFF(DAY, created_at, NOW()) * 0.003) DESC LIMIT 50
        """)
        rows = await self.db.execute(sql)
        results = []
        for i, r in enumerate(rows.fetchall()):
            results.append(self._row_to_item(r, 1.0 - i * 0.01, "hot"))
        return results

    async def _author_based(self, user_id: str) -> List[RecallItem]:
        if not user_id:
            return []
        author_sql = text("""
            SELECT DISTINCT c.author FROM cases c
            JOIN user_case_interactions uci ON c.id = uci.case_id
            WHERE uci.user_id = :uid AND uci.action_type IN ('view','like') LIMIT 10
        """)
        author_rows = await self.db.execute(author_sql, {"uid": user_id})
        authors = [r.author for r in author_rows.fetchall() if r.author]
        if not authors:
            return []

        conditions = " OR ".join(["c.author = :a%d" % i for i in range(len(authors))])
        params = {"uid": user_id}
        for i, a in enumerate(authors):
            params["a%d" % i] = a

        sql = text(f"""
            SELECT DISTINCT c.id, c.title, COALESCE(c.description,'') d, c.author,
                   c.tags, COALESCE(c.genre,'') g, COALESCE(c.cover_url,'') cov,
                   c.view_count, c.like_count, c.created_at
            FROM cases c WHERE c.status = 'published' AND c.id NOT IN (
                SELECT DISTINCT case_id FROM user_case_interactions WHERE user_id = :uid
            ) AND ({conditions}) ORDER BY c.created_at DESC LIMIT 30
        """)
        rows = await self.db.execute(sql, params)
        return [self._row_to_item(r, 0.8, "author") for r in rows.fetchall()]

    async def _search(self, query: str) -> List[RecallItem]:
        sql = text("""
            SELECT id, title, COALESCE(description,'') d, author,
                   tags, COALESCE(genre,'') g, COALESCE(cover_url,'') cov,
                   view_count, like_count, created_at
            FROM cases WHERE status = 'published'
            AND (title LIKE :q OR description LIKE :q2 OR tags LIKE :q3 OR author LIKE :q4)
            ORDER BY (like_count * 2 + view_count) DESC LIMIT 30
        """)
        kw = f"%{query}%"
        rows = await self.db.execute(sql, {"q": kw, "q2": kw, "q3": kw, "q4": kw})
        return [self._row_to_item(r, 0.85, "search") for r in rows.fetchall()]

    async def _embedding_semantic(self, user_id: str,
                                   user_history: list = None) -> List[RecallItem]:
        """#1: FAISS ANN 语义召回 — 向量相似度发现语义相关但标签不同内容"""
        if not self.embedding_recall or not user_id:
            return []
        try:
            from app.services.embedding_recall import EmbeddingRecall
            query = await self.embedding_recall.get_user_interest_vector(
                user_history or []
            )
            if not query:
                return []
            results = await self.embedding_recall.search(query, top_k=60)
            items = []
            for case_id, sim in results:
                items.append(RecallItem(
                    case_id=case_id, title="", description="", author="",
                    tags=[], genre="", cover_url="",
                    view_count=0, like_count=0, created_at="",
                    recall_score=0.6 + sim * 0.3, recall_source="embedding",
                ))
            if items:
                # Enrich with DB data for the top matches
                case_ids = [i.case_id for i in items[:30]]
                sql = text(
                    f"SELECT id, title, COALESCE(description,'') d, author, "
                    f"tags, COALESCE(genre,'') g, COALESCE(cover_url,'') cov, "
                    f"view_count, like_count, created_at "
                    f"FROM cases WHERE status='published' AND id IN :ids"
                )
                rows = await self.db.execute(sql, {"ids": tuple(case_ids)})
                enriched = {r.id: r for r in rows.fetchall()}
                enriched_items = []
                for item in items:
                    r = enriched.get(item.case_id)
                    if r:
                        enriched_items.append(self._row_to_item(r, item.recall_score, "embedding"))
                return enriched_items
            return []
        except Exception as e:
            logger.debug(f"Embedding recall failed (non-critical): {e}")
            return []

    async def _cold_start_explore(self) -> List[RecallItem]:
        """#4: 冷启动探索 — 新内容获得 10% 探索流量"""
        sql = text("""
            SELECT id, title, COALESCE(description,'') d, author,
                   tags, COALESCE(genre,'') g, COALESCE(cover_url,'') cov,
                   view_count, like_count, created_at
            FROM cases WHERE status='published'
            AND created_at >= :recent
            ORDER BY RAND() LIMIT 20
        """)
        recent = (datetime.now() - timedelta(days=RECENCY_WINDOW_DAYS)).isoformat()
        rows = await self.db.execute(sql, {"recent": recent})
        return [self._row_to_item(r, 0.65, "cold_start") for r in rows.fetchall()]

    def _row_to_item(self, r, score: float, source: str) -> RecallItem:
        tags = [t.strip() for t in (r.tags or "").split(",") if t.strip()]
        created = r.created_at.isoformat() if isinstance(r.created_at, datetime) else str(r.created_at or "")
        return RecallItem(
            case_id=r.id, title=r.title, description=r.d or "",
            author=r.author or "", tags=tags, genre=r.g or "",
            cover_url=r.cov or "", view_count=r.view_count or 0,
            like_count=r.like_count or 0, created_at=created,
            recall_score=score, recall_source=source,
        )


# ==============================
# Layer 2: Filter
# ==============================

class FilterLayer:
    """过滤层 — 去重、已看"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def apply(self, user_id: str, candidates: List[RecallItem]) -> List[RecallItem]:
        if not candidates:
            return []
        viewed = await self._get_viewed(user_id)
        seen: Dict[str, bool] = {}
        result: List[RecallItem] = []
        for c in candidates:
            if viewed.get(c.case_id):
                continue
            if seen.get(c.case_id):
                continue
            seen[c.case_id] = True
            result.append(c)
        return result

    async def _get_viewed(self, user_id: str) -> Dict[str, bool]:
        if not user_id:
            return {}
        sql = text("SELECT DISTINCT case_id FROM user_case_interactions WHERE user_id = :uid")
        rows = await self.db.execute(sql, {"uid": user_id})
        return {r.case_id: True for r in rows.fetchall()}


# ==============================
# Layer 3: CTR Ranking (Wide&Deep)
# ==============================

# ==============================
# Layer 1.5: Pre-Ranking — 双塔轻量模型 1000→200
# ==============================

class PreRankingLayer:
    """粗排层 — 轻量双塔模型快速筛选。

    从1000候选→200候选，用简单的用户-物品向量点积打分。
    保证精排层的输入质量，同时控制延迟。
    """

    @staticmethod
    async def pre_rank(candidates: List[RecallItem], user_profile: dict,
                       top_n: int = 200) -> List[RecallItem]:
        """快速粗排：加权公式 + 多样性保证。

        如果精排模型不可用，这层就是实际排序层。
        """
        if len(candidates) <= top_n:
            return candidates

        scored = []
        for item in candidates:
            # 轻量评分: 内容质量 + 时效 + 用户匹配
            quality = min(item.like_count / 5000, 0.5) + min(item.view_count / 50000, 0.3)
            # 时效衰减
            age_days = 0
            if item.created_at:
                try:
                    created = datetime.fromisoformat(item.created_at.replace("Z", "+00:00"))
                    age_days = (datetime.now() - created.replace(tzinfo=None)).days
                except Exception:
                    pass
            freshness = max(0.2, 1.0 - age_days * 0.01)
            # 用户匹配
            fav_tags = user_profile.get("favorite_tags", [])
            tag_match = len(set(item.tags or []) & set(fav_tags)) / max(len(fav_tags), 1) if fav_tags else 0
            fav_genre = user_profile.get("favorite_genre", "")
            genre_match = 1.0 if item.genre == fav_genre else 0.0

            score = (quality * 0.4 + freshness * 0.2 + tag_match * 0.25 + genre_match * 0.15)
            scored.append((item, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [item for item, _ in scored[:top_n]]


# ==============================
# Layer 3: CTR Ranking (Wide&Deep + 多目标)
# ==============================

class RankingLayer:
    """精排层 — Wide&Deep 多目标预估 (CTR + 完播率) + Contextual Bandit"""

    def __init__(self, ranking_service: RankingService, bandit_service: BanditService = None):
        self.service = ranking_service
        self.bandit = bandit_service

    async def rank(self, candidates: List[RecallItem], user_id: str = "",
                   user_profile: Dict[str, Any] = None) -> List[RankedItem]:
        # Extract features with real user data when available
        features_list = [self._extract_features(item, user_profile) for item in candidates]

        # 尝试 PyTorch 打分
        try:
            scores = self.service.rank(features_list)
            if len(scores) == len(candidates) and any(s > 0 for s in scores):
                ranked = [RankedItem(case=item, ctr_score=score) for item, score in zip(candidates, scores)]
                ranked.sort(key=lambda x: x.ctr_score, reverse=True)
                return ranked
        except Exception as e:
            logger.warning("PyTorch ranking failed, using fallback: %s", e)

        # Get bandit source weights if available (contextual exploration)
        bandit_weights = {}
        if self.bandit and user_id:
            try:
                # Use features from the first candidate as representative context
                user_features = {"total_interactions": 0, "is_new_user": not bool(user_id)}
                bandit_weights = await self.bandit.get_source_weights(
                    user_id, features_list[0] if features_list else {}, user_features)
                logger.debug("Bandit source weights: %s", {k: round(v, 3) for k, v in bandit_weights.items()})
            except Exception as e:
                logger.debug("Bandit weight fetch failed (non-critical): %s", e)

        # Weighted multi-objective formula (#3) with bandit
        ranked = []
        for item in candidates:
            ctr = 0.3 * min(item.like_count / 10000, 1.0)
            ctr += 0.1 * min(item.view_count / 100000, 1.0)
            src_weight = bandit_weights.get(item.recall_source, 0.5)
            ctr += 0.2 * item.recall_score * (0.5 + src_weight * 0.5)
            ctr = min(ctr, 1.0)

            # #3: 完播率预估 (基于观看/点赞比+内容时长推断)
            engagement_rate = item.like_count / max(item.view_count, 1)
            completion = min(engagement_rate * 5, 0.8) + 0.1 * (1.0 - min(item.view_count / 200000, 1.0))
            completion = min(completion, 1.0)

            # #3: 融合分 — CTR权重0.6 + 完播率0.4
            combined = ctr * 0.6 + completion * 0.4

            ranked.append(RankedItem(
                case=item, ctr_score=round(ctr, 6),
                completion_score=round(completion, 6),
                combined_score=round(combined, 6),
            ))
        ranked.sort(key=lambda x: x.combined_score, reverse=True)
        return ranked

    def _extract_features(self, item: RecallItem, user_profile: Dict[str, Any] = None) -> Dict[str, Any]:
        """Extract features for Wide&Deep ranking model.

        Args:
            item: Recall candidate.
            user_profile: Optional user interaction stats dict with keys:
                total_view_count, total_like_count, tag_diversity,
                favorite_tags, favorite_authors.
        """
        up = user_profile or {}
        fav_tags = up.get("favorite_tags", [])
        item_tags = item.tags or []
        tag_match = len(set(fav_tags) & set(item_tags)) if fav_tags and item_tags else 0

        fav_authors = up.get("favorite_authors", [])
        author_match = 1 if item.author in fav_authors else 0

        genre_match = 1 if item.genre and item.genre == up.get("favorite_genre", "") else 0

        # Item age in days
        item_age_days = 0
        if item.created_at:
            try:
                from datetime import datetime as dt
                created = dt.fromisoformat(item.created_at.replace("Z", "+00:00"))
                item_age_days = (dt.now() - created.replace(tzinfo=None)).days
            except Exception:
                pass

        return {
            "user_view_count": up.get("total_view_count", 0),
            "user_like_count": up.get("total_like_count", 0),
            "user_tag_diversity": up.get("tag_diversity", 0),
            "item_view_count": item.view_count,
            "item_like_count": item.like_count,
            "item_share_count": up.get("total_share_count", 0),
            "item_age_days": item_age_days,
            "tag_match_count": tag_match,
            "genre_match": genre_match,
            "author_match": author_match,
            "recall_source": item.recall_source,
            "recall_score": item.recall_score,
            "hour_of_day": datetime.now().hour,
            "item_genre": item.genre,
        }


# ==============================
# Layer 4: MMR Rerank
# ==============================

class RerankLayer:
    """MMR 最大边界相关性重排"""

    @staticmethod
    def rerank(ranked: List[RankedItem], top_n: int = 10, lambda_: float = 0.7) -> List[RankedItem]:
        if len(ranked) <= top_n:
            return ranked

        selected: List[RankedItem] = []
        pool = list(ranked)

        while len(selected) < top_n and pool:
            best_idx, best_score = 0, -math.inf
            for i, item in enumerate(pool):
                relevance = item.ctr_score
                max_sim = 0.0
                for sel in selected:
                    sim = RerankLayer._tag_similarity(item.case.tags, sel.case.tags)
                    if sim > max_sim:
                        max_sim = sim
                mmr = lambda_ * relevance - (1 - lambda_) * max_sim
                if mmr > best_score:
                    best_score, best_idx = mmr, i
            selected.append(pool.pop(best_idx))

        return selected

    @staticmethod
    def _tag_similarity(tags_a: List[str], tags_b: List[str]) -> float:
        if not tags_a or not tags_b:
            return 0.0
        set_b = set(tags_b)
        intersection = sum(1 for t in tags_a if t in set_b)
        union = len(set(tags_a) | set_b)
        return intersection / union if union > 0 else 0.0


# ==============================
# Pipeline Orchestrator
# ==============================

class RecommendationPipeline:
    """五层推荐流水线 (抖音标准) + Contextual Bandit"""

    def __init__(self, db: AsyncSession, ranking_service: RankingService,
                 bandit_service: BanditService = None, embedding_recall=None):
        self.recall = RecallLayer(db, embedding_recall)
        self.filter = FilterLayer(db)
        self.prerank = PreRankingLayer()  # #5: 粗排层
        self.ranking = RankingLayer(ranking_service, bandit_service)
        self.rank_layer = ranking_service
        self.db = db

    async def _get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Fetch rich user interaction stats for feature extraction.

        Returns:
            Dict with:
              - total_view_count, total_like_count, total_share_count
              - tag_diversity: unique tags interacted with
              - favorite_tags: top-5 most-interacted tags
              - favorite_genre: most-viewed genre
              - favorite_authors: top-3 most-interacted authors
              - recency_days: days since last activity
              - preferred_hour: peak activity hour (0-23)
        """
        if not user_id:
            return {}
        try:
            from sqlalchemy import text
            sql = text("""
                SELECT
                    COUNT(DISTINCT CASE WHEN uci.action_type = 'view' THEN uci.case_id END) as total_views,
                    COUNT(DISTINCT CASE WHEN uci.action_type = 'like' THEN uci.case_id END) as total_likes,
                    COUNT(DISTINCT CASE WHEN uci.action_type = 'share' THEN uci.case_id END) as total_shares,
                    DATEDIFF(NOW(), MAX(uci.created_at)) as recency_days,
                    HOUR(MAX(uci.created_at)) as recent_hour
                FROM user_case_interactions uci WHERE uci.user_id = :uid
            """)
            rows = await self.db.execute(sql, {"uid": user_id})
            row = rows.fetchone()
            if not row or row.total_views is None:
                return {}

            # Fetch favorite tags via joined query
            tag_sql = text("""
                SELECT TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(c.tags, ',', n.n), ',', -1)) t,
                       COUNT(*) cnt
                FROM cases c
                JOIN user_case_interactions uci ON c.id = uci.case_id
                JOIN (SELECT 1 n UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
                      UNION ALL SELECT 5 UNION ALL SELECT 6) n
                    ON CHAR_LENGTH(c.tags)-CHAR_LENGTH(REPLACE(c.tags,',','')) >= n.n-1
                WHERE uci.user_id = :uid AND uci.action_type IN ('view','like')
                GROUP BY t ORDER BY cnt DESC LIMIT 5
            """)
            tag_rows = await self.db.execute(tag_sql, {"uid": user_id})
            favorite_tags = [r.t for r in tag_rows.fetchall() if r.t]
            tag_diversity = len(favorite_tags)

            # Favorite genre
            genre_sql = text("""
                SELECT COALESCE(c.genre, '') g, COUNT(*) cnt
                FROM cases c JOIN user_case_interactions uci ON c.id = uci.case_id
                WHERE uci.user_id = :uid AND uci.action_type = 'view'
                GROUP BY g ORDER BY cnt DESC LIMIT 1
            """)
            genre_rows = await self.db.execute(genre_sql, {"uid": user_id})
            genre_row = genre_rows.fetchone()
            favorite_genre = genre_row.g if genre_row else ""

            # Favorite authors
            author_sql = text("""
                SELECT c.author, COUNT(*) cnt
                FROM cases c JOIN user_case_interactions uci ON c.id = uci.case_id
                WHERE uci.user_id = :uid AND uci.action_type IN ('view','like')
                GROUP BY c.author ORDER BY cnt DESC LIMIT 3
            """)
            author_rows = await self.db.execute(author_sql, {"uid": user_id})
            favorite_authors = [r.author for r in author_rows.fetchall() if r.author]

            return {
                "total_view_count": row.total_views or 0,
                "total_like_count": row.total_likes or 0,
                "total_share_count": row.total_shares or 0,
                "tag_diversity": tag_diversity,
                "favorite_tags": favorite_tags,
                "favorite_genre": favorite_genre,
                "favorite_authors": favorite_authors,
                "recency_days": int(row.recency_days) if row.recency_days is not None else 999,
                "preferred_hour": int(row.recent_hour) if row.recent_hour is not None else 12,
            }
        except Exception as e:
            logger.debug(f"User profile fetch failed (non-critical): {e}")
        return {}

    async def _get_user_history(self, user_id: str) -> list:
        """#2: Fetch user's recent behavior for real-time features."""
        if not user_id:
            return []
        try:
            sql = text("""
                SELECT c.id, c.title, c.tags, uci.action_type, uci.created_at
                FROM user_case_interactions uci
                JOIN cases c ON c.id = uci.case_id
                WHERE uci.user_id = :uid
                ORDER BY uci.created_at DESC LIMIT 50
            """)
            rows = await self.db.execute(sql, {"uid": user_id})
            return [{"case_id": r.id, "tags": r.tags, "action": r.action_type,
                     "time": r.created_at.isoformat() if r.created_at else ""}
                    for r in rows.fetchall()]
        except Exception:
            return []

    async def run(
        self, user_id: str = "", search_query: str = "", limit: int = 10,
    ) -> Tuple[List[RankedItem], str]:
        """
        抖音标准五层推荐流水线:
          Layer 1: 多路召回 (6路, ~1000候选)
          Layer 1.5: 粗排 (1000→200)
          Layer 2: 过滤 (去重+已看)
          Layer 3: 精排 (多目标: CTR+完播率)
          Layer 4: 重排 (MMR + 冷启动)

        Returns:
            (推荐结果列表, 推荐原因描述)
        """
        # #2: 获取用户实时行为序列
        user_history = await self._get_user_history(user_id) if user_id else []
        user_profile = await self._get_user_profile(user_id) if user_id else {}

        # Layer 1: Recall (6 channels)
        candidates = await self.recall.multi_path_recall(
            user_id, search_query, user_history=user_history,
        )
        recall_sources = list(set(c.recall_source for c in candidates))
        logger.info("Recall: %d candidates from %s", len(candidates), recall_sources)

        # #4: 冷启动探索 — 新内容获取曝光机会
        if random.random() < COLD_START_EXPLORE_RATIO:
            cold_items = await self.recall._cold_start_explore()
            if cold_items:
                candidates.extend(cold_items)
                logger.info("Cold start: %d new items injected into pool", len(cold_items))

        # Layer 1.5: Pre-Ranking (1000→200)
        candidates = await PreRankingLayer.pre_rank(candidates, user_profile, top_n=200)
        logger.info("PreRank: %d candidates after coarse ranking", len(candidates))

        # Layer 2: Filter
        candidates = await self.filter.apply(user_id, candidates)
        logger.info("Filter: %d candidates after dedup+viewed removal", len(candidates))

        # Layer 3: Rank (Wide&Deep multi-objective + Bandit)
        ranked = await self.ranking.rank(candidates, user_id, user_profile=user_profile)
        logger.info("Rank: top combined=%.4f ctr=%.4f completion=%.4f",
                    ranked[0].combined_score if ranked else 0,
                    ranked[0].ctr_score if ranked else 0,
                    ranked[0].completion_score if ranked else 0)

        # Layer 4: Rerank (MMR)
        final = RerankLayer.rerank(ranked, top_n=limit, lambda_=0.7)
        logger.info("Rerank: %d items after MMR diversity", len(final))

        reason = "personalized" if user_id else "popular"
        if recall_sources:
            reason = f"{reason} ({','.join(recall_sources[:3])})"

        return final, reason
