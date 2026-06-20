import logging
from typing import Dict, Any, Optional, List
import re
import asyncio
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.callbacks.base import BaseCallbackHandler

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

    async def generate_shots(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """使用DeepSeek生成镜头级分镜"""
        if not self._initialized:
            await self.initialize()

        try:
            logger.info(f"开始生成镜头级分镜: {request.get('title', '未命名剧本')}")

            # 尝试从缓存获取
            cache_key = f"shots:{request.get('title','')}:{hash(request.get('script','')[:200])}"
            if self.cache_service:
                cached = await self.cache_service.get_cached_storyboard(request)
                if cached and cached.get("episodes"):
                    logger.info("缓存命中: 镜头分镜生成结果")
                    return cached

            logger.info("缓存未命中，调用AI生成镜头级分镜...")

            # 构建提示
            system_prompt = self._build_shot_system_prompt(request)
            human_prompt = self._build_shot_human_prompt(request)

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]

            # 调用LLM
            logger.info("调用DeepSeek LLM生成镜头级分镜...")
            response = await self.llm.ainvoke(messages)
            shot_content = response.content

            # 解析JSON格式的镜头分镜
            shot_data = self._parse_shots(shot_content, request)

            # 缓存结果
            if self.cache_service and shot_data.get("episodes"):
                await self.cache_service.cache_storyboard_generation(request, shot_data)
                logger.info("镜头分镜生成结果已缓存")

            total_shots = sum(len(ep.get("shots", [])) for ep in shot_data.get("episodes", []))
            logger.info(f"镜头分镜生成完成，共 {len(shot_data.get('episodes', []))} 集，{total_shots} 个镜头")
            return shot_data

        except Exception as e:
            logger.error(f"镜头分镜生成失败: {e}")
            raise

    def _build_shot_system_prompt(self, request: Dict[str, Any]) -> str:
        """构建镜头级分镜系统提示词"""
        style = request.get('style', '写实风格')
        scene_refs = request.get('sceneRefs', [])
        character_names = request.get('characterNames', [])
        episode_count = request.get('episodeCount', 1)

        scene_refs_str = "、".join(scene_refs) if scene_refs else "由AI根据剧本自动推断"
        character_names_str = "、".join(character_names) if character_names else "由AI根据剧本自动推断"

        return f"""你是一个专业的影视分镜师，擅长将剧本拆分为详细的镜头级分镜脚本。

## 创作要求
1. 分镜风格: {style}
2. 目标平台: 短视频平台
3. 节奏: 快节奏、强冲突、视觉冲击力强
4. 预计集数: {episode_count} 集

## 镜头类型说明
你需要根据剧情需要，合理使用以下镜头类型（中文命名）:
- 远景: 展示大环境、场景全貌、人物与环境关系
- 全景: 人物全身，展示人物动作和空间关系
- 中景: 人物膝盖以上，适合对话和互动场景
- 近景: 人物胸部以上，突出表情和情绪
- 特写: 局部细节，如眼睛、手部、物品
- 大特写: 极致细节，强化情感冲击力
- 过肩镜头: 从角色肩后拍摄，增强代入感

## 摄像机角度选项
- 正面平视: 客观中性视角
- 俯视: 表现渺小、弱势、压抑
- 仰视: 表现高大、强势、威严
- 侧面: 表现旁观、疏离
- 斜角: 表现不安、紧张
- 跟踪拍摄: 跟随人物移动
- 摇镜头: 环境展示或视线转移

## 可用场景参考
{scene_refs_str}

## 可用角色参考
{character_names_str}

## 输出格式
严格按照JSON格式输出，每个镜头必须包含：
- number: 镜头编号（全局递增，跨集连续编号）
- shotType: 镜头类型（使用上述中文命名）
- duration: 时长秒数（1-60秒）
- cameraAngle: 摄像机角度
- sceneRef: 关联场景名称
- characters: 出场的角色名称数组
- description: 画面描述（构图、灯光、色彩、氛围）
- dialogue: 对白/旁白内容
- soundEffects: 音效数组
- music: 背景音乐描述
- notes: 备注

每集应包含6-12个镜头，确保镜头节奏紧凑。

输出JSON格式:
{{
  "episodes": [
    {{
      "id": "ep-1",
      "title": "第1集 - 标题",
      "number": 1,
      "description": "本集概要",
      "shots": [
        {{
          "id": 1,
          "number": 1,
          "shotType": "远景",
          "duration": 5,
          "cameraAngle": "正面平视",
          "sceneRef": "场景名称",
          "characters": ["角色1"],
          "description": "画面描述...",
          "dialogue": "对白内容...",
          "soundEffects": ["环境音"],
          "music": "轻柔钢琴曲",
          "notes": "备注..."
        }}
      ]
    }}
  ]
}}"""

    def _build_shot_human_prompt(self, request: Dict[str, Any]) -> str:
        """构建镜头级分镜用户提示词"""
        title = request.get('title', '未命名剧本')
        script = request.get('script', '')
        episode_count = request.get('episodeCount', 1)

        # 截断剧本避免超出token限制
        max_script_chars = 4000
        script_truncated = script[:max_script_chars]
        if len(script) > max_script_chars:
            script_truncated += "\n\n...(剧本内容已截断)..."

        return f"""请将以下剧本拆分为镜头级分镜脚本。

剧本标题: {title}

剧本内容:
{script_truncated}

请根据剧本内容，将每一集拆分为详细的镜头分镜。每个镜头必须包含画面描述、镜头类型、时长、摄像机角度、关联场景、出场角色、对白、音效、背景音乐和备注。

要求:
1. 共 {episode_count} 集，每集6-12个镜头
2. 镜头类型在 远景/全景/中景/近景/特写/大特写/过肩镜头 中选择，根据剧情合理分配
3. 时长分配合理: 远景3-8秒, 全景4-10秒, 中景5-15秒, 近景3-8秒, 特写2-5秒
4. 画面描述要具体: 包含构图方式、光线氛围、色彩基调、人物位置关系
5. 对白要口语化，符合角色性格
6. 镜头编号全局递增（第2集镜头从第1集最后一个镜头编号+1开始）
7. 严格按JSON格式输出，将所有数据包裹在顶层 {{}} 中"""

    def _parse_shots(self, content: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """解析镜头级分镜JSON输出"""
        import json

        try:
            # 提取JSON部分
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)

                # 验证并标准化输出
                if isinstance(data, dict):
                    episodes = data.get("episodes", [])
                    if episodes and isinstance(episodes, list):
                        normalized_episodes = []
                        shot_counter = 0
                        for ep_idx, ep in enumerate(episodes):
                            ep_id = ep.get("id", f"ep-{ep_idx + 1}")
                            ep_title = ep.get("title", f"第{ep_idx + 1}集")
                            ep_number = ep.get("number", ep_idx + 1)
                            ep_desc = ep.get("description", "")
                            shots = ep.get("shots", [])

                            normalized_shots = []
                            for s_idx, s in enumerate(shots):
                                shot_counter += 1
                                normalized_shots.append({
                                    "id": s.get("id", shot_counter),
                                    "number": s.get("number", shot_counter),
                                    "shotType": s.get("shotType", "中景"),
                                    "duration": int(s.get("duration", 5)),
                                    "cameraAngle": s.get("cameraAngle", "正面平视"),
                                    "sceneRef": s.get("sceneRef", ""),
                                    "characters": s.get("characters", []) if isinstance(s.get("characters"), list) else [],
                                    "description": s.get("description", ""),
                                    "dialogue": s.get("dialogue", ""),
                                    "soundEffects": s.get("soundEffects", []) if isinstance(s.get("soundEffects"), list) else [],
                                    "music": s.get("music", ""),
                                    "notes": s.get("notes", ""),
                                })

                            normalized_episodes.append({
                                "id": ep_id,
                                "title": ep_title,
                                "number": ep_number,
                                "shots": normalized_shots,
                                "description": ep_desc,
                            })

                        return {
                            "episodes": normalized_episodes,
                            "metadata": {
                                "generated_by": "deepseek-shot-division",
                                "style": request.get('style', '写实风格'),
                                "total_episodes": len(normalized_episodes),
                                "total_shots": sum(len(ep["shots"]) for ep in normalized_episodes),
                            }
                        }

            # JSON解析失败
            logger.warning("JSON解析失败，原始响应前200字符: %s", content[:200])
            return self._fallback_parse_shots(content, request)

        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析异常: {e}，尝试备用解析")
            return self._fallback_parse_shots(content, request)
        except Exception as e:
            logger.error(f"镜头分镜解析失败: {e}")
            return self._fallback_parse_shots(content, request)

    def _fallback_parse_shots(self, content: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """备用解析：当JSON解析失败时，从文本中提取镜头信息"""
        logger.info("使用备用解析方式解析镜头分镜...")

        shots = []
        shot_id = 0

        # 检测镜头标记：镜头 N、Shot N、N. 等
        shot_pattern = re.compile(r'(?:镜头|Shot)\s*(\d+)[\s:：]*(.+?)(?=(?:镜头|Shot)\s*\d+|$)', re.IGNORECASE | re.DOTALL)
        matches = shot_pattern.findall(content)

        if not matches:
            # 更宽泛的匹配：按行拆分，检测编号
            lines = content.strip().split('\n')
            current_shot = None
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # 检测以数字开头的行
                num_match = re.match(r'^(\d+)[\.\、\)）]\s*(.+)', line)
                if num_match:
                    if current_shot:
                        shots.append(current_shot)
                    shot_id += 1
                    current_shot = self._create_default_shot(shot_id, shot_id, line)
                elif current_shot:
                    # 追加到当前镜头的描述
                    if len(current_shot.get("description", "")) < 200:
                        current_shot["description"] += " " + line
            if current_shot:
                shots.append(current_shot)

        if matches:
            for match in matches:
                shot_id += 1
                num = int(match[0]) if match[0].isdigit() else shot_id
                detail = match[1].strip()
                shots.append(self._create_default_shot(shot_id, num, detail))

        # 如果还是没有，返回一个默认镜头
        if not shots:
            shot_id = 1
            shots.append({
                "id": 1, "number": 1, "shotType": "中景", "duration": 5,
                "cameraAngle": "正面平视", "sceneRef": "", "characters": [],
                "description": content[:200].strip() or "无法解析的镜头内容",
                "dialogue": "", "soundEffects": [], "music": "", "notes": "AI生成结果解析失败，请手动编辑"
            })

        return {
            "episodes": [{
                "id": "ep-1",
                "title": request.get('title', '第1集'),
                "number": 1,
                "shots": shots,
                "description": "自动生成的分镜",
            }],
            "metadata": {
                "generated_by": "fallback-parser",
                "style": request.get('style', '写实风格'),
            }
        }

    def _create_default_shot(self, shot_id: int, number: int, description: str) -> Dict[str, Any]:
        """创建默认镜头结构"""
        # 从描述中尝试推断镜头类型
        shot_type = "中景"
        if any(kw in description for kw in ["特写", "Close", "close", "细节", "眼神", "手指"]):
            shot_type = "特写"
        elif any(kw in description for kw in ["远景", "Wide", "wide", "全景", "Full", "full", "全景", "环境"]):
            shot_type = "远景"
        elif any(kw in description for kw in ["近景", "Close-up", "close-up", "面部", "表情"]):
            shot_type = "近景"

        return {
            "id": shot_id,
            "number": number,
            "shotType": shot_type,
            "duration": 5,
            "cameraAngle": "正面平视",
            "sceneRef": "",
            "characters": [],
            "description": description[:300],
            "dialogue": "",
            "soundEffects": [],
            "music": "",
            "notes": "",
        }

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
