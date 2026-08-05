"""
Storyboard Service SQLAlchemy 模型
"""
from sqlalchemy import Column, BigInteger, String, Text, Integer, JSON, DateTime, Float
from datetime import datetime, timezone

from app.core.database import Base


class Storyboard(Base):
    """分镜脚本模型"""
    __tablename__ = "storyboards"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    script_id = Column(BigInteger, nullable=True, index=True, comment="关联剧本ID")
    title = Column(String(255), nullable=False, comment="分镜标题")
    content = Column(Text, nullable=True, comment="分镜原始内容")
    theme = Column(String(100), nullable=True, comment="主题")
    style = Column(String(100), nullable=True, comment="风格")
    scenes_data = Column(JSON, nullable=True, comment="场景数据列表")
    total_scenes = Column(Integer, default=0, comment="场景总数")
    metadata_ = Column("metadata", JSON, nullable=True, comment="生成元数据")
    user_id = Column(String(64), nullable=True, index=True, comment="用户ID")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "script_id": self.script_id,
            "title": self.title,
            "content": self.content,
            "theme": self.theme,
            "style": self.style,
            "scenes": self.scenes_data,
            "total_scenes": self.total_scenes,
            "metadata": self.metadata_,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
