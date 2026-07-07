import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.usage_tracker import track_image_usage, track_video_usage
from app.services.task_store import get_task_store
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
from app.core.config import settings
from app.utils.sse import format_sse_event, EVENT_PROGRESS, EVENT_ERROR, EVENT_DONE

router = APIRouter()

logger = logging.getLogger(__name__)


# ==================== 图像生成端点 ====================

@router.post("/images/generate", response_model=ImageGenerationResponse)
async def generate_image_from_scene(
    request: StoryboardToImageRequest,
    background_tasks: BackgroundTasks,
    seedance_service=Depends(get_seedance_service)
):
    """
    根据分镜镜头描述生成单个镜头图像。
    设置 stream=true 启用 SSE 流式输出 (progress 事件)。
    """
    use_streaming = getattr(request, "stream", False) and settings.SSE_STREAMING_ENABLED

    if use_streaming:
        logger.info(f"[API] POST /images/generate (stream)")

        async def event_generator():
            try:
                yield format_sse_event({"stage": "starting", "progress": 0}, event=EVENT_PROGRESS)
                yield format_sse_event({"stage": "submitting_job", "progress": 10}, event=EVENT_PROGRESS)

                result = await seedance_service.generate_image_from_scene(
                    scene_description=request.scene_description,
                    style=request.style or "写实风格",
                    width=request.width or 1920,
                    height=request.height or 1920,
                    seed=request.seed,
                )

                if result and result.get("status") == "completed":
                    yield format_sse_event({"stage": "processing", "progress": 80}, event=EVENT_PROGRESS)
                    yield format_sse_event(result, event=EVENT_DONE)
                else:
                    yield format_sse_event({"error": "Image generation failed", "detail": result}, event=EVENT_ERROR)
            except Exception as e:
                logger.error(f"[API] Stream error: {e}")
                yield format_sse_event({"error": str(e), "code": type(e).__name__}, event=EVENT_ERROR)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    # Legacy non-streaming path
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
    task_store = await get_task_store()
    try:
        await task_store.create(task_id, {
            "status": "processing",
            "progress": 10,
            "result": None,
            "start_time": time.time(),
        })

        # 调用Seedance生成图像
        result = await seedance_service.generate_image_from_scene(
            scene_description=request.scene_description,
            style=request.style,
            width=request.width or 1920,
            height=request.height or 1920,
            seed=request.seed
        )

        if result and result.get("status") == "completed":
            await task_store.set(task_id, {
                "status": "completed",
                "progress": 100,
                "result": result,
                "end_time": time.time(),
                "task_id": task_id
            })
        else:
            await task_store.set(task_id, {
                "status": "failed",
                "progress": 0,
                "error": "Failed to generate image",
                "end_time": time.time()
            })

    except Exception as e:
        logger.error(f"图像生成失败，任务ID: {task_id}, 错误: {e}")
        await task_store.set(task_id, {
            "status": "failed",
            "progress": 0,
            "error": str(e),
            "end_time": time.time()
        })


@router.get("/images/{task_id}", response_model=ImageGenerationResponse)
async def get_image_generation_result(task_id: str):
    """
    获取图像生成结果
    """
    try:
        task_store = await get_task_store()
        task_info = await task_store.get(task_id)
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
        task_store = await get_task_store()
        task_info = await task_store.get(task_id)
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


# ==================== 角色形象设计端点 ====================

class CharacterDesignAPIRequest(BaseModel):
    name: str = Field(..., description="角色姓名")
    role: str = Field(default="supporting")
    gender: str = Field(default="男")
    age: int = Field(default=25)
    description: str = Field(default="")
    personality: str = Field(default="")
    appearance: str = Field(default="")
    era: str = Field(default="现代")
    genre: str = Field(default="")
    storyOutline: str = Field(default="")
    characterBios: str = Field(default="")
    episodeCount: int = Field(default=1)
    promptLanguage: str = Field(default="zh")
    style: str = Field(default="写实")
    generateImage: bool = Field(default=False, description="是否同时生成角色设定图")
    imageWidth: int = Field(default=1024)
    imageHeight: int = Field(default=1024)


@router.post("/character/design")
async def design_character(
    request: CharacterDesignAPIRequest,
    background_tasks: BackgroundTasks,
    seedance_service=Depends(get_seedance_service)
):
    """
    角色形象设计 — AI 生成 6 层身份锚点 + 可选角色设定图。

    返回角色设计结果（含 identityAnchors、visualPrompt、negativePrompt），
    若 generateImage=True 则同时提交图像生成任务。
    """
    try:
        from app.services.character_design_service import (
            CharacterDesignRequest,
            enrich_character_with_anchors,
            create_llm_client,
        )

        llm = create_llm_client()
        if not llm:
            raise HTTPException(status_code=503, detail="AI 服务未初始化（需配置 API Key）")

        design_req = CharacterDesignRequest(
            name=request.name,
            role=request.role,
            gender=request.gender,
            age=request.age,
            description=request.description,
            personality=request.personality,
            appearance=request.appearance,
            era=request.era,
            genre=request.genre,
            storyOutline=request.storyOutline,
            characterBios=request.characterBios,
            episodeCount=request.episodeCount,
            promptLanguage=request.promptLanguage,
        )

        result = await enrich_character_with_anchors(llm, design_req)

        response: Dict[str, Any] = {
            "name": result.name,
            "detailedDescription": result.detailedDescription,
            "visualPromptEn": result.visualPromptEn,
            "visualPromptZh": result.visualPromptZh,
            "clothingStyle": result.clothingStyle,
            "negativePrompt": result.negativePrompt,
        }

        if result.identityAnchors:
            response["identityAnchors"] = result.identityAnchors.model_dump()

        # 可选：同时生成图像
        image_task_id = None
        if request.generateImage and result.visualPromptZh:
            image_task_id = str(uuid.uuid4())
            prompt = result.visualPromptZh
            background_tasks.add_task(
                _generate_preview_image_task,
                task_id=image_task_id,
                prompt=prompt,
                style=request.style,
                width=request.imageWidth,
                height=request.imageHeight,
                seedance_service=seedance_service
            )
            response["imageTaskId"] = image_task_id
            response["message"] = "角色设计完成，图像生成已提交"

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 预览图像生成端点（场景/角色/道具） ====================

def _build_preview_prompt(description: str, category: str, style: str) -> str:
    """根据类型构建预览图像提示词"""
    if category == "character":
        # 使用专业角色设计提示词
        from app.services.character_design_service import CharacterDesignService
        return CharacterDesignService.build_character_sheet_prompt(
            name=description[:30] if description else "角色",
            description=description,
            style=style,
            language="zh",
        )
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
    设置 stream=true 启用 SSE 流式输出 (progress 事件)。
    """
    use_streaming = getattr(request, "stream", False) and settings.SSE_STREAMING_ENABLED

    if use_streaming:
        prompt = _build_preview_prompt(request.description, request.category, request.style or "写实风格")
        logger.info(f"[API] POST /preview-image (stream) category={request.category}")

        async def event_generator():
            try:
                yield format_sse_event({"stage": "starting", "progress": 0}, event=EVENT_PROGRESS)
                result = await seedance_service.generate_image_from_scene(
                    scene_description=prompt,
                    style=request.style or "写实风格",
                    width=request.width or 1024,
                    height=request.height or 1024,
                )
                if result and result.get("status") == "completed":
                    yield format_sse_event({"stage": "completed", "progress": 100}, event=EVENT_PROGRESS)
                    yield format_sse_event(result, event=EVENT_DONE)
                else:
                    yield format_sse_event({"error": "Preview generation failed"}, event=EVENT_ERROR)
            except Exception as e:
                yield format_sse_event({"error": str(e), "code": type(e).__name__}, event=EVENT_ERROR)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    # Legacy non-streaming path
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
    task_store = await get_task_store()
    try:
        await task_store.create(task_id, {
            "status": "processing",
            "progress": 10,
            "result": None,
            "start_time": time.time(),
            "task_type": "preview-image",
        })

        result = await seedance_service.generate_image_from_scene(
            scene_description=prompt,
            style=style,
            width=width,
            height=height,
        )

        if result and result.get("status") == "completed":
            await task_store.set(task_id, {
                "status": "completed",
                "progress": 100,
                "result": result,
                "end_time": time.time(),
                "task_id": task_id,
                "task_type": "preview-image",
            })
        else:
            err_detail = result.get("message", "") if result else "API返回为空"
            await task_store.set(task_id, {
                "status": "failed",
                "progress": 0,
                "error": f"Failed to generate preview image: {err_detail}",
                "end_time": time.time(),
                "task_type": "preview-image",
            })

    except Exception as e:
        logger.error(f"预览图像生成失败，任务ID: {task_id}, 错误: {e}")
        await task_store.set(task_id, {
            "status": "failed",
            "progress": 0,
            "error": str(e),
            "end_time": time.time(),
            "task_type": "preview-image",
        })


@router.get("/preview-image/{task_id}/status")
async def get_preview_image_status(task_id: str):
    """获取预览图像生成状态"""
    try:
        task_store = await get_task_store()
        task_info = await task_store.get(task_id)
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
    根据图像生成对应视频。
    设置 stream=true 启用 SSE 流式输出 (progress 事件)。
    """
    use_streaming = getattr(request, "stream", False) and settings.SSE_STREAMING_ENABLED

    if use_streaming:
        logger.info(f"[API] POST /videos/generate (stream)")

        async def event_generator():
            try:
                yield format_sse_event({"stage": "starting", "progress": 0}, event=EVENT_PROGRESS)
                yield format_sse_event({"stage": "submitting_task", "progress": 5}, event=EVENT_PROGRESS)

                result = await seedance_service.generate_video_from_image(
                    image_url=request.image_url,
                    prompt=request.prompt or request.image_url,
                    duration=request.duration,
                    seed=request.seed,
                )

                if result and result.get("status") == "completed":
                    yield format_sse_event({"stage": "completed", "progress": 100}, event=EVENT_PROGRESS)
                    yield format_sse_event(result, event=EVENT_DONE)
                else:
                    yield format_sse_event({"error": "Video generation failed", "detail": result}, event=EVENT_ERROR)
            except Exception as e:
                logger.error(f"[API] Stream error: {e}")
                yield format_sse_event({"error": str(e), "code": type(e).__name__}, event=EVENT_ERROR)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    # Legacy non-streaming path
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
    task_store = await get_task_store()
    try:
        await task_store.create(task_id, {
            "status": "processing",
            "progress": 10,
            "result": None,
            "start_time": time.time(),
        })

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
            await task_store.set(task_id, {
                "status": "completed",
                "progress": 100,
                "result": result,
                "end_time": time.time(),
                "task_id": task_id
            })
        else:
            await task_store.set(task_id, {
                "status": "failed",
                "progress": 0,
                "error": "Failed to generate video",
                "end_time": time.time()
            })

    except Exception as e:
        logger.error(f"视频生成失败，任务ID: {task_id}, 错误: {e}")
        await task_store.set(task_id, {
            "status": "failed",
            "progress": 0,
            "error": str(e),
            "end_time": time.time()
        })


@router.get("/videos/{task_id}", response_model=VideoGenerationResponse)
async def get_video_generation_result(task_id: str):
    """
    获取视频生成结果
    """
    try:
        task_store = await get_task_store()
        task_info = await task_store.get(task_id)
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
        task_store = await get_task_store()
        task_info = await task_store.get(task_id)
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
    根据分镜生成所有镜头图像并转换为视频（完整流程）。
    设置 stream=true 启用 SSE 流式输出 (progress 事件逐场景推送)。
    """
    use_streaming = getattr(request, "stream", False) and settings.SSE_STREAMING_ENABLED

    if use_streaming:
        total_scenes = len(request.scenes)
        logger.info(f"[API] POST /storyboard/generate-complete (stream) scenes={total_scenes}")

        async def event_generator():
            try:
                yield format_sse_event({"stage": "starting", "total_scenes": total_scenes, "progress": 0}, event=EVENT_PROGRESS)
                results = []
                for idx, scene in enumerate(request.scenes):
                    scene_number = scene.get("scene_number", idx + 1)
                    desc = scene.get("description", "")
                    yield format_sse_event({"stage": "scene_start", "scene_number": scene_number, "progress": int(idx / total_scenes * 90)}, event=EVENT_PROGRESS)

                    img_result = await seedance_service.generate_image_from_scene(
                        scene_description=desc, style=request.style or "写实风格",
                    )
                    if request.generate_video and img_result and img_result.get("image_url"):
                        yield format_sse_event({"stage": "video_start", "scene_number": scene_number, "progress": int((idx + 0.5) / total_scenes * 90)}, event=EVENT_PROGRESS)
                        vid_result = await seedance_service.generate_video_from_image(
                            image_url=img_result["image_url"],
                            prompt=desc,
                        )
                        results.append(SceneResult(
                            scene_number=scene_number,
                            image_url=img_result.get("image_url"),
                            video_url=vid_result.get("video_url") if vid_result else None,
                            status="completed" if vid_result else "partial",
                        ))
                    elif img_result:
                        results.append(SceneResult(
                            scene_number=scene_number,
                            image_url=img_result.get("image_url"),
                            status="completed",
                        ))
                    else:
                        results.append(SceneResult(scene_number=scene_number, status="failed", error="Image generation failed"))

                yield format_sse_event({"stage": "completed", "progress": 100}, event=EVENT_PROGRESS)
                yield format_sse_event({"storyboard_id": request.storyboard_id, "total_scenes": total_scenes, "successful_scenes": sum(1 for r in results if r.status == "completed"), "results": [r.dict() for r in results]}, event=EVENT_DONE)
            except Exception as e:
                yield format_sse_event({"error": str(e), "code": type(e).__name__}, event=EVENT_ERROR)

        return StreamingResponse(event_generator(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})

    # Legacy non-streaming path
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
    task_store = await get_task_store()
    try:
        await task_store.create(task_id, {
            "status": "processing",
            "progress": 5,
            "result": None,
            "start_time": time.time(),
        })

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

            # 更新进度（部分更新，不覆盖整个任务状态）
            await task_store.update(task_id, {"progress": int(5 + (idx + 1) / len(request.scenes) * 95)})

        await task_store.set(task_id, {
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
        })

    except Exception as e:
        logger.error(f"完整分镜生成失败，任务ID: {task_id}, 错误: {e}")
        await task_store.set(task_id, {
            "status": "failed",
            "progress": 0,
            "error": str(e),
            "end_time": time.time()
        })


@router.get("/storyboard/{task_id}/result", response_model=CompleteResult)
async def get_complete_storyboard_result(task_id: str):
    """
    获取完整分镜生成结果
    """
    try:
        task_store = await get_task_store()
        task_info = await task_store.get(task_id)
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
    从分镜头结构化字段构建视频生成提示词 — 5层语义结构（移植自 moyin-creator）

    Layer 1: 镜头设计（景别、机位、运动、角度、景深、设备）
    Layer 1.5: 灯光（风格、方向、色温）
    Layer 2: 主体与焦点（角色、画面描述、对白、焦点变换）
    Layer 3: 情绪与氛围（情绪标签、氛围特效）
    Layer 4: 场景与音频（场景名称、音效、背景音乐）
    Layer 5: 视觉风格
    """
    parts = []

    # ---- Layer 5: 风格 ----
    if style:
        parts.append(f"视觉风格：{style}")

    # ---- Layer 1: 镜头设计 ----
    layer1 = []
    if shot.get('shotType'):
        layer1.append(f"景别{shot['shotType']}")
    if shot.get('cameraAngle'):
        layer1.append(f"角度{shot['cameraAngle']}")
    if shot.get('cameraMovement'):
        layer1.append(f"运动{shot['cameraMovement']}")
    if shot.get('cameraRig'):
        rig_map = {"三脚架": "固定机位", "手持": "手持摄影", "斯坦尼康": "斯坦尼康稳定", "滑轨": "滑轨平移", "摇臂": "摇臂升降", "无人机": "空中俯拍"}
        layer1.append(rig_map.get(shot['cameraRig'], shot['cameraRig']))
    if shot.get('movementSpeed'):
        layer1.append(f"速度{shot['movementSpeed']}")
    if shot.get('depthOfField'):
        layer1.append(f"景深{shot['depthOfField']}")
    if shot.get('focusTarget'):
        layer1.append(f"对焦{shot['focusTarget']}")
    if shot.get('focusTransition'):
        layer1.append(f"焦点转移{shot['focusTransition']}")
    if shot.get('focalLength'):
        layer1.append(f"焦距{shot['focalLength']}")
    if shot.get('photographyTechnique'):
        layer1.append(f"技法{shot['photographyTechnique']}")
    if layer1:
        parts.append("，".join(layer1))

    # ---- Layer 1.5: 灯光 ----
    layer1_5 = []
    if shot.get('lightingStyle'):
        layer1_5.append(f"灯光{shot['lightingStyle']}")
    if shot.get('lightingDirection'):
        layer1_5.append(f"方向{shot['lightingDirection']}")
    if shot.get('colorTemperature'):
        layer1_5.append(f"色温{shot['colorTemperature']}")
    if shot.get('lightingNotes'):
        layer1_5.append(shot['lightingNotes'])
    if layer1_5:
        parts.append("，".join(layer1_5))

    # ---- Layer 2: 主体与焦点 ----
    layer2 = []
    characters = shot.get('characters', [])
    if characters:
        layer2.append(f"角色：{'、'.join(characters)}")
    if shot.get('description'):
        layer2.append(f"画面：{shot['description'][:300]}")
    if shot.get('dialogue'):
        layer2.append(f"对白：{shot['dialogue'][:200]}")
    if layer2:
        parts.append("，".join(layer2))

    # ---- Layer 3: 情绪与氛围 ----
    layer3 = []
    emotion_tags = shot.get('emotionTags', [])
    if emotion_tags:
        layer3.append(f"情绪：{'→'.join(emotion_tags)}")
    if shot.get('narrativeFunction'):
        layer3.append(f"叙事：{shot['narrativeFunction']}")
    if shot.get('atmosphericEffects'):
        intensity = shot.get('effectIntensity', '适中')
        layer3.append(f"氛围特效：{shot['atmosphericEffects']}（{intensity}）")
    if layer3:
        parts.append("，".join(layer3))

    # ---- Layer 4: 场景与音频 ----
    layer4 = []
    if shot.get('sceneRef'):
        layer4.append(f"场景：{shot['sceneRef']}")
    sound_effects = shot.get('soundEffects', [])
    if sound_effects:
        layer4.append(f"音效：{'、'.join(sound_effects)}")
    if shot.get('music'):
        layer4.append(f"背景音乐：{shot['music']}")
    if layer4:
        parts.append("，".join(layer4))

    # ---- 三层提示词优先级 ----
    # 如果已有完整的 videoPrompt（AI生成），直接使用
    if shot.get('videoPromptZh'):
        return shot['videoPromptZh']

    return "。".join(parts) + "。流畅动画，电影级质量。"


@router.post("/shots-to-video", response_model=ShotsToVideoResponse)
async def generate_shots_to_video(
    request: ShotsToVideoRequest,
    background_tasks: BackgroundTasks,
    seedance_service=Depends(get_seedance_service)
):
    """
    为每个分镜头批量生成视频。

    对每个 shot：构建视频提示词 -> 生成图像 -> 生成视频 -> 存储到 Ceph。
    设置 stream=true 启用 SSE 流式输出 (progress 事件逐镜头推送)。
    """
    use_streaming = getattr(request, "stream", False) and settings.SSE_STREAMING_ENABLED

    if use_streaming:
        total_shots = sum(len(ep.shots) for ep in request.episodes)
        logger.info(f"[API] POST /shots-to-video (stream) shots={total_shots}")

        # #S1: Build character consistency context from reference images
        ref_chars = {}
        if request.referenceImages and request.referenceImages.characters:
            ref_chars = request.referenceImages.characters  # name → image_url

        async def generate_shot_image(shot, ep_idx: int):
            """Generate image+video for a single shot with retry. Returns ShotVideoResult dict."""
            # #S2: Use PromptBuilder-enriched prompt if available, else raw description
            img_prompt = (
                shot.imagePromptZh or shot.imagePrompt or
                shot.description
            )

            # #S1: Append character consistency hint if reference images exist
            if ref_chars and shot.characters:
                char_refs = [f"{c}参考图:{ref_chars[c]}" for c in shot.characters if c in ref_chars]
                if char_refs:
                    img_prompt = f"{img_prompt}。角色视觉参考: {'; '.join(char_refs)}"

            # #S3: Retry image generation up to 2 times
            img_result = None
            for attempt in range(2):
                img_result = await seedance_service.generate_image_from_scene(
                    scene_description=img_prompt[:500],
                    style=request.style or "写实风格",
                    width=request.width or 1920, height=request.height or 1920,
                )
                if img_result and img_result.get("image_url"):
                    break
                logger.warning(f"Shot {shot.number} image attempt {attempt+1}/2 failed, retrying...")

            video_url = None
            if img_result and img_result.get("image_url"):
                vid_prompt = _build_shot_video_prompt(shot, request.style or "写实风格", request.referenceImages)
                # #S5: Adaptive duration — longer dialogue = longer video
                dialogue_len = len(shot.dialogue or "")
                adaptive_duration = max(3, min(15, shot.duration or 5, int(dialogue_len / 3) + 3))
                vid_result = await seedance_service.generate_video_from_image(
                    image_url=img_result["image_url"], prompt=vid_prompt,
                    duration=adaptive_duration,
                )
                video_url = vid_result.get("video_url") if vid_result else None

            return ShotVideoResult(
                shot_id=shot.id, shot_number=shot.number,
                episode_id=ep.id, episode_title=ep.title,
                status="completed" if video_url else "failed",
                video_url=video_url,
                image_url=img_result.get("image_url") if img_result else None,
            ).dict()

        async def event_generator():
            try:
                yield format_sse_event({"stage": "starting", "total_shots": total_shots, "progress": 0}, event=EVENT_PROGRESS)
                results = []
                completed = 0

                for ep in request.episodes:
                    ep_shots = ep.shots
                    # #S6: Process shots within an episode concurrently (max 3)
                    sem = asyncio.Semaphore(3)
                    async def process_one(s):
                        async with sem:
                            return await generate_shot_image(s, ep.number)
                    shot_tasks = [process_one(s) for s in ep_shots]
                    ep_results = await asyncio.gather(*shot_tasks)

                    for r in ep_results:
                        results.append(r)
                        if r["status"] == "completed":
                            completed += 1
                        yield format_sse_event(
                            {"stage": "shot_done", "shot_number": r["shot_number"],
                             "completed": completed, "total": total_shots,
                             "progress": int(5 + (completed / total_shots) * 95)},
                            event=EVENT_PROGRESS,
                        )

                yield format_sse_event({"stage": "completed", "progress": 100}, event=EVENT_PROGRESS)
                yield format_sse_event({"results": results, "total_shots": total_shots, "completed_shots": completed}, event=EVENT_DONE)
            except Exception as e:
                logger.error(f"shots-to-video stream error: {e}")
                yield format_sse_event({"error": str(e), "code": type(e).__name__}, event=EVENT_ERROR)

        return StreamingResponse(event_generator(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})

    # Legacy non-streaming path
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
    task_store = await get_task_store()
    try:
        total_shots = sum(len(ep.shots) for ep in request.episodes)

        await task_store.create(task_id, {
            "status": "processing",
            "progress": 5,
            "result": None,
            "start_time": time.time(),
            "task_type": "shots-to-video",
        })

        results: list = []
        completed_count = 0
        failed_count = 0
        scene_seeds: dict = {}  # #S11: shared seeds per scene for cross-shot consistency

        for ep in request.episodes:
            for shot in ep.shots:
                shot_dict = shot.model_dump() if hasattr(shot, 'model_dump') else shot

                try:
                    # 三层提示词：优先使用 AI 生成的 imagePrompt/videoPrompt
                    image_prompt = shot_dict.get('imagePromptZh') or shot_dict.get('imagePrompt')
                    video_prompt = shot_dict.get('videoPromptZh') or shot_dict.get('videoPrompt')
                    end_frame_prompt = shot_dict.get('endFramePromptZh') or shot_dict.get('endFramePrompt')
                    needs_end_frame = shot_dict.get('needsEndFrame', False)

                    # 如果没有 AI 生成的提示词，回退到 5 层构建
                    if not image_prompt:
                        image_prompt = _build_shot_video_prompt(shot_dict, request.style or "")
                    if not video_prompt:
                        video_prompt = image_prompt  # 回退：用图像提示词驱动视频

                    # 第一步：查找参考图像（角色/场景预览图），保持视觉一致性
                    reference_image_url = None
                    if request.referenceImages:
                        # 优先使用第一个角色的参考图作为角色一致性锚点
                        chars = shot_dict.get('characters', []) or []
                        ref_chars = request.referenceImages.characters or {}
                        for ch in chars:
                            if ch in ref_chars and ref_chars[ch]:
                                reference_image_url = ref_chars[ch]
                                logger.info(f"镜头 {shot_dict.get('number','?')} 使用角色参考图: {ch}")
                                break
                        # 如果没有角色参考图，尝试场景参考图
                        if not reference_image_url:
                            scene_ref = shot_dict.get('sceneRef', '')
                            ref_scenes = request.referenceImages.scenes or {}
                            if scene_ref and scene_ref in ref_scenes and ref_scenes[scene_ref]:
                                reference_image_url = ref_scenes[scene_ref]
                                logger.info(f"镜头 {shot_dict.get('number','?')} 使用场景参考图: {scene_ref}")

                    # #S11: Cross-shot consistency — shared seed per scene
                    scene_ref = shot_dict.get('sceneRef', '')
                    if scene_ref not in scene_seeds:
                        scene_seeds[scene_ref] = hash(scene_ref + str(shot_dict.get('number', 0))) % (2**31)
                    shared_seed = scene_seeds[scene_ref]

                    # 生成首帧图像：有参考图则跳过生成直接用参考图
                    if reference_image_url:
                        image_result = {"status": "completed", "image_url": reference_image_url,
                                       "original_url": reference_image_url}
                        logger.info(f"镜头 {shot_dict.get('number','?')} 复用参考图像，跳过文生图")
                    else:
                        image_result = await seedance_service.generate_image_from_scene(
                            scene_description=image_prompt,
                            style=request.style,
                            seed=shared_seed,  # Shared seed for scene consistency
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
                        # 使用 video_prompt（三层提示词的动作层）而非图像提示词
                        video_result = await seedance_service.generate_video_from_image(
                            image_url=original_url or image_url,
                            prompt=video_prompt,
                            duration=float(shot_dict.get('duration', 5)),
                        )

                        if video_result and video_result.get("status") == "completed":
                            video_url = video_result.get("video_url")
                            file_size = video_result.get("file_size")
                            status = "completed"
                            completed_count += 1
                        else:
                            # 视频生成失败 — 显式标记为 image_only，不伪装成 completed
                            video_url = None
                            status = "image_only"
                            error_msg = "视频生成失败，仅保留预览图"
                            # Do NOT increment completed_count — video wasn't completed
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

                # 更新进度（部分更新）
                total_processed = completed_count + failed_count
                progress = int(5 + (total_processed / total_shots) * 95)
                await task_store.update(task_id, {"progress": progress})

        await task_store.set(task_id, {
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
        })

        logger.info(f"批量镜头视频生成完成: {completed_count}/{total_shots} 成功")
        # 记录用量：图像生成数 + 视频生成数
        await track_image_usage(
            user_id=request.user_id or '',
            model_name="seedream-4.5",
            count=completed_count,
            endpoint="/shots-to-video",
            service_name="llmhua-service",
        )
        await track_video_usage(
            user_id=request.user_id or '',
            model_name="seedance-2.0",
            count=completed_count,
            endpoint="/shots-to-video",
            service_name="llmhua-service",
        )

    except Exception as e:
        logger.error(f"批量镜头视频生成失败，任务ID: {task_id}, 错误: {e}")
        await task_store.set(task_id, {
            "status": "failed",
            "progress": 0,
            "error": str(e),
            "end_time": time.time(),
            "task_type": "shots-to-video",
        })


@router.get("/shots-to-video/{task_id}/status", response_model=TaskStatusResponse)
async def get_shots_to_video_status(task_id: str):
    """
    获取批量镜头视频生成任务状态
    """
    try:
        task_store = await get_task_store()
        task_info = await task_store.get(task_id)
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
        task_store = await get_task_store()
        task_info = await task_store.get(task_id)
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
