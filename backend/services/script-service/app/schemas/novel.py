"""结构化输出模型 — 小说转剧本多阶段流水线"""

from pydantic import BaseModel, Field
from typing import List, Optional


class ExtractedCharacter(BaseModel):
    name: str = Field(..., description="Character name")
    role: str = Field(default="配角", description="主角/配角/反派/群众")
    description: str = Field(..., description="Visual description: age, appearance, clothing")


class ExtractCharactersResponse(BaseModel):
    characters: List[ExtractedCharacter] = Field(..., description="Extracted characters")


class ExtractedEvent(BaseModel):
    index: int = Field(..., description="Event index, starting from 0")
    title: str = Field(..., description="Brief event title")
    description: str = Field(..., description="Detailed event description")
    characters_involved: List[str] = Field(default_factory=list, description="Characters involved")
    location: str = Field(default="", description="Where the event takes place")
    is_major: bool = Field(default=True, description="True for major plot events")


class ExtractEventsResponse(BaseModel):
    events: List[ExtractedEvent] = Field(..., description="Extracted events in chronological order")


class WriteScriptResponse(BaseModel):
    script: List[str] = Field(..., description="Script scenes, one string per scene")


class EnhanceScriptResponse(BaseModel):
    script: List[str] = Field(..., description="Enhanced script scenes")


class ExtractedEntity(BaseModel):
    name: str = Field(..., description="Entity name")
    description: str = Field(default="", description="Brief description")


class ExtractedCharacterEntity(BaseModel):
    name: str = Field(..., description="Character name")
    role: str = Field(default="配角", description="Role: 主角/配角/反派/群众")
    gender: str = Field(default="", description="Gender: 男/女")
    description: str = Field(default="", description="Visual description")


class ExtractEntitiesResponse(BaseModel):
    characters: List[ExtractedCharacterEntity] = Field(default_factory=list)
    locations: List[ExtractedEntity] = Field(default_factory=list)
    props: List[ExtractedEntity] = Field(default_factory=list)
