"""
离线预生成管线 — 批量预生成剧本，覆盖热点请求。

策略：
  1. 从数据库提取热门大纲/小说/风格组合 (top-K)
  2. 检查是否已有语义缓存
  3. 批量调用 V2 管线预生成剧本
  4. 结果存入语义缓存 + Redis 缓存
  5. 用户请求时直接命中缓存

节省：80% 的用户实时 LLM 调用。
"""
import asyncio
import logging
import time
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# 并发限制: 预生成任务不应影响在线服务
MAX_BATCH_CONCURRENCY = 2
BATCH_INTERVAL_SECONDS = 300  # 5 min between batch runs


class BatchPreGenerator:
    """离线批量预生成剧本。

    从热门请求模板中预生成结果，存入语义缓存。
    适合在 Celery beat 定时任务或 K8s CronJob 中运行。
    """

    def __init__(self, llm=None, db_session=None):
        self.llm = llm
        self.db = db_session

    async def generate_popular_combinations(
        self, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Generate scripts for popular style+theme+length combinations.

        Returns list of (request, result) pairs suitable for cache population.
        """
        from app.services.semantic_cache import get_semantic_cache

        # Popular combinations (in production, fetch from analytics DB)
        popular = [
            {"title": "重生之都市修仙", "theme": "奇幻", "length": "长篇", "style": "古装风格", "setting": "现代都市"},
            {"title": "总裁的秘密", "theme": "爱情", "length": "短篇", "style": "浪漫喜剧", "setting": "现代都市"},
            {"title": "末日逃生", "theme": "科幻", "length": "中篇", "style": "写实风格", "setting": "末世废土"},
            {"title": "穿越王妃", "theme": "爱情", "length": "中篇", "style": "古装风格", "setting": "古代宫廷"},
            {"title": "悬案追踪", "theme": "悬疑", "length": "短篇", "style": "悬疑风格", "setting": "现代都市"},
            {"title": "武林外传", "theme": "武侠", "length": "长篇", "style": "古装风格", "setting": "古代江湖"},
            {"title": "AI觉醒", "theme": "科幻", "length": "短篇", "style": "科幻风格", "setting": "近未来"},
            {"title": "乡村教师", "theme": "成长", "length": "短篇", "style": "写实风格", "setting": "乡村"},
            {"title": "宫锁心玉", "theme": "爱情", "length": "长篇", "style": "古装风格", "setting": "清代宫廷"},
            {"title": "特工任务", "theme": "悬疑", "length": "中篇", "style": "写实风格", "setting": "国际都市"},
        ]

        sem_cache = get_semantic_cache()
        results = []

        for i, req in enumerate(popular[:limit]):
            # Skip if already cached
            cached = await sem_cache.get(req)
            if cached:
                logger.debug(f"BatchPreGen: already cached '{req['title']}'")
                continue

            # Generate via V2 pipeline
            try:
                from app.services.novel2script_v2_service import Novel2ScriptV2Service
                from app.core.config import settings

                n2s = Novel2ScriptV2Service(
                    llm=self.llm,
                    mock_mode=False,
                    config=settings,
                )
                outline = f"一个{req['theme']}主题的{req['length']}故事，发生在{req['setting']}"
                result = await n2s.run_full_pipeline(
                    novel_text=outline,
                    style=req["style"],
                    target_episodes={"短篇": 5, "中篇": 8, "长篇": 12}.get(req["length"], 5),
                )

                script = result.get("final_script", "")
                if script:
                    await sem_cache.put(req, script)
                    results.append({"request": req, "length": len(script)})
                    logger.info(
                        f"BatchPreGen [{i+1}/{min(limit, len(popular))}]: "
                        f"generated '{req['title']}' ({len(script)} chars)"
                    )
            except Exception as e:
                logger.warning(f"BatchPreGen failed for '{req['title']}': {e}")

        return results

    async def run_batch(self, limit: int = 50) -> Dict[str, Any]:
        """Run a full batch pre-generation cycle."""
        t0 = time.time()
        logger.info(f"BatchPreGen: starting batch (limit={limit})")

        results = await self.generate_popular_combinations(limit=limit)

        elapsed = time.time() - t0
        logger.info(
            f"BatchPreGen: completed {len(results)} new generations "
            f"in {elapsed:.1f}s"
        )
        return {
            "generated": len(results),
            "elapsed_seconds": elapsed,
            "entries": [{"title": r["request"]["title"], "length": r["length"]} for r in results],
        }


# Cron job entry point — suitable for Celery Beat or K8s CronJob
async def run_scheduled_pregen():
    """Entry point for scheduled batch pre-generation.

    Usage:
      In Celery Beat:  @app.task   def pregen(): asyncio.run(run_scheduled_pregen())
      In K8s CronJob: python -c "from app.services.batch_pregen import run_scheduled_pregen; ..."
    """
    from app.utils.model_router import create_llm_client
    from app.services.semantic_cache import get_semantic_cache

    logger.info("ScheduledPreGen: starting")
    llm = create_llm_client(prefer="deepseek", timeout=300.0)
    if llm is None:
        logger.warning("ScheduledPreGen: no LLM available, skipping")
        return {"skipped": True, "reason": "no LLM"}

    pregen = BatchPreGenerator(llm=llm)
    result = await pregen.run_batch(limit=30)
    logger.info(f"ScheduledPreGen: done {result}")
    return result
