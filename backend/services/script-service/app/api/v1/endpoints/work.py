from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import uuid
from datetime import datetime

from app.schemas.work import (
    WorkResponse,
    WorkListResponse,
    WorkCreateRequest,
    WorkUpdateRequest,
    ProgressUpdateRequest
)

router = APIRouter()

# 模拟数据 - 我的作品
mock_works = [
    {
        "id": "1",
        "title": "夏日海滩邂逅",
        "status": "已完成",
        "progress": 100,
        "type": "爱情短剧",
        "userId": "user123",
        "createdDate": "2026-03-15",
        "lastModified": "2026-03-18",
        "createdAt": "2026-03-15T08:30:00Z",
        "updatedAt": "2026-03-18T14:20:00Z",
        "description": "一个关于夏日海滩浪漫邂逅的爱情故事"
    },
    {
        "id": "2",
        "title": "星际移民计划",
        "status": "进行中",
        "progress": 65,
        "type": "科幻系列",
        "userId": "user123",
        "createdDate": "2026-03-10",
        "lastModified": "2026-03-19",
        "createdAt": "2026-03-10T09:15:00Z",
        "updatedAt": "2026-03-19T11:45:00Z",
        "description": "人类首次星际移民的冒险故事"
    },
    {
        "id": "3",
        "title": "侦探事务所",
        "status": "草稿",
        "progress": 30,
        "type": "悬疑单元剧",
        "userId": "user123",
        "createdDate": "2026-03-05",
        "lastModified": "2026-03-12",
        "createdAt": "2026-03-05T14:20:00Z",
        "updatedAt": "2026-03-12T16:30:00Z",
        "description": "一家侦探事务所解决各种神秘案件的故事"
    }
]

@router.get("/", response_model=WorkListResponse)
async def list_works(
    user_id: str = Query(..., description="用户ID"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量")
):
    """
    获取我的作品列表
    """
    try:
        # 按用户ID筛选
        filtered_works = [work for work in mock_works if work["userId"] == user_id]

        # 按状态筛选
        if status:
            filtered_works = [work for work in filtered_works if work["status"] == status]

        # 按更新时间排序（最新的在前）
        filtered_works.sort(key=lambda x: x["updatedAt"], reverse=True)

        # 分页
        total = len(filtered_works)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_works = filtered_works[start_idx:end_idx]

        return WorkListResponse(
            works=paginated_works,
            total=total,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{work_id}", response_model=WorkResponse)
async def get_work(work_id: str):
    """
    获取作品详情
    """
    try:
        work = next((w for w in mock_works if w["id"] == work_id), None)
        if not work:
            raise HTTPException(status_code=404, detail="Work not found")

        return WorkResponse(**work)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=WorkResponse)
async def create_work(request: WorkCreateRequest):
    """
    创建新作品
    """
    try:
        now = datetime.utcnow()
        now_str = now.isoformat() + "Z"
        date_str = now.strftime("%Y-%m-%d")

        new_work = {
            "id": str(uuid.uuid4()),
            "title": request.title,
            "status": "草稿",
            "progress": 0,
            "type": request.type,
            "userId": request.user_id,
            "createdDate": date_str,
            "lastModified": date_str,
            "createdAt": now_str,
            "updatedAt": now_str,
            "description": request.description or ""
        }

        # 模拟添加到列表
        mock_works.append(new_work)

        return WorkResponse(**new_work)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{work_id}", response_model=WorkResponse)
async def update_work(work_id: str, request: WorkUpdateRequest):
    """
    更新作品信息
    """
    try:
        work = next((w for w in mock_works if w["id"] == work_id), None)
        if not work:
            raise HTTPException(status_code=404, detail="Work not found")

        # 更新字段
        if request.title is not None:
            work["title"] = request.title
        if request.type is not None:
            work["type"] = request.type
        if request.description is not None:
            work["description"] = request.description
        if request.status is not None:
            work["status"] = request.status

        # 更新修改时间
        work["lastModified"] = datetime.utcnow().strftime("%Y-%m-%d")
        work["updatedAt"] = datetime.utcnow().isoformat() + "Z"

        return WorkResponse(**work)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{work_id}/progress", response_model=WorkResponse)
async def update_progress(work_id: str, request: ProgressUpdateRequest):
    """
    更新作品进度
    """
    try:
        work = next((w for w in mock_works if w["id"] == work_id), None)
        if not work:
            raise HTTPException(status_code=404, detail="Work not found")

        # 更新进度
        work["progress"] = request.progress

        # 根据进度更新状态
        if request.progress == 100:
            work["status"] = "已完成"
        elif request.progress > 0:
            work["status"] = "进行中"

        # 更新修改时间
        work["lastModified"] = datetime.utcnow().strftime("%Y-%m-%d")
        work["updatedAt"] = datetime.utcnow().isoformat() + "Z"

        return WorkResponse(**work)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{work_id}")
async def delete_work(work_id: str):
    """
    删除作品
    """
    try:
        global mock_works
        work = next((w for w in mock_works if w["id"] == work_id), None)
        if not work:
            raise HTTPException(status_code=404, detail="Work not found")

        # 模拟删除
        mock_works = [w for w in mock_works if w["id"] != work_id]

        return {"message": "Work deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{work_id}/export")
async def export_work(work_id: str):
    """
    导出作品
    """
    try:
        work = next((w for w in mock_works if w["id"] == work_id), None)
        if not work:
            raise HTTPException(status_code=404, detail="Work not found")

        # 模拟导出（返回导出信息）
        export_data = {
            "work_id": work_id,
            "title": work["title"],
            "format": "PDF",
            "download_url": f"/api/v1/works/{work_id}/download/export.pdf",
            "generated_at": datetime.utcnow().isoformat() + "Z"
        }

        return {"message": "Export started", "export": export_data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))