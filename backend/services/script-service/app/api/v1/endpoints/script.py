from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, UploadFile, File, Form
from fastapi.responses import StreamingResponse
import asyncio
import json
from typing import List, Optional
from pydantic import BaseModel
import os
import uuid
import time
import logging
import re as _re_module

from sqlalchemy import select, text

from app.models import Script
from app.schemas.script import (
    ScriptCreateRequest,
    ScriptResponse,
    ScriptListResponse,
    ScriptUpdateRequest,
    ScriptFromNovelRequest,
    ScriptFromOutlineRequest,
    GenerateResponse,
    ScriptSplitRequest,
    ScriptSplitResponse,
)
from app.services.script_service import ScriptService
from app.core.deps import get_script_service
from app.core.config import settings
from app.utils.sse import format_sse_event, EVENT_ERROR, EVENT_DONE

logger = logging.getLogger(__name__)

router = APIRouter()


async def _enqueue_task(
    task_id: str, task_type: str, request_dict: dict,
    background_tasks, fallback_fn,
) -> bool:
    """Try to enqueue task through Kafka/memory worker.

    Returns True if enqueued to worker, False if fell back to BackgroundTasks.
    """
    try:
        from app.services.task_worker import get_task_worker
        worker = await get_task_worker()
        if worker._queue is not None or hasattr(worker, '_consumer'):
            await worker.enqueue(task_id, task_type, request_dict)
            return True
    except Exception as e:
        logger.debug(f"Task worker enqueue unavailable ({e}) — using BackgroundTasks")

    # Fallback: schedule async task to current event loop
    # Normalize: fallback_fn can be a callable/lambda (novel pattern) or a coroutine (eager)
    if callable(fallback_fn):
        coro = fallback_fn()
    else:
        coro = fallback_fn
    task = asyncio.create_task(coro)
    logger.info(f"[_enqueue_task] Fallback task created: {task_id} task_name={task.get_name()}")
    return False


# (已移除 POST /generate — 从零创作不允许，请使用 /generate/from-novel 或 /generate/from-outline)

# ── Plot Templates (must be before /{script_id} to avoid route conflict) ──

@router.get("/templates")
async def list_plot_templates():
    """列出所有可用的情节结构模板"""
    from app.services.plot_templates import list_templates
    templates = list_templates()
    return {"success": True, "data": templates, "total": len(templates)}


@router.get("/templates/match")
async def match_plot_template(style: str = "", theme: str = ""):
    """根据风格和主题自动匹配最佳情节模板"""
    from app.services.plot_templates import match_template, list_templates
    template = match_template(style=style, theme=theme)
    if template:
        return {
            "success": True,
            "data": {
                "matched": True,
                "template_id": template.template_id,
                "genre_cn": template.genre_cn,
                "total_episodes": template.total_episodes,
                "character_archetypes": template.character_archetypes,
                "structure_summary": [
                    {"episode": ep.episode, "title": ep.title_hint, "beat": ep.primary_beat.value, "cliffhanger": ep.cliffhanger[:80]}
                    for ep in template.episodes[:8]
                ],
                "paywall_positions": template.get_paywall_positions(),
            },
        }
    return {"success": True, "data": {"matched": False, "available": [t["template_id"] for t in list_templates()]}}


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

        logger.info(f"[API] GET /{script_id} 成功 title={script.get('title', '')}")
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
        from app.services.script_service import _task_get
        status = await _task_get(script_id)
        if not status:
            logger.warning(f"[API] GET /{script_id}/status 任务未找到")
            raise HTTPException(status_code=404, detail="Task not found")

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
    从小说生成剧本 — 异步队列模式。返回 task_id，前端轮询状态。

    短内容自动降级: 如果无明显章节标记，走大纲轻量路径（同步返回）。
    """
    novel_content = getattr(request, 'novel_content', '') or ''
    novel_len = len(novel_content)

    # Auto-degrade: short text without chapter markers → outline path
    from app.services.generation_engine import ScriptGenerationEngine
    chapter_count = ScriptGenerationEngine.detect_chapter_count(novel_content)
    if chapter_count < 2:
        logger.info(f"[API] POST /generate/from-novel → degraded to outline path "
                    f"(len={novel_len}, chapters={chapter_count})")
        await script_service.initialize()
        engine = ScriptGenerationEngine(
            llm=script_service.llm,
            mock_mode=getattr(script_service, '_mock_mode', False),
            config=settings,
        )
        result = await engine.generate_from_outline(
            outline_text=novel_content,
            style=getattr(request, 'style', ''),
        )
        return ScriptResponse(
            task_id="degraded",
            status="completed",
            message="Auto-routed to outline pipeline (no chapter markers detected)",
            script={"episodes": result.get("episodes", []), "title": request.title},
        )

    # Full novel path — enqueue through Kafka/memory worker
    task_id = str(uuid.uuid4())
    logger.info(f"[API] POST /generate/from-novel task_id={task_id} title={request.title} "
                f"novel_len={novel_len} chapters={chapter_count} "
                f"style={getattr(request, 'style', '')}")
    try:
        enqueued = await _enqueue_task(
            task_id=task_id, task_type="from-novel", request_dict=request.dict(),
            background_tasks=background_tasks,
            fallback_fn=lambda: script_service.generate_script_from_novel_async(
                task_id, request),
        )
        backend = "kafka" if enqueued else "background"
        logger.info(f"[API] 小说转剧本任务已提交 task_id={task_id} backend={backend}")
        return ScriptResponse(
            task_id=task_id,
            status="processing",
            message="Script generation from novel started",
            script=None
        )
    except Exception as e:
        logger.error(f"[API] POST /generate/from-novel 失败 task_id={task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# (废弃的 POST /generate/from-outline 已移除 — 使用 /generate/from-outline)


@router.post("/generate/from-outline/continue", response_model=ScriptSplitResponse)
async def continue_outline_generation(
    data: dict,
    script_service: ScriptService = Depends(get_script_service),
):
    """续写大纲剧本 — 在前一批剧集之后生成更多集。

    请求体:
      {
        "previous_script_id": 123,         // 前一批的 script_id（用于加载框架+角色）
        "additional_episodes": 10,         // 要新生成多少集（最大20）
        "style": "ancient",
        "user_id": "xxx"
      }

    返回: 新生成的 episodes，前端拼接到已有剧集后面。
    """
    previous_script_id = data.get("previous_script_id", 0)
    additional_episodes = min(data.get("additional_episodes", 10), 20)

    if not previous_script_id:
        raise HTTPException(status_code=400, detail="previous_script_id is required")

    await script_service.initialize()
    prev_script = await script_service.get_script(int(previous_script_id))
    if not prev_script:
        raise HTTPException(status_code=404, detail="Previous script not found")

    # Load framework + characters + previous context from the previous script
    wf_meta = prev_script.get("workflow_metadata", {}) or {}
    story_framework = wf_meta.get("story_framework", "")
    if not story_framework:
        raise HTTPException(status_code=400, detail="Previous script has no story framework — cannot continue")
    previous_context = wf_meta.get("batch_context", "")

    # Parse characters from previous script
    import json as _json
    characters_raw = prev_script.get("characters", "[]")
    if isinstance(characters_raw, str):
        characters = _json.loads(characters_raw) if characters_raw else []
    else:
        characters = characters_raw or []

    existing_episodes = prev_script.get("episodes", []) or []
    start_ep = len(existing_episodes) + 1
    style = data.get("style", prev_script.get("style", ""))

    logger.info(f"[Continue] script={previous_script_id} existing={len(existing_episodes)}eps "
                f"adding={additional_episodes}eps starting_at={start_ep}")

    engine = ScriptGenerationEngine(
        llm=script_service.llm if not script_service._mock_mode else None,
        mock_mode=script_service._mock_mode,
        config=settings,
    )

    result = await engine.outline.continue_from(
        story_framework=story_framework,
        characters=characters,
        style=style,
        start_episode=start_ep,
        additional_episodes=additional_episodes,
        previous_context=previous_context,
        previous_episodes=existing_episodes,
    )

    new_episodes = result.get("episodes", [])

    # Append to existing script
    all_episodes = existing_episodes + new_episodes
    # Rebuild final_script
    final_script_parts = []
    for ep in all_episodes:
        ep_title = ep.get("title", f"第{ep.get('episode_number', '?')}集")
        final_script_parts.append(f"{ep_title}\n\n{ep.get('content', '')}")
    final_script = "\n\n" + "—" * 40 + "\n\n".join(final_script_parts)

    # Summarize latest episodes as context for potential next continuation
    recent_for_context = all_episodes[-5:] if len(all_episodes) >= 5 else all_episodes
    batch_context = await engine.outline.summarize_batch(recent_for_context, characters)

    # Update DB
    wf_meta["batch_context"] = batch_context or ""
    await script_service.repo.update_script(previous_script_id, {
        "content": final_script,
        "episodes": all_episodes,
        "workflow_metadata": wf_meta,
    })

    logger.info(f"[Continue] Done: {len(new_episodes)} new episodes "
                f"(total: {len(all_episodes)})")

    return {
        "script_id": previous_script_id,
        "title": prev_script.get("title", ""),
        "episodes": new_episodes,
        "total_episodes": len(all_episodes),
    }


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
    background_tasks: BackgroundTasks,
    script_service: ScriptService = Depends(get_script_service)
):
    """从剧本内容中提取主体（角色、地点、道具）— 异步模式。

    立即返回 task_id，后台执行 LLM 提取，前端轮询 /extract-entities/{task_id}/status。
    """
    content = request.get("content", "")
    script_id = request.get("script_id")
    task_id = str(uuid.uuid4())
    logger.info(f"[API] POST /extract-entities task_id={task_id} script_id={script_id} content_len={len(content) if content else 0}")

    if not content:
        raise HTTPException(status_code=400, detail="Content is required")

    # Set initial status via Redis
    from app.services.script_service import _task_set
    await _task_set(f"extract:{task_id}", {"status": "processing", "progress": 0})

    # Process in background
    background_tasks.add_task(
        _do_extract_entities,
        task_id=task_id, content=content, script_id=script_id,
        script_service=script_service,
    )

    return {"task_id": task_id, "status": "processing", "message": "提取任务已提交"}


async def _do_extract_entities(
    task_id: str, content: str, script_id, script_service
):
    """Background task: run entity extraction and store results in Redis."""
    from app.services.generation_engine import ScriptGenerationEngine
    from app.services.script_service import _task_set

    t0 = time.time()
    try:
        mock_mode = getattr(script_service, '_mock_mode', False)
        n2s_v2 = ScriptGenerationEngine(
            llm=script_service.llm if not mock_mode else None,
            mock_mode=mock_mode, config=settings,
        )

        await _task_set(f"extract:{task_id}", {"status": "processing", "progress": 50})

        # If script_id not provided, try to recover by content matching
        if not script_id and content:
            try:
                async with script_service._get_db() as db:
                    # Trim leading whitespace and use first 150 chars for matching
                    prefix = content.strip()[:150]
                    # Escape SQL LIKE wildcards
                    prefix_escaped = prefix.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
                    stmt = text(
                        "SELECT id FROM scripts WHERE content LIKE :prefix ESCAPE '\\\\' "
                        "ORDER BY id DESC LIMIT 1"
                    )
                    script_result = await db.execute(stmt, {"prefix": prefix_escaped + '%'})
                    row = script_result.fetchone()
                    if row:
                        script_id = row[0]
                        logger.info(f"[extract-entities] Recovered script_id={script_id} via content matching")
            except Exception as e:
                logger.warning(f"[extract-entities] Content-matching fallback failed: {e}")

        # Check for pre-extracted data if script_id provided
        # V2 pipeline already stores entities in DB — skip expensive LLM re-extraction
        pre_extracted_chars = None
        pre_extracted_locs = None
        pre_extracted_props = None
        if script_id:
            try:
                async with script_service._get_db() as db:
                    stmt = select(Script).where(Script.id == int(script_id))
                    script_result = await db.execute(stmt)
                    script = script_result.scalar_one_or_none()
                    if script and script.characters:
                        chars = script.characters
                        pre_extracted_chars = json.loads(chars) if isinstance(chars, str) else chars
                    if script and script.analysis_result:
                        ar = script.analysis_result
                        ar = json.loads(ar) if isinstance(ar, str) else ar
                        # analysis_result = { events: [], locations: [...], props: [...] }
                        pre_extracted_locs = ar.get("locations", [])
                        pre_extracted_props = ar.get("props", [])
                    if script and script.source_type == "novel":
                        logger.info("[extract-entities] Novel source: using V2 pipeline entities from DB")
            except Exception as e:
                logger.warning(f"[extract-entities] pre-extract failed: {e}")

        # Run LLM extraction only if no pre-extracted data (non-novel sources)
        if pre_extracted_chars is not None and pre_extracted_locs is not None:
            result = {
                "characters": pre_extracted_chars,
                "locations": pre_extracted_locs,
                "props": pre_extracted_props or [],
            }
        else:
            result = await n2s_v2._extract_entities_from_script(content, [], {})

        elapsed = time.time() - t0
        logger.info(f"[extract-entities] 完成 task={task_id} 角色={len(result.get('characters',[]))} "
                    f"地点={len(result.get('locations',[]))} 道具={len(result.get('props',[]))} "
                    f"耗时={elapsed:.1f}s")

        await _task_set(f"extract:{task_id}", {
            "status": "completed", "progress": 100,
            "result": result, "elapsed_ms": int(elapsed * 1000),
        })
    except Exception as e:
        logger.error(f"[extract-entities] 失败 task={task_id}: {e}")
        await _task_set(f"extract:{task_id}", {
            "status": "failed", "progress": 0, "error": str(e),
        })


@router.get("/extract-entities/{task_id}/status")
async def extract_entities_status(task_id: str):
    """查询实体提取任务状态"""
    from app.services.script_service import _task_get
    data = await _task_get(f"extract:{task_id}")
    if not data:
        return {"status": "not_found"}
    return data


@router.post("/upload", response_model=ScriptSplitResponse)
async def upload_script_file(
    file: UploadFile = File(...),
    title: str = Form(...),
    script_service: ScriptService = Depends(get_script_service),
):
    """上传剧本文件 — 服务端解析 + 自动分集。

    支持 .txt / .md / .docx 文件。
    解析后按「第N集」标记自动拆分为结构化分集列表，持久化到数据库。
    """
    logger.info(f"[API] POST /upload title={title} filename={file.filename} "
                f"size={file.size} content_type={file.content_type}")
    t0 = time.time()

    # 限制文件大小 (10MB)
    max_size = 10 * 1024 * 1024
    if file.size and file.size > max_size:
        raise HTTPException(status_code=400, detail=f"文件过大，最大支持 10MB")

    # 解析文件内容
    content = ""
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    try:
        raw_bytes = await file.read()

        if ext in ("txt", "md", ""):
            content = raw_bytes.decode("utf-8", errors="replace")
        elif ext == "docx":
            try:
                from io import BytesIO
                from docx import Document
                doc = Document(BytesIO(raw_bytes))
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                content = "\n\n".join(paragraphs)
            except ImportError:
                raise HTTPException(status_code=400, detail="服务端不支持 .docx 解析，请使用 .txt 格式")
        else:
            raise HTTPException(status_code=400, detail=f"不支持的文件格式: .{ext}，支持 .txt / .md / .docx")
    except UnicodeDecodeError:
        # Try other encodings
        try:
            content = raw_bytes.decode("gbk", errors="replace")
        except Exception:
            raise HTTPException(status_code=400, detail="文件编码无法识别，请使用 UTF-8 编码")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件解析失败: {e}")
        raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")

    if not content or not content.strip():
        raise HTTPException(status_code=400, detail="文件内容为空")

    # 构造 split 请求并复用分集逻辑
    split_request = ScriptSplitRequest(
        title=title,
        content=content,
        user_id="",  # 文件上传不绑定用户
    )
    result = await script_service.upload_and_split_script(split_request)

    elapsed = time.time() - t0
    logger.info(f"[API] POST /upload 完成 title={title} "
                f"episodes={result.get('total_episodes')} filename={filename} "
                f"size={len(content)} chars elapsed={elapsed:.1f}s")
    return result


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


async def _generate_outline_background(
    task_id: str, request: ScriptFromOutlineRequest, style: str,
    target_eps: int, full_context: str, plot_template, use_streaming: bool,
    llm=None, mock_mode: bool = False,
):
    """Background task: run outline generation via ScriptGenerationEngine."""
    from app.services.generation_engine import ScriptGenerationEngine
    from app.core.config import settings as _bg_settings
    from app.services.script_service import _task_set as _bg_task_set
    try:
        await _bg_task_set(task_id, {"status": "processing", "progress": 10, "title": request.title})
        engine = ScriptGenerationEngine(
            llm=llm if not mock_mode else None,
            mock_mode=mock_mode, config=_bg_settings,
        )
        await _bg_task_set(task_id, {"status": "processing", "stage": "framework", "progress": 20})
        result = await engine.generate_from_outline(
            outline_text=request.outline, style=style,
            target_episodes=target_eps, user_context=full_context,
        )
        episodes_data = result.get("episodes", [])
        await _bg_task_set(task_id, {
            "status": "completed", "progress": 100,
            "episodes": episodes_data,
            "total_episodes": len(episodes_data),
            "title": request.title,
        })
        logger.info(f"Background outline complete: task={task_id} episodes={len(episodes_data)}")
    except Exception as e:
        logger.error(f"Background outline generation failed task={task_id}: {e}")
        await _bg_task_set(task_id, {"status": "failed", "error": str(e)})


@router.post("/generate/from-outline", response_model=ScriptResponse)
async def generate_from_outline(
    request: ScriptFromOutlineRequest,
    background_tasks: BackgroundTasks,
    script_service: ScriptService = Depends(get_script_service)
):
    """从大纲/想法生成剧本 — 异步队列模式。返回 task_id，前端轮询状态。
    设置 stream=true 启用 SSE 流式输出。"""
    import asyncio as _asyncio
    from app.services.generation_engine import ScriptGenerationEngine
    from app.core.config import settings as app_settings

    outline_len = len(getattr(request, 'outline', '') or '')
    use_streaming = getattr(request, "stream", False) and settings.SSE_STREAMING_ENABLED
    logger.info(f"[API] POST /generate/from-outline title={request.title} "
                f"outline_len={outline_len} stream={use_streaming}")
    t0 = time.time()
    try:
        if not request.outline or not request.outline.strip():
            raise HTTPException(status_code=400, detail="想法/大纲内容不能为空")
        if not request.title or not request.title.strip():
            raise HTTPException(status_code=400, detail="剧本标题不能为空")

        if not script_service._initialized:
            await script_service.initialize()

        mock_mode = getattr(script_service, '_mock_mode', False)
        style = getattr(request, 'style', '') or app_settings.N2S_V2_DEFAULT_STYLE

        # ── 情节结构模板: 自动匹配最佳模板 ──
        from app.services.plot_templates import match_template
        plot_template = match_template(
            style=style,
            theme=getattr(request, 'theme', ''),
            outline=getattr(request, 'outline', ''),
        )
        template_context = ""
        plot_target_eps = 0
        if plot_template:
            template_context = plot_template.to_prompt_context()
            plot_target_eps = plot_template.total_episodes

        # ── 海外本土化 context ──
        target_locale = getattr(request, 'target_locale', 'zh-CN') or 'zh-CN'
        extra_context = ""
        if target_locale != 'zh-CN':
            from app.services.localization_service import ScriptLocalizationService
            loc_svc = ScriptLocalizationService(llm=None)
            extra_context = loc_svc.build_locale_system_prompt(target_locale=target_locale, style=style)

        # ── Fetch user preference profile ──
        user_context = ""
        user_id = getattr(request, 'user_id', '') or ''
        if user_id and user_id != 'anonymous':
            try:
                from app.services.user_preferences import get_user_preference_service
                pref_svc = await get_user_preference_service()
                db_session = getattr(script_service, '_db_session', None)
                profile = await pref_svc.get_profile(user_id, db_session)
                user_context = profile.to_prompt_context()
            except Exception as e:
                logger.debug(f"User preferences skipped: {e}")

        # Merge contexts
        full_context = template_context
        if user_context:
            full_context = f"{user_context}\n\n{full_context}" if full_context else user_context
        if extra_context:
            full_context = f"{full_context}\n\n{extra_context}" if full_context else extra_context

        # ── Parse episode count ──
        length_to_eps = {
            "超短篇": 3, "短篇": 10, "中篇": 25, "长篇": 60, "超长篇": 100,
        }
        import re as _re
        cn_num_map = {c: i for i, c in enumerate(
            ['', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十',
             '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十',
             '二十一', '二十二', '二十三', '二十四', '二十五', '二十六', '二十七', '二十八', '二十九', '三十',
             '三十一', '三十二', '三十三', '三十四', '三十五', '三十六', '三十七', '三十八', '三十九', '四十',
             '四十一', '四十二', '四十三', '四十四', '四十五', '四十六', '四十七', '四十八', '四十九', '五十',
             '五十一', '五十二', '五十三', '五十四', '五十五', '五十六', '五十七', '五十八', '五十九', '六十',
             '六十一', '六十二', '六十三', '六十四', '六十五', '六十六', '六十七', '六十八', '六十九', '七十',
             '七十一', '七十二', '七十三', '七十四', '七十五', '七十六', '七十七', '七十八', '七十九', '八十',
             '八十一', '八十二', '八十三', '八十四', '八十五', '八十六', '八十七', '八十八', '八十九', '九十',
             '九十一', '九十二', '九十三', '九十四', '九十五', '九十六', '九十七', '九十八', '九十九', '一百',
             '一百零一', '一百零二', '一百零三', '一百零四', '一百零五', '一百零六', '一百零七', '一百零八', '一百零九', '一百一十',
             '一百一十一', '一百一十二', '一百一十三', '一百一十四', '一百一十五', '一百一十六', '一百一十七', '一百一十八', '一百一十九', '一百二十'], start=0)}
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
        if plot_target_eps > 0:
            target_eps = plot_target_eps

        # ── Non-streaming: return task_id immediately, generate in background ──
        if not use_streaming:
            task_id = str(uuid.uuid4())
            logger.info(f"[API] 大纲转剧本任务已提交 task_id={task_id} target_eps={target_eps}")
            try:
                from app.models import GenerationTask, TaskStatus
                from app.core.database import AsyncSessionLocal
                async with AsyncSessionLocal() as db:
                    gen_task = GenerationTask(
                        task_id=task_id, status=TaskStatus.PROCESSING.value,
                        progress=5, start_time=time.time(),
                    )
                    db.add(gen_task)
                    await db.commit()
            except Exception:
                pass
            try:
                from app.services.task_worker import get_task_worker
                worker = await get_task_worker()
                if worker._queue is not None or hasattr(worker, '_consumer'):
                    await worker.enqueue(task_id, "from-outline",
                        request.dict() if hasattr(request, 'dict') else vars(request))
                    backend = "kafka"
                else:
                    raise RuntimeError("worker not started")
            except Exception as e:
                logger.info(f"Worker unavailable ({e}), using BackgroundTasks for {task_id}")
                background_tasks.add_task(
                    _generate_outline_background,
                    task_id, request, style, target_eps, full_context, plot_template, False,
                    script_service.llm, mock_mode,
                )
                backend = "background"
            return ScriptResponse(
                task_id=task_id, status="processing",
                message=f"Outline script generation started ({backend})",
                script=None,
            )

        # ── SSE streaming path below ──
        n2s_v2 = ScriptGenerationEngine(
            llm=script_service.llm if not mock_mode else None,
            mock_mode=mock_mode,
            config=app_settings,
        )

        # ── 情节结构模板: 自动匹配最佳模板 ──
        from app.services.plot_templates import match_template
        plot_template = match_template(
            style=style,
            theme=getattr(request, 'theme', ''),
            outline=getattr(request, 'outline', ''),
        )
        template_context = ""
        if plot_template:
            template_context = plot_template.to_prompt_context()
            target_eps = plot_template.total_episodes  # Override episode count to match template
            logger.info(f"[V2大纲] 情节模板匹配: {plot_template.genre_cn} ({plot_template.template_id}) "
                        f"episodes={target_eps}")

        # ── 海外本土化: 注入 locale-aware 上下文 ──
        target_locale = getattr(request, 'target_locale', 'zh-CN') or 'zh-CN'
        extra_context = ""
        if target_locale != 'zh-CN':
            from app.services.localization_service import ScriptLocalizationService
            loc_svc = ScriptLocalizationService(llm=None)
            extra_context = loc_svc.build_locale_system_prompt(
                target_locale=target_locale,
                style=style,
            )
            logger.info(f"[V2大纲] 海外本土化模式 locale={target_locale} "
                        f"context_len={len(extra_context)}")

        # Parse episode count for both paths
        length_to_eps = {
            "超短篇": 3, "短篇": 10, "中篇": 25, "长篇": 60, "超长篇": 100,
        }
        import re as _re
        cn_num_map = {c: i for i, c in enumerate(
            ['', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十',
             '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十',
             '二十一', '二十二', '二十三', '二十四', '二十五', '二十六', '二十七', '二十八', '二十九', '三十',
             '三十一', '三十二', '三十三', '三十四', '三十五', '三十六', '三十七', '三十八', '三十九', '四十',
             '四十一', '四十二', '四十三', '四十四', '四十五', '四十六', '四十七', '四十八', '四十九', '五十',
             '五十一', '五十二', '五十三', '五十四', '五十五', '五十六', '五十七', '五十八', '五十九', '六十',
             '六十一', '六十二', '六十三', '六十四', '六十五', '六十六', '六十七', '六十八', '六十九', '七十',
             '七十一', '七十二', '七十三', '七十四', '七十五', '七十六', '七十七', '七十八', '七十九', '八十',
             '八十一', '八十二', '八十三', '八十四', '八十五', '八十六', '八十七', '八十八', '八十九', '九十',
             '九十一', '九十二', '九十三', '九十四', '九十五', '九十六', '九十七', '九十八', '九十九', '一百',
             '一百零一', '一百零二', '一百零三', '一百零四', '一百零五', '一百零六', '一百零七', '一百零八', '一百零九', '一百一十',
             '一百一十一', '一百一十二', '一百一十三', '一百一十四', '一百一十五', '一百一十六', '一百一十七', '一百一十八', '一百一十九', '一百二十'], start=0)}
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
        # Auto-batch: split large requests into multiple passes via continue pipeline
        max_per_batch = 20
        if target_eps > max_per_batch:
            logger.info(f"Requested {target_eps} episodes > {max_per_batch} batch limit — "
                       f"will auto-chain via continue pipeline")

        # Fetch user preference profile for personalized generation
        user_context = ""
        user_id = getattr(request, 'user_id', '') or ''
        if user_id and user_id != 'anonymous':
            try:
                from app.services.user_preferences import get_user_preference_service
                pref_svc = await get_user_preference_service()
                # Use script_service's DB session for querying
                db_session = getattr(script_service, '_db_session', None)
                profile = await pref_svc.get_profile(user_id, db_session)
                user_context = profile.to_prompt_context()
                if user_context:
                    logger.info(f"User preferences loaded for {user_id}: {profile.total_scripts} scripts")
            except Exception as e:
                logger.debug(f"User preferences skipped: {e}")

        # ---- SSE streaming path ----
        if use_streaming:
            async def event_generator():
                async for sse_event in n2s_v2.generate_from_outline_sse(
                    outline_text=request.outline, style=style, target_episodes=target_eps,
                    user_context=full_context,
                ):
                    yield sse_event
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
            )

        # Merge locale context with user preferences
        # Merge: template context (highest priority) + user prefs + locale context
        full_context = template_context
        if user_context:
            full_context = f"{user_context}\n\n{full_context}" if full_context else user_context
        if extra_context:
            full_context = f"{full_context}\n\n{extra_context}" if full_context else extra_context

        # ---- Non-streaming path with auto-batching for large requests ----
        BATCH_SIZE = 20
        first_batch_target = min(target_eps, BATCH_SIZE)

        result = await _asyncio.wait_for(
            n2s_v2.generate_from_outline(
                outline_text=request.outline, style=style,
                target_episodes=first_batch_target,
                user_context=full_context,
            ),
            timeout=600
        )

        all_episodes = list(result.get("episodes") or [])
        all_storyboard = list(result.get("storyboard", []))
        story_framework_text = result.get("story_framework", "")
        characters = result.get("characters", [])
        prev_episodes = list(all_episodes)

        # Auto-chain remaining batches
        remaining = target_eps - len(all_episodes)
        batch_context = ""
        while remaining > 0:
            batch_size = min(remaining, BATCH_SIZE)
            start_ep = len(all_episodes) + 1
            logger.info(f"[Auto-batch] Continuing: {batch_size} more episodes (starting at ep {start_ep})")

            # Build context from recent episodes
            try:
                recent = prev_episodes[-10:]
                batch_context = await n2s_v2.outline.summarize_batch(recent, characters)
            except Exception as e:
                logger.warning(f"Batch context summarization failed: {e}")

            batch_result = await _asyncio.wait_for(
                n2s_v2.outline.continue_from(
                    story_framework=story_framework_text,
                    characters=characters,
                    style=style,
                    start_episode=start_ep,
                    additional_episodes=batch_size,
                    previous_context=batch_context,
                    previous_episodes=prev_episodes,
                ),
                timeout=600
            )

            new_eps = batch_result.get("episodes", [])
            new_sb = batch_result.get("storyboard", [])
            all_episodes.extend(new_eps)
            all_storyboard.extend(new_sb)
            prev_episodes = list(new_eps)
            remaining = target_eps - len(all_episodes)
            logger.info(f"[Auto-batch] Batch complete: {len(new_eps)} episodes, {remaining} remaining")

        # Build ShotEpisode-format storyboard from V2 pipeline data
        shot_episodes = script_service._build_shot_episodes(
            all_storyboard, all_episodes
        ) if all_storyboard else None

        # Track usage (fire-and-forget)
        from app.services.usage_tracker import track_llm_usage, estimate_tokens
        estimated_in = estimate_tokens(request.outline) * 2
        estimated_out = estimate_tokens(result.get("final_script", ""))
        user_id_str = str(getattr(request, 'user_id', '') or 'anonymous')
        _asyncio.ensure_future(track_llm_usage(
            user_id=user_id_str, model_name="deepseek-chat",
            tokens_in=estimated_in, tokens_out=estimated_out,
            call_count=len(all_episodes),
            duration_ms=int((time.time() - t0) * 1000),
            endpoint="/generate/from-outline",
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

        logger.info(f"[API] POST /generate/from-outline 完成 title={request.title} "
                    f"episodes={len(all_episodes)} "
                    f"storyboard_shots={len(all_storyboard)} "
                    f"耗时={time.time()-t0:.1f}s")

        # Clean episode content: strip beat-sheet block for frontend display
        import re as _re
        _clean_pattern = _re.compile(
            r'【分集标题】.*?\n|【节拍表】.*?(?=【场景地点】|【场景)|$',
            _re.DOTALL,
        )
        for _ep in all_episodes:
            raw = _ep.get("content", "")
            _ep["content"] = _clean_pattern.sub("", raw, count=2).strip()

        return {
            "script_id": 0, "title": request.title,
            "episodes": all_episodes, "total_episodes": len(all_episodes),
            "storyboard": shot_episodes,
            "story_framework": story_framework_text,
        }
    except _asyncio.TimeoutError:
        logger.error(f"[API] POST /generate/from-outline 超时 title={request.title} (600s)")
        raise HTTPException(status_code=504, detail="AI 生成超时（10分钟），请缩短输入内容后重试")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] POST /generate/from-outline 异常 title={request.title}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Export endpoints ──

from app.services.export_service import ExportService, ExportFormat, ExportTarget

_export_service = ExportService()


@router.post("/{script_id}/export")
async def export_script(
    script_id: int,
    target: str = "all",
    format: str = "auto",
    script_service: ScriptService = Depends(get_script_service),
):
    """导出剧本为下游 AI 成片工具兼容格式。

    Args:
        script_id: 剧本 ID
        target: 目标平台 — 'xiaoyunque' | 'libtv' | 'jurilu' | 'all'（默认）
        format: 导出格式 — 'raw_text' | 'structured_json' | 'storyboard_json' | 'auto'（默认，自动选最佳格式）
    """
    logger.info(f"[API] POST /{script_id}/export target={target} format={format}")
    t0 = time.time()

    try:
        script = await script_service.get_script(script_id)
        if not script:
            raise HTTPException(status_code=404, detail="Script not found")

        script_content = script.get("content", "")
        title = script.get("title", "")
        characters = json.loads(script.get("characters", "[]") or "[]") if isinstance(script.get("characters"), str) else (script.get("characters") or [])
        episodes = script.get("episodes", [])

        if target == "all":
            results = _export_service.export_all_formats(
                script_content, title=title, characters=characters, episodes=episodes
            )
            elapsed = time.time() - t0
            logger.info(f"[API] POST /{script_id}/export all platforms done "
                        f"chars={len(script_content)} elapsed={elapsed:.1f}s")
            return {
                "script_id": script_id,
                "title": title,
                "exports": {k: v.to_dict() for k, v in results.items()},
                "elapsed_ms": int(elapsed * 1000),
            }
        else:
            export_target = ExportTarget(target)
            if format == "auto":
                # Auto-select best format per platform
                format_map = {
                    ExportTarget.XIAOYUNQUE: ExportFormat.RAW_TEXT,
                    ExportTarget.LIBTV: ExportFormat.STORYBOARD_JSON,
                    ExportTarget.JURILU: ExportFormat.RAW_TEXT,
                }
                export_format = format_map[export_target]
            else:
                export_format = ExportFormat(format)

            result = _export_service.export(
                script_content, export_target, export_format,
                title=title, characters=characters, episodes=episodes,
            )
            elapsed = time.time() - t0
            logger.info(f"[API] POST /{script_id}/export target={target} format={export_format.value} "
                        f"chars={len(script_content)} warnings={len(result.warnings)} elapsed={elapsed:.1f}s")
            return {
                "script_id": script_id,
                "title": title,
                "export": result.to_dict(),
                "elapsed_ms": int(elapsed * 1000),
            }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] POST /{script_id}/export 异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Multi-Version Generation ──

@router.post("/generate/multi-version")
async def generate_multi_version(
    request: ScriptFromOutlineRequest,
    script_service: ScriptService = Depends(get_script_service),
):
    """生成 3 个版本的剧本（不同叙事角度），自动对比评分，返回最佳版本。

    对标: Sudowrite Brainstorm + QualityJudge A/B 对比。

    三个版本:
    - A: 标准短剧风格（快节奏，强钩子，每集结尾悬念）
    - B: 情感向（更深的人物塑造，情感层次丰富）
    - C: 反转向（更多 plot twist，出人意料的转折）

    Returns:
        {
            versions: [{version, script, score, strengths, weaknesses}],
            winner: {...},
            comparison: CompareReport
        }
    """
    import asyncio as _asyncio
    from app.services.generation_engine import ScriptGenerationEngine
    from app.core.config import settings as app_settings
    from app.services.quality_judge import QualityJudge

    t0 = time.time()
    logger.info(f"[API] POST /generate/multi-version title={request.title} "
                f"outline_len={len(getattr(request, 'outline', '') or '')}")

    try:
        await script_service.initialize()
        mock_mode = getattr(script_service, '_mock_mode', False)

        style = getattr(request, 'style', '') or app_settings.N2S_V2_DEFAULT_STYLE
        outline = getattr(request, 'outline', '')

        # Three narrative angles
        angles = [
            {
                "version": "A",
                "label": "标准风格",
                "angle_prompt": (
                    "采用标准短剧风格: 快节奏、每集结尾强钩子、3秒一反转、10秒一记忆点。"
                    "对话简洁有力，场景转换快速。付费点位置卡得精准。"
                ),
            },
            {
                "version": "B",
                "label": "情感向",
                "angle_prompt": (
                    "采用情感向风格: 更深的角色塑造、丰富的情感层次、让观众产生共情。"
                    "牺牲一些速度换取角色的真实感和成长弧光。对白更细腻。"
                ),
            },
            {
                "version": "C",
                "label": "反转向",
                "angle_prompt": (
                    "采用高反转风格: 大量 plot twist、出人意料的转折、让观众不断惊呼'原来是这样'。"
                    "每个反转都要有逻辑铺垫但不能太明显。节奏可以稍慢但每个反转必须有冲击力。"
                ),
            },
        ]

        # Generate all 3 versions concurrently
        async def generate_version(angle: dict) -> dict:
            logger.info(f"[multi-version] Generating version {angle['version']} ({angle['label']})...")
            v_t0 = time.time()

            n2s = ScriptGenerationEngine(
                llm=script_service.llm if not mock_mode else None,
                mock_mode=mock_mode, config=app_settings,
            )

            # Inject angle into outline
            angled_outline = f"{outline}\n\n【叙事角度要求】{angle['angle_prompt']}"

            result = await n2s.generate_from_outline(
                outline_text=angled_outline,
                style=style,
                target_episodes=10,
            )

            elapsed = time.time() - v_t0
            logger.info(f"[multi-version] Version {angle['version']} done ({elapsed:.1f}s)")

            return {
                "version": angle["version"],
                "label": angle["label"],
                "script_content": result.get("final_script", ""),
                "episodes": result.get("episodes", []),
                "characters": result.get("entities", {}).get("characters", []),
                "elapsed_ms": int(elapsed * 1000),
            }

        versions = await _asyncio.gather(
            *[generate_version(a) for a in angles], return_exceptions=True
        )

        # Filter out failed versions
        valid_versions = [v for v in versions if not isinstance(v, Exception) and v.get("script_content")]

        if not valid_versions:
            raise HTTPException(status_code=500, detail="All versions failed to generate")

        # QualityJudge scoring
        judge = QualityJudge(
            script_service.llm if not mock_mode else None,
            enabled=not mock_mode,
        )

        scored_versions = []
        for v in valid_versions:
            if not mock_mode:
                report = await judge.judge_script(
                    content=v["script_content"],
                    title=request.title,
                    style=style,
                    max_chars=6000,
                )
                v["score"] = report.total_score
                v["strengths"] = report.strengths
                v["weaknesses"] = report.weaknesses
                v["suggestions"] = report.suggestions
            else:
                v["score"] = 75
                v["strengths"] = ["mock mode"]
                v["weaknesses"] = []
                v["suggestions"] = ""
            scored_versions.append(v)

        # Sort by score
        scored_versions.sort(key=lambda v: v["score"], reverse=True)
        winner = scored_versions[0]

        # Pairwise comparison (winner vs runner-up)
        comparison = None
        if len(scored_versions) >= 2 and not mock_mode:
            runner_up = scored_versions[1]
            comparison = await judge.compare_scripts(
                script_a=winner["script_content"],
                script_b=runner_up["script_content"],
                label_a=f"Version {winner['version']} ({winner['label']})",
                label_b=f"Version {runner_up['version']} ({runner_up['label']})",
                max_chars=4000,
            )

        elapsed = time.time() - t0
        logger.info(f"[API] POST /generate/multi-version done: "
                    f"{len(scored_versions)} versions, winner={winner['version']}, "
                    f"elapsed={elapsed:.1f}s")

        return {
            "success": True,
            "data": {
                "title": request.title,
                "versions": scored_versions,
                "winner": {
                    "version": winner["version"],
                    "label": winner["label"],
                    "score": winner["score"],
                    "strengths": winner["strengths"],
                },
                "comparison": {
                    "winner": comparison.winner if comparison else winner["version"],
                    "confidence": comparison.confidence if comparison else 1.0,
                    "score_a": comparison.score_a if comparison else winner["score"],
                    "score_b": comparison.score_b if comparison else (scored_versions[1]["score"] if len(scored_versions) > 1 else 0),
                    "key_differences": comparison.key_differences if comparison else [],
                    "verdict_summary": comparison.verdict_summary if comparison else "",
                } if comparison else None,
                "elapsed_ms": int(elapsed * 1000),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] POST /generate/multi-version 异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Intent Mining (Conversational Guidance) ──


class IntentQuestion(BaseModel):
    id: str
    question: str
    options: List[str] = []


class IntentMiningResponse(BaseModel):
    enriched_outline: str = ""           # 挖掘后的丰富大纲，可直接用于生成
    questions: List[IntentQuestion] = []  # 需要用户澄清的问题
    detected_genre: str = ""             # 检测到的题材
    suggested_style: str = ""            # 建议的风格
    suggested_length: str = ""           # 建议的篇幅


@router.post("/generate/intent", response_model=IntentMiningResponse)
async def mine_intent(
    data: dict,
    script_service: ScriptService = Depends(get_script_service),
):
    """对话式意图挖掘 —— 在生成剧本前，先理解用户真正想要什么。

    请求体:
      {
        "idea": "帮我写个霸总故事",
        "style": "浪漫喜剧",       // 可选，用户已选的风格
        "theme": "爱情",            // 可选
        "length": "短篇"            // 可选
      }

    返回:
      {
        "enriched_outline": "...",   // 如果用户想法足够清晰，直接返回丰富后的大纲
        "questions": [               // 如果需要澄清，返回问题列表
          {id:"爽点", question:"这个故事的爽点是什么？", options:["身份反转","打脸虐渣","甜宠治愈"]}
        ],
        "detected_genre": "霸道总裁",
        "suggested_style": "浪漫喜剧"
      }

    用户回答后，将 answers 合并到下一轮调用中:
      POST /generate/intent  {idea: "...", answers: {爽点: "打脸虐渣", ...}}
    """
    if not script_service._initialized:
        await script_service.initialize()

    idea = data.get("idea", "").strip()
    if not idea:
        raise HTTPException(status_code=400, detail="想法不能为空")

    answers = data.get("answers", {})
    style = data.get("style", "")
    theme = data.get("theme", "")
    length = data.get("length", "")

    mock_mode = getattr(script_service, '_mock_mode', False)

    try:
        structured_llm = script_service.llm.with_structured_output(
            IntentMiningResponse, method="json_mode"
        )

        answers_text = ""
        if answers:
            answers_text = "\n".join([f"- {k}: {v}" for k, v in answers.items()])

        messages = [
            SystemMessage(content="""你是资深短剧策划。用户给你一个模糊的想法，你需要：
1. 判断想法是否足够清晰可以开始创作
2. 如果不够清晰，提出2-4个关键问题来挖掘用户的真实意图
3. 如果已有用户回答，将其整合为一个更丰富的故事大纲

关键维度:
- 爽点/核心卖点: 观众为什么想看？（身份反转/打脸虐渣/甜宠治愈/悬疑揭秘/复仇逆袭）
- 女主类型: （傻白甜逆袭/御姐强势/扮猪吃虎/清冷美人/普通女孩）
- 冲突类型: （感情纠葛/商战博弈/身份谎言/家族恩怨/生存危机）
- 反转密度: （每集小反转/每3集大反转/全程高能）

输出 JSON:
- enriched_outline: 整合后的丰富大纲（如果已有足够信息）或空字符串
- questions: 需要澄清的问题列表，每个问题给出2-4个选项
- detected_genre: 检测到的题材
- suggested_style/style_advice: 建议的风格和篇幅"""),
            HumanMessage(content=f"""用户想法: {idea}
已选风格: {style or '未指定'}
已选主题: {theme or '未指定'}
已选篇幅: {length or '未指定'}
用户回答: {answers_text or '无'}

请分析并返回结构化的问题或丰富后的大纲。"""),
        ]

        if mock_mode:
            return IntentMiningResponse(
                enriched_outline="",
                questions=[
                    IntentQuestion(id="爽点", question="这个故事的爽点是什么？", options=["身份反转", "打脸虐渣", "甜宠治愈", "强强对抗"]),
                    IntentQuestion(id="女主类型", question="女主角是什么类型？", options=["傻白甜逆袭", "御姐强势", "扮猪吃虎", "清冷美人"]),
                ],
                detected_genre="霸道总裁",
                suggested_style=style or "浪漫喜剧",
                suggested_length=length or "短篇",
            )

        result: IntentMiningResponse = await structured_llm.ainvoke(
            messages, config={"timeout": 30}
        )

        logger.info(
            f"[Intent] idea_len={len(idea)} enriched={len(result.enriched_outline)} "
            f"questions={len(result.questions)} genre={result.detected_genre}"
        )
        return result

    except Exception as e:
        logger.warning(f"[Intent] mining failed: {e}")
        return IntentMiningResponse(
            enriched_outline=idea,
            questions=[],
            detected_genre="",
            suggested_style=style,
            suggested_length=length,
        )

@router.post("/preferences/version-choice")
async def record_version_choice(data: dict):
    """记录用户在多版本对比中选择了哪个版本。

    请求体:
      {
        "user_id": "xxx",
        "chosen_version": "A",               // 用户选择的版本
        "versions": [                         // 全部 3 个版本（含分数）
          {"version": "A", "label": "标准风格", "score": 85},
          {"version": "B", "label": "情感向", "score": 72},
          {"version": "C", "label": "反转向", "score": 68}
        ],
        "style": "浪漫喜剧",                   // 本次生成的风格
        "theme": "爱情",                       // 本次生成的主题
        "auto_choice": false                  // 是用户手动选还是接受了推荐
      }

    后端通过 EMA 指数移动平均更新用户的叙事角度偏好权重。
    积累的数据后续用于自动推荐最佳生成角度。
    """
    user_id = data.get("user_id", "")
    chosen = data.get("chosen_version", "")
    versions = data.get("versions", [])
    style = data.get("style", "")
    theme = data.get("theme", "")
    auto_choice = data.get("auto_choice", False)

    if not user_id or user_id == "anonymous":
        return {"success": False, "message": "anonymous user — preference not recorded"}

    if chosen not in ("A", "B", "C"):
        raise HTTPException(status_code=400, detail="chosen_version must be A, B, or C")

    try:
        from app.services.user_preferences import get_user_preference_service
        from app.core.database import AsyncSessionLocal

        pref_svc = await get_user_preference_service()

        async with AsyncSessionLocal() as db:
            # Use record_feedback — updates in-memory profile (cached)
            # Angle preferences persist across requests within the same process;
            # they're rebuilt from script history on cold start.
            await pref_svc.record_feedback(
                user_id=user_id,
                feedback={
                    "action": "version_chosen",
                    "chosen_version": chosen,
                    "all_versions": versions,
                    "style": style,
                    "theme": theme,
                    "length": data.get("length", "短篇"),
                },
                db_session=db,
            )

            profile = await pref_svc.get_profile(user_id, db)

            logger.info(
                f"User {user_id}: version choice recorded → {chosen} "
                f"(auto={auto_choice}) "
                f"angles={profile.angle_preferences}"
            )

            return {
                "success": True,
                "message": f"Version choice '{chosen}' recorded",
                "angles": profile.angle_preferences,
                "preferred_angle": profile.infer_angle_preference(),
                "total_scripts": profile.total_scripts,
            }
    except Exception as e:
        logger.warning(f"Failed to record version choice: {e}")
        return {"success": False, "message": str(e)}


@router.get("/preferences/angles")
async def get_angle_preferences(user_id: str = ""):
    """查询用户的叙事角度偏好积累数据。

    返回:
      {
        "angles": {"standard": 0.6, "emotional": 0.3, "twist": 0.1},
        "preferred_angle": "standard",
        "total_choices": 12,
        "angle_history": [
          {"angle": "standard", "label": "标准风格", "count": 7},
          {"angle": "emotional", "label": "情感向", "count": 3},
          {"angle": "twist", "label": "反转向", "count": 2}
        ]
      }
    """
    if not user_id or user_id == "anonymous":
        return {"angles": {}, "preferred_angle": "standard", "total_choices": 0, "angle_history": []}

    try:
        from app.services.user_preferences import get_user_preference_service
        from app.core.database import AsyncSessionLocal

        pref_svc = await get_user_preference_service()
        async with AsyncSessionLocal() as db:
            profile = await pref_svc.get_profile(user_id, db)

            angle_labels = {
                "standard": "标准风格",
                "emotional": "情感向",
                "twist": "反转向",
            }

            # Build history from raw counts
            angle_history = []
            for angle, label in angle_labels.items():
                weight = profile.angle_preferences.get(angle, 0)
                if weight > 0:
                    angle_history.append({
                        "angle": angle,
                        "label": label,
                        "score": round(weight * 100, 0),
                    })
            angle_history.sort(key=lambda x: x["score"], reverse=True)

            return {
                "angles": profile.angle_preferences,
                "preferred_angle": profile.infer_angle_preference(),
                "total_choices": profile.total_scripts,
                "angle_history": angle_history,
            }
    except Exception as e:
        logger.warning(f"Failed to get angle preferences: {e}")
        return {"angles": {}, "preferred_angle": "standard", "total_choices": 0, "angle_history": []}


# ── Localization endpoints ──

@router.get("/markets")
async def list_markets():
    """列出所有支持的海外本土化市场"""
    from app.services.localization_service import ScriptLocalizationService
    markets = ScriptLocalizationService.list_markets()
    return {"success": True, "data": markets}


@router.get("/markets/{locale}")
async def get_market_info(locale: str):
    """获取指定市场的详细信息"""
    from app.services.localization_service import ScriptLocalizationService
    try:
        info = ScriptLocalizationService().get_market_info(locale)
        return {"success": True, "data": info}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Market not found: {locale}")


@router.post("/localize")
async def localize_script(data: dict, script_service: ScriptService = Depends(get_script_service)):
    """将剧本本土化适配到目标市场。

    Args (JSON body):
        script_content: 原始剧本内容
        target_locale: 目标市场 (en-US, ar-SA, tr-TR, ja-JP, ko-KR, es-MX, th-TH)
        source_locale: 源市场 (default: zh-CN)
        title: 剧本标题
        style: 原始风格
        adaptation_level: "light" (仅文化符号替换) | "full" (完整文化适配, default)
        preserve_plot: 是否保留原情节 (default: true)
        output_language: 输出语言 (空=使用目标市场语言)
    """
    from app.services.localization_service import ScriptLocalizationService, LocalizationRequest

    t0 = time.time()
    logger.info(f"[API] POST /localize target={data.get('target_locale')} level={data.get('adaptation_level', 'full')} chars={len(data.get('script_content', ''))}")

    try:
        await script_service.initialize()
        mock_mode = getattr(script_service, '_mock_mode', False)
        target_locale_val = data.get("target_locale", "en-US")

        # Locale-aware LLM routing: prefer Anthropic for English markets
        from app.utils.model_router import create_llm_for_locale
        llm = create_llm_for_locale(target_locale=target_locale_val) if not mock_mode else None

        svc = ScriptLocalizationService(llm=llm)
        req = LocalizationRequest(
            script_content=data.get("script_content", ""),
            source_locale=data.get("source_locale", "zh-CN"),
            target_locale=data.get("target_locale", "en-US"),
            title=data.get("title", ""),
            style=data.get("style", ""),
            adaptation_level=data.get("adaptation_level", "full"),
            preserve_plot=data.get("preserve_plot", True),
            preserve_episode_count=data.get("preserve_episode_count", True),
            output_language=data.get("output_language", ""),
        )

        if req.adaptation_level == "light":
            result = await svc.localize_light(req)
        else:
            result = await svc.localize(req)

        elapsed = time.time() - t0
        logger.info(f"[API] POST /localize done target={req.target_locale} "
                    f"success={result.success} elapsed={elapsed:.1f}s")
        return {
            "success": result.success,
            "data": {
                "localized_script": result.localized_script,
                "title_localized": result.title_localized,
                "source_locale": result.source_locale,
                "target_locale": result.target_locale,
                "market_name": result.market_name,
                "language": result.language,
                "changes_summary": result.changes_summary,
                "character_mappings": result.character_mappings,
                "adaptation_notes": result.adaptation_notes,
                "elapsed_ms": result.elapsed_ms,
            },
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[API] POST /localize 异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Collaboration endpoints ──

@router.post("/{script_id}/share")
async def share_script(
    script_id: int,
    data: dict,
    script_service: ScriptService = Depends(get_script_service),
):
    """分享剧本给其他用户或生成公开链接。

    Body:
        shared_with: 被分享者 user_id（空=生成公开链接）
        permission: view / comment / edit (default: view)
        ttl_hours: 公开链接有效期，小时 (default: 72)
    """
    from app.services.collaboration_service import get_collaboration_service, SharePermission

    collab = get_collaboration_service()

    script = await script_service.get_script(script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")

    link = collab.share_script(
        script_id=script_id,
        shared_by=data.get("shared_by", "user"),
        shared_with=data.get("shared_with", ""),
        permission=data.get("permission", SharePermission.VIEW),
        ttl_hours=data.get("ttl_hours", 72),
    )
    logger.info(f"[API] POST /{script_id}/share token={link.token} permission={link.permission}")
    return {"success": True, "data": link.to_dict()}


@router.get("/{script_id}/shares")
async def list_shares(script_id: int):
    """列出剧本的所有分享链接"""
    from app.services.collaboration_service import get_collaboration_service
    collab = get_collaboration_service()
    shares = collab.list_shares(script_id)
    return {"success": True, "data": [s.to_dict() for s in shares]}


@router.delete("/{script_id}/share/{token}")
async def revoke_share(script_id: int, token: str):
    """撤销分享链接"""
    from app.services.collaboration_service import get_collaboration_service
    collab = get_collaboration_service()
    ok = collab.revoke_share(token)
    return {"success": ok}


@router.post("/{script_id}/annotations")
async def add_annotation(script_id: int, data: dict):
    """添加剧本批注

    Body:
        user_id: 批注者
        content: 批注内容
        episode_number: 批注在哪一集 (default: 0=全局)
        position: {"line": 42, "char_offset": 10}
        annotation_type: note / suggestion / issue / praise (default: note)
    """
    from app.services.collaboration_service import get_collaboration_service
    collab = get_collaboration_service()
    ann = collab.add_annotation(
        script_id=script_id,
        user_id=data.get("user_id", "anonymous"),
        content=data.get("content", ""),
        episode_number=data.get("episode_number", 0),
        position=data.get("position"),
        annotation_type=data.get("annotation_type", "note"),
    )
    logger.info(f"[API] POST /{script_id}/annotations id={ann.annotation_id}")
    return {"success": True, "data": ann.to_dict()}


@router.get("/{script_id}/annotations")
async def list_annotations(
    script_id: int,
    episode_number: Optional[int] = None,
    resolved: Optional[bool] = None,
):
    """列出剧本批注"""
    from app.services.collaboration_service import get_collaboration_service
    collab = get_collaboration_service()
    annotations = collab.list_annotations(script_id, episode_number, resolved)
    summary = collab.get_annotations_summary(script_id)
    return {"success": True, "data": [a.to_dict() for a in annotations], "summary": summary}


@router.post("/{script_id}/annotations/{annotation_id}/reply")
async def reply_annotation(script_id: int, annotation_id: str, data: dict):
    """回复批注"""
    from app.services.collaboration_service import get_collaboration_service
    collab = get_collaboration_service()
    ok = collab.reply_annotation(annotation_id, data.get("user_id", ""), data.get("content", ""))
    return {"success": ok}


@router.post("/{script_id}/annotations/{annotation_id}/resolve")
async def resolve_annotation(script_id: int, annotation_id: str, data: dict):
    """标记批注为已解决"""
    from app.services.collaboration_service import get_collaboration_service
    collab = get_collaboration_service()
    ok = collab.resolve_annotation(annotation_id, data.get("resolved_by", ""))
    return {"success": ok}


@router.get("/{script_id}/collaborators")
async def list_collaborators(script_id: int):
    """列出剧本协作者"""
    from app.services.collaboration_service import get_collaboration_service
    collab = get_collaboration_service()
    users = collab.get_script_collaborators(script_id)
    return {"success": True, "data": users}
