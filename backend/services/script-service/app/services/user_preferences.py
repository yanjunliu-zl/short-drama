"""
用户偏好学习 v2 — 基于创作行为 + 选择反馈 + 编辑习惯的个性化引擎。

v2 升级:
- 多版本选择追踪: 用户选了 A/B/C 哪个版本 → 学习叙事风格偏好
- 编辑行为学习: 用户改了哪些内容 → 学习具体偏好
- 强化信号: 用户反复使用的风格/题材 → 强度递增
- 冷启动: 新用户基于初始选择快速建立画像

对标: YouTube 推荐算法思路（行为 > 声明）
"""
import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from collections import Counter, defaultdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── 偏好映射 ──
STYLE_TIPS = {
    "悬疑": "偏好悬疑风格，注重伏笔埋设和反转设计，节奏紧凑",
    "浪漫喜剧": "偏好浪漫喜剧，注重角色互动和幽默对白，氛围轻松",
    "古装": "偏好古装风格，注重历史细节和古典对白，场景考究",
    "科幻": "偏好科幻风格，注重世界观构建和未来感视觉",
    "写实": "偏好写实风格，注重生活细节和真实情感",
    "爱情": "偏好爱情题材，注重情感层次和浪漫场景",
    "复仇": "偏好复仇题材，注重情绪铺垫和高潮反转",
    "重生": "偏好重生/穿越题材，注重信息差和蝴蝶效应",
    "霸总": "偏好霸道总裁题材，注重权力不对等下的情感张力",
    "甜宠": "偏好甜宠风格，注重日常互动和温馨氛围",
    "虐恋": "偏好虐恋风格，注重情感起伏和情绪张力",
}

THEME_TIPS = {
    "爱情": "擅长爱情线描写，可强化情感冲突",
    "复仇": "擅长复仇叙事，可强化动机铺垫和反转",
    "成长": "擅长成长故事，可强化角色弧线",
    "悬疑": "擅长悬疑推理，可强化线索设计和反转",
    "商战": "擅长商业对抗，可强化智谋博弈",
    "宫斗": "擅长权力斗争，可强化计谋布局",
}


class UserPreferenceProfile:
    """用户创作偏好画像 v2"""

    def __init__(self, user_id: str = ""):
        self.user_id = user_id
        self.total_scripts: int = 0
        self.total_sessions: int = 0

        # Style preferences
        self.favorite_styles: List[str] = []
        self.favorite_themes: List[str] = []
        self.preferred_length: str = "短篇"

        # Narrative angle preference (from multi-version choices)
        self.angle_preferences: Dict[str, float] = {}
        # {"standard": 0.6, "emotional": 0.3, "twist": 0.1}

        # Pacing preference (inferred from edit behavior)
        self.pacing_preference: str = "balanced"  # fast | balanced | slow
        self.dialogue_ratio_preference: float = 0.0  # 0 = no preference, otherwise 0.3-0.7

        # Character type affinity
        self.character_archetypes: List[str] = []
        self.character_archetype_counts: Dict[str, int] = defaultdict(int)

        # Edit behavior
        self.avg_edit_distance: int = 0        # Avg chars changed per edit
        self.common_edit_targets: List[str] = []  # What user most frequently edits
        # ["dialogue", "ending", "character_description", ...]

        # Script metrics
        self.avg_script_length: int = 0
        self.avg_episode_count: int = 0

        # Learning signals
        self.style_signals: Dict[str, int] = defaultdict(int)    # style → use count
        self.theme_signals: Dict[str, int] = defaultdict(int)    # theme → use count
        self.length_signals: Dict[str, int] = defaultdict(int)   # length → use count

        # Timestamps
        self.last_updated: str = ""
        self.created_at: str = ""

    @property
    def is_cold_start(self) -> bool:
        return self.total_scripts < 2

    # ── Learning Methods ──

    def record_generation(
        self, style: str, theme: str, length: str, episode_count: int = 10
    ):
        """Record a script generation event."""
        self.total_scripts += 1
        self.total_sessions += 1
        if style:
            self.style_signals[style] += 1
        if theme:
            self.theme_signals[theme] += 1
        if length:
            self.length_signals[length] += 1
        if episode_count:
            self.avg_episode_count = int(
                (self.avg_episode_count * (self.total_scripts - 1) + episode_count)
                / self.total_scripts
            )

        self._rebuild()
        self.last_updated = datetime.now(timezone.utc).isoformat()

    def record_version_choice(
        self, chosen_version: str, all_versions: List[Dict[str, Any]]
    ):
        """Record which multi-version the user selected.

        Args:
            chosen_version: "A", "B", or "C"
            all_versions: [{version, label, score}, ...]
        """
        angle_map = {
            "A": "standard",    # 标准短剧风格
            "B": "emotional",   # 情感向
            "C": "twist",       # 反转向
        }

        angle = angle_map.get(chosen_version, "standard")
        # EMA update: alpha=0.3
        for a in self.angle_preferences:
            self.angle_preferences[a] *= 0.7  # decay
        self.angle_preferences[angle] = self.angle_preferences.get(angle, 0) + 0.3

        # Normalize
        total = sum(self.angle_preferences.values())
        if total > 0:
            for a in self.angle_preferences:
                self.angle_preferences[a] /= total

        logger.info(
            f"User {self.user_id}: angle preference updated → "
            f"{self.angle_preferences}"
        )

    def record_edit(
        self, original_content: str, edited_content: str, edit_targets: List[str] = None
    ):
        """Record user edit behavior to learn detailed preferences.

        Args:
            original_content: Original generated script
            edited_content: User's edited version
            edit_targets: What parts user edited (dialogue, ending, character...)
        """
        edit_distance = abs(len(edited_content) - len(original_content))
        if self.avg_edit_distance:
            self.avg_edit_distance = int(
                (self.avg_edit_distance * (self.total_sessions - 1) + edit_distance)
                / self.total_sessions
            )
        else:
            self.avg_edit_distance = edit_distance

        if edit_targets:
            for target in edit_targets:
                # Track common edit targets
                pass  # TODO: persist to DB

        # Infer pacing preference from edit patterns
        if edit_distance > len(original_content) * 0.3:
            # User added a lot → may prefer more detail/slower pace
            if self.pacing_preference == "fast":
                self.pacing_preference = "balanced"

        self.last_updated = datetime.now(timezone.utc).isoformat()

    def record_accept(self):
        """Record that user accepted the script without edits — strong positive signal."""
        # Boost all current signals
        for style in list(self.style_signals.keys())[-3:]:
            self.style_signals[style] += 1
        for theme in list(self.theme_signals.keys())[-3:]:
            self.theme_signals[theme] += 1

    # ── Inference ──

    def infer_angle_preference(self) -> str:
        """Infer user's preferred narrative angle."""
        if not self.angle_preferences:
            return "standard"
        return max(self.angle_preferences, key=self.angle_preferences.get)

    def infer_genre_affinity(self, style: str, theme: str) -> float:
        """How strongly does the user prefer this style+theme combination? 0-1."""
        if self.is_cold_start:
            return 0.0
        style_score = self.style_signals.get(style, 0) / max(self.total_scripts, 1)
        theme_score = self.theme_signals.get(theme, 0) / max(self.total_scripts, 1)
        return (style_score + theme_score) / 2

    # ── Export ──

    def to_prompt_context(self) -> str:
        """Convert preferences into LLM prompt context."""
        if self.total_scripts < 2:
            return ""

        parts = []

        # Style & Theme
        if self.favorite_styles:
            tips = [STYLE_TIPS.get(s, "") for s in self.favorite_styles[:2]]
            parts.append(
                f"用户偏好风格: {', '.join(self.favorite_styles[:3])}。"
                + " ".join(t for t in tips if t)
            )

        if self.favorite_themes:
            parts.append(f"用户偏好题材: {', '.join(self.favorite_themes[:3])}")

        # Narrative angle
        if self.angle_preferences:
            preferred = self.infer_angle_preference()
            angle_desc = {
                "standard": "快节奏强钩子",
                "emotional": "情感向深角色",
                "twist": "高反转多惊喜",
            }
            parts.append(
                f"用户叙事偏好: {angle_desc.get(preferred, '标准风格')} "
                f"(权重: {', '.join(f'{k}={v:.1f}' for k,v in self.angle_preferences.items())})"
            )

        # Pacing
        if self.pacing_preference != "balanced":
            pacing_desc = {
                "fast": "偏好快节奏，场景转换要快，对话要简洁",
                "slow": "偏好慢节奏，注重细节描写和氛围营造",
            }
            parts.append(pacing_desc.get(self.pacing_preference, ""))

        # Length
        if self.preferred_length:
            parts.append(f"用户常用篇幅: {self.preferred_length}")

        # Character types
        if self.character_archetypes:
            parts.append(f"常用角色类型: {', '.join(self.character_archetypes[:3])}")

        if parts:
            return "【用户创作偏好 — 请参考以下信息调整剧本风格】\n" + "\n".join(parts)
        return ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "total_scripts": self.total_scripts,
            "favorite_styles": self.favorite_styles,
            "favorite_themes": self.favorite_themes,
            "preferred_length": self.preferred_length,
            "angle_preferences": self.angle_preferences,
            "pacing_preference": self.pacing_preference,
            "character_archetypes": self.character_archetypes,
            "avg_script_length": self.avg_script_length,
            "avg_episode_count": self.avg_episode_count,
            "avg_edit_distance": self.avg_edit_distance,
            "is_cold_start": self.is_cold_start,
        }

    # ── Internal ──

    def _rebuild(self):
        """Rebuild derived fields from signal counters."""
        style_counter = Counter(dict(self.style_signals))
        theme_counter = Counter(dict(self.theme_signals))
        length_counter = Counter(dict(self.length_signals))

        self.favorite_styles = [s for s, _ in style_counter.most_common(3)]
        self.favorite_themes = [t for t, _ in theme_counter.most_common(3)]
        self.preferred_length = (
            length_counter.most_common(1)[0][0] if length_counter else "短篇"
        )


# ═══════════════════════════════════════════════════════════════
# Service
# ═══════════════════════════════════════════════════════════════

class UserPreferenceService:
    """用户偏好服务 v2"""

    def __init__(self):
        self._cache: Dict[str, UserPreferenceProfile] = {}

    async def initialize(self):
        pass

    async def get_profile(
        self, user_id: str, db_session=None
    ) -> UserPreferenceProfile:
        if not user_id or user_id == "anonymous":
            return UserPreferenceProfile(user_id="anonymous")

        if user_id in self._cache:
            return self._cache[user_id]

        profile = UserPreferenceProfile(user_id=user_id)

        if db_session is None:
            self._cache[user_id] = profile
            return profile

        try:
            from sqlalchemy import text
            sql = text("""
                SELECT title, theme, style, length, content, characters
                FROM scripts
                WHERE user_id = :uid AND status = 'completed'
                ORDER BY created_at DESC LIMIT 30
            """)
            rows = await db_session.execute(sql, {"uid": user_id})
            rows_list = rows.fetchall()

            if not rows_list:
                self._cache[user_id] = profile
                return profile

            profile.total_scripts = len(rows_list)
            total_chars = 0

            for row in rows_list:
                if row.style:
                    profile.style_signals[row.style] += 1
                if row.theme:
                    profile.theme_signals[row.theme] += 1
                if row.length:
                    profile.length_signals[row.length] += 1
                if row.content:
                    total_chars += len(row.content)

            profile._rebuild()
            profile.avg_script_length = total_chars // max(profile.total_scripts, 1)

            self._cache[user_id] = profile
            logger.info(
                f"User profile built v2: user={user_id} scripts={profile.total_scripts} "
                f"styles={profile.favorite_styles} themes={profile.favorite_themes} "
                f"angle={profile.infer_angle_preference()}"
            )
        except Exception as e:
            logger.warning(f"User profile build failed (non-critical): {e}")

        self._cache[user_id] = profile
        return profile

    async def record_feedback(
        self, user_id: str, feedback: Dict[str, Any], db_session=None
    ):
        """Record user feedback from multi-version selection or edits.

        Args:
            feedback: {
                action: "version_chosen" | "accepted" | "edited",
                chosen_version: "A"|"B"|"C",
                style: str, theme: str, length: str,
                ...
            }
        """
        profile = await self.get_profile(user_id, db_session)

        action = feedback.get("action", "")
        if action == "version_chosen":
            profile.record_version_choice(
                feedback.get("chosen_version", "A"),
                feedback.get("all_versions", []),
            )
        elif action == "accepted":
            profile.record_accept()
        elif action == "edited":
            profile.record_edit(
                feedback.get("original_content", ""),
                feedback.get("edited_content", ""),
                feedback.get("edit_targets", []),
            )

        # Also record generation metadata
        if feedback.get("style") or feedback.get("theme"):
            profile.record_generation(
                style=feedback.get("style", ""),
                theme=feedback.get("theme", ""),
                length=feedback.get("length", "短篇"),
                episode_count=feedback.get("episode_count", 10),
            )

        self._cache[user_id] = profile

    def invalidate(self, user_id: str):
        self._cache.pop(user_id, None)


# Global instance
_user_preference_service: Optional[UserPreferenceService] = None


async def get_user_preference_service() -> UserPreferenceService:
    global _user_preference_service
    if _user_preference_service is None:
        _user_preference_service = UserPreferenceService()
        await _user_preference_service.initialize()
    return _user_preference_service
