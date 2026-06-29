"""
ViMax 风格小说转剧本多阶段流水线

阶段: Compress → Extract Characters → Extract Events → Write Script → Enhance
"""
import asyncio
import logging
import re
import time
from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.prompts import (
    SYSTEM_COMPRESS_NOVEL_CHUNK, HUMAN_COMPRESS_NOVEL_CHUNK,
    SYSTEM_AGGREGATE_CHUNKS, HUMAN_AGGREGATE_CHUNKS,
    SYSTEM_EXTRACT_CHARACTERS, HUMAN_EXTRACT_CHARACTERS,
    SYSTEM_EXTRACT_EVENTS, HUMAN_EXTRACT_EVENTS,
    SYSTEM_DEVELOP_STORY, HUMAN_DEVELOP_STORY,
    SYSTEM_WRITE_SCRIPT, HUMAN_WRITE_SCRIPT,
    SYSTEM_ENHANCE_SCRIPT, HUMAN_ENHANCE_SCRIPT,
    SYSTEM_EXTRACT_ENTITIES, HUMAN_EXTRACT_ENTITIES,
)
from app.schemas.novel import (
    ExtractCharactersResponse,
    ExtractEventsResponse,
    WriteScriptResponse,
    EnhanceScriptResponse,
    ExtractEntitiesResponse,
)

logger = logging.getLogger(__name__)


class Novel2ScriptService:
    """小说转剧本多阶段流水线服务"""

    def __init__(self, llm: ChatOpenAI, mock_mode: bool = False):
        self.llm = llm
        self.mock_mode = mock_mode
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=65536,
            chunk_overlap=8192,
        )

    # ================================================================
    # 阶段1: 小说压缩
    # ================================================================

    def split_novel(self, novel_text: str) -> List[str]:
        """将长篇小说分割为可处理的块"""
        return self.splitter.split_text(novel_text)

    async def compress_chunk(self, sem: asyncio.Semaphore, index: int, chunk: str) -> tuple:
        """压缩单个小说块"""
        async with sem:
            logger.info(f"压缩小说块 {index}...")
            if self.mock_mode:
                await asyncio.sleep(0.3)
                return index, chunk[:2000]

            messages = [
                SystemMessage(content=SYSTEM_COMPRESS_NOVEL_CHUNK),
                HumanMessage(content=HUMAN_COMPRESS_NOVEL_CHUNK.format(novel_chunk=chunk)),
            ]
            response = await self.llm.ainvoke(messages)
            return index, response.content

    async def compress_novel(self, novel_text: str, max_concurrent: int = 3) -> str:
        """完整小说压缩流程：分割 → 并发压缩 → 聚合"""
        chunks = self.split_novel(novel_text)
        logger.info(f"小说分割为 {len(chunks)} 块")

        if len(chunks) <= 1:
            # 短文本直接返回
            if self.mock_mode:
                return novel_text
            messages = [
                SystemMessage(content=SYSTEM_COMPRESS_NOVEL_CHUNK),
                HumanMessage(content=HUMAN_COMPRESS_NOVEL_CHUNK.format(novel_chunk=novel_text)),
            ]
            response = await self.llm.ainvoke(messages)
            return response.content

        # 并发压缩各块
        sem = asyncio.Semaphore(max_concurrent)
        tasks = [self.compress_chunk(sem, i, chunk) for i, chunk in enumerate(chunks)]
        results = await asyncio.gather(*tasks)
        compressed_chunks = [content for _, content in sorted(results, key=lambda x: x[0])]

        # 聚合压缩后的块
        if self.mock_mode:
            return "\n\n".join(compressed_chunks)

        chunks_str = "\n".join([
            f"<CHUNK_{i}_START>\n{chunk}\n<CHUNK_{i}_END>"
            for i, chunk in enumerate(compressed_chunks)
        ])
        messages = [
            SystemMessage(content=SYSTEM_AGGREGATE_CHUNKS),
            HumanMessage(content=HUMAN_AGGREGATE_CHUNKS.format(chunks=chunks_str)),
        ]
        response = await self.llm.ainvoke(messages)
        return response.content

    # ================================================================
    # 阶段2: 角色提取
    # ================================================================

    async def extract_characters(self, story: str) -> List[Dict[str, Any]]:
        """从故事中提取角色"""
        logger.info(f"提取角色... 输入长度={len(story)}")
        t0 = time.time()
        if self.mock_mode:
            return [
                {"name": "主角", "role": "主角", "description": "故事中的主要角色"},
                {"name": "配角", "role": "配角", "description": "辅助角色"},
            ]

        structured_model = self.llm.with_structured_output(ExtractCharactersResponse, method="json_mode")
        messages = [
            SystemMessage(content=SYSTEM_EXTRACT_CHARACTERS),
            HumanMessage(content=HUMAN_EXTRACT_CHARACTERS.format(script=story)),
        ]
        response: ExtractCharactersResponse = await structured_model.ainvoke(messages)
        result = [c.model_dump() for c in response.characters]
        logger.info(f"提取角色完成: {len(result)}个 耗时={time.time()-t0:.1f}s")
        return result

    # ================================================================
    # 阶段3: 事件提取
    # ================================================================

    async def extract_events(self, story: str) -> List[Dict[str, Any]]:
        """从故事中提取关键事件"""
        logger.info(f"提取事件... 输入长度={len(story)}")
        t0 = time.time()
        if self.mock_mode:
            return [
                {"index": 0, "title": "开场", "description": "故事的开始",
                 "characters_involved": ["主角"], "location": "开场地点", "is_major": True},
                {"index": 1, "title": "发展", "description": "故事的发展",
                 "characters_involved": ["主角", "配角"], "location": "发展地点", "is_major": True},
            ]

        structured_model = self.llm.with_structured_output(ExtractEventsResponse, method="json_mode")
        messages = [
            SystemMessage(content=SYSTEM_EXTRACT_EVENTS),
            HumanMessage(content=HUMAN_EXTRACT_EVENTS.format(story=story)),
        ]
        response: ExtractEventsResponse = await structured_model.ainvoke(messages)
        result = [e.model_dump() for e in response.events]
        logger.info(f"提取事件完成: {len(result)}个 耗时={time.time()-t0:.1f}s")
        return result

    # ================================================================
    # 阶段4: 编剧生成（故事+剧本）
    # ================================================================

    async def develop_story(self, compressed_novel: str, user_requirement: str = "") -> str:
        """基于压缩小说发展完整故事"""
        logger.info(f"发展故事... 输入长度={len(compressed_novel)}")
        t0 = time.time()
        if self.mock_mode:
            return compressed_novel

        requirement = user_requirement or "Short drama script, 3-5 scenes, visual storytelling style"
        # Truncate input to avoid timeout
        idea_text = compressed_novel[:4000]
        if len(compressed_novel) > 4000:
            idea_text += "\n\n[...故事后续部分已省略，基于前文继续创作...]"

        messages = [
            SystemMessage(content=SYSTEM_DEVELOP_STORY),
            HumanMessage(content=HUMAN_DEVELOP_STORY.format(
                idea=idea_text,
                user_requirement=requirement,
            )),
        ]
        try:
            response = await self.llm.ainvoke(messages, config={"timeout": 300})
            logger.info(f"发展故事完成: 输出长度={len(response.content)} 耗时={time.time()-t0:.1f}s")
            return response.content
        except Exception:
            logger.warning(f"develop_story 超时 (300s)，跳过此阶段")
            return compressed_novel

    async def write_script(self, story: str, user_requirement: str = "") -> List[str]:
        """将故事转为分场剧本"""
        logger.info(f"编写剧本... 输入长度={len(story)}")
        t0 = time.time()
        if self.mock_mode:
            return [story] if isinstance(story, str) else story

        requirement = user_requirement or "Short drama format, each scene as a continuous string"
        story_text = story[:6000] if len(story) > 6000 else story

        try:
            structured_model = self.llm.with_structured_output(WriteScriptResponse, method="json_mode")
            messages = [
                SystemMessage(content=SYSTEM_WRITE_SCRIPT),
                HumanMessage(content=HUMAN_WRITE_SCRIPT.format(
                    story=story_text,
                    user_requirement=requirement,
                )),
            ]
            response: WriteScriptResponse = await structured_model.ainvoke(messages, config={"timeout": 300})
            logger.info(f"编写剧本完成: {len(response.script)}场 耗时={time.time()-t0:.1f}s")
            return response.script
        except Exception as e:
            logger.warning(f"write_script 失败 (耗时={time.time()-t0:.1f}s): {e}，使用备用方案")
            # Fallback: AI 超时时，按章节（第X回/第X章）拆分原文，封装为剧集格式
            return self._fallback_split_to_episodes(story_text, user_requirement)

    @staticmethod
    def _fallback_split_to_episodes(text: str, user_requirement: str = "") -> List[str]:
        """AI 失败时的备用方案：按章节标记将原文拆分为剧集（去重处理）"""
        # 匹配所有第X回/第X章，记录位置和编号
        marker_pattern = re.compile(r'(?:^|\n)\s*(?:#{1,6}\s*)?第\s*([一二三四五六七八九十百千\d]+)\s*[回章节]', re.MULTILINE)
        markers = [(m.start(), m.group(1)) for m in marker_pattern.finditer(text)]

        if len(markers) < 2:
            return [f"第一集\n\n{text.strip()}"]

        # 去重：同一编号只保留第一次出现
        seen_nums = set()
        unique_markers = []
        for pos, num in markers:
            if num not in seen_nums:
                seen_nums.add(num)
                unique_markers.append((pos, num))

        episodes = []
        cn_nums = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']
        for i in range(len(unique_markers)):
            if i >= 10:
                break
            start_pos = unique_markers[i][0]
            end_pos = unique_markers[i + 1][0] if i + 1 < len(unique_markers) else len(text)
            chapter_text = text[start_pos:end_pos].strip()

            ep_num = i + 1
            num_str = cn_nums[ep_num] if ep_num <= 10 else str(ep_num)
            # 用集替换章/回
            episode_content = marker_pattern.sub(f'第{num_str}集', chapter_text, count=1)
            episodes.append(f"第{num_str}集\n\n{episode_content}")

        logger.info(f"备用方案：从原文去重拆分为 {len(episodes)} 集")
        return episodes

    # ================================================================
    # 阶段5: 剧本增强
    # ================================================================

    async def enhance_script(self, scenes: List[str]) -> List[str]:
        """增强剧本（对话优化、节奏调整）"""
        logger.info(f"增强剧本... {len(scenes)}场")
        t0 = time.time()
        if self.mock_mode or not scenes:
            return scenes

        # DeepSeek structured output 不稳定，使用纯文本增强
        enhanced = []
        failed = 0
        for i, scene in enumerate(scenes):  # 增强所有场景
            logger.info(f"增强第{i+1}/{len(scenes)}场... 长度={len(scene)}")
            prompt = f"""请对以下剧本场景进行优化增强，改进对话的自然度和画面的可视化描述，保持剧情不变。

原剧本：
{scene[:3000]}

返回增强后的完整剧本场景，不要添加任何解释。
注意：如果原剧本以"第X集"（如第一集、第二集）开头的剧集标记行，必须完整保留该行不变。"""
            try:
                response = await self.llm.ainvoke(prompt)
                enhanced.append(response.content)
            except Exception as e:
                logger.warning(f"增强第{i+1}场失败: {e}，保留原文")
                enhanced.append(scene)
                failed += 1

        # 补充未增强的场景
        if len(enhanced) < len(scenes):
            enhanced.extend(scenes[len(enhanced):])

        logger.info(f"增强剧本完成: {len(enhanced)}场 失败={failed} 耗时={time.time()-t0:.1f}s")
        return enhanced

    # ================================================================
    # 辅助: 章节检测
    # ================================================================

    @staticmethod
    def detect_chapter_count(novel_text: str) -> int:
        """检测小说的章节/回数（去重计数，支持多种格式）"""
        # 格式1: 第X回/章/节（行首，可能有 ## 等 markdown 标记）
        pattern = r'(?:^|\n)\s*(?:#{1,6}\s*)?第\s*([一二三四五六七八九十百千\d]+)\s*[回章节]'
        matches = re.findall(pattern, novel_text, re.MULTILINE)
        if matches and len(matches) >= 2:
            unique = list(dict.fromkeys(matches))
            logger.info(f"检测到 {len(unique)} 个不重复章节 (行首): {unique[:10]}")
            return min(len(unique), 50)
        # 格式2: 任意位置的第X回/章（放宽限制）
        pattern2 = r'第\s*([一二三四五六七八九十百千\d]+)\s*[回章节]'
        matches2 = re.findall(pattern2, novel_text)
        if matches2 and len(matches2) >= 2:
            unique = list(dict.fromkeys(matches2))
            logger.info(f"检测到 {len(unique)} 个不重复章节 (全文): {unique[:10]}")
            return min(len(unique), 50)
        # 格式3: 英文 Chapter
        eng = re.findall(r'Chapter\s+(\d+)', novel_text, re.IGNORECASE)
        if eng and len(eng) >= 2:
            unique = list(dict.fromkeys(eng))
            return min(len(unique), 50)
        return 0

    @staticmethod
    def build_user_requirement(novel_text: str, original_requirement: str = "") -> str:
        """根据小说内容构建用户需求，自动检测章节数"""
        chapter_count = Novel2ScriptService.detect_chapter_count(novel_text)

        if original_requirement:
            base = original_requirement
        else:
            base = "Short drama script, visual storytelling style"

        if chapter_count >= 2:
            return (
                f"{base}. "
                f"The novel has {chapter_count} chapters. "
                f"Create a {chapter_count}-episode short drama script. "
                f"Each episode must start with a clear marker: '第N集' (e.g. '第一集', '第二集', ...). "
                f"Each episode should cover the content of the corresponding novel chapter. "
                f"Each episode should have 3-6 scenes."
            )
        else:
            return (
                f"{base}. "
                f"Create a multi-episode short drama script based on the story structure. "
                f"Divide the script into logical episodes (typically 3-6 episodes). "
                f"Each episode must start with a clear marker: '第N集' (e.g. '第一集', '第二集', ...). "
                f"Each episode should have 3-6 scenes."
            )

    # ================================================================
    # 完整流水线
    # ================================================================

    async def run_full_pipeline(self, novel_text: str, user_requirement: str = "") -> Dict[str, Any]:
        """执行完整小说转剧本流水线"""
        result = {
            "stages": {},
            "characters": [],
            "events": [],
            "script_scenes": [],
            "final_script": "",
        }

        # 构建包含剧集需求的用户要求
        effective_requirement = self.build_user_requirement(novel_text, user_requirement)
        chapter_count = self.detect_chapter_count(novel_text)
        logger.info(f"检测到 {chapter_count} 个章节，需求: {effective_requirement[:200]}...")

        # 阶段1: 压缩
        logger.info("=== 阶段1: 小说压缩 ===")
        compressed = await self.compress_novel(novel_text)
        result["stages"]["compressed"] = {"length": len(compressed)}

        # 阶段2: 角色提取
        logger.info("=== 阶段2: 角色提取 ===")
        result["characters"] = await self.extract_characters(compressed)
        result["stages"]["characters"] = {"count": len(result["characters"])}

        # 阶段3: 事件提取
        logger.info("=== 阶段3: 事件提取 ===")
        result["events"] = await self.extract_events(compressed)
        result["stages"]["events"] = {"count": len(result["events"])}

        # 阶段4: 故事发展 + 剧本编写
        logger.info("=== 阶段4: 编剧生成 ===")
        story = await self.develop_story(compressed, effective_requirement)
        result["script_scenes"] = await self.write_script(story, effective_requirement)
        result["stages"]["script"] = {"scenes": len(result["script_scenes"])}

        # 阶段5: 增强
        logger.info("=== 阶段5: 剧本增强 ===")
        enhanced = await self.enhance_script(result["script_scenes"])
        result["script_scenes"] = enhanced
        result["stages"]["enhanced"] = {"scenes": len(enhanced)}

        # 合并为最终剧本
        result["final_script"] = "\n\n".join(enhanced)
        result["stages"]["final"] = {"total_length": len(result["final_script"])}

        logger.info(f"流水线完成: {len(result['characters'])} 角色, "
                     f"{len(result['events'])} 事件, "
                     f"{len(enhanced)} 场剧本, "
                     f"总长度 {len(result['final_script'])} 字符")

        return result

    # ================================================================
    # 阶段6: 主体提取
    # ================================================================

    async def extract_entities(self, script_content: str) -> Dict[str, Any]:
        """从剧本中提取角色、地点和道具"""
        logger.info(f"提取主体实体... 输入长度={len(script_content)}")
        t0 = time.time()
        if self.mock_mode:
            return {
                "characters": [
                    {"name": "主角", "role": "主角", "description": "故事主人公"},
                    {"name": "配角", "role": "配角", "description": "辅助角色"},
                ],
                "locations": [
                    {"name": "城市街道", "description": "故事发生的主要场景"},
                ],
                "props": [
                    {"name": "手机", "description": "关键道具"},
                ],
            }

        try:
            structured_model = self.llm.with_structured_output(ExtractEntitiesResponse, method="json_mode")
            # Truncate if too long (increased from 8000 for better coverage)
            text = script_content[:32000] if len(script_content) > 32000 else script_content
            messages = [
                SystemMessage(content=SYSTEM_EXTRACT_ENTITIES),
                HumanMessage(content=HUMAN_EXTRACT_ENTITIES.format(script=text)),
            ]
            response: ExtractEntitiesResponse = await structured_model.ainvoke(messages, config={"timeout": 60})
            result = {
                "characters": [c.model_dump() for c in response.characters],
                "locations": [l.model_dump() for l in response.locations],
                "props": [p.model_dump() for p in response.props],
            }
            logger.info(f"实体提取完成: {len(result['characters'])}角色 {len(result['locations'])}地点 "
                        f"{len(result['props'])}道具 耗时={time.time()-t0:.1f}s")
            return result
        except Exception as e:
            logger.warning(f"实体提取失败 (耗时={time.time()-t0:.1f}s): {e}，使用备用方案")
            # Fallback: basic regex extraction
            return self._fallback_extract_entities(script_content)

    def _fallback_extract_entities(self, content: str) -> Dict[str, Any]:
        """备用方案：基于正则的简单提取"""
        import re
        characters = []
        locations = []
        props = []

        # 提取角色名（中文名+冒号格式）
        char_pattern = re.findall(r'\n([^\s：:]{2,4})[：:]', content)
        seen = set()
        for c in char_pattern:
            if c not in seen and not c.startswith(('【', '第', '场', 'Scene')):
                seen.add(c)
                characters.append({"name": c, "role": "", "description": ""})

        # 提取地点
        loc_pattern = re.findall(r'【场景[^】]*[：:]([^—\-—]+)', content)
        for l in loc_pattern[:10]:
            loc = l.strip()
            if loc and len(loc) < 30:
                locations.append({"name": loc, "description": ""})

        # 提取道具关键词
        item_keywords = ['手机', '电脑', 'U盘', '文件', '照片', '箱子', '纸条', '名片', '信', '钥匙', '日记', '密码锁', '刀', '枪', '子弹', '血', '针', '药']
        for item in item_keywords:
            if item in content:
                props.append({"name": item, "description": ""})

        return {"characters": characters, "locations": locations, "props": props}
