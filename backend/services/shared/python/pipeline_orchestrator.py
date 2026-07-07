"""
AI 全链路流水线编排 — 剧本→场景提取→分镜→图像→视频串联。

提供跨服务编排能力，可独立部署为编排服务或被各服务调用。
"""
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class PipelineStage(str, Enum):
    SCRIPT = "script"            # 剧本生成
    EXTRACT_SCENES = "extract"    # 场景提取
    STORYBOARD = "storyboard"     # 分镜生成
    IMAGES = "images"             # 图像生成
    VIDEOS = "videos"             # 视频生成


@dataclass
class PipelineState:
    """全链路流水线状态"""
    stage: PipelineStage = PipelineStage.SCRIPT
    progress: int = 0

    # Stage outputs
    script: Optional[Dict[str, Any]] = None
    extracted_scenes: Optional[List[Dict[str, Any]]] = None
    storyboard: Optional[Dict[str, Any]] = None
    images: Optional[List[Dict[str, Any]]] = None
    videos: Optional[List[Dict[str, Any]]] = None

    # Metadata
    errors: List[str] = field(default_factory=list)
    stage_elapsed: Dict[str, float] = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        return self.stage == PipelineStage.VIDEOS and not self.errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage.value,
            "progress": self.progress,
            "script": self.script,
            "extracted_scenes": self.extracted_scenes,
            "storyboard": self.storyboard,
            "images": self.images,
            "videos": self.videos,
            "errors": self.errors,
            "stage_elapsed": self.stage_elapsed,
        }


# ============================================================
# 场景→分镜数据转换器
# ============================================================

def convert_scenes_to_storyboard_input(
    extracted_scenes: List[Dict[str, Any]],
    style: str = "写实风格",
) -> Dict[str, Any]:
    """Convert scene-extractor output to storyboard-service input format.

    Maps:
      SceneResponse → ShotGenerationRequest.episodeContents
      CharacterResponse → ShotGenerationRequest.characterNames
      SceneResponse.location → sceneRef

    Args:
        extracted_scenes: List of scene dicts from scene-extractor.
        style: Visual style string.

    Returns:
        Dict compatible with ShotGenerationRequest.
    """
    episode_contents = []
    all_characters = set()
    all_locations = set()

    for i, scene in enumerate(extracted_scenes):
        desc = scene.get("description", "")
        location = scene.get("location", "")
        characters = scene.get("characters", [])
        time_of_day = scene.get("time_of_day", "白天")

        episode_text = (
            f"**{i+1}-{i+1} {time_of_day} {location}**\n"
            f"△{desc}\n"
            f"人物：{'、'.join(characters) if characters else '无'}\n"
        )
        episode_contents.append(episode_text)

        for c in characters:
            all_characters.add(c)
        if location:
            all_locations.add(location)

    return {
        "title": "Scene-Extracted Storyboard",
        "script": "\n\n".join(episode_contents),
        "episodeCount": len(extracted_scenes),
        "episodeContents": episode_contents,
        "style": style,
        "sceneRefs": list(all_locations),
        "characterNames": list(all_characters),
    }


def convert_storyboard_to_image_input(
    storyboard: Dict[str, Any],
    style: str = "写实风格",
) -> List[Dict[str, Any]]:
    """Convert storyboard output to llmhua-service image generation input.

    Extracts scene descriptions from storyboard episodes/shots.

    Args:
        storyboard: Storyboard output dict with 'episodes' key.
        style: Visual style.

    Returns:
        List of dicts compatible with StoryboardToImageRequest.
    """
    scenes = []
    for ep in storyboard.get("episodes", []):
        for shot in ep.get("shots", []):
            scenes.append({
                "scene_description": shot.get("description", ""),
                "storyboard_id": storyboard.get("task_id", "unknown"),
                "scene_number": shot.get("number", 0),
                "style": style,
            })
    return scenes
