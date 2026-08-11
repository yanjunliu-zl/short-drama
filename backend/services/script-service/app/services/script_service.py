from typing import List, Optional, Dict, Any
import asyncio
import logging
import json
from uuid import uuid4
import time
from datetime import datetime, timezone

from sqlalchemy import select, func, update, delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.script import (
    ScriptUpdateRequest,
    ScriptFromNovelRequest,
    ScriptFromOutlineRequest,
    ScriptSplitRequest,
)
from app.utils.model_router import create_llm_client, provider_is_healthy
from app.services.generation_engine import ScriptGenerationEngine
from app.services.script_repository import ScriptRepository
from app.core.config import settings as app_settings
from langchain_core.messages import HumanMessage
from app.client.service_clients import VideoServiceClient, LLMServiceClient
from app.models import Script, GenerationTask, ScriptStatus, TaskStatus, ScriptSourceType
from app.core.database import AsyncSessionLocal
from app.services.usage_tracker import track_llm_usage

logger = logging.getLogger(__name__)

# Redis task status store — avoids MySQL transaction isolation issues
import redis.asyncio as aioredis
_task_redis: Optional[aioredis.Redis] = None
_TASK_TTL = 7200  # 2 hours


async def _get_task_redis() -> aioredis.Redis:
    global _task_redis
    if _task_redis is None:
        _task_redis = aioredis.from_url(
            f"redis://{app_settings.REDIS_HOST}:{app_settings.REDIS_PORT}/{app_settings.REDIS_DB}",
            socket_connect_timeout=3,
        )
    return _task_redis


async def _task_set(task_id: str, data: dict):
    """Write task status to Redis (immediately visible, no isolation)."""
    try:
        r = await _get_task_redis()
        await r.setex(f"task:{task_id}", _TASK_TTL, json.dumps(data, default=str))
    except Exception as e:
        logger.warning(f"Redis task write failed (non-critical): {e}")


async def _task_get(task_id: str) -> Optional[dict]:
    """Read task status from Redis."""
    try:
        r = await _get_task_redis()
        raw = await r.get(f"task:{task_id}")
        return json.loads(raw) if raw else None
    except Exception:
        return None


class ScriptService:
    """剧本生成服务，集成LangChain和LangGraph，使用SQLAlchemy持久化"""

    def __init__(self):
        # LLM client (lazy init via initialize())
        self.llm = None
        self._mock_mode = False
        self.repo = ScriptRepository()  # DB operations

        # 初始化微服务客户端
        self.video_client: Optional[VideoServiceClient] = None
        self.llm_client: Optional[LLMServiceClient] = None

        self._initialized = False

    # ---------- 中文数字工具 ----------

    @staticmethod
    def _parse_chinese_numeral(s: str) -> int:
        """解析中文数字字符串（或纯数字字符串）为整数"""
        s = s.strip()
        if s.isdigit():
            return int(s)
        digit_map = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
                     '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
        # 已映射常见值
        if s in digit_map:
            return digit_map[s]
        # 处理"十N"（十一..十九）和"X十"（二十..九十）和"X十N"（二十一..九十九）
        if '十' in s:
            prefix, _, suffix = s.partition('十')
            base = digit_map.get(prefix, 1) * 10
            if suffix:
                base += digit_map.get(suffix, 0)
            return base
        # 百
        if '百' in s:
            prefix, _, suffix = s.partition('百')
            base = digit_map.get(prefix, 1) * 100
            if suffix:
                base += ScriptService._parse_chinese_numeral(suffix)
            return base
        # 千
        if '千' in s:
            prefix, _, suffix = s.partition('千')
            base = digit_map.get(prefix, 1) * 1000
            if suffix:
                base += ScriptService._parse_chinese_numeral(suffix)
            return base
        # 万
        if '万' in s:
            prefix, _, suffix = s.partition('万')
            base = digit_map.get(prefix, 1) * 10000
            if suffix:
                base += ScriptService._parse_chinese_numeral(suffix)
            return base
        # 最后兜底：逐字转换简单拼接（不完整，但覆盖大多数情况）
        result = 0
        for ch in s:
            if ch in digit_map:
                result = result * 10 + digit_map[ch]
        return result if result > 0 else 1

    @staticmethod
    def _split_content_to_episodes(content: str) -> list:
        """
        将完整剧本内容按「第N集」标记拆分为分集列表。
        如果没有检测到分集标记，整篇作为一个 episode 返回。

        返回 list[dict]: 每个 dict 包含 episode_number, title, content
        """
        import re

        episodes: list = []
        # 匹配 第X集（中文数字或阿拉伯数字），大小写不敏感
        pattern = re.compile(r'第\s*([一二三四五六七八九十百千万\d]+)\s*集', re.IGNORECASE)

        markers = list(pattern.finditer(content))

        if not markers:
            # 无分集标记：整篇作为一个 episode
            trimmed = content.strip()
            if trimmed:
                episodes.append({
                    "episode_number": 1,
                    "title": "完整剧本",
                    "content": trimmed,
                })
            return episodes

        for i, match in enumerate(markers):
            start = match.end()  # 内容从「第N集」标记之后开始
            end = markers[i + 1].start() if i + 1 < len(markers) else len(content)
            episode_num_str = match.group(1)

            episode_number = ScriptService._parse_chinese_numeral(episode_num_str)

            episode_content = content[start:end].strip()
            # 过滤无效内容（太短的视为误匹配，跳过）
            if len(episode_content) < 50:
                continue
            episodes.append({
                "episode_number": episode_number,
                "title": f"第{episode_num_str}集",
                "content": episode_content,
            })

        return episodes

    # ---------- 初始化 ----------
    async def initialize(self):
        """初始化服务"""
        if self._initialized:
            return
        try:
            logger.info("初始化ScriptService...")
            self.llm = create_llm_client(prefer="deepseek", timeout=180.0)
            self._mock_mode = not provider_is_healthy()
            self._initialized = True
            logger.info(f"ScriptService初始化完成 (mock={self._mock_mode})")
        except Exception as e:
            logger.error(f"ScriptService初始化失败: {e}")
            raise

    def _get_db(self) -> AsyncSession:
        """获取数据库会话"""
        return AsyncSessionLocal()


    @staticmethod
    def _num_to_cn(n: int) -> str:
        """数字转中文（1-99）"""
        if n <= 0: return str(n)
        digits = ['', '一','二','三','四','五','六','七','八','九']
        if n <= 10: return digits[n] if n <= 9 else '十'
        if n < 20: return '十' + digits[n-10]
        if n < 100: return digits[n//10] + '十' + (digits[n%10] if n%10 else '')
        return str(n)

    def _merge_characters(self, all_chars: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """合并去重角色：按 name 去重，保留最详细的 description，合并 role"""
        merged = {}
        for c in all_chars:
            name = c.get("name", "").strip()
            if not name:
                continue
            if name in merged:
                existing = merged[name]
                # 保留更详细的描述
                if len(c.get("description", "")) > len(existing.get("description", "")):
                    existing["description"] = c["description"]
                # 主角 > 反派 > 配角 > 群众
                role_priority = {"主角": 0, "反派": 1, "配角": 2, "群众": 3}
                if role_priority.get(c.get("role", ""), 3) < role_priority.get(existing.get("role", ""), 3):
                    existing["role"] = c["role"]
            else:
                merged[name] = dict(c)
        return list(merged.values())

    def _derive_locations_from_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """从事件列表中提取并去重地点"""
        locations = {}
        for e in events:
            loc = e.get("location", "").strip()
            if loc and loc not in locations:
                locations[loc] = {"name": loc, "description": ""}
        return list(locations.values())

    def _build_shot_episodes(self, storyboard: list, episodes: list) -> list:
        """Convert V2 storyboard flat list to ShotEpisode format for frontend.

        V2 storyboard shot: {shot_number, camera_type, camera_movement,
                             duration_seconds, description, _chapter, _scene}
        Target Shot: {id, number, shotType, duration, description, cameraAngle, sceneRef, ...}
        """
        if not storyboard:
            return []

        # Group shots by _chapter → map to episode number
        shot_episodes: Dict[str, list] = {}
        for shot in storyboard:
            ch = shot.get("_chapter", "")
            if ch not in shot_episodes:
                shot_episodes[ch] = []
            shot_episodes[ch].append(shot)

        result = []
        global_id = 0
        ep_list = episodes or []

        for ep_idx, (chapter, shots) in enumerate(shot_episodes.items()):
            ep_num = ep_idx + 1
            # Find matching episode title from stored episodes
            ep_title = f"第{self._num_to_cn(ep_num)}集"
            if ep_idx < len(ep_list):
                ep_title = ep_list[ep_idx].get("title", ep_title)

            shot_list = []
            for s in shots:
                global_id += 1
                dur = s.get("duration_seconds", 5)
                shot_list.append({
                    "id": global_id,
                    "number": s.get("shot_number", global_id),
                    "shotType": s.get("camera_type", "中景"),
                    "duration": int(dur) if dur else 5,
                    "cameraAngle": "正面平视",
                    "sceneRef": s.get("_scene", ""),
                    "characters": [],
                    "description": s.get("description", ""),
                    "dialogue": "",
                    "soundEffects": [],
                    "music": "",
                    "notes": s.get("camera_movement", ""),
                    "imagePrompt": None,
                    "imagePromptZh": None,
                    "videoPrompt": None,
                    "videoPromptZh": None,
                })
            result.append({
                "id": f"ep-{ep_num}",
                "title": ep_title,
                "number": ep_num,
                "shots": shot_list,
                "description": "",
            })

        logger.info(f"Built ShotEpisodes: {len(result)} episodes, {global_id} shots")
        return result

    async def generate_script_from_novel_async(self, task_id: str, request: ScriptFromNovelRequest):
        """异步从小说生成剧本 — V2 RAG-based pipeline"""
        t_total = time.time()
        async with self._get_db() as db:
            try:
                if not self._initialized:
                    await self.initialize()

                novel_content = getattr(request, 'novel_content', '') or ''
                logger.info(f"[小说→剧本] 开始 task={task_id} title={request.title} novel_len={len(novel_content)} style={request.style}")

                # Task status via Redis — immediately visible, no isolation issues
                await _task_set(task_id, {"status": "processing", "progress": 5, "title": request.title})

                task = await db.get(GenerationTask, task_id)
                if not task:
                    task = GenerationTask(
                        task_id=task_id, status=TaskStatus.PROCESSING.value,
                        progress=5, start_time=time.time(),
                    )
                    db.add(task)
                else:
                    task.status = TaskStatus.PROCESSING.value
                    task.progress = 5
                await db.flush()
                await db.commit()

                await self._generate_from_novel_v2(task_id, request, task, db, novel_content)
                return

            except Exception as e:
                logger.error(f"[小说→剧本] 异常失败 task={task_id} 耗时={time.time()-t_total:.1f}s: {e}")
                await db.rollback()

    # ================================================================
    # V2: RAG-based novel-to-script pipeline
    # ================================================================

    async def _generate_from_novel_v2(
        self, task_id: str, request: ScriptFromNovelRequest,
        task: GenerationTask, db, novel_content: str
    ):
        """Execute the V2 RAG-based novel-to-script pipeline."""
        t_total = time.time()
        try:
            mock_mode = self._mock_mode
            style = getattr(request, 'style', '') or app_settings.N2S_V2_DEFAULT_STYLE

            n2s_v2 = ScriptGenerationEngine(
                llm=self.llm if not mock_mode else None,
                mock_mode=mock_mode,
                config=app_settings,
            )

            async def progress_callback(pct: int, stage: str):
                task.progress = pct
                await db.commit()
                await _task_set(task_id, {"status": "processing", "progress": pct, "title": request.title, "stage": stage})
                logger.info(f"[V2] 进度 {pct}% — {stage} task={task_id}")

            result = await n2s_v2.generate_from_novel(
                novel_text=novel_content,
                style=style,
                progress_callback=progress_callback,
            )

            final_script = result.get("final_script", "")
            if not final_script:
                raise ValueError("V2 pipeline produced empty script")

            # Use episodes from V2 pipeline (built with 第N集 markers), fallback to regex split
            episodes = result.get("episodes") or self._split_content_to_episodes(final_script)
            characters_data = result.get("characters", [])
            character_graph = result.get("character_graph", {})
            storyboard_data = result.get("storyboard", [])
            entities_data = result.get("entities", {})

            # Use extracted entities for characters/locations/props when available
            extracted_characters = entities_data.get("characters", [])
            extracted_locations = entities_data.get("locations", [])
            extracted_props = entities_data.get("props", [])

            # Build events-compatible analysis_result for downstream consumers
            analysis_events = []
            for ch in result.get("script_scenes", []):
                analysis_events.append({
                    "index": ch.get("scene_number", ""),
                    "title": ch.get("chapter_title", ""),
                    "description": ch.get("script_body", "")[:200],
                    "characters_involved": ch.get("characters", []),
                    "location": ch.get("location", ""),
                    "is_major": True,
                })

            script = Script(
                task_id=task_id,
                title=request.title,
                content=final_script,
                episodes=episodes,
                theme=getattr(request, 'theme', ''),
                length=getattr(request, 'length', '短篇'),
                style=style,
                setting=getattr(request, 'setting', ''),
                characters=json.dumps(extracted_characters, ensure_ascii=False) if extracted_characters else (
                    json.dumps(characters_data, ensure_ascii=False) if characters_data else None
                ),
                source_type="novel",
                source_content=novel_content[:500],
                status=ScriptStatus.COMPLETED.value,
                user_id=str(getattr(request, 'user_id', '')),
                pipeline_version="v2",
                character_graph=character_graph if character_graph else None,
                storyboard=storyboard_data if storyboard_data else None,
                workflow_metadata={
                    "pipeline": "v2_rag_chapter_based",
                    "stages": result.get("stages", {}),
                    "story_framework": result.get("story_framework", ""),
                },
                analysis_result={
                    "events": analysis_events,
                    "locations": extracted_locations,
                    "props": extracted_props,
                    "global_characters": characters_data,
                },
            )
            db.add(script)
            await db.flush()

            task.status = TaskStatus.COMPLETED.value
            task.progress = 100
            task.script_id = script.id
            await _task_set(task_id, {"status": "completed", "progress": 100, "title": request.title, "script_id": script.id})
            task.end_time = time.time()
            await db.commit()

            logger.info(f"[V2] 完成 script_id={script.id}, {len(episodes)}集, "
                        f"{len(characters_data)}角色, {len(storyboard_data)}分镜, "
                        f"总长度={len(final_script)} 总耗时={time.time()-t_total:.1f}s")

            # Record business metrics for Grafana
            try:
                from app.middleware.prometheus import BusinessMetrics
                BusinessMetrics.record_script_generation(
                    script_type="novel", status="success",
                    duration=time.time() - t_total)
            except Exception:
                pass

            # Track usage — V2 makes N+2 LLM calls (global extract + N chapters + entity extract)
            from app.services.usage_tracker import estimate_tokens
            chapter_count = len(result.get("script_scenes", []))
            call_count = chapter_count + 2 if chapter_count > 0 else 1
            # Total input: novel(full) + per-chapter prompts + entity extraction prompt
            estimated_in = estimate_tokens(novel_content) * 2  # novel read twice (global + per-chapter RAG)
            estimated_out = estimate_tokens(final_script)
            await track_llm_usage(
                user_id=str(getattr(request, 'user_id', '')),
                model_name="deepseek-chat",
                tokens_in=estimated_in,
                tokens_out=estimated_out,
                call_count=call_count,
                duration_ms=int((time.time() - t_total) * 1000),
                endpoint="/generate/from-novel",
                service_name="script-service",
            )

        except Exception as e:
            logger.error(f"[V2] 异常失败 task={task_id} 耗时={time.time()-t_total:.1f}s: {e}")
            await db.rollback()
            try:
                task.status = TaskStatus.FAILED.value
                task.error = str(e)
                task.end_time = time.time()
                await db.commit()
            except Exception:
                pass

    async def get_script(self, script_id) -> Optional[dict]:
        """获取剧本详情，委托给 ScriptRepository"""
        return await self.repo.get_script(int(script_id))

    async def get_script_character_graph(self, script_id: int) -> Optional[dict]:
        return await self.repo.get_character_graph(script_id)

    async def upload_and_split_script(self, request: ScriptSplitRequest) -> dict:
        """
        上传完整剧本，拆分为分集，持久化到数据库。
        同步操作，无需后台任务。
        """
        async with self._get_db() as db:
            try:
                title = request.title.strip()
                content = request.content.strip()
                user_id = str(getattr(request, 'user_id', '') or '')

                if not content:
                    raise ValueError("剧本内容不能为空")
                if not title:
                    raise ValueError("剧本标题不能为空")

                # 拆分为分集
                episodes = self._split_content_to_episodes(content)

                # 持久化到数据库
                script = Script(
                    title=title,
                    content=content,
                    episodes=episodes,
                    source_type=ScriptSourceType.MANUAL.value,
                    status=ScriptStatus.COMPLETED.value,
                    user_id=user_id,
                )
                db.add(script)
                await db.commit()
                await db.refresh(script)

                logger.info(f"剧本上传并分集完成，剧本ID: {script.id}, 共 {len(episodes)} 集")

                return {
                    "script_id": script.id,
                    "title": title,
                    "episodes": episodes,
                    "total_episodes": len(episodes),
                }

            except ValueError as e:
                raise e
            except Exception as e:
                logger.error(f"剧本上传分集失败: {e}")
                await db.rollback()
                raise
