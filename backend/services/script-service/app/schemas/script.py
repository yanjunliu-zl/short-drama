from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


# 剧本生成请求
class ScriptGenerationRequest(BaseModel):
    """剧本生成请求"""
    title: str = Field(..., description="剧本标题")
    theme: str = Field(..., description="剧本主题")
    length: str = Field(..., description="剧本长度: 短篇, 中篇, 长篇")
    characters: Optional[List[str]] = Field(default=[], description="角色列表")
    setting: Optional[str] = Field(default="现代都市", description="故事背景")
    style: Optional[str] = Field(default="浪漫喜剧", description="剧本风格")
    user_id: Optional[str] = Field(default=None, description="用户ID")


# 剧本生成请求 - 从剧本大纲
class ScriptFromOutlineRequest(BaseModel):
    """从剧本大纲生成剧本"""
    title: str = Field(..., description="剧本标题")
    outline: str = Field(..., description="剧本大纲")
    theme: str = Field(..., description="剧本主题")
    length: str = Field(..., description="剧本长度: 短篇, 中篇, 长篇")
    characters: Optional[List[str]] = Field(default=[], description="角色列表")
    setting: Optional[str] = Field(default="现代都市", description="故事背景")
    style: Optional[str] = Field(default="浪漫喜剧", description="剧本风格")
    user_id: Optional[str] = Field(default=None, description="用户ID")


# 剧本生成请求 - 从小说
class ScriptFromNovelRequest(BaseModel):
    """从小说生成剧本"""
    title: str = Field(..., description="剧本标题")
    novel_content: str = Field(..., description="小说内容")
    theme: str = Field(..., description="剧本主题")
    length: str = Field(..., description="剧本长度: 短篇, 中篇, 长篇")
    characters: Optional[List[str]] = Field(default=[], description="角色列表")
    setting: Optional[str] = Field(default="现代都市", description="故事背景")
    style: Optional[str] = Field(default="浪漫喜剧", description="剧本风格")
    user_id: Optional[str] = Field(default=None, description="用户ID")
    excerpt_ratio: Optional[float] = Field(default=0.3, description="抽取比例(0-1)，用于长小说")


# 剧本创建请求
class ScriptCreateRequest(BaseModel):
    """剧本创建请求"""
    title: str = Field(..., description="剧本标题")
    content: str = Field(..., description="剧本内容")
    theme: Optional[str] = Field(default=None, description="剧本主题")
    length: Optional[str] = Field(default="短篇", description="剧本长度")
    user_id: str = Field(..., description="用户ID")


# 剧本更新请求
class ScriptUpdateRequest(BaseModel):
    """剧本更新请求"""
    title: Optional[str] = Field(default=None, description="剧本标题")
    content: Optional[str] = Field(default=None, description="剧本内容")
    status: Optional[str] = Field(default=None, description="状态: 草稿, 进行中, 已完成")


# 剧本响应
class ScriptResponse(BaseModel):
    """剧本响应"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="状态: processing, completed, failed")
    message: str = Field(..., description="消息")
    script: Optional[Dict[str, Any]] = Field(default=None, description="剧本数据")


# 剧本列表响应
class ScriptListResponse(BaseModel):
    """剧本列表响应"""
    scripts: List[Dict[str, Any]] = Field(..., description="剧本列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")


# 生成响应
class GenerateResponse(BaseModel):
    """生成响应"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="状态: processing, completed, failed")
    message: str = Field(..., description="消息")
    script_id: Optional[str] = Field(default=None, description="剧本ID")


# ========== 上传剧本并分集 ==========

class EpisodeItem(BaseModel):
    """单集剧本"""
    episode_number: int = Field(..., description="集号，从1开始")
    title: str = Field(..., description="集标题，如 '第一集'")
    content: str = Field(..., description="该集完整剧本内容")


class ScriptSplitRequest(BaseModel):
    """上传完整剧本并自动分集请求"""
    title: str = Field(..., description="剧本标题")
    content: str = Field(..., description="完整剧本内容")
    user_id: Optional[str] = Field(default=None, description="用户ID")


class ScriptSplitResponse(BaseModel):
    """剧本分集响应"""
    script_id: int = Field(..., description="持久化后的剧本ID")
    title: str = Field(..., description="剧本标题")
    episodes: List[EpisodeItem] = Field(default_factory=list, description="分集列表")
    total_episodes: int = Field(default=0, description="总集数")