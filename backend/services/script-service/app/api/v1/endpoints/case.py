from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import uuid
from datetime import datetime

from app.schemas.case import (
    CaseResponse,
    CaseListResponse,
    CaseCreateRequest,
    CaseUpdateRequest
)

router = APIRouter()

# 模拟数据 - 案例广场
mock_cases = [
    {
        "id": "1",
        "title": "未来都市冒险",
        "description": "一部关于未来科技与人性冲突的科幻短剧",
        "author": "AI创作助手",
        "likes": 245,
        "views": 1560,
        "tags": ["科幻", "冒险", "未来"],
        "coverColor": "#1890ff",
        "createdAt": "2026-03-15T10:30:00Z",
        "updatedAt": "2026-03-18T14:20:00Z"
    },
    {
        "id": "2",
        "title": "古风爱情传奇",
        "description": "古代宫廷中的爱恨情仇，精美的服化道设计",
        "author": "传统编剧师",
        "likes": 189,
        "views": 980,
        "tags": ["古风", "爱情", "历史"],
        "coverColor": "#52c41a",
        "createdAt": "2026-03-10T09:15:00Z",
        "updatedAt": "2026-03-16T11:45:00Z"
    },
    {
        "id": "3",
        "title": "悬疑推理剧场",
        "description": "密室谋杀案的层层解谜，反转不断的剧情",
        "author": "推理大师",
        "likes": 312,
        "views": 2100,
        "tags": ["悬疑", "推理", "犯罪"],
        "coverColor": "#fa8c16",
        "createdAt": "2026-03-05T14:20:00Z",
        "updatedAt": "2026-03-12T16:30:00Z"
    },
    {
        "id": "4",
        "title": "奇幻魔法世界",
        "description": "魔法学院的新生成长故事，奇幻生物与魔法对决",
        "author": "奇幻作家",
        "likes": 178,
        "views": 1250,
        "tags": ["奇幻", "魔法", "成长"],
        "coverColor": "#722ed1",
        "createdAt": "2026-03-08T11:45:00Z",
        "updatedAt": "2026-03-14T13:15:00Z"
    },
    {
        "id": "5",
        "title": "职场奋斗日记",
        "description": "互联网公司的职场生存法则与团队协作",
        "author": "职场观察员",
        "likes": 156,
        "views": 890,
        "tags": ["职场", "励志", "都市"],
        "coverColor": "#13c2c2",
        "createdAt": "2026-03-12T08:30:00Z",
        "updatedAt": "2026-03-17T10:20:00Z"
    },
    {
        "id": "6",
        "title": "家庭温情小品",
        "description": "普通家庭中的温馨日常与亲情故事",
        "author": "生活记录者",
        "likes": 198,
        "views": 1100,
        "tags": ["家庭", "温情", "生活"],
        "coverColor": "#f759ab",
        "createdAt": "2026-03-03T13:10:00Z",
        "updatedAt": "2026-03-09T15:40:00Z"
    }
]

@router.get("/", response_model=CaseListResponse)
async def list_cases(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    tag: Optional[str] = Query(None, description="按标签筛选"),
    sort_by: Optional[str] = Query("createdAt", description="排序字段: views, likes, createdAt"),
    order: Optional[str] = Query("desc", description="排序顺序: asc, desc")
):
    """
    获取案例广场列表
    """
    try:
        # 筛选数据
        filtered_cases = mock_cases
        if tag:
            filtered_cases = [case for case in mock_cases if tag in case["tags"]]

        # 排序
        reverse = order == "desc"
        if sort_by == "views":
            filtered_cases.sort(key=lambda x: x["views"], reverse=reverse)
        elif sort_by == "likes":
            filtered_cases.sort(key=lambda x: x["likes"], reverse=reverse)
        elif sort_by == "createdAt":
            filtered_cases.sort(key=lambda x: x["createdAt"], reverse=reverse)

        # 分页
        total = len(filtered_cases)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_cases = filtered_cases[start_idx:end_idx]

        return CaseListResponse(
            cases=paginated_cases,
            total=total,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(case_id: str):
    """
    获取案例详情
    """
    try:
        case = next((c for c in mock_cases if c["id"] == case_id), None)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        return CaseResponse(**case)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{case_id}/view")
async def record_view(case_id: str):
    """
    记录案例浏览
    """
    try:
        case = next((c for c in mock_cases if c["id"] == case_id), None)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        # 模拟增加浏览数
        case["views"] += 1
        return {"message": "View recorded", "views": case["views"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{case_id}/like")
async def toggle_like(case_id: str):
    """
    点赞/取消点赞案例
    """
    try:
        case = next((c for c in mock_cases if c["id"] == case_id), None)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        # 模拟切换点赞状态（这里简化为总是增加）
        case["likes"] += 1
        return {"message": "Liked", "likes": case["likes"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{case_id}/share")
async def record_share(case_id: str):
    """
    记录案例分享
    """
    try:
        case = next((c for c in mock_cases if c["id"] == case_id), None)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        # 这里可以记录分享到数据库
        return {"message": "Share recorded"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=CaseResponse)
async def create_case(request: CaseCreateRequest):
    """
    创建新案例（管理员功能）
    """
    try:
        new_case = {
            "id": str(uuid.uuid4()),
            "title": request.title,
            "description": request.description,
            "author": request.author,
            "likes": 0,
            "views": 0,
            "tags": request.tags,
            "coverColor": request.coverColor,
            "createdAt": datetime.utcnow().isoformat() + "Z",
            "updatedAt": datetime.utcnow().isoformat() + "Z"
        }

        # 模拟添加到列表
        mock_cases.append(new_case)

        return CaseResponse(**new_case)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))