"""
媒体资产数据库模型

记录 AI 生成的图片和视频在 Ceph 中的存储信息。
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, BigInteger, DateTime, Text, Enum as SAEnum
from app.core.database import Base
import enum


class MediaType(str, enum.Enum):
    IMAGE = "image"
    VIDEO = "video"


class SourceService(str, enum.Enum):
    LLMHUA = "llmhua-service"
    SCENE_EXTRACTOR = "scene-extractor"
    STORYBOARD = "storyboard-service"
    VIDEO_SERVICE = "video-service"
    FINAL_CUT = "final-cut-service"


class MediaAsset(Base):
    """
    媒体资产表 — 记录存储在 Ceph 中的 AI 生成媒体文件

    存储路径格式: {media_type}/{date}/{entity_type}/{entity_id}/{uuid}.{ext}
    """
    __tablename__ = "media_assets"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="自增主键")
    object_key = Column(
        String(512), unique=True, nullable=False, index=True,
        comment="Ceph 对象 Key（存储路径）"
    )
    bucket = Column(
        String(128), nullable=False, default="short-drama",
        comment="Ceph Bucket 名称"
    )
    media_type = Column(
        SAEnum(MediaType), nullable=False, default=MediaType.IMAGE,
        comment="媒体类型: image / video"
    )
    content_type = Column(
        String(128), nullable=True,
        comment="MIME 类型，如 image/png, video/mp4"
    )
    file_size = Column(
        BigInteger, nullable=True, default=0,
        comment="文件大小（字节）"
    )
    original_url = Column(
        String(2048), nullable=True,
        comment="原始来源 URL（如 Seedance 返回的 URL）"
    )
    ceph_url = Column(
        String(2048), nullable=True,
        comment="Ceph 预签名 URL 或公开 URL"
    )
    source_service = Column(
        String(64), nullable=False, default="scene-extractor",
        comment="来源服务名称"
    )
    related_entity_type = Column(
        String(64), nullable=True, index=True,
        comment="关联实体类型 (scene, storyboard, video, character)"
    )
    related_entity_id = Column(
        String(128), nullable=True, index=True,
        comment="关联实体 ID"
    )
    user_id = Column(
        String(128), nullable=True, index=True,
        comment="用户 ID"
    )
    metadata_json = Column(
        Text, nullable=True,
        comment="额外元数据 (JSON)"
    )
    created_at = Column(
        DateTime, default=datetime.utcnow, nullable=False,
        comment="创建时间"
    )

    def __repr__(self):
        return (
            f"<MediaAsset(id={self.id}, type={self.media_type}, "
            f"key={self.object_key}, entity={self.related_entity_type}:{self.related_entity_id})>"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "object_key": self.object_key,
            "bucket": self.bucket,
            "media_type": self.media_type.value if isinstance(self.media_type, MediaType) else self.media_type,
            "content_type": self.content_type,
            "file_size": self.file_size,
            "original_url": self.original_url,
            "ceph_url": self.ceph_url,
            "source_service": self.source_service,
            "related_entity_type": self.related_entity_type,
            "related_entity_id": self.related_entity_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
