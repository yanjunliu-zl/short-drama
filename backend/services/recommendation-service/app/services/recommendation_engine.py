"""
推荐引擎 — 四层架构 (独立微服务)

Layer 1: 多路召回 → Layer 2: 过滤 → Layer 3: Wide&Deep排序 → Layer 4: MMR重排
"""
import asyncio
import logging
import math
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ranking_model import RankingService, get_ranking_service
from app.services.bandit import BanditService, get_bandit_service, _build_context

logger = logging.getLogger(__name__)


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
    recall_source: str  # cf / content / hot / author / search


@dataclass
class RankedItem:
    case: RecallItem
    ctr_score: float  # CTR 预估分 (0~1)


# ==============================
# Layer 1: Multi-Path Recall
# ==============================

class RecallLayer:
    """多路召回 — 5路并行, 融合去重后截断到 200 条"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def multi_path_recall(self, user_id: str = "", search_query: str = "") -> List[RecallItem]:
        tasks = [
            self._collaborative(user_id),
            self._content_based(user_id),
            self._hot(),
            self._author_based(user_id),
            self._search(search_query) if search_query else asyncio.sleep(0),
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
        return merged[:200]

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

class RankingLayer:
    """排序层 — PyTorch Wide&Deep CTR预估 + Contextual Bandit, 降级为加权公式"""

    def __init__(self, ranking_service: RankingService, bandit_service: BanditService = None):
        self.service = ranking_service
        self.bandit = bandit_service

    async def rank(self, candidates: List[RecallItem], user_id: str = "") -> List[RankedItem]:
        # 提取特征
        features_list = [self._extract_features(item) for item in candidates]

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

        # Weighted CTR formula with bandit-adjusted recall_source weights
        ranked = []
        for item in candidates:
            ctr = 0.3 * min(item.like_count / 10000, 1.0)
            ctr += 0.1 * min(item.view_count / 100000, 1.0)
            # Bandit adjusts the recall_source contribution
            src_weight = bandit_weights.get(item.recall_source, 0.5)
            ctr += 0.2 * item.recall_score * (0.5 + src_weight * 0.5)
            ctr += 0.05 * random.random()  # residual exploration noise
            ctr = min(ctr, 1.0)
            ranked.append(RankedItem(case=item, ctr_score=round(ctr, 6)))
        ranked.sort(key=lambda x: x.ctr_score, reverse=True)
        return ranked

    def _extract_features(self, item: RecallItem) -> Dict[str, Any]:
        return {
            "user_view_count": 0,
            "user_like_count": 0,
            "user_tag_diversity": 0,
            "item_view_count": item.view_count,
            "item_like_count": item.like_count,
            "item_share_count": 0,
            "item_age_days": 0,
            "tag_match_count": 0,
            "genre_match": 0,
            "author_match": 0,
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
    """四层推荐流水线 + Contextual Bandit"""

    def __init__(self, db: AsyncSession, ranking_service: RankingService, bandit_service: BanditService = None):
        self.recall = RecallLayer(db)
        self.filter = FilterLayer(db)
        self.ranking = RankingLayer(ranking_service, bandit_service)
        self.rank_layer = ranking_service  # store for reference

    async def run(
        self, user_id: str = "", search_query: str = "", limit: int = 10,
    ) -> Tuple[List[RankedItem], str]:
        """
        执行完整推荐流水线: 召回 → 过滤 → 排序 → 重排

        Returns:
            (推荐结果列表, 推荐原因描述)
        """
        # Layer 1: Recall
        candidates = await self.recall.multi_path_recall(user_id, search_query)
        recall_sources = list(set(c.recall_source for c in candidates))
        logger.info("Recall: %d candidates from %s", len(candidates), recall_sources)

        # Layer 2: Filter
        candidates = await self.filter.apply(user_id, candidates)
        logger.info("Filter: %d candidates after dedup+viewed removal", len(candidates))

        # Layer 3: Rank (with Contextual Bandit)
        ranked = await self.ranking.rank(candidates, user_id)
        logger.info("Rank: top score=%.4f", ranked[0].ctr_score if ranked else 0)

        # Layer 4: Rerank
        final = RerankLayer.rerank(ranked, top_n=limit, lambda_=0.7)
        logger.info("Rerank: %d items after MMR diversity", len(final))

        reason = "personalized" if user_id else "popular"
        if recall_sources:
            reason = f"{reason} ({','.join(recall_sources[:3])})"

        return final, reason
