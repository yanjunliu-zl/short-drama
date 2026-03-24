import logging
from typing import Dict, Any, Optional
import asyncio
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from langchain.callbacks.base import BaseCallbackHandler

from app.core.config import settings
from app.services.cache_service import get_cache_service

logger = logging.getLogger(__name__)


class ScriptAICallbackHandler(BaseCallbackHandler):
    """AI回调处理器，用于跟踪剧本生成进度"""

    def __init__(self):
        self.current_step = 0
        self.total_steps = 4  # 生成步骤数
        self.progress_callbacks = []

    def on_llm_start(self, serialized: Dict[str, Any], prompts: list[str], **kwargs):
        """LLM开始处理时调用"""
        self.current_step += 1
        logger.info(f"AI生成步骤 {self.current_step}/{self.total_steps}: {prompts[0][:50]}...")

    def on_llm_end(self, response, **kwargs):
        """LLM处理结束时调用"""
        logger.info(f"AI生成步骤 {self.current_step}/{self.total_steps} 完成")


class AIService:
    """AI服务，封装LangChain和LangGraph功能，支持缓存"""

    def __init__(self):
        self.llm = None
        self.callback_handler = None
        self.cache_service = None
        self._initialized = False

    async def initialize(self):
        """初始化AI服务"""
        if self._initialized:
            return

        try:
            logger.info("初始化AI服务...")

            # 初始化缓存服务
            self.cache_service = await get_cache_service()

            # 初始化回调处理器
            self.callback_handler = ScriptAICallbackHandler()

            # 配置AI模型 - 优先使用DeepSeek，其次OpenAI
            llm_kwargs = {
                "model_name": settings.MODEL_NAME,
                "temperature": settings.OPENAI_TEMPERATURE,
                "max_tokens": settings.OPENAI_MAX_TOKENS,
                "timeout": settings.OPENAI_TIMEOUT,
                "streaming": False,
            }

            # 优先使用DeepSeek
            if settings.DEEPSEEK_API_KEY:
                llm_kwargs["openai_api_key"] = settings.DEEPSEEK_API_KEY
                llm_kwargs["openai_api_base"] = settings.DEEPSEEK_API_BASE
                llm_kwargs["model_name"] = settings.DEEPSEEK_MODEL
                logger.info(f"使用DeepSeek模型: {settings.DEEPSEEK_MODEL}")
            elif settings.OPENAI_API_KEY:
                llm_kwargs["openai_api_key"] = settings.OPENAI_API_KEY
                if settings.OPENAI_API_BASE:
                    llm_kwargs["openai_api_base"] = settings.OPENAI_API_BASE
                logger.info(f"使用OpenAI模型: {settings.MODEL_NAME}")
            else:
                raise ValueError("未配置AI API密钥，请设置DEEPSEEK_API_KEY或OPENAI_API_KEY环境变量")

            # 创建LLM实例
            self.llm = ChatOpenAI(**llm_kwargs)

            # 配置LangChain追踪
            if settings.LANGCHAIN_TRACING and settings.LANGCHAIN_API_KEY:
                import os
                os.environ["LANGCHAIN_TRACING_V2"] = "true"
                os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT or "https://api.smith.langchain.com"
                os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
                os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT or "shortdrama-script-service"

            self._initialized = True
            logger.info("AI服务初始化完成")

        except Exception as e:
            logger.error(f"AI服务初始化失败: {e}")
            raise

    async def generate_script(self, request: Dict[str, Any]) -> str:
        """使用LangChain生成剧本，支持缓存"""
        if not self._initialized:
            await self.initialize()

        try:
            logger.info(f"开始生成剧本: {request.get('title', '未命名剧本')}")

            # 尝试从缓存获取
            if self.cache_service:
                cached_script = await self.cache_service.get_cached_script(request)
                if cached_script:
                    logger.info("缓存命中: 剧本生成结果")
                    return cached_script

            logger.info("缓存未命中，调用AI生成...")

            # 构建系统提示
            system_prompt = self._build_system_prompt(request)
            human_prompt = self._build_human_prompt(request)

            # 创建消息链
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]

            # 调用LLM
            logger.info("调用LLM生成剧本...")
            response = await self.llm.ainvoke(messages)

            script_content = response.content

            # 缓存结果
            if self.cache_service:
                await self.cache_service.cache_script_generation(request, script_content)
                logger.info("剧本生成结果已缓存")

            logger.info(f"剧本生成完成，长度: {len(script_content)} 字符")
            return script_content

        except Exception as e:
            logger.error(f"剧本生成失败: {e}")
            raise

    def _build_system_prompt(self, request: Dict[str, Any]) -> str:
        """构建系统提示"""
        theme = request.get('theme', '爱情')
        length = request.get('length', '短篇')
        style = request.get('style', '浪漫喜剧')
        setting = request.get('setting', '现代都市')

        return f"""你是一个专业的剧本作家，专门创作{theme}主题的{style}剧本。

创作要求:
1. 剧本类型: {length}剧本
2. 故事背景: {setting}
3. 剧本风格: {style}
4. 目标观众: 短视频平台用户

剧本结构要求:
1. 必须有引人入胜的开场
2. 角色发展要有层次感
3. 冲突和转折要合理
4. 结局要符合{theme}主题

输出格式:
请按照标准的剧本格式输出，包括场景描述、角色对话和动作指示。
"""

    def _build_human_prompt(self, request: Dict[str, Any]) -> str:
        """构建用户提示"""
        title = request.get('title', '未命名剧本')
        characters = request.get('characters', [])
        additional_notes = request.get('additional_notes', '')

        character_str = "\n".join([f"- {char}" for char in characters]) if characters else "请自行设计2-3个主要角色"

        return f"""请创作一个名为《{title}》的剧本。

角色设定:
{character_str}

额外要求:
{additional_notes if additional_notes else '无特殊要求'}

请创作一个完整、吸引人且适合短视频平台的剧本。"""

    async def analyze_script_structure(self, script_content: str) -> Dict[str, Any]:
        """分析剧本结构，支持缓存"""
        if not self._initialized:
            await self.initialize()

        try:
            # 尝试从缓存获取
            if self.cache_service:
                cached_analysis = await self.cache_service.get_cached_analysis(script_content)
                if cached_analysis:
                    logger.info("缓存命中: 剧本分析结果")
                    return cached_analysis

            logger.info("缓存未命中，调用AI分析剧本结构...")

            prompt = f"""请分析以下剧本的结构:

{script_content[:1000]}...

请分析:
1. 主要场景数量
2. 角色数量
3. 故事节奏
4. 情感曲线
5. 建议改进点

请以JSON格式返回分析结果。"""

            messages = [
                SystemMessage(content="你是一个剧本分析师，擅长分析剧本结构和故事节奏。"),
                HumanMessage(content=prompt)
            ]

            response = await self.llm.ainvoke(messages)
            # 这里应该解析JSON，但简化处理
            analysis_result = {
                "analysis": response.content,
                "scenes_count": 4,  # 示例值
                "characters_count": 3,  # 示例值
                "pace": "适中",
            }

            # 缓存结果
            if self.cache_service:
                await self.cache_service.cache_script_analysis(script_content, analysis_result)
                logger.info("剧本分析结果已缓存")

            return analysis_result

        except Exception as e:
            logger.error(f"剧本分析失败: {e}")
            return {"error": str(e)}

    async def optimize_script(self, script_content: str, feedback: str) -> str:
        """优化剧本，支持缓存"""
        if not self._initialized:
            await self.initialize()

        try:
            # 尝试从缓存获取
            if self.cache_service:
                cached_optimization = await self.cache_service.get_cached_optimization(script_content, feedback)
                if cached_optimization:
                    logger.info("缓存命中: 剧本优化结果")
                    return cached_optimization

            logger.info("缓存未命中，调用AI优化剧本...")

            prompt = f"""请根据以下反馈优化剧本:

反馈: {feedback}

原剧本:
{script_content[:2000]}...

优化要求:
1. 保持原故事主线
2. 改进角色对话
3. 增强情感表达
4. 优化场景转换

请返回优化后的完整剧本。"""

            messages = [
                SystemMessage(content="你是一个剧本优化专家，擅长改进剧本的对话和情感表达。"),
                HumanMessage(content=prompt)
            ]

            response = await self.llm.ainvoke(messages)
            optimized_script = response.content

            # 缓存结果
            if self.cache_service:
                await self.cache_service.cache_script_optimization(script_content, feedback, optimized_script)
                logger.info("剧本优化结果已缓存")

            return optimized_script

        except Exception as e:
            logger.error(f"剧本优化失败: {e}")
            raise