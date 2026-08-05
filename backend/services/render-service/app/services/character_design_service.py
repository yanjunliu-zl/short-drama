"""
角色形象设计服务 — 移植自 moyin-creator 的 6 层身份锚点系统

提供：
- 6 层身份锚点 AI 生成（enrich_character_with_anchors）
- 专业角色设定图提示词构建（build_character_sheet_prompt）
- 年代服装指导
"""
import logging
import json
import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def create_llm_client():
    """创建 LLM 客户端（优先 DeepSeek，其次 OpenAI/Anthropic，否则返回 None）"""
    try:
        from app.utils.model_router import create_llm_client as _router_create
        from app.utils.model_router import get_active_provider
        import logging
        logger = logging.getLogger(__name__)
        llm = _router_create(prefer="deepseek", timeout=120.0)
        if llm:
            logger.info(f"CharacterDesign LLM provider: {get_active_provider()}")
        return llm
    except Exception as e:
        logger.warning(f"创建 LLM 客户端失败: {e}")
        return None


# =============================================================
# 6 层身份锚点数据模型
# =============================================================

class ColorAnchors(BaseModel):
    iris: Optional[str] = None   # Hex: #3D2314
    hair: Optional[str] = None   # Hex: #1A1A1A
    skin: Optional[str] = None   # Hex: #E8C4A0
    lips: Optional[str] = None   # Hex: #C4727E


class IdentityAnchors(BaseModel):
    # Layer 1: 骨相层
    faceShape: Optional[str] = None
    jawline: Optional[str] = None
    cheekbones: Optional[str] = None
    # Layer 2: 五官层
    eyeShape: Optional[str] = None
    eyeDetails: Optional[str] = None
    noseShape: Optional[str] = None
    lipShape: Optional[str] = None
    # Layer 3: 辨识标记层（最强锚点）
    uniqueMarks: List[str] = Field(default_factory=list)
    # Layer 4: 色彩锚点层
    colorAnchors: Optional[ColorAnchors] = None
    # Layer 5: 皮肤纹理层
    skinTexture: Optional[str] = None
    # Layer 6: 发型锚点层
    hairStyle: Optional[str] = None
    hairlineDetails: Optional[str] = None


class NegativePrompt(BaseModel):
    avoid: List[str] = Field(default_factory=list)
    styleExclusions: List[str] = Field(default_factory=list)


class CharacterDesignResult(BaseModel):
    name: str
    detailedDescription: Optional[str] = None
    visualPromptEn: Optional[str] = None
    visualPromptZh: Optional[str] = None
    clothingStyle: Optional[str] = None
    identityAnchors: Optional[IdentityAnchors] = None
    negativePrompt: Optional[NegativePrompt] = None


class CharacterDesignRequest(BaseModel):
    name: str = Field(..., description="角色姓名")
    role: str = Field(default="supporting", description="角色定位: protagonist/supporting/minor")
    gender: str = Field(default="男")
    age: int = Field(default=25)
    description: str = Field(default="", description="角色描述")
    personality: str = Field(default="", description="性格特征")
    appearance: str = Field(default="", description="外貌描述")
    era: str = Field(default="现代", description="时代背景")
    genre: str = Field(default="", description="剧本类型")
    storyOutline: str = Field(default="", description="故事大纲")
    characterBios: str = Field(default="", description="人物小传")
    episodeCount: int = Field(default=1, description="总集数")
    promptLanguage: str = Field(default="zh", description="提示词语言: zh/en")


# =============================================================
# CharacterDesignService
# =============================================================

class CharacterDesignService:
    """角色形象设计服务"""

    # ---- 年代服装指导 ----
    @staticmethod
    def get_era_fashion_guidance(era: str, story_year: Optional[int] = None) -> str:
        """根据年代返回服装指导"""
        era_lower = era.lower()

        if story_year and story_year >= 2020:
            return f"【{era}服装指导】所有角色穿着{era}当代服装，反映{story_year}年代的时尚潮流。禁止古代服装。"
        if story_year and story_year >= 2010:
            return f"【{era}服装指导】所有角色穿着{era}当代服装。禁止古代服装。"
        if story_year and story_year >= 1990:
            return f"【{era}服装指导】所有角色穿着{era}年代服装。禁止未来感或古代服装。"
        if story_year and story_year >= 1950:
            return f"【{era}服装指导】所有角色穿着{story_year}年代复古服装。禁止现代服装。"

        if "唐" in era:
            return "【唐朝服装指导】男性：圆领袍衫/直裰/幞头。女性：齐胸衫裙/大袖衫/披帛。禁止现代服装。"
        if "明" in era:
            return "【明朝服装指导】男性：曳服/直裰/网巾或乌纱帽。女性：交领衫/马面裙/披风。禁止现代服装。"
        if "清" in era:
            return "【清朝服装指导】男性：长袍马褂/瓜皮帽。女性：旗装/旗头。禁止现代服装。"
        if any(kw in era_lower for kw in ["古代", "武侠", "仙侠", "玄幻", "宫斗", "战国", "春秋", "汉", "三国", "历史"]):
            return f"【{era}服装指导】所有角色穿着中国古代服饰（长袍/袖衫/披风）。发型为古代式样。禁止现代服装（西装/T恤/牛仔裤/运动鞋）。"
        if any(kw in era_lower for kw in ["科幻", "未来", "星际", "太空"]):
            return f"【{era}服装指导】设计未来感/科技感服装，保持内部一致性。禁止与世界观不符的服装。"

        return f"【{era}服装指导】服装/发型/配饰需符合「{era}」时代特征。禁止与该时代不符的服装。"

    # ---- 从锚点构建提示词 ----
    @staticmethod
    def build_prompt_from_anchors(
        anchors: Optional[IdentityAnchors],
        has_reference_images: bool = False,
        language: str = "zh",
    ) -> str:
        """根据是否有参考图，从锚点构建角色一致性提示词片段"""
        if not anchors:
            return ""

        if has_reference_images:
            # 有参考图：仅用最强锚点（第3层 + 第4层）
            parts = []
            if anchors.uniqueMarks:
                marks = "、".join(anchors.uniqueMarks)
                parts.append(f"distinctive marks: {marks}" if language == "en" else f"辨识标记：{marks}")
            if anchors.colorAnchors:
                ca = anchors.colorAnchors
                color_parts = []
                if ca.iris:
                    color_parts.append(f"iris color {ca.iris}" if language == "en" else f"虹膜色{ca.iris}")
                if ca.hair:
                    color_parts.append(f"hair color {ca.hair}" if language == "en" else f"发色{ca.hair}")
                if ca.skin:
                    color_parts.append(f"skin tone {ca.skin}" if language == "en" else f"肤色{ca.skin}")
                if color_parts:
                    separator = ", " if language == "en" else "，"
                    parts.append(separator.join(color_parts))
            return ", ".join(parts) if language == "en" else "，".join(parts)

        # 无参考图：完整 6 层
        parts = []
        is_cn = language == "zh"

        # Layer 1: 骨相
        bone_parts = [p for p in [anchors.faceShape, anchors.jawline, anchors.cheekbones] if p]
        if bone_parts:
            prefix = "facial bone structure:" if not is_cn else "面部骨骼："
            parts.append(f"{prefix}{'，'.join(bone_parts)}" if is_cn else f"{prefix} {' '.join(bone_parts)}")

        # Layer 2: 五官
        feature_parts = [p for p in [anchors.eyeShape, anchors.eyeDetails, anchors.noseShape, anchors.lipShape] if p]
        if feature_parts:
            prefix = "facial features:" if not is_cn else "五官特征："
            parts.append(f"{prefix}{'，'.join(feature_parts)}" if is_cn else f"{prefix} {' '.join(feature_parts)}")

        # Layer 3: 辨识标记（最强）
        if anchors.uniqueMarks:
            marks = "、".join(anchors.uniqueMarks)
            prefix = "distinctive marks:" if not is_cn else "辨识标记："
            parts.append(f"{prefix}{marks}")

        # Layer 4: 色彩锚点
        if anchors.colorAnchors:
            ca = anchors.colorAnchors
            color_parts = []
            if ca.iris:
                color_parts.append(f"虹膜色{ca.iris}" if is_cn else f"iris color {ca.iris}")
            if ca.hair:
                color_parts.append(f"发色{ca.hair}" if is_cn else f"hair color {ca.hair}")
            if ca.skin:
                color_parts.append(f"肤色{ca.skin}" if is_cn else f"skin tone {ca.skin}")
            if ca.lips:
                color_parts.append(f"唇色{ca.lips}" if is_cn else f"lip color {ca.lips}")
            if color_parts:
                separator = "，" if is_cn else ", "
                prefix = "color anchors:" if not is_cn else "色彩锚点："
                parts.append(f"{prefix}{separator.join(color_parts)}")

        # Layer 5: 皮肤纹理
        if anchors.skinTexture:
            prefix = "skin texture:" if not is_cn else "皮肤纹理："
            parts.append(f"{prefix}{anchors.skinTexture}")

        # Layer 6: 发型
        hair_parts = [p for p in [anchors.hairStyle, anchors.hairlineDetails] if p]
        if hair_parts:
            prefix = "hair style:" if not is_cn else "发型："
            parts.append(f"{prefix}{'，'.join(hair_parts)}" if is_cn else f"{prefix} {' '.join(hair_parts)}")

        separator = ", " if not is_cn else "，"
        return separator.join(parts)

    # ---- 终极角色设定图提示词 ----
    @staticmethod
    def build_character_sheet_prompt(
        name: str,
        description: str,
        anchors: Optional[IdentityAnchors] = None,
        era: str = "现代",
        style: str = "写实",
        language: str = "zh",
        has_reference_images: bool = False,
        sheet_elements: Optional[List[str]] = None,
        story_year: Optional[int] = None,
    ) -> str:
        """构建专业的角色设定图生成提示词"""
        is_cn = language == "zh"

        # 基础描述
        base = f'专业角色设计参考图，"{name}"，{description}' if is_cn else \
               f'professional character design sheet for "{name}", {description}'

        # 锚点提示词
        anchor_prompt = CharacterDesignService.build_prompt_from_anchors(
            anchors, has_reference_images, language
        )

        # 年代服装
        era_fashion = CharacterDesignService.get_era_fashion_guidance(era, story_year)

        # 内容元素（三视图/表情/比例等）
        if sheet_elements is None:
            if style in ("写实", "realistic", "电影级"):
                sheet_elements = ["正面全身像", "侧面像", "背面像"] if is_cn else \
                                 ["front full-body view", "side view", "back view"]
            else:
                sheet_elements = ["三视图", "表情设定", "比例设定"] if is_cn else \
                                 ["turnaround", "expression sheet", "proportion reference"]

        content = "，".join(sheet_elements) if is_cn else ", ".join(sheet_elements)

        # 风格标识
        style_tokens = {
            "写实": "电影级写实风格，超高清，皮肤质感真实",
            "realistic": "cinematic photorealism, ultra HD, realistic skin texture",
            "动漫": "日式动漫风格，赛璐璐着色，清晰线条",
            "anime": "anime style, cel shading, clean lineart",
            "3D": "3D渲染风格，PBR材质，柔和光影",
            "3d": "3D rendered style, PBR materials, soft lighting",
        }
        style_str = style_tokens.get(style, style_tokens.get("写实", ""))

        # 背景
        bg = "纯白背景，角色独立于白色背景上，无背景场景" if is_cn else \
             "pure solid white background, isolated character on white background"

        # 组装
        prompt_parts = [base]
        if anchor_prompt:
            prompt_parts.append(anchor_prompt)
        prompt_parts.append(era_fashion)
        prompt_parts.append(content)
        prompt_parts.append(bg)
        prompt_parts.append(style_str)
        prompt_parts.append("高质量，细节丰富" if is_cn else "high quality, detailed")

        return "，".join(prompt_parts) if is_cn else ", ".join(prompt_parts)

    # ---- 调用 LLM 生成 6 层锚点 ----
    @staticmethod
    def build_enrich_system_prompt(
        era: str,
        genre: str,
        story_outline: str,
        character_bios: str,
        episode_count: int,
        story_year: Optional[int] = None,
        language: str = "zh",
    ) -> str:
        """构建角色锚点生成的系统提示词"""
        era_fashion = CharacterDesignService.get_era_fashion_guidance(era, story_year)
        is_cn = language == "zh"

        if is_cn:
            anchor_spec = """【核心输出：6层身份锚点】
这是AI生图中保持角色一致性的关键技术，必须用中文详细填写：

① 骨相层（面部骨骼结构）
   - faceShape: 脸型（鹅蛋形/方形/心形/圆形/菱形/长圆形）
   - jawline: 下颌线（棱角分明/柔和圆润/突出方正）
   - cheekbones: 颧骨（高颧骨/不明显/宽颧骨）

② 五官层（精确描述）
   - eyeShape: 眼型（杏仁形/圆眼/内双/单眼皮/上挑形）
   - eyeDetails: 眼部细节（双眼皮、轻微内眦褶、深邃眼窝）
   - noseShape: 鼻型（高鼻梁、圆鼻头、小巧挺鼻）
   - lipShape: 唇型（丰唇、薄唇、明显的唇珠）

③ 辨识标记层（最强锚点！）
   - uniqueMarks: 必填数组！至少2-3个独特标记，用中文描述
   - 示例：["左眼下方2cm处小痣", "右眉尾处淡疤", "左脸颊酒窝"]
   - 这是最强的角色识别特征，必须精确到位置

④ 色彩锚点层（Hex色值）
   - colorAnchors.iris: 虹膜色（如 #3D2314 深棕色）
   - colorAnchors.hair: 发色（如 #1A1A1A 乌黑）
   - colorAnchors.skin: 肤色（如 #E8C4A0 暖米色）
   - colorAnchors.lips: 唇色（如 #C4727E 豆沙粉）

⑤ 皮肤纹理层
   - skinTexture: 皮肤质感，用中文描述（毛孔清晰、淡雀斑、笑纹明显）

⑥ 发型锚点层
   - hairStyle: 发型，用中文描述（齐肩层次剪、寸头、波波头）
   - hairlineDetails: 发际线，用中文描述（自然发际线、美人尖、额角后退）

【负面提示词】
为角色生成negativePrompt，排除不符合设定的特征，用中文填写：
- avoid: 要避免的特征（如中国人角色应避免 金色头发、蓝色眼睛）
- styleExclusions: 风格排除（如 动漫风、卡通风、油画风）"""
        else:
            anchor_spec = """【Core Output: 6-Layer Identity Anchors】
This is the key technology for maintaining character consistency in AI image generation:

① Bone Structure Layer
   - faceShape: oval/square/heart/round/diamond/oblong
   - jawline: sharp angular/soft rounded/prominent
   - cheekbones: high prominent/subtle/wide set

② Facial Features Layer
   - eyeShape: almond/round/hooded/monolid/upturned
   - eyeDetails: double eyelids, slight epicanthic fold, deep-set
   - noseShape: straight bridge, rounded tip, button nose
   - lipShape: full lips, thin lips, defined cupid's bow

③ Distinctive Marks Layer (STRONGEST!)
   - uniqueMarks: REQUIRED array! At least 2-3 unique marks
   - Example: ["small mole 2cm below left eye", "faint scar on right eyebrow", "dimple on left cheek"]

④ Color Anchor Layer (Hex)
   - colorAnchors.iris: e.g. #3D2314 dark brown
   - colorAnchors.hair: e.g. #1A1A1A jet black
   - colorAnchors.skin: e.g. #E8C4A0 warm beige
   - colorAnchors.lips: e.g. #C4727E dusty rose

⑤ Skin Texture Layer
   - skinTexture: visible pores, light freckles, smile lines

⑥ Hair Anchor Layer
   - hairStyle: shoulder-length layered cut, buzz cut, bob
   - hairlineDetails: natural hairline, widow's peak, receding temples

【Negative Prompt】
- avoid: features to exclude (e.g. blonde hair, blue eyes for Chinese characters)
- styleExclusions: style exclusions (e.g. cartoon style, oil painting style)"""

        return f"""你是好莱坞顶级角色设计大师，曾为漫威、迪士尼、皮克斯设计过无数经典角色。

你的专业能力：
- **角色视觉设计**：能准确捕捉角色的外在形象、服装风格、肢体语言
- **年代服装专家**：精通不同年代的中国服装潮流，能准确还原历史时期的服装特征
- **AI图像生成专家**：深谙 Midjourney、DALL-E、Stable Diffusion 等 AI 绘图模型
- **角色一致性专家**：掌握"6层特征锁定"技术，确保同一角色在不同场景保持一致

【剧本信息】
类型：{genre or '未知类型'}
时代背景：{era}
总集数：{episode_count}集

{era_fashion}

【故事大纲】
{story_outline[:1200] or '无'}

【人物小传】
{character_bios[:1200] or '无'}

{anchor_spec}

请输出 JSON 格式，包含以下字段：
- name, detailedDescription, visualPromptEn, visualPromptZh, clothingStyle
- identityAnchors（6层锚点对象）
- negativePrompt（avoid 和 styleExclusions 数组）"""


async def enrich_character_with_anchors(
    llm,  # LangChain ChatOpenAI instance
    request: CharacterDesignRequest,
) -> CharacterDesignResult:
    """调用 LLM 为角色生成 6 层身份锚点"""
    system_prompt = CharacterDesignService.build_enrich_system_prompt(
        era=request.era,
        genre=request.genre,
        story_outline=request.storyOutline,
        character_bios=request.characterBios,
        episode_count=request.episodeCount,
        story_year=None,
        language=request.promptLanguage,
    )

    user_prompt = f"""请为以下角色生成完整的 6 层身份锚点和角色设计：

角色姓名：{request.name}
角色定位：{request.role}
性别：{request.gender}
年龄：{request.age}
描述：{request.description}
性格：{request.personality}
外貌：{request.appearance}

请输出 JSON。"""

    from langchain_core.messages import SystemMessage, HumanMessage

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    try:
        response = await llm.ainvoke(messages)
        content = response.content

        # 提取 JSON（可能被 markdown 代码块包裹）
        json_str = content
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0]

        data = json.loads(json_str)

        # 解析锚点
        anchors_data = data.get("identityAnchors", {})
        color_data = anchors_data.get("colorAnchors", {})
        anchors = IdentityAnchors(
            faceShape=anchors_data.get("faceShape"),
            jawline=anchors_data.get("jawline"),
            cheekbones=anchors_data.get("cheekbones"),
            eyeShape=anchors_data.get("eyeShape"),
            eyeDetails=anchors_data.get("eyeDetails"),
            noseShape=anchors_data.get("noseShape"),
            lipShape=anchors_data.get("lipShape"),
            uniqueMarks=anchors_data.get("uniqueMarks", []),
            colorAnchors=ColorAnchors(**color_data) if color_data else None,
            skinTexture=anchors_data.get("skinTexture"),
            hairStyle=anchors_data.get("hairStyle"),
            hairlineDetails=anchors_data.get("hairlineDetails"),
        )

        neg_data = data.get("negativePrompt", {})
        negative = NegativePrompt(
            avoid=neg_data.get("avoid", []),
            styleExclusions=neg_data.get("styleExclusions", []),
        )

        return CharacterDesignResult(
            name=data.get("name", request.name),
            detailedDescription=data.get("detailedDescription"),
            visualPromptEn=data.get("visualPromptEn"),
            visualPromptZh=data.get("visualPromptZh"),
            clothingStyle=data.get("clothingStyle"),
            identityAnchors=anchors,
            negativePrompt=negative,
        )

    except Exception as e:
        logger.error(f"角色锚点生成失败: {e}")
        # 返回基础结果（无锚点）
        return CharacterDesignResult(
            name=request.name,
            detailedDescription=request.description,
            visualPromptZh=f"角色设计：{request.name}，{request.gender}，{request.age}岁，{request.description}",
        )
