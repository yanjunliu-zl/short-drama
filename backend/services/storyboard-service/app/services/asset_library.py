"""
资产库服务 — 角色视觉资产 · 场景模板 · 分镜预设 · 团队协作

对标 LibTV 的"协同与资产沉淀"原则：
- 角色三视图资产化（跨剧集一致性 ≥95%）
- 场景模板可复用（常见短剧场景 + 预设灯光/机位）
- 分镜预设库（爆款镜头构图可沉淀复用）
- 团队级资产共享（数据引力护城河）

设计理念：
- 资产 = 数据 + 引用计数 + 版本历史
- 每个资产有唯一的视觉参考 ID，可在 Seedance prompt 中引用
- 资产越用越准（反馈闭环：生成结果 → 评分 → 资产优化）
"""
import logging
import json
import time
import hashlib
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════

class AssetType(str, Enum):
    CHARACTER = "character"       # 角色视觉资产
    SCENE = "scene"               # 场景模板
    SHOT_PRESET = "shot_preset"   # 分镜预设
    LIGHTING = "lighting"         # 灯光方案
    CAMERA_RIG = "camera_rig"     # 机位方案


class AssetVisibility(str, Enum):
    PRIVATE = "private"           # 仅创建者可见
    TEAM = "team"                 # 团队内共享
    PUBLIC = "public"             # 全平台公开


@dataclass
class CharacterAsset:
    """角色视觉资产 — 对标 LibTV 的角色三视图。

    核心价值：跨剧集角色一致性。Seedance 生成时注入 reference_image_id。
    """
    asset_id: str
    name: str                              # 角色名
    role_type: str = "配角"                # 主角/配角/反派/群众
    gender: str = ""                       # 男/女
    age_range: str = ""                    # 年龄段: 少年/青年/中年/老年
    appearance: str = ""                   # 外貌描述（AI prompt 用）
    clothing_style: str = ""               # 服装风格
    distinctive_features: List[str] = field(default_factory=list)  # 辨识特征（泪痣/伤疤/特殊发型）

    # 三视图
    reference_images: Dict[str, str] = field(default_factory=dict)
    # {"front": "url", "side": "url", "back": "url", "closeup": "url"}

    # 表情参考
    expression_images: Dict[str, str] = field(default_factory=dict)
    # {"neutral": "url", "angry": "url", "sad": "url", "happy": "url", "surprised": "url"}

    # Prompt 工程
    seedance_prompt_prefix: str = ""       # 注入到每个含此角色的 prompt 前
    negative_prompt: str = ""              # 负面提示词（避免的特征）

    # 元数据
    created_by: str = ""
    team_id: str = ""
    visibility: AssetVisibility = AssetVisibility.TEAM
    version: int = 1
    usage_count: int = 0                   # 引用计数 — 衡量资产价值
    avg_quality_score: float = 0.0         # 基于生成结果反馈的平均质量
    tags: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_prompt_context(self) -> str:
        """生成注入到 Seedance prompt 中的角色上下文。"""
        parts = [f"角色「{self.name}」: {self.appearance}"]
        if self.clothing_style:
            parts.append(f"服装: {self.clothing_style}")
        if self.distinctive_features:
            parts.append(f"特征: {', '.join(self.distinctive_features)}")
        if self.negative_prompt:
            parts.append(f"避免: {self.negative_prompt}")
        return "；".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "type": AssetType.CHARACTER.value,
            "name": self.name,
            "role_type": self.role_type,
            "gender": self.gender,
            "age_range": self.age_range,
            "appearance": self.appearance,
            "clothing_style": self.clothing_style,
            "distinctive_features": self.distinctive_features,
            "reference_images": self.reference_images,
            "expression_images": self.expression_images,
            "prompt_prefix": self.seedance_prompt_prefix,
            "usage_count": self.usage_count,
            "avg_quality_score": self.avg_quality_score,
            "tags": self.tags,
            "visibility": self.visibility.value,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class SceneTemplate:
    """场景模板 — 常见短剧拍摄场景 + 预设灯光/机位。

    短剧高频场景：宫廷大殿、王府书房、现代办公室、咖啡厅、医院走廊、天台、停车场...
    """
    template_id: str
    name: str                              # 模板名称
    category: str = ""                     # 古装/都市/悬疑/奇幻
    location_description: str = ""         # 场景描述（AI prompt 用）

    # 灯光预设
    lighting_setup: Dict[str, Any] = field(default_factory=dict)
    # {"style": "三点布光", "direction": "正面偏侧", "temperature": "暖色调3200K",
    #  "key_light": 0.8, "fill_light": 0.4, "rim_light": 0.3}

    # 机位预设
    camera_setups: List[Dict[str, Any]] = field(default_factory=list)
    # [{"name": "establishing", "type": "全景", "angle": "俯拍45°", "focal": "24mm", "movement": "缓慢推入"},
    #  {"name": "dialogue",    "type": "中景", "angle": "平视",    "focal": "50mm", "movement": "固定"},
    #  {"name": "closeup",     "type": "近景", "angle": "平视",    "focal": "85mm", "movement": "固定"}]

    # 参考图
    reference_images: List[str] = field(default_factory=list)

    # 元数据
    created_by: str = ""
    team_id: str = ""
    visibility: AssetVisibility = AssetVisibility.TEAM
    version: int = 1
    usage_count: int = 0
    tags: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_prompt_context(self) -> str:
        """生成注入到分镜 prompt 中的场景上下文。"""
        parts = [f"场景「{self.name}」: {self.location_description}"]
        if self.lighting_setup:
            lights = self.lighting_setup
            parts.append(
                f"灯光: {lights.get('style', '')} "
                f"方向={lights.get('direction', '')} "
                f"色温={lights.get('temperature', '')}"
            )
        return "；".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "type": AssetType.SCENE.value,
            "name": self.name,
            "category": self.category,
            "location_description": self.location_description,
            "lighting_setup": self.lighting_setup,
            "camera_setups": self.camera_setups,
            "reference_images": self.reference_images,
            "usage_count": self.usage_count,
            "tags": self.tags,
            "visibility": self.visibility.value,
            "version": self.version,
        }


@dataclass
class ShotPreset:
    """分镜预设 — 可复用的镜头构图方案。

    对标 LibTV 的"多机位九宫格"——每个预设是一个经过验证的镜头配置。
    爆款构图可沉淀、共享、复用。
    """
    preset_id: str
    name: str                              # 预设名称
    shot_type: str = "中景"                # 全景/中景/近景/特写/大特写
    camera_angle: str = "平视"             # 俯拍/仰拍/平视/鸟瞰/荷兰角
    camera_movement: str = "固定"          # 推/拉/摇/移/跟/升/降/固定
    focal_length: str = "50mm"             # 镜头焦段
    composition_rule: str = ""             # 构图法则: 三分法/对称/引导线/框架式
    depth_of_field: str = "中等景深"
    duration_range: str = "2-4s"           # 推荐时长范围
    description: str = ""                  # 使用场景说明

    # 参考效果
    reference_shots: List[str] = field(default_factory=list)  # 参考图 URL
    prompt_template: str = ""              # Seedance prompt 模板（含 {character} {scene} 占位符）

    # 元数据
    created_by: str = ""
    team_id: str = ""
    visibility: AssetVisibility = AssetVisibility.TEAM
    version: int = 1
    usage_count: int = 0
    avg_quality_score: float = 0.0
    tags: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_prompt_context(self) -> str:
        """生成注入到 Seedance prompt 的镜头上下文。"""
        parts = [
            f"镜头类型: {self.shot_type}",
            f"机位: {self.camera_angle}",
            f"运镜: {self.camera_movement}",
            f"焦段: {self.focal_length}",
        ]
        if self.composition_rule:
            parts.append(f"构图: {self.composition_rule}")
        if self.depth_of_field:
            parts.append(f"景深: {self.depth_of_field}")
        return "；".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "preset_id": self.preset_id,
            "type": AssetType.SHOT_PRESET.value,
            "name": self.name,
            "shot_type": self.shot_type,
            "camera_angle": self.camera_angle,
            "camera_movement": self.camera_movement,
            "focal_length": self.focal_length,
            "composition_rule": self.composition_rule,
            "depth_of_field": self.depth_of_field,
            "duration_range": self.duration_range,
            "description": self.description,
            "prompt_template": self.prompt_template,
            "usage_count": self.usage_count,
            "avg_quality_score": self.avg_quality_score,
            "tags": self.tags,
            "visibility": self.visibility.value,
            "version": self.version,
        }


# ═══════════════════════════════════════════════════════════════
# 资产库服务
# ═══════════════════════════════════════════════════════════════

class AssetLibrary:
    """资产库 — CRUD + 搜索 + 引用追踪 + 质量反馈闭环。

    生产环境中应使用 MySQL/PostgreSQL + Redis 持久化，
    当前为内存实现，接口与持久化版本一致。
    """

    def __init__(self, team_id: str = ""):
        self.team_id = team_id
        self._characters: Dict[str, CharacterAsset] = {}
        self._scenes: Dict[str, SceneTemplate] = {}
        self._shot_presets: Dict[str, ShotPreset] = {}
        # 反向索引：标签 → 资产ID
        self._tag_index: Dict[str, Set[str]] = {}

    # ═══════════════ 角色资产 ═══════════════

    def create_character(self, **kwargs) -> CharacterAsset:
        asset_id = _generate_id("char")
        now = _now_iso()
        char = CharacterAsset(
            asset_id=asset_id,
            created_at=now,
            updated_at=now,
            **kwargs,
        )
        self._characters[asset_id] = char
        self._index_tags(asset_id, char.tags)
        logger.info(f"Character asset created: {char.name} ({asset_id})")
        return char

    def get_character(self, asset_id: str) -> Optional[CharacterAsset]:
        return self._characters.get(asset_id)

    def list_characters(
        self,
        team_id: str = "",
        role_type: str = "",
        tags: Optional[List[str]] = None,
        sort_by: str = "usage_count",
        limit: int = 50,
    ) -> List[CharacterAsset]:
        results = list(self._characters.values())
        if team_id:
            results = [c for c in results if c.team_id == team_id]
        if role_type:
            results = [c for c in results if c.role_type == role_type]
        if tags:
            results = [c for c in results if set(tags) & set(c.tags)]
        results.sort(key=lambda c: getattr(c, sort_by, 0), reverse=True)
        return results[:limit]

    def update_character(self, asset_id: str, **kwargs) -> Optional[CharacterAsset]:
        char = self._characters.get(asset_id)
        if not char:
            return None
        for k, v in kwargs.items():
            if hasattr(char, k) and v is not None:
                setattr(char, k, v)
        char.version += 1
        char.updated_at = _now_iso()
        self._index_tags(asset_id, char.tags)
        return char

    def record_character_usage(self, asset_id: str, quality_score: float = 0.0):
        """记录角色资产被使用 + 反馈质量分。"""
        char = self._characters.get(asset_id)
        if char:
            char.usage_count += 1
            if quality_score > 0:
                # 指数移动平均: EMA(α=0.1)
                char.avg_quality_score = (
                    char.avg_quality_score * 0.9 + quality_score * 0.1
                )

    def search_characters(self, query: str, limit: int = 20) -> List[CharacterAsset]:
        q = query.lower()
        results = []
        for char in self._characters.values():
            score = 0
            if q in char.name.lower():
                score += 10
            if q in char.appearance.lower():
                score += 5
            if q in char.role_type.lower():
                score += 3
            if q in " ".join(char.tags).lower():
                score += 3
            if score > 0:
                results.append((score, char))
        results.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in results[:limit]]

    # ═══════════════ 场景模板 ═══════════════

    def create_scene(self, **kwargs) -> SceneTemplate:
        template_id = _generate_id("scene")
        now = _now_iso()
        scene = SceneTemplate(
            template_id=template_id,
            created_at=now,
            updated_at=now,
            **kwargs,
        )
        self._scenes[template_id] = scene
        self._index_tags(template_id, scene.tags)
        logger.info(f"Scene template created: {scene.name} ({template_id})")
        return scene

    def get_scene(self, template_id: str) -> Optional[SceneTemplate]:
        return self._scenes.get(template_id)

    def list_scenes(
        self, category: str = "", tags: Optional[List[str]] = None, limit: int = 50
    ) -> List[SceneTemplate]:
        results = list(self._scenes.values())
        if category:
            results = [s for s in results if s.category == category]
        if tags:
            results = [s for s in results if set(tags) & set(s.tags)]
        results.sort(key=lambda s: s.usage_count, reverse=True)
        return results[:limit]

    def get_scene_camera_setups(self, template_id: str) -> List[Dict[str, Any]]:
        scene = self._scenes.get(template_id)
        return scene.camera_setups if scene else []

    # ═══════════════ 分镜预设 ═══════════════

    def create_shot_preset(self, **kwargs) -> ShotPreset:
        preset_id = _generate_id("shot")
        now = _now_iso()
        preset = ShotPreset(
            preset_id=preset_id,
            created_at=now,
            updated_at=now,
            **kwargs,
        )
        self._shot_presets[preset_id] = preset
        self._index_tags(preset_id, preset.tags)
        logger.info(f"Shot preset created: {preset.name} ({preset_id})")
        return preset

    def get_shot_preset(self, preset_id: str) -> Optional[ShotPreset]:
        return self._shot_presets.get(preset_id)

    def list_shot_presets(
        self,
        shot_type: str = "",
        tags: Optional[List[str]] = None,
        limit: int = 50,
    ) -> List[ShotPreset]:
        results = list(self._shot_presets.values())
        if shot_type:
            results = [p for p in results if p.shot_type == shot_type]
        if tags:
            results = [p for p in results if set(tags) & set(p.tags)]
        results.sort(key=lambda p: p.usage_count, reverse=True)
        return results[:limit]

    def record_preset_usage(self, preset_id: str, quality_score: float = 0.0):
        preset = self._shot_presets.get(preset_id)
        if preset:
            preset.usage_count += 1
            if quality_score > 0:
                preset.avg_quality_score = (
                    preset.avg_quality_score * 0.9 + quality_score * 0.1
                )

    # ═══════════════ 标签索引 ═══════════════

    def _index_tags(self, asset_id: str, tags: List[str]):
        for tag in tags:
            tag_lower = tag.lower().strip()
            if tag_lower:
                if tag_lower not in self._tag_index:
                    self._tag_index[tag_lower] = set()
                self._tag_index[tag_lower].add(asset_id)

    def find_by_tag(self, tag: str) -> List[str]:
        """按标签查找资产 ID。"""
        return list(self._tag_index.get(tag.lower().strip(), set()))

    # ═══════════════ 批量导出（给 Seedance prompt builder 用） ═══════════════

    def build_episode_context(
        self,
        character_ids: List[str],
        scene_template_id: str = "",
        shot_preset_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """构建单集的完整资产上下文。

        在生成分镜/视频前调用，将资产信息注入 prompt。

        Returns:
            {
                "character_contexts": [...],
                "scene_context": "...",
                "shot_presets": [...],
                "combined_prompt_prefix": "..."  # 可直接拼接在 Seedance prompt 前
            }
        """
        result: Dict[str, Any] = {
            "character_contexts": [],
            "scene_context": "",
            "shot_presets": [],
            "combined_prompt_prefix": "",
        }

        # Gather character contexts
        prefix_parts = []
        for cid in character_ids:
            char = self._characters.get(cid)
            if char:
                ctx = char.to_prompt_context()
                result["character_contexts"].append(ctx)
                if char.seedance_prompt_prefix:
                    prefix_parts.append(char.seedance_prompt_prefix)
                # Record usage
                char.usage_count += 1

        # Gather scene context
        if scene_template_id:
            scene = self._scenes.get(scene_template_id)
            if scene:
                result["scene_context"] = scene.to_prompt_context()
                scene.usage_count += 1

        # Gather shot presets
        for pid in (shot_preset_ids or []):
            preset = self._shot_presets.get(pid)
            if preset:
                result["shot_presets"].append(preset.to_prompt_context())
                preset.usage_count += 1

        result["combined_prompt_prefix"] = " | ".join(prefix_parts) if prefix_parts else ""
        return result

    # ═══════════════ 预置资产（开箱即用的短剧常见库） ═══════════════

    @classmethod
    def with_presets(cls, team_id: str = "") -> "AssetLibrary":
        """创建预置了常见短剧资产的库。"""
        lib = cls(team_id=team_id)

        # 预置高频场景模板
        _preset_scenes = [
            ("宫廷大殿", "古装", "金碧辉煌的古代宫殿，金色龙柱，红色帷幔，玉石地面反光",
             {"style": "三点布光", "direction": "顶光+侧光", "temperature": "暖色调3200K"}),
            ("王府书房", "古装", "古色古香的书房，紫檀书架，青花瓷，宣纸铺案，烛光摇曳",
             {"style": "低调光", "direction": "侧光", "temperature": "暖色调2800K"}),
            ("现代办公室", "都市", "开放式办公区，落地窗，白色极简风格，绿植点缀，自然光",
             {"style": "自然光+补光", "direction": "窗光为主", "temperature": "日光5600K"}),
            ("咖啡厅靠窗位", "都市", "文艺风格咖啡厅，靠窗双人座，暖黄灯光，木纹桌面",
             {"style": "柔光", "direction": "窗光+顶灯", "temperature": "暖色调3500K"}),
            ("医院走廊", "悬疑", "惨白的医院走廊，日光灯频闪，消毒水气味感，墙角有阴影",
             {"style": "顶光为主", "direction": "顶光", "temperature": "冷色调4500K"}),
            ("天台夜景", "都市", "高楼天台，城市夜景灯光背景，栏杆边，夜风吹动衣角",
             {"style": "低调光", "direction": "背光+城市光", "temperature": "冷色调5000K"}),
            ("竹林小径", "古装/奇幻", "幽深竹林，雾气弥漫，阳光透过竹叶形成光柱",
             {"style": "自然光+雾", "direction": "逆光", "temperature": "冷色调6000K"}),
            ("停车场", "悬疑/都市", "地下停车场，水泥柱，荧光灯嗡嗡作响，阴影角落",
             {"style": "顶荧光灯", "direction": "顶光", "temperature": "冷色调4000K"}),
        ]
        for name, cat, desc, lights in _preset_scenes:
            lib.create_scene(
                name=name, category=cat, location_description=desc, lighting_setup=lights,
                visibility=AssetVisibility.PUBLIC,
            )

        # 预置分镜预设
        _preset_shots = [
            ("开场定场", "全景", "俯拍45°", "缓慢推入", "24mm", "三分法",
             "场景全貌建立空间感 + 缓慢推入营造进入感"),
            ("双人对白标准", "中景", "平视", "固定", "50mm", "三分法",
             "两人对话标准机位，注意视线高度一致"),
            ("单人情绪特写", "近景", "平视", "缓慢推进", "85mm", "中心构图",
             "面部微表情捕捉，浅景深虚化背景"),
            ("悬念揭示", "特写", "俯拍", "固定→快速拉远", "50mm", "中心构图",
             "关键物品或线索的揭示镜头"),
            ("动作跟随", "中景", "平视", "跟拍", "35mm", "引导线",
             "角色行走或动作的跟随镜头，保持角色在画面中"),
            ("对话过肩", "中景", "平视", "固定", "50mm", "框架式",
             "过肩镜头增强对话沉浸感"),
            ("大场面建立", "全景", "鸟瞰", "缓慢下降+推入", "16mm", "三分法",
             "大型场景的全景展示，从高处缓慢下降"),
            ("快速转场", "中景", "荷兰角", "快速摇摄", "35mm", "",
             "紧张情绪或时空转换，倾斜构图+快速运动"),
        ]
        for name, shot_type, angle, movement, focal, composition, desc in _preset_shots:
            lib.create_shot_preset(
                name=name, shot_type=shot_type, camera_angle=angle,
                camera_movement=movement, focal_length=focal,
                composition_rule=composition, description=desc,
                visibility=AssetVisibility.PUBLIC,
            )

        logger.info(f"AssetLibrary initialized with presets: "
                    f"{len(lib._scenes)} scenes, {len(lib._shot_presets)} shot presets")
        return lib


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _generate_id(prefix: str) -> str:
    return f"{prefix}_{int(time.time()*1000)}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:6]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
