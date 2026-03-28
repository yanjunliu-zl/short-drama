import logging

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import List, Optional
import uuid
import time

logger = logging.getLogger(__name__)

from app.schemas.storyboard import (
    StoryboardGenerationRequest,
    StoryboardResponse,
    StoryboardListResponse
)
from app.services.storyboard_service import StoryboardAIService
from app.core.deps import get_storyboard_service

router = APIRouter()


@router.post("/generate", response_model=StoryboardResponse)
async def generate_storyboard(
    request: StoryboardGenerationRequest,
    background_tasks: BackgroundTasks,
    storyboard_service: StoryboardAIService = Depends(get_storyboard_service)
):
    """
    生成分镜

    使用AI模型根据剧本生成分镜脚本
    """
    try:
        task_id = str(uuid.uuid4())

        background_tasks.add_task(
            _generate_storyboard_task,
            task_id=task_id,
            request=request,
            storyboard_service=storyboard_service
        )

        return StoryboardResponse(
            task_id=task_id,
            status="processing",
            message="Storyboard generation started",
            storyboard=None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _generate_storyboard_task(
    task_id: str,
    request: StoryboardGenerationRequest,
    storyboard_service: StoryboardAIService
):
    """后台分镜生成任务"""
    try:
        # 更新任务状态为进行中
        _storyboard_tasks[task_id] = {
            "status": "processing",
            "progress": 10,
            "result": None,
            "start_time": time.time(),
            "request": request.dict()
        }

        # 生成分镜
        storyboard_data = await storyboard_service.generate_storyboard(request.dict())

        # 更新任务状态为完成
        _storyboard_tasks[task_id] = {
            "status": "completed",
            "progress": 100,
            "result": storyboard_data,
            "end_time": time.time(),
            "task_id": task_id
        }

    except Exception as e:
        logger.error(f"分镜生成失败，任务ID: {task_id}, 错误: {e}")
        _storyboard_tasks[task_id] = {
            "status": "failed",
            "progress": 0,
            "error": str(e),
            "end_time": time.time()
        }


# 全局任务存储
_storyboard_tasks: dict = {}


@router.get("/{storyboard_id}", response_model=StoryboardResponse)
async def get_storyboard(
    storyboard_id: str,
    storyboard_service: StoryboardAIService = Depends(get_storyboard_service)
):
    """
    获取分镜详情
    """
    try:
        task_info = _storyboard_tasks.get(storyboard_id)
        if not task_info:
            raise HTTPException(status_code=404, detail="Storyboard not found")

        if task_info["status"] != "completed":
            raise HTTPException(status_code=404, detail="Storyboard not ready")

        return StoryboardResponse(
            task_id=storyboard_id,
            status="completed",
            message="Storyboard retrieved successfully",
            storyboard=task_info.get("result")
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=StoryboardListResponse)
async def list_storyboards(
    page: int = 1,
    page_size: int = 10
):
    """
    获取分镜列表
    """
    try:
        all_tasks = list(_storyboard_tasks.values())
        completed_tasks = [t for t in all_tasks if t.get("status") == "completed"]

        # 按完成时间倒序排序
        completed_tasks.sort(key=lambda x: x.get("end_time", 0), reverse=True)

        # 分页
        total = len(completed_tasks)
        start = (page - 1) * page_size
        end = start + page_size
        paginated = completed_tasks[start:end]

        return StoryboardListResponse(
            storyboards=paginated,
            total=total,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{storyboard_id}/status")
async def get_storyboard_status(
    storyboard_id: str
):
    """
    获取分镜生成状态
    """
    try:
        task_info = _storyboard_tasks.get(storyboard_id)
        if not task_info:
            raise HTTPException(status_code=404, detail="Storyboard not found")

        status_info = {
            "task_id": storyboard_id,
            "status": task_info.get("status", "unknown"),
            "progress": task_info.get("progress", 0),
            "error": task_info.get("error"),
        }

        if "start_time" in task_info:
            status_info["start_time"] = task_info["start_time"]
            status_info["duration"] = (task_info.get("end_time", time.time()) - task_info["start_time"])

        return status_info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
