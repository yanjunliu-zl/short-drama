import logging
from typing import Dict, Any, Optional, List
import re
import asyncio
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from langchain.callbacks.base import BaseCallbackHandler

from app.core.config import settings
from app.services.cache_service import get_storyboard_cache_service

logger = logging.getLogger(__name__)


class StoryboardAICallbackHandler(BaseCallbackHandler):
    """AI回调处理器，用于跟踪分镜生成进度"""

    def __init__(self):
        self.current_step = 0
        self.total_steps = 3
        self.progress_callbacks = []

    def on_llm_start(self, serialized: Dict[str, Any], prompts: list[str], **kwargs):
        self.current_step += 1
        logger.info(f"AI生成步骤 {self.current_step}/{self.total_steps}: {prompts[0][:50]}...")

    def on_llm_end(self, response, **kwargs):
        logger.info(f"AI生成步骤 {self.current_step}/{self.total_steps} 完成")


class StoryboardAIService:
    """分镜AI服务，封装LangChain和DeepSeek LLM"""

    def __init__(self):
        self.llm = None
        self.callback_handler = None
        self.cache_service = None
        self._initialized = False

    async def initialize(self):
        """初始化分镜AI服务"""
        if self._initialized:
            return

        try:
            logger.info("初始化分镜AI服务...")

            # 初始化缓存服务
            try:
                self.cache_service = await get_storyboard_cache_service()
                logger.info("缓存服务初始化成功")
            except Exception as e:
                logger.warning(f"缓存服务初始化失败，将禁用缓存: {e}")
                self.cache_service = None

            # 初始化回调处理器
            self.callback_handler = StoryboardAICallbackHandler()

            # 配置AI模型 - 使用DeepSeek
            llm_kwargs = {
                "model_name": settings.DEEPSEEK_MODEL,
                "temperature": settings.STORYBOARD_TEMPERATURE,
                "max_tokens": settings.STORYBOARD_MAX_TOKENS,
                "timeout": settings.STORYBOARD_TIMEOUT,
                "streaming": False,
                "openai_api_key": settings.DEEPSEEK_API_KEY,
                "openai_api_base": settings.DEEPSEEK_API_BASE,
            }

            logger.info(f"使用DeepSeek模型: {settings.DEEPSEEK_MODEL}")

            # 创建LLM实例
            self.llm = ChatOpenAI(**llm_kwargs)

            # 配置LangChain追踪
            if settings.LANGCHAIN_TRACING and settings.LANGCHAIN_API_KEY:
                import os
                os.environ["LANGCHAIN_TRACING_V2"] = "true"
                os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT or "https://api.smith.langchain.com"
                os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
                os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT or "shortdrama-storyboard-service"

            self._initialized = True
            logger.info("分镜AI服务初始化完成")

        except Exception as e:
            logger.error(f"分镜AI服务初始化失败: {e}")
            raise

    async def generate_storyboard(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """使用DeepSeek生成分镜"""
        if not self._initialized:
            await self.initialize()

        try:
            logger.info(f"开始生成分镜: {request.get('title', '未命名剧本')}")

            # 尝试从缓存获取
            if self.cache_service:
                cached_storyboard = await self.cache_service.get_cached_storyboard(request)
                if cached_storyboard:
                    logger.info("缓存命中: 分镜生成结果")
                    return cached_storyboard

            logger.info("缓存未命中，调用AI生成分镜...")

            # 构建系统提示
            system_prompt = self._build_system_prompt(request)
            human_prompt = self._build_human_prompt(request)

            # 创建消息链
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]

            # 调用LLM
            logger.info("调用DeepSeek LLM生成分镜...")
            response = await self.llm.ainvoke(messages)

            storyboard_content = response.content

            # 解析JSON格式的分镜
            storyboard_data = self._parse_storyboard(storyboard_content, request)

            # 缓存结果
            if self.cache_service:
                await self.cache_service.cache_storyboard_generation(request, storyboard_data)
                logger.info("分镜生成结果已缓存")

            logger.info(f"分镜生成完成，场景数量: {len(storyboard_data.get('scenes', []))}")
            return storyboard_data

        except Exception as e:
            logger.error(f"分镜生成失败: {e}")
            raise

    async def analyze_script_for_storyboard(self, script_content: str) -> Dict[str, Any]:
        """分析剧本，识别分镜节点"""
        if not self._initialized:
            await self.initialize()

        try:
            prompt = f"""请分析以下剧本的分镜节点:

{script_content[:2000]}

请分析:
1. 场景切换点
2. 镜头建议（特写、中景、全景等）
3. 角色位置关系
4. 关键动作节点

请以JSON格式返回分析结果。"""

            messages = [
                SystemMessage(content="你是一个专业的分镜师，擅长将剧本转换成分镜脚本。"),
                HumanMessage(content=prompt)
            ]

            response = await self.llm.ainvoke(messages)

            return {
                "analysis": response.content,
                "status": "success"
            }

        except Exception as e:
            logger.error(f"剧本分析失败: {e}")
            return {"error": str(e)}

    def _build_system_prompt(self, request: Dict[str, Any]) -> str:
        """构建系统提示"""
        style = request.get('style', '写实风格')
        theme = request.get('theme', '爱情')
        scene_count = request.get('scene_count', 0)

        return f"""你是一个专业的分镜师，专门创作{theme}主题的分镜脚本。

创作要求:
1. 分镜风格: {style}
2. 目标受众: 短视频平台用户
3. 节奏感: 快节奏、强冲突

分镜格式要求:
1. 使用JSON格式输出
2. 包含场景编号、描述、角色、对话、镜头指示等元素
3. 每个场景要有明确的视觉元素和情绪表达

{"指定场景数量: " + str(scene_count) + "个" if scene_count > 0 else "根据剧本内容自动判断场景数量，通常3-6个场景"}

输出格式示例:
{{"scenes": [
    {{"scene_number": 1, "description": "场景描述", "characters": ["角色1", "角色2"], "dialogue": ["对话1", "对话2"], "camera_directions": ["镜头指示"], "setting": "场景设定", "emotions": ["情绪"], "visual_elements": ["视觉元素"]}}
]}}"""

    def _build_human_prompt(self, request: Dict[str, Any]) -> str:
        """构建用户提示"""
        title = request.get('title', '未命名剧本')
        script = request.get('script', '')

        return f"""请将以下剧本转换成分镜脚本。

剧本标题: {title}

剧本内容:
{script[:3000]}

请根据剧本内容，创建详细的分镜脚本，包括每个场景的视觉描述、角色位置、对话、镜头运动等元素。

要求:
1. 确保分镜节奏紧凑，适合短视频平台
2. 每个场景要有明确的视觉焦点
3. 对话要简洁有力
4. 加入适当的镜头语言指示"""

    def _parse_storyboard(self, content: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """解析分镜内容"""
        try:
            # 尝试解析JSON
            import json
            # 提取JSON部分
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                data = json.loads(json_match.group())
                if isinstance(data, dict):
                    return data
        except Exception as e:
            logger.warning(f"JSON解析失败: {e}，尝试备用解析方式")

        # 备用解析方式：非JSON格式
        scenes = []
        content_lines = content.split('\n')

        current_scene = {
            "scene_number": 1,
            "description": "",
            "characters": [],
            "dialogue": [],
            "camera_directions": [],
            "setting": request.get('setting', '现代都市'),
            "emotions": [],
            "visual_elements": []
        }

        scene_num = 1
        for line in content_lines:
            line = line.strip()
            if not line:
                continue

            # 检测场景切换
            if re.match(r'(场景|镜头|S\d+)', line, re.IGNORECASE):
                if current_scene.get("description"):
                    scenes.append(current_scene)
                    scene_num += 1
                    current_scene = {
                        "scene_number": scene_num,
                        "description": "",
                        "characters": [],
                        "dialogue": [],
                        "camera_directions": [],
                        "setting": request.get('setting', '现代都市'),
                        "emotions": [],
                        "visual_elements": []
                    }

            # 解析描述
            if line.startswith(('描述', '场景描述', '画面')):
                current_scene["description"] = line.split(':', 1)[-1].strip() if ':' in line else line

            # 解析角色
            elif line.startswith(('角色', '人物')):
                char_str = line.split(':', 1)[-1].strip() if ':' in line else line
                current_scene["characters"] = [c.strip() for c in char_str.split(',') if c.strip()]

            # 解析对话
            elif line.startswith(('对话', '台词')):
                dialog_str = line.split(':', 1)[-1].strip() if ':' in line else line
                current_scene["dialogue"] = [d.strip() for d in dialog_str.split('|') if d.strip()]

            # 解析镜头
            elif line.startswith(('镜头', '拍摄')):
                cam_str = line.split(':', 1)[-1].strip() if ':' in line else line
                current_scene["camera_directions"] = [c.strip() for c in cam_str.split(',') if c.strip()]

        if current_scene.get("description"):
            scenes.append(current_scene)

        return {
            "title": request.get('title', '未命名剧本'),
            "theme": request.get('theme', ''),
            "scenes": scenes,
            "total_scenes": len(scenes),
            "metadata": {
                "generated_by": "deepseek-storyboard",
                "style": request.get('style', '写实风格')
            }
        }
