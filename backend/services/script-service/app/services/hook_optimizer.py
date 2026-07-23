"""
钩子/付费点自动设计 — 短剧商业逻辑的核心引擎。

短剧的商业模式本质上是"让用户想点下一集" + "让用户愿意付费"。
AI 剧本不仅要有好的故事，更要在正确的位置放置正确类型的钩子。

核心能力:
1. 钩子注入: 在每集结尾自动生成高转化悬念
2. 付费点优化: 确定最佳付费位置 + 生成"卡点"内容
3. 钩子类型库: 7 种经过行业验证的钩子模式
4. 质量闭环: 生成 → QualityJudge 评分 → 不达标自动重写
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Hook Types (7 种行业验证的钩子模式)
# ═══════════════════════════════════════════════════════════════

class HookType(str, Enum):
    INFORMATION_ASYMMETRY = "information_asymmetry"  # 信息差: 观众知道，角色不知道
    LIFE_OR_DEATH = "life_or_death"                  # 生死危机: 主角命悬一线
    RELATIONSHIP_CLIFF = "relationship_cliff"         # 关系悬念: 告白/分手/误会
    IDENTITY_REVEAL = "identity_reveal"               # 身份揭露: "其实我是..."
    TRAP_SPRUNG = "trap_sprung"                       # 布局收网: 主角的计谋即将揭晓
    NEW_THREAT = "new_threat"                         # 新威胁: 更大的敌人出现
    EMOTIONAL_PEAK = "emotional_peak"                 # 情感高潮: 泪点/燃点


HOOK_PATTERNS: Dict[str, Dict[str, Any]] = {
    "information_asymmetry": {
        "name": "信息差悬念",
        "description": "观众知道一个角色不知道的关键信息，产生'快看后面'的焦虑感",
        "template": (
            "【角色A】还不知道，【关键信息】。而这件事将彻底改变一切。"
            "镜头切到【知情人】——他/她正在做【行动】，嘴角露出一丝【情绪】。"
        ),
        "effectiveness": 0.9,  # 最高的钩子转化率
        "best_for": ["悬疑反转", "重生复仇", "古装宫斗"],
    },
    "life_or_death": {
        "name": "生死危机",
        "description": "主角或重要角色面临生命安全威胁",
        "template": (
            "【威胁】逼近。主角的【弱点/限制】让逃跑变得不可能。"
            "最后一秒——【转折】。但这是救援还是……更大的陷阱？"
        ),
        "effectiveness": 0.85,
        "best_for": ["战神归来", "悬疑反转", "穿越系统"],
    },
    "relationship_cliff": {
        "name": "关系悬念",
        "description": "感情线的关键时刻卡住——告白被打断/误会刚产生/真相即将揭露",
        "template": (
            "【角色A】终于鼓起勇气——'【告白/质问/坦白的前半句】'。"
            "但【角色B】的手机/敲门声/尖叫声打断了这一刻。"
            "【角色A】低头看到——【意外发现】。表情凝固。"
        ),
        "effectiveness": 0.8,
        "best_for": ["霸总甜宠", "先婚后爱", "虐恋情深"],
    },
    "identity_reveal": {
        "name": "身份揭露",
        "description": "隐藏身份即将暴露或刚刚暴露的瞬间",
        "template": (
            "【角色】缓缓摘下面具/转过身/说出那个名字——'其实，我是【隐藏身份】。'"
            "在场所有人的表情都变了。尤其是【关键人物】——他/她的反应说明了一切。"
        ),
        "effectiveness": 0.85,
        "best_for": ["重生复仇", "战神归来", "悬疑反转"],
    },
    "trap_sprung": {
        "name": "布局收网",
        "description": "主角精心设计的计划即将实现——但可能有意外",
        "template": (
            "'一切都准备好了。'主角看着【场景】，眼神冷峻。"
            "但有一个细节——【意外因素】——主角没有算到。"
            "这个细节会在下一集改变一切。"
        ),
        "effectiveness": 0.75,
        "best_for": ["重生复仇", "古装宫斗", "搞钱经商"],
    },
    "new_threat": {
        "name": "新威胁出现",
        "description": "你以为最大的敌人已经被解决了？不，真正的 Boss 刚出现",
        "template": (
            "主角以为胜利了。但暗处——【新敌人】正在看着这一切。"
            "'有意思。'镜头特写——【新敌人的特征/动作】。'接下来该我玩了。'"
        ),
        "effectiveness": 0.8,
        "best_for": ["战神归来", "悬疑反转", "穿越系统"],
    },
    "emotional_peak": {
        "name": "情感高潮",
        "description": "情绪推到最高点后戛然而止——泪点/燃点/甜点",
        "template": (
            "【角色A】的眼泪终于落下。'【情感金句】。'"
            "音乐推高——回忆闪现——然后，黑屏。"
            "下一集: 【暗示】"
        ),
        "effectiveness": 0.7,
        "best_for": ["虐恋情深", "先婚后爱", "都市职场"],
    },
}


# ═══════════════════════════════════════════════════════════════
# Paywall Strategy
# ═══════════════════════════════════════════════════════════════

@dataclass
class PaywallConfig:
    """付费点配置"""
    positions: List[int] = field(default_factory=lambda: [10, 20])  # 默认第10、20集为付费点
    hook_type: HookType = HookType.INFORMATION_ASYMMETRY
    intensity: str = "极高"  # 付费点的钩子必须比普通钩子更强
    free_preview_episodes: int = 5  # 免费预览集数

    @classmethod
    def for_genre(cls, total_eps: int) -> "PaywallConfig":
        """根据总集数自动计算最佳付费点位置。

        策略:
        - 20集: 第10集（中点）+ 第17集（高潮前）
        - 24集: 第10集 + 第20集
        - 30集: 第10集 + 第20集
        - 16集: 第8集 + 第13集
        """
        if total_eps <= 16:
            return cls(positions=[8, 13], free_preview_episodes=4)
        elif total_eps <= 20:
            return cls(positions=[10, 17], free_preview_episodes=5)
        elif total_eps <= 24:
            return cls(positions=[10, 20], free_preview_episodes=5)
        else:
            return cls(positions=[10, 20], free_preview_episodes=5)


# ═══════════════════════════════════════════════════════════════
# HookInjector
# ═══════════════════════════════════════════════════════════════

class HookInjector:
    """钩子注入器 — 在指定集数结尾自动生成并注入钩子。

    与情节模板配合：模板标记了每集的 beat type 和 cliffhanger，
    HookInjector 将 cliffhanger 转化为可执行的钩子文本。
    """

    def __init__(self, llm=None, quality_judge=None):
        self.llm = llm
        self._judge = quality_judge

    def select_hook_type(
        self, episode_beat: str, genre: str, episode_num: int, is_paywall: bool = False
    ) -> HookType:
        """根据情节节拍、类型和位置选择最佳钩子类型。"""
        if is_paywall:
            # 付费点必须用最强的钩子
            return HookType.INFORMATION_ASYMMETRY

        beat_to_hook = {
            "hook": HookType.NEW_THREAT,
            "reversal": HookType.IDENTITY_REVEAL,
            "reveal": HookType.INFORMATION_ASYMMETRY,
            "climax": HookType.LIFE_OR_DEATH,
            "romance": HookType.RELATIONSHIP_CLIFF,
            "emotional": HookType.EMOTIONAL_PEAK,
            "conflict": HookType.TRAP_SPRUNG,
            "betrayal": HookType.IDENTITY_REVEAL,
            "trap": HookType.TRAP_SPRUNG,
        }

        return beat_to_hook.get(episode_beat, HookType.NEW_THREAT)

    def build_hook_prompt(
        self,
        hook_type: HookType,
        episode_content: str,
        episode_num: int,
        is_paywall: bool = False,
    ) -> str:
        """构建钩子生成的 prompt。"""
        pattern = HOOK_PATTERNS.get(hook_type.value, HOOK_PATTERNS["new_threat"])
        intensity = "极高" if is_paywall else "高"

        return (
            f"你是短剧钩子设计专家。为第{episode_num}集生成结尾钩子（cliffhanger）。\n\n"
            f"【钩子类型】{pattern['name']}（{pattern['description']}）\n"
            f"【钩子强度要求】{intensity}\n"
            f"【参考模板】{pattern['template']}\n\n"
            f"【当前剧情】\n{episode_content[-2000:]}\n\n"
            f"【要求】\n"
            f"1. 生成 3-5 句话的钩子\n"
            f"2. 使用短剧行业标准格式（△ 描述 + 角色名：台词）\n"
            f"3. 必须在观众心中制造强烈的'下一集会怎样'的冲动\n"
            f"{'4. 这是付费点位置——钩子必须让用户产生强烈的付费冲动' if is_paywall else ''}\n"
            f"5. 钩子必须与当前剧情逻辑自洽，不能凭空出现新信息\n"
        )

    async def inject_hook(
        self,
        episode_content: str,
        episode_num: int,
        beat_type: str,
        genre: str = "",
        is_paywall: bool = False,
        max_retries: int = 2,
    ) -> str:
        """为一集剧本注入结尾钩子。

        Args:
            episode_content: 该集剧本内容
            episode_num: 集号
            beat_type: 该集的情节节拍类型
            genre: 短剧类型
            is_paywall: 是否为付费点
            max_retries: 质量不达标时的最大重试次数

        Returns:
            带钩子的完整该集剧本
        """
        hook_type = self.select_hook_type(beat_type, genre, episode_num, is_paywall)

        for attempt in range(max_retries + 1):
            try:
                if self.llm:
                    prompt = self.build_hook_prompt(
                        hook_type, episode_content, episode_num, is_paywall
                    )
                    from langchain_core.messages import HumanMessage
                    response = await self.llm.ainvoke(
                        [HumanMessage(content=prompt)],
                        config={"timeout": 60},
                    )
                    hook_text = response.content.strip()
                else:
                    # No LLM: use template-based fallback
                    pattern = HOOK_PATTERNS.get(hook_type.value)
                    hook_text = f"△{pattern['description']}\n\n（悬念待展开——下一集揭晓）"

                # Validate hook quality
                if self._judge and attempt < max_retries:
                    judge_result = await self._judge.judge_script(
                        content=episode_content + "\n\n" + hook_text,
                        max_chars=2000,
                    )
                    # Check cliffhanger quality specifically
                    if hasattr(judge_result, 'scores'):
                        cliff_score = judge_result.scores.get("cliffhanger_quality", 80)
                        if cliff_score < 50:
                            logger.warning(
                                f"Hook quality low ({cliff_score}/100) for ep {episode_num}, "
                                f"retrying (attempt {attempt+1})"
                            )
                            continue

                return episode_content + "\n\n【结尾钩子】\n" + hook_text

            except Exception as e:
                logger.warning(f"Hook injection failed ep {episode_num} attempt {attempt+1}: {e}")
                if attempt >= max_retries:
                    # Fallback: return original with generic hook
                    return episode_content + "\n\n△（悬念未完——持续关注下一集）"

        return episode_content

    async def inject_all_hooks(
        self,
        episodes: List[Dict[str, Any]],
        beat_types: List[str],
        genre: str = "",
        paywall_positions: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """批量为所有集注入钩子。

        Args:
            episodes: 分集列表 [{episode_number, content}, ...]
            beat_types: 每集的节拍类型
            genre: 短剧类型
            paywall_positions: 付费点位置列表

        Returns:
            注入钩子后的分集列表
        """
        paywall_positions = paywall_positions or []
        result = []

        for i, ep in enumerate(episodes):
            ep_num = ep.get("episode_number", i + 1)
            beat = beat_types[i] if i < len(beat_types) else "conflict"
            is_paywall = ep_num in paywall_positions

            content = ep.get("content", "")
            if content:
                enhanced = await self.inject_hook(
                    episode_content=content,
                    episode_num=ep_num,
                    beat_type=beat,
                    genre=genre,
                    is_paywall=is_paywall,
                )
                ep = {**ep, "content": enhanced, "hook_injected": True}
            result.append(ep)

        logger.info(
            f"HookInjector: processed {len(episodes)} episodes, "
            f"{len(paywall_positions)} paywalls"
        )
        return result


# ═══════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════

def get_hook_patterns() -> List[Dict[str, Any]]:
    """List all available hook patterns."""
    return [
        {
            "id": k,
            "name": v["name"],
            "description": v["description"],
            "effectiveness": v["effectiveness"],
            "best_for": v["best_for"],
        }
        for k, v in HOOK_PATTERNS.items()
    ]


def get_paywall_config(total_episodes: int) -> PaywallConfig:
    """Get optimal paywall configuration for episode count."""
    return PaywallConfig.for_genre(total_episodes)
