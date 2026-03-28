from typing import List, Optional, Dict, Any
import logging
from uuid import uuid4
import time

from app.schemas.script import (
    ScriptUpdateRequest,
    ScriptGenerationRequest,
    ScriptFromNovelRequest,
    ScriptFromOutlineRequest
)
from app.services.ai_service import AIService
from app.services.workflow import ScriptWorkflow
from app.client.service_clients import VideoServiceClient, LLMServiceClient

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


class ScriptService:
    """剧本生成服务，集成LangChain和LangGraph"""

    def __init__(self):
        self._generation_tasks: Dict[str, Any] = {}
        self._scripts_storage: Dict[str, Any] = {}

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

    async def generate_script_async(self, task_id: str, request: ScriptGenerationRequest):
        """异步生成剧本 - 使用LangGraph工作流"""
        try:
            # 确保服务已初始化
            if not self._initialized:
                await self.initialize()

            logger.info(f"开始生成剧本，任务ID: {task_id}, 标题: {request.title}")

            # 更新任务状态为进行中
            self._generation_tasks[task_id] = {
                "status": "processing",
                "progress": 10,
                "result": None,
                "start_time": time.time(),
                "request": request.dict() if hasattr(request, 'dict') else vars(request)
            }

            # 将请求转换为字典
            request_dict = request.dict() if hasattr(request, 'dict') else vars(request)

            # 执行LangGraph工作流
            workflow_result = await self.workflow.execute(request_dict, thread_id=task_id)

            if workflow_result["success"]:
                # 创建剧本记录
                script_id = str(uuid4())
                script_record = {
                    "id": script_id,
                    "task_id": task_id,
                    "title": request.title,
                    "content": workflow_result["script"],
                    "theme": getattr(request, 'theme', ''),
                    "length": getattr(request, 'length', '短篇'),
                    "style": getattr(request, 'style', ''),
                    "setting": getattr(request, 'setting', ''),
                    "characters": getattr(request, 'characters', []),
                    "status": "completed",
                    "user_id": getattr(request, 'user_id', ''),
                    "workflow_metadata": workflow_result.get("metadata", {}),
                    "analysis_result": workflow_result.get("analysis"),
                    "has_optimized_version": workflow_result.get("optimized_version") is not None,
                    "created_at": time.time(),
                    "updated_at": time.time()
                }

                self._scripts_storage[script_id] = script_record
                self._generation_tasks[task_id] = {
                    "status": "completed",
                    "progress": 100,
                    "result": script_record,
                    "end_time": time.time(),
                    "workflow_result": workflow_result,
                    "script_id": script_id
                }

                logger.info(f"剧本生成完成，任务ID: {task_id}, 剧本ID: {script_id}, 长度: {len(workflow_result['script'])} 字符")
            else:
                # 工作流失败
                error_msg = workflow_result.get("error", "未知错误")
                self._generation_tasks[task_id] = {
                    "status": "failed",
                    "progress": 0,
                    "error": error_msg,
                    "end_time": time.time(),
                    "workflow_result": workflow_result
                }
                logger.error(f"剧本生成失败，任务ID: {task_id}, 错误: {error_msg}")

        except Exception as e:
            logger.error(f"剧本生成异常: {e}")
            self._generation_tasks[task_id] = {
                "status": "failed",
                "progress": 0,
                "error": str(e),
                "end_time": time.time()
            }

    async def get_script(self, script_id: str) -> Optional[Dict]:
        """获取剧本详情"""
        return self._scripts_storage.get(script_id)

    async def list_scripts(self, page: int = 1, page_size: int = 10,
                          user_id: Optional[str] = None,
                          status: Optional[str] = None) -> tuple[List[Dict], int]:
        """获取剧本列表"""
        scripts = list(self._scripts_storage.values())

        # 过滤
        if user_id:
            scripts = [s for s in scripts if s.get('user_id') == user_id]
        if status:
            scripts = [s for s in scripts if s.get('status') == status]

        # 按创建时间倒序排序
        scripts.sort(key=lambda x: x.get('created_at', 0), reverse=True)

        # 分页
        total = len(scripts)
        start = (page - 1) * page_size
        end = start + page_size
        paginated = scripts[start:end]

        return paginated, total

    async def update_script(self, script_id: str, request: ScriptUpdateRequest) -> Optional[Dict]:
        """更新剧本"""
        if script_id not in self._scripts_storage:
            return None

        script = self._scripts_storage[script_id]

        # 更新字段
        request_dict = request.dict() if hasattr(request, 'dict') else vars(request)

        for field in ['title', 'content', 'status']:
            if field in request_dict and request_dict[field] is not None:
                script[field] = request_dict[field]

        script['updated_at'] = time.time()
        self._scripts_storage[script_id] = script

        return script

    async def delete_script(self, script_id: str) -> bool:
        """删除剧本"""
        if script_id in self._scripts_storage:
            del self._scripts_storage[script_id]

            # 同时清理相关的任务记录
            for task_id, task_info in list(self._generation_tasks.items()):
                if task_info.get('script_id') == script_id:
                    del self._generation_tasks[task_id]

            return True
        return False

    async def get_generation_status(self, task_id: str) -> Optional[Dict]:
        """获取剧本生成状态"""
        task_info = self._generation_tasks.get(task_id)

        if not task_info:
            return None

        # 计算进度百分比（如果有进度信息）
        status_info = {
            "task_id": task_id,
            "status": task_info.get("status", "unknown"),
            "progress": task_info.get("progress", 0),
            "script_id": task_info.get("script_id"),
            "error": task_info.get("error"),
        }

        # 添加时间信息
        if "start_time" in task_info:
            status_info["start_time"] = task_info["start_time"]
            status_info["duration"] = (task_info.get("end_time", time.time()) - task_info["start_time"])

        return status_info

    async def regenerate_script(self, script_id: str, modifications: Dict[str, Any]) -> Optional[Dict]:
        """重新生成剧本（基于现有剧本进行修改）"""
        if script_id not in self._scripts_storage:
            return None

        original_script = self._scripts_storage[script_id]

        # 构建新的生成请求
        request_dict = {
            "title": modifications.get("title", original_script.get("title")),
            "theme": modifications.get("theme", original_script.get("theme")),
            "length": modifications.get("length", original_script.get("length")),
            "style": modifications.get("style", original_script.get("style")),
            "setting": modifications.get("setting", original_script.get("setting")),
            "characters": modifications.get("characters", original_script.get("characters", [])),
            "user_id": original_script.get("user_id"),
            "regenerate_from": script_id,
            "modifications": modifications
        }

        # 执行工作流
        workflow_result = await self.workflow.execute(request_dict, thread_id=f"regenerate_{script_id}")

        if workflow_result["success"]:
            # 创建新版本的剧本记录
            new_script_id = str(uuid4())
            new_script_record = {
                **original_script,
                "id": new_script_id,
                "content": workflow_result["script"],
                "regenerated_from": script_id,
                "modifications": modifications,
                "status": "completed",
                "created_at": time.time(),
                "updated_at": time.time()
            }

            # 更新标题等修改的字段
            for field in ["title", "theme", "length", "style", "setting", "characters"]:
                if field in modifications:
                    new_script_record[field] = modifications[field]

            self._scripts_storage[new_script_id] = new_script_record

            return {
                "success": True,
                "new_script_id": new_script_id,
                "script": new_script_record,
                "workflow_result": workflow_result
            }
        else:
            return {
                "success": False,
                "error": workflow_result.get("error"),
                "workflow_result": workflow_result
            }

    async def generate_script_from_novel_async(self, task_id: str, request: ScriptFromNovelRequest):
        """异步从小说生成剧本 - 使用LangGraph工作流"""
        try:
            # 确保服务已初始化
            if not self._initialized:
                await self.initialize()

            logger.info(f"开始从小说生成剧本，任务ID: {task_id}, 标题: {request.title}")

            # 更新任务状态为进行中
            self._generation_tasks[task_id] = {
                "status": "processing",
                "progress": 10,
                "result": None,
                "start_time": time.time(),
                "request": request.dict() if hasattr(request, 'dict') else vars(request)
            }

            # 将请求转换为字典
            request_dict = request.dict() if hasattr(request, 'dict') else vars(request)

            # 执行LangGraph工作流
            workflow_result = await self.workflow.execute(request_dict, thread_id=task_id)

            if workflow_result["success"]:
                # 创建剧本记录
                script_id = str(uuid4())
                script_record = {
                    "id": script_id,
                    "task_id": task_id,
                    "title": request.title,
                    "content": workflow_result["script"],
                    "theme": getattr(request, 'theme', ''),
                    "length": getattr(request, 'length', '短篇'),
                    "style": getattr(request, 'style', ''),
                    "setting": getattr(request, 'setting', ''),
                    "characters": getattr(request, 'characters', []),
                    "source_type": "novel",
                    "source_content": getattr(request, 'novel_content', '')[:500],  # 保存部分原文
                    "status": "completed",
                    "user_id": getattr(request, 'user_id', ''),
                    "workflow_metadata": workflow_result.get("metadata", {}),
                    "analysis_result": workflow_result.get("analysis"),
                    "has_optimized_version": workflow_result.get("optimized_version") is not None,
                    "created_at": time.time(),
                    "updated_at": time.time()
                }

                self._scripts_storage[script_id] = script_record
                self._generation_tasks[task_id] = {
                    "status": "completed",
                    "progress": 100,
                    "result": script_record,
                    "end_time": time.time(),
                    "workflow_result": workflow_result,
                    "script_id": script_id
                }

                logger.info(f"剧本生成完成，任务ID: {task_id}, 剧本ID: {script_id}, 长度: {len(workflow_result['script'])} 字符")
            else:
                # 工作流失败
                error_msg = workflow_result.get("error", "未知错误")
                self._generation_tasks[task_id] = {
                    "status": "failed",
                    "progress": 0,
                    "error": error_msg,
                    "end_time": time.time(),
                    "workflow_result": workflow_result
                }
                logger.error(f"剧本生成失败，任务ID: {task_id}, 错误: {error_msg}")

        except Exception as e:
            logger.error(f"剧本生成异常: {e}")
            self._generation_tasks[task_id] = {
                "status": "failed",
                "progress": 0,
                "error": str(e),
                "end_time": time.time()
            }

    async def generate_script_from_outline_async(self, task_id: str, request: ScriptFromOutlineRequest):
        """异步从大纲生成剧本 - 使用LangGraph工作流"""
        try:
            # 确保服务已初始化
            if not self._initialized:
                await self.initialize()

            logger.info(f"开始从大纲生成剧本，任务ID: {task_id}, 标题: {request.title}")

            # 更新任务状态为进行中
            self._generation_tasks[task_id] = {
                "status": "processing",
                "progress": 10,
                "result": None,
                "start_time": time.time(),
                "request": request.dict() if hasattr(request, 'dict') else vars(request)
            }

            # 将请求转换为字典
            request_dict = request.dict() if hasattr(request, 'dict') else vars(request)

            # 执行LangGraph工作流
            workflow_result = await self.workflow.execute(request_dict, thread_id=task_id)

            if workflow_result["success"]:
                # 创建剧本记录
                script_id = str(uuid4())
                script_record = {
                    "id": script_id,
                    "task_id": task_id,
                    "title": request.title,
                    "content": workflow_result["script"],
                    "theme": getattr(request, 'theme', ''),
                    "length": getattr(request, 'length', '短篇'),
                    "style": getattr(request, 'style', ''),
                    "setting": getattr(request, 'setting', ''),
                    "characters": getattr(request, 'characters', []),
                    "source_type": "outline",
                    "source_content": getattr(request, 'outline', '')[:500],  # 保存部分原文
                    "status": "completed",
                    "user_id": getattr(request, 'user_id', ''),
                    "workflow_metadata": workflow_result.get("metadata", {}),
                    "analysis_result": workflow_result.get("analysis"),
                    "has_optimized_version": workflow_result.get("optimized_version") is not None,
                    "created_at": time.time(),
                    "updated_at": time.time()
                }

                self._scripts_storage[script_id] = script_record
                self._generation_tasks[task_id] = {
                    "status": "completed",
                    "progress": 100,
                    "result": script_record,
                    "end_time": time.time(),
                    "workflow_result": workflow_result,
                    "script_id": script_id
                }

                logger.info(f"剧本生成完成，任务ID: {task_id}, 剧本ID: {script_id}, 长度: {len(workflow_result['script'])} 字符")
            else:
                # 工作流失败
                error_msg = workflow_result.get("error", "未知错误")
                self._generation_tasks[task_id] = {
                    "status": "failed",
                    "progress": 0,
                    "error": error_msg,
                    "end_time": time.time(),
                    "workflow_result": workflow_result
                }
                logger.error(f"剧本生成失败，任务ID: {task_id}, 错误: {error_msg}")

        except Exception as e:
            logger.error(f"剧本生成异常: {e}")
            self._generation_tasks[task_id] = {
                "status": "failed",
                "progress": 0,
                "error": str(e),
                "end_time": time.time()
            }