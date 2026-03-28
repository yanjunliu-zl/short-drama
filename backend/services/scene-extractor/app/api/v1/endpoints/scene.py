from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional
import logging
from datetime import datetime

from app.schemas.scene import (
    SceneExtractionRequest,
    ExtractionResponse,
    SceneResponse,
    CharacterResponse,
    PropResponse
)
from app.services.scene_extractor_service import get_scene_extractor_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=ExtractionResponse)
async def extract_scenes(request: SceneExtractionRequest, background_tasks: BackgroundTasks):
    """
    从剧本中抽取场景、角色和道具

    参数:
    - script_content: 剧本内容
    - extract_type: 抽取类型 (all/scenes/characters/props)
    - style: 图像生成风格
    """
    try:
        service = await get_scene_extractor_service()
        result = await service.extract(request)
        return result
    except Exception as e:
        logger.error(f"抽取失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenes", response_model=List[SceneResponse])
async def extract_only_scenes(request: SceneExtractionRequest):
    """
    仅抽取场景
    """
    try:
        service = await get_scene_extractor_service()
        scenes = await service.extract_scenes(request.script_content)
        return scenes
    except Exception as e:
        logger.error(f"场景抽取失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/characters", response_model=List[CharacterResponse])
async def extract_only_characters(request: SceneExtractionRequest):
    """
    仅抽取角色
    """
    try:
        service = await get_scene_extractor_service()
        characters = await service.extract_characters(request.script_content)
        return characters
    except Exception as e:
        logger.error(f"角色抽取失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/props", response_model=List[PropResponse])
async def extract_only_props(request: SceneExtractionRequest):
    """
    仅抽取道具
    """
    try:
        service = await get_scene_extractor_service()
        props = await service.extract_props(request.script_content)
        return props
    except Exception as e:
        logger.error(f"道具抽取失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-scene-images")
async def generate_scene_images(scenes: List[dict], style: str = "写实风格"):
    """
    为场景生成图像
    """
    try:
        from app.services.seedance_service import get_seedance_service

        seedance_service = await get_seedance_service()
        results = []

        for scene in scenes:
            description = scene.get("description", "")
            scene_id = scene.get("scene_id", 0)

            try:
                image_result = await seedance_service.generate_image_from_scene(
                    scene_description=description,
                    style=style
                )
                results.append({
                    "scene_id": scene_id,
                    "image_url": image_result.get("image_url") if image_result else None,
                    "status": "completed" if image_result else "failed"
                })
            except Exception as e:
                logger.warning(f"场景 {scene_id} 图像生成失败: {e}")
                results.append({
                    "scene_id": scene_id,
                    "image_url": None,
                    "status": "failed",
                    "error": str(e)
                })

        return {"results": results}
    except Exception as e:
        logger.error(f"批量生成场景图像失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
