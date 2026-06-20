from typing import List, Optional, Dict, Any
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
    ScriptFromOutlineRequest
)
from app.services.ai_service import AIService
from app.services.workflow import ScriptWorkflow
from app.services.novel2script_service import Novel2ScriptService
from app.client.service_clients import VideoServiceClient, LLMServiceClient
from app.models import Script, GenerationTask, ScriptStatus, TaskStatus
from app.core.database import AsyncSessionLocal

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

                    logger.info(f"剧本生成完成，任务ID: {task_id}, 剧本ID: {script.id}")
                else:
                    error_msg = workflow_result.get("error", "未知错误")
                    task.status = TaskStatus.FAILED.value
                    task.progress = 0
                    task.error = error_msg
                    task.end_time = time.time()
                    await db.commit()
                    logger.error(f"剧本生成失败，任务ID: {task_id}, 错误: {error_msg}")

            except Exception as e:
                logger.error(f"剧本生成异常: {e}")
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
            return script.to_dict() if script else None

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
                return None

            request_dict = request.dict(exclude_unset=True) if hasattr(request, 'dict') else vars(request)
            for field in ['title', 'content', 'status']:
                if field in request_dict and request_dict[field] is not None:
                    setattr(script, field, request_dict[field])

            script.updated_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(script)
            return script.to_dict()

    async def delete_script(self, script_id: int) -> bool:
        """删除剧本"""
        async with self._get_db() as db:
            script = await db.get(Script, script_id)
            if not script:
                return False

            # 清理关联任务
            stmt = delete(GenerationTask).where(GenerationTask.script_id == script_id)
            await db.execute(stmt)

            await db.delete(script)
            await db.commit()
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
                    status["result"] = {
                        "title": script.title,
                        "content": script.content,
                        "theme": script.theme,
                        "style": script.style,
                        "length": script.length,
                        "setting": script.setting,
                        "characters": script.characters,
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

    async def generate_script_from_novel_async(self, task_id: str, request: ScriptFromNovelRequest):
        """异步从小说生成剧本 — ViMax 多阶段流水线"""
        async with self._get_db() as db:
            try:
                if not self._initialized:
                    await self.initialize()

                logger.info(f"开始从小说生成剧本(ViMax流水线)，任务ID: {task_id}")

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

                novel_content = getattr(request, 'novel_content', '') or ''
                user_req = f"主题:{getattr(request, 'theme', '')}; 风格:{getattr(request, 'style', '')}; 长度:{getattr(request, 'length', '短篇')}; 背景:{getattr(request, 'setting', '')}"

                # 使用 Novel2ScriptService 多阶段流水线
                mock_mode = getattr(self.ai_service, '_mock_mode', False)
                n2s = Novel2ScriptService(self.ai_service.llm, mock_mode)

                # 阶段1: 压缩 (5% → 25%)
                task.progress = 15; await db.commit()
                compressed = await n2s.compress_novel(novel_content)

                # 阶段2: 角色提取 (25% → 40%)
                task.progress = 30; await db.commit()
                characters = await n2s.extract_characters(compressed)

                # 阶段3: 事件提取 (40% → 55%)
                task.progress = 50; await db.commit()
                events = await n2s.extract_events(compressed)

                # 阶段4: 编剧生成 (55% → 80%)
                task.progress = 65; await db.commit()
                story = await n2s.develop_story(compressed, user_req)
                scenes = await n2s.write_script(story, user_req)

                # 阶段5: 增强 (80% → 95%)
                task.progress = 85; await db.commit()
                enhanced = await n2s.enhance_script(scenes)
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
                        characters=json.dumps([c.get('name', '') for c in characters], ensure_ascii=False) if characters else None,
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

                    logger.info(f"剧本(ViMax流水线)生成完成，剧本ID: {script.id}, "
                                f"{len(characters)}角色, {len(events)}事件, {len(enhanced)}场")
                else:
                    raise ValueError("生成的剧本内容为空")
                    task.error = error_msg
                    task.end_time = time.time()
                    await db.commit()

            except Exception as e:
                logger.error(f"剧本（小说转）生成异常: {e}")
                await db.rollback()

    async def generate_script_from_outline_async(self, task_id: str, request: ScriptFromOutlineRequest):
        """异步从大纲生成剧本"""
        async with self._get_db() as db:
            try:
                if not self._initialized:
                    await self.initialize()

                logger.info(f"开始从大纲生成剧本，任务ID: {task_id}")

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
                        source_type="outline",
                        source_content=str(getattr(request, 'outline', ''))[:500],
                        status=ScriptStatus.COMPLETED.value,
                        user_id=str(getattr(request, 'user_id', '')),
                        workflow_metadata=workflow_result.get("metadata", {}),
                        analysis_result=workflow_result.get("analysis"),
                        has_optimized_version=workflow_result.get("optimized_version") is not None,
                    )
                    db.add(script)
                    await db.flush()

                    task.status = TaskStatus.COMPLETED.value
                    task.progress = 100
                    task.script_id = script.id
                    task.end_time = time.time()
                    await db.commit()

                    logger.info(f"剧本（大纲转）生成完成，剧本ID: {script.id}")
                else:
                    error_msg = workflow_result.get("error", "未知错误")
                    task.status = TaskStatus.FAILED.value
                    task.error = error_msg
                    task.end_time = time.time()
                    await db.commit()

            except Exception as e:
                logger.error(f"剧本（大纲转）生成异常: {e}")
                await db.rollback()
