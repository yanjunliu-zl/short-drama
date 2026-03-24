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