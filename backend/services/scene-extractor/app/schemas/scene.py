from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime


# 请求模型
class SceneExtractionRequest(BaseModel):
    """场景抽取请求"""
    script_content: str = Field(..., description="剧本内容")
    extract_type: Optional[str] = Field(default="all", description="抽取类型: all, scenes, characters, props")
    style: Optional[str] = Field(default="写实风格", description="图像生成风格")


class SceneRequest(BaseModel):
    """单个场景抽取请求"""
    script_content: str = Field(..., description="剧本内容")
    scene_id: Optional[int] = Field(default=None, description="场景ID（可选，指定抽取特定场景）")


class CharacterRequest(BaseModel):
    """角色抽取请求"""
    script_content: str = Field(..., description="剧本内容")


class PropRequest(BaseModel):
    """道具抽取请求"""
    script_content: str = Field(..., description="剧本内容")


# 响应模型
class SceneResponse(BaseModel):
    """场景信息"""
    scene_id: int
    location: str
    time_of_day: str
    description: str
    characters: List[str]
    props: List[str]
    action_summary: str
    image_url: Optional[str] = None


class CharacterResponse(BaseModel):
    """角色信息"""
    character_id: int
    name: str
    description: str
    age: Optional[int]
    personality: str
    clothing: str
    role: str


class PropResponse(BaseModel):
    """道具信息"""
    prop_id: int
    name: str
    description: str
    category: str
    usage: str
    scenes: List[int]


class ExtractionResponse(BaseModel):
    """抽取结果响应"""
    script_id: Optional[str] = None
    scenes: List[SceneResponse]
    characters: List[CharacterResponse]
    props: List[PropResponse]
    extracted_at: datetime
    metadata: Optional[Dict[str, Any]] = None


class ExtractionStatusResponse(BaseModel):
    """抽取状态响应"""
    task_id: str
    status: str  # pending, processing, completed, failed
    progress: int
    result: Optional[ExtractionResponse] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
