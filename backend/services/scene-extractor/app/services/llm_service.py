import logging
from typing import Dict, Any, Optional
import asyncio

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.callbacks.base import BaseCallbackHandler

from app.core.config import settings

logger = logging.getLogger(__name__)


class SceneExtractorCallbackHandler(BaseCallbackHandler):
    """AI回调处理器，用于跟踪场景抽取进度"""

    def __init__(self):
        self.current_step = 0
        self.total_steps = 3
        self.progress_callbacks = []

    def on_llm_start(self, serialized: Dict[str, Any], prompts: list[str], **kwargs):
        """LLM开始处理时调用"""
        self.current_step += 1
        logger.info(f"AI抽取步骤 {self.current_step}/{self.total_steps}: 开始处理")

    def on_llm_end(self, response, **kwargs):
        """LLM处理结束时调用"""
        logger.info(f"AI抽取步骤 {self.current_step}/{self.total_steps} 完成")


class LLMService:
    """LLM服务，封装DeepSeek和LangChain功能"""

    def __init__(self):
        self.llm = None
        self.callback_handler = None
        self._initialized = False

    async def initialize(self):
        """初始化LLM服务"""
        if self._initialized:
            return

        try:
            logger.info("初始化LLM服务...")

            # 初始化回调处理器
            self.callback_handler = SceneExtractorCallbackHandler()

            # 配置AI模型 - 使用DeepSeek
            llm_kwargs = {
                "model_name": settings.DEEPSEEK_MODEL,
                "temperature": settings.DEEPSEEK_TEMPERATURE,
                "max_tokens": settings.DEEPSEEK_MAX_TOKENS,
                "timeout": 60,
                "streaming": False,
            }

            # 使用DeepSeek
            if settings.DEEPSEEK_API_KEY:
                llm_kwargs["openai_api_key"] = settings.DEEPSEEK_API_KEY
                llm_kwargs["openai_api_base"] = settings.DEEPSEEK_API_BASE
                logger.info(f"使用DeepSeek模型: {settings.DEEPSEEK_MODEL}")
            else:
                raise ValueError("未配置DEEPSEEK_API_KEY环境变量")

            # 创建LLM实例
            self.llm = ChatOpenAI(**llm_kwargs)

            # 配置LangChain追踪
            if settings.LANGCHAIN_TRACING and settings.LANGCHAIN_API_KEY:
                import os
                os.environ["LANGCHAIN_TRACING_V2"] = "true"
                os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT or "https://api.smith.langchain.com"
                os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
                os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT or "scene-extractor"

            self._initialized = True
            logger.info("LLM服务初始化完成")

        except Exception as e:
            logger.error(f"LLM服务初始化失败: {e}")
            raise

    async def extract_scenes(self, script_content: str) -> Dict[str, Any]:
        """从剧本中抽取场景信息"""
        if not self._initialized:
            await self.initialize()

        try:
            logger.info("开始抽取场景信息...")

            prompt = f"""请从以下剧本中抽取所有场景信息。

剧本内容:
{script_content[:8000]}

请以JSON格式返回以下信息:
- scenes: 场景列表，每个场景包含:
  - scene_id: 场景编号
  - location: 场景地点
  - time_of_day: 时间（白天/夜晚/清晨/傍晚）
  - description: 场景描述
  - characters: 出现的角色列表
  - props: 出现的道具列表
  - action_summary: 场景动作摘要

请确保:
1. 每个场景有唯一的scene_id
2. location尽可能具体
3. characters和props使用原始剧本中的名称
4. action_summary简洁描述场景主要动作

返回格式:
{{
  "scenes": [
    {{
      "scene_id": 1,
      "location": "咖啡馆内",
      "time_of_day": "白天",
      "description": "温馨舒适的咖啡馆，有木质桌椅",
      "characters": ["角色A", "角色B"],
      "props": ["咖啡杯", "笔记本电脑"],
      "action_summary": "角色A和B在咖啡馆见面交谈"
    }}
  ]
}}"""

            messages = [
                SystemMessage(content="你是一个专业的剧本分析师，擅长从剧本中抽取场景、角色和道具信息。请以JSON格式返回结果。"),
                HumanMessage(content=prompt)
            ]

            response = await self.llm.ainvoke(messages)
            result_text = response.content

            # 解析JSON结果
            result = self._parse_extraction_result(result_text)
            logger.info(f"场景抽取完成，共找到 {len(result.get('scenes', []))} 个场景")
            return result

        except Exception as e:
            logger.error(f"场景抽取失败: {e}")
            raise

    async def extract_characters(self, script_content: str) -> Dict[str, Any]:
        """从剧本中抽取角色信息"""
        if not self._initialized:
            await self.initialize()

        try:
            logger.info("开始抽取角色信息...")

            prompt = f"""请从以下剧本中抽取所有角色信息。

剧本内容:
{script_content[:8000]}

请以JSON格式返回以下信息:
- characters: 角色列表，每个角色包含:
  - character_id: 角色编号
  - name: 角色名称
  - description: 角色描述
  - age: 年龄（如未知则为null）
  - personality: 性格特点
  - clothing: 衣着描述
  - role: 角色类型（主角/配角/次要角色）

返回格式:
{{
  "characters": [
    {{
      "character_id": 1,
      "name": "张三",
      "description": "男主角",
      "age": 25,
      "personality": "阳光开朗",
      "clothing": "休闲装",
      "role": "主角"
    }}
  ]
}}"""

            messages = [
                SystemMessage(content="你是一个专业的剧本分析师，擅长从剧本中抽取角色信息。请以JSON格式返回结果。"),
                HumanMessage(content=prompt)
            ]

            response = await self.llm.ainvoke(messages)
            result_text = response.content

            result = self._parse_extraction_result(result_text)
            logger.info(f"角色抽取完成，共找到 {len(result.get('characters', []))} 个角色")
            return result

        except Exception as e:
            logger.error(f"角色抽取失败: {e}")
            raise

    async def extract_props(self, script_content: str) -> Dict[str, Any]:
        """从剧本中抽取道具信息"""
        if not self._initialized:
            await self.initialize()

        try:
            logger.info("开始抽取道具信息...")

            prompt = f"""请从以下剧本中抽取所有道具信息。

剧本内容:
{script_content[:8000]}

请以JSON格式返回以下信息:
- props: 道具列表，每个道具包含:
  - prop_id: 道具编号
  - name: 道具名称
  - description: 道具描述
  - category: 道具分类（家具/电器/日常用品/特殊道具）
  - usage: 用途说明
  - scenes: 出现的场景ID列表

返回格式:
{{
  "props": [
    {{
      "prop_id": 1,
      "name": "咖啡杯",
      "description": "白色陶瓷咖啡杯",
      "category": "日常用品",
      "usage": "用于喝咖啡",
      "scenes": [1, 2]
    }}
  ]
}}"""

            messages = [
                SystemMessage(content="你是一个专业的剧本分析师，擅长从剧本中抽取道具信息。请以JSON格式返回结果。"),
                HumanMessage(content=prompt)
            ]

            response = await self.llm.ainvoke(messages)
            result_text = response.content

            result = self._parse_extraction_result(result_text)
            logger.info(f"道具抽取完成，共找到 {len(result.get('props', []))} 个道具")
            return result

        except Exception as e:
            logger.error(f"道具抽取失败: {e}")
            raise

    async def extract_all(self, script_content: str) -> Dict[str, Any]:
        """同时抽取场景、角色和道具"""
        if not self._initialized:
            await self.initialize()

        try:
            logger.info("开始抽取场景、角色和道具...")

            prompt = f"""请从以下剧本中抽取场景、角色和道具信息。

剧本内容:
{script_content[:8000]}

请以JSON格式返回以下信息:
- scenes: 场景列表
- characters: 角色列表
- props: 道具列表

每个场景包含:
- scene_id: 场景编号
- location: 场景地点
- time_of_day: 时间（白天/夜晚/清晨/傍晚）
- description: 场景描述
- characters: 出现的角色列表
- props: 出现的道具列表
- action_summary: 场景动作摘要

每个角色包含:
- character_id: 角色编号
- name: 角色名称
- description: 角色描述
- age: 年龄
- personality: 性格特点
- clothing: 衣着描述
- role: 角色类型

每个道具包含:
- prop_id: 道具编号
- name: 道具名称
- description: 道具描述
- category: 道具分类
- usage: 用途说明
- scenes: 出现的场景ID列表

返回完整的JSON格式结果。"""

            messages = [
                SystemMessage(content="你是一个专业的剧本分析师，擅长从剧本中抽取场景、角色和道具信息。请以JSON格式返回结果。"),
                HumanMessage(content=prompt)
            ]

            response = await self.llm.ainvoke(messages)
            result_text = response.content

            result = self._parse_extraction_result(result_text)
            logger.info(f"全面抽取完成: {len(result.get('scenes', []))} 个场景, {len(result.get('characters', []))} 个角色, {len(result.get('props', []))} 个道具")
            return result

        except Exception as e:
            logger.error(f"全面抽取失败: {e}")
            raise

    def _parse_extraction_result(self, result_text: str) -> Dict[str, Any]:
        """解析抽取结果"""
        import json
        import re

        try:
            # 尝试直接解析JSON
            if result_text.startswith('{'):
                return json.loads(result_text)
        except json.JSONDecodeError:
            pass

        try:
            # 尝试从Markdown代码块中提取JSON
            json_match = re.search(r'```json\s*(.*?)\s*```', result_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
        except (json.JSONDecodeError, AttributeError):
            pass

        try:
            # 尝试从任意代码块中提取JSON
            json_match = re.search(r'```\s*(.*?)\s*```', result_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
        except (json.JSONDecodeError, AttributeError):
            pass

        # 如果解析失败，返回空结果
        logger.warning("无法解析JSON结果，返回空结构")
        return {"scenes": [], "characters": [], "props": []}
