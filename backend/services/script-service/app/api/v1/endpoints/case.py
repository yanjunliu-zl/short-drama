"""案例广场 API — 代理到 content-service"""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
import logging

from app.schemas.case import (
    CaseResponse,
    CaseListResponse,
    CaseCreateRequest,
    CaseUpdateRequest
)
from app.client.content_service_client import get_content_service_client, ContentServiceClient

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_client() -> ContentServiceClient:
    return get_content_service_client()


@router.get("/", response_model=CaseListResponse)
async def list_cases(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    tag: Optional[str] = Query(None, description="按标签筛选"),
    sort_by: Optional[str] = Query("createdAt", description="排序字段: views, likes, createdAt"),
    order: Optional[str] = Query("desc", description="排序顺序: asc, desc"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    client: ContentServiceClient = Depends(_get_client),
):
    """获取案例广场列表"""
    try:
        result = await client.list_cases(
            page=page, page_size=page_size, tag=tag,
            sort_by=sort_by, order=order, search=search,
        )
        return CaseListResponse(**result)
    except Exception as e:
        logger.error(f"list_cases failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommended", response_model=CaseListResponse)
async def get_recommended(
    user_id: Optional[str] = Query(None, description="用户 ID"),
    limit: int = Query(6, ge=1, le=20, description="推荐数量"),
    client: ContentServiceClient = Depends(_get_client),
):
    """获取个性化推荐案例"""
    try:
        result = await client.get_recommended(user_id=user_id, limit=limit)
        cases = result.get("cases", [])
        return CaseListResponse(
            cases=cases, total=len(cases),
            page=1, page_size=len(cases),
        )
    except Exception as e:
        logger.error(f"get_recommended failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search", response_model=CaseListResponse)
async def search_cases(
    q: Optional[str] = Query(None, description="搜索关键词"),
    tags: Optional[str] = Query(None, description="标签，逗号分隔"),
    genre: Optional[str] = Query(None, description="类型"),
    author: Optional[str] = Query(None, description="作者"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    client: ContentServiceClient = Depends(_get_client),
):
    """搜索案例（支持 ES 全文检索）"""
    try:
        tag_list = [t.strip() for t in tags.split(",")] if tags else None
        result = await client.search_cases(
            q=q, tags=tag_list, genre=genre, author=author,
            page=page, page_size=page_size,
        )
        return CaseListResponse(**result)
    except Exception as e:
        logger.error(f"search_cases failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: str,
    client: ContentServiceClient = Depends(_get_client),
):
    """获取案例详情"""
    try:
        case = await client.get_case(case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        return CaseResponse(**case)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_case failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{case_id}/view")
async def record_view(
    case_id: str,
    client: ContentServiceClient = Depends(_get_client),
):
    """记录案例浏览"""
    try:
        await client.record_view(case_id)
        return {"message": "View recorded"}
    except Exception as e:
        logger.error(f"record_view failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{case_id}/like")
async def toggle_like(
    case_id: str,
    client: ContentServiceClient = Depends(_get_client),
):
    """点赞案例（写入 user_case_interactions 表）"""
    try:
        result = await client.record_like(case_id)
        return {"message": "Liked", "likes": result.get("likes", 0)}
    except Exception as e:
        logger.error(f"toggle_like failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{case_id}/share")
async def record_share(
    case_id: str,
    client: ContentServiceClient = Depends(_get_client),
):
    """记录案例分享"""
    try:
        await client.record_share(case_id)
        return {"message": "Share recorded"}
    except Exception as e:
        logger.error(f"record_share failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=CaseResponse)
async def create_case(
    request: CaseCreateRequest,
    client: ContentServiceClient = Depends(_get_client),
):
    """创建新案例"""
    try:
        data = {
            "title": request.title,
            "description": request.description,
            "author": request.author,
            "tags": request.tags,
            "coverColor": request.coverColor,
        }
        result = await client.create_case(data)
        if not result:
            raise HTTPException(status_code=502, detail="Content service unavailable")
        return CaseResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_case failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
