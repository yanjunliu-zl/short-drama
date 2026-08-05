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
    stream: bool = Field(default=False, description="是否启用SSE流式输出")


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


# ========== 镜头级分镜 (Shot-level) Schemas ==========

class Shot(BaseModel):
    """分镜头（扩展自 moyin-creator 的电影摄影字段）"""
    id: int = Field(..., description="镜头唯一ID")
    number: int = Field(..., description="镜头编号")
    shotType: str = Field(..., description="镜头类型：远景/全景/中景/近景/特写/大特写/过肩镜头")
    duration: int = Field(default=5, description="时长(秒)")
    cameraAngle: str = Field(default="正面平视", description="摄像机角度")
    sceneRef: str = Field(default="", description="关联的场景")
    characters: List[str] = Field(default=[], description="出场的角色")
    description: str = Field(..., description="画面描述")
    dialogue: str = Field(default="", description="对白/旁白")
    soundEffects: List[str] = Field(default=[], description="音效")
    music: str = Field(default="", description="背景音乐")
    notes: str = Field(default="", description="备注")

    # ═══ 三层提示词（moyin-creator 核心） ═══
    imagePrompt: Optional[str] = Field(default=None, description="首帧静态图像提示词")
    imagePromptZh: Optional[str] = Field(default=None, description="首帧中文提示词")
    videoPrompt: Optional[str] = Field(default=None, description="视频动作提示词")
    videoPromptZh: Optional[str] = Field(default=None, description="视频中文提示词")
    endFramePrompt: Optional[str] = Field(default=None, description="尾帧提示词（仅 needsEndFrame=true 时）")
    endFramePromptZh: Optional[str] = Field(default=None, description="尾帧中文提示词")
    needsEndFrame: bool = Field(default=False, description="是否需要尾帧")

    # ═══ 灯光与布光 (Gaffer) ═══
    lightingStyle: Optional[str] = Field(default=None, description="灯光风格")
    lightingDirection: Optional[str] = Field(default=None, description="灯光方向")
    colorTemperature: Optional[str] = Field(default=None, description="色温")
    lightingNotes: Optional[str] = Field(default=None, description="灯光备注")

    # ═══ 焦点 (Focus Puller) ═══
    depthOfField: Optional[str] = Field(default=None, description="景深")
    focusTarget: Optional[str] = Field(default=None, description="焦点主体")
    focusTransition: Optional[str] = Field(default=None, description="焦点转移")

    # ═══ 拍摄设备 (Camera Rig) ═══
    cameraRig: Optional[str] = Field(default=None, description="拍摄设备（三脚架/手持/滑轨/摇臂等）")
    movementSpeed: Optional[str] = Field(default=None, description="运动速度")
    cameraMovement: Optional[str] = Field(default=None, description="摄像机运动描述")
    focalLength: Optional[str] = Field(default=None, description="焦距")
    photographyTechnique: Optional[str] = Field(default=None, description="拍摄技法")

    # ═══ 情绪与叙事 ═══
    emotionTags: List[str] = Field(default=[], description="情绪标签")
    narrativeFunction: Optional[str] = Field(default=None, description="叙事功能")

    # ═══ 氛围特效 (SFX) ═══
    atmosphericEffects: Optional[str] = Field(default=None, description="氛围特效（雾/雨/粒子等）")
    effectIntensity: Optional[str] = Field(default=None, description="特效强度")

    # ═══ 连续性 ═══
    continuityRef: Optional[str] = Field(default=None, description="连续性参考（角色位置/服装/道具）")
    playbackSpeed: Optional[str] = Field(default=None, description="播放速度")


class ShotEpisode(BaseModel):
    """一集的分镜"""
    id: str = Field(..., description="集ID")
    title: str = Field(..., description="集标题")
    number: int = Field(..., description="集编号")
    shots: List[Shot] = Field(default=[], description="该集的分镜头")
    description: Optional[str] = Field(default=None, description="集描述")


class ShotGenerationRequest(BaseModel):
    """分镜(镜头级)生成请求"""
    title: str = Field(..., description="剧本标题")
    script: str = Field(..., description="剧本内容")
    episodeCount: Optional[int] = Field(default=1, description="集数")
    episodeContents: Optional[List[str]] = Field(default=[], description="各集独立内容（用于逐集生成）")
    style: Optional[str] = Field(default="写实风格", description="分镜风格")
    sceneRefs: Optional[List[str]] = Field(default=[], description="可用的场景名称列表")
    characterNames: Optional[List[str]] = Field(default=[], description="可用的角色名称列表")
    user_id: Optional[str] = Field(default=None, description="用户ID")
    stream: bool = Field(default=False, description="是否启用SSE流式输出")


class ShotGenerationResponse(BaseModel):
    """分镜(镜头级)生成响应"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="状态")
    message: str = Field(..., description="消息")
    episodes: Optional[List[ShotEpisode]] = Field(default=None, description="分集镜头数据")
