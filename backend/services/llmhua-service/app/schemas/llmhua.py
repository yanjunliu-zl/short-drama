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


# ==================== 分镜头批量视频生成模型 ====================

class ShotRequest(BaseModel):
    """单个分镜头请求（用于视频生成）"""
    id: int = Field(..., description="镜头唯一ID")
    number: int = Field(..., description="镜头编号")
    shotType: str = Field(..., description="镜头类型：远景/全景/中景/近景/特写")
    duration: int = Field(default=5, description="时长(秒)")
    cameraAngle: str = Field(default="正面平视", description="摄像机角度")
    sceneRef: str = Field(default="", description="关联场景")
    characters: List[str] = Field(default=[], description="出场角色")
    description: str = Field(..., description="画面描述")
    dialogue: str = Field(default="", description="对白/旁白")
    soundEffects: List[str] = Field(default=[], description="音效")
    music: str = Field(default="", description="背景音乐")
    notes: str = Field(default="", description="备注")


class ShotEpisodeRequest(BaseModel):
    """一集的分镜请求"""
    id: str = Field(..., description="集ID")
    title: str = Field(..., description="集标题")
    number: int = Field(..., description="集编号")
    shots: List[ShotRequest] = Field(default=[], description="该集的分镜头")
    description: Optional[str] = Field(default=None, description="集描述")


class ReferenceImagesInput(BaseModel):
    """参考图像：name → image_url 映射，用于保持角色/场景视觉一致性"""
    characters: Dict[str, str] = Field(default={}, description="角色名→图像URL")
    scenes: Dict[str, str] = Field(default={}, description="场景名→图像URL")
    props: Dict[str, str] = Field(default={}, description="道具名→图像URL")


class ShotsToVideoRequest(BaseModel):
    """批量分镜头生成视频请求"""
    storyboard_id: Optional[str] = Field(default=None, description="分镜ID")
    episodes: List[ShotEpisodeRequest] = Field(..., description="分集镜头数据")
    referenceImages: Optional[ReferenceImagesInput] = Field(default=None, description="参考图像（角色/场景/道具预览图，用于保持一致性）")
    style: Optional[str] = Field(default="写实风格", description="整体风格")
    width: Optional[int] = Field(default=1920, description="视频宽度")
    height: Optional[int] = Field(default=1920, description="视频高度")
    fps: Optional[int] = Field(default=24, description="帧率")
    user_id: Optional[str] = Field(default=None, description="用户ID")


class ShotVideoResult(BaseModel):
    """单个镜头的视频生成结果"""
    shot_id: int = Field(..., description="镜头ID")
    shot_number: int = Field(..., description="镜头编号")
    episode_id: str = Field(..., description="所属集ID")
    episode_title: str = Field(default="", description="所属集标题")
    status: str = Field(..., description="状态: completed/failed")
    video_url: Optional[str] = Field(default=None, description="生成的视频URL")
    image_url: Optional[str] = Field(default=None, description="中间生成的图像URL")
    file_size: Optional[int] = Field(default=None, description="文件大小(bytes)")
    error: Optional[str] = Field(default=None, description="错误信息")


class ShotsToVideoResponse(BaseModel):
    """批量分镜头视频生成响应"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="状态")
    message: str = Field(..., description="消息")
    total_shots: int = Field(default=0, description="总镜头数")
    completed_shots: int = Field(default=0, description="已完成镜头数")
    results: List[ShotVideoResult] = Field(default=[], description="各镜头结果")


# ==================== 预览图像生成模型 ====================

class PreviewImageRequest(BaseModel):
    """场景/角色/道具预览图像生成请求"""
    description: str = Field(..., description="图像描述（场景环境、角色外貌或道具外观）")
    category: str = Field(default="scene", description="类型: scene/character/prop")
    style: Optional[str] = Field(default="写实风格", description="图像风格")
    width: Optional[int] = Field(default=1920, description="图像宽度")
    height: Optional[int] = Field(default=1920, description="图像高度")


class PreviewImageResponse(BaseModel):
    """预览图像生成响应"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(default="processing", description="状态")
    image_url: Optional[str] = Field(default=None, description="生成的图像URL")
    message: str = Field(default="", description="消息")
