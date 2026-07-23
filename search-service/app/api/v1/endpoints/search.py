"""Search API — 站内搜索增强（Query 理解 / 语义检索 / LTR / 个性化 / 建议 / 漏斗）"""
import logging
import time
from typing import Optional

from fastapi import APIRouter, Query
from app.services.search_engine import SearchEnhancer

logger = logging.getLogger(__name__)

router = APIRouter()
_search_enhancer: Optional[SearchEnhancer] = None


async def _get_enhancer() -> SearchEnhancer:
    global _search_enhancer
    if _search_enhancer is None:
        import redis.asyncio as aioredis
        from app.core.config import settings
        try:
            r = aioredis.from_url(
                f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
                socket_connect_timeout=3,
            )
            await r.ping()
            _search_enhancer = SearchEnhancer(redis_client=r)
            logger.info("SearchEnhancer initialized with Redis")
        except Exception as e:
            logger.warning(f"Redis unavailable, SearchEnhancer in degraded mode: {e}")
            _search_enhancer = SearchEnhancer()
    return _search_enhancer


# ═══════════════ Search ═══════════════

@router.get("/search")
async def search(
    q: str = Query(..., description="搜索关键词"),
    user_id: str = Query("", description="用户 ID（个性化）"),
    page: int = Query(1),
    page_size: int = Query(20),
):
    """增强搜索：Query 理解 + BM25 + 语义检索 + LTR + 个性化"""
    t0 = time.time()
    try:
        enhancer = await _get_enhancer()

        # Fetch BM25 results from content-service
        import httpx
        from app.core.config import settings
        bm25_results = []
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{settings.CONTENT_SERVICE_URL}/api/v1/cases/search",
                    params={"q": q, "page": page, "pageSize": page_size * 2},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    bm25_results = data.get("hits", data.get("cases", []))
        except Exception as e:
            logger.warning(f"Content-service BM25 search failed: {e}")

        result = await enhancer.search(
            query=q, user_id=user_id,
            bm25_results=bm25_results,
            top_k=page_size,
        )

        await enhancer.record_query(q)

        elapsed = time.time() - t0
        logger.info(f"Search: q='{q}' hits={len(result.get('results', []))} elapsed={elapsed:.2f}s")
        return result

    except Exception as e:
        logger.error(f"Search failed: {e}")
        return {"results": [], "error": str(e)}


# ═══════════════ Suggestions ═══════════════

@router.get("/search/suggestions")
async def suggestions(
    q: str = Query("", description="前缀（自动补全）"),
    type: str = Query("autocomplete", description="autocomplete | trending"),
):
    """搜索建议：自动补全 / 热门搜索"""
    enhancer = await _get_enhancer()
    if type == "trending":
        items = await enhancer.suggest.trending(limit=10)
    else:
        items = await enhancer.autocomplete(q, limit=5)
    return {"suggestions": items}


# ═══════════════ Click Tracking ═══════════════

@router.post("/search/click")
async def search_click(
    query: str = Query(...),
    item_id: str = Query(...),
    position: int = Query(0),
    user_id: str = Query(""),
):
    """记录搜索结果点击（漏斗分析）"""
    enhancer = await _get_enhancer()
    await enhancer.record_click(query, item_id, position, user_id)
    return {"status": "ok"}


# ═══════════════ Funnel Stats ═══════════════

@router.get("/search/funnel")
async def search_funnel(query: str = Query("")):
    """搜索漏斗统计（CTR / 曝光 / 点击）"""
    enhancer = await _get_enhancer()
    return await enhancer.get_funnel_stats(query)


# ═══════════════ Health ═══════════════

@router.get("/health")
async def health():
    return {"status": "ok", "service": "search-service"}
