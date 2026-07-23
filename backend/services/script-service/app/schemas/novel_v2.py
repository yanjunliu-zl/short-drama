"""V2 小说转剧本结构化输出模型 — RAG + 分镜 + 角色关系图谱"""

from pydantic import BaseModel, Field
from typing import List, Optional


class StoryboardShot(BaseModel):
    """单个分镜镜头"""
    shot_number: int = Field(..., description="镜号")
    camera_type: str = Field(..., description="镜头类型：全景/中景/近景/特写")
    camera_movement: str = Field(..., description="运镜方式：推/拉/摇/移/固定")
    duration_seconds: float = Field(default=5.0, description="镜头时长（秒）")
    description: str = Field(..., description="画面内容描述")


class ChapterScriptV2(BaseModel):
    """单章剧本（含分镜表）"""
    chapter_title: str = Field(..., description="章节标题")
    scene_number: str = Field(..., description="场景编号，如 SCENE-001")
    scene_type: str = Field(..., description="场景类型：外景/内景 + 白天/黑夜")
    location: str = Field(..., description="场景地点")
    characters: List[str] = Field(default_factory=list, description="出场角色列表")
    props: List[str] = Field(default_factory=list, description="核心道具列表")
    storyboard: List[StoryboardShot] = Field(default_factory=list, description="分镜明细表")
    script_body: str = Field(..., description="标准化剧本正文（含动作旁白和台词）")


class GenerateChapterScriptResponse(BaseModel):
    """单章剧本生成 LLM 结构化输出"""
    scene_number: str = Field(..., description="场景编号")
    scene_type: str = Field(..., description="场景类型")
    location: str = Field(..., description="场景地点")
    characters: List[str] = Field(default_factory=list, description="出场角色")
    props: List[str] = Field(default_factory=list, description="核心道具")
    storyboard: List[StoryboardShot] = Field(default_factory=list, description="分镜明细表")
    script_body: str = Field(..., description="标准化剧本正文")


class CharacterRelation(BaseModel):
    """角色关系"""
    source: str = Field(..., description="角色A")
    target: str = Field(..., description="角色B")
    relation_type: str = Field(..., description="关系类型：师徒/父子/恋人/仇敌/朋友/同门/君臣 等")
    description: str = Field(default="", description="关系简述")


class GlobalCharacter(BaseModel):
    """全局角色"""
    name: str = Field(..., description="角色名")
    personality: str = Field(default="", description="性格特征")
    role: str = Field(default="配角", description="主角/配角/反派")


class GlobalScene(BaseModel):
    """全局场景"""
    name: str = Field(..., description="场景名称")
    description: str = Field(default="", description="场景描述")
    category: str = Field(default="", description="场景类别：宫廷/市井/战场/山林 等")


class GlobalProp(BaseModel):
    """全局道具"""
    name: str = Field(..., description="道具名称")
    description: str = Field(default="", description="道具描述")
    significance: str = Field(default="", description="道具在剧情中的意义")


class GlobalInfoResponse(BaseModel):
    """全局信息提取 LLM 结构化输出"""
    characters: List[GlobalCharacter] = Field(default_factory=list, description="全部角色")
    relationships: List[CharacterRelation] = Field(default_factory=list, description="角色关系图谱")
    key_scenes: List[GlobalScene] = Field(default_factory=list, description="核心场景汇总")
    key_props: List[GlobalProp] = Field(default_factory=list, description="高频核心道具汇总")


# ── Entity Extraction (shared across V2 pipeline and standalone API) ──

class ExtractedEntity(BaseModel):
    """通用实体"""
    name: str = Field(..., description="实体名称")
    description: str = Field(default="", description="简要描述")


class ExtractedCharacterEntity(BaseModel):
    """提取的角色实体"""
    name: str = Field(..., description="角色名")
    role: str = Field(default="配角", description="角色：主角/配角/反派/群众")
    gender: str = Field(default="", description="性别：男/女")
    description: str = Field(default="", description="视觉描述")


class ExtractEntitiesResponse(BaseModel):
    """实体提取 LLM 结构化输出"""
    characters: List[ExtractedCharacterEntity] = Field(default_factory=list)
    locations: List[ExtractedEntity] = Field(default_factory=list)
    props: List[ExtractedEntity] = Field(default_factory=list)
