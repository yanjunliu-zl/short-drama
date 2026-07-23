"""
Agent Skill 接口 — 将短剧制作管线暴露为 AI Agent 可调用的技能。

对标 LibTV 的"Agent 原生"原则：
- 每个能力封装为独立 Skill（函数 + JSON Schema 描述）
- Agent 可以按需调用、组合、编排
- 支持多 Agent 协作（一个 Agent 负责剧本、一个负责分镜、一个负责视频）

设计:
    SkillRegistry → 注册/发现/调用 Skill
    Skill 定义 = name + description + parameters_schema + handler_function

用法:
    # 在任何 agent / LLM function-calling 场景
    from app.services.agent_skills import SkillRegistry

    registry = SkillRegistry()
    registry.register_from_module()  # 自动注册所有 @skill 装饰的函数

    # Agent 可调用：
    result = await registry.call("generate_storyboard", {
        "script_content": "...",
        "style": "古装",
        "character_ids": ["char_001", "char_002"],
        "scene_template_id": "scene_palace_hall",
    })
"""
import logging
import json
import inspect
from typing import Dict, Any, Optional, List, Callable, Awaitable, get_type_hints
from dataclasses import dataclass, field
from functools import wraps

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Skill Definition
# ═══════════════════════════════════════════════════════════════

@dataclass
class SkillDef:
    """技能定义 — 兼容 OpenAI function-calling / Anthropic tool-use 格式。"""
    name: str                              # 技能名 (unique)
    description: str                       # 自然语言描述（Agent 据此决策是否调用）
    parameters: Dict[str, Any]             # JSON Schema for parameters
    handler: Callable[..., Awaitable[Any]] # async 处理函数
    category: str = "general"              # 分类: script | storyboard | asset | video | pipeline
    requires_approval: bool = False        # 是否需要人工审批
    tags: List[str] = field(default_factory=list)

    def to_openai_tool(self) -> Dict[str, Any]:
        """导出为 OpenAI function-calling 格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_anthropic_tool(self) -> Dict[str, Any]:
        """导出为 Anthropic tool-use 格式。"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }


# ═══════════════════════════════════════════════════════════════
# Skill Registry
# ═══════════════════════════════════════════════════════════════

class SkillRegistry:
    """技能注册中心 — 全局单例。

    用法:
        registry = SkillRegistry()

        @registry.register(
            name="generate_storyboard",
            description="根据剧本生成分镜...",
            parameters={...},
            category="storyboard",
        )
        async def generate_storyboard(...): ...

        # Agent 调用
        result = await registry.call("generate_storyboard", {"script_content": "..."})

        # 获取所有可用工具（给 LLM function-calling）
        tools = registry.get_openai_tools()
    """

    def __init__(self):
        self._skills: Dict[str, SkillDef] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        category: str = "general",
        requires_approval: bool = False,
        tags: Optional[List[str]] = None,
    ):
        """装饰器：注册一个 Skill。"""
        def decorator(func):
            @wraps(func)
            async def wrapper(**kwargs):
                return await func(**kwargs)

            skill = SkillDef(
                name=name,
                description=description,
                parameters=parameters,
                handler=func,
                category=category,
                requires_approval=requires_approval,
                tags=tags or [],
            )
            self._skills[name] = skill
            logger.info(f"Skill registered: {name} (category={category})")
            return wrapper
        return decorator

    def register_direct(self, skill: SkillDef):
        """直接注册 Skill 对象。"""
        self._skills[skill.name] = skill
        logger.info(f"Skill registered (direct): {skill.name}")

    async def call(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Agent 调用技能。

        Args:
            name: 技能名。
            arguments: 参数（key-value）。

        Returns:
            {"success": True/False, "data": ..., "error": "..."}

        Raises:
            ValueError: 技能不存在。
        """
        skill = self._skills.get(name)
        if not skill:
            return {"success": False, "error": f"Skill not found: {name}"}

        try:
            result = await skill.handler(**arguments)
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"Skill '{name}' failed: {e}")
            return {"success": False, "error": str(e)}

    def get_skill(self, name: str) -> Optional[SkillDef]:
        return self._skills.get(name)

    def list_skills(self, category: str = "") -> List[SkillDef]:
        skills = list(self._skills.values())
        if category:
            skills = [s for s in skills if s.category == category]
        return skills

    def get_openai_tools(self, categories: Optional[List[str]] = None) -> List[Dict]:
        """导出为 OpenAI function-calling tools 列表。"""
        skills = list(self._skills.values())
        if categories:
            skills = [s for s in skills if s.category in categories]
        return [s.to_openai_tool() for s in skills]

    def get_anthropic_tools(self, categories: Optional[List[str]] = None) -> List[Dict]:
        """导出为 Anthropic tool-use tools 列表。"""
        skills = list(self._skills.values())
        if categories:
            skills = [s for s in skills if s.category in categories]
        return [s.to_anthropic_tool() for s in skills]


# ═══════════════════════════════════════════════════════════════
# 全局注册表
# ═══════════════════════════════════════════════════════════════

_pipeline_skill_registry = SkillRegistry()


def get_skill_registry() -> SkillRegistry:
    return _pipeline_skill_registry


# ═══════════════════════════════════════════════════════════════
# 预置 Skill 定义（JSON Schema + 描述，不含实现）
# ═══════════════════════════════════════════════════════════════
# 实现通过 register_direct() 注入，实现接口与实现分离。

# ── Asset Skills ──

SKILL_CREATE_CHARACTER = SkillDef(
    name="create_character_asset",
    description="创建一个角色视觉资产（对标 LibTV 角色三视图），"
                "包含外貌描述、服装风格、辨识特征。后续分镜/视频生成会引用此资产以保证角色一致性。",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "角色名"},
            "role_type": {"type": "string", "enum": ["主角", "配角", "反派", "群众"], "description": "角色定位"},
            "gender": {"type": "string", "enum": ["男", "女"], "description": "性别"},
            "age_range": {"type": "string", "description": "年龄段: 少年/青年/中年/老年"},
            "appearance": {"type": "string", "description": "外貌描述（越详细越好，用于AI生成参考图）"},
            "clothing_style": {"type": "string", "description": "服装风格，如'白色长袍、腰间玉带'"},
            "distinctive_features": {"type": "array", "items": {"type": "string"}, "description": "辨识特征，如['左眼角泪痣', '银色长发']"},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "标签，如['古装', '仙侠', '高冷']"},
        },
        "required": ["name", "appearance"],
    },
    category="asset",
    handler=None,
)


SKILL_LIST_CHARACTERS = SkillDef(
    name="list_character_assets",
    description="列出已有的角色资产库。可按角色类型、标签筛选。用于决定是复用已有角色还是创建新角色。",
    parameters={
        "type": "object",
        "properties": {
            "role_type": {"type": "string", "description": "筛选角色类型"},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "按标签筛选"},
            "limit": {"type": "integer", "default": 20, "description": "返回数量上限"},
        },
    },
    category="asset",
    handler=None,
)


SKILL_CREATE_SCENE_TEMPLATE = SkillDef(
    name="create_scene_template",
    description="创建一个场景模板，包含地点描述、灯光预设、推荐机位。可在后续分镜生成时直接引用。",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "场景模板名称，如'咖啡厅靠窗位'"},
            "category": {"type": "string", "description": "分类: 古装/都市/悬疑/奇幻"},
            "location_description": {"type": "string", "description": "场景描述（AI prompt用）"},
            "lighting_style": {"type": "string", "description": "灯光风格"},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["name", "category", "location_description"],
    },
    category="asset",
    handler=None,
)


SKILL_CREATE_SHOT_PRESET = SkillDef(
    name="create_shot_preset",
    description="创建一个分镜预设——可复用的镜头构图方案。对标 LibTV 的多机位九宫格。",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "预设名称，如'双人对白标准'"},
            "shot_type": {"type": "string", "enum": ["全景", "中景", "近景", "特写", "大特写"], "description": "镜头类型"},
            "camera_angle": {"type": "string", "description": "机位角度"},
            "camera_movement": {"type": "string", "description": "运镜方式"},
            "focal_length": {"type": "string", "description": "焦段"},
            "composition_rule": {"type": "string", "description": "构图法则"},
            "description": {"type": "string", "description": "使用场景说明"},
        },
        "required": ["name", "shot_type"],
    },
    category="asset",
    handler=None,
)


# ── Storyboard Skills ──

SKILL_GENERATE_STORYBOARD = SkillDef(
    name="generate_storyboard",
    description="根据剧本生成分镜。支持指定角色资产ID（保证角色一致性）、"
                "场景模板ID（复用灯光/机位预设）、分镜预设ID（指定镜头风格）。"
                "对标 LibTV 的脚本工作流。",
    parameters={
        "type": "object",
        "properties": {
            "script_content": {"type": "string", "description": "完整剧本内容"},
            "title": {"type": "string", "description": "剧本标题"},
            "style": {"type": "string", "description": "视觉风格: 古装/写实/悬疑/赛博朋克等"},
            "character_ids": {"type": "array", "items": {"type": "string"}, "description": "要引用的角色资产ID列表"},
            "scene_template_id": {"type": "string", "description": "场景模板ID"},
            "shot_preset_ids": {"type": "array", "items": {"type": "string"}, "description": "分镜预设ID列表"},
            "episode_contents": {"type": "array", "items": {"type": "string"}, "description": "已分集的剧本内容（可选）"},
        },
        "required": ["script_content"],
    },
    category="storyboard",
    handler=None,
)


# ── Pipeline Skills ──

SKILL_RUN_PIPELINE = SkillDef(
    name="run_pipeline",
    description="执行从剧本到视频的完整管线。自动完成：实体提取→分镜生成→质量审核→图像生成→视频生成。"
                "支持在任意阶段暂停等待审批。",
    parameters={
        "type": "object",
        "properties": {
            "script_content": {"type": "string", "description": "剧本内容"},
            "title": {"type": "string", "description": "剧本标题"},
            "style": {"type": "string", "description": "视觉风格"},
            "start_from": {"type": "string", "enum": ["script", "extract", "storyboard", "images", "videos"], "description": "从哪个阶段开始"},
            "stop_at": {"type": "string", "enum": ["storyboard", "images", "videos"], "description": "到哪个阶段停止"},
            "auto_approve": {"type": "boolean", "default": True, "description": "是否自动通过审核门（false=每阶段等待人工审批）"},
            "character_ids": {"type": "array", "items": {"type": "string"}, "description": "角色资产ID列表"},
        },
        "required": ["script_content"],
    },
    category="pipeline",
    handler=None,
    requires_approval=False,
)


SKILL_QUALITY_CHECK = SkillDef(
    name="quality_check",
    description="对剧本或分镜进行 7 维质量评估，返回评分和修改建议。"
                "维度：连贯性、角色一致性、对白自然度、短视频适配度、钩子质量、类型准确度、合规性。",
    parameters={
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "要评估的剧本/分镜内容"},
            "title": {"type": "string", "description": "剧本标题"},
            "style": {"type": "string", "description": "剧本风格"},
            "platform": {"type": "string", "enum": ["xiaoyunque", "libtv", "jurilu", "internal"], "description": "目标平台"},
        },
        "required": ["content"],
    },
    category="pipeline",
    handler=None,
)


SKILL_EXPORT_SCRIPT = SkillDef(
    name="export_script",
    description="将剧本导出为下游AI成片工具兼容格式（小云雀/LibTV/巨日禄）。",
    parameters={
        "type": "object",
        "properties": {
            "script_content": {"type": "string", "description": "剧本内容"},
            "title": {"type": "string", "description": "剧本标题"},
            "target": {"type": "string", "enum": ["xiaoyunque", "libtv", "jurilu", "all"], "description": "目标平台"},
            "format": {"type": "string", "enum": ["auto", "raw_text", "structured_json", "storyboard_json"], "default": "auto"},
        },
        "required": ["script_content"],
    },
    category="pipeline",
    handler=None,
)


# ── Export ──

ALL_PREDEFINED_SKILLS: List[SkillDef] = [
    SKILL_CREATE_CHARACTER,
    SKILL_LIST_CHARACTERS,
    SKILL_CREATE_SCENE_TEMPLATE,
    SKILL_CREATE_SHOT_PRESET,
    SKILL_GENERATE_STORYBOARD,
    SKILL_RUN_PIPELINE,
    SKILL_QUALITY_CHECK,
    SKILL_EXPORT_SCRIPT,
]
