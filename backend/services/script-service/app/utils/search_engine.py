"""
Industrial Search Enhancement (Douyin Standard)

Modules:
  QueryUnderstanding: spell correction, intent classification, synonym expansion, NER
  SemanticSearch: embedding ANN + BM25 hybrid retrieval
  LearningToRank: pointwise/pairwise LTR model
  PersonalizedSearch: user profile injection
  QuerySuggest: auto-complete, trending, history
  SearchAnalytics: impression→click→conversion funnel

Usage:
  enhancer = SearchEnhancer(embedding_model="BAAI/bge-large-zh-v1.5")
  result = await enhancer.search(query, user_id, filters)
"""
import asyncio
import json
import logging
import re
import time
from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ============================================================
# #S1: Query Understanding
# ============================================================

class QueryUnderstanding:
    """Query correction, intent classification, synonym expansion, entity recognition."""

    # Chinese common typos → correction mapping
    _TYPO_MAP = {
        "总载": "总裁", "木又": "权", "王后": "皇后",
        "万界": "万界", "武动": "武动", "斗破": "斗破",
        "秀真": "修真", "期幻": "奇幻", "科环": "科幻",
    }

    # Synonym expansion for search recall
    _SYNONYMS = {
        "总裁": ["CEO", "老板", "霸道", "豪门"],
        "穿越": ["时空", "重生", "魂穿", "异世界"],
        "修真": ["修仙", "修炼", "仙侠", "道法"],
        "甜宠": ["甜文", "宠溺", "甜蜜", "恋爱"],
        "悬疑": ["推理", "侦探", "刑侦", "破案", "谜题"],
        "末日": ["末世", "丧尸", "废土", "灾难", "生存"],
        "宫斗": ["后宫", "宫廷", "嫡女", "庶女"],
        "武侠": ["江湖", "武林", "功夫", "侠客"],
    }

    # Intent categories
    _INTENT_PATTERNS = [
        (r"推荐|好看|热门|最近|有什么", "discovery"),
        (r"怎么|什么|多少|如何|哪", "question"),
        (r"小说|漫画|剧本|短剧|视频", "content_type"),
        (r"总裁|甜宠|恋爱|言情|爱情|婚恋", "genre_romance"),
        (r"穿越|重生|古代|宫廷|王妃|嫡女|庶女", "genre_period"),
        (r"修仙|修真|仙侠|玄幻|魔法|异界", "genre_fantasy"),
        (r"悬疑|推理|侦探|恐怖|惊悚|鬼", "genre_suspense"),
        (r"科幻|末日|末世|未来|机甲|太空", "genre_scifi"),
    ]

    # Entity patterns (named entities in search context)
    _ENTITY_PATTERNS = [
        (r"第\s*[一二三四五六七八九十百千\d]+\s*[季部集章]", "episode_ref"),
        (r"作者[：:]\s*(\S{2,8})", "author_spec"),
    ]

    @classmethod
    def correct(cls, query: str) -> str:
        """Apply typo correction."""
        for typo, correct in cls._TYPO_MAP.items():
            if typo in query:
                query = query.replace(typo, correct)
        return query

    @classmethod
    def expand_synonyms(cls, query: str) -> List[str]:
        """Expand query with synonyms for better recall."""
        expanded = [query]
        for term, syns in cls._SYNONYMS.items():
            if term in query:
                for s in syns[:2]:  # Take top 2 synonyms
                    expanded.append(query.replace(term, s))
        return list(set(expanded))

    @classmethod
    def classify_intent(cls, query: str) -> str:
        """Classify user search intent."""
        for pattern, intent in cls._INTENT_PATTERNS:
            if re.search(pattern, query):
                return intent
        return "general"

    @classmethod
    def extract_entities(cls, query: str) -> Dict[str, str]:
        """Extract named entities from query."""
        entities = {}
        for pattern, entity_type in cls._ENTITY_PATTERNS:
            m = re.search(pattern, query)
            if m:
                entities[entity_type] = m.group(1) if m.lastindex else m.group(0)
        return entities

    @classmethod
    def enhance(cls, query: str) -> Dict[str, Any]:
        """Full query enhancement pipeline.

        Returns dict with corrected query, expanded queries, intent, entities.
        """
        corrected = cls.correct(query)
        return {
            "original": query,
            "corrected": corrected,
            "expanded": cls.expand_synonyms(corrected),
            "intent": cls.classify_intent(corrected),
            "entities": cls.extract_entities(corrected),
        }


# ============================================================
# #S2: Semantic Search — Embedding + BM25 Hybrid
# ============================================================

class SemanticSearch:
    """Embedding-based ANN retrieval combined with BM25."""

    def __init__(self, embedding_model: str = "BAAI/bge-large-zh-v1.5"):
        self._embeddings = None
        self._faiss_index = None
        self._item_texts: Dict[str, str] = {}  # item_id → text for embedding
        self._embedding_model_name = embedding_model

    def _get_embeddings(self):
        if self._embeddings is None:
            from langchain_huggingface import HuggingFaceEmbeddings
            self._embeddings = HuggingFaceEmbeddings(model_name=self._embedding_model_name)
        return self._embeddings

    async def index_items(self, items: List[Dict[str, Any]]):
        """Index items for semantic search."""
        texts = []
        ids = []
        for item in items:
            # Build rich text: weighted title + tags + description
            parts = []
            title = item.get("title", "")
            if title:
                parts.append((title + " ") * 3)
            tags = item.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            if tags:
                parts.append(" ".join(tags) * 2)
            desc = item.get("description", "")
            if desc:
                parts.append(desc)
            text = " ".join(parts)
            if text.strip():
                texts.append(text)
                ids.append(item.get("id", ""))

        if not texts:
            return

        from langchain_community.vectorstores import FAISS
        embeddings = self._get_embeddings()
        self._faiss_index = FAISS.from_texts(
            texts, embeddings,
            metadatas=[{"item_id": iid} for iid in ids]
        )
        self._item_texts = {iid: txt for iid, txt in zip(ids, texts)}
        logger.info(f"SemanticSearch: indexed {len(texts)} items")

    async def search(self, query: str, top_k: int = 50,
                     bm25_results: List[Dict] = None) -> List[Dict[str, Any]]:
        """Semantic ANN search, optionally fused with BM25 results.

        Returns items ranked by combined score.
        """
        results = {}

        # Dense vector search
        if self._faiss_index:
            try:
                docs_with_scores = self._faiss_index.similarity_search_with_score(
                    query, k=top_k
                )
                for doc, score in docs_with_scores:
                    item_id = doc.metadata.get("item_id", "")
                    if item_id:
                        results[item_id] = {
                            "item_id": item_id,
                            "dense_score": 1.0 / (1.0 + float(score)),
                        }
            except Exception as e:
                logger.warning(f"Dense search failed: {e}")

        # Fuse with BM25
        if bm25_results:
            for rank, item in enumerate(bm25_results[:top_k]):
                item_id = item.get("id", "")
                if item_id in results:
                    # RRF fusion
                    rrf_dense = 1.0 / (60 + rank + 1) if item_id in results else 0
                    results[item_id]["bm25_score"] = item.get("_score", 0)
                    results[item_id]["combined"] = (
                        results[item_id].get("dense_score", 0) + rrf_dense
                    )
                else:
                    results[item_id] = {
                        "item_id": item_id,
                        "bm25_score": item.get("_score", 0),
                        "dense_score": 0,
                        "combined": 1.0 / (60 + rank + 1),
                    }

        # Sort by combined score
        sorted_results = sorted(
            results.values(),
            key=lambda x: x.get("combined", x.get("dense_score", 0)),
            reverse=True,
        )
        return sorted_results[:top_k]


# ============================================================
# #S3: Learning to Rank (Pointwise LTR)
# ============================================================

class LearningToRank:
    """Pointwise LTR model for search result re-ranking.

    Features: text relevance (BM25) + semantic similarity (dense) +
              content quality + freshness + popularity + personalization.
    """

    def __init__(self):
        self._weights = {
            "text_relevance": 0.30,    # BM25 score
            "semantic_match": 0.25,    # Dense cosine similarity
            "content_quality": 0.15,   # likes/views ratio
            "freshness": 0.10,         # Time decay
            "popularity": 0.10,        # Raw view count
            "personalization": 0.10,   # User tag/genre match
        }

    def score(self, item: Dict[str, Any], user_profile: Dict = None,
              semantic_score: float = 0.0) -> float:
        """Compute final ranking score for a search result."""
        scores = {}

        # Text relevance (BM25, normalized)
        scores["text_relevance"] = min(item.get("_score", 0) / 20.0, 1.0)

        # Semantic match
        scores["semantic_match"] = semantic_score

        # Content quality (engagement rate)
        views = item.get("view_count", 0) or item.get("views", 0)
        likes = item.get("like_count", 0) or item.get("likes", 0)
        engagement = likes / max(views, 1)
        scores["content_quality"] = min(engagement * 10, 1.0)

        # Freshness
        created = item.get("created_at") or item.get("createdAt", "")
        age_days = 30
        if created:
            try:
                dt = datetime.fromisoformat(str(created).replace("Z", "+00:00").replace(" ", "T"))
                age_days = (datetime.now() - dt.replace(tzinfo=None)).days
            except Exception:
                pass
        scores["freshness"] = max(0.1, 1.0 - age_days * 0.01)

        # Popularity
        scores["popularity"] = min(views / 100000, 1.0)

        # Personalization
        scores["personalization"] = 0.0
        if user_profile:
            item_tags = item.get("tags", [])
            if isinstance(item_tags, str):
                item_tags = [t.strip() for t in item_tags.split(",")]
            fav_tags = user_profile.get("favorite_tags", [])
            if fav_tags and item_tags:
                match = len(set(item_tags) & set(fav_tags))
                scores["personalization"] = min(match / max(len(fav_tags), 1), 1.0)

        total = sum(scores[k] * self._weights[k] for k in self._weights)
        return round(total, 4)


# ============================================================
# #S4: Personalized Search
# ============================================================

class PersonalizedSearch:
    """User profile injection for personalized search results."""

    @staticmethod
    def build_user_context(user_profile: Dict[str, Any]) -> str:
        """Build a user context string for query enrichment.

        Example output: "用户偏好:古装,爱情。喜欢作者:墨香。最近在看:修真类"
        """
        parts = []
        fav_tags = user_profile.get("favorite_tags", [])
        if fav_tags:
            parts.append("偏好:" + ",".join(fav_tags[:5]))
        fav_genre = user_profile.get("favorite_genre", "")
        if fav_genre:
            parts.append("类型:" + fav_genre)
        fav_authors = user_profile.get("favorite_authors", [])
        if fav_authors:
            parts.append("作者:" + ",".join(fav_authors[:3]))
        return "。".join(parts) if parts else ""

    @staticmethod
    def personalize_results(results: List[Dict],
                            user_profile: Dict[str, Any]) -> List[Dict]:
        """Boost results matching user preferences."""
        if not user_profile:
            return results

        fav_tags = set(user_profile.get("favorite_tags", []))
        fav_genre = user_profile.get("favorite_genre", "")
        fav_authors = set(user_profile.get("favorite_authors", []))

        for item in results:
            boost = 0.0
            item_tags = item.get("tags", [])
            if isinstance(item_tags, str):
                item_tags = [t.strip() for t in item_tags.split(",")]
            if fav_tags:
                tag_match = len(set(item_tags) & fav_tags)
                boost += tag_match * 0.03
            if fav_genre and item.get("genre", "") == fav_genre:
                boost += 0.05
            if fav_authors and item.get("author", "") in fav_authors:
                boost += 0.08
            item["_personalization_boost"] = boost
            item["_score"] = item.get("_score", 0) + boost

        results.sort(key=lambda x: x.get("_score", 0), reverse=True)
        return results


# ============================================================
# #S5: Query Suggestions
# ============================================================

class QuerySuggest:
    """Auto-complete, trending searches, search history."""

    def __init__(self, redis_client=None):
        self.redis = redis_client
        self._trending_cache = []
        self._trending_updated = 0

        # Hot query templates (in production, from analytics)
        self._hot_queries = [
            "总裁的替身新娘", "重生之都市修仙", "穿越古代当王妃",
            "末日求生指南", "悬疑推理之真相", "武林外传新编",
            "甜宠：霸道总裁爱上我", "科幻：AI觉醒",
        ]

    async def trending(self, limit: int = 10) -> List[str]:
        """Get trending search queries (24h window)."""
        now = time.time()
        if now - self._trending_updated < 300 and self._trending_cache:
            return self._trending_cache[:limit]

        if self.redis:
            try:
                # Get top queries from Redis sorted set
                key = f"search:trending:{datetime.now().strftime('%Y%m%d')}"
                top = await self.redis.zrevrange(key, 0, limit - 1, withscores=True)
                if top:
                    self._trending_cache = [q for q, _ in top]
                    self._trending_updated = now
                    return self._trending_cache[:limit]
            except Exception as e:
                logger.debug(f"Trending fetch failed: {e}")

        return self._hot_queries[:limit]

    async def autocomplete(self, prefix: str, limit: int = 5) -> List[str]:
        """Prefix-based autocomplete suggestions."""
        if not prefix or len(prefix) < 1:
            return []
        suggestions = []
        for q in self._hot_queries:
            if q.startswith(prefix) or prefix in q:
                suggestions.append(q)
            if len(suggestions) >= limit:
                break
        return suggestions

    async def record_query(self, query: str):
        """Record a search query for trending analysis."""
        if self.redis and query.strip():
            try:
                key = f"search:trending:{datetime.now().strftime('%Y%m%d')}"
                await self.redis.zincrby(key, 1, query.strip())
                await self.redis.expire(key, 86400 * 3)  # 3 day TTL
            except Exception as e:
                logger.debug(f"Query record failed: {e}")


# ============================================================
# #S7: Search Analytics Funnel
# ============================================================

class SearchAnalytics:
    """Impression → Click → Conversion funnel tracking."""

    def __init__(self, redis_client=None):
        self.redis = redis_client

    async def track_impression(self, query: str, results: List[str], user_id: str = ""):
        """Track search result impressions."""
        if not self.redis:
            return
        try:
            ts = time.time()
            key = f"search:funnel:{datetime.now().strftime('%Y%m%d%H')}"
            data = json.dumps({
                "event": "impression", "query": query, "user_id": user_id,
                "results": results[:20], "ts": ts,
            })
            await self.redis.lpush(key, data)
            await self.redis.expire(key, 86400)
        except Exception:
            pass

    async def track_click(self, query: str, item_id: str, position: int,
                          user_id: str = ""):
        """Track a click on a search result."""
        if not self.redis:
            return
        try:
            key = f"search:funnel:{datetime.now().strftime('%Y%m%d%H')}"
            data = json.dumps({
                "event": "click", "query": query, "item_id": item_id,
                "position": position, "user_id": user_id, "ts": time.time(),
            })
            await self.redis.lpush(key, data)
            await self.redis.expire(key, 86400)

            # Update per-query CTR
            ctr_key = f"search:ctr:{query}"
            await self.redis.hincrby(ctr_key, "clicks", 1)
        except Exception:
            pass

    async def get_funnel_stats(self, query: str = "",
                               hours: int = 24) -> Dict[str, Any]:
        """Get funnel statistics for a query or globally."""
        # Simplified: in production, aggregate from clickhouse/ES
        impressions = 0
        clicks = 0
        if self.redis:
            try:
                ctr_key = f"search:ctr:{query}" if query else "search:ctr:global"
                data = await self.redis.hgetall(ctr_key) or {}
                impressions = int(data.get("impressions", 0))
                clicks = int(data.get("clicks", 0))
            except Exception:
                pass

        ctr = clicks / max(impressions, 1)
        return {
            "impressions": impressions,
            "clicks": clicks,
            "ctr": round(ctr, 4),
            "hours": hours,
        }


# ============================================================
# Main Search Enhancer
# ============================================================

class SearchEnhancer:
    """Complete search enhancement pipeline — Douyin standard."""

    def __init__(self, embedding_model: str = "BAAI/bge-large-zh-v1.5",
                 redis_client=None):
        self.query_understanding = QueryUnderstanding()
        self.semantic_search = SemanticSearch(embedding_model)
        self.ltr = LearningToRank()
        self.personalized = PersonalizedSearch()
        self.suggest = QuerySuggest(redis_client)
        self.analytics = SearchAnalytics(redis_client)

    async def search(self, query: str, user_id: str = "",
                     user_profile: Dict = None,
                     bm25_results: List[Dict] = None,
                     top_k: int = 20) -> Dict[str, Any]:
        """Execute complete search pipeline.

        Args:
            query: Raw user query string.
            user_id: Authenticated user ID.
            user_profile: User preference profile from recommendation system.
            bm25_results: Pre-fetched BM25 results from Elasticsearch.
            top_k: Number of results to return.

        Returns:
            {
                "results": [...ranked items...],
                "query_enhanced": {...query analysis...},
                "suggestions": [...trending...],
                "funnel_id": "trace-uuid",
            }
        """
        t0 = time.time()

        # #S1: Query understanding
        enhanced = self.query_understanding.enhance(query)

        # #S2: Semantic search
        semantic_results = await self.semantic_search.search(
            enhanced["corrected"], top_k=top_k * 2,
            bm25_results=bm25_results,
        )

        # #S3: LTR Re-rank
        for item in bm25_results or []:
            sem_score = 0.0
            for sr in semantic_results:
                if sr.get("item_id") == item.get("id"):
                    sem_score = sr.get("dense_score", 0)
                    break
            item["_ltr_score"] = self.ltr.score(item, user_profile, sem_score)

        if bm25_results:
            bm25_results.sort(key=lambda x: x.get("_ltr_score", 0), reverse=True)

        # #S4: Personalization
        results = self.personalized.personalize_results(
            bm25_results or [], user_profile
        )[:top_k]

        # #S5: Suggestions
        suggestions = await self.suggest.trending(limit=5)

        # #S7: Track impression
        result_ids = [r.get("id", "") for r in results]
        funnel_id = f"search_{user_id}_{int(time.time())}"
        await self.analytics.track_impression(query, result_ids, user_id)

        elapsed = time.time() - t0
        logger.info(f"Search: query='{query}' → {len(results)} results, "
                    f"intent={enhanced['intent']}, elapsed={elapsed:.2f}s")

        return {
            "results": results[:top_k],
            "query_enhanced": {
                "original": enhanced["original"],
                "corrected": enhanced["corrected"],
                "intent": enhanced["intent"],
                "entities": enhanced["entities"],
            },
            "suggestions": suggestions,
            "funnel_id": funnel_id,
            "total": len(results),
            "elapsed_ms": int(elapsed * 1000),
        }

    async def record_click(self, query: str, item_id: str, position: int,
                           user_id: str = ""):
        """Record a search result click for funnel analytics."""
        await self.analytics.track_click(query, item_id, position, user_id)

    async def record_query(self, query: str):
        """Record a query for trending analysis."""
        await self.suggest.record_query(query)

    async def autocomplete(self, prefix: str, limit: int = 5) -> List[str]:
        """Get autocomplete suggestions."""
        return await self.suggest.autocomplete(prefix, limit)

    async def get_funnel_stats(self, query: str = "") -> Dict[str, Any]:
        """Get search funnel statistics."""
        return await self.analytics.get_funnel_stats(query)
