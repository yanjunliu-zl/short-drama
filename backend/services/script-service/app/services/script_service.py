from typing import List, Optional, Dict, Any
import asyncio
import logging
import json
from uuid import uuid4
import time
from datetime import datetime, timezone

from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.script import (
    ScriptUpdateRequest,
    ScriptGenerationRequest,
    ScriptFromNovelRequest,
    ScriptFromOutlineRequest,
    ScriptSplitRequest,
)
from app.services.ai_service import AIService
from app.services.workflow import ScriptWorkflow
from app.services.novel2script_v2_service import Novel2ScriptV2Service
from app.core.config import settings as app_settings
from langchain_core.messages import HumanMessage
from app.client.service_clients import VideoServiceClient, LLMServiceClient
from app.models import Script, GenerationTask, ScriptStatus, TaskStatus, ScriptSourceType
from app.core.database import AsyncSessionLocal
from app.services.usage_tracker import track_llm_usage

logger = logging.getLogger(__name__)


class ScriptService:
    """剧本生成服务，集成LangChain和LangGraph，使用SQLAlchemy持久化"""

    def __init__(self):
        # 初始化AI服务和工作流
        self.ai_service = AIService()
        self.workflow = ScriptWorkflow(self.ai_service)

        # 初始化微服务客户端
        self.video_client: Optional[VideoServiceClient] = None
        self.llm_client: Optional[LLMServiceClient] = None

        # 初始化标志
        self._initialized = False
        self._clients_initialized = False

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
            await self.ai_service.initialize()
            await self.workflow.initialize()
            self._initialized = True
            logger.info("ScriptService初始化完成")
        except Exception as e:
            logger.error(f"ScriptService初始化失败: {e}")
            raise

    def _get_db(self) -> AsyncSession:
        """获取数据库会话"""
        return AsyncSessionLocal()

    async def generate_script_async(self, task_id: str, request: ScriptGenerationRequest):
        """异步生成剧本 - 使用LangGraph工作流 + SQLAlchemy持久化"""
        t0 = time.time()
        async with self._get_db() as db:
            try:
                if not self._initialized:
                    await self.initialize()

                logger.info(f"开始生成剧本，任务ID: {task_id}, 标题: {request.title}")

                # 创建或更新任务记录
                task = await db.get(GenerationTask, task_id)
                if not task:
                    task = GenerationTask(
                        task_id=task_id,
                        status=TaskStatus.PROCESSING.value,
                        progress=10,
                        start_time=time.time(),
                    )
                    db.add(task)
                else:
                    task.status = TaskStatus.PROCESSING.value
                    task.progress = 10
                await db.commit()

                # 执行LangGraph工作流
                request_dict = request.dict() if hasattr(request, 'dict') else vars(request)
                workflow_result = await self.workflow.execute(request_dict, thread_id=task_id)

                if workflow_result["success"]:
                    script = Script(
                        task_id=task_id,
                        title=request.title,
                        content=workflow_result["script"],
                        theme=getattr(request, 'theme', ''),
                        length=getattr(request, 'length', '短篇'),
                        style=getattr(request, 'style', ''),
                        setting=getattr(request, 'setting', ''),
                        characters=getattr(request, 'characters', []),
                        status=ScriptStatus.COMPLETED.value,
                        user_id=str(getattr(request, 'user_id', '')),
                        workflow_metadata=workflow_result.get("metadata", {}),
                        analysis_result=workflow_result.get("analysis"),
                        has_optimized_version=workflow_result.get("optimized_version") is not None,
                    )
                    db.add(script)
                    await db.flush()  # 获取自增ID

                    # 更新任务状态
                    task.status = TaskStatus.COMPLETED.value
                    task.progress = 100
                    task.script_id = script.id
                    task.end_time = time.time()
                    task.duration = task.end_time - (task.start_time or time.time())
                    task.result_data = {"script_id": script.id}
                    await db.commit()

                    logger.info(f"剧本生成完成，任务ID: {task_id}, 剧本ID: {script.id}, 耗时={time.time()-t0:.1f}s")
                else:
                    error_msg = workflow_result.get("error", "未知错误")
                    task.status = TaskStatus.FAILED.value
                    task.progress = 0
                    task.error = error_msg
                    task.end_time = time.time()
                    await db.commit()
                    logger.error(f"剧本生成失败，任务ID: {task_id}, 耗时={time.time()-t0:.1f}s, 错误: {error_msg}")

            except Exception as e:
                logger.error(f"剧本生成异常 task={task_id} 耗时={time.time()-t0:.1f}s: {e}")
                await db.rollback()
                # 尝试更新任务状态
                try:
                    task = await db.get(GenerationTask, task_id)
                    if task:
                        task.status = TaskStatus.FAILED.value
                        task.error = str(e)
                        task.end_time = time.time()
                        await db.commit()
                except Exception:
                    pass

    async def get_script(self, script_id: int) -> Optional[Dict]:
        """获取剧本详情"""
        async with self._get_db() as db:
            script = await db.get(Script, script_id)
            if script:
                return script.to_dict()
            logger.warning(f"剧本未找到 script_id={script_id}")
            return None

    async def list_scripts(self, page: int = 1, page_size: int = 10,
                          user_id: Optional[str] = None,
                          status: Optional[str] = None) -> tuple:
        """获取剧本列表"""
        async with self._get_db() as db:
            stmt = select(Script)

            if user_id:
                stmt = stmt.where(Script.user_id == user_id)
            if status:
                stmt = stmt.where(Script.status == status)

            # 按创建时间倒序
            stmt = stmt.order_by(Script.created_at.desc())

            # 计算总数
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total_result = await db.execute(count_stmt)
            total = total_result.scalar() or 0

            # 分页
            offset = (page - 1) * page_size
            stmt = stmt.offset(offset).limit(page_size)
            result = await db.execute(stmt)
            scripts = result.scalars().all()

            return [s.to_dict() for s in scripts], total

    async def update_script(self, script_id: int, request: ScriptUpdateRequest) -> Optional[Dict]:
        """更新剧本"""
        async with self._get_db() as db:
            script = await db.get(Script, script_id)
            if not script:
                logger.warning(f"剧本未找到，无法更新 script_id={script_id}")
                return None

            request_dict = request.dict(exclude_unset=True) if hasattr(request, 'dict') else vars(request)
            for field in ['title', 'content', 'status']:
                if field in request_dict and request_dict[field] is not None:
                    setattr(script, field, request_dict[field])

            script.updated_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(script)
            logger.info(f"剧本已更新 script_id={script_id} title={script.title}")
            return script.to_dict()

    async def delete_script(self, script_id: int) -> bool:
        """删除剧本"""
        async with self._get_db() as db:
            script = await db.get(Script, script_id)
            if not script:
                logger.warning(f"剧本未找到，无法删除 script_id={script_id}")
                return False

            # 清理关联任务
            stmt = delete(GenerationTask).where(GenerationTask.script_id == script_id)
            await db.execute(stmt)

            await db.delete(script)
            await db.commit()
            logger.info(f"剧本已删除 script_id={script_id} title={script.title}")
            return True

    async def get_generation_status(self, task_id: str) -> Optional[Dict]:
        """获取剧本生成状态"""
        async with self._get_db() as db:
            stmt = select(GenerationTask).where(GenerationTask.task_id == task_id)
            result = await db.execute(stmt)
            task = result.scalar_one_or_none()

            if not task:
                return None

            status = task.to_dict()

            # 如果任务完成且有script_id，附加剧本内容
            if task.status == TaskStatus.COMPLETED.value and task.script_id:
                script_stmt = select(Script).where(Script.id == task.script_id)
                script_result = await db.execute(script_stmt)
                script = script_result.scalar_one_or_none()
                if script:
                    # 兼容 V1 (list) 和 V2 (dict with events/locations/props)
                    raw = script.analysis_result or {}
                    if isinstance(raw, dict):
                        events = raw.get("events", [])
                        locations = raw.get("locations", [])
                    else:
                        events = raw if isinstance(raw, list) else []
                        locations = self._derive_locations_from_events(events) if events else []
                    # V2: build ShotEpisode-format storyboard from stored data
                    storyboard_episodes = None
                    if script.pipeline_version == 'v2' and script.storyboard:
                        storyboard_episodes = self._build_shot_episodes(
                            script.storyboard, script.episodes
                        )

                    # V2: extract story_framework from workflow_metadata
                    wf_meta = script.workflow_metadata or {}
                    story_framework = wf_meta.get("story_framework", "")

                    status["result"] = {
                        "title": script.title,
                        "content": script.content,
                        "episodes": script.episodes,
                        "storyboard": storyboard_episodes,
                        "story_framework": story_framework or None,
                        "theme": script.theme,
                        "style": script.style,
                        "length": script.length,
                        "setting": script.setting,
                        "characters": script.characters,
                        "locations": locations,
                        "events": events,
                    }

            return status

    async def regenerate_script(self, script_id: int, modifications: Dict[str, Any]) -> Optional[Dict]:
        """重新生成剧本"""
        async with self._get_db() as db:
            original = await db.get(Script, script_id)
            if not original:
                return None

            request_dict = {
                "title": modifications.get("title", original.title),
                "theme": modifications.get("theme", original.theme),
                "length": modifications.get("length", original.length),
                "style": modifications.get("style", original.style),
                "setting": modifications.get("setting", original.setting),
                "characters": modifications.get("characters", original.characters or []),
                "user_id": original.user_id,
                "regenerate_from": script_id,
                "modifications": modifications
            }

            workflow_result = await self.workflow.execute(request_dict, thread_id=f"regenerate_{script_id}")

            if workflow_result["success"]:
                new_script = Script(
                    title=modifications.get("title", original.title),
                    content=workflow_result["script"],
                    theme=modifications.get("theme", original.theme),
                    length=modifications.get("length", original.length),
                    style=modifications.get("style", original.style),
                    setting=modifications.get("setting", original.setting),
                    characters=modifications.get("characters", original.characters),
                    source_type=original.source_type,
                    status=ScriptStatus.COMPLETED.value,
                    user_id=original.user_id,
                    regenerated_from=script_id,
                    modifications=modifications,
                    workflow_metadata=workflow_result.get("metadata", {}),
                    analysis_result=workflow_result.get("analysis"),
                    has_optimized_version=workflow_result.get("optimized_version") is not None,
                )
                db.add(new_script)
                await db.commit()
                await db.refresh(new_script)

                return {
                    "success": True,
                    "new_script_id": new_script.id,
                    "script": new_script.to_dict(),
                    "workflow_result": workflow_result
                }
            else:
                return {
                    "success": False,
                    "error": workflow_result.get("error"),
                    "workflow_result": workflow_result
                }

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

                # Create or retrieve task record
                task = await db.get(GenerationTask, task_id)
                if not task:
                    task = GenerationTask(
                        task_id=task_id,
                        status=TaskStatus.PROCESSING.value,
                        progress=5,
                        start_time=time.time(),
                    )
                    db.add(task)
                else:
                    task.status = TaskStatus.PROCESSING.value
                    task.progress = 5
                await db.commit()

                # --- V2 RAG-based pipeline (V1 ViMax has been removed) ---
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
            mock_mode = getattr(self.ai_service, '_mock_mode', False)
            style = getattr(request, 'style', '') or app_settings.N2S_V2_DEFAULT_STYLE

            n2s_v2 = Novel2ScriptV2Service(
                llm=self.ai_service.llm if not mock_mode else None,
                mock_mode=mock_mode,
                config=app_settings,
            )

            async def progress_callback(pct: int, stage: str):
                task.progress = pct
                await db.commit()
                logger.info(f"[V2] 进度 {pct}% — {stage} task={task_id}")

            result = await n2s_v2.run_full_pipeline(
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

    async def get_script_character_graph(self, script_id: int) -> Optional[dict]:
        """Get the character relationship graph for a V2 script."""
        async with self._get_db() as db:
            script = await db.get(Script, script_id)
            if script and script.character_graph:
                return script.character_graph
            return None

    def _sync_generate_from_outline(self, request_dict: dict) -> Optional[str]:
        """同步调用 AI 生成大纲剧本（在线程池中运行）"""
        import asyncio as _asyncio
        try:
            loop = _asyncio.new_event_loop()
            _asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                self.ai_service.generate_script_from_outline(request_dict)
            )
            loop.close()
            return result
        except Exception as e:
            logger.error(f"大纲生成线程内失败: {e}")
            return None

    async def generate_script_from_outline_async(self, task_id: str, request: ScriptFromOutlineRequest):
        """异步从大纲生成剧本 — 使用 V2 管线，统一输出格式"""
        t_total = time.time()
        async with self._get_db() as db:
            try:
                if not self._initialized:
                    await self.initialize()

                outline = getattr(request, 'outline', '') or ''
                logger.info(f"[大纲→剧本 V2] 开始 task={task_id} title={request.title} outline_len={len(outline)}")

                task = await db.get(GenerationTask, task_id)
                if not task:
                    task = GenerationTask(
                        task_id=task_id,
                        status=TaskStatus.PROCESSING.value,
                        progress=5,
                        start_time=time.time(),
                    )
                    db.add(task)
                else:
                    task.status = TaskStatus.PROCESSING.value
                    task.progress = 5
                await db.commit()

                mock_mode = getattr(self.ai_service, '_mock_mode', False)
                style = getattr(request, 'style', '') or app_settings.N2S_V2_DEFAULT_STYLE

                n2s_v2 = Novel2ScriptV2Service(
                    llm=self.ai_service.llm if not mock_mode else None,
                    mock_mode=mock_mode,
                    config=app_settings,
                )

                async def progress_callback(pct: int, stage: str):
                    task.progress = pct
                    await db.commit()
                    logger.info(f"[V2大纲] 进度 {pct}% — {stage} task={task_id}")

                # Map length to target episode count (outline has no chapter markers)
                length_to_eps = {"短篇": 5, "中篇": 8, "长篇": 12}
                # Parse explicit episode count from user's outline/title (e.g. "二十集")
                import re as _re2
                _cn_nums = {c: i for i, c in enumerate(
                    ['', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十',
                     '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十',
                     '二十一', '二十二', '二十三', '二十四', '二十五', '二十六', '二十七', '二十八', '二十九', '三十',
                     '三十一', '三十二', '三十三', '三十四', '三十五', '三十六', '三十七', '三十八', '三十九', '四十',
                     '四十一', '四十二', '四十三', '四十四', '四十五', '四十六', '四十七', '四十八', '四十九', '五十'], start=0)}
                def _parse_ep(text: str) -> int:
                    if not text: return 0
                    for m in _re2.finditer(r'([一二三四五六七八九十百千\d]+)\s*集', text):
                        s = m.group(1)
                        if s.isdigit(): return int(s)
                        n = _cn_nums.get(s, 0)
                        if n > 0: return n
                    return 0
                user_ep = _parse_ep(outline) or _parse_ep(request.title)
                target_eps = user_ep if user_ep > 0 else length_to_eps.get(getattr(request, 'length', '短篇'), 5)
                target_eps = min(target_eps, 50)  # cap at 50

                result = await n2s_v2.run_full_pipeline(
                    novel_text=outline,
                    style=style,
                    progress_callback=progress_callback,
                    target_episodes=target_eps,
                )

                final_script = result.get("final_script", "")
                if not final_script:
                    raise ValueError("V2 outline pipeline produced empty script")

                episodes = result.get("episodes") or self._split_content_to_episodes(final_script)
                entities_data = result.get("entities", {})
                extracted_characters = entities_data.get("characters", [])
                character_graph = result.get("character_graph", {})
                storyboard_data = result.get("storyboard", [])

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
                    characters=json.dumps(extracted_characters, ensure_ascii=False) if extracted_characters else None,
                    source_type="outline",
                    source_content=outline[:500],
                    status=ScriptStatus.COMPLETED.value,
                    user_id=str(getattr(request, 'user_id', '')),
                    pipeline_version="v2",
                    character_graph=character_graph if character_graph else None,
                    storyboard=storyboard_data if storyboard_data else None,
                    workflow_metadata={
                        "pipeline": "v2_rag_outline",
                        "stages": result.get("stages", {}),
                        "story_framework": result.get("story_framework", ""),
                    },
                    analysis_result={
                        "events": analysis_events,
                        "locations": entities_data.get("locations", []),
                        "props": entities_data.get("props", []),
                    },
                )
                db.add(script)
                await db.flush()

                task.status = TaskStatus.COMPLETED.value
                task.progress = 100
                task.script_id = script.id
                task.end_time = time.time()
                await db.commit()

                logger.info(f"[V2大纲] 完成 script_id={script.id}, {len(episodes)}集, "
                            f"{len(storyboard_data)}分镜, 总长度={len(final_script)} 总耗时={time.time()-t_total:.1f}s")

                from app.services.usage_tracker import estimate_tokens
                chapter_count = len(result.get("script_scenes", []))
                call_count = chapter_count + 2 if chapter_count > 0 else 1
                estimated_in = estimate_tokens(outline) * 2
                estimated_out = estimate_tokens(final_script)
                await track_llm_usage(
                    user_id=str(getattr(request, 'user_id', '')),
                    model_name="deepseek-chat",
                    tokens_in=estimated_in,
                    tokens_out=estimated_out,
                    call_count=call_count,
                    duration_ms=int((time.time() - t_total) * 1000),
                    endpoint="/generate/from-outline",
                    service_name="script-service",
                )

            except Exception as e:
                logger.error(f"[V2大纲] 异常失败 task={task_id} 耗时={time.time()-t_total:.1f}s: {e}")
                await db.rollback()
                try:
                    task = await db.get(GenerationTask, task_id)
                    if task:
                        task.status = TaskStatus.FAILED.value
                        task.error = str(e)
                        task.end_time = time.time()
                        await db.commit()
                except Exception:
                    pass

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
