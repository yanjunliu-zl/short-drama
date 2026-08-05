"""
Scene Extractor Service SQLAlchemy 模型
"""
from sqlalchemy import Column, BigInteger, String, Text, Integer, JSON, DateTime, Float
from datetime import datetime, timezone

from app.core.database import Base
from app.models.media_asset import MediaAsset, MediaType, SourceService


class ExtractedScene(Base):
    """抽取的场景模型"""
    __tablename__ = "extracted_scenes"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    script_id = Column(BigInteger, nullable=True, index=True, comment="关联剧本ID")
    scene_name = Column(String(255), nullable=True, comment="场景名称")
    description = Column(Text, nullable=True, comment="场景描述")
    characters_data = Column(JSON, nullable=True, comment="角色数据")
    props_data = Column(JSON, nullable=True, comment="道具数据")
    image_url = Column(String(512), nullable=True, comment="场景图片URL")
    style = Column(String(100), nullable=True, comment="风格")
    user_id = Column(String(64), nullable=True, index=True, comment="用户ID")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "script_id": self.script_id,
            "scene_name": self.scene_name,
            "description": self.description,
            "characters": self.characters_data,
            "props": self.props_data,
            "image_url": self.image_url,
            "style": self.style,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ExtractedCharacter(Base):
    """抽取的角色模型"""
    __tablename__ = "extracted_characters"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    scene_id = Column(BigInteger, nullable=True, index=True, comment="关联场景ID")
    script_id = Column(BigInteger, nullable=True, comment="关联剧本ID")
    name = Column(String(100), nullable=False, comment="角色名称")
    description = Column(Text, nullable=True, comment="角色描述")
    role_type = Column(String(50), nullable=True, comment="角色类型（主角/配角/龙套）")
    attributes = Column(JSON, nullable=True, comment="角色属性")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "scene_id": self.scene_id,
            "script_id": self.script_id,
            "name": self.name,
            "description": self.description,
            "role_type": self.role_type,
            "attributes": self.attributes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ExtractedProp(Base):
    """抽取的道具模型"""
    __tablename__ = "extracted_props"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    scene_id = Column(BigInteger, nullable=True, index=True, comment="关联场景ID")
    script_id = Column(BigInteger, nullable=True, comment="关联剧本ID")
    name = Column(String(100), nullable=False, comment="道具名称")
    description = Column(Text, nullable=True, comment="道具描述")
    prop_type = Column(String(50), nullable=True, comment="道具类型")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "scene_id": self.scene_id,
            "script_id": self.script_id,
            "name": self.name,
            "description": self.description,
            "prop_type": self.prop_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
