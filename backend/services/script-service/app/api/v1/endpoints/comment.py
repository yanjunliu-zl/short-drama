"""评论区 API — 案例详情页下部评论区"""
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


# ==================== Schema ====================

class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000, description="评论内容")
    author: str = Field(default="匿名用户", max_length=100)
    user_id: str = Field(default="")


class CommentResponse(BaseModel):
    id: int
    case_id: str
    user_id: str
    author: str
    content: str
    created_at: str


class CommentListResponse(BaseModel):
    comments: List[CommentResponse]
    total: int
    page: int
    pages: int


# ==================== Endpoints ====================

@router.get("/{case_id}", response_model=CommentListResponse)
async def list_comments(
    case_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """获取案例的评论列表（分页）"""
    try:
        # 查询总数
        count_result = await db.execute(
            text("SELECT COUNT(*) FROM comments WHERE case_id = :cid"),
            {"cid": case_id},
        )
        total = count_result.scalar() or 0

        # 查询分页数据
        offset = (page - 1) * page_size
        result = await db.execute(
            text(
                "SELECT id, case_id, user_id, author, content, "
                "DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s') as created_at "
                "FROM comments WHERE case_id = :cid "
                "ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            ),
            {"cid": case_id, "limit": page_size, "offset": offset},
        )
        rows = result.fetchall()

        comments = [
            CommentResponse(
                id=row.id,
                case_id=row.case_id,
                user_id=row.user_id or "",
                author=row.author or "匿名用户",
                content=row.content,
                created_at=row.created_at or "",
            )
            for row in rows
        ]

        pages = max(1, (total + page_size - 1) // page_size)

        return CommentListResponse(
            comments=comments, total=total, page=page, pages=pages,
        )
    except Exception as e:
        logger.error(f"获取评论失败 case_id={case_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{case_id}", response_model=CommentResponse)
async def create_comment(
    case_id: str,
    body: CommentCreate,
    db: AsyncSession = Depends(get_db),
):
    """发表评论"""
    try:
        result = await db.execute(
            text(
                "INSERT INTO comments (case_id, user_id, author, content) "
                "VALUES (:case_id, :user_id, :author, :content)"
            ),
            {
                "case_id": case_id,
                "user_id": body.user_id,
                "author": body.author or "匿名用户",
                "content": body.content,
            },
        )
        await db.commit()

        comment_id = result.lastrowid

        # 查回刚插入的记录
        row_result = await db.execute(
            text("SELECT id, case_id, user_id, author, content, "
                 "DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s') as created_at "
                 "FROM comments WHERE id = :id"),
            {"id": comment_id},
        )
        row = row_result.fetchone()
        if not row:
            raise HTTPException(status_code=500, detail="评论创建后查询失败")

        return CommentResponse(
            id=row.id,
            case_id=row.case_id,
            user_id=row.user_id or "",
            author=row.author or "匿名用户",
            content=row.content,
            created_at=row.created_at or "",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"发表评论失败 case_id={case_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{case_id}/{comment_id}")
async def delete_comment(
    case_id: str,
    comment_id: int,
    user_id: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
):
    """删除评论（仅评论作者可删除）"""
    try:
        result = await db.execute(
            text("DELETE FROM comments WHERE id = :id AND case_id = :cid"),
            {"id": comment_id, "cid": case_id},
        )
        await db.commit()

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="评论不存在")

        return {"message": "删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除评论失败 comment_id={comment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
