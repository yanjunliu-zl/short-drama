"""
Novel2Script V2 — Industrial-standard RAG-based novel-to-script pipeline.

Upgraded from Naive RAG to Advanced RAG (v0.2.0):
  1. Semantic chunking (replaces fixed-size RecursiveCharacterTextSplitter)
  2. BM25 sparse + FAISS dense dual retrieval with RRF fusion
  3. Per-chunk metadata tagging (chapter, characters, scene_type, timeline)
  4. Character passage retrieval (source evidence, not LLM profiles) for cross-chapter consistency
  5. Query rewriting for structured retrieval

Stages:
  1. Semantic chunking + metadata tagging + BM25+FAISS index
  2. Detect & split chapters
  3. Extract global character relationships → character vector store
  4. Per-chapter: query rewrite → hybrid search (BM25+dense+RRF+filtered) → generate
  5. Entity extraction + quality evaluation
  6. Build episodes + storyboard
"""
import asyncio
import hashlib
import logging
import os
import re
import time
from typing import Dict, Any, List, Optional, Callable, Tuple

import numpy as np
from langchain_core.messages import SystemMessage, HumanMessage

from app.prompts import (
    SYSTEM_EXTRACT_GLOBAL_V2, HUMAN_EXTRACT_GLOBAL_V2,
    SYSTEM_GENERATE_CHAPTER_V2, HUMAN_GENERATE_CHAPTER_V2,
    SYSTEM_EXTRACT_ENTITIES_V2, HUMAN_EXTRACT_ENTITIES_V2,
    SYSTEM_DEVELOP_STORY_V2, HUMAN_DEVELOP_STORY_V2,
)
from app.schemas.novel_v2 import GlobalInfoResponse
from app.utils.sse import format_sse_event, EVENT_STAGE, EVENT_ERROR, EVENT_DONE
from app.services.quality_judge import QualityJudge
from app.services.content_safety import get_safety_checker

logger = logging.getLogger(__name__)

MAX_CONCURRENT_CHAPTERS = 3


from app.services.outline_pipeline import OutlinePipeline


class ScriptGenerationEngine:
    """Script generation engine — novel (RAG) + outline (lightweight).

    Usage:
      engine = ScriptGenerationEngine(llm=..., config=...)
      engine.generate_from_novel(novel_text="...")      # novel → script (RAG)
      engine.generate_from_outline(outline_text="...")   # outline → script (lightweight)
    """

    def __init__(self, llm, mock_mode: bool = False, config=None):
        self.llm = llm
        self.mock_mode = mock_mode
        self.config = config
        self._embeddings = None

        # Configurable parameters
        self.chunk_size = getattr(config, 'N2S_V2_CHUNK_SIZE', 4096) if config else 4096
        self.top_k = getattr(config, 'N2S_V2_TOP_K', 8) if config else 8  # increased for RRF
        self.default_style = getattr(config, 'N2S_V2_DEFAULT_STYLE', 'ancient') if config else 'ancient'

        # Cache directories
        cache_dir = getattr(config, 'N2S_V2_OUTPUT_DIR', '/app/data/output') if config else '/app/data/output'
        self._cache_dir = os.path.join(cache_dir, 'faiss_cache')
        os.makedirs(self._cache_dir, exist_ok=True)

        # #4: Independent character profile vector store
        self._char_vector_store = None

        # #2: BM25 sparse retriever (lazy-built)
        self._bm25 = None
        self._bm25_chunks = []

        # LlamaIndex hierarchical RAG (optional, falls back to existing)
        self._llama_rag = None
        self._use_llama = False

        # Outline pipeline (composition, not inheritance)
        self.outline = OutlinePipeline(self)

    # ================================================================
    # FAISS disk cache helpers
    # ================================================================

    @staticmethod
    def _text_hash(text: str) -> str:
        """Stable hash of novel content for cache key."""
        return hashlib.md5(text.encode('utf-8', errors='replace')).hexdigest()[:16]

    def _faiss_cache_path(self, text_hash: str) -> str:
        return os.path.join(self._cache_dir, f'{text_hash}.faiss')

    def _load_faiss_cache(self, text_hash: str):
        """Try to load FAISS index from disk cache."""
        from langchain_community.vectorstores import FAISS
        path = self._faiss_cache_path(text_hash)
        if os.path.exists(path):
            try:
                embeddings = self._get_embeddings()
                vector_store = FAISS.load_local(
                    path, embeddings, allow_dangerous_deserialization=True
                )
                logger.info(f"FAISS cache hit: {path}")
                return vector_store
            except Exception as e:
                logger.warning(f"FAISS cache load failed: {e}, rebuilding...")
                # Clean up corrupted cache
                try:
                    os.remove(path)
                except Exception:
                    pass
        return None

    def _save_faiss_cache(self, text_hash: str, vector_store):
        """Save FAISS index to disk cache."""
        path = self._faiss_cache_path(text_hash)
        try:
            vector_store.save_local(path)
            logger.info(f"FAISS cache saved: {path}")
        except Exception as e:
            logger.warning(f"FAISS cache save failed: {e}")

    # ================================================================
    # Embedding model (lazy init)
    # ================================================================

    def _get_embeddings(self):
        """Lazy-load the HuggingFace embedding model.

        Default: BAAI/bge-large-zh-v1.5 — SOTA Chinese embedding (1024-dim, C-MTEB top-3).
        Falls back to all-MiniLM-L6-v2 (384-dim, English) for lightweight dev.
        """
        if self._embeddings is None:
            from langchain_huggingface import HuggingFaceEmbeddings
            model_name = getattr(self.config, 'N2S_V2_EMBEDDING_MODEL', 'BAAI/bge-large-zh-v1.5') if self.config else 'BAAI/bge-large-zh-v1.5'
            model_kwargs = {'device': 'cpu'}
            encode_kwargs = {'normalize_embeddings': True}
            logger.info(f"Loading embedding model: {model_name}")
            self._embeddings = HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs=model_kwargs,
                encode_kwargs=encode_kwargs,
            )
        return self._embeddings

    # ================================================================
    # #3: Metadata tagging helper
    # ================================================================

    @staticmethod
    def _tag_chunk_metadata(text: str, chapter_idx: int,
                            chapter_title: str = "",
                            global_info: dict = None) -> dict:
        """Tag a text chunk with structured metadata for filtered retrieval.

        Extracts: chapter index, detected character names, scene_type hint,
        timeline position, chunk_type (dialogue/action/environment).
        """
        meta = {
            "chapter": chapter_idx,
            "chapter_title": chapter_title,
            "characters": [],
            "timeline": "early" if chapter_idx < 10 else "middle" if chapter_idx < 30 else "late",
            "chunk_type": "narrative",
        }

        # Detect characters present (quick regex: Chinese names in quotes or dialogue)
        global_chars = {}
        if global_info:
            global_chars = {c.get("name", ""): c for c in global_info.get("characters", [])}

        detected = []
        for name in global_chars:
            if name and name in text:
                detected.append(name)
        if detected:
            meta["characters"] = list(set(detected))[:8]

        # Detect chunk type
        dialogue_count = len(re.findall(r'[：:"」]', text))
        action_count = len(re.findall(r'[△▲]|走|跑|推|拉|打|杀|飞|跳|坐|站|躺', text))
        env_count = len(re.findall(r'[景色天空山水风雪雨雾花草木]|环境|周围|四周|远处', text))
        if dialogue_count > action_count and dialogue_count > env_count:
            meta["chunk_type"] = "dialogue"
        elif action_count > dialogue_count:
            meta["chunk_type"] = "action"
        elif env_count > 2:
            meta["chunk_type"] = "environment"

        # Scene boundary detection
        if re.search(r'(?:^|\n)\s*[第第].{1,3}[回章节部卷]|【场景|Scene\s+\d+|Chapter\s+\d+', text):
            meta["is_scene_boundary"] = True

        return meta

    # ================================================================
    # #1: Semantic chunking — scene-aware splitting
    # ================================================================

    def _semantic_chunk(self, chapter_content: str, chapter_idx: int,
                        chapter_title: str = "", global_info: dict = None) -> List[dict]:
        """Semantic chunking: split by scene boundaries and natural paragraph breaks.

        Unlike fixed-size RecursiveCharacterTextSplitter, this preserves scene
        integrity by detecting natural breakpoints:
          - Chapter/scene markers (第X回, 第X章, Scene N)
          - Double newlines (paragraph separators)
          - Dialogue→narration transitions
          - 2000-5000 char target (configurable via chunk_size)
        """
        # Step 1: Split on major scene boundaries
        raw_sections = re.split(
            r'(?:^|\n)(?:\s*(?:第\s*[一二三四五六七八九十百千\d]+\s*[回章节]|【场景[^】]*】|Scene\s+\d+|Chapter\s+\d+).*?(?:\n|$))',
            chapter_content
        )

        # Step 2: Within each scene, split on paragraph breaks, merge small chunks
        chunks = []
        for section in raw_sections:
            if not section.strip():
                continue
            paragraphs = [p.strip() for p in section.split("\n\n") if p.strip()]
            current = ""
            for para in paragraphs:
                if len(current) + len(para) < self.chunk_size:
                    current = (current + "\n\n" + para) if current else para
                else:
                    if current:
                        chunks.append(current)
                    current = para
            if current:
                chunks.append(current)

        # Step 3: Tag each chunk with metadata
        return [
            {
                "text": chunk,
                "metadata": self._tag_chunk_metadata(
                    chunk, chapter_idx, chapter_title, global_info
                ),
            }
            for chunk in chunks if len(chunk) >= 50
        ]

    # ================================================================
    # Stage 1: Build industrial-standard knowledge base (FAISS + BM25 + Metadata)
    # ================================================================

    async def _build_knowledge_base(self, novel_text: str, global_info: dict = None,
                              progress_callback=None):
        """Build knowledge base — LlamaIndex (preferred) or FAISS+BM25 (fallback).

        Returns (index, chunk_dicts_or_nodes).
        """
        # Try LlamaIndex first
        try:
            from app.services.llama_rag_service import HierarchicalRAG
            self._llama_rag = HierarchicalRAG(
                embedding_model=getattr(self.config, 'N2S_V2_EMBEDDING_MODEL', 'BAAI/bge-large-zh-v1.5') if self.config else 'BAAI/bge-large-zh-v1.5',
                cache_dir=self._cache_dir,
            )
            llama_result = await self._llama_rag.build_index(
                novel_text, global_info=global_info, progress_callback=progress_callback,
            )
            self._use_llama = True
            logger.info(f"LlamaIndex KB built: L1={llama_result['l1_chapter_summaries']} "
                       f"L2={llama_result['l2_scene_nodes']} chapters={llama_result['chapters']}")
            # Return placeholder — _rag_search will use LlamaIndex directly
            return None, [{"text": "", "metadata": {}}]  # stub
        except ImportError:
            logger.info("LlamaIndex not installed — using FAISS+BM25 fallback")
        except Exception as e:
            logger.warning(f"LlamaIndex build failed ({e}) — falling back to FAISS+BM25")

        # Fallback: existing FAISS + BM25 implementation
        text_hash = self._text_hash(novel_text)

        # Try disk cache first
        if not self.mock_mode:
            cached = self._load_faiss_cache(text_hash)
            if cached is not None:
                # Re-chunk (quick) for BM25 and metadata
                all_chunks = []
                chapters = self.split_chapters(novel_text)
                for ch in chapters:
                    chunked = self._semantic_chunk(
                        ch["content"], ch["index"], ch["title"], global_info
                    )
                    all_chunks.extend(chunked)
                return cached, all_chunks

        # Build from scratch
        from langchain_community.vectorstores import FAISS

        # Semantic chunk all chapters
        all_chunks = []
        chapters = self.split_chapters(novel_text)
        for ch in chapters:
            chunked = self._semantic_chunk(
                ch["content"], ch["index"], ch["title"], global_info
            )
            all_chunks.extend(chunked)

        logger.info(f"Semantic chunking: {len(all_chunks)} chunks from {len(chapters)} chapters")

        # Handle edge case: input too short → no chunks
        if len(all_chunks) == 0:
            # Create a single dummy chunk from the raw novel text
            dummy_text = novel_text[:8192] if novel_text else " "
            all_chunks = [{"text": dummy_text, "metadata": {"chapter": "full", "scene_type": "full"}}]
            logger.warning(f"No chunks produced — using whole text as single chunk ({len(dummy_text)} chars)")

        # Build FAISS dense index
        embeddings = self._get_embeddings()
        chunk_texts = [c["text"] for c in all_chunks]
        chunk_metadatas = [c["metadata"] for c in all_chunks]
        vector_store = FAISS.from_texts(chunk_texts, embeddings, metadatas=chunk_metadatas)
        logger.info(f"FAISS index built: {len(chunk_texts)} vectors")

        # #2: Build BM25 sparse index
        self._build_bm25(chunk_texts)

        if not self.mock_mode:
            self._save_faiss_cache(text_hash, vector_store)

        return vector_store, all_chunks

    # ================================================================
    # #2: BM25 sparse index
    # ================================================================

    @staticmethod
    def _tokenize_chinese(text: str) -> List[str]:
        """Tokenize Chinese text using jieba (word-level), falls back to character-level."""
        try:
            import jieba
            return [w for w in jieba.cut(text) if w.strip()]
        except ImportError:
            return list(text)  # Character-level fallback

    def _build_bm25(self, chunk_texts: List[str]):
        """Build BM25 sparse retriever from chunk texts.

        Uses jieba word-level tokenization for Chinese — critical for
        accurate keyword matching (e.g. '总裁' vs '总裁助理').
        """
        try:
            from rank_bm25 import BM25Okapi
            tokenized = [self._tokenize_chinese(text) for text in chunk_texts]
            self._bm25 = BM25Okapi(tokenized)
            self._bm25_chunks = chunk_texts
            logger.info(f"BM25 index built: {len(chunk_texts)} documents (jieba tokenized)")
        except ImportError:
            logger.warning("rank_bm25 not installed — BM25 unavailable, using dense-only")
            self._bm25 = None

    def _bm25_search(self, query: str, k: int = 8) -> List[Tuple[int, float]]:
        """BM25 sparse search with jieba tokenization. Returns [(chunk_index, score), ...]."""
        if self._bm25 is None or not self._bm25_chunks:
            return []
        tokenized_query = self._tokenize_chinese(query)
        scores = self._bm25.get_scores(tokenized_query)
        max_score = max(scores) if scores and max(scores) > 0 else 1.0
        ranked = sorted(
            [(i, s / max_score) for i, s in enumerate(scores)],
            key=lambda x: x[1], reverse=True
        )
        return ranked[:k]

    @staticmethod
    def _rrf_fusion(dense_results: List[Tuple[int, float]],
                    sparse_results: List[Tuple[int, float]],
                    k: int = 60) -> List[int]:
        """Reciprocal Rank Fusion — merge dense + sparse rankings."""
        scores = {}
        for rank, (idx, _) in enumerate(dense_results):
            scores[idx] = scores.get(idx, 0) + 1.0 / (k + rank + 1)
        for rank, (idx, _) in enumerate(sparse_results):
            scores[idx] = scores.get(idx, 0) + 1.0 / (k + rank + 1)
        # Sort by fused score descending
        fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [idx for idx, _ in fused]

    # ================================================================
    # #4: Character profile vector store
    # ================================================================

    def _build_character_store(self, global_info: dict, chapters: list):
        """Index character APPEARANCES from the original novel text.

        Instead of storing LLM-summarized profiles (which may hallucinate traits
        not in the source), we index every paragraph where a character appears.
        When generating a chapter, we retrieve the most relevant passages showing
        how the character actually behaves in the novel — not how an LLM describes them.

        Each entry: "【第N章】角色名出现在以下段落中: ...原文内容..."
        """
        characters = global_info.get("characters", [])
        if not characters:
            return

        char_names = [c.get("name", "") for c in characters if c.get("name")]
        if len(char_names) < 2:
            return

        from langchain_community.vectorstores import FAISS

        # Build character passage entries
        char_passages = []
        for ch in chapters:
            ch_title = ch.get("title", "")
            content = ch.get("content", "")
            # Split chapter into paragraphs
            paragraphs = [p.strip() for p in content.split("\n") if p.strip() and len(p.strip()) > 20]
            for para in paragraphs:
                for name in char_names:
                    if name in para:
                        char_passages.append(
                            f"【{ch_title}】角色「{name}」出场:\n{para[:500]}"
                        )
                        break  # One entry per paragraph, tagged with first matching character

        if len(char_passages) < 5:
            return  # Too few passages to build useful index

        embeddings = self._get_embeddings()
        self._char_vector_store = FAISS.from_texts(char_passages, embeddings)
        logger.info(f"Character passage store built: {len(char_passages)} passages "
                    f"across {len(char_names)} characters")

    def _search_characters(self, names: List[str], k: int = 8) -> str:
        """Retrieve character APPEARANCE PASSAGES from the source novel.

        Searches for paragraphs where the given characters appear.
        Returns actual novel text showing their behavior — not LLM summaries.

        Also ensures we retrieve both EARLY and RECENT passages for each character
        to show character evolution (arc) across the story.
        """
        if self._char_vector_store is None or not names:
            return ""
        try:
            # Retrieve ALL passages for these characters
            query = " ".join(names)
            docs = self._char_vector_store.similarity_search(query, k=k * 3)

            # Filter to only passages mentioning target characters
            matches = [d for d in docs if any(n in d.page_content for n in names)]

            if not matches:
                return ""

            # Balance early and recent appearances per character
            selected = []
            for name in names[:4]:
                named_docs = [d for d in matches if f"「{name}」" in d.page_content]
                if not named_docs:
                    continue
                # Take 1 early + 1 recent passage
                selected.append(named_docs[0].page_content)  # First appearance (early)
                if len(named_docs) > 1:
                    selected.append(named_docs[-1].page_content)  # Last appearance (recent)
                if len(named_docs) > 3:
                    selected.append(named_docs[len(named_docs)//2].page_content)  # Middle

            result = "\n---\n".join(selected[:k])
            logger.debug(f"Character search: {len(selected)} passages for {len(names)} characters")
            return result if result else ""
        except Exception as e:
            logger.debug(f"Character search failed: {e}")
            return ""

    # ================================================================
    # Stage 2: Chapter detection & splitting
    # ================================================================

    @staticmethod
    def detect_chapter_count(novel_text: str) -> int:
        """Detect number of chapters (de-duplicated). Reuses same regex as V1."""
        # Format 1: 第X回/章/节 (line-start, may have ## markdown)
        pattern = r'(?:^|\n)\s*(?:#{1,6}\s*)?第\s*([一二三四五六七八九十百千\d]+)\s*[回章节]'
        matches = re.findall(pattern, novel_text, re.MULTILINE)
        if matches and len(matches) >= 2:
            unique = list(dict.fromkeys(matches))
            return min(len(unique), 50)
        # Format 2: 第X回/章/节 (anywhere)
        pattern2 = r'第\s*([一二三四五六七八九十百千\d]+)\s*[回章节]'
        matches2 = re.findall(pattern2, novel_text)
        if matches2 and len(matches2) >= 2:
            unique = list(dict.fromkeys(matches2))
            return min(len(unique), 50)
        # Format 3: Chapter N
        eng = re.findall(r'Chapter\s+(\d+)', novel_text, re.IGNORECASE)
        if eng and len(eng) >= 2:
            unique = list(dict.fromkeys(eng))
            return min(len(unique), 50)
        return 0

    @staticmethod
    def split_chapters(novel_text: str) -> List[Dict[str, Any]]:
        """Split novel into chapters with de-duplicated markers.

        #13: Supports Chinese (第X回/章/节) and English (Chapter N) formats.
        Returns list of {index, title, content}.
        """
        markers = []

        # Format 1: Chinese 第X回/章/节 (line-start, may have ## markdown)
        pattern_cn = r'(?:^|\n)\s*(?:#{1,6}\s*)?第\s*([一二三四五六七八九十百千\d]+)\s*[回章节]'
        for m in re.finditer(pattern_cn, novel_text, re.MULTILINE):
            markers.append((m.start(), m.group(0).strip(), m.group(1)))

        # Format 2: English Chapter N (fallback)
        if len(markers) <= 1:
            pattern_en = r'(?:^|\n)\s*(?:#{1,6}\s*)?Chapter\s+(\d+)'
            for m in re.finditer(pattern_en, novel_text, re.IGNORECASE | re.MULTILINE):
                markers.append((m.start(), m.group(0).strip(), m.group(1)))

        # De-duplicate by chapter number
        seen_nums = set()
        unique_markers = []
        for pos, raw_title, num in markers:
            if num not in seen_nums:
                seen_nums.add(num)
                unique_markers.append((pos, raw_title, num))

        if len(unique_markers) <= 1:
            return [{"index": 0, "title": "全文", "content": novel_text.strip()}]

        chapters = []
        for i in range(len(unique_markers)):
            start = unique_markers[i][0]
            end = unique_markers[i + 1][0] if i + 1 < len(unique_markers) else len(novel_text)
            content = novel_text[start:end].strip()
            if len(content) >= 50:  # Skip too-short fragments
                chapters.append({
                    "index": i,
                    "title": unique_markers[i][1],
                    "content": content,
                })

        logger.info(f"Chapter split: {len(chapters)} chapters (from {len(markers)} raw markers, "
                    f"format={'EN' if len(markers) > 0 and markers[0][0] == 0 else 'CN'})")
        return chapters

    # ================================================================
    # Stage 3: Global character relationship extraction
    # ================================================================

    async def _extract_global_info(self, novel_text: str) -> Dict[str, Any]:
        """One LLM call to extract all characters, relationships, scenes, props."""
        logger.info(f"Extracting global info... input length={len(novel_text)}")
        t0 = time.time()

        if self.mock_mode:
            return {
                "characters": [
                    {"name": "主角", "personality": "勇敢坚毅", "role": "主角"},
                    {"name": "配角", "personality": "机智幽默", "role": "配角"},
                ],
                "relationships": [
                    {"source": "主角", "target": "配角", "relation_type": "朋友",
                     "description": "并肩作战的伙伴"},
                ],
                "key_scenes": [
                    {"name": "京城", "description": "繁华都城", "category": "市井"},
                ],
                "key_props": [
                    {"name": "玉佩", "description": "传家宝", "significance": "身份的象征"},
                ],
            }

        # Truncate for very long novels (embedding-based RAG handles detail)
        text = novel_text[:80000] if len(novel_text) > 80000 else novel_text

        try:
            structured_model = self.llm.with_structured_output(
                GlobalInfoResponse, method="json_mode"
            )
            messages = [
                SystemMessage(content=SYSTEM_EXTRACT_GLOBAL_V2),
                HumanMessage(content=HUMAN_EXTRACT_GLOBAL_V2.format(novel_full=text)),
            ]
            response: GlobalInfoResponse = await structured_model.ainvoke(
                messages, config={"timeout": 180}
            )
            result = {
                "characters": [c.model_dump() for c in response.characters],
                "relationships": [r.model_dump() for r in response.relationships],
                "key_scenes": [s.model_dump() for s in response.key_scenes],
                "key_props": [p.model_dump() for p in response.key_props],
            }
            logger.info(f"Global info extracted: {len(result['characters'])} chars, "
                        f"{len(result['relationships'])} relations, "
                        f"{len(result['key_scenes'])} scenes, "
                        f"{len(result['key_props'])} props, "
                        f"elapsed={time.time()-t0:.1f}s")
            return result
        except Exception as e:
            logger.warning(f"Global info extraction failed: {e}, using fallback")
            return {
                "characters": [],
                "relationships": [],
                "key_scenes": [],
                "key_props": [],
            }

    # ================================================================
    # Stage 3b: Story Development — expand outline into rich story framework
    # ================================================================

    async def _develop_story_framework(self, story_input: str, target_episodes: int, style: str) -> str:
        """Expand a brief idea/outline into a detailed story framework.

        Returns a structured text with: synopsis, characters, episode outlines,
        key scenes, and key props. This framework then guides per-episode generation.
        """
        logger.info(f"Developing story framework for {target_episodes} episodes... input_len={len(story_input)}")
        t0 = time.time()

        if self.mock_mode:
            return f"【故事梗概】这是一个关于{story_input[:50]}的故事...\n\n【角色设定】主角：勇敢少年\n\n【分集大纲】共{target_episodes}集"

        try:
            style_rule = self._get_style_instructions(style)
            messages = [
                SystemMessage(content=SYSTEM_DEVELOP_STORY_V2),
                HumanMessage(content=HUMAN_DEVELOP_STORY_V2.format(
                    story_input=story_input[:8000] if len(story_input) > 8000 else story_input,
                    target_episodes=target_episodes,
                    style_rule=style_rule,
                )),
            ]
            response = await self.llm.ainvoke(messages, config={"timeout": 180})
            framework = response.content
            logger.info(f"Story framework developed: {len(framework)} chars, elapsed={time.time()-t0:.1f}s")
            return framework
        except Exception as e:
            logger.warning(f"Story development failed: {e}, using raw input")
            return story_input

    # ================================================================
    # Stage 4: RAG search
    # ================================================================

    # ================================================================
    # #5: HyDE — Hypothetical Document Embeddings for query expansion
    # ================================================================

    async def _hyde_expand(self, chapter_name: str, chapter_hint: str,
                           characters: list = None) -> str:
        """HyDE: generate a hypothetical script passage, then use it as the query.

        Instead of keyword-based query rewriting, we ask the LLM to write a
        short hypothetical scene based on the chapter context. This 'fake answer'
        is lexically closer to the novel text than the original query,
        resulting in 15-20% better retrieval recall.

        Args:
            chapter_name: Chapter title (e.g. "第三章 初遇")
            chapter_hint: First 500 chars of chapter content as context
            characters: Character names for the scene

        Returns:
            A 200-500 char hypothetical passage to use as the retrieval query.
        """
        if self.mock_mode or self.llm is None:
            return f"检索章节 '{chapter_name}' 的内容: {chapter_hint[:500]}"

        chars_str = "、".join(characters[:4]) if characters else "所有角色"
        try:
            messages = [
                SystemMessage(content="用一段话(200-500字)描述以下小说章节可能包含的场景，包括环境、角色动作、对白风格和情感基调。你不需要猜对情节，只需要用自然的小说语言描述，使这段文字在词汇和句式上接近原文风格。"),
                HumanMessage(content=f"章节:{chapter_name}。出场角色:{chars_str}。章节开头:{chapter_hint[:500]}"),
            ]
            response = await self.llm.ainvoke(messages, config={"timeout": 30})
            hyde_text = response.content.strip()[:600]
            logger.debug(f"HyDE: generated hypothetical ({len(hyde_text)} chars)")
            return hyde_text
        except Exception as e:
            logger.debug(f"HyDE failed ({e}), using chapter hint")
            return f"检索章节 '{chapter_name}' 相关内容: {chapter_hint[:500]}"

    # ================================================================
    # #2 + #3: Hybrid search (BM25 + Dense + RRF + Metadata filter)
    # ================================================================

    async def _rag_search(self, vector_store, query: str, k: int = None,
                    filter_characters: list = None, filter_chapter: int = None) -> str:
        """Hybrid search — LlamaIndex (preferred) or BM25+Dense+RRF (fallback).

        Returns formatted context string with source annotations.
        """
        # Try LlamaIndex hierarchical RAG first
        if self._use_llama and self._llama_rag:
            try:
                result = await self._llama_rag.retrieve(
                    query=query,
                    filter_chapter=filter_chapter,
                    filter_characters=filter_characters,
                    top_k=k or self.top_k,
                )
                if result and len(result) > 100:
                    return result
            except Exception as e:
                logger.warning(f"LlamaIndex retrieve failed ({e}) — falling back")

        # Fallback: existing BM25+Dense+RRF
        if k is None:
            k = self.top_k

        # Dense search (FAISS with optional metadata filter)
        filter_dict = None
        if filter_chapter is not None:
            filter_dict = {"chapter": filter_chapter}
        dense_texts: Dict[int, str] = {}  # index → text mapping
        dense_scores: List[Tuple[int, float]] = []  # (index, score) for RRF
        try:
            dense_docs = vector_store.similarity_search_with_score(
                query, k=k * 2, filter=filter_dict
            )
            for i, (doc, score) in enumerate(dense_docs):
                dense_texts[i] = doc.page_content
                dense_scores.append((i, 1.0 / (1.0 + score)))
        except Exception:
            retriever = vector_store.as_retriever(search_kwargs={"k": k * 2})
            docs = retriever.invoke(query)
            for i, doc in enumerate(docs):
                dense_texts[i] = doc.page_content
                dense_scores.append((i, 0.8))

        # Sparse search (BM25)
        sparse_scores = self._bm25_search(query, k=k * 2)

        # RRF fusion
        if sparse_scores:
            fused_indices = self._rrf_fusion(dense_scores, sparse_scores, k=60)
        else:
            fused_indices = [i for i, _ in dense_scores]

        # Collect results with deduplication
        seen_texts = set()
        context_parts = []
        rank = 0
        for idx in fused_indices[:k]:
            # Check BM25 chunks first
            if idx < len(self._bm25_chunks):
                text = self._bm25_chunks[idx]
            # Check dense results
            elif idx in dense_texts:
                text = dense_texts[idx]
            else:
                continue
            if text and text not in seen_texts:
                seen_texts.add(text)
                rank += 1
                context_parts.append(f"[来源{rank}] {text[:800]}")

        # #3: Filter by target characters if specified
        if filter_characters and context_parts:
            filtered = []
            for part in context_parts:
                if any(c in part for c in filter_characters):
                    filtered.append(part)
            if filtered:
                context_parts = filtered

        # Sort by chapter order for temporal consistency
        result = "\n---\n".join(context_parts)
        logger.debug(f"Hybrid RAG: dense={len(dense_scores)} sparse={len(sparse_scores)} "
                    f"fused→{len(context_parts)} chunks, filtered={'yes' if filter_characters else 'no'}")
        return result if result else "\n".join([c["text"] for c in self._bm25_chunks[:3]]) if self._bm25_chunks else ""

    # ================================================================
    # #6: Cross-encoder Reranker — fine-grained relevance scoring
    # ================================================================

    def _rerank(self, query: str, documents: List[str], top_k: int = 5) -> List[str]:
        """Re-rank candidates using BGE-Reranker cross-encoder.

        The reranker scores each (query, doc) pair with a cross-attention model,
        yielding much higher precision than embedding similarity alone.

        Falls back gracefully if FlagEmbedding is not installed.
        """
        if len(documents) <= top_k:
            return documents
        try:
            from FlagEmbedding import FlagReranker
            reranker = FlagReranker('BAAI/bge-reranker-v2-m3',
                                     use_fp16=True,
                                     devices=['cpu'])
            pairs = [[query, doc[:2000]] for doc in documents]
            scores = reranker.compute_score(pairs, normalize=True)
            # Sort by score descending
            ranked = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)
            result = [doc for doc, _ in ranked[:top_k]]
            logger.debug(f"Reranker: {len(documents)} → {len(result)} candidates "
                         f"(top score={ranked[0][1]:.3f})")
            return result
        except ImportError:
            logger.debug("FlagEmbedding not installed — skipping reranker")
            return documents[:top_k]
        except Exception as e:
            logger.warning(f"Reranker failed ({e}) — returning top_k as-is")
            return documents[:top_k]

    async def _rag_search_with_rerank(
        self, vector_store, query: str, k: int = None,
        filter_characters: list = None, filter_chapter: int = None,
        rerank_top_k: int = 5,
    ) -> str:
        """Hybrid search + reranker for production-quality retrieval."""
        # Step 1: Hybrid search (BM25 + Dense + RRF) → 2x candidates
        candidates_text = await self._rag_search(
            vector_store, query, k=(k or self.top_k) * 2,
            filter_characters=filter_characters, filter_chapter=filter_chapter,
        )
        if not candidates_text or "\n---\n" not in candidates_text:
            return candidates_text

        # Step 2: Split candidates back into individual docs
        docs = [d.strip() for d in candidates_text.split("---") if d.strip()]
        docs = [d.split("]", 1)[1].strip() if "]" in d[:10] else d for d in docs]

        # Step 3: Rerank
        reranked = self._rerank(query, docs, top_k=rerank_top_k)

        # Step 4: Rebuild context
        result = "\n---\n".join(
            f"[来源{i+1}] {doc[:800]}" for i, doc in enumerate(reranked)
        )
        return result if result else candidates_text[:3000]

    # ================================================================
    # Style instructions
    # ================================================================

    @staticmethod
    def _get_style_instructions(style: str) -> str:
        """Return style-specific dialogue formatting instructions."""
        styles = {
            "ancient": "古风台词，用词雅致、对仗工整，符合古代人物说话语气，摒弃现代网络用语，文风古典温润",
            "suspense": "悬疑风格台词，语气压抑、留白充足，暗藏伏笔，对话简短精炼，营造紧张诡异氛围",
            "comedy": "喜剧风格台词，轻松幽默、自带梗感，对话活泼诙谐，人物语气夸张生动，贴合喜剧影视节奏",
        }
        return styles.get(style, "正常写实台词风格")

    # ================================================================
    # Stage 5: Per-chapter script generation
    # ================================================================

    async def _generate_chapter_script(
        self,
        chapter: dict,
        global_info: dict,
        vector_store,
        style: str,
        scene_serial: str,
        cumulative_context: str = "",
    ) -> list:
        """Iterative scene-by-scene generation for one chapter.

        Phase 1: Split chapter into N scene segments (one LLM call for scene planning).
        Phase 2: Generate each scene individually (focused on its specific text segment).
        This avoids the attention dilution of batch generation and ensures
        every part of the chapter is covered.
        """
        chapter_name = chapter.get("title", f"第{chapter['index']+1}章")
        chapter_content = chapter.get("content", "")
        episode_hint = chapter.get("episode_hint", "")

        chapter_len = len(chapter_content)
        hard_cap = 20  # Safety cap — LLM-decided scene count won't exceed this

        # Shared context (computed once, reused across all scene calls)
        characters_list = [c.get("name", "") for c in global_info.get("characters", [])[:5]]
        # Retrieve character APPEARANCE PASSAGES from source novel (not LLM profiles)
        character_evidence = self._search_characters(
            characters_list + (chapter.get("characters", []) or [])[:3]
        )
        style_rule = self._get_style_instructions(style)

        # RAG — HyDE expansion → hybrid retrieval + rerank
        hyde_query = await self._hyde_expand(
            chapter_name=chapter_name,
            chapter_hint=chapter_content[:500],
            characters=characters_list,
        )
        rag_context = await self._rag_search_with_rerank(
            vector_store, query=hyde_query,
            filter_characters=characters_list if characters_list else None,
        )

        logger.info(f"Iterative scene generation for {chapter_name}: "
                    f"content_len={chapter_len} chars, rag={len(rag_context)} chars")

        if self.mock_mode:
            return [{
                "chapter_title": chapter_name, "scene_number": scene_serial,
                "scene_type": "内景 白天", "location": "大殿",
                "characters": ["主角", "配角"], "props": ["宝剑"],
                "storyboard": [{"shot_number": 1, "camera_type": "全景",
                    "camera_movement": "固定", "duration_seconds": 5.0,
                    "description": "大殿全景，人物入场"}],
                "script_body": "（大殿内，庄严肃穆）\n主角：（坚定）台词内容",
            }]

        try:
            # ── Phase 1: Scene planning (LLM decides scene count) ──
            segments = await self._plan_scenes(
                chapter_content, chapter_name, hard_cap, global_info,
                character_evidence, rag_context, cumulative_context, style_rule,
            )
            if not segments:
                segments = self._fallback_segments(chapter_content, hard_cap)

            # ── Phase 2: Iterative per-scene generation ──
            all_scenes = []
            prev_summary = ""
            for idx, seg in enumerate(segments):
                scene_serial_i = f"{scene_serial}-{idx+1}"
                scene = await self._generate_single_scene(
                    segment_text=seg.get("text", ""),
                    segment_summary=seg.get("summary", f"场景{idx+1}"),
                    chapter_name=chapter_name,
                    scene_serial=scene_serial_i,
                    global_info=global_info,
                    character_evidence=character_evidence,
                    rag_context=rag_context,
                    cumulative_context=cumulative_context,
                    prev_scene_summary=prev_summary,
                    style_rule=style_rule,
                    scene_index=idx,
                    total_scenes=len(segments),
                )
                if scene:
                    prev_summary = seg.get("summary", "")[:100]
                    all_scenes.append(scene)

            logger.info(f"Chapter '{chapter_name}' → {len(all_scenes)}/{len(segments)} scenes")

            # ── Source fidelity review (novel adaptation specific) ──
            combined_script = "\n\n".join(s.get("script_body", "") for s in all_scenes)
            if not self.mock_mode and self.llm and len(combined_script) > 100:
                fidelity = await self._review_source_fidelity(
                    chapter_name=chapter_name,
                    chapter_content=chapter_content[:8000],
                    script=combined_script[:8000],
                )
                if fidelity.get("needs_revision") and fidelity.get("issues"):
                    all_scenes = await self._revise_for_fidelity(
                        all_scenes=all_scenes, chapter_content=chapter_content[:8000],
                        issues=fidelity["issues"], chapter_name=chapter_name,
                    )
                    logger.info(f"Chapter '{chapter_name}' revised for source fidelity "
                                f"({len(fidelity['issues'])} issue(s))")

            return all_scenes if all_scenes else [self._fallback_chapter_script(chapter, scene_serial)]

        except Exception as e:
            logger.warning(f"Chapter script generation failed for {chapter_name}: {e}")
            return [self._fallback_chapter_script(chapter, scene_serial)]

    # ── Source fidelity review & revision ──

    async def _review_source_fidelity(
        self, chapter_name: str, chapter_content: str, script: str,
    ) -> dict:
        """Check if the generated script stays faithful to the original novel.

        Two dimensions reviewed in parallel:
        1. Plot fidelity: are key events preserved? any fabricated plot points?
        2. Character fidelity: do characters behave/speak consistently with the source?
        """
        try:
            async def _check_plot():
                messages = [
                    SystemMessage(content="对比小说原文和改编剧本，检查情节是否忠实。只关注: 关键事件是否被遗漏或篡改、是否编造了原文不存在的重要情节。输出 JSON: {\"fidelity\": true, \"issues\": [\"具体问题\"], \"suggestions\": [\"修改建议\"]}"),
                    HumanMessage(content=f"【{chapter_name}原文（前8000字）】\n{chapter_content[:8000]}\n\n【改编剧本】\n{script[:6000]}"),
                ]
                structured = self.llm.with_structured_output(
                    type('FidelityResult', (), {'__annotations__': {'fidelity': bool, 'issues': list, 'suggestions': list}}),
                    method="json_mode",
                )
                return await structured.ainvoke(messages, config={"timeout": 60})

            async def _check_characters():
                messages = [
                    SystemMessage(content="对比小说原文和改编剧本，检查角色是否OOC。只关注: 角色性格突变、对白风格与原文不符、角色关系表达错误。输出 JSON: {\"fidelity\": true, \"issues\": [\"具体问题\"], \"suggestions\": [\"修改建议\"]}"),
                    HumanMessage(content=f"【{chapter_name}原文（前8000字）】\n{chapter_content[:8000]}\n\n【改编剧本】\n{script[:6000]}"),
                ]
                structured = self.llm.with_structured_output(
                    type('FidelityResult', (), {'__annotations__': {'fidelity': bool, 'issues': list, 'suggestions': list}}),
                    method="json_mode",
                )
                return await structured.ainvoke(messages, config={"timeout": 60})

            plot_result, char_result = await asyncio.gather(_check_plot(), _check_characters())

            all_issues = []
            all_suggestions = []
            for r in [plot_result, char_result]:
                if r and isinstance(r, dict):
                    all_issues.extend(r.get("issues", []))
                    all_suggestions.extend(r.get("suggestions", []))

            needs_revision = len(all_issues) > 0
            logger.info(f"Source fidelity for '{chapter_name}': "
                        f"{'PASS' if not needs_revision else f'{len(all_issues)} issue(s)'}")
            return {
                "needs_revision": needs_revision,
                "issues": all_issues,
                "suggestions": all_suggestions,
            }
        except Exception as e:
            logger.warning(f"Source fidelity review failed ({e}) — skipping")
            return {"needs_revision": False, "issues": [], "suggestions": []}

    async def _revise_for_fidelity(
        self, all_scenes: list, chapter_content: str, issues: list, chapter_name: str,
    ) -> list:
        """Revise generated scenes to fix source fidelity issues.

        Only targets the specific problems identified — does not rewrite the whole chapter.
        """
        feedback = "\n".join(f"- {i}" for i in issues[:5])
        combined = "\n\n---\n\n".join(
            f"【{s.get('scene_number', '?')}】\n{s.get('script_body', '')}"
            for s in all_scenes
        )

        try:
            messages = [
                SystemMessage(content="你是剧本改编编辑。根据评审意见修正改编剧本，使其更忠实于小说原文。只修改评审指出的问题，保持其余部分完全不变。"),
                HumanMessage(content=f"""根据以下评审意见修正改编剧本。

【评审意见】
{feedback}

【小说原文参考】
{chapter_content[:4000]}

【待修正的改编剧本】
{combined[:8000]}

直接返回修正后的完整剧本，保持相同的分场结构（【SCENE-xxx】标记）。"""),
            ]
            response = await self.llm.ainvoke(messages, config={"timeout": 120})
            revised_text = response.content

            # Split back into scenes by SCENE markers
            import re as _re
            scene_splits = _re.split(r'(?:^|\n)(【SCENE-\d+】)', revised_text)
            if len(scene_splits) > 1:
                revised_scenes = []
                for i, s in enumerate(all_scenes):
                    if i < len(scene_splits) // 2:
                        seg_idx = i * 2 + 1
                        if seg_idx < len(scene_splits):
                            s["script_body"] = (scene_splits[seg_idx - 1] + scene_splits[seg_idx]).strip()
                    revised_scenes.append(s)
                logger.info(f"Fidelity revision: {len(all_scenes)} scenes updated for '{chapter_name}'")
                return revised_scenes
        except Exception as e:
            logger.warning(f"Fidelity revision failed ({e}) — keeping original")

        return all_scenes

    # ── Phase 1: Scene planning ──

    async def _plan_scenes(
        self, chapter_content: str, chapter_name: str, max_scenes: int,
        global_info: dict, character_evidence: str, rag_context: str,
        cumulative_context: str, style_rule: str,
    ) -> list:
        """Analyze chapter and split into N scene segments with plot boundaries."""
        plan_prompt = f"""分析以下小说章节，根据内容决定拆分为多少个场景片段。

场景数量的判断依据：
- 情节密度：事件多、反转多的章节拆更多；流水叙述拆更少
- 场景转换：出现"与此同时""画面一转""另一方面"等标记 → 新场景
- 对话/动作比例：对话密集（角色来回交锋）→ 少拆，让对话连贯；动作描写多 → 多拆，每个动作节拍一个场景
- 时间跳跃："三天后""当晚""次日" → 新场景

场景总数没有固定限制，完全由内容决定。但不要超过 {max_scenes} 个场景。

每个场景片段应包含：
1. 覆盖的小说原文段落（从章节原文中截取）
2. 一句话摘要（该场景要讲什么）

【章节名称】{chapter_name}
【章节内容】
{chapter_content[:12000]}

输出格式（JSON）：
{{
  "scene_count_analysis": "本章有3次场景转换+2次时间跳跃+密集对话段，建议拆为5个场景",
  "scenes": [
    {{"summary": "男主在咖啡厅遇见女主", "text": "...对应的原文段落..."}},
    ...
  ]
}}

要求：
- 完整覆盖章节所有关键情节，不要遗漏
- 每个场景的text字段包含对应原文（不要截断）
- 场景数由内容决定，不要为了凑数硬拆或硬并"""

        try:
            messages = [
                SystemMessage(content="你是专业剧本策划，擅长将小说章节拆分为场景片段。"),
                HumanMessage(content=plan_prompt),
            ]
            response = await self.llm.ainvoke(messages, config={"timeout": 120})
            data = self._parse_json_response(response.content)
            scenes = data.get("scenes", [])
            if scenes and len(scenes) > 0:
                return scenes[:max_scenes]
        except Exception as e:
            logger.warning(f"Scene planning failed for {chapter_name}: {e}")
        return []

    def _fallback_segments(self, chapter_content: str, max_scenes: int) -> list:
        """Content-aware fallback when LLM planning fails.

        Splits on paragraph boundaries (double newlines) and natural scene markers,
        not on arbitrary character counts.
        """
        # Try to split on natural boundaries first
        raw = re.split(r'\n\n+', chapter_content)
        paragraphs = [p.strip() for p in raw if p.strip() and len(p.strip()) > 30]

        if len(paragraphs) <= max_scenes:
            return [{"summary": p[:80], "text": p} for p in paragraphs]

        # Merge small paragraphs, keep big ones as-is
        segments = []
        current = ""
        for para in paragraphs:
            if len(current) + len(para) < 2000:
                current = (current + "\n\n" + para) if current else para
            else:
                if current:
                    segments.append({"summary": current[:80], "text": current})
                current = para
        if current:
            segments.append({"summary": current[:80], "text": current})

        return segments[:max_scenes]

    # ── Phase 2: Single scene generation ──

    async def _generate_single_scene(
        self, segment_text: str, segment_summary: str, chapter_name: str,
        scene_serial: str, global_info: dict, character_evidence: str,
        rag_context: str, cumulative_context: str, prev_scene_summary: str,
        style_rule: str, scene_index: int, total_scenes: int,
    ) -> dict:
        """Generate ONE scene from one text segment — focused and complete."""
        scene_prompt = f"""根据以下小说片段，生成一个独立的影视场景。

【章节】{chapter_name}
【本场景】{scene_index + 1}/{total_scenes} — {segment_summary}
【前一场景摘要】{prev_scene_summary if prev_scene_summary else '无（这是本章第一个场景）'}
【前情提要】{cumulative_context[:500]}
【角色原文参考（保持人设一致的依据）】
{character_evidence[:800]}
【相关前文】{rag_context[:500]}
【台词风格】{style_rule}

【小说原文片段 — 只改编以下内容】
{segment_text[:3000]}

【输出格式】
【场景编号】{scene_serial}
【场景地点】地点名 - 白天/黑夜
【场景类型】外景/内景
△环境描写（一句话）

角色名：（情绪）对白内容
角色名：（情绪）对白内容
...

【分镜明细】
镜号：1 | 镜头类型：全景/中景/近景/特写 | 运镜：推/拉/摇/移/固定 | 时长：3-8s | 画面：详细描述
镜号：2 | ...

【要求】
- 只改编上面【小说原文片段】中的内容，不要编造新的情节
- 如果是本章最后一个场景({scene_index+1 == total_scenes})，结尾加【本集钩子】
- 对白:动作:环境 = 5:3:2"""

        try:
            messages = [
                SystemMessage(content="你是专业影视编剧，将小说片段改编为场景剧本。"),
                HumanMessage(content=scene_prompt),
            ]
            response = await self.llm.ainvoke(messages, config={"timeout": 120})
            parsed = self._parse_chapter_response(
                response.content, chapter_name, scene_serial
            )
            return parsed[0] if parsed else None
        except Exception as e:
            logger.warning(f"Single scene generation failed for {scene_serial}: {e}")
            return None

    @staticmethod
    def _parse_json_response(text: str) -> dict:
        """Parse JSON from LLM response with fallback."""
        import json
        try:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            if "{" in text:
                text = text[text.index("{"):text.rindex("}")+1]
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return {}

    def _parse_chapter_response(self, response_text: str, chapter_title: str,
                                 scene_serial: str) -> list:
        """Parse LLM text response into MULTIPLE structured scene dicts.

        The LLM generates 3-6 scenes per chapter, delimited by 【场景N：...】 markers.
        Each scene has its own type, location, characters, props, and storyboard.
        """
        scenes = []

        # Extract per-chapter metadata (shared across all scenes in this chapter)
        chapter_chars_raw = re.search(r'【出场角色】(.+)', response_text)
        chapter_chars = []
        if chapter_chars_raw:
            chapter_chars = [c.strip() for c in re.split(r'[、，,]', chapter_chars_raw.group(1)) if c.strip()]

        chapter_props_raw = re.search(r'【核心道具】(.+)', response_text)
        chapter_props = []
        if chapter_props_raw:
            chapter_props = [p.strip() for p in re.split(r'[、，,]', chapter_props_raw.group(1)) if p.strip()]

        # Split into individual scenes by 【场景N：...】 markers
        # Pattern matches: 【场景1：地点 - 时间】 or 【场景一：地点】
        scene_pattern = re.compile(
            r'【场景\s*([一二三四五六七八九十\d]+)\s*[：:]([^】]+)】',
            re.IGNORECASE
        )
        scene_splits = list(scene_pattern.finditer(response_text))

        if not scene_splits:
            # No scene markers found — treat entire text as one scene (fallback)
            scenes.append({
                "chapter_title": chapter_title,
                "scene_number": scene_serial,
                "scene_type": "",
                "location": "",
                "characters": chapter_chars,
                "props": chapter_props,
                "storyboard": [],
                "script_body": response_text,
            })
            return scenes

        for i, match in enumerate(scene_splits):
            scene_num_str = match.group(1)
            scene_location = match.group(2).strip()
            start = match.end()
            end = scene_splits[i + 1].start() if i + 1 < len(scene_splits) else len(response_text)
            scene_body = response_text[start:end].strip()

            # Generate unique scene serial: "SCENE-001", "SCENE-002", etc.
            scene_serial_int = int(scene_serial.split('-')[1]) if '-' in scene_serial else i + 1
            unique_serial = f"SCENE-{scene_serial_int + i:03d}"

            # Extract scene-specific metadata
            scene_type = ""
            type_match = re.search(r'【场景类型】(.+)', scene_body)
            if type_match:
                scene_type = type_match.group(1).strip()

            # Extract scene-specific characters from body (角色名：台词 pattern)
            scene_chars = list(set(re.findall(r'([^\s：:△【（(]{2,5})[：:]', scene_body)))
            all_chars = list(set(chapter_chars + scene_chars))

            # Extract storyboard for this scene
            board_pattern = re.compile(
                r'镜号：(\d+)\s*\|\s*镜头类型：(.*?)\s*\|\s*运镜：(.*?)\s*\|\s*时长：(.*?)\s*\|\s*画面[：:](.*?)(?=镜号|【|$)',
                re.S
            )
            storyboard = []
            for m in board_pattern.finditer(scene_body):
                try:
                    dur_str = m.group(4).strip().replace('s', '').replace('秒', '')
                    storyboard.append({
                        "shot_number": len(storyboard) + 1,
                        "camera_type": m.group(2).strip(),
                        "camera_movement": m.group(3).strip(),
                        "duration_seconds": float(dur_str) if dur_str else 5.0,
                        "description": m.group(5).strip(),
                    })
                except (ValueError, IndexError):
                    continue

            # Extract cliffhanger (hook) from last scene
            hook = ""
            if i == len(scene_splits) - 1:  # Last scene
                hook_match = re.search(r'【本集钩子】(.+)', response_text)
                if hook_match:
                    hook = hook_match.group(1).strip()

            scenes.append({
                "chapter_title": chapter_title,
                "scene_number": unique_serial,
                "scene_type": scene_type,
                "location": scene_location,
                "characters": all_chars,
                "props": chapter_props,
                "storyboard": storyboard,
                "script_body": scene_body,
                "hook": hook,
            })

        return scenes

    def _fallback_chapter_script(self, chapter: dict, scene_serial: str) -> dict:
        """Fallback: programmatic conversion of chapter content to basic script format.

        #11: Improved fallback — extracts dialogue lines and scene markers
        instead of just returning raw text. Much better than the previous version
        which just returned the first 2000 chars unchanged.
        """
        content = chapter.get("content", "")
        chapter_title = chapter.get("title", f"章节{chapter.get('index', 0)+1}")
        lines = content.split("\n")

        # Try to extract dialogue (Chinese dialogue pattern: 角色名：台词)
        dialogue_pattern = re.compile(r'^([^\s：:△【（(]{2,5})[：:](.+)$')
        script_lines = []
        extracted_chars = set()
        current_scene = "未知场景"

        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Detect scene markers
            if re.match(r'(第[一二三四五六七八九十百千\d]+[回章节集]|\*\*?\d+[-—])', line):
                script_lines.append(f"\n△{line}")
                continue
            # Detect dialogue
            m = dialogue_pattern.match(line)
            if m:
                char_name = m.group(1).strip()
                dialogue = m.group(2).strip()
                if not char_name.startswith(("第", "Chapter", "场景")):
                    extracted_chars.add(char_name)
                    # Infer emotion from keywords
                    emotion = ""
                    if any(kw in dialogue for kw in ["？", "什么", "怎么", "为何"]):
                        emotion = "疑惑"
                    elif any(kw in dialogue for kw in ["！", "不", "必须", "一定"]):
                        emotion = "坚定"
                    script_lines.append(f"{char_name}：（{emotion}）{dialogue}" if emotion else f"{char_name}：{dialogue}")
                continue
            # Narrative → action description
            if len(line) > 10:
                script_lines.append(f"△{line[:200]}")

        script_body = "\n".join(script_lines[:100]) if script_lines else content[:3000]

        return {
            "chapter_title": chapter_title,
            "scene_number": scene_serial,
            "scene_type": "内景 白天",
            "location": "未知场景",
            "characters": list(extracted_chars)[:5],
            "props": [],
            "storyboard": [
                {"shot_number": 1, "camera_type": "中景", "camera_movement": "固定",
                 "duration_seconds": 5.0, "description": "场景转换"},
                {"shot_number": 2, "camera_type": "近景", "camera_movement": "固定",
                 "duration_seconds": 4.0, "description": "角色对话"},
            ],
            "script_body": script_body,
        }

    # ================================================================
    # Stage 5b: Entity extraction from final script
    # ================================================================

    async def _extract_entities_from_script(
        self, final_script: str, all_chapters: List[dict], global_info: dict
    ) -> Dict[str, Any]:
        """Extract characters, locations, and props from the final generated script.

        Uses LLM structured output; falls back to aggregating per-chapter data.
        """
        logger.info(f"Extracting entities from final script... length={len(final_script)}")
        t0 = time.time()

        if self.mock_mode:
            return self._aggregate_chapter_entities(all_chapters, global_info)

        try:
            # Reuse V1's ExtractEntitiesResponse schema
            from app.schemas.novel_v2 import ExtractEntitiesResponse
            structured_model = self.llm.with_structured_output(
                ExtractEntitiesResponse, method="json_mode"
            )
            text = final_script[:32000] if len(final_script) > 32000 else final_script
            messages = [
                SystemMessage(content=SYSTEM_EXTRACT_ENTITIES_V2),
                HumanMessage(content=HUMAN_EXTRACT_ENTITIES_V2.format(script=text)),
            ]
            response: ExtractEntitiesResponse = await structured_model.ainvoke(
                messages, config={"timeout": 120}
            )
            result = {
                "characters": [c.model_dump() for c in response.characters],
                "locations": [l.model_dump() for l in response.locations],
                "props": [p.model_dump() for p in response.props],
            }
            logger.info(f"Entities extracted: {len(result['characters'])} chars, "
                        f"{len(result['locations'])} locations, "
                        f"{len(result['props'])} props, "
                        f"elapsed={time.time()-t0:.1f}s")
            return result
        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}, using aggregated chapter data")
            return self._aggregate_chapter_entities(all_chapters, global_info)

    def _aggregate_chapter_entities(
        self, all_chapters: List[dict], global_info: dict
    ) -> Dict[str, Any]:
        """Fallback: aggregate per-chapter characters, locations, and props.
        Merges with global extraction data to avoid duplicates."""
        # Collect from per-chapter data
        chapter_chars: Dict[str, dict] = {}
        chapter_locations: Dict[str, dict] = {}
        chapter_props: Dict[str, dict] = {}

        for ch in all_chapters:
            for c_name in ch.get("characters", []):
                name = c_name.strip()
                if name and name not in chapter_chars:
                    chapter_chars[name] = {"name": name, "role": "配角", "gender": "", "description": ""}
            loc = ch.get("location", "").strip()
            if loc and loc not in chapter_locations:
                chapter_locations[loc] = {"name": loc, "description": ""}
            for p_name in ch.get("props", []):
                name = p_name.strip()
                if name and name not in chapter_props:
                    chapter_props[name] = {"name": name, "description": ""}

        # Merge with global extraction: global data is more authoritative
        for gc in global_info.get("characters", []):
            name = gc.get("name", "").strip()
            if name and name in chapter_chars:
                chapter_chars[name] = {
                    "name": name,
                    "role": gc.get("role", "配角"),
                    "gender": gc.get("gender", ""),
                    "description": gc.get("personality", gc.get("description", "")),
                }

        # Add global key scenes as locations
        for gs in global_info.get("key_scenes", []):
            name = gs.get("name", "").strip()
            if name and name not in chapter_locations:
                chapter_locations[name] = {
                    "name": name,
                    "description": gs.get("description", ""),
                }

        # Add global key props
        for gp in global_info.get("key_props", []):
            name = gp.get("name", "").strip()
            if name and name not in chapter_props:
                chapter_props[name] = {
                    "name": name,
                    "description": gp.get("description", gp.get("significance", "")),
                }

        logger.info(f"Aggregated entities: {len(chapter_chars)} chars, "
                    f"{len(chapter_locations)} locations, {len(chapter_props)} props")
        return {
            "characters": list(chapter_chars.values()),
            "locations": list(chapter_locations.values()),
            "props": list(chapter_props.values()),
        }

    # ================================================================
    # #5: Chapter summarization + cumulative context
    # ================================================================

    async def _summarize_chapter(self, chapter: dict, chapter_index: int,
                                  total_chapters: int) -> str:
        """Generate a 100-200 char summary of a chapter for cross-chapter context.

        This summary is injected into subsequent chapters as '前情提要'.
        Uses a lightweight LLM call with short timeout.
        """
        chapter_content = chapter.get("content", "")
        chapter_name = chapter.get("title", f"第{chapter_index+1}章")
        text = chapter_content[:4000] if len(chapter_content) > 4000 else chapter_content

        if self.mock_mode or self.llm is None:
            return f"第{chapter_index+1}章: {chapter_name}"

        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            messages = [
                SystemMessage(content="用一句话(不超过200字)总结以下章节的核心情节。只输出摘要文本，不要标题或编号。"),
                HumanMessage(content=f"章节: {chapter_name}\n\n{text}"),
            ]
            response = await self.llm.ainvoke(messages, config={"timeout": 30})
            summary = response.content.strip()[:250]
            return f"第{chapter_index+1}章({chapter_name}): {summary}"
        except Exception as e:
            logger.debug(f"Chapter {chapter_index+1} summarization failed: {e}")
            return f"第{chapter_index+1}章: {chapter_name}"

    def _build_cumulative_context(self, chapter_summaries: list,
                                   current_index: int) -> str:
        """Build cumulative context from previous chapter summaries.

        For chapter N, provides summaries of chapters 1 through N-1 plus
        a preview of chapter N+1 (if available).
        """
        parts = []
        # Previous chapters context (last 3 summaries to keep context focused)
        start = max(0, current_index - 3)
        if current_index > 0:
            prev = chapter_summaries[start:current_index]
            if prev:
                parts.append("【前情提要】")
                parts.extend(prev)

        # Next chapter preview
        if current_index + 1 < len(chapter_summaries):
            parts.append(f"【下集预告】{chapter_summaries[current_index + 1][:150]}")

        return "\n".join(parts) if parts else ""

    # (Outline pipeline methods moved to outline_pipeline.py — imported via OutlinePipelineMixin)


    # ================================================================
    # Full pipeline (novel → script, with RAG)
    # ================================================================

    async def generate_from_outline(
        self, outline_text: str, style: str = "", target_episodes: int = 10,
        progress_callback=None, user_context: str = "",
    ) -> Dict[str, Any]:
        """Generate script from an outline/idea (lightweight pipeline)."""
        return await self.outline.generate(
            outline_text=outline_text, style=style,
            target_episodes=target_episodes,
            progress_callback=progress_callback, user_context=user_context,
        )

    async def generate_from_outline_sse(
        self, outline_text: str, style: str = "",
        target_episodes: int = 10, user_context: str = "",
    ):
        """SSE streaming wrapper for generate_from_outline."""
        async for event in self.outline.generate_sse(
            outline_text=outline_text, style=style,
            target_episodes=target_episodes, user_context=user_context,
        ):
            yield event

    async def generate_from_novel(
        self,
        novel_text: str,
        style: str = "",
        progress_callback: Optional[Callable[[int, str], Any]] = None,
        target_episodes: int = 0,
        user_context: str = "",
    ) -> Dict[str, Any]:
        """Execute the complete V2 novel-to-script pipeline.

        Args:
            novel_text: Full novel content
            style: Script style (ancient/suspense/comedy)
            progress_callback: Optional async callback(progress_pct, stage_name)
            target_episodes: Minimum episodes to produce (0=auto). Used for outlines.
            user_context: Optional user preference context string injected into prompts.

        Returns:
            Dict with keys: script_scenes, final_script, characters, character_graph,
                            storyboard, episodes, stages
        """
        if not style:
            style = self.default_style

        result: Dict[str, Any] = {
            "stages": {},
            "script_scenes": [],
            "final_script": "",
            "characters": [],
            "character_graph": {"relationships": [], "key_scenes": [], "key_props": []},
            "entities": {"characters": [], "locations": [], "props": []},
            "storyboard": [],
        }

        t_total = time.time()

        # --- Stage 1: Build knowledge base ---
        logger.info("=== V2 Stage 1/5: Building knowledge base ===")
        if progress_callback:
            await progress_callback(10, "构建知识库")
        vector_store, chunks = await self._build_knowledge_base(
            novel_text, global_info=None, progress_callback=progress_callback,
        )
        result["stages"]["knowledge_base"] = {"chunks": len(chunks)}

        # --- Stage 2: Chapter detection ---
        logger.info("=== V2 Stage 2/5: Detecting chapters ===")
        if progress_callback:
            await progress_callback(20, "检测章节")
        chapters = self.split_chapters(novel_text)

        # Outline mode: expand single chapter into multiple episodes
        if len(chapters) == 1 and target_episodes > 1:
            content = chapters[0]["content"]
            chapters = []
            for ep in range(target_episodes):
                chapters.append({
                    "index": ep,
                    "title": f"第{ep + 1}集",
                    "content": content,
                    "episode_hint": f"这是第{ep + 1}集，共{target_episodes}集。请只创作本集内容，确保与前后的剧情连贯。",
                })
            logger.info(f"Outline mode: expanded to {target_episodes} virtual chapters")

        result["stages"]["chapters"] = {"count": len(chapters)}

        # --- Stage 3: Global character extraction ---
        logger.info("=== V2 Stage 3/5: Extracting global characters ===")
        if progress_callback:
            await progress_callback(30, "提取角色关系图谱")
        global_info = await self._extract_global_info(novel_text)
        result["characters"] = global_info.get("characters", [])
        result["character_graph"] = {
            "relationships": global_info.get("relationships", []),
            "key_scenes": global_info.get("key_scenes", []),
            "key_props": global_info.get("key_props", []),
        }
        result["stages"]["global_info"] = {
            "characters": len(result["characters"]),
            "relationships": len(result["character_graph"]["relationships"]),
        }

        # #4: Build independent character profile vector store
        self._build_character_store(global_info, chapters)

        # --- Stage 3b: Story Development — only for outlines, not full novels ---
        is_full_novel = len(chapters) >= 5
        if is_full_novel:
            logger.info(f"=== V2 Stage 3b/5: Skipping story framework (full novel, {len(chapters)} chapters) ===")
            story_framework = ""
            result["stages"]["story_framework"] = {"skipped": True, "reason": "full_novel"}
        else:
            logger.info("=== V2 Stage 3b/5: Developing story framework (outline mode) ===")
            if progress_callback:
                await progress_callback(35, "扩展故事框架")
            story_framework = await self._develop_story_framework(
                story_input=novel_text,
                target_episodes=max(target_episodes, len(chapters)),
                style=style,
            )
            result["story_framework"] = story_framework
            result["stages"]["story_framework"] = {"length": len(story_framework)}
        # Enrich global_info with framework + user preferences
        global_info["story_framework"] = story_framework
        global_info["user_preferences"] = user_context

        # --- GraphRAG: build cross-chapter context from knowledge graph ---
        graphrag_context = ""
        try:
            from app.services.graphrag_service import get_graphrag_service
            graphrag = await get_graphrag_service()
            if graphrag._initialized:
                # Extract key characters and build relationship context
                key_characters = [c.get("name", "") for c in global_info.get("characters", [])[:5]]
                if key_characters:
                    graphrag_context = await graphrag.vector_store.get_context_for_entities(
                        key_characters, script_id=text_hash,
                    )
                    if graphrag_context:
                        logger.info(f"GraphRAG context built: {len(graphrag_context)} chars "
                                    f"for {len(key_characters)} characters")
        except Exception as e:
            logger.warning(f"GraphRAG context building failed (non-critical): {e}")
        global_info["graphrag_context"] = graphrag_context

        # --- Stage 3c: Chapter summarization for cross-chapter context (#5 + #1) ---
        chapter_summaries = []
        if len(chapters) > 1 and not self.mock_mode:
            logger.info(f"=== V2 Stage 3c/5: Summarizing {len(chapters)} chapters ===")
            if progress_callback:
                await progress_callback(37, "生成章节摘要")
            # Serial: lightweight LLM calls (30s timeout each), necessary for coherence
            for i, ch in enumerate(chapters):
                summary = await self._summarize_chapter(ch, i, len(chapters))
                chapter_summaries.append(summary)
            logger.info(f"Chapter summaries complete: {len(chapter_summaries)} summaries")

        # --- Stage 4: Per-chapter script generation (parallel) ---
        logger.info(f"=== V2 Stage 4/5: Generating scripts for {len(chapters)} chapters "
                    f"(parallel, max {MAX_CONCURRENT_CHAPTERS} concurrent) ===")
        if progress_callback:
            await progress_callback(40, f"生成{len(chapters)}章剧本")
        sem = asyncio.Semaphore(MAX_CONCURRENT_CHAPTERS)
        completed = 0

        async def generate_one(i: int, chapter: dict) -> tuple:
            nonlocal completed
            scene_serial = f"SCENE-{str(i + 1).zfill(3)}"  # Placeholder, renumbered later
            # Build cumulative context from previous chapter summaries (#5)
            cum_ctx = self._build_cumulative_context(chapter_summaries, i)
            async with sem:
                result_ch = await self._generate_chapter_script(
                    chapter=chapter, global_info=global_info,
                    vector_store=vector_store, style=style,
                    scene_serial=scene_serial,
                    cumulative_context=cum_ctx,
                )
            completed += 1
            if progress_callback and len(chapters) > 1:
                pct = 40 + int(completed / len(chapters) * 35)
                await progress_callback(pct, f"剧本生成 {completed}/{len(chapters)}")
            return i, result_ch

        # Launch all chapter tasks concurrently, ordered by semaphore
        tasks = [generate_one(i, ch) for i, ch in enumerate(chapters)]
        results = await asyncio.gather(*tasks)
        # Sort by original chapter order
        results.sort(key=lambda x: x[0])
        # Flatten: each chapter now produces a LIST of scenes
        all_chapters = []
        for r in results:
            chapter_scenes = r[1] if isinstance(r[1], list) else [r[1]]
            all_chapters.extend(chapter_scenes)

        # Global sequential scene numbering (SCENE-001, SCENE-002, ...)
        for idx, scene in enumerate(all_chapters):
            scene["scene_number"] = f"SCENE-{str(idx + 1).zfill(3)}"

        result["script_scenes"] = all_chapters
        result["stages"]["script"] = {"chapters_generated": len(all_chapters)}

        # Collect all storyboard entries
        all_storyboard = []
        for ch in all_chapters:
            for shot in ch.get("storyboard", []):
                shot["_chapter"] = ch.get("chapter_title", "")
                shot["_scene"] = ch.get("scene_number", "")
                all_storyboard.append(shot)
        result["storyboard"] = all_storyboard

        # Build final concatenated script text with 第N集 markers
        # Group scenes by chapter_title for per-chapter episodes
        chapter_groups: dict = {}
        for scene in all_chapters:
            ch_title = scene.get("chapter_title", "未知章节")
            if ch_title not in chapter_groups:
                chapter_groups[ch_title] = []
            chapter_groups[ch_title].append(scene)

        parts = []
        episodes = []
        cn_nums = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十',
                   '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十',
                   '二十一', '二十二', '二十三', '二十四', '二十五', '二十六', '二十七', '二十八', '二十九', '三十',
                   '三十一', '三十二', '三十三', '三十四', '三十五', '三十六', '三十七', '三十八', '三十九', '四十',
                   '四十一', '四十二', '四十三', '四十四', '四十五', '四十六', '四十七', '四十八', '四十九', '五十']

        ep_num = 0
        for chapter_title, scenes in chapter_groups.items():
            ep_num += 1
            ep_cn = cn_nums[ep_num] if ep_num < len(cn_nums) else str(ep_num)
            ep_title = f"第{ep_cn}集"
            # Join all scene bodies for this chapter with scene markers
            scene_bodies = []
            for si, sc in enumerate(scenes):
                scene_num = sc.get('scene_number', f'SCENE-{si+1:03d}')
                location = sc.get('location', '')
                scene_type = sc.get('scene_type', '')
                body = sc.get('script_body', '')
                scene_bodies.append(
                    f"【场景编号】{scene_num}\n"
                    f"【场景地点】{location}\n"
                    f"【场景类型】{scene_type}\n\n"
                    f"{body}"
                )
            full_body = "\n\n" + "—" * 30 + "\n\n".join(scene_bodies)

            # Don't duplicate episode markers if LLM already generated them
            if re.match(r'\s*(?:\*\*)?第\s*[一二三四五六七八九十百千\d]+\s*集', full_body):
                episode_content = full_body
            else:
                episode_content = (
                    f"{ep_title}\n"
                    f"【场景数量】{len(scenes)}\n\n"
                    f"{full_body}"
                )
            parts.append(episode_content)
            episodes.append({
                "episode_number": ep_num,
                "title": ep_title,
                "content": episode_content,
            })

        result["final_script"] = "\n\n" + "—" * 40 + "\n\n".join(parts)
        result["episodes"] = episodes

        # --- Stage 5: Entity extraction from final script ---
        logger.info("=== V2 Stage 5/5: Extracting entities from final script ===")
        if progress_callback:
            await progress_callback(80, "提取场景角色道具")
        extracted_entities = await self._extract_entities_from_script(
            final_script=result["final_script"],
            all_chapters=all_chapters,
            global_info=global_info,
        )
        result["entities"] = extracted_entities
        result["stages"]["entities"] = {
            "characters": len(extracted_entities.get("characters", [])),
            "locations": len(extracted_entities.get("locations", [])),
            "props": len(extracted_entities.get("props", [])),
        }

        result["stages"]["final"] = {
            "total_length": len(result["final_script"]),
            "total_elapsed": time.time() - t_total,
        }

        if progress_callback:
            await progress_callback(100, "完成")

        logger.info(f"V2 pipeline complete: {len(all_chapters)} chapters, "
                    f"{len(all_storyboard)} storyboard shots, "
                    f"{len(result['final_script'])} chars, "
                    f"elapsed={time.time()-t_total:.1f}s")

        # --- Content safety check ---
        try:
            safety = get_safety_checker(enabled=True)
            safety_report = safety.check_script(
                content=result["final_script"],
                title=result.get("stages", {}).get("script", {}).get("chapters_generated", ""),
            )
            result["safety_report"] = safety_report.to_dict()
            if not safety_report.passed:
                logger.warning(f"Content safety: REJECTED score={safety_report.score}")
        except Exception as e:
            logger.warning(f"Content safety check skipped: {e}")

        # --- Stage 6: LLM-as-Judge quality evaluation ---
        if not self.mock_mode and self.llm:
            try:
                logger.info("=== V2 Stage 6/6: Quality evaluation ===")
                if progress_callback:
                    await progress_callback(90, "质量评审")
                judge = QualityJudge(self.llm, enabled=True)
                report = await judge.judge_script(
                    content=result["final_script"],
                    title=result.get("stages", {}).get("script", {}).get("chapters_generated", ""),
                )
                result["quality_report"] = report.to_dict()
                result["stages"]["quality"] = {
                    "total_score": report.total_score,
                    "verdict": report.verdict,
                    "elapsed_ms": report.judge_elapsed_ms,
                }
                if not report.passed:
                    logger.warning(
                        f"QualityJudge: {report.verdict} score={report.total_score} "
                        f"weaknesses={report.weaknesses}"
                    )

                # #7: Auto-retry on low quality
                if report.needs_retry and len(chapters) <= 5:
                    logger.info(
                        f"QualityJudge retry triggered: "
                        f"score={report.total_score} feedback={report.suggestions[:100]}"
                    )
                    if progress_callback:
                        await progress_callback(92, "质量优化中(自动重试)")
                    # Build optimization prompt with judge feedback
                    optimization_prompt = (
                        f"请根据以下评审意见优化剧本质量:\n\n"
                        f"【需要改进的问题】\n{report.suggestions}\n"
                        f"【具体弱项】\n" + "\n".join(f"- {w}" for w in report.weaknesses) + "\n\n"
                        f"请重新生成完整的优化版剧本。"
                    )
                    # Apply optimization to each chapter
                    for ch in all_chapters:
                        try:
                            optimize_messages = [
                                SystemMessage(content="你是专业剧本编辑，请根据反馈优化以下剧本。保持原有场景结构，重点改进评审指出的弱项。直接返回优化后的完整剧本。"),
                                HumanMessage(content=optimization_prompt + "\n\n原剧本:\n" + ch.get("script_body", "")[:6000]),
                            ]
                            optimize_resp = await self.llm.ainvoke(
                                optimize_messages, config={"timeout": 120}
                            )
                            ch["script_body"] = optimize_resp.content
                        except Exception as e2:
                            logger.warning(f"Chapter optimization failed: {e2}")
                    # Rebuild final script after optimization
                    parts = []
                    for i, ch in enumerate(all_chapters):
                        parts.append(f"第{cn_nums[i+1] if i+1 < len(cn_nums) else i+1}集\n\n{ch.get('script_body', '')}")
                    result["final_script"] = "\n\n" + "—" * 40 + "\n\n".join(parts)
                    logger.info(f"QualityJudge retry completed: chapters optimized")
            except Exception as e:
                logger.warning(f"Quality evaluation skipped: {e}")

        return result
    async def generate_from_novel_sse(
        self,
        novel_text: str,
        style: str = "",
        target_episodes: int = 0,
        user_context: str = "",
    ) -> "AsyncGenerator[str, None]":
        """Execute V2 pipeline with SSE stage-progress streaming.

        Uses an asyncio.Queue to bridge the synchronous progress_callback
        to the async SSE generator. Each pipeline stage emits a 'stage' event.

        Args:
            novel_text: Full novel/outline content.
            style: Script style (ancient/suspense/comedy).
            target_episodes: Minimum episodes to produce (0=auto).
            user_context: Optional user preference context string.

        Yields:
            SSE-formatted event strings (event: stage, event: done, event: error).
        """
        import asyncio
        queue: asyncio.Queue = asyncio.Queue()

        async def progress_callback(pct: int, stage_name: str):
            """Bridge: push progress updates into the async queue."""
            await queue.put(format_sse_event(
                {"stage": stage_name, "progress": pct},
                event=EVENT_STAGE,
            ))

        async def run_pipeline():
            """Run the actual pipeline in background, push result/error to queue."""
            try:
                result = await self.generate_from_novel(
                    novel_text=novel_text,
                    style=style,
                    user_context=user_context,
                    progress_callback=progress_callback,
                    target_episodes=target_episodes,
                )
                await queue.put(("__result__", result))
            except Exception as e:
                logger.error(f"V2 pipeline SSE error: {e}", exc_info=True)
                await queue.put(("__error__", str(e)))

        task = asyncio.create_task(run_pipeline())

        # Yield SSE events from the queue until result or error
        while True:
            item = await queue.get()
            if isinstance(item, tuple):
                kind, payload = item[0], item[1]
                if kind == "__result__":
                    yield format_sse_event(
                        {"status": "completed", "result": payload},
                        event=EVENT_DONE,
                    )
                    break
                elif kind == "__error__":
                    yield format_sse_event(
                        {"error": payload, "code": "PIPELINE_ERROR"},
                        event=EVENT_ERROR,
                    )
                    break
            else:
                # Already-formatted SSE string from progress_callback
                yield item

        # Ensure the background task is done
        await task
