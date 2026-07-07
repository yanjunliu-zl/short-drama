"""
GraphRag 服务 - 用于剧本创作过程中的上下文一致性和知识管理

该模块提供以下功能：
1. 实体提取：从剧本中提取角色、地点、事件等实体
2. 关系构建：构建实体之间的关系图谱
3. 上下文检索：基于图谱的上下文检索，确保一致性
4. 知识图谱存储：使用 Neo4j 存储和管理剧本知识
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
import hashlib
import json

from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


# ============== 数据模型 ==============

@dataclass
class Entity:
    """实体定义"""
    id: str
    name: str
    entity_type: str  # CHARACTER, LOCATION, OBJECT, EVENT, EMOTION 等
    description: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Relationship:
    """关系定义"""
    id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: str  # RELATES_TO, LOVES, HATES, WORKS_AT, VISITS 等
    description: str = ""
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SceneContext:
    """场景上下文"""
    scene_id: str
    script_id: str
    scene_number: int
    setting: str
    characters: List[str]
    key_events: List[str]
    emotional_tone: str
    previous_context_summary: str = ""
    next_context_preview: str = ""


# ============== 知识图谱存储接口 ==============

class KnowledgeGraphStorage:
    """知识图谱存储接口 - 支持多种后端"""

    async def add_entity(self, entity: Entity) -> bool:
        raise NotImplementedError

    async def add_relationship(self, relationship: Relationship) -> bool:
        raise NotImplementedError

    async def get_entity(self, entity_id: str) -> Optional[Entity]:
        raise NotImplementedError

    async def get_entities_by_type(self, entity_type: str) -> List[Entity]:
        raise NotImplementedError

    async def get_entity_relationships(self, entity_id: str) -> List[Relationship]:
        raise NotImplementedError

    async def find_path(self, start_entity: str, end_entity: str) -> Optional[List[Relationship]]:
        """查找两个实体之间的路径"""
        raise NotImplementedError

    async def search_by_attribute(self, entity_type: str, attribute: str, value: Any) -> List[Entity]:
        """根据属性搜索实体"""
        raise NotImplementedError


# ============== Neo4j 实现 ==============

class Neo4jStorage(KnowledgeGraphStorage):
    """Neo4j 知识图谱存储实现"""

    def __init__(self):
        self.driver = None
        self._connected = False
        self._uri = settings.GRAPHRAG_NEO4J_URI
        self._username = settings.GRAPHRAG_NEO4J_USERNAME
        self._password = settings.GRAPHRAG_NEO4J_PASSWORD

    async def connect(self):
        """连接 Neo4j"""
        if self._connected:
            return

        try:
            from neo4j import AsyncGraphDatabase

            logger.info(f"连接 Neo4j 图数据库: {self._uri}")

            self.driver = AsyncGraphDatabase.driver(
                self._uri,
                auth=(self._username, self._password)
            )

            # 测试连接
            async with self.driver.session() as session:
                await session.run("RETURN 1 AS result")

            self._connected = True
            logger.info("Neo4j 图数据库连接成功")

        except ImportError:
            logger.warning("neo4j 包未安装，使用内存存储")
            self._connected = False
        except Exception as e:
            logger.error(f"Neo4j 连接失败: {e}")
            self._connected = False

    async def disconnect(self):
        """断开 Neo4j 连接"""
        if self.driver:
            await self.driver.close()
            self._connected = False
            logger.info("Neo4j 图数据库已断开连接")

    async def add_entity(self, entity: Entity) -> bool:
        if not self._connected:
            return False

        try:
            async with self.driver.session() as session:
                await session.run(
                    """
                    MERGE (e:Entity {
                        id: $entity_id,
                        name: $name,
                        type: $entity_type
                    })
                    SET e.description = $description,
                        e.attributes = $attributes,
                        e.metadata = $metadata,
                        e.updated_at = datetime()
                    RETURN e
                    """,
                    entity_id=entity.id,
                    name=entity.name,
                    entity_type=entity.entity_type,
                    description=entity.description,
                    attributes=json.dumps(entity.attributes),
                    metadata=json.dumps(entity.metadata)
                )
            return True
        except Exception as e:
            logger.error(f"添加实体失败: {e}")
            return False

    async def add_relationship(self, relationship: Relationship) -> bool:
        if not self._connected:
            return False

        try:
            async with self.driver.session() as session:
                await session.run(
                    """
                    MATCH (source:Entity {id: $source_id}), (target:Entity {id: $target_id})
                    MERGE (source)-[r:RELATIONSHIP {
                        id: $rel_id,
                        type: $relationship_type
                    }]->(target)
                    SET r.description = $description,
                        r.weight = $weight,
                        r.metadata = $metadata,
                        r.updated_at = datetime()
                    RETURN r
                    """,
                    rel_id=relationship.id,
                    source_id=relationship.source_entity_id,
                    target_id=relationship.target_entity_id,
                    relationship_type=relationship.relationship_type,
                    description=relationship.description,
                    weight=relationship.weight,
                    metadata=json.dumps(relationship.metadata)
                )
            return True
        except Exception as e:
            logger.error(f"添加关系失败: {e}")
            return False

    async def get_entity(self, entity_id: str) -> Optional[Entity]:
        if not self._connected:
            return None

        try:
            async with self.driver.session() as session:
                result = await session.run(
                    """
                    MATCH (e:Entity {id: $entity_id})
                    RETURN e.id AS id, e.name AS name, e.type AS entity_type,
                           e.description AS description, e.attributes AS attributes,
                           e.metadata AS metadata
                    """,
                    entity_id=entity_id
                )
                record = await result.single()
                if record:
                    return Entity(
                        id=record["id"],
                        name=record["name"],
                        entity_type=record["entity_type"],
                        description=record["description"] or "",
                        attributes=json.loads(record["attributes"] or "{}"),
                        metadata=json.loads(record["metadata"] or "{}")
                    )
                return None
        except Exception as e:
            logger.error(f"获取实体失败: {e}")
            return None

    async def get_entities_by_type(self, entity_type: str) -> List[Entity]:
        if not self._connected:
            return []

        try:
            async with self.driver.session() as session:
                result = await session.run(
                    """
                    MATCH (e:Entity {type: $entity_type})
                    RETURN e.id AS id, e.name AS name, e.type AS entity_type,
                           e.description AS description, e.attributes AS attributes,
                           e.metadata AS metadata
                    """,
                    entity_type=entity_type
                )
                entities = []
                async for record in result:
                    entities.append(Entity(
                        id=record["id"],
                        name=record["name"],
                        entity_type=record["entity_type"],
                        description=record["description"] or "",
                        attributes=json.loads(record["attributes"] or "{}"),
                        metadata=json.loads(record["metadata"] or "{}")
                    ))
                return entities
        except Exception as e:
            logger.error(f"获取实体列表失败: {e}")
            return []

    async def get_entity_relationships(self, entity_id: str) -> List[Relationship]:
        if not self._connected:
            return []

        try:
            async with self.driver.session() as session:
                result = await session.run(
                    """
                    MATCH (source:Entity {id: $entity_id})-[r]->(target:Entity)
                    RETURN r.id AS id, r.type AS relationship_type,
                           r.description AS description, r.weight AS weight,
                           r.metadata AS metadata,
                           target.id AS target_id
                    """,
                    entity_id=entity_id
                )
                relationships = []
                async for record in result:
                    relationships.append(Relationship(
                        id=record["id"],
                        source_entity_id=entity_id,
                        target_entity_id=record["target_id"],
                        relationship_type=record["relationship_type"],
                        description=record["description"] or "",
                        weight=record["weight"] or 1.0,
                        metadata=json.loads(record["metadata"] or "{}")
                    ))
                return relationships
        except Exception as e:
            logger.error(f"获取关系列表失败: {e}")
            return []

    async def find_path(self, start_entity: str, end_entity: str, max_depth: int = 3) -> Optional[List[Dict]]:
        """查找两个实体之间的路径"""
        if not self._connected:
            return None

        try:
            async with self.driver.session() as session:
                result = await session.run(
                    """
                    MATCH path = shortestPath((start:Entity {id: $start_id})-[*..$max_depth]-(end:Entity {id: $end_id}))
                    WITH path, relationships(path) AS rels
                    RETURN [n IN nodes(path) | n.id] AS node_ids,
                           [r IN rels | {
                               source: startNode(r).id,
                               target: endNode(r).id,
                               type: r.type
                           }] AS relationships
                    """,
                    start_id=start_entity,
                    end_id=end_entity,
                    max_depth=max_depth
                )
                record = await result.single()
                if record:
                    return {
                        "node_ids": record["node_ids"],
                        "relationships": record["relationships"]
                    }
                return None
        except Exception as e:
            logger.error(f"查找路径失败: {e}")
            return None

    async def search_by_attribute(self, entity_type: str, attribute: str, value: Any) -> List[Entity]:
        if not self._connected:
            return []

        try:
            async with self.driver.session() as session:
                result = await session.run(
                    """
                    MATCH (e:Entity {type: $entity_type})
                    WHERE e.attributes[$attr] = $value
                    RETURN e.id AS id, e.name AS name, e.type AS entity_type,
                           e.description AS description, e.attributes AS attributes,
                           e.metadata AS metadata
                    """,
                    entity_type=entity_type,
                    attr=attribute,
                    value=value
                )
                entities = []
                async for record in result:
                    entities.append(Entity(
                        id=record["id"],
                        name=record["name"],
                        entity_type=record["entity_type"],
                        description=record["description"] or "",
                        attributes=json.loads(record["attributes"] or "{}"),
                        metadata=json.loads(record["metadata"] or "{}")
                    ))
                return entities
        except Exception as e:
            logger.error(f"按属性搜索失败: {e}")
            return []


# ============== 内存存储（备选） ==============

class InMemoryStorage(KnowledgeGraphStorage):
    """内存知识图谱存储实现（用于开发和测试）"""

    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.relationships: Dict[str, Relationship] = {}

    async def add_entity(self, entity: Entity) -> bool:
        self.entities[entity.id] = entity
        return True

    async def add_relationship(self, relationship: Relationship) -> bool:
        self.relationships[relationship.id] = relationship
        return True

    async def get_entity(self, entity_id: str) -> Optional[Entity]:
        return self.entities.get(entity_id)

    async def get_entities_by_type(self, entity_type: str) -> List[Entity]:
        return [e for e in self.entities.values() if e.entity_type == entity_type]

    async def get_entity_relationships(self, entity_id: str) -> List[Relationship]:
        return [r for r in self.relationships.values()
                if r.source_entity_id == entity_id or r.target_entity_id == entity_id]

    async def find_path(self, start_entity: str, end_entity: str) -> Optional[List[Relationship]]:
        # 简单的 BFS 路径查找
        if start_entity not in self.entities or end_entity not in self.entities:
            return None

        visited = {start_entity}
        queue = [[start_entity]]

        while queue:
            path = queue.pop(0)
            node = path[-1]

            if node == end_entity:
                # 构建关系列表
                relationships = []
                for i in range(len(path) - 1):
                    rel_id = hashlib.md5(f"{path[i]}->{path[i+1]}".encode()).hexdigest()
                    if rel_id in self.relationships:
                        relationships.append(self.relationships[rel_id])
                return relationships

            for rel in self.relationships.values():
                if rel.source_entity_id == node and rel.target_entity_id not in visited:
                    new_path = path + [rel.target_entity_id]
                    queue.append(new_path)
                    visited.add(rel.target_entity_id)

                elif rel.target_entity_id == node and rel.source_entity_id not in visited:
                    new_path = path + [rel.source_entity_id]
                    queue.append(new_path)
                    visited.add(rel.source_entity_id)

        return None

    async def search_by_attribute(self, entity_type: str, attribute: str, value: Any) -> List[Entity]:
        return [
            e for e in self.entities.values()
            if e.entity_type == entity_type and e.attributes.get(attribute) == value
        ]


# ============== FAISS 向量存储（真实 embedding） ==============

class VectorKnowledgeStore:
    """FAISS-based 向量知识存储 — 用于语义检索。

    使用 HuggingFace embeddings（与 V2 pipeline 共享模型）实现真实语义搜索，
    替代之前基于 MD5 hash 的关键词匹配。
    """

    def __init__(self, embedding_model_name: str = "BAAI/bge-large-zh-v1.5"):
        self._texts: Dict[str, str] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._embeddings = None  # Lazy-loaded
        self._faiss_index = None  # Lazy-built
        self._embedding_model_name = embedding_model_name
        self._dirty = False

    def _get_embeddings(self):
        """Lazy-load the HuggingFace embedding model."""
        if self._embeddings is None:
            from langchain_huggingface import HuggingFaceEmbeddings
            logger.info(f"GraphRAG: loading embedding model {self._embedding_model_name}")
            self._embeddings = HuggingFaceEmbeddings(
                model_name=self._embedding_model_name,
            )
        return self._embeddings

    def _build_index(self):
        """Build FAISS index from stored texts."""
        from langchain_community.vectorstores import FAISS
        if not self._texts:
            return
        embeddings = self._get_embeddings()
        texts = list(self._texts.values())
        self._faiss_index = FAISS.from_texts(texts, embeddings)
        self._dirty = False

    async def add_text(self, text_id: str, text: str, metadata: Dict[str, Any] = None):
        """Add text to vector store and mark index for rebuild."""
        self._texts[text_id] = text
        self._metadata[text_id] = metadata or {}
        self._dirty = True

    async def search_similar(self, query: str, top_k: int = 5) -> List[Dict]:
        """Semantic search using FAISS + real embeddings.

        Falls back to keyword matching if the embedding model fails to load.
        """
        # Try FAISS semantic search
        if self._faiss_index is None or self._dirty:
            try:
                self._build_index()
            except Exception as e:
                logger.warning(f"FAISS index build failed: {e} — falling back to keyword")

        if self._faiss_index is not None:
            try:
                docs = self._faiss_index.similarity_search_with_score(query, k=top_k)
                results = []
                for doc, score in docs:
                    text_id = None
                    for tid, text in self._texts.items():
                        if text == doc.page_content:
                            text_id = tid
                            break
                    results.append({
                        "id": text_id or "unknown",
                        "text": doc.page_content,
                        "score": float(1.0 / (1.0 + score)),  # Convert distance to similarity
                        "metadata": doc.metadata or {},
                    })
                if results:
                    return results
            except Exception as e:
                logger.warning(f"FAISS search failed: {e} — falling back to keyword")

        # Fallback: keyword matching
        results = []
        for text_id, data in list(self._texts.items()):
            score = sum(1 for kw in query.split() if kw in data)
            if score > 0:
                results.append({
                    "id": text_id,
                    "text": data,
                    "score": min(score * 0.3, 1.0),
                    "metadata": self._metadata.get(text_id, {}),
                })

        if not results:
            for text_id, data in list(self._texts.items())[:top_k]:
                results.append({
                    "id": text_id,
                    "text": data,
                    "score": 0.1,
                    "metadata": self._metadata.get(text_id, {}),
                })

        return sorted(results, key=lambda x: x["score"], reverse=True)[:top_k]

    async def get_context_for_entities(self, entity_names: List[str], script_id: str) -> str:
        """Get context snippets for given entities using semantic search."""
        context_parts = []
        for entity_name in entity_names:
            results = await self.search_similar(entity_name, top_k=2)
            for r in results:
                if r["metadata"].get("script_id") == script_id or not script_id:
                    context_parts.append(r["text"][:500])
        if context_parts:
            return "\n---\n".join(context_parts[:3])
        return ""


# ============== 实体和关系提取器 ==============

class GraphRagExtractor:
    """GraphRag 实体和关系提取器"""

    def __init__(self, llm):
        self.llm = llm
        self.entity_template = PromptTemplate.from_template(
            """你是一个专业的剧本分析专家，请从以下剧本内容中提取实体。

剧本内容：
{script_content}

请识别以下类型的实体：
1. 角色 (CHARACTER) - 主要和次要角色
2. 地点 (LOCATION) - 场景和地点
3. 物品 (OBJECT) - 重要道具
4. 事件 (EVENT) - 关键事件
5. 情感 (EMOTION) - 情感状态

请以 JSON 格式返回提取的实体：
{{"entities": [
    {{"id": "entity_1", "name": "角色名", "type": "CHARACTER", "description": "角色描述", "attributes": {}}}
]}]

注意事项：
1. 实体名称要统一，避免同义词
2. 描述要简洁但包含关键信息
3. 每个实体只出现一次"""
        )

        self.relationship_template = PromptTemplate.from_template(
            """你是一个专业的剧本分析专家，请从以下剧本内容中提取实体之间的关系。

剧本内容：
{script_content}

已识别的实体：
{entities}

请识别以下类型的关系：
1. RELATES_TO - 一般关系
2. LOVES - 爱情关系
3. HATES - 敌对关系
4. WORKS_AT - 工作地点
5. VISITS - 访问地点
6. HAS - 拥有关系
7. AFFECTS - 影响关系

请以 JSON 格式返回提取的关系：
{{"relationships": [
    {{"id": "rel_1", "source_entity_id": "entity_1", "target_entity_id": "entity_2", "type": "RELATIONSHIP", "description": "关系描述", "weight": 0.8}}
]}]

注意事项：
1. 关系要基于剧本内容
2. weight 表示关系强度，范围 0-1"""
        )

    async def extract_entities(self, script_content: str) -> List[Entity]:
        """从剧本中提取实体"""
        try:
            messages = [
                SystemMessage(content="你是一个专业的剧本分析专家，擅长从剧本中提取实体信息。"),
                HumanMessage(content=self.entity_template.format(script_content=script_content[:3000]))
            ]

            response = await self.llm.ainvoke(messages)
            content = response.content

            # 解析 JSON
            try:
                # 尝试从响应中提取 JSON
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = content[json_start:json_end]
                    data = json.loads(json_str)
                else:
                    data = json.loads(content)

                entities = []
                for entity_data in data.get("entities", []):
                    entities.append(Entity(
                        id=entity_data.get("id", hashlib.md5(entity_data.get("name", "").encode()).hexdigest()),
                        name=entity_data.get("name", ""),
                        entity_type=entity_data.get("type", "UNKNOWN"),
                        description=entity_data.get("description", ""),
                        attributes=entity_data.get("attributes", {})
                    ))
                return entities

            except json.JSONDecodeError:
                logger.warning(f"无法解析实体提取响应: {content[:100]}...")
                return []

        except Exception as e:
            logger.error(f"实体提取失败: {e}")
            return []

    async def extract_relationships(self, script_content: str, entities: List[Entity]) -> List[Relationship]:
        """从剧本中提取实体之间的关系"""
        # 构建实体列表字符串
        entities_str = "\n".join([
            f"- {e.id}: {e.name} ({e.entity_type})"
            for e in entities
        ])

        try:
            messages = [
                SystemMessage(content="你是一个专业的剧本分析专家，擅长从剧本中提取实体关系。"),
                HumanMessage(content=self.relationship_template.format(
                    script_content=script_content[:3000],
                    entities=entities_str
                ))
            ]

            response = await self.llm.ainvoke(messages)
            content = response.content

            try:
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = content[json_start:json_end]
                    data = json.loads(json_str)
                else:
                    data = json.loads(content)

                relationships = []
                for rel_data in data.get("relationships", []):
                    relationships.append(Relationship(
                        id=rel_data.get("id", ""),
                        source_entity_id=rel_data.get("source_entity_id", ""),
                        target_entity_id=rel_data.get("target_entity_id", ""),
                        relationship_type=rel_data.get("type", "RELATES_TO"),
                        description=rel_data.get("description", ""),
                        weight=rel_data.get("weight", 1.0)
                    ))
                return relationships

            except json.JSONDecodeError:
                logger.warning(f"无法解析关系提取响应: {content[:100]}...")
                return []

        except Exception as e:
            logger.error(f"关系提取失败: {e}")
            return []


# ============== GraphRag 服务主类 ==============

class GraphRagService:
    """GraphRag 服务 - 管理剧本知识图谱，确保创作一致性"""

    def __init__(self):
        self.llm = None
        self.extractor = None
        self.storage: Optional[KnowledgeGraphStorage] = None
        self.vector_store = VectorKnowledgeStore()
        self._initialized = False

    async def initialize(self):
        """初始化 GraphRag 服务"""
        if self._initialized:
            return

        logger.info("初始化 GraphRag 服务...")

        # 初始化 LLM（复用 AI 服务的 LLM）
        from app.services.ai_service import AIService
        ai_service = AIService()
        await ai_service.initialize()
        self.llm = ai_service.llm

        # 初始化提取器
        self.extractor = GraphRagExtractor(self.llm)

        # 初始化知识图谱存储（优先使用 Neo4j）
        if settings.GRAPHRAG_ENABLED:
            self.storage = Neo4jStorage()
            await self.storage.connect()

            if not self.storage._connected:
                logger.warning("Neo4j 连接失败，使用内存存储")
                self.storage = InMemoryStorage()
        else:
            logger.info("GraphRag 未启用，使用内存存储")
            self.storage = InMemoryStorage()

        self._initialized = True
        logger.info("GraphRag 服务初始化完成")

    async def cleanup(self):
        """清理 GraphRag 服务"""
        if self.storage and isinstance(self.storage, Neo4jStorage):
            await self.storage.disconnect()
        self._initialized = False

    async def analyze_script(self, script_id: str, script_content: str) -> Dict[str, Any]:
        """分析剧本，提取实体和关系，构建知识图谱"""
        if not self._initialized:
            await self.initialize()

        logger.info(f"分析剧本: {script_id}")

        try:
            # 提取实体
            entities = await self.extractor.extract_entities(script_content)
            logger.info(f"提取了 {len(entities)} 个实体")

            # 存储实体
            for entity in entities:
                await self.storage.add_entity(entity)

            # 提取关系
            relationships = await self.extractor.extract_relationships(script_content, entities)
            logger.info(f"提取了 {len(relationships)} 条关系")

            # 存储关系
            for relationship in relationships:
                await self.storage.add_relationship(relationship)

            # 存储向量索引
            await self.vector_store.add_text(
                text_id=f"script_{script_id}_full",
                text=script_content,
                metadata={"script_id": script_id, "type": "full_script"}
            )

            # 统计信息
            character_count = len([e for e in entities if e.entity_type == "CHARACTER"])
            location_count = len([e for e in entities if e.entity_type == "LOCATION"])
            emotion_count = len([e for e in entities if e.entity_type == "EMOTION"])

            return {
                "script_id": script_id,
                "entities_extracted": len(entities),
                "relationships_extracted": len(relationships),
                "statistics": {
                    "characters": character_count,
                    "locations": location_count,
                    "objects": len([e for e in entities if e.entity_type == "OBJECT"]),
                    "events": len([e for e in entities if e.entity_type == "EVENT"]),
                    "emotions": emotion_count
                },
                "entities": [{"id": e.id, "name": e.name, "type": e.entity_type} for e in entities[:10]],
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"剧本分析失败: {e}")
            return {
                "script_id": script_id,
                "error": str(e),
                "entities_extracted": 0,
                "relationships_extracted": 0
            }

    async def get_character_consistency(self, character_name: str, script_id: str) -> Dict[str, Any]:
        """获取角色的上下文一致性信息"""
        if not self._initialized:
            await self.initialize()

        try:
            # 查找角色实体
            characters = await self.storage.search_by_attribute("CHARACTER", "name", character_name)

            if not characters:
                return {"error": f"未找到角色: {character_name}"}

            character = characters[0]

            # 获取角色关系
            relationships = await self.storage.get_entity_relationships(character.id)

            # 构建关系图谱
            related_characters = []
            for rel in relationships:
                target = await self.storage.get_entity(rel.target_entity_id)
                if target:
                    related_characters.append({
                        "name": target.name,
                        "type": target.entity_type,
                        "relationship": rel.relationship_type,
                        "description": rel.description
                    })

            # 获取角色相关上下文
            context = await self.vector_store.get_context_for_entities([character_name], script_id)

            return {
                "character_name": character_name,
                "character_id": character.id,
                "description": character.description,
                "relationships": related_characters,
                "context_snippet": context[:500] if context else "",
                "relationship_count": len(relationships)
            }

        except Exception as e:
            logger.error(f"获取角色一致性信息失败: {e}")
            return {"error": str(e)}

    async def get_context_for_generation(self, script_id: str, current_scene: Dict[str, Any]) -> str:
        """为剧本生成获取上下文信息"""
        if not self._initialized:
            await self.initialize()

        logger.info(f"为剧本生成获取上下文: {script_id}")

        context_parts = []

        try:
            # 1. 获取已识别的实体
            characters = await self.storage.get_entities_by_type("CHARACTER")
            locations = await self.storage.get_entities_by_type("LOCATION")

            if characters:
                context_parts.append("角色列表:")
                for char in characters[:10]:
                    context_parts.append(f"- {char.name}: {char.description[:100]}")

            if locations:
                context_parts.append("\n地点列表:")
                for loc in locations[:10]:
                    context_parts.append(f"- {loc.name}: {loc.description[:100]}")

            # 2. 检查人物关系一致性
            if current_scene.get("characters"):
                context_parts.append("\n人物关系:")
                for char_name in current_scene["characters"][:5]:
                    consistency_info = await self.get_character_consistency(char_name, script_id)
                    if "relationships" in consistency_info:
                        for rel in consistency_info["relationships"][:3]:
                            context_parts.append(
                                f"- {char_name} 与 {rel['name']} 的关系: {rel['relationship']}"
                            )

            # 3. 搜索相关剧本片段
            query_parts = []
            if current_scene.get("setting"):
                query_parts.append(current_scene["setting"])
            if current_scene.get("characters"):
                query_parts.extend(current_scene["characters"][:3])

            if query_parts:
                search_results = await self.vector_store.search_similar(
                    " ".join(query_parts), top_k=3
                )
                if search_results:
                    context_parts.append("\n相关上下文片段:")
                    for result in search_results:
                        context_parts.append(f"[片段]\n{result['text'][:300]}...")

            return "\n".join(context_parts)

        except Exception as e:
            logger.error(f"获取上下文失败: {e}")
            return "\n".join(context_parts) if context_parts else ""

    async def check_consistency(self, script_id: str, new_content: str,
                                 characters: List[str]) -> Dict[str, Any]:
        """检查新内容与已有剧本的一致性"""
        if not self._initialized:
            await self.initialize()

        logger.info(f"检查剧本一致性: {script_id}")

        inconsistencies = []

        try:
            # 1. 检查角色是否存在
            for char_name in characters:
                characters_found = await self.storage.search_by_attribute("CHARACTER", "name", char_name)
                if not characters_found:
                    inconsistencies.append({
                        "type": "unknown_character",
                        "message": f"未知角色: {char_name}",
                        "suggestion": f"请确认角色 '{char_name}' 的名字是否正确，或在之前的剧本中添加该角色"
                    })

            # 2. 检查地点一致性
            current_locations = await self.storage.get_entities_by_type("LOCATION")
            current_location_names = [loc.name for loc in current_locations]

            # 简单的地点匹配（实际应使用更复杂的语义匹配）
            import re
            found_locations = []
            for loc in current_locations:
                if loc.name in new_content:
                    found_locations.append(loc.name)

            # 3. 检查情感一致性
            emotions = await self.storage.get_entities_by_type("EMOTION")
            if emotions:
                emotion_names = [e.name for e in emotions]
                for emotion in emotion_names:
                    if emotion in new_content:
                        # 检查情感是否与角色一致
                        for char_name in characters:
                            consistency_info = await self.get_character_consistency(char_name, script_id)
                            # 这里可以添加更复杂的情感一致性检查

            return {
                "script_id": script_id,
                "is_consistent": len(inconsistencies) == 0,
                "inconsistencies": inconsistencies,
                "checked_characters": characters,
                "found_locations": found_locations
            }

        except Exception as e:
            logger.error(f"一致性检查失败: {e}")
            return {
                "script_id": script_id,
                "is_consistent": True,
                "inconsistencies": [],
                "error": str(e)
            }

    async def generate_scene_context(self, script_id: str, scene_number: int,
                                      scene_content: str) -> SceneContext:
        """生成场景上下文"""
        if not self._initialized:
            await self.initialize()

        try:
            # 提取场景信息
            characters = []
            setting = ""
            key_events = []
            emotional_tone = ""

            # 从存储的实体中提取
            scene_entities = await self.storage.search_by_attribute("CHARACTER", "scene", scene_number)
            characters = [e.name for e in scene_entities]

            # 从向量存储中获取场景信息
            scene_results = await self.vector_store.search_similar(
                f"scene {scene_number}", top_k=1
            )
            if scene_results:
                # 简单解析（实际应使用 LLM 提取）
                setting = scene_results[0]["text"][:100]

            return SceneContext(
                scene_id=f"{script_id}_scene_{scene_number}",
                script_id=script_id,
                scene_number=scene_number,
                setting=setting,
                characters=characters,
                key_events=key_events,
                emotional_tone=emotional_tone
            )

        except Exception as e:
            logger.error(f"生成场景上下文失败: {e}")
            return SceneContext(
                scene_id=f"{script_id}_scene_{scene_number}",
                script_id=script_id,
                scene_number=scene_number,
                setting="",
                characters=[],
                key_events=[],
                emotional_tone=""
            )


# 全局实例
_graphrag_service_instance: Optional[GraphRagService] = None


async def get_graphrag_service() -> GraphRagService:
    """获取 GraphRag 服务实例（单例模式）"""
    global _graphrag_service_instance

    if _graphrag_service_instance is None:
        _graphrag_service_instance = GraphRagService()
        await _graphrag_service_instance.initialize()

    return _graphrag_service_instance
