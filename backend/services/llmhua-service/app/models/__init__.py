"""
Llmhua Video Generation Service SQLAlchemy 模型
"""
from sqlalchemy import Column, BigInteger, String, Text, Integer, JSON, DateTime, Float, Boolean
from datetime import datetime, timezone

from app.core.database import Base
from app.models.media_asset import MediaAsset, MediaType, SourceService


class VideoGenerationTask(Base):
    """视频生成任务模型"""
    __tablename__ = "video_generation_tasks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(String(64), unique=True, nullable=False, index=True, comment="任务UUID")
    scene_id = Column(BigInteger, nullable=True, index=True, comment="关联场景ID")
    script_id = Column(BigInteger, nullable=True, comment="关联剧本ID")
    status = Column(String(20), nullable=False, default="pending", index=True, comment="任务状态")
    progress = Column(Integer, default=0, comment="进度 0-100")
    video_url = Column(String(512), nullable=True, comment="生成的视频URL")
    image_url = Column(String(512), nullable=True, comment="生成的图片URL")
    prompt = Column(Text, nullable=True, comment="生成提示词")
    parameters = Column(JSON, nullable=True, comment="生成参数")
    error = Column(Text, nullable=True, comment="错误信息")
    user_id = Column(String(64), nullable=True, index=True, comment="用户ID")
    duration = Column(Float, nullable=True, comment="视频时长")
    start_time = Column(Float, nullable=True)
    end_time = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "scene_id": self.scene_id,
            "script_id": self.script_id,
            "status": self.status,
            "progress": self.progress,
            "video_url": self.video_url,
            "image_url": self.image_url,
            "prompt": self.prompt,
            "parameters": self.parameters,
            "error": self.error,
            "user_id": self.user_id,
            "duration": self.duration,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
