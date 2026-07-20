"""推荐 API — 独立微服务 (Contextual Bandit enhanced)"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.services.ranking_model import get_ranking_service, RankingService
from app.services.recommendation_engine import RecommendationPipeline, RecallItem
from app.services.bandit import get_bandit_service, BanditService

router = APIRouter()
logger = logging.getLogger(__name__)


class RecommendResponse(BaseModel):
    items: List[dict]
    reason: str
    total: int


class FeedbackRequest(BaseModel):
    user_id: str
    case_id: str
    action: str  # view / like / share / skip
    recall_source: str = ""  # the recall source that produced this item


@router.get("/recommend", response_model=RecommendResponse)
async def get_recommendations(
    user_id: str = Query(default="", description="用户ID(空则返回热门)"),
    search_query: str = Query(default="", alias="q", description="搜索词"),
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    四层推荐流水线 + Contextual Bandit: 召回 → 过滤 → 排序(RL) → 重排

    示例:
      GET /api/v1/recommendations/recommend?user_id=1&limit=6
      GET /api/v1/recommendations/recommend?q=悬疑&limit=10
    """
    ranking_svc = get_ranking_service()
    redis = await get_redis()
    bandit_svc = get_bandit_service(redis)

    pipeline = RecommendationPipeline(db, ranking_svc, bandit_svc)

    ranked, reason = await pipeline.run(
        user_id=user_id,
        search_query=search_query,
        limit=limit,
    )

    items = []
    for i, r in enumerate(ranked):
        items.append({
            "id": r.case.case_id,
            "title": r.case.title,
            "description": r.case.description,
            "author": r.case.author,
            "tags": r.case.tags,
            "genre": r.case.genre,
            "views": r.case.view_count,
            "likes": r.case.like_count,
            "coverColor": r.case.cover_url,
            "createdAt": r.case.created_at,
            "_score": r.ctr_score,
            "_recall_source": r.case.recall_source,
        })

    return RecommendResponse(items=items, reason=reason, total=len(items))


@router.post("/feedback")
async def submit_feedback(
    req: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    提交用户交互反馈 — 用于 Bandit 在线学习

    示例:
      POST /api/v1/recommendations/feedback
      {"user_id":"1","case_id":"abc","action":"like","recall_source":"cf"}
    """
    if not req.user_id or not req.case_id:
        return {"status": "skipped", "reason": "missing user_id or case_id"}

    try:
        redis = await get_redis()
        bandit_svc = get_bandit_service(redis)

        # Build lightweight context from DB
        item_features = {"tag_match_count": 0, "genre_match": 0, "author_match": 0,
                          "item_age_days": 0, "hour_of_day": 12, "item_like_count": 0}
        user_features = {"total_interactions": 0, "is_new_user": False}

        # Fetch case metadata for richer context
        try:
            from sqlalchemy import text
            row = await db.execute(
                text("SELECT tags, genre, author, like_count, TIMESTAMPDIFF(DAY, created_at, NOW()) age_days FROM cases WHERE id=:id"),
                {"id": req.case_id})
            r = row.fetchone()
            if r:
                item_features["item_like_count"] = r.like_count or 0
                item_features["item_age_days"] = r.age_days or 0
        except Exception:
            pass

        await bandit_svc.record_feedback(
            req.user_id, req.case_id, req.action,
            req.recall_source or "hot", item_features, user_features)

        logger.info("Bandit feedback recorded: user=%s action=%s source=%s",
                     req.user_id, req.action, req.recall_source)
        return {"status": "ok"}
    except Exception as e:
        logger.error("Feedback recording failed: %s", e)
        return {"status": "error", "message": str(e)}


@router.post("/train")
async def trigger_training():
    """触发推荐模型离线训练 — 供 K8s CronJob 或手动调用"""
    import asyncio
    try:
        from app.services.train_model import run_scheduled_training
        result = await run_scheduled_training()
        return result
    except Exception as e:
        logger.error(f"Training trigger failed: {e}")
        return {"status": "failed", "error": str(e)}


@router.get("/health")
async def health():
    return {"status": "ok", "service": "recommendation-service"}
