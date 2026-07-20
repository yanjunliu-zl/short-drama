"""
Embedding-based ANN recall — 向量化内容召回。

用 bge-large-zh-v1.5 对案例标题+描述+标签做 embedding，FAISS 做近似最近邻检索。
替代纯 SQL 标签精确匹配，实现语义级内容发现。
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingRecall:
    """FAISS-based semantic content recall.

    Vectorizes case metadata into embeddings, indexes with FAISS,
    provides ANN search for semantically similar content.
    """

    def __init__(self, embedding_model: str = "BAAI/bge-large-zh-v1.5",
                 cache_dir: str = "/app/data/embedding_cache"):
        self._embed_model = None
        self._faiss_index = None
        self._embedding_model_name = embedding_model
        self._case_ids: List[str] = []  # FAISS ID → case_id
        self._dirty = True

    def _get_embeddings(self):
        if self._embed_model is None:
            from langchain_huggingface import HuggingFaceEmbeddings
            logger.info(f"EmbeddingRecall: loading {self._embedding_model_name}")
            self._embed_model = HuggingFaceEmbeddings(model_name=self._embedding_model_name)
        return self._embed_model

    @staticmethod
    def _build_case_text(case: Dict[str, Any]) -> str:
        """Build a rich text representation of a case for embedding.

        Weighted: title 3×, tags 2×, description 1×.
        """
        parts = []
        title = case.get("title", "")
        if title:
            parts.append((title + " ") * 3)  # repeat 3x for weight
        tags = case.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        if tags:
            parts.append((" ".join(tags) + " ") * 2)
        desc = case.get("description", "")
        if desc:
            parts.append(desc)
        return " ".join(parts).strip()

    async def build_index(self, cases: List[Dict[str, Any]]):
        """Build FAISS index from case list.

        Args:
            cases: List of case dicts with id, title, tags, description.
        """
        if not cases:
            return

        embeddings = self._get_embeddings()
        texts = []
        ids = []
        for c in cases:
            text = self._build_case_text(c)
            if text:
                texts.append(text)
                ids.append(c.get("id", ""))

        if not texts:
            return

        from langchain_community.vectorstores import FAISS
        # Use FAISS with metadata containing case_id
        metadatas = [{"case_id": cid} for cid in ids]
        self._faiss_index = FAISS.from_texts(texts, embeddings, metadatas=metadatas)
        self._case_ids = ids
        self._dirty = False
        logger.info(f"EmbeddingRecall: FAISS index built with {len(texts)} cases")

    async def search(self, query: str, top_k: int = 50,
                     exclude_ids: List[str] = None) -> List[Tuple[str, float]]:
        """ANN search for semantically similar cases.

        Args:
            query: Search query (user's interest description).
            top_k: Number of results.
            exclude_ids: Case IDs to exclude (already seen).

        Returns:
            List of (case_id, similarity_score) tuples.
        """
        if self._faiss_index is None or self._dirty:
            return []

        try:
            exclude_set = set(exclude_ids or [])
            # Search with slightly more candidates, then filter
            docs_with_scores = self._faiss_index.similarity_search_with_score(
                query, k=top_k + len(exclude_set) + 10
            )
            results = []
            for doc, score in docs_with_scores:
                case_id = doc.metadata.get("case_id", "")
                if case_id and case_id not in exclude_set:
                    # Convert L2 distance to similarity (0~1)
                    similarity = 1.0 / (1.0 + float(score))
                    results.append((case_id, similarity))
                if len(results) >= top_k:
                    break
            return results
        except Exception as e:
            logger.warning(f"EmbeddingRecall search failed: {e}")
            return []

    async def get_user_interest_vector(self, user_history: List[Dict[str, Any]]) -> str:
        """Build a user interest query from viewing history.

        Aggregates tags and descriptions from recently viewed cases.
        """
        if not user_history:
            return ""
        tags = []
        for h in user_history[:20]:
            t = h.get("tags", [])
            if isinstance(t, str):
                tags.extend([x.strip() for x in t.split(",") if x.strip()])
            elif isinstance(t, list):
                tags.extend(t)
        # Top tags as query
        from collections import Counter
        top_tags = Counter(tags).most_common(10)
        return " ".join([t for t, _ in top_tags])
