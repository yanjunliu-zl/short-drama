from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# 案例基础模型
class CaseBase(BaseModel):
    title: str
    description: str
    author: str
    tags: List[str]
    coverColor: str

# 案例创建请求
class CaseCreateRequest(CaseBase):
    pass

# 案例更新请求
class CaseUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    tags: Optional[List[str]] = None
    coverColor: Optional[str] = None

# 案例响应
class CaseResponse(CaseBase):
    id: str
    likes: int
    views: int
    createdAt: str
    updatedAt: str

    class Config:
        from_attributes = True

# 案例列表响应
class CaseListResponse(BaseModel):
    cases: List[CaseResponse]
    total: int
    page: int
    page_size: int

# 点赞响应
class LikeResponse(BaseModel):
    message: str
    likes: int

# 浏览响应
class ViewResponse(BaseModel):
    message: str
    views: int

# 分享响应
class ShareResponse(BaseModel):
    message: str