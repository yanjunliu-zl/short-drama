"""推荐 API — 独立微服务 (Contextual Bandit enhanced)"""
import json
import logging
import os
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
async def trigger_training(limit: int = 200000):
    """Trigger model training. POST /recommendations/train?limit=500000"""
    try:
        from app.services.train_model import TrainingPipeline
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            pipeline = TrainingPipeline(db_session=db)
            result = await pipeline.run(sample_limit=limit)
            return result
    except Exception as e:
        logger.error(f"Training failed: {e}")
        return {"status": "failed", "error": str(e)}


@router.get("/model-info")
async def get_model_info():
    """Return active model version and metrics."""
    from app.services.train_model import DEFAULT_MODEL_DIR
    metrics_path = os.path.join(DEFAULT_MODEL_DIR, "metrics.json")
    version_path = os.path.join(DEFAULT_MODEL_DIR, "version_history.json")
    info = {"active_version": None, "versions": [], "latest_metrics": None}
    if os.path.exists(metrics_path):
        with open(metrics_path) as f:
            info["latest_metrics"] = json.load(f)
    if os.path.exists(version_path):
        with open(version_path) as f:
            versions = json.load(f)
            info["versions"] = versions
            if versions:
                info["active_version"] = versions[-1]["version"]
    return info


@router.post("/rollback")
async def rollback_model(version: str = None):
    """Rollback to a specific version or to the best previous version."""
    try:
        from app.services.train_model import TrainingPipeline, DEFAULT_MODEL_DIR
        import shutil
        pipeline = TrainingPipeline(model_dir=DEFAULT_MODEL_DIR)
        pipeline._load_version_history()
        if not pipeline._versions:
            return {"status": "error", "reason": "no versions available"}

        if version:
            target = next((v for v in pipeline._versions if v.version == version), None)
        else:
            target = pipeline._get_best_version()

        if not target:
            return {"status": "error", "reason": "version not found"}

        # Copy versioned files to "latest"
        for src, dst_name in [(target.model_path, "wide_and_deep.pt"),
                               (target.preproc_path, "preprocessor.pkl")]:
            shutil.copy(src, os.path.join(DEFAULT_MODEL_DIR, dst_name))

        # Reload model
        from app.services.ranking_model import get_ranking_service
        svc = get_ranking_service()
        svc.initialize()

        logger.info(f"Rolled back to version {target.version} (AUC={target.metrics.get('best_auc')})")
        return {"status": "ok", "version": target.version,
                "metrics": target.metrics}
    except Exception as e:
        return {"status": "error", "reason": str(e)}


# ================================================================
# Enhanced Search (Douyin standard)
# ================================================================

# Lazy-loaded search enhancer instance
_search_enhancer = None


async def _get_search_enhancer():
    global _search_enhancer
    if _search_enhancer is None:
        from app.core.redis import get_redis
        from search_engine import SearchEnhancer
        redis = await get_redis()
        _search_enhancer = SearchEnhancer(redis_client=redis)
    return _search_enhancer


@router.get("/search")
async def enhanced_search(
    q: str = Query(..., description="Search query"),
    user_id: str = Query("", description="User ID for personalization"),
    page: int = Query(1), page_size: int = Query(20),
):
    """Enhanced search with query understanding, semantic retrieval, LTR, personalization."""
    try:
        enhancer = await _get_search_enhancer()

        # Fetch BM25 results from content-service ES
        import httpx
        bm25_results = []
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"http://content-service:8081/api/v1/cases/search",
                    params={"q": q, "page": page, "pageSize": page_size * 2},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    bm25_results = data.get("hits", data.get("cases", []))
        except Exception as e:
            logger.warning(f"Content-service search failed: {e}")

        # Fetch user profile for personalization
        user_profile = {}
        if user_id:
            from sqlalchemy.ext.asyncio import AsyncSession
            from app.core.database import get_db
            try:
                db = await get_db().__anext__()
                from app.services.recommendation_engine import RecommendationPipeline
                pipeline = RecommendationPipeline.__new__(RecommendationPipeline)
                pipeline.db = db
                user_profile = await pipeline._get_user_profile(user_id)
            except Exception as e:
                logger.debug(f"User profile fetch failed: {e}")

        # Enhanced search
        result = await enhancer.search(
            query=q, user_id=user_id,
            user_profile=user_profile,
            bm25_results=bm25_results,
            top_k=page_size,
        )

        # Record query for trending
        await enhancer.record_query(q)

        return result
    except Exception as e:
        logger.error(f"Enhanced search failed: {e}")
        return {"results": [], "error": str(e)}


@router.get("/search/suggestions")
async def search_suggestions(
    q: str = Query("", description="Prefix for autocomplete"),
    type: str = Query("autocomplete", description="autocomplete | trending"),
):
    """Search suggestions: autocomplete or trending queries."""
    enhancer = await _get_search_enhancer()
    if type == "trending":
        items = await enhancer.suggest.trending(limit=10)
    else:
        items = await enhancer.autocomplete(q, limit=5)
    return {"suggestions": items}


@router.post("/search/click")
async def search_click(
    query: str = Query(...),
    item_id: str = Query(...),
    position: int = Query(0),
    user_id: str = Query(""),
):
    """Record a search result click for funnel analytics."""
    enhancer = await _get_search_enhancer()
    await enhancer.record_click(query, item_id, position, user_id)
    return {"status": "ok"}


@router.get("/search/funnel")
async def search_funnel(query: str = Query("")):
    """Get search funnel statistics (CTR, impressions, clicks)."""
    enhancer = await _get_search_enhancer()
    return await enhancer.get_funnel_stats(query)


@router.get("/health")
async def health():
    return {"status": "ok", "service": "recommendation-service"}
