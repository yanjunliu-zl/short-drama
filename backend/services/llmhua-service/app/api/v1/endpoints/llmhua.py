import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
import uuid
import time

from app.schemas.llmhua import (
    StoryboardToImageRequest,
    ImageToVideoRequest,
    StoryboardGenerationRequest,
    ImageGenerationResponse,
    VideoGenerationResponse,
    CompleteResult,
    SceneResult,
    TaskStatusResponse,
    TaskStatus
)
from app.services.seedance_service import get_seedance_service, close_seedance_service

router = APIRouter()

logger = logging.getLogger(__name__)


# ==================== 全局状态存储 ====================
_llmhua_tasks: Dict[str, Dict[str, Any]] = {}


# ==================== 图像生成端点 ====================

@router.post("/images/generate", response_model=ImageGenerationResponse)
async def generate_image_from_scene(
    request: StoryboardToImageRequest,
    background_tasks: BackgroundTasks,
    seedance_service=Depends(get_seedance_service)
):
    """
    根据分镜镜头描述生成单个镜头图像
    """
    try:
        task_id = str(uuid.uuid4())

        background_tasks.add_task(
            _generate_image_task,
            task_id=task_id,
            request=request,
            seedance_service=seedance_service
        )

        return ImageGenerationResponse(
            task_id=task_id,
            status="processing",
            image_url=None,
            seed=None,
            message="Image generation started"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _generate_image_task(
    task_id: str,
    request: StoryboardToImageRequest,
    seedance_service
):
    """后台图像生成任务"""
    try:
        _llmhua_tasks[task_id] = {
            "status": "processing",
            "progress": 10,
            "result": None,
            "start_time": time.time(),
        }

        # 调用Seedance生成图像
        result = await seedance_service.generate_image_from_scene(
            scene_description=request.scene_description,
            style=request.style,
            width=request.width or 1920,
            height=request.height or 1080,
            seed=request.seed
        )

        if result and result.get("status") == "completed":
            _llmhua_tasks[task_id] = {
                "status": "completed",
                "progress": 100,
                "result": result,
                "end_time": time.time(),
                "task_id": task_id
            }
        else:
            _llmhua_tasks[task_id] = {
                "status": "failed",
                "progress": 0,
                "error": "Failed to generate image",
                "end_time": time.time()
            }

    except Exception as e:
        logger.error(f"图像生成失败，任务ID: {task_id}, 错误: {e}")
        _llmhua_tasks[task_id] = {
            "status": "failed",
            "progress": 0,
            "error": str(e),
            "end_time": time.time()
        }


@router.get("/images/{task_id}", response_model=ImageGenerationResponse)
async def get_image_generation_result(task_id: str):
    """
    获取图像生成结果
    """
    try:
        task_info = _llmhua_tasks.get(task_id)
        if not task_info:
            raise HTTPException(status_code=404, detail="Task not found")

        result = task_info.get("result", {})

        return ImageGenerationResponse(
            task_id=task_id,
            status=task_info.get("status", "unknown"),
            image_url=result.get("image_url") if result else None,
            seed=result.get("seed") if result else None,
            message="Image retrieved successfully" if task_info.get("status") == "completed" else "Still processing"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/images/{task_id}/status", response_model=TaskStatusResponse)
async def get_image_generation_status(task_id: str):
    """
    获取图像生成任务状态
    """
    try:
        task_info = _llmhua_tasks.get(task_id)
        if not task_info:
            raise HTTPException(status_code=404, detail="Task not found")

        status_info = TaskStatusResponse(
            task_id=task_id,
            status=task_info.get("status", "unknown"),
            progress=task_info.get("progress", 0),
            result=task_info.get("result"),
            error=task_info.get("error"),
            created_at=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(task_info.get("start_time", 0))),
            completed_at=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(task_info.get("end_time", 0))) if task_info.get("end_time") else None
        )

        return status_info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 视频生成端点 ====================

@router.post("/videos/generate", response_model=VideoGenerationResponse)
async def generate_video_from_image(
    request: ImageToVideoRequest,
    background_tasks: BackgroundTasks,
    seedance_service=Depends(get_seedance_service)
):
    """
    根据图像生成对应视频
    """
    try:
        task_id = str(uuid.uuid4())

        background_tasks.add_task(
            _generate_video_task,
            task_id=task_id,
            request=request,
            seedance_service=seedance_service
        )

        return VideoGenerationResponse(
            task_id=task_id,
            status="processing",
            video_url=None,
            message="Video generation started"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _generate_video_task(
    task_id: str,
    request: ImageToVideoRequest,
    seedance_service
):
    """后台视频生成任务"""
    try:
        _llmhua_tasks[task_id] = {
            "status": "processing",
            "progress": 10,
            "result": None,
            "start_time": time.time(),
        }

        # 调用Seedance生成视频
        result = await seedance_service.generate_video_from_image(
            image_url=request.image_url,
            prompt=request.prompt or request.image_url,  # 如果没有提示词，使用图像URL作为提示
            duration=request.duration,
            fps=request.fps,
            seed=request.seed,
            strength=request.strength
        )

        if result and result.get("status") == "completed":
            _llmhua_tasks[task_id] = {
                "status": "completed",
                "progress": 100,
                "result": result,
                "end_time": time.time(),
                "task_id": task_id
            }
        else:
            _llmhua_tasks[task_id] = {
                "status": "failed",
                "progress": 0,
                "error": "Failed to generate video",
                "end_time": time.time()
            }

    except Exception as e:
        logger.error(f"视频生成失败，任务ID: {task_id}, 错误: {e}")
        _llmhua_tasks[task_id] = {
            "status": "failed",
            "progress": 0,
            "error": str(e),
            "end_time": time.time()
        }


@router.get("/videos/{task_id}", response_model=VideoGenerationResponse)
async def get_video_generation_result(task_id: str):
    """
    获取视频生成结果
    """
    try:
        task_info = _llmhua_tasks.get(task_id)
        if not task_info:
            raise HTTPException(status_code=404, detail="Task not found")

        result = task_info.get("result", {})

        return VideoGenerationResponse(
            task_id=task_id,
            status=task_info.get("status", "unknown"),
            video_url=result.get("video_url") if result else None,
            message="Video retrieved successfully" if task_info.get("status") == "completed" else "Still processing"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/videos/{task_id}/status", response_model=TaskStatusResponse)
async def get_video_generation_status(task_id: str):
    """
    获取视频生成任务状态
    """
    try:
        task_info = _llmhua_tasks.get(task_id)
        if not task_info:
            raise HTTPException(status_code=404, detail="Task not found")

        return TaskStatusResponse(
            task_id=task_id,
            status=task_info.get("status", "unknown"),
            progress=task_info.get("progress", 0),
            result=task_info.get("result"),
            error=task_info.get("error"),
            created_at=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(task_info.get("start_time", 0))),
            completed_at=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(task_info.get("end_time", 0))) if task_info.get("end_time") else None
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 完整流程端点 ====================

@router.post("/storyboard/generate-complete", response_model=CompleteResult)
async def generate_complete_storyboard(
    request: StoryboardGenerationRequest,
    background_tasks: BackgroundTasks,
    seedance_service=Depends(get_seedance_service)
):
    """
    根据分镜生成所有镜头图像并转换为视频（完整流程）
    """
    try:
        task_id = str(uuid.uuid4())

        background_tasks.add_task(
            _generate_complete_storyboard_task,
            task_id=task_id,
            request=request,
            seedance_service=seedance_service
        )

        return CompleteResult(
            storyboard_id=request.storyboard_id,
            total_scenes=len(request.scenes),
            successful_scenes=0,
            results=[]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _generate_complete_storyboard_task(
    task_id: str,
    request: StoryboardGenerationRequest,
    seedance_service
):
    """后台完整分镜生成任务"""
    try:
        _llmhua_tasks[task_id] = {
            "status": "processing",
            "progress": 5,
            "result": None,
            "start_time": time.time(),
        }

        results = []
        successful_count = 0

        for idx, scene in enumerate(request.scenes):
            scene_number = scene.get("scene_number", idx + 1)
            scene_description = scene.get("description", "")

            # 生成图像
            image_result = await seedance_service.generate_image_from_scene(
                scene_description=scene_description,
                style=request.style,
                width=1920,
                height=1080,
            )

            scene_result = SceneResult(
                scene_number=scene_number,
                status="failed",
                image_url=None,
                video_url=None
            )

            if image_result and image_result.get("status") == "completed":
                scene_result.image_url = image_result.get("image_url")
                scene_result.status = "image_generated"

                # 如果需要生成视频
                if request.generate_video:
                    video_result = await seedance_service.generate_video_from_image(
                        image_url=scene_result.image_url,
                        prompt=scene_description,
                        duration=5.0,
                        fps=24,
                    )

                    if video_result and video_result.get("status") == "completed":
                        scene_result.video_url = video_result.get("video_url")
                        scene_result.status = "completed"
                        successful_count += 1
                    else:
                        scene_result.status = "image_only"
                else:
                    scene_result.status = "completed"
                    successful_count += 1

            results.append(scene_result)

            # 更新进度
            _llmhua_tasks[task_id]["progress"] = int(5 + (idx + 1) / len(request.scenes) * 95)

        _llmhua_tasks[task_id] = {
            "status": "completed",
            "progress": 100,
            "result": {
                "storyboard_id": request.storyboard_id,
                "total_scenes": len(request.scenes),
                "successful_scenes": successful_count,
                "results": results
            },
            "end_time": time.time(),
            "task_id": task_id
        }

    except Exception as e:
        logger.error(f"完整分镜生成失败，任务ID: {task_id}, 错误: {e}")
        _llmhua_tasks[task_id] = {
            "status": "failed",
            "progress": 0,
            "error": str(e),
            "end_time": time.time()
        }


@router.get("/storyboard/{task_id}/result", response_model=CompleteResult)
async def get_complete_storyboard_result(task_id: str):
    """
    获取完整分镜生成结果
    """
    try:
        task_info = _llmhua_tasks.get(task_id)
        if not task_info:
            raise HTTPException(status_code=404, detail="Task not found")

        result = task_info.get("result", {})

        if not result:
            raise HTTPException(status_code=404, detail="Result not ready")

        return CompleteResult(
            storyboard_id=result.get("storyboard_id", ""),
            total_scenes=result.get("total_scenes", 0),
            successful_scenes=result.get("successful_scenes", 0),
            results=result.get("results", [])
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 健康检查 ====================

@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "llmhua-video-generation",
        "timestamp": time.time()
    }
