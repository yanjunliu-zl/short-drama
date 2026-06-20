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
    TaskStatus,
    ShotsToVideoRequest,
    ShotsToVideoResponse,
    ShotVideoResult,
    PreviewImageRequest,
    PreviewImageResponse,
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
            height=request.height or 1920,
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


# ==================== 预览图像生成端点（场景/角色/道具） ====================

def _build_preview_prompt(description: str, category: str, style: str) -> str:
    """根据类型构建预览图像提示词"""
    if category == "character":
        return f"一个角色的全身肖像，{description}。风格：{style}，高质量，细节丰富，适合短剧角色设计。"
    elif category == "prop":
        return f"一件道具的展示图，{description}。风格：{style}，白底产品图，高质量，细节清晰。"
    else:  # scene
        return f"一个场景环境图，{description}。风格：{style}，宽屏构图，高质量，适合短剧场景设定。"


@router.post("/preview-image", response_model=PreviewImageResponse)
async def generate_preview_image(
    request: PreviewImageRequest,
    background_tasks: BackgroundTasks,
    seedance_service=Depends(get_seedance_service)
):
    """
    为场景/角色/道具生成预览图像。

    根据描述和类别（scene/character/prop）构建合适的提示词，调用 Seedance 生成图像。
    """
    try:
        task_id = str(uuid.uuid4())

        prompt = _build_preview_prompt(request.description, request.category, request.style or "写实风格")

        background_tasks.add_task(
            _generate_preview_image_task,
            task_id=task_id,
            prompt=prompt,
            style=request.style,
            width=request.width or 1024,
            height=request.height or 1024,
            seedance_service=seedance_service
        )

        return PreviewImageResponse(
            task_id=task_id,
            status="processing",
            message="Preview image generation started"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _generate_preview_image_task(
    task_id: str,
    prompt: str,
    style: str,
    width: int,
    height: int,
    seedance_service
):
    """后台预览图像生成任务"""
    try:
        _llmhua_tasks[task_id] = {
            "status": "processing",
            "progress": 10,
            "result": None,
            "start_time": time.time(),
            "task_type": "preview-image",
        }

        result = await seedance_service.generate_image_from_scene(
            scene_description=prompt,
            style=style,
            width=width,
            height=height,
        )

        if result and result.get("status") == "completed":
            _llmhua_tasks[task_id] = {
                "status": "completed",
                "progress": 100,
                "result": result,
                "end_time": time.time(),
                "task_id": task_id,
                "task_type": "preview-image",
            }
        else:
            err_detail = result.get("message", "") if result else "API返回为空"
            _llmhua_tasks[task_id] = {
                "status": "failed",
                "progress": 0,
                "error": f"Failed to generate preview image: {err_detail}",
                "end_time": time.time(),
                "task_type": "preview-image",
            }

    except Exception as e:
        logger.error(f"预览图像生成失败，任务ID: {task_id}, 错误: {e}")
        _llmhua_tasks[task_id] = {
            "status": "failed",
            "progress": 0,
            "error": str(e),
            "end_time": time.time(),
            "task_type": "preview-image",
        }


@router.get("/preview-image/{task_id}/status")
async def get_preview_image_status(task_id: str):
    """获取预览图像生成状态"""
    try:
        task_info = _llmhua_tasks.get(task_id)
        if not task_info:
            raise HTTPException(status_code=404, detail="Task not found")

        return {
            "task_id": task_id,
            "status": task_info.get("status", "unknown"),
            "progress": task_info.get("progress", 0),
            "image_url": task_info.get("result", {}).get("image_url") if task_info.get("result") else None,
            "error": task_info.get("error"),
        }
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
                        image_url=image_result.get("original_url") or scene_result.image_url,
                        prompt=scene_description,
                        duration=5.0,
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


# ==================== 分镜头批量视频生成端点 ====================

def _build_shot_video_prompt(shot: dict, style: str = "") -> str:
    """
    从分镜头结构化字段构建视频生成提示词。

    将 shotType、cameraAngle、description、dialogue、characters、
    sceneRef、soundEffects、music 组合为 Seedance 的中文提示词。
    """
    parts = []

    if style:
        parts.append(f"风格：{style}")

    shot_type = shot.get('shotType', '中景')
    parts.append(f"镜头类型：{shot_type}")

    camera_angle = shot.get('cameraAngle', '正面平视')
    parts.append(f"摄像机角度：{camera_angle}")

    if shot.get('sceneRef'):
        parts.append(f"场景：{shot['sceneRef']}")

    characters = shot.get('characters', [])
    if characters:
        parts.append(f"角色：{'、'.join(characters)}")

    description = shot.get('description', '')
    if description:
        parts.append(f"画面描述：{description}")

    dialogue = shot.get('dialogue', '')
    if dialogue:
        parts.append(f"对白/旁白：{dialogue}")

    sound_effects = shot.get('soundEffects', [])
    if sound_effects:
        parts.append(f"音效：{'、'.join(sound_effects)}")

    music = shot.get('music', '')
    if music:
        parts.append(f"背景音乐：{music}")

    notes = shot.get('notes', '')
    if notes:
        parts.append(f"备注：{notes}")

    return "，".join(parts) + "。"


@router.post("/shots-to-video", response_model=ShotsToVideoResponse)
async def generate_shots_to_video(
    request: ShotsToVideoRequest,
    background_tasks: BackgroundTasks,
    seedance_service=Depends(get_seedance_service)
):
    """
    为每个分镜头批量生成视频。

    对每个 shot：构建视频提示词 -> 生成图像 -> 生成视频 -> 存储到 Ceph。
    """
    try:
        task_id = str(uuid.uuid4())

        total_shots = sum(len(ep.shots) for ep in request.episodes)

        background_tasks.add_task(
            _generate_shots_to_video_task,
            task_id=task_id,
            request=request,
            seedance_service=seedance_service
        )

        return ShotsToVideoResponse(
            task_id=task_id,
            status="processing",
            message=f"Video generation started for {total_shots} shots",
            total_shots=total_shots,
            completed_shots=0,
            results=[]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _generate_shots_to_video_task(
    task_id: str,
    request: ShotsToVideoRequest,
    seedance_service
):
    """后台批量镜头视频生成任务"""
    try:
        total_shots = sum(len(ep.shots) for ep in request.episodes)

        _llmhua_tasks[task_id] = {
            "status": "processing",
            "progress": 5,
            "result": None,
            "start_time": time.time(),
            "task_type": "shots-to-video",
        }

        results: list = []
        completed_count = 0
        failed_count = 0

        for ep in request.episodes:
            for shot in ep.shots:
                shot_dict = shot.model_dump() if hasattr(shot, 'model_dump') else shot

                try:
                    # 构建视频提示词
                    prompt = _build_shot_video_prompt(shot_dict, request.style or "")

                    # 第一步：生成图像
                    image_result = await seedance_service.generate_image_from_scene(
                        scene_description=prompt,
                        style=request.style,
                        width=request.width or 1920,
                        height=request.height or 1920,
                    )

                    video_url = None
                    image_url = None
                    file_size = None
                    status = "failed"
                    error_msg = None

                    if image_result and image_result.get("status") == "completed":
                        image_url = image_result.get("image_url")        # MinIO URL (浏览器可访问)
                        original_url = image_result.get("original_url")  # Ark 公网 URL (云端可访问)

                        # 第二步：从图像生成视频 (Seedance 2.0 via Ark API)
                        # 必须用原始公网 URL，Ark 云端无法访问 MinIO 内部地址
                        video_result = await seedance_service.generate_video_from_image(
                            image_url=original_url or image_url,
                            prompt=prompt,
                            duration=float(shot_dict.get('duration', 5)),
                        )

                        if video_result and video_result.get("status") == "completed":
                            video_url = video_result.get("video_url")
                            file_size = video_result.get("file_size")
                            status = "completed"
                            completed_count += 1
                        else:
                            # 视频生成失败，用图像作为降级输出
                            video_url = image_url
                            status = "completed"
                            error_msg = "视频生成失败，保留预览图"
                            completed_count += 1
                    else:
                        error_msg = "图像生成失败"
                        failed_count += 1

                except Exception as e:
                    logger.error(f"镜头 {shot_dict.get('number', '?')} 生成失败: {e}")
                    status = "failed"
                    error_msg = str(e)
                    failed_count += 1
                    video_url = None
                    image_url = None
                    file_size = None

                results.append(ShotVideoResult(
                    shot_id=shot_dict.get('id', 0),
                    shot_number=shot_dict.get('number', 0),
                    episode_id=ep.id,
                    episode_title=ep.title,
                    status=status,
                    video_url=video_url,
                    image_url=image_url,
                    file_size=file_size,
                    error=error_msg,
                ).model_dump())

                # 更新进度
                total_processed = completed_count + failed_count
                progress = int(5 + (total_processed / total_shots) * 95)
                _llmhua_tasks[task_id]["progress"] = progress

        _llmhua_tasks[task_id] = {
            "status": "completed",
            "progress": 100,
            "result": {
                "task_id": task_id,
                "total_shots": total_shots,
                "completed_shots": completed_count,
                "results": results,
            },
            "end_time": time.time(),
            "task_id": task_id,
            "task_type": "shots-to-video",
        }

        logger.info(f"批量镜头视频生成完成: {completed_count}/{total_shots} 成功")

    except Exception as e:
        logger.error(f"批量镜头视频生成失败，任务ID: {task_id}, 错误: {e}")
        _llmhua_tasks[task_id] = {
            "status": "failed",
            "progress": 0,
            "error": str(e),
            "end_time": time.time(),
            "task_type": "shots-to-video",
        }


@router.get("/shots-to-video/{task_id}/status", response_model=TaskStatusResponse)
async def get_shots_to_video_status(task_id: str):
    """
    获取批量镜头视频生成任务状态
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


@router.get("/shots-to-video/{task_id}", response_model=ShotsToVideoResponse)
async def get_shots_to_video_result(task_id: str):
    """
    获取批量镜头视频生成结果
    """
    try:
        task_info = _llmhua_tasks.get(task_id)
        if not task_info:
            raise HTTPException(status_code=404, detail="Task not found")

        if task_info["status"] != "completed":
            raise HTTPException(status_code=404, detail="Task not completed yet")

        result = task_info.get("result", {})

        return ShotsToVideoResponse(
            task_id=task_id,
            status="completed",
            message="Video generation completed",
            total_shots=result.get("total_shots", 0),
            completed_shots=result.get("completed_shots", 0),
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
