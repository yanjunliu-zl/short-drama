"""
剧本本土化服务 — 文化适配引擎。

将剧本适配到目标市场的文化语境。不是翻译，而是重写——让剧本
读起来像目标市场本地编剧写的。

核心能力:
1. 文化符号替换（地名、食物、节日、货币 → 市场本地等价物）
2. 角色原型重映射（中国角色原型 → 目标市场角色原型）
3. 叙事惯例调整（节奏、悬念风格、情感表达方式）
4. 合规性适配（不同市场的内容红线不同）
5. 直接多语言生成（locale-aware system prompt）

管线:
  script_content → [MarketProfile.apply] → localized_script + locale metadata
"""
import logging
import json
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from langchain_core.messages import SystemMessage, HumanMessage

from app.services.market_profiles import MarketProfile, get_profile, list_locales, ALL_LOCALES

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════

@dataclass
class LocalizationRequest:
    """本土化请求"""
    script_content: str                           # 原始剧本
    source_locale: str = "zh-CN"                  # 源市场
    target_locale: str = "en-US"                  # 目标市场
    title: str = ""                               # 剧本标题
    style: str = ""                               # 原始风格
    adaptation_level: str = "full"                # "light" (仅替换文化符号) | "full" (完整文化适配)
    preserve_plot: bool = True                    # 保留原始情节结构
    preserve_episode_count: bool = True            # 保留原始集数
    output_language: str = ""                     # 输出语言（空=使用目标市场语言）


@dataclass
class LocalizationResult:
    """本土化结果"""
    success: bool = False
    localized_script: str = ""
    title_localized: str = ""
    source_locale: str = ""
    target_locale: str = ""
    market_name: str = ""
    language: str = ""
    changes_summary: List[str] = field(default_factory=list)
    character_mappings: Dict[str, str] = field(default_factory=dict)
    # {"顾清寒": "Clara Blackwood", "沈惊澜": "Damian Cross"}
    adaptation_notes: str = ""
    elapsed_ms: int = 0


# ═══════════════════════════════════════════════════════════════
# System Prompts
# ═══════════════════════════════════════════════════════════════

_LOCALIZE_SYSTEM_LIGHT = """You are a professional script localization specialist.

TASK: Perform LIGHT cultural adaptation of a short drama script from {source_market} to {target_market}.

LIGHT adaptation means:
1. Replace character names with culturally appropriate {target_market} names
2. Replace locations/settings with {target_market} equivalents
3. Replace food, drink, cultural references with {target_market} equivalents
4. Replace currency, measurements, date formats
5. Replace idioms and expressions with natural {target_language} equivalents
6. DO NOT change the plot, episode structure, dialogue meaning, or emotional arcs

Output the FULL adapted script. Preserve all episode markers, scene markers, and dialogue format.
"""

_LOCALIZE_SYSTEM_FULL = """You are a senior short drama scriptwriter who specializes in cross-cultural adaptation.

TASK: Perform FULL cultural localization of a short drama script from {source_market} to {target_market}.

FULL adaptation means ALL of the light adaptation PLUS:
1. Adapt character archetypes to resonate with {target_market} audiences
   {character_guidance}
2. Adjust narrative pacing to match {target_market} conventions: {pacing}
3. Adapt romance/relationship style: {romance_style}
4. Adapt humor and emotional expression to cultural norms
5. REPLACE any {source_market}-specific social hierarchies with {target_market} equivalents
6. Ensure all cliffhangers use styles that work in {target_market}: {cliffhanger}

CRITICAL RULES:
- Output in {target_language}
- Preserve the original episode count and overall plot structure
- Every episode must still end with a cliffhanger
- Character personalities must remain recognizable after adaptation
- DO NOT introduce content that violates {target_market} cultural taboos: {taboos}

{genre_guidance}

Output the FULL adapted script. Preserve all episode markers (第N集), scene markers (【场景】),
dialogue format (角色名：台词), and action markers (△).
"""


# ═══════════════════════════════════════════════════════════════
# LocalizationService
# ═══════════════════════════════════════════════════════════════

class ScriptLocalizationService:
    """剧本本土化服务"""

    def __init__(self, llm=None):
        self.llm = llm   # LangChain chat model
        self._profiles: Dict[str, MarketProfile] = {}

    # ── Public API ──

    async def localize(self, request: LocalizationRequest) -> LocalizationResult:
        """Full cultural localization pipeline."""
        t0 = time.time()

        profile = get_profile(request.target_locale)
        result = LocalizationResult(
            source_locale=request.source_locale,
            target_locale=request.target_locale,
            market_name=profile.market_name,
            language=profile.language,
        )

        if not self.llm:
            # No LLM: return source script with metadata
            result.success = True
            result.localized_script = request.script_content
            result.adaptation_notes = "LLM not available — returned source script"
            result.elapsed_ms = int((time.time() - t0) * 1000)
            return result

        try:
            # Build prompt
            if request.adaptation_level == "light":
                system_prompt = _LOCALIZE_SYSTEM_LIGHT.format(
                    source_market="Chinese Mainland",
                    target_market=profile.market_name,
                    target_language=profile.language,
                )
            else:
                char_guidance = self._build_character_guidance(profile)
                genre_guidance = self._build_genre_guidance(profile, request.style)
                system_prompt = _LOCALIZE_SYSTEM_FULL.format(
                    source_market="Chinese Mainland",
                    target_market=profile.market_name,
                    target_language=profile.language,
                    character_guidance=char_guidance,
                    pacing=profile.pacing_style,
                    romance_style=profile.romance_style,
                    cliffhanger=profile.cliffhanger_style,
                    taboos=", ".join(profile.taboo_topics[:5]),
                    genre_guidance=genre_guidance,
                )

            user_prompt = self._build_user_prompt(request, profile)

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            response = await self.llm.ainvoke(messages, config={"timeout": 180})
            localized = response.content

            result.success = True
            result.localized_script = localized
            result.title_localized = self._localize_title(request.title, profile)
            result.character_mappings = self._extract_character_mappings(
                request.script_content, localized
            )
            result.adaptation_notes = (
                f"Adapted from {request.source_locale} to {profile.market_name} "
                f"({profile.language}), level={request.adaptation_level}"
            )
            result.elapsed_ms = int((time.time() - t0) * 1000)

            logger.info(
                f"Localization: {request.source_locale}→{request.target_locale} "
                f"level={request.adaptation_level} "
                f"chars_in={len(request.script_content)} chars_out={len(localized)} "
                f"elapsed={result.elapsed_ms}ms"
            )

        except Exception as e:
            logger.error(f"Localization failed: {e}")
            result.success = False
            result.adaptation_notes = f"Error: {str(e)[:200]}"
            result.elapsed_ms = int((time.time() - t0) * 1000)

        return result

    async def localize_light(self, request: LocalizationRequest) -> LocalizationResult:
        """Quick cultural symbol replacement (no LLM — regex-based)."""
        t0 = time.time()
        profile = get_profile(request.target_locale)
        result = LocalizationResult(
            source_locale=request.source_locale,
            target_locale=request.target_locale,
            market_name=profile.market_name,
            language=profile.language,
        )

        content = request.script_content
        changes = []

        # Direct replacements from sensitive_replacements map
        for cn_term, local_term in profile.sensitive_replacements.items():
            if cn_term in content:
                content = content.replace(cn_term, local_term)
                changes.append(f"'{cn_term}' → '{local_term}'")

        result.success = True
        result.localized_script = content
        result.changes_summary = changes
        result.adaptation_notes = f"Light localization: {len(changes)} term replacements"
        result.elapsed_ms = int((time.time() - t0) * 1000)

        logger.info(f"Light localization: {request.target_locale}, {len(changes)} changes")
        return result

    # ── Locale-Aware Script Generation ──

    def build_locale_system_prompt(
        self, target_locale: str, base_system_prompt: str = "",
        style: str = "",
    ) -> str:
        """Build a locale-aware system prompt for direct script generation.

        This injects market-specific character archetypes, genre preferences,
        and cultural norms into the system prompt, so generated scripts are
        culturally native from the start (not adapted post-hoc).
        """
        profile = get_profile(target_locale)

        parts = [base_system_prompt or "你是专业短剧编剧。"]

        # Market context
        parts.append(f"\n【目标市场】{profile.market_name}（{profile.language}）")

        # Character guidance
        parts.append("\n【角色塑造指南】")
        for arch in profile.character_archetypes[:3]:
            parts.append(
                f"- {arch['role']}: {arch['archetype']} — {arch['traits']}"
            )

        # Genre guidance
        if style:
            mapper = _style_to_genre_mapper()
            mapped = [mapper.get(g.strip(), g) for g in style.split("/")]
            parts.append(f"\n【类型适配】将'{style}'风格转化为{profile.market_name}市场对应的热门类型: {', '.join(mapped[:3])}。")
            parts.append(f"热门类型: {', '.join(profile.popular_genres[:5])}")

        # Narrative conventions
        parts.append(f"\n【叙事惯例】{profile.pacing_style}")
        parts.append(f"悬念风格: {profile.cliffhanger_style}")

        # Cultural settings
        parts.append(f"\n【文化设定】")
        parts.append(f"常见场景: {', '.join(profile.common_settings[:5])}")
        parts.append(f"常见男性名字: {', '.join(profile.common_male_names[:6])}")
        parts.append(f"常见女性名字: {', '.join(profile.common_female_names[:6])}")
        parts.append(f"文化事件: {', '.join(profile.cultural_events[:3])}")
        parts.append(f"常见食物/饮品: {', '.join(profile.food_references[:5])}")

        # Taboos
        if profile.taboo_topics:
            parts.append(f"\n【避免内容】{', '.join(profile.taboo_topics[:5])}")

        # Output language
        parts.append(f"\n【输出语言】{profile.language}（{profile.language_name}）")

        parts.append("\n确保剧本中的所有文化元素（人名、地名、食物、节日、社交礼仪）"
                      f"都符合{profile.market_name}市场，让当地观众感到亲切自然。")

        return "\n".join(parts)

    # ── Market Information ──

    def get_market_info(self, locale: str) -> Dict[str, Any]:
        """Get market profile information for display."""
        profile = get_profile(locale)
        return {
            "locale": profile.locale,
            "market_name": profile.market_name,
            "language": profile.language,
            "language_name": profile.language_name,
            "popular_genres": profile.popular_genres[:5],
            "episode_length": profile.episode_length_preferred,
            "total_episodes": profile.total_episodes_preferred,
            "pacing_style": profile.pacing_style,
            "romance_style": profile.romance_style,
            "cliffhanger_style": profile.cliffhanger_style,
            "taboo_topics_count": len(profile.taboo_topics),
        }

    @staticmethod
    def list_markets() -> List[Dict[str, str]]:
        return list_locales()

    # ── Helpers ──

    def _build_character_guidance(self, profile: MarketProfile) -> str:
        lines = []
        for arch in profile.character_archetypes:
            lines.append(
                f"   {arch['role']} → {arch['archetype']}: {arch['traits']}"
            )
        return "\n".join(lines) if lines else "Adapt characters to local archetypes"

    def _build_genre_guidance(self, profile: MarketProfile, source_style: str) -> str:
        if not source_style:
            return f"Popular genres in this market: {', '.join(profile.popular_genres[:5])}"
        mapper = _style_to_genre_mapper()
        mapped = [mapper.get(g.strip(), g) for g in source_style.split("/")]
        return (
            f"Original style '{source_style}' should be adapted to "
            f"{profile.market_name} equivalents: {', '.join(mapped[:3])}. "
            f"Popular local genres: {', '.join(profile.popular_genres[:5])}"
        )

    def _build_user_prompt(
        self, request: LocalizationRequest, profile: MarketProfile
    ) -> str:
        parts = [
            f"请将以下{request.source_locale}短剧剧本{'进行轻度文化适配' if request.adaptation_level == 'light' else '完整本土化改编'}为{profile.market_name}市场版本。",
        ]
        if request.title:
            parts.append(f"剧本标题: {request.title}")
        if request.output_language:
            parts.append(f"输出语言: {request.output_language}")
        parts.append(f"\n--- 原始剧本 ---\n{request.script_content[:15000]}")
        parts.append("\n--- 请输出完整改编后的剧本 ---")
        return "\n".join(parts)

    def _localize_title(self, title: str, profile: MarketProfile) -> str:
        """Simple title localization using LLM or heuristics."""
        if not title:
            return ""
        # TODO: use LLM for nuanced title localization
        return title  # Placeholder — titles are usually re-named separately

    def _extract_character_mappings(
        self, source: str, localized: str
    ) -> Dict[str, str]:
        """Extract name mappings from source and localized scripts."""
        import re
        mappings = {}

        # Find Chinese names in source (2-3 character + common surname pattern)
        cn_names = set(re.findall(r'([一-鿿]{2,4})[：:]', source))

        # Find potential English/Arabic/etc names in localized
        # Simple heuristic: find capitalized words before colons
        localized_names = re.findall(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)[：:]', localized)

        # Crude mapping by order of appearance
        cn_list = sorted(cn_names, key=lambda n: source.index(n) if n in source else 99999)
        for i, cn_name in enumerate(cn_list[:min(5, len(localized_names))]):
            mappings[cn_name] = localized_names[i]

        return mappings


# ═══════════════════════════════════════════════════════════════
# Style → Genre Mapper (Chinese style → Market-specific genre)
# ═══════════════════════════════════════════════════════════════

def _style_to_genre_mapper() -> Dict[str, str]:
    """Map Chinese style names to locale-appropriate genre names."""
    return {
        "古装": "Historical Fantasy / Period Drama",
        "言情": "Romance",
        "爱情": "Romance",
        "悬疑": "Mystery Thriller",
        "推理": "Crime Mystery",
        "奇幻": "Fantasy / Paranormal",
        "科幻": "Sci-Fi",
        "重生": "Second Chance / Rebirth Drama",
        "穿越": "Time Travel Romance",
        "复仇": "Revenge Drama",
        "甜宠": "Sweet Romance",
        "虐恋": "Angst Romance / Tragic Love",
        "霸总": "Billionaire Romance",
        "玄幻": "Xianxia Fantasy / Cultivation Epic",
        "武侠": "Wuxia / Martial Arts Drama",
        "都市": "Urban / Contemporary",
        "现代": "Modern / Contemporary",
        "校园": "Campus / Youth",
        "职场": "Workplace / Office Drama",
    }
