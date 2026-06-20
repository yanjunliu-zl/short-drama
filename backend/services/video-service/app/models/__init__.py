"""
Video Service SQLAlchemy 模型
"""
from sqlalchemy import Column, BigInteger, String, Text, Integer, JSON, DateTime, Float, Boolean
from datetime import datetime, timezone

from app.core.database import Base


class Video(Base):
    """视频记录模型"""
    __tablename__ = "videos"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    script_id = Column(BigInteger, nullable=True, index=True, comment="关联剧本ID")
    storyboard_id = Column(BigInteger, nullable=True, comment="关联分镜ID")
    title = Column(String(255), nullable=False, comment="视频标题")
    description = Column(Text, nullable=True, comment="视频描述")
    video_url = Column(String(512), nullable=True, comment="视频URL")
    thumbnail_url = Column(String(512), nullable=True, comment="缩略图URL")
    duration = Column(Float, nullable=True, comment="视频时长（秒）")
    file_size = Column(BigInteger, nullable=True, comment="文件大小（字节）")
    resolution = Column(String(50), nullable=True, comment="分辨率（如1920x1080）")
    format = Column(String(20), nullable=True, comment="视频格式（mp4/webm等）")
    status = Column(String(20), nullable=False, default="pending", index=True, comment="状态")
    storage_type = Column(String(20), nullable=True, comment="存储类型（s3/local）")
    storage_path = Column(String(512), nullable=True, comment="存储路径")
    user_id = Column(String(64), nullable=True, index=True, comment="用户ID")
    metadata_ = Column("metadata", JSON, nullable=True, comment="元数据")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "script_id": self.script_id,
            "storyboard_id": self.storyboard_id,
            "title": self.title,
            "description": self.description,
            "video_url": self.video_url,
            "thumbnail_url": self.thumbnail_url,
            "duration": self.duration,
            "file_size": self.file_size,
            "resolution": self.resolution,
            "format": self.format,
            "status": self.status,
            "storage_type": self.storage_type,
            "storage_path": self.storage_path,
            "user_id": self.user_id,
            "metadata": self.metadata_,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class VideoProcessingTask(Base):
    """视频处理任务模型"""
    __tablename__ = "video_processing_tasks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(String(64), unique=True, nullable=False, index=True, comment="任务UUID")
    video_id = Column(BigInteger, nullable=True, index=True, comment="关联视频ID")
    task_type = Column(String(50), nullable=False, comment="任务类型（generation/encoding/thumbnail等）")
    status = Column(String(20), nullable=False, default="pending", index=True, comment="状态")
    progress = Column(Integer, default=0, comment="进度 0-100")
    parameters = Column(JSON, nullable=True, comment="任务参数")
    result = Column(JSON, nullable=True, comment="任务结果")
    error = Column(Text, nullable=True, comment="错误信息")
    retry_count = Column(Integer, default=0, comment="重试次数")
    celery_task_id = Column(String(64), nullable=True, comment="Celery任务ID")
    start_time = Column(Float, nullable=True)
    end_time = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "video_id": self.video_id,
            "task_type": self.task_type,
            "status": self.status,
            "progress": self.progress,
            "parameters": self.parameters,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
            "celery_task_id": self.celery_task_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
