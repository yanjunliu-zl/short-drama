from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from typing import List, Optional
import os
import uuid
import time
import logging

from sqlalchemy import select

from app.models import Script
from app.schemas.script import (
    ScriptCreateRequest,
    ScriptResponse,
    ScriptListResponse,
    ScriptUpdateRequest,
    ScriptGenerationRequest,
    ScriptFromNovelRequest,
    ScriptFromOutlineRequest,
    GenerateResponse,
    ScriptSplitRequest,
    ScriptSplitResponse,
)
from app.services.script_service import ScriptService
from app.services.novel2script_service import Novel2ScriptService
from app.core.deps import get_script_service
from app.core.config import settings
from app.utils.sse import format_sse_event, EVENT_ERROR, EVENT_DONE

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/generate", response_model=ScriptResponse)
async def generate_script(
    request: ScriptGenerationRequest,
    background_tasks: BackgroundTasks,
    script_service: ScriptService = Depends(get_script_service)
):
    """
    生成剧本

    使用AI模型生成新的漫剧剧本。
    设置 stream=true 启用 SSE 流式输出。
    """
    use_streaming = getattr(request, "stream", False) and settings.SSE_STREAMING_ENABLED

    if use_streaming:
        logger.info(f"[API] POST /generate (stream) title={request.title}")

        async def event_generator():
            try:
                async for sse_event in script_service.ai_service.generate_script_stream(
                    request.dict()
                ):
                    yield sse_event
                yield format_sse_event({"status": "completed"}, event=EVENT_DONE)
            except Exception as e:
                logger.error(f"[API] Stream error: {e}")
                yield format_sse_event({"error": str(e), "code": type(e).__name__}, event=EVENT_ERROR)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    # Legacy non-streaming path
    task_id = str(uuid.uuid4())
    logger.info(f"[API] POST /generate task_id={task_id} title={request.title}")
    try:
        background_tasks.add_task(
            script_service.generate_script_async,
            task_id=task_id,
            request=request
        )
        logger.info(f"[API] 生成任务已提交 task_id={task_id}")
        return ScriptResponse(
            task_id=task_id,
            status="processing",
            message="Script generation started",
            script=None
        )
    except Exception as e:
        logger.error(f"[API] POST /generate 失败 task_id={task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{script_id}", response_model=ScriptResponse)
async def get_script(
    script_id: str,
    script_service: ScriptService = Depends(get_script_service)
):
    """
    获取剧本详情
    """
    logger.info(f"[API] GET /{script_id}")
    try:
        script = await script_service.get_script(script_id)
        if not script:
            logger.warning(f"[API] GET /{script_id} 剧本未找到")
            raise HTTPException(status_code=404, detail="Script not found")

        logger.info(f"[API] GET /{script_id} 成功 title={script.title}")
        return ScriptResponse(
            task_id=script_id,
            status="completed",
            message="Script retrieved successfully",
            script=script
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] GET /{script_id} 异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=ScriptListResponse)
async def list_scripts(
    page: int = 1,
    page_size: int = 10,
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    script_service: ScriptService = Depends(get_script_service)
):
    """
    获取剧本列表
    """
    logger.info(f"[API] GET / page={page} page_size={page_size} user_id={user_id} status={status}")
    try:
        scripts, total = await script_service.list_scripts(
            page=page,
            page_size=page_size,
            user_id=user_id,
            status=status
        )
        logger.info(f"[API] GET / 返回 {len(scripts)}/{total} 条记录")
        return ScriptListResponse(
            scripts=scripts,
            total=total,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        logger.error(f"[API] GET / 列表查询异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{script_id}", response_model=ScriptResponse)
async def update_script(
    script_id: str,
    request: ScriptUpdateRequest,
    script_service: ScriptService = Depends(get_script_service)
):
    """
    更新剧本
    """
    logger.info(f"[API] PUT /{script_id} title={request.title}")
    try:
        updated_script = await script_service.update_script(script_id, request)
        if not updated_script:
            logger.warning(f"[API] PUT /{script_id} 剧本未找到")
            raise HTTPException(status_code=404, detail="Script not found")

        logger.info(f"[API] PUT /{script_id} 更新成功")
        return ScriptResponse(
            task_id=script_id,
            status="completed",
            message="Script updated successfully",
            script=updated_script
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] PUT /{script_id} 异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{script_id}")
async def delete_script(
    script_id: str,
    script_service: ScriptService = Depends(get_script_service)
):
    """
    删除剧本
    """
    logger.info(f"[API] DELETE /{script_id}")
    try:
        success = await script_service.delete_script(script_id)
        if not success:
            logger.warning(f"[API] DELETE /{script_id} 剧本未找到")
            raise HTTPException(status_code=404, detail="Script not found")

        logger.info(f"[API] DELETE /{script_id} 删除成功")
        return {"message": "Script deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] DELETE /{script_id} 异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{script_id}/status")
async def get_script_status(
    script_id: str,
    script_service: ScriptService = Depends(get_script_service)
):
    """
    获取剧本生成状态
    """
    logger.info(f"[API] GET /{script_id}/status")
    try:
        status = await script_service.get_generation_status(script_id)
        if not status:
            logger.warning(f"[API] GET /{script_id}/status 任务未找到")
            raise HTTPException(status_code=404, detail="Script not found")

        logger.info(f"[API] GET /{script_id}/status 状态={status.get('status')} 进度={status.get('progress')}")
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] GET /{script_id}/status 异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/from-novel", response_model=ScriptResponse)
async def generate_script_from_novel(
    request: ScriptFromNovelRequest,
    background_tasks: BackgroundTasks,
    script_service: ScriptService = Depends(get_script_service)
):
    """
    从小说生成剧本

    使用AI模型将小说内容转换为剧本。
    设置 stream=true 启用 SSE 流式输出。
    """
    use_streaming = getattr(request, "stream", False) and settings.SSE_STREAMING_ENABLED

    if use_streaming:
        novel_len = len(getattr(request, 'novel_content', '') or '')
        logger.info(f"[API] POST /generate/from-novel (stream) title={request.title} novel_len={novel_len}")

        async def event_generator():
            try:
                async for sse_event in script_service.ai_service.novel_to_script_stream(
                    request.dict()
                ):
                    yield sse_event
                yield format_sse_event({"status": "completed"}, event=EVENT_DONE)
            except Exception as e:
                logger.error(f"[API] Stream error: {e}")
                yield format_sse_event({"error": str(e), "code": type(e).__name__}, event=EVENT_ERROR)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    # Legacy non-streaming path
    task_id = str(uuid.uuid4())
    novel_len = len(getattr(request, 'novel_content', '') or '')
    logger.info(f"[API] POST /generate/from-novel task_id={task_id} title={request.title} "
                f"novel_len={novel_len} style={getattr(request, 'style', '')}")
    try:
        background_tasks.add_task(
            script_service.generate_script_from_novel_async,
            task_id=task_id,
            request=request
        )
        logger.info(f"[API] 小说转剧本任务已提交 task_id={task_id}")
        return ScriptResponse(
            task_id=task_id,
            status="processing",
            message="Script generation from novel started",
            script=None
        )
    except Exception as e:
        logger.error(f"[API] POST /generate/from-novel 失败 task_id={task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/from-outline", response_model=ScriptResponse)
async def generate_script_from_outline(
    request: ScriptFromOutlineRequest,
    background_tasks: BackgroundTasks,
    script_service: ScriptService = Depends(get_script_service)
):
    """
    从大纲生成剧本

    使用AI模型根据剧本大纲扩展成完整剧本。
    设置 stream=true 启用 SSE 流式输出。
    """
    use_streaming = getattr(request, "stream", False) and settings.SSE_STREAMING_ENABLED

    if use_streaming:
        outline_len = len(getattr(request, 'outline', '') or '')
        logger.info(f"[API] POST /generate/from-outline (stream) title={request.title} outline_len={outline_len}")

        async def event_generator():
            try:
                async for sse_event in script_service.ai_service.generate_script_from_outline_stream(
                    request.dict()
                ):
                    yield sse_event
                yield format_sse_event({"status": "completed"}, event=EVENT_DONE)
            except Exception as e:
                logger.error(f"[API] Stream error: {e}")
                yield format_sse_event({"error": str(e), "code": type(e).__name__}, event=EVENT_ERROR)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    # Legacy non-streaming path
    task_id = str(uuid.uuid4())
    outline_len = len(getattr(request, 'outline', '') or '')
    logger.info(f"[API] POST /generate/from-outline task_id={task_id} title={request.title} "
                f"outline_len={outline_len}")
    try:
        background_tasks.add_task(
            script_service.generate_script_from_outline_async,
            task_id=task_id,
            request=request
        )
        logger.info(f"[API] 大纲生成任务已提交 task_id={task_id}")
        return ScriptResponse(
            task_id=task_id,
            status="processing",
            message="Script generation from outline started",
            script=None
        )
    except Exception as e:
        logger.error(f"[API] POST /generate/from-outline 失败 task_id={task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear-cache")
async def clear_cache():
    """清除所有 Redis 缓存（删除作品时调用）"""
    logger.info("[API] POST /clear-cache")
    try:
        from app.services.cache_service import get_cache_service
        cache = await get_cache_service()
        if cache and hasattr(cache, 'redis') and cache.redis:
            await cache.redis.flushdb()
            logger.info("[API] /clear-cache Redis 已清除")
        return {"message": "Cache cleared"}
    except Exception as e:
        logger.warning(f"[API] /clear-cache 失败: {e}")
        return {"message": f"Clear cache failed: {e}"}


@router.post("/extract-entities")
async def extract_entities(
    request: dict,
    script_service: ScriptService = Depends(get_script_service)
):
    """从剧本内容中提取主体（角色、地点、道具）。
    支持传入 script_id 复用剧本生成时已提取的角色和地点数据，仅对道具做 LLM 提取。"""
    content = request.get("content", "")
    script_id = request.get("script_id")
    content_len = len(content) if content else 0
    logger.info(f"[API] POST /extract-entities script_id={script_id} content_len={content_len}")
    t0 = time.time()

    try:
        mock_mode = getattr(script_service.ai_service, '_mock_mode', False)
        n2s = Novel2ScriptService(
            llm=script_service.ai_service.llm if not mock_mode else None,
            mock_mode=mock_mode
        )

        # 如果有 script_id，尝试从数据库获取预提取的角色和事件
        pre_extracted_characters = None
        pre_extracted_locations = None
        if script_id:
            try:
                async with script_service._get_db() as db:
                    stmt = select(Script).where(Script.id == int(script_id))
                    script_result = await db.execute(stmt)
                    script = script_result.scalar_one_or_none()
                    if script and script.characters:
                        pre_extracted_characters = script.characters
                        logger.info(f"[extract-entities] 从DB加载预提取角色: {len(pre_extracted_characters)}个 script_id={script_id}")
                    if script and script.analysis_result:
                        events = script.analysis_result
                        pre_extracted_locations = script_service._derive_locations_from_events(events)
                        logger.info(f"[extract-entities] 从事件派生地点: {len(pre_extracted_locations)}个 script_id={script_id}")
            except Exception as e:
                logger.warning(f"[extract-entities] 加载预提取实体失败 script_id={script_id}: {e}，回退到LLM提取")

        # 如果有预提取的角色和地点，仅对道具做 LLM 提取
        if pre_extracted_characters is not None and pre_extracted_locations is not None:
            if not content:
                logger.info(f"[extract-entities] 使用预提取数据（无道具）耗时={time.time()-t0:.1f}s")
                return {
                    "characters": pre_extracted_characters,
                    "locations": pre_extracted_locations,
                    "props": [],
                }
            # 仅提取道具
            try:
                props_result = await n2s.extract_entities(content)
                result = {
                    "characters": pre_extracted_characters,
                    "locations": pre_extracted_locations,
                    "props": props_result.get("props", []),
                }
                logger.info(f"[extract-entities] 预提取+道具LLM完成 "
                            f"角色={len(result['characters'])} 地点={len(result['locations'])} "
                            f"道具={len(result['props'])} 耗时={time.time()-t0:.1f}s")
                return result
            except Exception as e:
                logger.warning(f"[extract-entities] 道具LLM提取失败: {e}，返回无道具结果")
                return {
                    "characters": pre_extracted_characters,
                    "locations": pre_extracted_locations,
                    "props": [],
                }

        # 无预提取数据，走完整 LLM 提取
        if not content:
            raise HTTPException(status_code=400, detail="Content is required")

        result = await n2s.extract_entities(content)
        logger.info(f"[extract-entities] 完整LLM提取完成 "
                    f"角色={len(result.get('characters',[]))} "
                    f"地点={len(result.get('locations',[]))} "
                    f"道具={len(result.get('props',[]))} 耗时={time.time()-t0:.1f}s")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] POST /extract-entities 异常 script_id={script_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/split", response_model=ScriptSplitResponse)
async def upload_and_split_script(
    request: ScriptSplitRequest,
    script_service: ScriptService = Depends(get_script_service)
):
    """
    上传完整剧本并自动拆分为分集

    接收完整剧本内容，检测「第N集」标记，拆分为结构化分集列表，
    持久化到数据库，并返回分集数据。
    """
    logger.info(f"[API] POST /split title={request.title} content_len={len(request.content) if request.content else 0}")
    try:
        if not request.content or not request.content.strip():
            raise HTTPException(status_code=400, detail="剧本内容不能为空")
        if not request.title or not request.title.strip():
            raise HTTPException(status_code=400, detail="剧本标题不能为空")

        result = await script_service.upload_and_split_script(request)
        logger.info(f"[API] POST /split 完成 script_id={result.get('script_id')} episodes={result.get('total_episodes')}")
        return result
    except ValueError as e:
        logger.warning(f"[API] POST /split 参数错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] POST /split 异常 title={request.title}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{script_id}/character-graph")
async def get_character_graph(
    script_id: int,
    script_service: ScriptService = Depends(get_script_service)
):
    """获取角色关系图谱（V2 pipeline）"""
    logger.info(f"[API] GET /{script_id}/character-graph")
    try:
        graph = await script_service.get_script_character_graph(script_id)
        if graph is None:
            raise HTTPException(status_code=404, detail="Character graph not available for this script")
        return graph
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] GET /{script_id}/character-graph 异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/from-outline-sync", response_model=ScriptSplitResponse)
async def generate_from_outline_sync(
    request: ScriptFromOutlineRequest,
    script_service: ScriptService = Depends(get_script_service)
):
    """从大纲/想法同步生成剧本 — 使用 V2 管线，统一输出格式。
    设置 stream=true 启用 SSE 流式输出（stage 事件 + done 结果）。"""
    import asyncio as _asyncio
    from app.services.novel2script_v2_service import Novel2ScriptV2Service
    from app.core.config import settings as app_settings

    outline_len = len(getattr(request, 'outline', '') or '')
    use_streaming = getattr(request, "stream", False) and settings.SSE_STREAMING_ENABLED
    logger.info(f"[API] POST /generate/from-outline-sync title={request.title} "
                f"outline_len={outline_len} stream={use_streaming}")
    t0 = time.time()
    try:
        if not request.outline or not request.outline.strip():
            raise HTTPException(status_code=400, detail="想法/大纲内容不能为空")
        if not request.title or not request.title.strip():
            raise HTTPException(status_code=400, detail="剧本标题不能为空")

        if not script_service._initialized:
            await script_service.initialize()

        mock_mode = getattr(script_service.ai_service, '_mock_mode', False)
        style = getattr(request, 'style', '') or app_settings.N2S_V2_DEFAULT_STYLE

        n2s_v2 = Novel2ScriptV2Service(
            llm=script_service.ai_service.llm if not mock_mode else None,
            mock_mode=mock_mode,
            config=app_settings,
        )

        # Parse episode count for both paths
        import re as _re
        cn_num_map = {c: i for i, c in enumerate(
            ['', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十',
             '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十',
             '二十一', '二十二', '二十三', '二十四', '二十五', '二十六', '二十七', '二十八', '二十九', '三十',
             '三十一', '三十二', '三十三', '三十四', '三十五', '三十六', '三十七', '三十八', '三十九', '四十',
             '四十一', '四十二', '四十三', '四十四', '四十五', '四十六', '四十七', '四十八', '四十九', '五十'], start=0)}
        def _parse_ep_count(text: str) -> int:
            if not text: return 0
            for m in _re.finditer(r'([一二三四五六七八九十百千\d]+)\s*集', text):
                num_str = m.group(1)
                if num_str.isdigit(): return int(num_str)
                n = cn_num_map.get(num_str, 0)
                if n > 0: return n
            return 0

        user_ep_count = _parse_ep_count(request.outline) or _parse_ep_count(request.title)
        target_eps = user_ep_count if user_ep_count > 0 else length_to_eps.get(getattr(request, 'length', '短篇'), 5)
        target_eps = min(target_eps, 50)

        # ---- SSE streaming path ----
        if use_streaming:
            async def event_generator():
                async for sse_event in n2s_v2.run_full_pipeline_sse(
                    novel_text=request.outline, style=style, target_episodes=target_eps,
                ):
                    yield sse_event
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            )

        # ---- Non-streaming path (existing code) ----
        result = await _asyncio.wait_for(
            n2s_v2.run_full_pipeline(novel_text=request.outline, style=style,
                                      target_episodes=target_eps),
            timeout=600
        )

        episodes = result.get("episodes") or script_service._split_content_to_episodes(
            result.get("final_script", "")
        )
        # Build ShotEpisode-format storyboard from V2 pipeline data
        storyboard_data = result.get("storyboard", [])
        shot_episodes = script_service._build_shot_episodes(
            storyboard_data, episodes
        ) if storyboard_data else None

        # Track usage (fire-and-forget)
        from app.services.usage_tracker import track_llm_usage, estimate_tokens
        chapter_count = len(result.get("script_scenes", []))
        call_count = chapter_count + 2 if chapter_count > 0 else 1
        estimated_in = estimate_tokens(request.outline) * 2
        estimated_out = estimate_tokens(result.get("final_script", ""))
        user_id_str = str(getattr(request, 'user_id', '') or 'anonymous')
        _asyncio.ensure_future(track_llm_usage(
            user_id=user_id_str, model_name="deepseek-chat",
            tokens_in=estimated_in, tokens_out=estimated_out,
            call_count=call_count,
            duration_ms=int((time.time() - t0) * 1000),
            endpoint="/generate/from-outline-sync",
            service_name="script-service",
        ))

        # Record business metrics
        try:
            from app.middleware.prometheus import BusinessMetrics
            BusinessMetrics.record_script_generation(
                script_type="outline", status="success",
                duration=time.time() - t0)
        except Exception:
            pass

        logger.info(f"[API] POST /generate/from-outline-sync 完成 title={request.title} "
                    f"episodes={len(episodes)} total_chars={len(result.get('final_script', ''))} "
                    f"storyboard_shots={len(storyboard_data)} "
                    f"耗时={time.time()-t0:.1f}s")
        return {
            "script_id": 0, "title": request.title,
            "episodes": episodes, "total_episodes": len(episodes),
            "storyboard": shot_episodes,
        }
    except _asyncio.TimeoutError:
        logger.error(f"[API] POST /generate/from-outline-sync 超时 title={request.title} (600s)")
        raise HTTPException(status_code=504, detail="AI 生成超时（10分钟），请缩短输入内容后重试")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] POST /generate/from-outline-sync 异常 title={request.title}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
