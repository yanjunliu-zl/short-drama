from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class StoryboardScene(BaseModel):
    """分镜场景"""
    scene_number: int = Field(..., description="场景编号")
    description: str = Field(..., description="场景描述")
    characters: List[str] = Field(default=[], description="场景中的角色")
    dialogue: List[str] = Field(default=[], description="角色对话")
    camera_directions: List[str] = Field(default=[], description="镜头指示")
    setting: Optional[str] = Field(default=None, description="场景设定")
    emotions: Optional[List[str]] = Field(default=[], description="角色情绪")
    visual_elements: Optional[List[str]] = Field(default=[], description="视觉元素")


class StoryboardGenerationRequest(BaseModel):
    """分镜生成请求"""
    title: str = Field(..., description="剧本标题")
    script: str = Field(..., description="剧本内容")
    theme: str = Field(..., description="主题")
    style: Optional[str] = Field(default="写实风格", description="分镜风格")
    scene_count: Optional[int] = Field(default=0, description="预期场景数量，0表示自动")
    user_id: Optional[str] = Field(default=None, description="用户ID")


class StoryboardResponse(BaseModel):
    """分镜响应"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="状态: processing, completed, failed")
    message: str = Field(..., description="消息")
    storyboard: Optional[Dict[str, Any]] = Field(default=None, description="分镜数据")


class StoryboardListResponse(BaseModel):
    """分镜列表响应"""
    storyboards: List[Dict[str, Any]] = Field(..., description="分镜列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
