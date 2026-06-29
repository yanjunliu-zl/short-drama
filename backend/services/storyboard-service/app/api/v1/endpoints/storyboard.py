import logging

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import List, Optional
import uuid
import time

logger = logging.getLogger(__name__)

from app.schemas.storyboard import (
    StoryboardGenerationRequest,
    StoryboardResponse,
    StoryboardListResponse,
    ShotGenerationRequest,
    ShotGenerationResponse,
)
from app.services.storyboard_service import StoryboardAIService
from app.services.task_store import get_task_store, TaskStore
from app.core.deps import get_storyboard_service

router = APIRouter()


async def _get_task_store() -> TaskStore:
    return await get_task_store()


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
    task_id = str(uuid.uuid4())
    script_len = len(request.script) if request.script else 0
    logger.info(f"[API] POST /generate task_id={task_id} title={request.title} script_len={script_len}")
    try:
        background_tasks.add_task(
            _generate_storyboard_task,
            task_id=task_id,
            request=request,
            storyboard_service=storyboard_service
        )
        logger.info(f"[API] 分镜生成任务已提交 task_id={task_id}")
        return StoryboardResponse(
            task_id=task_id,
            status="processing",
            message="Storyboard generation started",
            storyboard=None
        )
    except Exception as e:
        logger.error(f"[API] POST /generate 失败 task_id={task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _generate_storyboard_task(
    task_id: str,
    request: StoryboardGenerationRequest,
    storyboard_service: StoryboardAIService
):
    """后台分镜生成任务"""
    t0 = time.time()
    store = await get_task_store()
    logger.info(f"[Task] 分镜生成开始 task_id={task_id} title={request.title}")
    try:
        await store.set(task_id, {
            "status": "processing",
            "progress": 10,
            "result": None,
            "start_time": time.time(),
            "request": request.dict()
        })

        storyboard_data = await storyboard_service.generate_storyboard(request.dict())

        elapsed = time.time() - t0
        scene_count = len(storyboard_data.get("scenes", []))
        await store.set(task_id, {
            "status": "completed",
            "progress": 100,
            "result": storyboard_data,
            "end_time": time.time(),
            "task_id": task_id
        })
        logger.info(f"[Task] 分镜生成完成 task_id={task_id} scenes={scene_count} 耗时={elapsed:.1f}s")

    except Exception as e:
        elapsed = time.time() - t0
        logger.error(f"[Task] 分镜生成失败 task_id={task_id} 耗时={elapsed:.1f}s: {e}")
        await store.set(task_id, {
            "status": "failed",
            "progress": 0,
            "error": str(e),
            "end_time": time.time()
        })


@router.get("/{storyboard_id}", response_model=StoryboardResponse)
async def get_storyboard(
    storyboard_id: str,
    storyboard_service: StoryboardAIService = Depends(get_storyboard_service)
):
    """
    获取分镜详情
    """
    logger.info(f"[API] GET /{storyboard_id}")
    try:
        store = await _get_task_store()
        task_info = await store.get(storyboard_id)
        if not task_info:
            logger.warning(f"[API] GET /{storyboard_id} 分镜未找到")
            raise HTTPException(status_code=404, detail="Storyboard not found")

        if task_info["status"] != "completed":
            logger.warning(f"[API] GET /{storyboard_id} 分镜未就绪 status={task_info['status']}")
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
        logger.error(f"[API] GET /{storyboard_id} 异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=StoryboardListResponse)
async def list_storyboards(
    page: int = 1,
    page_size: int = 10
):
    """
    获取分镜列表
    """
    logger.info(f"[API] GET / page={page} page_size={page_size}")
    try:
        store = await _get_task_store()
        completed_tasks = await store.list_completed(limit=100)

        # 按完成时间倒序排序
        completed_tasks.sort(key=lambda x: x.get("end_time", 0), reverse=True)

        # 分页
        total = len(completed_tasks)
        start = (page - 1) * page_size
        end = start + page_size
        paginated = completed_tasks[start:end]

        logger.info(f"[API] GET / 返回 {len(paginated)}/{total} 条记录")
        return StoryboardListResponse(
            storyboards=paginated,
            total=total,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        logger.error(f"[API] GET / 列表查询异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{storyboard_id}/status")
async def get_storyboard_status(
    storyboard_id: str
):
    """
    获取分镜生成状态
    """
    logger.info(f"[API] GET /{storyboard_id}/status")
    try:
        store = await _get_task_store()
        task_info = await store.get(storyboard_id)
        if not task_info:
            logger.warning(f"[API] GET /{storyboard_id}/status 分镜未找到")
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

        logger.info(f"[API] GET /{storyboard_id}/status status={status_info['status']} progress={status_info['progress']}")
        return status_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] GET /{storyboard_id}/status 异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 镜头级分镜 (Shot-level) 端点 ==========

@router.post("/shots/generate", response_model=ShotGenerationResponse)
async def generate_shots(
    request: ShotGenerationRequest,
    background_tasks: BackgroundTasks,
    storyboard_service: StoryboardAIService = Depends(get_storyboard_service)
):
    """
    智能分镜：使用AI模型将剧本拆分为镜头级分镜

    根据剧本内容自动分析并划分每个镜头，包括镜头类型、时长、摄像机角度等
    """
    task_id = str(uuid.uuid4())
    script_len = len(request.script) if request.script else 0
    ep_count = request.episodeCount or 0
    logger.info(f"[API] POST /shots/generate task_id={task_id} title={request.title} "
                f"script_len={script_len} episodes={ep_count}")
    try:
        background_tasks.add_task(
            _generate_shots_task,
            task_id=task_id,
            request=request,
            storyboard_service=storyboard_service
        )
        logger.info(f"[API] 智能分镜任务已提交 task_id={task_id}")
        return ShotGenerationResponse(
            task_id=task_id,
            status="processing",
            message="Shot division generation started",
            episodes=None
        )
    except Exception as e:
        logger.error(f"[API] POST /shots/generate 失败 task_id={task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _generate_shots_task(
    task_id: str,
    request: ShotGenerationRequest,
    storyboard_service: StoryboardAIService
):
    """后台镜头级分镜生成任务"""
    t0 = time.time()
    store = await get_task_store()
    logger.info(f"[Task] 智能分镜开始 task_id={task_id} title={request.title}")
    try:
        await store.set(task_id, {
            "status": "processing",
            "progress": 10,
            "result": None,
            "start_time": time.time(),
            "request": request.dict(),
            "task_type": "shots",
        })

        shot_data = await storyboard_service.generate_shots(request.dict())

        elapsed = time.time() - t0
        ep_count = len(shot_data.get("episodes", []))
        total_shots = sum(len(ep.get("shots", [])) for ep in shot_data.get("episodes", []))
        await store.set(task_id, {
            "status": "completed",
            "progress": 100,
            "result": shot_data,
            "end_time": time.time(),
            "task_id": task_id,
            "task_type": "shots",
        })
        logger.info(f"[Task] 智能分镜完成 task_id={task_id} episodes={ep_count} shots={total_shots} 耗时={elapsed:.1f}s")

    except Exception as e:
        elapsed = time.time() - t0
        logger.error(f"[Task] 智能分镜失败 task_id={task_id} 耗时={elapsed:.1f}s: {e}")
        await store.set(task_id, {
            "status": "failed",
            "progress": 0,
            "error": str(e),
            "end_time": time.time(),
            "task_type": "shots",
        })


@router.get("/shots/{task_id}/status")
async def get_shot_generation_status(task_id: str):
    """
    获取镜头分镜生成状态
    """
    logger.info(f"[API] GET /shots/{task_id}/status")
    try:
        store = await _get_task_store()
        task_info = await store.get(task_id)
        if not task_info:
            logger.warning(f"[API] GET /shots/{task_id}/status 任务未找到")
            raise HTTPException(status_code=404, detail="Shot generation task not found")

        status_info = {
            "task_id": task_id,
            "status": task_info.get("status", "unknown"),
            "progress": task_info.get("progress", 0),
            "error": task_info.get("error"),
        }

        if "start_time" in task_info:
            status_info["start_time"] = task_info["start_time"]
            status_info["duration"] = (task_info.get("end_time", time.time()) - task_info["start_time"])

        logger.info(f"[API] GET /shots/{task_id}/status status={status_info['status']} progress={status_info['progress']}")
        return status_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] GET /shots/{task_id}/status 异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shots/{task_id}", response_model=ShotGenerationResponse)
async def get_shot_generation_result(
    task_id: str,
    storyboard_service: StoryboardAIService = Depends(get_storyboard_service)
):
    """
    获取镜头分镜生成结果
    """
    logger.info(f"[API] GET /shots/{task_id}")
    try:
        store = await _get_task_store()
        task_info = await store.get(task_id)
        if not task_info:
            logger.warning(f"[API] GET /shots/{task_id} 任务未找到")
            raise HTTPException(status_code=404, detail="Shot generation task not found")

        if task_info["status"] != "completed":
            logger.warning(f"[API] GET /shots/{task_id} 任务未就绪 status={task_info['status']}")
            raise HTTPException(status_code=404, detail="Shot generation not ready")

        result = task_info.get("result", {})
        ep_count = len(result.get("episodes", []))
        logger.info(f"[API] GET /shots/{task_id} 返回 {ep_count} 集")
        return ShotGenerationResponse(
            task_id=task_id,
            status="completed",
            message="Shot division retrieved successfully",
            episodes=result.get("episodes"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] GET /shots/{task_id} 异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))
