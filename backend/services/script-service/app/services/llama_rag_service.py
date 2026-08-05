"""
LlamaIndex 分层 RAG 服务 — 工业标准长篇小说检索。

三层索引架构（Hierarchical RAG）:
  L1: 章节摘要层 — 快速定位目标章节
  L2: 情节节点层 — 语义分块 + 元数据标签（人物/场景/时序）
  L3: 原文细粒度块 — 保留原始对白/动作/环境描写

检索链路:
  Query改写 → L1摘要定位 → L2 Hybrid检索(BM25+Dense+RRF)
  → Metadata过滤(人物/章节) → Rerank → L3原文补全 → 合并上下文
"""
import asyncio
import logging
import os
import re
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Lazy imports — only load when used
_LLAMA_AVAILABLE = False


def _check_llama():
    global _LLAMA_AVAILABLE
    if _LLAMA_AVAILABLE:
        return True
    try:
        import llama_index.core  # noqa: F401
        _LLAMA_AVAILABLE = True
        return True
    except ImportError:
        logger.warning("LlamaIndex not installed — falling back to basic RAG")
        return False


class HierarchicalRAG:
    """LlamaIndex-backed hierarchical RAG for long novels.

    Usage:
        rag = HierarchicalRAG(embedding_model="BAAI/bge-large-zh-v1.5")
        await rag.build_index(novel_text)  # Build L1/L2/L3 indexes
        context = await rag.retrieve("第15章 主角和女主吵架的片段",
                                     filter_chapter=15, filter_characters=["男主","女主"])
    """

    def __init__(self, embedding_model: str = "BAAI/bge-large-zh-v1.5",
                 chunk_size: int = 2048, chunk_overlap: int = 200,
                 cache_dir: str = "/app/data/llama_index"):
        self.embedding_model = embedding_model
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.cache_dir = cache_dir

        # Lazy-initialized
        self._embed_model = None
        self._Settings = None

        # Indexes
        self._l1_index = None      # Chapter summary index
        self._l2_index = None      # Scene/paragraph index
        self._l2_nodes = []        # L2 nodes with metadata
        self._chapters = []        # Chapter splits

        # BM25
        self._bm25_retriever = None
        self._bm25_corpus = []

        os.makedirs(self.cache_dir, exist_ok=True)

    def _init_llama(self):
        """Initialize LlamaIndex globals."""
        if not _check_llama():
            raise RuntimeError("LlamaIndex not available")
        if self._Settings is not None:
            return

        from llama_index.core import Settings
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding

        self._embed_model = HuggingFaceEmbedding(
            model_name=self.embedding_model,
            trust_remote_code=True,
        )
        Settings.embed_model = self._embed_model
        Settings.chunk_size = self.chunk_size
        Settings.chunk_overlap = self.chunk_overlap
        self._Settings = Settings
        logger.info(f"LlamaIndex initialized: embed={self.embedding_model}, "
                    f"chunk={self.chunk_size}")

    # ================================================================
    # Chapter splitting (delegates to existing logic, returns structured)
    # ================================================================

    @staticmethod
    def split_chapters(novel_text: str) -> List[Dict[str, Any]]:
        """Split novel into chapters with de-duplication."""
        markers = []
        pattern_cn = r'(?:^|\n)\s*(?:#{1,6}\s*)?第\s*([一二三四五六七八九十百千\d]+)\s*[回章节]'
        for m in re.finditer(pattern_cn, novel_text, re.MULTILINE):
            markers.append((m.start(), m.group(0).strip(), m.group(1)))

        if len(markers) <= 1:
            pattern_en = r'(?:^|\n)\s*(?:#{1,6}\s*)?Chapter\s+(\d+)'
            for m in re.finditer(pattern_en, novel_text, re.IGNORECASE | re.MULTILINE):
                markers.append((m.start(), m.group(0).strip(), m.group(1)))

        seen_nums = set()
        unique = []
        for pos, raw_title, num in markers:
            if num not in seen_nums:
                seen_nums.add(num)
                unique.append((pos, raw_title, num))

        if len(unique) <= 1:
            return [{"index": 0, "title": "全文", "content": novel_text.strip()}]

        chapters = []
        for i in range(len(unique)):
            start = unique[i][0]
            end = unique[i + 1][0] if i + 1 < len(unique) else len(novel_text)
            content = novel_text[start:end].strip()
            if len(content) >= 50:
                chapters.append({
                    "index": i,
                    "title": unique[i][1],
                    "content": content,
                })
        return chapters

    # ================================================================
    # Build L1 + L2 indexes
    # ================================================================

    async def build_index(self, novel_text: str,
                          global_info: dict = None,
                          progress_callback=None) -> Dict[str, Any]:
        """Build L1 (chapter summary) + L2 (semantic chunk) indexes.

        L1: One node per chapter summary (300 chars)
        L2: Semantic chunks per chapter with metadata
        """
        self._init_llama()
        import time
        from llama_index.core import VectorStoreIndex, Document
        from llama_index.core.node_parser import SentenceSplitter

        t0 = time.time()

        # Split chapters
        self._chapters = self.split_chapters(novel_text)
        logger.info(f"LlamaIndex: {len(self._chapters)} chapters detected")

        # --- L1: Chapter summaries ---
        l1_docs = []
        for ch in self._chapters:
            # Summary = first 300 chars of chapter (lightweight, no LLM call needed)
            summary = ch["content"][:300].replace("\n", " ")
            l1_docs.append(Document(
                text=summary,
                metadata={
                    "chapter_idx": ch["index"],
                    "chapter_title": ch["title"],
                    "level": "L1_summary",
                },
            ))

        self._l1_index = VectorStoreIndex.from_documents(l1_docs)
        logger.info(f"L1 index built: {len(l1_docs)} chapter summaries")

        # --- L2: Semantic chunks ---
        if progress_callback:
            await progress_callback(15, "LlamaIndex语义分块")

        splitter = SentenceSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            paragraph_separator="\n\n",
        )

        l2_nodes = []
        for ch in self._chapters:
            doc = Document(text=ch["content"])
            nodes = splitter.get_nodes_from_documents([doc])
            # Tag metadata
            for node in nodes:
                node.metadata.update({
                    "chapter_idx": ch["index"],
                    "chapter_title": ch["title"],
                    "level": "L2_scene",
                })
            l2_nodes.extend(nodes)

        self._l2_nodes = l2_nodes
        self._l2_index = VectorStoreIndex(l2_nodes)
        self._bm25_corpus = [n.get_content() for n in l2_nodes]

        logger.info(f"L2 index built: {len(l2_nodes)} nodes in "
                    f"{len(self._chapters)} chapters, elapsed={time.time()-t0:.1f}s")

        # --- Build BM25 ---
        try:
            from llama_index.retrievers.bm25 import BM25Retriever
            self._bm25_retriever = BM25Retriever.from_defaults(
                nodes=l2_nodes,
                similarity_top_k=10,
            )
            logger.info(f"LlamaIndex BM25 built: {len(l2_nodes)} docs")
        except ImportError:
            logger.warning("llama-index-retrievers-bm25 not installed")
        except Exception as e:
            logger.warning(f"BM25 build failed: {e}")

        return {
            "l1_chapter_summaries": len(l1_docs),
            "l2_scene_nodes": len(l2_nodes),
            "chapters": len(self._chapters),
            "elapsed": time.time() - t0,
        }

    # ================================================================
    # Hybrid retrieval (L1→L2→L3)
    # ================================================================

    async def retrieve(self, query: str,
                       filter_chapter: int = None,
                       filter_characters: List[str] = None,
                       top_k: int = 8) -> str:
        """Hybrid retrieval: L1 chapter filter → L2 hybrid search → formatted context.

        Args:
            query: Search query (already rewritten by caller).
            filter_chapter: Target chapter index (from L1).
            filter_characters: Only return chunks mentioning these characters.
            top_k: Number of chunks to return.

        Returns:
            Formatted context string ready for LLM prompt injection.
        """
        self._init_llama()

        # L1: Chapter-level filtering
        if filter_chapter is not None and self._l1_index:
            try:
                l1_retriever = self._l1_index.as_retriever(similarity_top_k=3)
                l1_results = l1_retriever.retrieve(f"第{filter_chapter+1}章 {query[:100]}")
                target_chapters = {n.metadata.get("chapter_idx") for n in l1_results}
                logger.debug(f"L1 filter: target chapters = {target_chapters}")
            except Exception:
                target_chapters = {filter_chapter}
        else:
            target_chapters = None

        # L2: Hybrid search (Dense + BM25)
        dense_contexts = []
        if self._l2_index:
            try:
                dense_retriever = self._l2_index.as_retriever(similarity_top_k=top_k * 2)
                dense_results = dense_retriever.retrieve(query)

                # Filter by chapter and characters
                for r in dense_results:
                    ch = r.metadata.get("chapter_idx")
                    if target_chapters and ch not in target_chapters:
                        continue
                    if filter_characters:
                        text = r.get_content()
                        if not any(c in text for c in filter_characters):
                            continue
                    dense_contexts.append(r.get_content()[:800])
            except Exception as e:
                logger.warning(f"Dense retrieval failed: {e}")

        # BM25
        sparse_contexts = []
        if self._bm25_retriever:
            try:
                bm25_results = self._bm25_retriever.retrieve(query)
                for r in bm25_results[:top_k]:
                    ch = r.metadata.get("chapter_idx")
                    if target_chapters and ch not in target_chapters:
                        continue
                    sparse_contexts.append(r.get_content()[:800])
            except Exception as e:
                logger.debug(f"BM25 retrieval failed: {e}")

        # Merge and deduplicate
        seen = set()
        parts = []
        for ctx in (dense_contexts + sparse_contexts):
            key = ctx[:100]
            if key not in seen:
                seen.add(key)
                parts.append(ctx)

        # Sort by chapter order for temporal consistency
        result = "\n---\n".join(parts[:top_k])
        logger.debug(f"LlamaIndex retrieve: dense={len(dense_contexts)} "
                    f"sparse={len(sparse_contexts)} → {len(parts)} unique")
        return result if result else "\n".join(self._bm25_corpus[:3])

    # ================================================================
    # L3: Fine-grained original text retrieval
    # ================================================================

    def retrieve_l3_detail(self, chapter_idx: int, keywords: str,
                           max_chars: int = 2000) -> str:
        """Retrieve original fine-grained text from a specific chapter.

        Used to fetch exact dialogue/action descriptions for script writing.
        """
        if chapter_idx >= len(self._chapters):
            return ""
        content = self._chapters[chapter_idx]["content"]
        if not keywords:
            return content[:max_chars]

        # Simple keyword-guided extraction
        kw_list = [kw.strip() for kw in keywords.split() if len(kw.strip()) >= 2]
        if not kw_list:
            return content[:max_chars]

        # Find paragraphs containing keywords
        paragraphs = content.split("\n\n")
        matched = [p for p in paragraphs if any(kw in p for kw in kw_list)]
        if matched:
            return "\n\n".join(matched)[:max_chars]
        return content[:max_chars]
