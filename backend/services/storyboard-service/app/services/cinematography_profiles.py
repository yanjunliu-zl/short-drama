"""
电影摄影风格预设 — 移植自 moyin-creator 的 cinematography-profiles.ts

17 种预设，5 大分类，为分镜生成提供一致的视觉语言基线。
"""
from typing import Optional, Dict, List


class CinematographyProfile:
    """电影摄影风格预设"""

    def __init__(
        self,
        id: str,
        name: str,
        category: str,
        lighting_style: Optional[str] = None,
        lighting_direction: Optional[str] = None,
        color_temperature: Optional[str] = None,
        depth_of_field: Optional[str] = None,
        camera_rig: Optional[str] = None,
        movement_speed: Optional[str] = None,
        atmospheric_effects: Optional[str] = None,
        effect_intensity: Optional[str] = None,
        playback_speed: Optional[str] = None,
        camera_angle: Optional[str] = None,
        focal_length: Optional[str] = None,
        photography_technique: Optional[str] = None,
        description: str = "",
    ):
        self.id = id
        self.name = name
        self.category = category
        self.lighting_style = lighting_style
        self.lighting_direction = lighting_direction
        self.color_temperature = color_temperature
        self.depth_of_field = depth_of_field
        self.camera_rig = camera_rig
        self.movement_speed = movement_speed
        self.atmospheric_effects = atmospheric_effects
        self.effect_intensity = effect_intensity
        self.playback_speed = playback_speed
        self.camera_angle = camera_angle
        self.focal_length = focal_length
        self.photography_technique = photography_technique
        self.description = description


# =============================================================
# 17 种预设
# =============================================================

PROFILES: Dict[str, CinematographyProfile] = {
    # ---- 经典电影 ----
    "classic-cinematic": CinematographyProfile(
        id="classic-cinematic",
        name="经典电影感",
        category="经典电影",
        lighting_style="三点布光",
        lighting_direction="正面偏侧",
        color_temperature="暖色调 3200K",
        depth_of_field="浅景深",
        camera_rig="斯坦尼康",
        movement_speed="缓慢流畅",
        description="经典好莱坞式电影感，柔和灯光，浅景深，流畅运镜",
    ),
    "film-noir": CinematographyProfile(
        id="film-noir",
        name="黑色电影",
        category="经典电影",
        lighting_style="低调光",
        lighting_direction="侧光",
        color_temperature="冷色调 4000K",
        depth_of_field="中等景深",
        camera_rig="三脚架",
        movement_speed="极少运动",
        atmospheric_effects="雾",
        effect_intensity="轻微",
        description="高对比度，深阴影，硬朗灯光，黑色电影风格",
    ),
    # ---- 纪录片 ----
    "documentary": CinematographyProfile(
        id="documentary",
        name="纪实风格",
        category="纪录片",
        lighting_style="自然光",
        lighting_direction="环境光",
        color_temperature="自然光 5600K",
        depth_of_field="深景深",
        camera_rig="手持",
        movement_speed="自然晃动",
        description="自然光线，手持摄影，纪录片真实感",
    ),
    "natural-light": CinematographyProfile(
        id="natural-light",
        name="自然光纪录",
        category="纪录片",
        lighting_style="自然光",
        lighting_direction="窗光/天光",
        color_temperature="日光 5500K",
        depth_of_field="中等景深",
        camera_rig="肩扛",
        movement_speed="呼吸感",
        description="纯自然光拍摄，无人工布光痕迹",
    ),
    # ---- 风格化 ----
    "cyberpunk-neon": CinematographyProfile(
        id="cyberpunk-neon",
        name="赛博朋克霓虹",
        category="风格化",
        lighting_style="霓虹光",
        lighting_direction="多方向彩色",
        color_temperature="混合色温（蓝+品红）",
        depth_of_field="浅景深",
        camera_rig="滑轨",
        movement_speed="缓慢",
        atmospheric_effects="雾",
        effect_intensity="中等",
        description="霓虹灯光，赛博朋克美学，雨夜氛围",
    ),
    "wong-kar-wai": CinematographyProfile(
        id="wong-kar-wai",
        name="王家卫色调",
        category="风格化",
        lighting_style="低调光",
        lighting_direction="侧光+逆光",
        color_temperature="暖调偏绿 2800K",
        depth_of_field="浅景深",
        camera_rig="手持",
        movement_speed="慢动作",
        photography_technique="step-printing 降格拍摄",
        description="浓郁色彩，降格慢镜，霓虹灯光，王家卫式美学",
    ),
    "japanese-fresh": CinematographyProfile(
        id="japanese-fresh",
        name="日系清新",
        category="风格化",
        lighting_style="自然光",
        lighting_direction="逆光+柔光",
        color_temperature="偏冷 5000K",
        depth_of_field="浅景深",
        camera_rig="斯坦尼康",
        movement_speed="缓慢",
        description="日系小清新，自然逆光，高调柔和色调，空气感",
    ),
    # ---- 类型片 ----
    "wuxia-classic": CinematographyProfile(
        id="wuxia-classic",
        name="武侠经典",
        category="类型片",
        lighting_style="三点布光",
        lighting_direction="多角度",
        color_temperature="自然光 5600K",
        depth_of_field="深景深",
        camera_rig="摇臂",
        movement_speed="快速",
        atmospheric_effects="尘雾",
        effect_intensity="轻微",
        description="武侠片风格，广角深景深，摇臂运动，尘雾氛围",
    ),
    "suspense-thriller": CinematographyProfile(
        id="suspense-thriller",
        name="悬疑惊悚",
        category="类型片",
        lighting_style="低调光",
        lighting_direction="侧光+逆光",
        color_temperature="冷色调 4500K",
        depth_of_field="浅景深",
        camera_rig="手持",
        movement_speed="紧张晃动",
        description="悬疑片风格，暗调灯光，浅景深，手持紧张感",
    ),
    "romantic-comedy": CinematographyProfile(
        id="romantic-comedy",
        name="浪漫喜剧",
        category="类型片",
        lighting_style="高调光",
        lighting_direction="正面柔光",
        color_temperature="暖色调 3200K",
        depth_of_field="浅景深",
        camera_rig="斯坦尼康",
        movement_speed="流畅",
        description="浪漫喜剧风格，明亮柔光，暖色调，流畅运镜",
    ),
    "sci-fi-future": CinematographyProfile(
        id="sci-fi-future",
        name="科幻未来",
        category="类型片",
        lighting_style="霓虹光",
        lighting_direction="多方向",
        color_temperature="冷色调 6000K",
        depth_of_field="中等景深",
        camera_rig="滑轨",
        movement_speed="精确缓慢",
        atmospheric_effects="粒子",
        effect_intensity="轻微",
        description="科幻风格，冷色调，霓虹灯光，精确运镜，粒子效果",
    ),
    "family-warmth": CinematographyProfile(
        id="family-warmth",
        name="家庭温馨",
        category="类型片",
        lighting_style="自然光",
        lighting_direction="窗光",
        color_temperature="暖色调 3000K",
        depth_of_field="中等景深",
        camera_rig="三脚架",
        movement_speed="极少运动",
        description="温暖家庭氛围，自然窗光，暖色调，稳定构图",
    ),
    # ---- 年代 ----
    "hk-retro-90s": CinematographyProfile(
        id="hk-retro-90s",
        name="港风复古90s",
        category="年代",
        lighting_style="低调光",
        lighting_direction="侧光+霓虹",
        color_temperature="混合色温 3200K",
        depth_of_field="中等景深",
        camera_rig="手持",
        movement_speed="自然",
        description="90年代港片风格，混合灯光，手持摄影，复古质感",
    ),
    "republican-era": CinematographyProfile(
        id="republican-era",
        name="民国风情",
        category="年代",
        lighting_style="自然光",
        lighting_direction="窗光+烛光",
        color_temperature="暖色调 2800K",
        depth_of_field="浅景深",
        camera_rig="滑轨",
        movement_speed="缓慢优雅",
        description="民国时期美学，暖光，浅景深，优雅缓慢运镜",
    ),
    "ancient-palace": CinematographyProfile(
        id="ancient-palace",
        name="古装宫廷",
        category="年代",
        lighting_style="三点布光",
        lighting_direction="多角度",
        color_temperature="暖色 3200K",
        depth_of_field="深景深",
        camera_rig="摇臂",
        movement_speed="缓慢",
        atmospheric_effects="烛光",
        effect_intensity="轻微",
        description="古装宫廷风格，宏大构图，摇曳烛光，金色暖调",
    ),
    "renaissance": CinematographyProfile(
        id="renaissance",
        name="文艺复兴",
        category="年代",
        lighting_style="侧光",
        lighting_direction="窗口光",
        color_temperature="暖金色 2700K",
        depth_of_field="浅景深",
        camera_rig="三脚架",
        movement_speed="极少运动",
        photography_technique="chiaroscuro 明暗对照法",
        description="文艺复兴绘画风格，窗口侧光，明暗对照，静态构图",
    ),
}


def get_profile(profile_id: str) -> Optional[CinematographyProfile]:
    """根据 ID 获取摄影风格预设"""
    return PROFILES.get(profile_id)


def list_profiles(category: Optional[str] = None) -> List[CinematographyProfile]:
    """列出所有（或按分类筛选）摄影风格预设"""
    if category:
        return [p for p in PROFILES.values() if p.category == category]
    return list(PROFILES.values())


PROFILE_CATEGORIES: List[str] = ["经典电影", "纪录片", "风格化", "类型片", "年代"]
