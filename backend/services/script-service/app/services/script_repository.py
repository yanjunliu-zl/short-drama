"""
Script & Task Repository — pure DB operations, no business logic.

Extracted from script_service.py to separate data access from orchestration.
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Script, GenerationTask, ScriptStatus, TaskStatus
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class ScriptRepository:
    """Data access for scripts and generation tasks."""

    async def get_script(self, script_id: int) -> Optional[Dict]:
        async with AsyncSessionLocal() as db:
            script = await db.get(Script, script_id)
            return script.to_dict() if script else None

    async def list_scripts(
        self, page: int = 1, page_size: int = 10,
        user_id: Optional[str] = None, status: Optional[str] = None,
    ) -> tuple:
        async with AsyncSessionLocal() as db:
            stmt = select(Script)
            if user_id:
                stmt = stmt.where(Script.user_id == user_id)
            if status:
                stmt = stmt.where(Script.status == status)
            stmt = stmt.order_by(Script.created_at.desc())

            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = (await db.execute(count_stmt)).scalar() or 0

            offset = (page - 1) * page_size
            stmt = stmt.offset(offset).limit(page_size)
            scripts = (await db.execute(stmt)).scalars().all()
            return [s.to_dict() for s in scripts], total

    async def update_script(self, script_id: int, fields: dict) -> Optional[Dict]:
        async with AsyncSessionLocal() as db:
            script = await db.get(Script, script_id)
            if not script:
                return None
            for field, value in fields.items():
                if value is not None:
                    setattr(script, field, value)
            script.updated_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(script)
            return script.to_dict()

    async def delete_script(self, script_id: int) -> bool:
        async with AsyncSessionLocal() as db:
            script = await db.get(Script, script_id)
            if not script:
                return False
            stmt = delete(GenerationTask).where(GenerationTask.script_id == script_id)
            await db.execute(stmt)
            await db.delete(script)
            await db.commit()
            return True

    async def get_generation_status(self, task_id: str) -> Optional[dict]:
        """Get generation task status from DB (Redis-based lookup is in script_service)."""
        async with AsyncSessionLocal() as db:
            stmt = select(Script).where(
                Script.task_id == task_id
            ).order_by(Script.created_at.desc()).limit(1)
            result = await db.execute(stmt)
            script = result.scalar_one_or_none()
            if script:
                return {
                    "title": script.title, "content": script.content,
                    "episodes": script.episodes, "theme": script.theme,
                    "style": script.style, "length": script.length,
                    "setting": script.setting, "characters": script.characters,
                }
            return None

    async def get_character_graph(self, script_id: int) -> Optional[dict]:
        async with AsyncSessionLocal() as db:
            script = await db.get(Script, script_id)
            if script and script.character_graph:
                return script.character_graph
            return None

    async def get_or_create_task(
        self, task_id: str,
    ) -> tuple:
        """Get existing task or create a new one. Returns (task, is_new)."""
        async with AsyncSessionLocal() as db:
            task = await db.get(GenerationTask, task_id)
            is_new = task is None
            if is_new:
                task = GenerationTask(task_id=task_id, status=TaskStatus.PROCESSING.value)
                db.add(task)
                await db.commit()
                await db.refresh(task)
            return task, is_new
