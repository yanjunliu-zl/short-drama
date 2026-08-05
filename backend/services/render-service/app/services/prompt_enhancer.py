"""
图像/视频生成 Prompt 增强器 — 用 LLM 将简单的场景描述翻译为专业图像生成 prompt。

将 "{style}, {scene_description}" 的简单拼接升级为：
  构图设计 + 光线氛围 + 色彩调性 + 细节质感 + 质量关键词 + 风格约束
"""
import logging
from typing import Optional

from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_ENHANCER = """你是顶级 AI 图像生成 prompt 工程师。将场景描述翻译为专业的图像生成提示词。

【输出格式】
严格输出以下 JSON，不要多余解释：
{
  "image_prompt": "专业的英文图像生成提示词，包含构图、光线、色彩、细节、风格、质量关键词",
  "image_prompt_zh": "对应的中文版提示词"
}

【提示词结构】(按优先级排列)
1. 主体与构图: 描述画面核心内容、人物位置关系、镜头角度
2. 光线与氛围: 光源方向、色温、明暗对比、情绪氛围
3. 色彩与质感: 主色调、材质细节、纹理
4. 风格约束: 必须遵循指定的视觉风格
5. 质量关键词: 8k, highly detailed, cinematic lighting, sharp focus, professional photography
6. 负向约束: 在 JSON 外不要输出

【重要规则】
- image_prompt 用英文（Stable Diffusion 兼容）
- image_prompt_zh 用中文
- 保留原始场景描述中的所有关键元素（人物、地点、动作、道具）
- 不要添加原始描述中没有的人物或元素
- 长度控制在 200-400 字符"""

_HUMAN_ENHANCE = """【场景描述】
{description}

【视觉风格】
{style}

【场景类型】
{scene_type}

【可用角色参考（可选）】
{characters}"""


class PromptEnhancer:
    """LLM-based image/video prompt enhancer."""

    def __init__(self, llm=None):
        self.llm = llm

    async def enhance(
        self,
        description: str,
        style: str = "写实风格",
        scene_type: str = "scene",
        characters: str = "",
    ) -> dict:
        """Enhance a plain scene description into a professional image prompt.

        Args:
            description: Raw scene/shot description.
            style: Visual style string (e.g. "写实风格", "古装风格").
            scene_type: "scene", "character", or "prop".
            characters: Optional comma-separated character names.

        Returns:
            {"image_prompt": "...", "image_prompt_zh": "..."}
        """
        if self.llm is None:
            return self._fallback_enhance(description, style)

        try:
            messages = [
                SystemMessage(content=_SYSTEM_PROMPT_ENHANCER),
                HumanMessage(content=_HUMAN_ENHANCE.format(
                    description=description[:500],
                    style=style,
                    scene_type=scene_type,
                    characters=characters or "无特定角色参考",
                )),
            ]
            response = await self.llm.ainvoke(messages, config={"timeout": 30})
            return self._parse_response(response.content, description, style)
        except Exception as e:
            logger.warning(f"Prompt enhancement failed: {e} — using fallback")
            return self._fallback_enhance(description, style)

    def _parse_response(self, text: str, fallback_desc: str, fallback_style: str) -> dict:
        """Parse LLM JSON response, with fallback."""
        import json
        try:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            start = text.index("{")
            end = text.rindex("}") + 1
            data = json.loads(text[start:end])
            return {
                "image_prompt": data.get("image_prompt", ""),
                "image_prompt_zh": data.get("image_prompt_zh", ""),
            }
        except Exception:
            return self._fallback_enhance(fallback_desc, fallback_style)

    @staticmethod
    def _fallback_enhance(description: str, style: str) -> dict:
        """Template-based fallback when LLM is unavailable."""
        quality_tags = "8k, highly detailed, cinematic lighting, sharp focus, professional photography"
        zh = f"{style}，{description}，{quality_tags}"
        en = f"{style}, {description}, {quality_tags}"
        return {"image_prompt": en, "image_prompt_zh": zh}


# Global instance
_prompt_enhancer: Optional[PromptEnhancer] = None


def get_prompt_enhancer(llm=None) -> PromptEnhancer:
    global _prompt_enhancer
    if _prompt_enhancer is None:
        _prompt_enhancer = PromptEnhancer(llm=llm)
    elif llm is not None and _prompt_enhancer.llm is None:
        _prompt_enhancer.llm = llm
    return _prompt_enhancer
