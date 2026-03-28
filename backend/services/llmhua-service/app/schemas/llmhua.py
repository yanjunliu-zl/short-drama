from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ==================== 请求模型 ====================

class StoryboardToImageRequest(BaseModel):
    """分镜镜头转图像请求"""
    scene_description: str = Field(..., description="镜头描述")
    storyboard_id: str = Field(..., description="分镜ID")
    scene_number: int = Field(..., description="场景编号")
    style: Optional[str] = Field(default="写实风格", description="图像风格")
    seed: Optional[int] = Field(default=None, description="随机种子")
    width: Optional[int] = Field(default=None, description="图像宽度")
    height: Optional[int] = Field(default=None, description="图像高度")
    user_id: Optional[str] = Field(default=None, description="用户ID")


class ImageToVideoRequest(BaseModel):
    """图像转视频请求"""
    image_url: str = Field(..., description="图像URL")
    prompt: Optional[str] = Field(default=None, description="视频生成提示词")
    duration: Optional[float] = Field(default=5.0, description="视频时长（秒）")
    fps: Optional[int] = Field(default=24, description="帧率")
    seed: Optional[int] = Field(default=None, description="随机种子")
    strength: Optional[float] = Field(default=None, description="图像强度")
    user_id: Optional[str] = Field(default=None, description="用户ID")


class StoryboardGenerationRequest(BaseModel):
    """完整的分镜生成并转换为视频的请求"""
    storyboard_id: str = Field(..., description="分镜ID")
    scenes: List[Dict[str, Any]] = Field(..., description="分镜场景列表")
    style: Optional[str] = Field(default="写实风格", description="整体风格")
    generate_video: Optional[bool] = Field(default=True, description="是否生成视频")
    user_id: Optional[str] = Field(default=None, description="用户ID")


# ==================== 响应模型 ====================

class LlmhuaResponse(BaseModel):
    """通用响应"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="状态")
    message: str = Field(..., description="消息")


class ImageGenerationResponse(BaseModel):
    """图像生成响应"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="状态")
    image_url: Optional[str] = Field(default=None, description="生成的图像URL")
    seed: Optional[int] = Field(default=None, description="使用的随机种子")
    message: str = Field(..., description="消息")


class VideoGenerationResponse(BaseModel):
    """视频生成响应"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="状态")
    video_url: Optional[str] = Field(default=None, description="生成的视频URL")
    message: str = Field(..., description="消息")


class SceneResult(BaseModel):
    """场景处理结果"""
    scene_number: int = Field(..., description="场景编号")
    image_url: Optional[str] = Field(default=None, description="图像URL")
    video_url: Optional[str] = Field(default=None, description="视频URL")
    status: str = Field(..., description="状态")
    error: Optional[str] = Field(default=None, description="错误信息")


class CompleteResult(BaseModel):
    """完整任务结果"""
    storyboard_id: str = Field(..., description="分镜ID")
    total_scenes: int = Field(..., description="总场景数")
    successful_scenes: int = Field(..., description="成功场景数")
    results: List[SceneResult] = Field(default=[], description="场景结果列表")


# ==================== 状态查询模型 ====================

class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态")
    progress: Optional[int] = Field(default=None, description="进度")
    result: Optional[Dict[str, Any]] = Field(default=None, description="结果数据")
    error: Optional[str] = Field(default=None, description="错误信息")
    created_at: Optional[str] = Field(default=None, description="创建时间")
    completed_at: Optional[str] = Field(default=None, description="完成时间")
