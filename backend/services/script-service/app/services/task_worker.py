"""
Kafka-backed AI task worker — consumes generation tasks from queue.

Flow:
  API endpoint → KafkaQueue.enqueue(task) → return task_id
  TaskWorker.consume() → dequeue → execute pipeline → Redis task status

Falls back to in-memory queue when Kafka is unavailable (dev mode).
"""
import asyncio
import json
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)


class TaskWorker:
    """Consumer worker that processes AI generation tasks from a queue.

    Supports two backends via `shared/python/task_queue.py`:
      - memory: In-process async queue (dev/single-node)
      - kafka:  Kafka consumer group (production, multi-pod)
    """

    def __init__(self, script_service=None, backend: str = "memory"):
        self._script_service = script_service
        self._backend_name = backend
        self._queue = None
        self._running = False
        self._tasks_processed = 0

    @property
    def tasks_processed(self) -> int:
        return self._tasks_processed

    # ── Start ──

    async def start(self, script_service, bootstrap_servers: str = "kafka:9092",
                    consumer_group: str = "ai-workers-script",
                    concurrency: int = 3):
        """Start the consumer loop.

        Args:
            script_service: ScriptService instance (for pipeline execution).
            bootstrap_servers: Kafka bootstrap servers.
            consumer_group: Kafka consumer group ID.
            concurrency: Max concurrent task processing.
        """
        self._script_service = script_service
        await script_service.initialize()

        if self._backend_name == "kafka":
            await self._start_kafka(bootstrap_servers, consumer_group, concurrency)
        else:
            await self._start_memory(concurrency)

    async def _start_kafka(self, bootstrap_servers: str, consumer_group: str,
                           concurrency: int):
        """Start Kafka consumer using shared KafkaQueue abstraction."""
        # Use shared KafkaQueue for both enqueue (producer) and consume
        try:
            from app.services.task_queue import KafkaQueue
        except ImportError:
            import sys, os as _os
            shared_path = _os.path.join(_os.path.dirname(__file__), '..', '..', '..', 'shared', 'python')
            if shared_path not in sys.path:
                sys.path.insert(0, _os.path.abspath(shared_path))
            from task_queue import KafkaQueue

        try:
            self._queue = KafkaQueue(
                bootstrap_servers=bootstrap_servers,
                group_id=consumer_group,
            )
            # Start consumer loop
            await self._queue.start_consumer(
                queue_name="script",
                handler=self._execute_task,
                concurrency=concurrency,
            )
            # Store queue ref for enqueue
            self._running = True
            logger.info(f"TaskWorker: Kafka consumer started "
                        f"(topic=ai-tasks-script, group={consumer_group})")
        except ImportError:
            logger.warning("aiokafka not installed — falling back to memory queue")
            await self._start_memory(concurrency)
        except Exception as e:
            logger.warning(f"Kafka consumer start failed ({e}) — falling back to memory queue")
            await self._start_memory(concurrency)

    async def _start_memory(self, concurrency: int):
        """Start in-memory queue consumer."""
        # task_queue.py is in shared/python, copied into app/services/ by Dockerfile
        try:
            from app.services.task_queue import MemoryQueue, Task as TQTask
        except ImportError:
            # Fallback: try relative import for local dev
            import sys
            import os as _os
            shared_path = _os.path.join(_os.path.dirname(__file__), '..', '..', '..', 'shared', 'python')
            if shared_path not in sys.path:
                sys.path.insert(0, _os.path.abspath(shared_path))
            from task_queue import MemoryQueue, Task as TQTask

        self._queue = MemoryQueue()
        self._running = True
        sem = asyncio.Semaphore(concurrency)

        async def _loop():
            while self._running:
                task = await self._queue.dequeue("ai-tasks-script", timeout=1.0)
                if task is None:
                    continue
                async with sem:
                    payload = task.to_dict() if hasattr(task, 'to_dict') else task
                    await self._execute_task(payload)

        asyncio.create_task(_loop())
        logger.info("TaskWorker: memory queue consumer started")

    # ── Enqueue (called by API endpoints) ──

    async def enqueue(self, task_id: str, task_type: str,
                      request_data: dict) -> str:
        """Enqueue a generation task. Called by API handlers.

        Returns task_id immediately — consumer processes asynchronously.
        """
        from app.services.task_queue import Task as TQTask

        task = TQTask(
            task_id=task_id,
            queue_name="script",
            payload={"task_type": task_type, "request": request_data, "enqueued_at": time.time()},
        )

        if self._queue is not None:
            await self._queue.enqueue(task)
            logger.info(f"TaskWorker: enqueued {task_id} ({task_type}) → {self._backend_name}")
        else:
            # Queue not started yet — buffer locally and start memory fallback
            logger.warning(f"TaskWorker: queue not started, buffering {task_id} in memory")
            await self._start_memory(concurrency=3)
            await self._queue.enqueue(task)

        return task_id

    # ── Task execution ──

    async def _execute_task(self, task_data: dict):
        """Execute a single generation task. Called by consumer loop."""
        task_id = task_data.get("task_id", "unknown")
        task_type = task_data.get("task_type", "")
        request = task_data.get("request", {})
        enqueued_at = task_data.get("enqueued_at", time.time())

        wait_ms = int((time.time() - enqueued_at) * 1000)
        logger.info(f"TaskWorker: executing {task_id} ({task_type}) "
                    f"queue_wait={wait_ms}ms")

        from app.services.script_service import _task_set

        try:
            if task_type == "from-novel":
                await self._execute_novel(task_id, request)
            elif task_type == "from-outline":
                await self._execute_outline(task_id, request)
            else:
                raise ValueError(f"Unknown task type: {task_type}")

            self._tasks_processed += 1
            logger.info(f"TaskWorker: completed {task_id} (total: {self._tasks_processed})")

        except Exception as e:
            self._tasks_processed += 1
            logger.error(f"TaskWorker: failed {task_id}: {e}")
            await _task_set(task_id, {
                "status": "failed", "error": str(e),
                "progress": 0,
            })

    async def _execute_novel(self, task_id: str, request: dict):
        """Execute novel-to-script V2 pipeline."""
        from app.services.script_service import _task_set
        from app.core.database import AsyncSessionLocal
        from app.models import Script, GenerationTask, TaskStatus, ScriptStatus
        from app.core.config import settings as app_settings
        from app.services.generation_engine import ScriptGenerationEngine
        from sqlalchemy import select
        import json as _json

        svc = self._script_service
        novel_content = request.get("novel_content", "")
        style = request.get("style", "") or app_settings.N2S_V2_DEFAULT_STYLE

        await _task_set(task_id, {
            "status": "processing", "progress": 5,
            "title": request.get("title", ""), "stage": "初始化",
        })

        n2s_v2 = ScriptGenerationEngine(
            llm=svc.ai_service.llm,
            mock_mode=getattr(svc.ai_service, '_mock_mode', False),
            config=app_settings,
        )

        async def progress_callback(pct: int, stage: str):
            await _task_set(task_id, {
                "status": "processing", "progress": pct,
                "title": request.get("title", ""), "stage": stage,
            })

        t0 = time.time()
        result = await n2s_v2.generate_from_novel(
            novel_text=novel_content,
            style=style,
            progress_callback=progress_callback,
        )

        final_script = result.get("final_script", "")
        episodes = result.get("episodes") or svc._split_content_to_episodes(final_script)
        entities = result.get("entities", {})
        storyboard_data = result.get("storyboard", [])

        # Persist to DB
        async with AsyncSessionLocal() as db:
            script = Script(
                task_id=task_id,
                title=request.get("title", ""),
                content=final_script,
                episodes=episodes,
                theme=request.get("theme", ""),
                length=request.get("length", "短篇"),
                style=style,
                setting=request.get("setting", ""),
                characters=_json.dumps(entities.get("characters", []), ensure_ascii=False),
                source_type="novel",
                source_content=novel_content[:500],
                status=ScriptStatus.COMPLETED.value,
                user_id=str(request.get("user_id", "")),
                pipeline_version="v2",
                storyboard=storyboard_data if storyboard_data else None,
                character_graph=result.get("character_graph"),
                workflow_metadata={
                    "pipeline": "v2_rag_kafka_worker",
                    "stages": result.get("stages", {}),
                },
                analysis_result={
                    "events": [],
                    "locations": entities.get("locations", []),
                    "props": entities.get("props", []),
                },
            )
            db.add(script)
            await db.flush()

            task = await db.get(GenerationTask, task_id)
            if task:
                task.status = TaskStatus.COMPLETED.value
                task.progress = 100
                task.script_id = script.id
                task.end_time = time.time()
                task.duration = task.end_time - t0
            await db.commit()

        await _task_set(task_id, {
            "status": "completed", "progress": 100,
            "script_id": script.id,
            "title": request.get("title", ""),
        })

        logger.info(f"TaskWorker: novel {task_id} → script_id={script.id} "
                    f"{len(episodes)}eps elapsed={time.time()-t0:.1f}s")

    async def _execute_outline(self, task_id: str, request: dict):
        """Execute outline-to-script V2 pipeline."""
        from app.services.script_service import _task_set
        from app.core.database import AsyncSessionLocal
        from app.models import Script, GenerationTask, TaskStatus, ScriptStatus
        from app.core.config import settings as app_settings
        from app.services.generation_engine import ScriptGenerationEngine
        from sqlalchemy import select
        import json as _json

        svc = self._script_service
        outline = request.get("outline", "")
        style = request.get("style", "") or app_settings.N2S_V2_DEFAULT_STYLE

        # Parse target episodes
        length_to_eps = {"超短篇": 3, "短篇": 10, "中篇": 25, "长篇": 60}
        target_eps = length_to_eps.get(request.get("length", "短篇"), 10)

        await _task_set(task_id, {
            "status": "processing", "progress": 5,
            "title": request.get("title", ""), "stage": "初始化",
        })

        n2s_v2 = ScriptGenerationEngine(
            llm=svc.ai_service.llm,
            mock_mode=getattr(svc.ai_service, '_mock_mode', False),
            config=app_settings,
        )

        async def progress_callback(pct: int, stage: str):
            await _task_set(task_id, {
                "status": "processing", "progress": pct,
                "title": request.get("title", ""), "stage": stage,
            })

        t0 = time.time()
        result = await n2s_v2.generate_from_outline(
            outline_text=outline,
            style=style,
            target_episodes=target_eps,
            progress_callback=progress_callback,
        )

        final_script = result.get("final_script", "")
        episodes = result.get("episodes") or svc._split_content_to_episodes(final_script)
        entities = result.get("entities", {})
        storyboard_data = result.get("storyboard", [])

        async with AsyncSessionLocal() as db:
            script = Script(
                task_id=task_id,
                title=request.get("title", ""),
                content=final_script,
                episodes=episodes,
                theme=request.get("theme", ""),
                length=request.get("length", "短篇"),
                style=style,
                setting=request.get("setting", ""),
                characters=_json.dumps(entities.get("characters", []), ensure_ascii=False),
                source_type="outline",
                source_content=outline[:500],
                status=ScriptStatus.COMPLETED.value,
                user_id=str(request.get("user_id", "")),
                pipeline_version="v2",
                storyboard=storyboard_data if storyboard_data else None,
                character_graph=result.get("character_graph"),
                workflow_metadata={
                    "pipeline": "v2_outline_kafka_worker",
                    "stages": result.get("stages", {}),
                },
                analysis_result={
                    "events": [],
                    "locations": entities.get("locations", []),
                    "props": entities.get("props", []),
                },
            )
            db.add(script)
            await db.flush()

            task = await db.get(GenerationTask, task_id)
            if task:
                task.status = TaskStatus.COMPLETED.value
                task.progress = 100
                task.script_id = script.id
                task.end_time = time.time()
                task.duration = task.end_time - t0
            await db.commit()

        await _task_set(task_id, {
            "status": "completed", "progress": 100,
            "script_id": script.id,
            "title": request.get("title", ""),
        })

        logger.info(f"TaskWorker: outline {task_id} → script_id={script.id} "
                    f"{len(episodes)}eps elapsed={time.time()-t0:.1f}s")

    # ── Stop ──

    async def stop(self):
        """Graceful shutdown."""
        self._running = False
        logger.info("TaskWorker: stopped (processed {} tasks)".format(self._tasks_processed))


# Singleton
_worker: Optional[TaskWorker] = None


async def get_task_worker() -> TaskWorker:
    global _worker
    if _worker is None:
        from app.core.config import settings
        _worker = TaskWorker(backend=settings.TASK_QUEUE_BACKEND)
    return _worker
