import logging
from typing import Dict, Any, Optional, List
import uuid
import json
from datetime import datetime

from app.services.llm_service import LLMService
from app.services.seedance_service import get_seedance_service, close_seedance_service
from app.schemas.scene import (
    SceneResponse,
    CharacterResponse,
    PropResponse,
    ExtractionResponse,
    SceneExtractionRequest
)

logger = logging.getLogger(__name__)


class SceneExtractorService:
    """场景抽取服务，整合LLM和Seedance服务"""

    def __init__(self):
        self.llm_service = LLMService()
        self._initialized = False

    async def initialize(self):
        """初始化服务"""
        if self._initialized:
            return

        logger.info("初始化SceneExtractorService...")
        await self.llm_service.initialize()
        self._initialized = True
        logger.info("SceneExtractorService初始化完成")

    async def extract(self, request: SceneExtractionRequest) -> ExtractionResponse:
        """从剧本中抽取场景、角色和道具"""
        if not self._initialized:
            await self.initialize()

        try:
            logger.info(f"开始抽取: extract_type={request.extract_type}")

            # 调用LLM服务进行抽取
            if request.extract_type == "all":
                result = await self.llm_service.extract_all(request.script_content)
            elif request.extract_type == "scenes":
                result = await self.llm_service.extract_scenes(request.script_content)
            elif request.extract_type == "characters":
                result = await self.llm_service.extract_characters(request.script_content)
            elif request.extract_type == "props":
                result = await self.llm_service.extract_props(request.script_content)
            else:
                result = await self.llm_service.extract_all(request.script_content)

            # 生成图像（针对场景）
            scenes_data = result.get("scenes", [])
            for scene in scenes_data:
                try:
                    # 获取Seedance服务
                    seedance_service = await get_seedance_service()
                    # 生成场景图像
                    image_result = await seedance_service.generate_image_from_scene(
                        scene_description=scene.get("description", ""),
                        style=request.style
                    )
                    if image_result and image_result.get("image_url"):
                        scene["image_url"] = image_result.get("image_url")
                        logger.info(f"场景 {scene.get('scene_id')} 图像生成完成")
                except Exception as e:
                    logger.warning(f"场景 {scene.get('scene_id')} 图像生成失败: {e}")
                    # 图像生成失败不影响主流程

            # 转换为响应模型
            scenes = [SceneResponse(**scene) for scene in scenes_data]
            characters = [CharacterResponse(**char) for char in result.get("characters", [])]
            props = [PropResponse(**prop) for prop in result.get("props", [])]

            response = ExtractionResponse(
                scenes=scenes,
                characters=characters,
                props=props,
                extracted_at=datetime.now()
            )

            logger.info(f"抽取完成: {len(scenes)} 个场景, {len(characters)} 个角色, {len(props)} 个道具")
            return response

        except Exception as e:
            logger.error(f"抽取失败: {e}")
            raise

    async def extract_scenes(self, script_content: str) -> List[SceneResponse]:
        """仅抽取场景"""
        request = SceneExtractionRequest(
            script_content=script_content,
            extract_type="scenes"
        )
        result = await self.extract(request)
        return result.scenes

    async def extract_characters(self, script_content: str) -> List[CharacterResponse]:
        """仅抽取角色"""
        request = SceneExtractionRequest(
            script_content=script_content,
            extract_type="characters"
        )
        result = await self.extract(request)
        return result.characters

    async def extract_props(self, script_content: str) -> List[PropResponse]:
        """仅抽取道具"""
        request = SceneExtractionRequest(
            script_content=script_content,
            extract_type="props"
        )
        result = await self.extract(request)
        return result.props


# 全局服务实例
_scene_extractor_service: Optional[SceneExtractorService] = None


async def get_scene_extractor_service() -> SceneExtractorService:
    """获取全局SceneExtractor服务实例"""
    global _scene_extractor_service
    if _scene_extractor_service is None:
        _scene_extractor_service = SceneExtractorService()
        await _scene_extractor_service.initialize()
    return _scene_extractor_service


async def close_scene_extractor_service():
    """关闭全局SceneExtractor服务实例"""
    global _scene_extractor_service
    if _scene_extractor_service:
        await close_seedance_service()
        _scene_extractor_service = None
