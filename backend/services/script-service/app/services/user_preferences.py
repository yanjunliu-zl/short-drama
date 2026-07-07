"""
用户偏好记忆 — 基于历史创作行为构建个性化创作画像。

从数据库提取用户历史：
  - 偏好风格 (style preferences)
  - 偏好题材 (theme preferences)
  - 常用角色类型 (character archetypes)
  - 创作习惯 (length preferences, creation frequency)

在新剧本生成时，将用户画像注入 System Prompt 作为个性化上下文。
"""
import logging
from typing import Dict, Any, List, Optional
from collections import Counter

logger = logging.getLogger(__name__)

# 风格偏好映射到创作建议
STYLE_TIPS = {
    "悬疑": "偏好悬疑风格，注重伏笔埋设和反转设计，节奏紧凑",
    "浪漫喜剧": "偏好浪漫喜剧，注重角色互动和幽默对白，氛围轻松",
    "古装": "偏好古装风格，注重历史细节和古典对白，场景考究",
    "科幻": "偏好科幻风格，注重世界观构建和未来感视觉",
    "写实": "偏好写实风格，注重生活细节和真实情感",
    "爱情": "偏好爱情题材，注重情感层次和浪漫场景",
}

THEME_TIPS = {
    "爱情": "擅长爱情线描写，可强化情感冲突",
    "复仇": "擅长复仇叙事，可强化动机铺垫和反转",
    "成长": "擅长成长故事，可强化角色弧线",
    "悬疑": "擅长悬疑推理，可强化线索设计和反转",
}


class UserPreferenceProfile:
    """用户创作偏好画像"""

    def __init__(self, user_id: str = ""):
        self.user_id = user_id
        self.total_scripts: int = 0
        self.favorite_styles: List[str] = []  # Top 3
        self.favorite_themes: List[str] = []  # Top 3
        self.preferred_length: str = "短篇"
        self.character_archetypes: List[str] = []  # Top 3
        self.avg_script_length: int = 0  # Chars

    def to_prompt_context(self) -> str:
        """Convert preferences into a prompt context string for LLM."""
        if self.total_scripts < 2:
            return ""

        parts = []
        if self.favorite_styles:
            parts.append(f"用户偏好风格: {', '.join(self.favorite_styles[:3])}")
            style_tips = [STYLE_TIPS.get(s, "") for s in self.favorite_styles[:2]]
            parts.append(f"风格建议: {'; '.join(t for t in style_tips if t)}")

        if self.favorite_themes:
            parts.append(f"用户偏好题材: {', '.join(self.favorite_themes[:3])}")
            theme_tips = [THEME_TIPS.get(t, "") for t in self.favorite_themes[:2]]
            parts.append(f"题材建议: {'; '.join(t for t in theme_tips if t)}")

        if self.preferred_length:
            parts.append(f"用户常用篇幅: {self.preferred_length}")

        if self.character_archetypes:
            parts.append(f"常用角色类型: {', '.join(self.character_archetypes[:3])}")

        if parts:
            return "【用户创作偏好】\n" + "\n".join(parts)

        return ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "total_scripts": self.total_scripts,
            "favorite_styles": self.favorite_styles,
            "favorite_themes": self.favorite_themes,
            "preferred_length": self.preferred_length,
            "character_archetypes": self.character_archetypes,
            "avg_script_length": self.avg_script_length,
        }


class UserPreferenceService:
    """用户偏好服务 — 从 DB 提取并缓存用户创作画像"""

    def __init__(self):
        self._cache: Dict[str, UserPreferenceProfile] = {}
        self._initialized = False

    async def initialize(self):
        self._initialized = True

    async def get_profile(self, user_id: str, db_session=None) -> UserPreferenceProfile:
        """Get or build user preference profile from script history.

        Uses in-memory cache; results are lightweight so no Redis needed.
        """
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
                ORDER BY created_at DESC LIMIT 20
            """)
            rows = await db_session.execute(sql, {"uid": user_id})
            rows_list = rows.fetchall()

            if not rows_list:
                self._cache[user_id] = profile
                return profile

            profile.total_scripts = len(rows_list)
            styles = []
            themes = []
            lengths = []
            total_chars = 0

            for row in rows_list:
                if row.style:
                    styles.append(row.style)
                if row.theme:
                    themes.append(row.theme)
                if row.length:
                    lengths.append(row.length)
                if row.content:
                    total_chars += len(row.content)

            # Top counts
            style_counter = Counter(styles)
            theme_counter = Counter(themes)
            length_counter = Counter(lengths)

            profile.favorite_styles = [s for s, _ in style_counter.most_common(3)]
            profile.favorite_themes = [t for t, _ in theme_counter.most_common(3)]
            profile.preferred_length = length_counter.most_common(1)[0][0] if length_counter else "短篇"
            profile.avg_script_length = total_chars // max(profile.total_scripts, 1)

            self._cache[user_id] = profile
            logger.info(
                f"User profile built: user={user_id} scripts={profile.total_scripts} "
                f"styles={profile.favorite_styles} themes={profile.favorite_themes}"
            )
        except Exception as e:
            logger.warning(f"User profile build failed (non-critical): {e}")

        self._cache[user_id] = profile
        return profile

    def invalidate(self, user_id: str):
        """Clear cached profile (call after new script is completed)."""
        self._cache.pop(user_id, None)


# Global instance
_user_preference_service: Optional[UserPreferenceService] = None


async def get_user_preference_service() -> UserPreferenceService:
    global _user_preference_service
    if _user_preference_service is None:
        _user_preference_service = UserPreferenceService()
        await _user_preference_service.initialize()
    return _user_preference_service
