"""
Script Service SQLAlchemy 模型
"""
from sqlalchemy import Column, Integer, BigInteger, String, Text, Boolean, Float, JSON, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from app.core.database import Base


class ScriptStatus(str, enum.Enum):
    DRAFT = "draft"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ScriptSourceType(str, enum.Enum):
    MANUAL = "manual"
    NOVEL = "novel"
    OUTLINE = "outline"
    AI_GENERATED = "ai_generated"


class Script(Base):
    """剧本模型"""
    __tablename__ = "scripts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(String(64), nullable=True, index=True, comment="异步任务ID")
    title = Column(String(255), nullable=False, comment="剧本标题")
    content = Column(Text, nullable=True, comment="剧本内容")
    theme = Column(String(100), nullable=True, comment="主题")
    length = Column(String(20), nullable=True, comment="篇幅（短篇/中篇/长篇）")
    style = Column(String(100), nullable=True, comment="风格")
    setting = Column(String(255), nullable=True, comment="故事背景")
    characters = Column(JSON, nullable=True, comment="角色列表")
    source_type = Column(String(20), nullable=False, default=ScriptSourceType.MANUAL.value, comment="来源类型")
    source_content = Column(Text, nullable=True, comment="原始来源内容（如小说原文）")
    status = Column(String(20), nullable=False, default=ScriptStatus.DRAFT.value, index=True, comment="状态")
    user_id = Column(String(64), nullable=True, index=True, comment="用户ID")
    regenerated_from = Column(BigInteger, nullable=True, comment="重新生成的源剧本ID")
    modifications = Column(JSON, nullable=True, comment="修改记录")
    workflow_metadata = Column(JSON, nullable=True, comment="工作流元数据")
    analysis_result = Column(JSON, nullable=True, comment="分析结果")
    has_optimized_version = Column(Boolean, default=False, comment="是否有优化版本")
    error_message = Column(Text, nullable=True, comment="错误信息")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), comment="创建时间")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), comment="更新时间")

    # 关联
    task = relationship("GenerationTask", back_populates="script", uselist=False)

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "title": self.title,
            "content": self.content,
            "theme": self.theme,
            "length": self.length,
            "style": self.style,
            "setting": self.setting,
            "characters": self.characters,
            "source_type": self.source_type,
            "source_content": self.source_content,
            "status": self.status,
            "user_id": self.user_id,
            "regenerated_from": self.regenerated_from,
            "modifications": self.modifications,
            "workflow_metadata": self.workflow_metadata,
            "analysis_result": self.analysis_result,
            "has_optimized_version": self.has_optimized_version,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class GenerationTask(Base):
    """剧本生成任务模型"""
    __tablename__ = "generation_tasks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(String(64), unique=True, nullable=False, index=True, comment="任务UUID")
    script_id = Column(BigInteger, ForeignKey("scripts.id", ondelete="SET NULL"), nullable=True, comment="关联剧本ID")
    status = Column(String(20), nullable=False, default=TaskStatus.PENDING.value, index=True, comment="任务状态")
    progress = Column(Integer, default=0, comment="进度百分比 0-100")
    error = Column(Text, nullable=True, comment="错误信息")
    request_data = Column(JSON, nullable=True, comment="请求原始数据")
    result_data = Column(JSON, nullable=True, comment="结果数据")
    start_time = Column(Float, nullable=True, comment="开始时间戳")
    end_time = Column(Float, nullable=True, comment="结束时间戳")
    duration = Column(Float, nullable=True, comment="耗时（秒）")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # 关联
    script = relationship("Script", back_populates="task")

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "script_id": self.script_id,
            "status": self.status,
            "progress": self.progress,
            "error": self.error,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
