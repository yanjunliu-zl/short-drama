"""
Novel2Script V2 — RAG-based novel-to-script pipeline.

Stages:
  1. Build FAISS knowledge base from full novel (disk-cached)
  2. Detect & split chapters
  3. Extract global character relationships, scenes, props
  4. Per-chapter RAG search + script generation (parallel, up to 3 concurrent)
  5. Entity extraction from final script
  6. Build episodes + storyboard
"""
import asyncio
import hashlib
import logging
import os
import re
import time
from typing import Dict, Any, List, Optional, Callable, Tuple

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.prompts import (
    SYSTEM_EXTRACT_GLOBAL_V2, HUMAN_EXTRACT_GLOBAL_V2,
    SYSTEM_GENERATE_CHAPTER_V2, HUMAN_GENERATE_CHAPTER_V2,
    SYSTEM_EXTRACT_ENTITIES_V2, HUMAN_EXTRACT_ENTITIES_V2,
    SYSTEM_DEVELOP_STORY_V2, HUMAN_DEVELOP_STORY_V2,
)
from app.schemas.novel_v2 import GlobalInfoResponse

logger = logging.getLogger(__name__)

# Max concurrent chapter LLM calls
MAX_CONCURRENT_CHAPTERS = 3


class Novel2ScriptV2Service:
    """RAG-based novel-to-script V2 pipeline service."""

    def __init__(self, llm, mock_mode: bool = False, config=None):
        """
        Args:
            llm: LangChain chat model (ChatOpenAI / ChatDeepSeek / ChatAnthropic)
            mock_mode: If True, return placeholder data without LLM calls
            config: Settings object (app.core.config.Settings)
        """
        self.llm = llm
        self.mock_mode = mock_mode
        self.config = config

        # Lazy-loaded embedding model
        self._embeddings = None

        # Configurable parameters
        self.chunk_size = getattr(config, 'N2S_V2_CHUNK_SIZE', 4096) if config else 4096
        self.chunk_overlap = getattr(config, 'N2S_V2_CHUNK_OVERLAP', 512) if config else 512
        self.top_k = getattr(config, 'N2S_V2_TOP_K', 5) if config else 5
        self.default_style = getattr(config, 'N2S_V2_DEFAULT_STYLE', 'ancient') if config else 'ancient'

        # FAISS disk cache directory
        cache_dir = getattr(config, 'N2S_V2_OUTPUT_DIR', '/app/data/output') if config else '/app/data/output'
        self._cache_dir = os.path.join(cache_dir, 'faiss_cache')
        os.makedirs(self._cache_dir, exist_ok=True)

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
        """Lazy-load the HuggingFace embedding model."""
        if self._embeddings is None:
            from langchain_huggingface import HuggingFaceEmbeddings
            model_name = getattr(self.config, 'N2S_V2_EMBEDDING_MODEL', 'all-MiniLM-L6-v2') if self.config else 'all-MiniLM-L6-v2'
            logger.info(f"Loading embedding model: {model_name}")
            self._embeddings = HuggingFaceEmbeddings(model_name=model_name)
        return self._embeddings

    # ================================================================
    # Stage 1: Build FAISS knowledge base
    # ================================================================

    def _build_knowledge_base(self, novel_text: str):
        """Chunk the novel, embed all chunks, build FAISS index (disk-cached).

        Returns (faiss_index, chunk_texts).
        """
        text_hash = self._text_hash(novel_text)

        # Try disk cache first
        if not self.mock_mode:
            cached = self._load_faiss_cache(text_hash)
            if cached is not None:
                # Re-chunk to get chunk_texts (needed for RAG retrieval)
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap,
                    separators=["\n\n", "\n", "。", "！", "？"]
                )
                chunks = splitter.split_text(novel_text)
                return cached, chunks

        # Build from scratch
        from langchain_community.vectorstores import FAISS
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", "。", "！", "？"]
        )
        chunks = splitter.split_text(novel_text)
        logger.info(f"Knowledge base: split into {len(chunks)} chunks")

        embeddings = self._get_embeddings()
        vector_store = FAISS.from_texts(chunks, embeddings)
        logger.info(f"Knowledge base: FAISS index built with {len(chunks)} vectors")

        # Persist to disk
        if not self.mock_mode:
            self._save_faiss_cache(text_hash, vector_store)

        return vector_store, chunks

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

        Returns list of {index, title, content}.
        """
        pattern = r'(?:^|\n)\s*(?:#{1,6}\s*)?第\s*([一二三四五六七八九十百千\d]+)\s*[回章节]'
        markers = [(m.start(), m.group(0).strip(), m.group(1))
                    for m in re.finditer(pattern, novel_text, re.MULTILINE)]

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

        logger.info(f"Chapter split: {len(chapters)} chapters (from {len(markers)} raw markers)")
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

    def _rag_search(self, vector_store, query: str, k: int = None) -> str:
        """Semantic search: retrieve top-k relevant chunks from the knowledge base."""
        if k is None:
            k = self.top_k
        retriever = vector_store.as_retriever(search_kwargs={"k": k})
        docs = retriever.invoke(query)
        context = "\n【关联前文检索内容】\n".join([d.page_content for d in docs])
        logger.debug(f"RAG search: retrieved {len(docs)} chunks for query[:100]={query[:100]}")
        return context

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
    ) -> dict:
        """Generate script for one chapter with RAG context and storyboard."""
        chapter_name = chapter.get("title", f"第{chapter['index']+1}章")
        chapter_content = chapter.get("content", "")
        episode_hint = chapter.get("episode_hint", "")

        # RAG: retrieve relevant context from the full novel
        rag_query = f"检索相关人物性格、过往剧情、场景设定、道具伏笔：{chapter_content[:1000]}"
        rag_context = self._rag_search(vector_store, rag_query)

        style_rule = self._get_style_instructions(style)

        logger.info(f"Generating script for {chapter_name}... "
                    f"content_len={len(chapter_content)}, rag_ctx_len={len(rag_context)}"
                    f"{', hint=' + episode_hint[:50] if episode_hint else ''}")

        if self.mock_mode:
            return {
                "chapter_title": chapter_name,
                "scene_number": scene_serial,
                "scene_type": "内景 白天",
                "location": "大殿",
                "characters": ["主角", "配角"],
                "props": ["宝剑"],
                "storyboard": [
                    {"shot_number": 1, "camera_type": "全景", "camera_movement": "固定",
                     "duration_seconds": 5.0, "description": "大殿全景，人物入场"},
                    {"shot_number": 2, "camera_type": "中景", "camera_movement": "推",
                     "duration_seconds": 4.0, "description": "角色对话场景"},
                ],
                "script_body": f"（大殿内，庄严肃穆）\n主角：（坚定）台词内容\n配角：（恭敬）台词内容",
            }

        try:
            messages = [
                SystemMessage(content=SYSTEM_GENERATE_CHAPTER_V2),
                HumanMessage(content=HUMAN_GENERATE_CHAPTER_V2.format(
                    global_info=global_info,
                    story_framework=global_info.get("story_framework", ""),
                    rag_context=rag_context,
                    chapter_name=chapter_name,
                    chapter_content=chapter_content[:6000],
                    style_rule=style_rule,
                    scene_serial=scene_serial,
                    episode_hint=episode_hint,
                )),
            ]
            response = await self.llm.ainvoke(messages, config={"timeout": 180})
            return self._parse_chapter_response(response.content, chapter_name, scene_serial)
        except Exception as e:
            logger.warning(f"Chapter script generation failed for {chapter_name}: {e}")
            return self._fallback_chapter_script(chapter, scene_serial)

    def _parse_chapter_response(self, response_text: str, chapter_title: str,
                                 scene_serial: str) -> dict:
        """Parse LLM text response into structured chapter script dict."""
        result = {
            "chapter_title": chapter_title,
            "scene_number": scene_serial,
            "scene_type": "",
            "location": "",
            "characters": [],
            "props": [],
            "storyboard": [],
            "script_body": response_text,
        }

        # Extract scene type
        type_match = re.search(r'【场景类型】(.+)', response_text)
        if type_match:
            result["scene_type"] = type_match.group(1).strip()

        # Extract location
        loc_match = re.search(r'【场景地点】(.+)', response_text)
        if loc_match:
            result["location"] = loc_match.group(1).strip()

        # Extract characters
        char_match = re.search(r'【出场角色】(.+)', response_text)
        if char_match:
            result["characters"] = [c.strip() for c in re.split(r'[、，,]', char_match.group(1)) if c.strip()]

        # Extract props
        prop_match = re.search(r'【核心道具】(.+)', response_text)
        if prop_match:
            result["props"] = [p.strip() for p in re.split(r'[、，,]', prop_match.group(1)) if p.strip()]

        # Extract storyboard table
        board_pattern = re.compile(
            r'镜号：(\d+)\s*\|\s*镜头类型：(.*?)\s*\|\s*运镜：(.*?)\s*\|\s*时长：(.*?)\s*\|\s*画面内容：(.*?)(?=镜号|【|$)',
            re.S
        )
        for m in board_pattern.finditer(response_text):
            try:
                dur_str = m.group(4).strip().replace('s', '').replace('秒', '')
                result["storyboard"].append({
                    "shot_number": int(m.group(1)),
                    "camera_type": m.group(2).strip(),
                    "camera_movement": m.group(3).strip(),
                    "duration_seconds": float(dur_str) if dur_str else 5.0,
                    "description": m.group(5).strip(),
                })
            except (ValueError, IndexError):
                continue

        return result

    def _fallback_chapter_script(self, chapter: dict, scene_serial: str) -> dict:
        """Fallback: return chapter content as basic script."""
        return {
            "chapter_title": chapter.get("title", f"章节{chapter.get('index', 0)+1}"),
            "scene_number": scene_serial,
            "scene_type": "内景 白天",
            "location": "未知场景",
            "characters": [],
            "props": [],
            "storyboard": [],
            "script_body": chapter.get("content", "")[:2000],
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
            from app.schemas.novel import ExtractEntitiesResponse
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
    # Full pipeline
    # ================================================================

    async def run_full_pipeline(
        self,
        novel_text: str,
        style: str = "",
        progress_callback: Optional[Callable[[int, str], Any]] = None,
        target_episodes: int = 0,
    ) -> Dict[str, Any]:
        """Execute the complete V2 novel-to-script pipeline.

        Args:
            novel_text: Full novel content
            style: Script style (ancient/suspense/comedy)
            progress_callback: Optional async callback(progress_pct, stage_name)
            target_episodes: Minimum episodes to produce (0=auto). Used for outlines.

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
        logger.info("=== V2 Stage 1/5: Building FAISS knowledge base ===")
        if progress_callback:
            await progress_callback(10, "构建知识库")
        vector_store, chunks = await asyncio.to_thread(
            self._build_knowledge_base, novel_text
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

        # --- Stage 3b: Story Development — expand outline into rich story framework ---
        logger.info("=== V2 Stage 3b/5: Developing story framework ===")
        if progress_callback:
            await progress_callback(35, "扩展故事框架")
        story_framework = await self._develop_story_framework(
            story_input=novel_text,
            target_episodes=max(target_episodes, len(chapters)),
            style=style,
        )
        result["story_framework"] = story_framework
        # Enrich global_info with the developed framework for per-chapter generation
        global_info["story_framework"] = story_framework
        result["stages"]["story_framework"] = {"length": len(story_framework)}

        # --- Stage 4: Per-chapter script generation (parallel) ---
        logger.info(f"=== V2 Stage 4/5: Generating scripts for {len(chapters)} chapters "
                    f"(parallel, max {MAX_CONCURRENT_CHAPTERS} concurrent) ===")
        if progress_callback:
            await progress_callback(40, f"生成{len(chapters)}章剧本")
        sem = asyncio.Semaphore(MAX_CONCURRENT_CHAPTERS)
        completed = 0

        async def generate_one(i: int, chapter: dict) -> tuple:
            nonlocal completed
            scene_serial = f"SCENE-{str(i + 1).zfill(3)}"
            async with sem:
                result_ch = await self._generate_chapter_script(
                    chapter=chapter, global_info=global_info,
                    vector_store=vector_store, style=style,
                    scene_serial=scene_serial,
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
        all_chapters = [r[1] for r in results]

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

        # Build final concatenated script text with 第N集 markers for episode splitting
        parts = []
        episodes = []
        cn_nums = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十',
                   '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十',
                   '二十一', '二十二', '二十三', '二十四', '二十五', '二十六', '二十七', '二十八', '二十九', '三十',
                   '三十一', '三十二', '三十三', '三十四', '三十五', '三十六', '三十七', '三十八', '三十九', '四十',
                   '四十一', '四十二', '四十三', '四十四', '四十五', '四十六', '四十七', '四十八', '四十九', '五十']

        for i, ch in enumerate(all_chapters):
            ep_num = i + 1
            ep_cn = cn_nums[ep_num] if ep_num < len(cn_nums) else str(ep_num)
            ep_title = f"第{ep_cn}集"
            chapter_title = ch.get('chapter_title', '')

            episode_content = (
                f"{ep_title}\n\n"
                f"【场景编号】{ch.get('scene_number', '')}\n"
                f"【场景类型】{ch.get('scene_type', '')}\n"
                f"【场景地点】{ch.get('location', '')}\n\n"
                f"{ch.get('script_body', '')}"
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
        return result
