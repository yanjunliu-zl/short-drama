"""
LLM 语义缓存 — 基于 FAISS 向量相似度的请求→结果复用。

原理：
  1. 对每个 LLM 请求提取关键参数 (title + theme + outline 摘要)
  2. 用 embedding 模型将其向量化
  3. 存入 FAISS 索引
  4. 新请求到达时，计算相似度
  5. 如果已有相似请求 (cosine_sim > 0.95)，直接返回缓存结果
  6. 省去重复的 LLM 调用

预期节省：热点请求 60-80% 的 LLM 调用。
"""
import asyncio
import hashlib
import json
import logging
import os
import time
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)

# 相似度阈值 — 超过此值认为命中
SIMILARITY_THRESHOLD = 0.92
# 最大缓存条目数
MAX_CACHE_ENTRIES = 10000
# 最小请求长度才做语义缓存 (太短的不值得)
MIN_REQUEST_LENGTH = 50


class SemanticCache:
    """FAISS-based semantic cache for LLM request→response pairs."""

    def __init__(self, embedding_model_name: str = "BAAI/bge-large-zh-v1.5",
                 cache_dir: str = "/app/data/semantic_cache"):
        self._embeddings = None
        self._faiss_index = None
        self._embedding_model_name = embedding_model_name
        self._cache_dir = cache_dir
        self._texts: Dict[int, str] = {}        # faiss_id → request_key
        self._results: Dict[str, Any] = {}       # request_key → result
        self._next_id = 0
        self._hits = 0
        self._misses = 0
        os.makedirs(self._cache_dir, exist_ok=True)

    def _get_embeddings(self):
        if self._embeddings is None:
            from langchain_huggingface import HuggingFaceEmbeddings
            logger.info(f"SemanticCache: loading {self._embedding_model_name}")
            self._embeddings = HuggingFaceEmbeddings(model_name=self._embedding_model_name)
        return self._embeddings

    @staticmethod
    def _make_request_key(request: Dict[str, Any]) -> str:
        """Create a stable key from request parameters for dedup."""
        key_parts = {
            "title": request.get("title", ""),
            "theme": request.get("theme", ""),
            "style": request.get("style", ""),
            "length": request.get("length", ""),
            "setting": request.get("setting", ""),
        }
        # Include a content hash for outline/novel content
        content = request.get("outline") or request.get("novel_content") or ""
        if content:
            key_parts["content_hash"] = hashlib.md5(content[:500].encode()).hexdigest()[:12]
        return json.dumps(key_parts, sort_keys=True, ensure_ascii=False)

    @staticmethod
    def _make_query_text(request: Dict[str, Any]) -> str:
        """Build a query string from request for embedding."""
        parts = []
        for field in ["title", "theme", "style", "outline", "novel_content"]:
            val = request.get(field, "")
            if val:
                parts.append(str(val)[:300])
        return " ".join(parts)

    async def get(self, request: Dict[str, Any]) -> Optional[Any]:
        """Try to retrieve a cached result for a semantically similar request.

        Args:
            request: The LLM request dict (title, theme, style, outline, etc.).

        Returns:
            Cached result dict or None if no similar request found.
        """
        query_text = self._make_query_text(request)
        if len(query_text) < MIN_REQUEST_LENGTH:
            return None

        # Check exact match first (fast path)
        exact_key = self._make_request_key(request)
        if exact_key in self._results:
            self._hits += 1
            logger.info(f"SemanticCache: exact hit (total hits={self._hits}, misses={self._misses})")
            return self._results[exact_key]

        # Semantic similarity search
        if self._faiss_index is not None and len(self._texts) > 0:
            try:
                embeddings = self._get_embeddings()
                query_vec = await asyncio.to_thread(embeddings.embed_query, query_text)
                scores, indices = self._faiss_index.search(
                    query_vec.reshape(1, -1).astype("float32"), k=3
                )
                for score, idx in zip(scores[0], indices[0]):
                    if idx < 0 or idx not in self._texts:
                        continue
                    # FAISS returns L2 distance; convert to similarity
                    similarity = 1.0 / (1.0 + float(score))
                    if similarity >= SIMILARITY_THRESHOLD:
                        cached_key = self._texts[idx]
                        if cached_key in self._results:
                            self._hits += 1
                            logger.info(
                                f"SemanticCache: similarity hit sim={similarity:.3f} "
                                f"(total hits={self._hits}, misses={self._misses})"
                            )
                            return self._results[cached_key]
            except Exception as e:
                logger.debug(f"SemanticCache: search failed ({e}) — cache miss")

        self._misses += 1
        return None

    async def put(self, request: Dict[str, Any], result: Any):
        """Cache a request→result pair for future semantic lookup.

        Args:
            request: The LLM request dict.
            result: The LLM response to cache.
        """
        query_text = self._make_query_text(request)
        if len(query_text) < MIN_REQUEST_LENGTH:
            return

        exact_key = self._make_request_key(request)
        self._results[exact_key] = result

        # Add to FAISS index
        try:
            embeddings = self._get_embeddings()
            vec = await asyncio.to_thread(embeddings.embed_query, query_text)
            vec = vec.reshape(1, -1).astype("float32")

            from langchain_community.vectorstores import FAISS
            if self._faiss_index is None:
                self._faiss_index = FAISS.from_embeddings(
                    [(query_text, vec[0])], embeddings
                )
                self._texts[0] = exact_key
                self._next_id = 1
            else:
                self._faiss_index.add_embeddings([(query_text, vec[0])])
                self._texts[self._next_id] = exact_key
                self._next_id += 1

            # Evict oldest entries if over max
            while len(self._results) > MAX_CACHE_ENTRIES:
                oldest = next(iter(self._results))
                self._results.pop(oldest, None)

            logger.debug(f"SemanticCache: stored entry (total={len(self._results)})")
        except Exception as e:
            logger.debug(f"SemanticCache: store failed ({e})")

    async def clear(self):
        """Clear all cached entries."""
        self._texts.clear()
        self._results.clear()
        self._faiss_index = None
        self._next_id = 0
        self._hits = 0
        self._misses = 0

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0


# Global instance
_semantic_cache: Optional[SemanticCache] = None


def get_semantic_cache() -> SemanticCache:
    global _semantic_cache
    if _semantic_cache is None:
        _semantic_cache = SemanticCache()
    return _semantic_cache
