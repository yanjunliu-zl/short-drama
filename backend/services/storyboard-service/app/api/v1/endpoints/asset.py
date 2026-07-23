"""资产库 API — 角色视觉资产、场景模板、分镜预设的 CRUD。"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
import logging

from app.services.asset_library import (
    AssetLibrary, AssetType, AssetVisibility,
    CharacterAsset, SceneTemplate, ShotPreset,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# 全局单例（生产环境用 DB 替代）
_asset_library: Optional[AssetLibrary] = None


def get_asset_library() -> AssetLibrary:
    global _asset_library
    if _asset_library is None:
        _asset_library = AssetLibrary.with_presets()
    return _asset_library


# ═══════════════ 角色资产 ═══════════════

@router.post("/characters")
async def create_character(data: dict):
    """创建角色视觉资产"""
    lib = get_asset_library()
    char = lib.create_character(**data)
    return {"success": True, "data": char.to_dict()}


@router.get("/characters")
async def list_characters(
    role_type: str = "",
    tags: Optional[str] = None,  # comma-separated
    sort_by: str = "usage_count",
    limit: int = 50,
):
    """列出角色资产"""
    lib = get_asset_library()
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    chars = lib.list_characters(
        role_type=role_type, tags=tag_list, sort_by=sort_by, limit=limit
    )
    return {"success": True, "data": [c.to_dict() for c in chars], "total": len(chars)}


@router.get("/characters/search")
async def search_characters(q: str = Query(..., min_length=1), limit: int = 20):
    """搜索角色资产"""
    lib = get_asset_library()
    results = lib.search_characters(q, limit=limit)
    return {"success": True, "data": [c.to_dict() for c in results], "total": len(results)}


@router.get("/characters/{asset_id}")
async def get_character(asset_id: str):
    """获取单个角色资产"""
    lib = get_asset_library()
    char = lib.get_character(asset_id)
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
    return {"success": True, "data": char.to_dict()}


@router.put("/characters/{asset_id}")
async def update_character(asset_id: str, data: dict):
    """更新角色资产"""
    lib = get_asset_library()
    char = lib.update_character(asset_id, **data)
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
    return {"success": True, "data": char.to_dict()}


# ═══════════════ 场景模板 ═══════════════

@router.post("/scenes")
async def create_scene(data: dict):
    """创建场景模板"""
    lib = get_asset_library()
    scene = lib.create_scene(**data)
    return {"success": True, "data": scene.to_dict()}


@router.get("/scenes")
async def list_scenes(
    category: str = "",
    tags: Optional[str] = None,
    limit: int = 50,
):
    """列出场景模板"""
    lib = get_asset_library()
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    scenes = lib.list_scenes(category=category, tags=tag_list, limit=limit)
    return {"success": True, "data": [s.to_dict() for s in scenes], "total": len(scenes)}


@router.get("/scenes/{template_id}")
async def get_scene(template_id: str):
    """获取单个场景模板"""
    lib = get_asset_library()
    scene = lib.get_scene(template_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene template not found")
    return {"success": True, "data": scene.to_dict()}


# ═══════════════ 分镜预设 ═══════════════

@router.post("/shot-presets")
async def create_shot_preset(data: dict):
    """创建分镜预设"""
    lib = get_asset_library()
    preset = lib.create_shot_preset(**data)
    return {"success": True, "data": preset.to_dict()}


@router.get("/shot-presets")
async def list_shot_presets(
    shot_type: str = "",
    tags: Optional[str] = None,
    limit: int = 50,
):
    """列出分镜预设"""
    lib = get_asset_library()
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    presets = lib.list_shot_presets(shot_type=shot_type, tags=tag_list, limit=limit)
    return {"success": True, "data": [p.to_dict() for p in presets], "total": len(presets)}


@router.get("/shot-presets/{preset_id}")
async def get_shot_preset(preset_id: str):
    """获取单个分镜预设"""
    lib = get_asset_library()
    preset = lib.get_shot_preset(preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Shot preset not found")
    return {"success": True, "data": preset.to_dict()}


# ═══════════════ 批量上下文 ═══════════════

@router.post("/build-context")
async def build_episode_context(data: dict):
    """构建单集的完整资产上下文（分镜/视频生成前调用）"""
    lib = get_asset_library()
    result = lib.build_episode_context(
        character_ids=data.get("character_ids", []),
        scene_template_id=data.get("scene_template_id", ""),
        shot_preset_ids=data.get("shot_preset_ids", []),
    )
    return {"success": True, "data": result}
