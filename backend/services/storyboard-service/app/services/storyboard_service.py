import logging
from typing import Dict, Any, Optional, List, AsyncGenerator
import re
import json
import asyncio
import time
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.callbacks.base import BaseCallbackHandler

from app.core.config import settings
from app.services.cache_service import get_storyboard_cache_service
from app.services.usage_tracker import track_llm_usage
from app.utils.sse import stream_tokens_from_llm, format_sse_event, EVENT_STAGE, EVENT_DONE
from app.utils.model_router import create_llm_client, get_active_provider, provider_is_healthy
from app.services.prompt_builder import PromptBuilder, ShotPromptInput
from app.services.cinematography_profiles import get_profile, list_profiles

# Map Chinese style names → cinematography profile IDs
_STYLE_TO_PROFILE: Dict[str, str] = {
    "写实风格": "classic-cinematic",
    "悬疑风格": "suspense-thriller",
    "悬疑": "suspense-thriller",
    "浪漫喜剧": "romantic-comedy",
    "喜剧": "romantic-comedy",
    "古装风格": "ancient-palace",
    "古风": "wuxia-classic",
    "武侠": "wuxia-classic",
    "科幻": "sci-fi-future",
    "赛博朋克": "cyberpunk-neon",
    "日系": "japanese-fresh",
    "纪实风格": "documentary",
    "家庭": "family-warmth",
    "民国": "republican-era",
    "港风": "hk-retro-90s",
}

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

            # Use ModelRouter for automatic provider fallback
            self.llm = create_llm_client(
                prefer="deepseek",
                timeout=settings.STORYBOARD_TIMEOUT,
            )
            logger.info(f"LLM provider: {get_active_provider()}")

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

        t0 = time.time()
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

            elapsed = time.time() - t0
            logger.info(f"分镜生成完成: {len(storyboard_data.get('scenes', []))}场景 耗时={elapsed:.1f}s")
            return storyboard_data

        except Exception as e:
            elapsed = time.time() - t0
            logger.error(f"分镜生成失败 (耗时={elapsed:.1f}s): {e}")
            raise

    async def generate_shots(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """使用DeepSeek生成镜头级分镜 — 逐集生成，超长集自动按场景分段"""
        if not self._initialized:
            await self.initialize()

        t0 = time.time()
        try:
            title = request.get('title', '未命名剧本')
            episode_count = len(request.get('episodeContents', []))
            script_len = len(request.get('script', ''))
            logger.info(f"开始生成镜头级分镜(逐集): {title} episodes={episode_count} script_len={script_len}")

            if self.cache_service:
                cached = await self.cache_service.get_cached_shots(request)
                if cached and cached.get("episodes"):
                    logger.info("缓存命中")
                    return cached

            # 优先使用前端传来的独立集内容，否则从剧本文本拆分
            episode_texts = request.get('episodeContents', [])
            if not episode_texts:
                episode_texts = self._split_script_to_episodes(request.get('script', ''))

            all_episodes = []
            global_shot_id = 0
            max_chars = settings.STORYBOARD_MAX_SCRIPT_CHARS

            for ep_idx, ep_text in enumerate(episode_texts):
                ep_num = ep_idx + 1

                # 超长集：按场景拆分为多段，逐段生成后合并
                if len(ep_text) > max_chars:
                    chunks = self._split_episode_to_scene_chunks(ep_text, max_chars)
                    logger.info(f"生成第{ep_num}集分镜... ({len(chunks)}段, 总{len(ep_text)}字)")
                    ep_shots = []
                    chunk_start_shot_id = global_shot_id

                    for chunk_idx, chunk_text in enumerate(chunks):
                        chunk_ep_request = {**request, 'script': chunk_text, 'episodeCount': 1,
                                            'maxScriptChars': max_chars}
                        system_prompt = self._build_shot_system_prompt(chunk_ep_request)
                        human_prompt = self._build_shot_human_prompt(chunk_ep_request)

                        try:
                            response = await self.llm.ainvoke([
                                SystemMessage(content=system_prompt),
                                HumanMessage(content=human_prompt)
                            ])
                            shot_data = self._parse_single_episode_shots(
                                response.content, ep_num, chunk_start_shot_id, request
                            )
                        except Exception as e:
                            logger.warning(f"第{ep_num}集第{chunk_idx+1}段AI生成失败: {e}，使用程序化分镜")
                            shot_data = self._programmatic_shots(chunk_text, ep_num, chunk_start_shot_id)

                        if shot_data.get("episodes"):
                            ep = shot_data["episodes"][0]
                            chunk_shots = ep.get("shots", [])
                            chunk_start_shot_id += len(chunk_shots)
                            ep_shots.append(ep)

                    # 合并本集所有分段
                    merged = self._merge_episode_shots(ep_shots, ep_num)
                    if merged.get("episodes"):
                        merged_ep = merged["episodes"][0]
                        global_shot_id += len(merged_ep.get("shots", []))
                        all_episodes.append(merged_ep)
                        logger.info(f"第{ep_num}集完成: {len(merged_ep.get('shots', []))}镜头 (合并{len(chunks)}段)")
                else:
                    logger.info(f"生成第{ep_num}集分镜... ({len(ep_text)}字)")
                    ep_request = {**request, 'script': ep_text, 'episodeCount': 1,
                                  'maxScriptChars': max_chars}
                    system_prompt = self._build_shot_system_prompt(ep_request)
                    human_prompt = self._build_shot_human_prompt(ep_request)

                    try:
                        response = await self.llm.ainvoke([
                            SystemMessage(content=system_prompt),
                            HumanMessage(content=human_prompt)
                        ])
                        shot_data = self._parse_single_episode_shots(response.content, ep_num, global_shot_id, request)
                    except Exception as e:
                        logger.warning(f"第{ep_num}集AI生成失败: {e}，使用程序化分镜")
                        shot_data = self._programmatic_shots(ep_text, ep_num, global_shot_id)

                    if shot_data.get("episodes"):
                        ep = shot_data["episodes"][0]
                        global_shot_id += len(ep.get("shots", []))
                        all_episodes.append(ep)

            # Enrich shots with 5-layer prompt builder + cinematography profiles
            style = request.get("style", "写实风格")
            all_episodes = self._enrich_all_shots(all_episodes, style)

            result = {"episodes": all_episodes}
            if self.cache_service and all_episodes:
                await self.cache_service.cache_shots_generation(request, result)

            total = sum(len(ep.get("shots", [])) for ep in all_episodes)
            elapsed = time.time() - t0
            logger.info(f"镜头分镜完成: {len(all_episodes)}集, {total}镜头 耗时={elapsed:.1f}s")
            # 记录 LLM 用量
            await track_llm_usage(
                user_id=request.get('user_id', ''),
                model_name="deepseek-chat",
                tokens_in=script_len,
                tokens_out=total * 200,  # 估计每个镜头 ~200 tokens 输出
                duration_ms=int(elapsed * 1000),
                endpoint="/shots/generate",
                service_name="storyboard-service",
            )
            return result

        except Exception as e:
            elapsed = time.time() - t0
            logger.error(f"镜头分镜生成失败 (耗时={elapsed:.1f}s): {e}")
            raise

    # ================================================================
    # Streaming methods (SSE token-by-token / stage-by-stage output)
    # ================================================================

    async def generate_storyboard_stream(self, request: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Stream storyboard generation as SSE 'token' events."""
        if not self._initialized:
            await self.initialize()
        system_prompt = self._build_system_prompt(request)
        human_prompt = self._build_human_prompt(request)
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)]
        async for sse_event in stream_tokens_from_llm(self.llm, messages):
            yield sse_event

    async def generate_shots_stream(self, request: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Stream shot-level storyboard generation with per-episode 'stage' events.

        Each episode emits a 'stage' event on start and completion.
        Final result emitted as a 'done' event.
        """
        if not self._initialized:
            await self.initialize()

        title = request.get('title', '未命名剧本')
        episode_texts = request.get('episodeContents', [])
        if not episode_texts:
            episode_texts = self._split_script_to_episodes(request.get('script', ''))

        max_chars = settings.STORYBOARD_MAX_SCRIPT_CHARS
        all_episodes = []
        global_shot_id = 0

        for ep_idx, ep_text in enumerate(episode_texts):
            ep_num = ep_idx + 1
            yield format_sse_event(
                {"episode": ep_num, "total": len(episode_texts), "stage": "generating_shots"},
                event=EVENT_STAGE,
            )

            ep_request = {**request, 'script': ep_text, 'episodeCount': 1, 'maxScriptChars': max_chars}
            try:
                response = await self.llm.ainvoke([
                    SystemMessage(content=self._build_shot_system_prompt(ep_request)),
                    HumanMessage(content=self._build_shot_human_prompt(ep_request))
                ])
                shot_data = self._parse_single_episode_shots(response.content, ep_num, global_shot_id, request)
            except Exception as e:
                logger.warning(f"第{ep_num}集AI生成失败: {e}，使用程序化分镜")
                shot_data = self._programmatic_shots(ep_text, ep_num, global_shot_id)

            if shot_data.get("episodes"):
                ep = shot_data["episodes"][0]
                global_shot_id += len(ep.get("shots", []))
                all_episodes.append(ep)

            yield format_sse_event(
                {"episode": ep_num, "shots": len(ep.get("shots", [])), "stage": "episode_done"},
                event=EVENT_STAGE,
            )

        # Enrich shots with 5-layer prompt builder + cinematography profiles
        style = request.get("style", "写实风格")
        all_episodes = self._enrich_all_shots(all_episodes, style)

        yield format_sse_event(
            {"status": "completed", "episodes": all_episodes},
            event=EVENT_DONE,
        )

    # ================================================================
    # Prompt enrichment — 5-layer builder + cinematography profiles
    # ================================================================

    def _get_profile_for_style(self, style: str) -> Optional[Any]:
        """Resolve a Chinese style name to a CinematographyProfile."""
        profile_id = _STYLE_TO_PROFILE.get(style)
        if profile_id:
            return get_profile(profile_id)
        # Fuzzy match: check if any known key contains the style string
        for key, pid in _STYLE_TO_PROFILE.items():
            if style in key or key in style:
                return get_profile(pid)
        return get_profile("classic-cinematic")

    def _enrich_shot_with_prompts(self, shot: dict, style: str) -> dict:
        """Enrich a single shot with image/video prompts from PromptBuilder.

        Adds imagePromptZh, videoPromptZh, endFramePromptZh, needsEndFrame
        fields to the shot dict if they are not already populated.
        """
        profile = self._get_profile_for_style(style)
        try:
            shot_input = ShotPromptInput(
                shot_type=shot.get("shotType", "中景"),
                duration=shot.get("duration", 5),
                camera_angle=shot.get("cameraAngle", "正面平视"),
                description=shot.get("description", ""),
                dialogue=shot.get("dialogue", ""),
                characters=shot.get("characters", []),
                camera_movement=shot.get("cameraMovement"),
                camera_rig=shot.get("cameraRig"),
                movement_speed=shot.get("movementSpeed"),
                depth_of_field=shot.get("depthOfField"),
                focus_target=shot.get("focusTarget"),
                focus_transition=shot.get("focusTransition"),
                lighting_style=shot.get("lightingStyle"),
                lighting_direction=shot.get("lightingDirection"),
                color_temperature=shot.get("colorTemperature"),
                emotion_tags=shot.get("emotionTags", []),
                narrative_function=shot.get("narrativeFunction"),
                atmospheric_effects=shot.get("atmosphericEffects"),
                effect_intensity=shot.get("effectIntensity"),
                focal_length=shot.get("focalLength"),
                photography_technique=shot.get("photographyTechnique"),
                playback_speed=shot.get("playbackSpeed"),
                style=style,
            )

            # Only generate if not already set by AI
            if not shot.get("imagePromptZh"):
                shot["imagePromptZh"] = PromptBuilder.build_image_prompt(shot_input, profile)
            if not shot.get("videoPromptZh"):
                shot["videoPromptZh"] = PromptBuilder.build_video_prompt(shot_input, profile)
            if not shot.get("needsEndFrame"):
                shot["needsEndFrame"] = PromptBuilder.infer_needs_end_frame(shot_input)
            if shot.get("needsEndFrame") and not shot.get("endFramePromptZh"):
                shot["endFramePromptZh"] = PromptBuilder.build_end_frame_prompt(shot_input, profile)
        except Exception as e:
            logger.warning(f"Prompt enrichment failed for shot {shot.get('id', '?')}: {e}")

        return shot

    def _enrich_all_shots(self, episodes: list, style: str) -> list:
        """Enrich all shots across all episodes with PromptBuilder prompts."""
        for ep in episodes:
            for shot in ep.get("shots", []):
                self._enrich_shot_with_prompts(shot, style)
        return episodes

    def _split_script_to_episodes(self, script: str) -> list:
        """按第N集标记拆分剧本（仅精确匹配集标题）"""
        markers = list(re.finditer(r'(?:\*\*)?第\s*([一二三四五六七八九十百千\d]+)\s*集', script))
        if len(markers) <= 1:
            return [script]
        texts = []
        for i, m in enumerate(markers):
            start = m.end()
            end = markers[i+1].start() if i+1 < len(markers) else len(script)
            texts.append(script[start:end])
        return texts

    def _split_episode_to_scene_chunks(self, ep_text: str, max_chars: int) -> List[str]:
        """将长集剧本按场景标记拆分为多个块，每块不超过 max_chars"""
        # 按【场景N：...】或【场景N:...】标记拆分
        scene_pattern = r'(?:^|\n)(【场景[^】]*】)'
        parts = re.split(scene_pattern, ep_text)

        if len(parts) <= 1:
            # 没有场景标记，按段落拆分
            paragraphs = [p.strip() for p in ep_text.split('\n\n') if p.strip()]
            chunks = []
            current = ""
            for p in paragraphs:
                if len(current) + len(p) + 2 > max_chars and current:
                    chunks.append(current)
                    current = p
                else:
                    current = current + "\n\n" + p if current else p
            if current:
                chunks.append(current)
            return chunks if chunks else [ep_text]

        # 有场景标记：重新组装，将相邻场景合并到同一块
        chunks = []
        current = ""
        i = 0
        while i < len(parts):
            segment = parts[i]
            # 检查下一个是否是场景标记
            if i + 1 < len(parts) and re.match(r'【场景[^】]*】', parts[i+1]):
                # 这是场景标题 + 场景内容
                scene_header = parts[i+1]
                scene_body = parts[i+2] if i + 2 < len(parts) else ""
                full_scene = segment + scene_header + scene_body
                if len(current) + len(full_scene) > max_chars and current:
                    chunks.append(current)
                    current = full_scene
                else:
                    current = current + full_scene if current else full_scene
                i += 3
            else:
                if len(current) + len(segment) > max_chars and current:
                    chunks.append(current)
                    current = segment
                else:
                    current = current + segment if current else segment
                i += 1
        if current:
            chunks.append(current)
        return chunks if chunks else [ep_text]

    def _merge_episode_shots(self, episodes: List[Dict[str, Any]], ep_num: int) -> Dict[str, Any]:
        """合并同一集多个分段的分镜结果"""
        if not episodes:
            return {"episodes": []}
        if len(episodes) == 1:
            return {"episodes": episodes}
        # 合并所有shots，重新编号
        merged_shots = []
        shot_counter = 1
        for ep in episodes:
            for shot in ep.get("shots", []):
                shot["number"] = shot_counter
                shot["id"] = shot_counter
                shot_counter += 1
                merged_shots.append(shot)
        cn = ['', '一','二','三','四','五','六','七','八','九','十']
        return {"episodes": [{
            "id": f"ep-{ep_num}",
            "title": f"第{cn[ep_num] if ep_num<=10 else ep_num}集",
            "number": ep_num,
            "description": episodes[0].get("description", ""),
            "shots": merged_shots,
        }]}

    def _parse_single_episode_shots(self, content: str, ep_num: int, start_shot_id: int, request: Dict[str, Any]) -> Dict[str, Any]:
        """解析单集镜头JSON（容错处理）"""
        try:
            json_str = content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]
            data = json.loads(json_str)
            eps = data.get("episodes", [])
            if eps:
                ep = eps[0]
                ep["number"] = ep_num
                cn = ['', '一','二','三','四','五','六','七','八','九','十']
                ep["title"] = f"第{cn[ep_num] if ep_num<=10 else ep_num}集"
                ep["id"] = f"ep-{ep_num}"
                for s in ep.get("shots", []):
                    s["id"] = start_shot_id + s.get("number", 1)
                return {"episodes": [ep]}
        except json.JSONDecodeError:
            logger.warning(f"第{ep_num}集JSON解析失败，使用程序化分镜")
        except Exception as e:
            logger.warning(f"第{ep_num}集解析异常: {e}")
        return self._programmatic_shots(content, ep_num, start_shot_id)

    def _programmatic_shots(self, text: str, ep_num: int, start_shot_id: int) -> Dict[str, Any]:
        """程序化分镜：从剧本格式文本提取场景生成镜头"""
        shots = []
        shot_id = start_shot_id
        # 按场景标记拆分
        scenes = re.split(r'\n(?:\*\*)?\d+-\d+\s', text)
        if len(scenes) <= 1:
            scenes = [p.strip() for p in text.split('\n\n') if p.strip()][:8]
        for scene_text in (scenes if len(scenes) > 1 else [text])[:8]:
            shot_id += 1
            chars = re.findall(r'人物[：:]\s*(.+)', scene_text)
            char_list = [c.strip() for c in (chars[0].split('、') if chars else [])]
            dialogue = re.findall(r'([^\s△（(]+)[：:].*?["""\n]', scene_text)
            dialogue_str = '；'.join([f'{d.strip()}：…' for d in dialogue[:2]]) if dialogue else ''
            desc = scene_text.strip()[:200]
            shot_type = "中景"
            if any(kw in scene_text[:100] for kw in ['特写', '近景', '细节', '眼神', '手指', '面部']): shot_type = "特写"
            elif any(kw in scene_text[:100] for kw in ['全景', '远景', '环境', '俯瞰', '城市', '天空']): shot_type = "全景"
            shots.append({
                "id": shot_id, "number": shot_id, "shotType": shot_type, "duration": 5,
                "cameraAngle": "正面平视", "sceneRef": "", "characters": char_list,
                "description": desc, "dialogue": dialogue_str,
                "soundEffects": [], "music": "", "notes": ""
            })
        cn = ['', '一','二','三','四','五','六','七','八','九','十']
        return {"episodes": [{"id": f"ep-{ep_num}", "title": f"第{cn[ep_num] if ep_num<=10 else ep_num}集", "number": ep_num, "shots": shots}]}

    def _fallback_parse_shots(self, content: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """备用：程序化分镜"""
        return self._programmatic_shots(request.get('script', content), 1, 0)

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
4. 预计集数: {min(episode_count, 3)} 集（最多3集）

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
- lightingStyle: 灯光风格（自然光/三点布光/高调光/低调光/侧光/逆光/霓虹光/烛光）
- depthOfField: 景深（浅景深/中等景深/深景深）
- cameraRig: 拍摄设备（三脚架/手持/斯坦尼康/滑轨/摇臂/无人机）
- cameraMovement: 运镜方式（推/拉/摇/移/跟/升/降/固定）
- movementSpeed: 运动速度（缓慢/中速/快速）
- emotionTags: 情绪标签数组（如["紧张","压抑","期待"]）
- atmosphericEffects: 氛围特效（无/雾/雨/雪/烟/灰尘）

每集应包含6-12个镜头，确保镜头节奏紧凑。
每个镜头必须填充所有上述摄影字段，根据剧情设计不同的值而非全用默认。

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

        # 截断剧本避免超出token限制（可配置上限）
        max_script_chars = request.get('maxScriptChars', settings.STORYBOARD_MAX_SCRIPT_CHARS)
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
        """备用解析：从剧本内容的场景标记直接生成分镜（不依赖 AI JSON）"""
        logger.info("使用备用解析方式从剧本生成镜头分镜...")

        script = request.get('script', '') or content
        episodes = []

        # 按剧集标记拆分：**第N集** 或 第N集
        ep_markers = list(re.finditer(r'(?:\*\*)?第\s*([一二三四五六七八九十百千\d]+)\s*集(?:\*\*)?', script))
        cn_nums = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']

        if len(ep_markers) <= 1:
            # 只有一集或没有标记，整篇作为一集
            ep_markers = [(0, '1', len(script))]
            episode_texts = [script]
        else:
            episode_texts = []
            for i, m in enumerate(ep_markers):
                start = m.end()
                end = ep_markers[i+1].start() if i+1 < len(ep_markers) else len(script)
                episode_texts.append(script[start:end])

        # 为每集生成镜头
        for ep_idx, ep_text in enumerate(episode_texts[:5]):  # 最多5集
            ep_num = ep_idx + 1
            num_str = cn_nums[ep_num] if ep_num <= 10 else str(ep_num)

            # 按场景标记拆分：**N-N ...** 或 N-N ...
            scene_pattern = re.compile(r'(?:\*\*)?(\d+-\d+)\s*(?:日|夜|昼).*?(?:\*\*)?\s*(.+?)(?=\n\s*(?:\*\*)?\d+-\d+\s*(?:日|夜|昼)|\Z)', re.DOTALL)
            scenes = scene_pattern.findall(ep_text)

            shots = []
            shot_id = 0
            if scenes:
                for scene_num, scene_text in scenes[:12]:  # 每集最多12个镜头
                    shot_id += 1
                    # 从场景中提取角色和对话
                    chars = re.findall(r'人物[：:]\s*(.+)', scene_text)
                    char_list = [c.strip() for c in (chars[0].split('、') if chars else [])]
                    dialogue = re.findall(r'([^\s△]+)[：:].*?["""](.+?)[""」]', scene_text)
                    dialogue_str = '；'.join([f'{d[0]}：{d[1]}' for d in dialogue[:2]]) if dialogue else ''

                    # 推断镜头类型
                    shot_type = "中景"
                    desc = scene_text.strip()[:150]
                    if any(kw in scene_text for kw in ['特写', '近景', '细节', '眼神']):
                        shot_type = "特写"
                    elif any(kw in scene_text for kw in ['全景', '远景', '环境', '俯瞰']):
                        shot_type = "全景"

                    shots.append({
                        "id": shot_id, "number": shot_id,
                        "shotType": shot_type, "duration": 5,
                        "cameraAngle": "正面平视",
                        "sceneRef": f"场景{scene_num}",
                        "characters": char_list,
                        "description": desc,
                        "dialogue": dialogue_str,
                        "soundEffects": [], "music": "", "notes": ""
                    })

            if not shots:
                # 如果没有场景标记，按段落拆分
                paragraphs = [p.strip() for p in ep_text.split('\n\n') if p.strip()]
                for p_idx, para in enumerate(paragraphs[:12]):
                    shot_id += 1
                    shots.append({
                        "id": shot_id, "number": shot_id,
                        "shotType": "中景", "duration": 5,
                        "cameraAngle": "正面平视", "sceneRef": "",
                        "characters": [], "description": para[:150],
                        "dialogue": "", "soundEffects": [], "music": "", "notes": ""
                    })

            episodes.append({
                "id": f"ep-{ep_num}",
                "title": f"第{num_str}集",
                "number": ep_num,
                "shots": shots,
                "description": "",
            })

        total_shots = sum(len(ep.get("shots", [])) for ep in episodes)
        logger.info(f"从剧本拆分为 {len(episodes)} 集，共 {total_shots} 个镜头")

        return {
            "episodes": episodes,
            "metadata": {
                "generated_by": "script-parser",
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

{script_content[:settings.STORYBOARD_MAX_SCRIPT_CHARS]}

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

        max_chars = settings.STORYBOARD_MAX_SCRIPT_CHARS
        script_truncated = script[:max_chars]
        if len(script) > max_chars:
            script_truncated += "\n\n...(剧本内容已截断)..."

        return f"""请将以下剧本转换成分镜脚本。

剧本标题: {title}

剧本内容:
{script_truncated}

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
