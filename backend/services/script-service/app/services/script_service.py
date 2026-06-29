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
from app.services.novel2script_service import Novel2ScriptService
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
                    # 从 analysis_result（events）中提取地点
                    events = script.analysis_result or []
                    locations = self._derive_locations_from_events(events) if events else []
                    status["result"] = {
                        "title": script.title,
                        "content": script.content,
                        "episodes": script.episodes,
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

    async def _generate_long_novel_script(
        self, novel_content: str, n2s: Novel2ScriptService,
        request: ScriptFromNovelRequest, task, task_id: str, db, chapter_count: int
    ) -> Dict[str, Any]:
        """长篇小说分批 ViMax 处理：每批6章，批内走完整流水线保证质量。
        返回 {"script": str, "characters": list, "events": list}"""
        import re
        # 用去重拆分：只按每个章节编号的首次出现切分（避免子章节/引用干扰）
        pattern = r'(?:^|\n)\s*(?:#{1,6}\s*)?第\s*([一二三四五六七八九十百千\d]+)\s*[回章节]'
        markers = [(m.start(), m.group(1)) for m in re.finditer(pattern, novel_content, re.MULTILINE)]
        # 去重：同一编号只保留第一次出现的位置
        seen = set()
        unique_positions = []
        for pos, num in markers:
            if num not in seen:
                seen.add(num)
                unique_positions.append(pos)

        if len(unique_positions) <= 1:
            chapters = [novel_content]
        else:
            chapters = []
            for i, pos in enumerate(unique_positions):
                end = unique_positions[i+1] if i+1 < len(unique_positions) else len(novel_content)
                chapters.append(novel_content[pos:end])

        logger.info(f"[分批ViMax] 拆分完成: {len(chapters)}章(去重), 原始匹配{len(markers)}标记, 共{(len(chapters)+5)//6}批")
        batch_size = 6
        all_results = []
        all_characters: List[Dict[str, Any]] = []
        all_events: List[Dict[str, Any]] = []
        base_style = getattr(request, 'style', '古风历史')
        base_theme = getattr(request, 'theme', '战争')
        base_setting = getattr(request, 'setting', '三国')

        total_batches = (len(chapters) + batch_size - 1) // batch_size
        for batch_idx in range(total_batches):
            start = batch_idx * batch_size
            end = min(start + batch_size, len(chapters))
            batch_text = "\n\n".join(chapters[start:end])
            ep_start = start + 1
            batch_count = end - start

            progress = 50 + int((batch_idx / max(total_batches, 1)) * 40)
            task.progress = progress; await db.commit()
            logger.info(f"[分批ViMax] 第{batch_idx+1}/{total_batches}批开始: 章{ep_start}-{end}, 目标{batch_count}集, 进度{progress}%")

            # 带重试的 ViMax 流水线（最多重试2次，全部失败用原文兜底）
            batch_success = False
            for retry in range(3):
                try:
                    compressed = await n2s.compress_novel(batch_text)
                    chars = await n2s.extract_characters(compressed)
                    events = await n2s.extract_events(compressed)

                    # 收集每批的角色和事件（用于最终合并去重）
                    all_characters.extend(chars)
                    all_events.extend(events)

                    batch_req = f"主题:{base_theme}; 风格:{base_style}; 长度:长篇; 背景:{base_setting}"
                    effective = n2s.build_user_requirement(batch_text, batch_req)
                    ep_start_cn = self._num_to_cn(ep_start)
                    ep_end_cn = self._num_to_cn(end)
                    effective += f" 必须输出恰好{batch_count}集！编号从第{ep_start_cn}集到第{ep_end_cn}集，用中文数字，连续递增。"

                    story = await n2s.develop_story(compressed, effective)
                    scenes = await n2s.write_script(story, effective)
                    enhanced = await n2s.enhance_script(scenes)
                    all_results.append("\n\n".join(enhanced))
                    batch_success = True
                    logger.info(f"[分批ViMax] 第{batch_idx+1}/{total_batches}批成功, 输出{len(enhanced)}场, {len(chars)}角色, {len(events)}事件")
                    break
                except Exception as e:
                    logger.warning(f"批次{batch_idx+1}第{retry+1}次失败: {e}")
                    if retry < 2:
                        await asyncio.sleep(5)

            if not batch_success:
                logger.warning(f"批次{batch_idx+1}全部重试失败，使用原文片段兜底")
                fallback_parts = []
                for j in range(start, end):
                    n = j + 1
                    num_str = self._num_to_cn(n)
                    fallback_parts.append(f"**第{num_str}集**\n\n{chapters[j][:600]}")
                all_results.append("\n\n".join(fallback_parts))

        final_script = "\n\n".join(all_results)
        merged_characters = self._merge_characters(all_characters)
        logger.info(f"[分批ViMax] 角色合并: {len(all_characters)}条原始 → {len(merged_characters)}个唯一角色, "
                     f"{len(all_events)}个事件")
        return {
            "script": final_script,
            "characters": merged_characters,
            "events": all_events,
        }

    async def generate_script_from_novel_async(self, task_id: str, request: ScriptFromNovelRequest):
        """异步从小说生成剧本 — ViMax 多阶段流水线"""
        t_total = time.time()
        async with self._get_db() as db:
            try:
                if not self._initialized:
                    await self.initialize()

                novel_content = getattr(request, 'novel_content', '') or ''
                logger.info(f"[小说→剧本] 开始 task={task_id} title={request.title} novel_len={len(novel_content)} style={request.style}")

                mock_mode = getattr(self.ai_service, '_mock_mode', False)
                n2s = Novel2ScriptService(self.ai_service.llm, mock_mode)

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

                # 先检测章节数（纯文本，不调AI），长篇小说直接分批处理
                chapter_count = n2s.detect_chapter_count(novel_content)
                logger.info(f"[小说→剧本] 章节检测: {chapter_count}章, 小说长度={len(novel_content)}字")

                if chapter_count > 15:
                    logger.info(f"[小说→剧本] 长篇小说模式: 启用分批ViMax, 预计{ (chapter_count+5)//6 }批, 每批6章")
                    result = await self._generate_long_novel_script(
                        novel_content, n2s, request, task, task_id, db, chapter_count
                    )
                    if result and result.get("script"):
                        final_script = result["script"]
                        episodes = self._split_content_to_episodes(final_script)
                        merged_characters = result.get("characters", [])
                        all_events = result.get("events", [])
                        script = Script(
                            task_id=task_id, title=request.title, content=final_script,
                            episodes=episodes, theme=getattr(request, 'theme', ''),
                            length=getattr(request, 'length', '短篇'), style=getattr(request, 'style', ''),
                            setting=getattr(request, 'setting', ''),
                            characters=json.dumps(merged_characters, ensure_ascii=False) if merged_characters else None,
                            source_type="novel", source_content=novel_content[:500],
                            status=ScriptStatus.COMPLETED.value,
                            user_id=str(getattr(request, 'user_id', '')),
                            workflow_metadata={
                                "pipeline": "long_novel_batch_vimax",
                                "chapter_count": chapter_count,
                                "character_count": len(merged_characters),
                                "event_count": len(all_events),
                            },
                            analysis_result=all_events if all_events else None,
                        )
                        db.add(script); await db.flush()
                        task.status = TaskStatus.COMPLETED.value; task.progress = 100
                        task.script_id = script.id; task.end_time = time.time()
                        await db.commit()
                        logger.info(f"[分批ViMax] 完成: script_id={script.id}, {len(episodes)}集, "
                                     f"{len(merged_characters)}角色, {len(all_events)}事件, "
                                     f"总长度={len(final_script)} 总耗时={time.time()-t_total:.1f}s")
                        # 记录 LLM 用量
                        await track_llm_usage(
                            user_id=str(getattr(request, 'user_id', '')),
                            model_name="deepseek-chat",
                            tokens_in=len(novel_content),
                            tokens_out=len(final_script),
                            duration_ms=int((time.time() - t_total) * 1000),
                            endpoint="/generate/from-novel",
                            service_name="script-service",
                        )
                        return

                # 短篇/中篇：完整 ViMax 流水线
                logger.info(f"[短篇ViMax] 开始5阶段流水线")
                user_req = f"主题:{getattr(request, 'theme', '')}; 风格:{getattr(request, 'style', '')}; 长度:{getattr(request, 'length', '短篇')}; 背景:{getattr(request, 'setting', '')}"
                task.progress = 15; await db.commit()
                logger.info(f"[短篇ViMax] 阶段1/5: 压缩小说...")
                compressed = await n2s.compress_novel(novel_content)
                logger.info(f"[短篇ViMax] 阶段1完成: 压缩后{len(compressed)}字")
                task.progress = 30; await db.commit()
                logger.info(f"[短篇ViMax] 阶段2/5: 提取角色...")
                characters = await n2s.extract_characters(compressed)
                logger.info(f"[短篇ViMax] 阶段2完成: {len(characters)}个角色")
                task.progress = 50; await db.commit()
                logger.info(f"[短篇ViMax] 阶段3/5: 提取事件...")
                events = await n2s.extract_events(compressed)
                logger.info(f"[短篇ViMax] 阶段3完成: {len(events)}个事件")
                effective_req = n2s.build_user_requirement(novel_content, user_req)

                # 阶段4: 编剧生成 — 短篇小说 ViMax 流水线（带重试）
                task.progress = 65; await db.commit()
                logger.info(f"[短篇ViMax] 阶段4/5: 编剧生成...")
                scenes = None
                for retry in range(3):
                    try:
                        story = await n2s.develop_story(compressed, effective_req)
                        scenes = await n2s.write_script(story, effective_req)
                        logger.info(f"[短篇ViMax] 阶段4完成: {len(scenes)}场")
                        break
                    except Exception as e:
                        logger.warning(f"ViMax编剧第{retry+1}次失败: {e}")
                        if retry < 2: await asyncio.sleep(3)
                if scenes is None:
                    logger.warning("ViMax编剧全部重试失败，使用原文分集")
                    scenes = n2s._fallback_split_to_episodes(novel_content, effective_req)

                # 如果AI超时导致只返回1场，用原文分集做回退
                if len(scenes) <= 1 and chapter_count >= 2:
                    logger.info(f"AI返回场景数不足({len(scenes)})，使用原文分集回退（共{chapter_count}章）")
                    scenes = n2s._fallback_split_to_episodes(novel_content, effective_req)

                # 阶段5: 增强 (80% → 95%)
                task.progress = 85; await db.commit()
                logger.info(f"[短篇ViMax] 阶段5/5: 增强剧本...")
                try:
                    enhanced = await n2s.enhance_script(scenes)
                    logger.info(f"[短篇ViMax] 阶段5完成: {len(enhanced)}场增强")
                except Exception as e:
                    logger.warning(f"[短篇ViMax] 增强失败: {e}，使用未增强版本")
                    enhanced = scenes
                final_script = "\n\n".join(enhanced)

                # 保存结果
                if final_script:
                    script = Script(
                        task_id=task_id,
                        title=request.title,
                        content=final_script,
                        theme=getattr(request, 'theme', ''),
                        length=getattr(request, 'length', '短篇'),
                        style=getattr(request, 'style', ''),
                        setting=getattr(request, 'setting', ''),
                        characters=json.dumps(characters, ensure_ascii=False) if characters else None,
                        source_type="novel",
                        source_content=novel_content[:500],
                        status=ScriptStatus.COMPLETED.value,
                        user_id=str(getattr(request, 'user_id', '')),
                        workflow_metadata={
                            "pipeline": "vimax_novel2script",
                            "compressed_length": len(compressed),
                            "character_count": len(characters),
                            "event_count": len(events),
                            "scene_count": len(enhanced),
                        },
                        analysis_result=events,
                        has_optimized_version=False,
                    )
                    db.add(script)
                    await db.flush()

                    task.status = TaskStatus.COMPLETED.value
                    task.progress = 100
                    task.script_id = script.id
                    task.end_time = time.time()
                    await db.commit()

                    logger.info(f"[短篇ViMax] 生成完成 script_id={script.id}, {len(characters)}角色, {len(events)}事件, "
                                f"{len(enhanced)}场 总耗时={time.time()-t_total:.1f}s")
                else:
                    raise ValueError("生成的剧本内容为空")
                    task.error = error_msg
                    task.end_time = time.time()
                    await db.commit()

            except Exception as e:
                logger.error(f"[小说→剧本] 异常失败 task={task_id} 耗时={time.time()-t_total:.1f}s: {e}")
                await db.rollback()

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
        """异步从大纲生成剧本 — 在线程池中运行 AI 调用，确保超时可靠"""
        loop = asyncio.get_running_loop()
        request_dict = request.dict() if hasattr(request, 'dict') else vars(request)

        # 初始化 AI（必须在主线程完成）
        if not self._initialized:
            await self.initialize()

        # 先创建任务记录（让前端能立即轮询到）
        async with self._get_db() as db:
            task = await db.get(GenerationTask, task_id)
            if not task:
                task = GenerationTask(
                    task_id=task_id,
                    status=TaskStatus.PROCESSING.value,
                    progress=10,
                    start_time=time.time(),
                )
                db.add(task)
                await db.commit()
            logger.info(f"开始从大纲生成剧本，任务ID: {task_id}")

        # 在线程池中运行 AI 调用
        try:
            script_content = await asyncio.wait_for(
                loop.run_in_executor(None, self._sync_generate_from_outline, request_dict),
                timeout=300
            )
        except asyncio.TimeoutError:
            script_content = None
        except Exception as e:
            logger.error(f"大纲生成 AI 调用失败: {e}")
            script_content = None

        # 更新任务结果
        async with self._get_db() as db:
            try:
                task = await db.get(GenerationTask, task_id)
                if not task:
                    return

                if script_content is None:
                    task.status = TaskStatus.FAILED.value
                    task.error = "AI 生成超时（5分钟），请缩短输入内容后重试"
                    task.end_time = time.time()
                    await db.commit()
                    return

                # 后处理：将生成内容拆分为分集
                episodes = self._split_content_to_episodes(script_content)
                logger.info(f"大纲生成剧本完成，拆分为 {len(episodes)} 集")

                script = Script(
                    task_id=task_id,
                    title=request.title,
                    content=script_content,
                    episodes=episodes,
                    theme=getattr(request, 'theme', ''),
                    length=getattr(request, 'length', '短篇'),
                    style=getattr(request, 'style', ''),
                    setting=getattr(request, 'setting', ''),
                    characters=getattr(request, 'characters', []),
                    source_type="outline",
                    source_content=str(getattr(request, 'outline', ''))[:500],
                    status=ScriptStatus.COMPLETED.value,
                    user_id=str(getattr(request, 'user_id', '')),
                    has_optimized_version=False,
                )
                db.add(script)
                await db.flush()

                task.status = TaskStatus.COMPLETED.value
                task.progress = 100
                task.script_id = script.id
                task.end_time = time.time()
                await db.commit()

                logger.info(f"剧本（大纲转）生成完成，剧本ID: {script.id}")

            except Exception as e:
                logger.error(f"剧本（大纲转）生成异常: {e}")
                await db.rollback()

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
