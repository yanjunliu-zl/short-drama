from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import List, Optional
import uuid

from app.schemas.script import (
    ScriptCreateRequest,
    ScriptResponse,
    ScriptListResponse,
    ScriptUpdateRequest,
    ScriptGenerationRequest,
    ScriptFromNovelRequest,
    ScriptFromOutlineRequest,
    GenerateResponse
)
from app.services.script_service import ScriptService
from app.core.deps import get_script_service

router = APIRouter()


@router.post("/generate", response_model=ScriptResponse)
async def generate_script(
    request: ScriptGenerationRequest,
    background_tasks: BackgroundTasks,
    script_service: ScriptService = Depends(get_script_service)
):
    """
    生成剧本

    使用AI模型生成新的漫剧剧本
    """
    try:
        # 异步生成剧本
        task_id = str(uuid.uuid4())

        # 将生成任务添加到后台
        background_tasks.add_task(
            script_service.generate_script_async,
            task_id=task_id,
            request=request
        )

        return ScriptResponse(
            task_id=task_id,
            status="processing",
            message="Script generation started",
            script=None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{script_id}", response_model=ScriptResponse)
async def get_script(
    script_id: str,
    script_service: ScriptService = Depends(get_script_service)
):
    """
    获取剧本详情
    """
    try:
        script = await script_service.get_script(script_id)
        if not script:
            raise HTTPException(status_code=404, detail="Script not found")

        return ScriptResponse(
            task_id=script_id,
            status="completed",
            message="Script retrieved successfully",
            script=script
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=ScriptListResponse)
async def list_scripts(
    page: int = 1,
    page_size: int = 10,
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    script_service: ScriptService = Depends(get_script_service)
):
    """
    获取剧本列表
    """
    try:
        scripts, total = await script_service.list_scripts(
            page=page,
            page_size=page_size,
            user_id=user_id,
            status=status
        )

        return ScriptListResponse(
            scripts=scripts,
            total=total,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{script_id}", response_model=ScriptResponse)
async def update_script(
    script_id: str,
    request: ScriptUpdateRequest,
    script_service: ScriptService = Depends(get_script_service)
):
    """
    更新剧本
    """
    try:
        updated_script = await script_service.update_script(script_id, request)
        if not updated_script:
            raise HTTPException(status_code=404, detail="Script not found")

        return ScriptResponse(
            task_id=script_id,
            status="completed",
            message="Script updated successfully",
            script=updated_script
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{script_id}")
async def delete_script(
    script_id: str,
    script_service: ScriptService = Depends(get_script_service)
):
    """
    删除剧本
    """
    try:
        success = await script_service.delete_script(script_id)
        if not success:
            raise HTTPException(status_code=404, detail="Script not found")

        return {"message": "Script deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{script_id}/status")
async def get_script_status(
    script_id: str,
    script_service: ScriptService = Depends(get_script_service)
):
    """
    获取剧本生成状态
    """
    try:
        status = await script_service.get_generation_status(script_id)
        if not status:
            raise HTTPException(status_code=404, detail="Script not found")

        return status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/from-novel", response_model=ScriptResponse)
async def generate_script_from_novel(
    request: ScriptFromNovelRequest,
    background_tasks: BackgroundTasks,
    script_service: ScriptService = Depends(get_script_service)
):
    """
    从小说生成剧本

    使用AI模型将小说内容转换为剧本
    """
    try:
        # 异步生成剧本
        task_id = str(uuid.uuid4())

        # 将生成任务添加到后台
        background_tasks.add_task(
            script_service.generate_script_from_novel_async,
            task_id=task_id,
            request=request
        )

        return ScriptResponse(
            task_id=task_id,
            status="processing",
            message="Script generation from novel started",
            script=None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/from-outline", response_model=ScriptResponse)
async def generate_script_from_outline(
    request: ScriptFromOutlineRequest,
    background_tasks: BackgroundTasks,
    script_service: ScriptService = Depends(get_script_service)
):
    """
    从大纲生成剧本

    使用AI模型根据剧本大纲扩展成完整剧本
    """
    try:
        # 异步生成剧本
        task_id = str(uuid.uuid4())

        # 将生成任务添加到后台
        background_tasks.add_task(
            script_service.generate_script_from_outline_async,
            task_id=task_id,
            request=request
        )

        return ScriptResponse(
            task_id=task_id,
            status="processing",
            message="Script generation from outline started",
            script=None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))