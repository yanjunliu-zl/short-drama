from pydantic import BaseModel, Field
from typing import List, Optional

# 作品基础模型
class WorkBase(BaseModel):
    title: str
    type: str
    description: Optional[str] = None

# 作品创建请求
class WorkCreateRequest(WorkBase):
    user_id: str = Field(..., description="用户ID")

# 作品更新请求
class WorkUpdateRequest(BaseModel):
    title: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = Field(None, description="状态: 草稿, 进行中, 已完成")

# 进度更新请求
class ProgressUpdateRequest(BaseModel):
    progress: int = Field(..., ge=0, le=100, description="进度百分比")

# 作品响应
class WorkResponse(WorkBase):
    id: str
    status: str
    progress: int
    userId: str
    createdDate: str
    lastModified: str
    createdAt: str
    updatedAt: str

    class Config:
        from_attributes = True

# 作品列表响应
class WorkListResponse(BaseModel):
    works: List[WorkResponse]
    total: int
    page: int
    page_size: int

# 导出响应
class ExportResponse(BaseModel):
    message: str
    export: dict