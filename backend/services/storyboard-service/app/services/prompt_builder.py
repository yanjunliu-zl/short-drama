"""
5 层语义提示词构建器 — 移植自 moyin-creator 的 prompt-builder.ts

层级结构：
  Layer 1: 镜头设计 (Camera) - 最高优先级
  Layer 1.5: 灯光设计 (Lighting)
  Layer 2: 内容焦点 (Subject) - 次高优先级
  Layer 3: 氛围修饰 (Mood / Narrative)
  Layer 4: 场景音频 (Setting & Audio)
  Layer 5: 视觉风格 (Style)
"""
from typing import Optional, List, Dict
from cinematography_profiles import CinematographyProfile


# =============================================================
# Shot 数据结构（精简版，完整 Schema 见 schemas/storyboard.py）
# =============================================================

class ShotPromptInput:
    """提示词构建所需的镜头输入"""
    def __init__(
        self,
        shot_type: str = "中景",
        duration: int = 5,
        camera_angle: str = "正面平视",
        description: str = "",
        dialogue: str = "",
        characters: List[str] = None,
        location: str = "",
        # 扩展字段
        image_prompt: Optional[str] = None,
        video_prompt: Optional[str] = None,
        end_frame_prompt: Optional[str] = None,
        needs_end_frame: bool = False,
        lighting_style: Optional[str] = None,
        lighting_direction: Optional[str] = None,
        color_temperature: Optional[str] = None,
        depth_of_field: Optional[str] = None,
        focus_target: Optional[str] = None,
        focus_transition: Optional[str] = None,
        camera_rig: Optional[str] = None,
        movement_speed: Optional[str] = None,
        camera_movement: Optional[str] = None,
        shot_size: Optional[str] = None,
        emotion_tags: List[str] = None,
        narrative_function: Optional[str] = None,
        atmospheric_effects: Optional[str] = None,
        effect_intensity: Optional[str] = None,
        continuity_ref: Optional[str] = None,
        focal_length: Optional[str] = None,
        photography_technique: Optional[str] = None,
        playback_speed: Optional[str] = None,
        # 风格
        style: str = "电影级写实",
    ):
        self.shot_type = shot_type
        self.duration = duration
        self.camera_angle = camera_angle
        self.description = description
        self.dialogue = dialogue
        self.characters = characters or []
        self.location = location
        self.image_prompt = image_prompt
        self.video_prompt = video_prompt
        self.end_frame_prompt = end_frame_prompt
        self.needs_end_frame = needs_end_frame
        self.lighting_style = lighting_style
        self.lighting_direction = lighting_direction
        self.color_temperature = color_temperature
        self.depth_of_field = depth_of_field
        self.focus_target = focus_target
        self.focus_transition = focus_transition
        self.camera_rig = camera_rig
        self.movement_speed = movement_speed
        self.camera_movement = camera_movement
        self.shot_size = shot_size
        self.emotion_tags = emotion_tags or []
        self.narrative_function = narrative_function
        self.atmospheric_effects = atmospheric_effects
        self.effect_intensity = effect_intensity
        self.continuity_ref = continuity_ref
        self.focal_length = focal_length
        self.photography_technique = photography_technique
        self.playback_speed = playback_speed
        self.style = style


# =============================================================
# 镜头术语映射表
# =============================================================

_SHOT_TYPE_MAP: Dict[str, str] = {
    "远景": "extreme wide shot, establishing the full environment",
    "全景": "full shot, showing the complete character from head to toe",
    "中景": "medium shot, waist-up framing",
    "近景": "close-up, chest-up framing",
    "特写": "extreme close-up, focusing on facial details",
    "大特写": "macro close-up, extreme detail on a specific feature",
    "过肩镜头": "over-the-shoulder shot, intimate perspective",
}

_CAMERA_ANGLE_MAP: Dict[str, str] = {
    "正面平视": "eye-level, straight-on",
    "俯视": "high angle, looking down",
    "仰视": "low angle, looking up",
    "斜侧": "dutch angle, tilted frame",
    "鸟瞰": "bird's eye view, directly overhead",
    "鱼眼": "fisheye, extreme wide distortion",
}

_LIGHTING_STYLE_MAP: Dict[str, str] = {
    "自然光": "natural daylight, soft ambient illumination",
    "三点布光": "classic three-point lighting (key, fill, rim)",
    "高调光": "high-key lighting, bright even illumination",
    "低调光": "low-key lighting, deep shadows, high contrast",
    "侧光": "side lighting, dramatic chiaroscuro",
    "逆光": "backlight, rim-lit silhouette",
    "霓虹光": "neon lighting, vibrant colored illumination",
    "烛光": "candlelight, warm flickering intimate glow",
    "赛博朋克": "cyberpunk lighting, neon mixed with shadows",
}

_CAMERA_RIG_MAP: Dict[str, str] = {
    "三脚架": "tripod, locked-off, perfectly still",
    "手持": "handheld, natural camera shake, organic feel",
    "斯坦尼康": "steadicam, smooth floating movement",
    "滑轨": "dolly on tracks, smooth lateral movement",
    "摇臂": "crane, sweeping vertical movement",
    "无人机": "drone, aerial sweeping movement",
    "肩扛": "shoulder-mounted, documentary style",
}

_DOF_MAP: Dict[str, str] = {
    "浅景深": "shallow depth of field, background heavily blurred, bokeh",
    "中等景深": "moderate depth of field, background slightly soft",
    "深景深": "deep focus, everything in sharp focus",
    "移焦": "rack focus, pull focus between subjects",
}


# =============================================================
# 5 层提示词构建器
# =============================================================

class PromptBuilder:
    """分镜提示词构建器"""

    @staticmethod
    def _select(shot_val: Optional[str], profile_val: Optional[str]) -> Optional[str]:
        """镜头字段为空时，回退到摄影风格预设"""
        return shot_val if shot_val else profile_val

    # ---- Layer 1: 镜头设计 ----
    @staticmethod
    def build_camera_layer(shot: ShotPromptInput, profile: Optional[CinematographyProfile] = None) -> str:
        """Layer 1: Camera design"""
        parts = []

        # Shot size / type
        shot_size = shot.shot_size or shot.shot_type
        if shot_size:
            token = _SHOT_TYPE_MAP.get(shot_size, shot_size)
            parts.append(token)

        # Camera angle
        angle = _CAMERA_ANGLE_MAP.get(shot.camera_angle, shot.camera_angle)
        if angle:
            parts.append(angle)

        # Camera movement
        if shot.camera_movement:
            parts.append(shot.camera_movement)

        # Camera rig
        rig = PromptBuilder._select(shot.camera_rig, profile.camera_rig if profile else None)
        if rig:
            token = _CAMERA_RIG_MAP.get(rig, rig)
            parts.append(token)

        # Movement speed
        speed = PromptBuilder._select(shot.movement_speed, profile.movement_speed if profile else None)
        if speed:
            parts.append(speed)

        # Depth of field
        dof = PromptBuilder._select(shot.depth_of_field, profile.depth_of_field if profile else None)
        if dof:
            token = _DOF_MAP.get(dof, dof)
            parts.append(token)

        # Focus target
        if shot.focus_target:
            parts.append(f"focus on {shot.focus_target}")

        # Focus transition
        if shot.focus_transition:
            parts.append(shot.focus_transition)

        # Focal length
        if shot.focal_length:
            parts.append(shot.focal_length)

        # Photography technique
        if shot.photography_technique:
            parts.append(shot.photography_technique)

        return ", ".join(parts)

    # ---- Layer 1.5: 灯光 ----
    @staticmethod
    def build_lighting_layer(shot: ShotPromptInput, profile: Optional[CinematographyProfile] = None) -> str:
        """Layer 1.5: Lighting design"""
        parts = []

        style = PromptBuilder._select(shot.lighting_style, profile.lighting_style if profile else None)
        if style:
            token = _LIGHTING_STYLE_MAP.get(style, style)
            parts.append(token)

        direction = PromptBuilder._select(shot.lighting_direction, profile.lighting_direction if profile else None)
        if direction:
            parts.append(direction)

        temp = PromptBuilder._select(shot.color_temperature, profile.color_temperature if profile else None)
        if temp:
            parts.append(temp)

        return ", ".join(parts)

    # ---- Layer 2: 主体与焦点 ----
    @staticmethod
    def build_subject_layer(shot: ShotPromptInput) -> str:
        """Layer 2: Subject and visual focus"""
        parts = []

        if shot.characters:
            chars = "、".join(shot.characters)
            parts.append(f"characters: {chars}")

        if shot.dialogue:
            parts.append(f"dialogue: {shot.dialogue[:100]}")

        if shot.description:
            parts.append(shot.description[:300])

        return ", ".join(parts)

    # ---- Layer 3: 情绪与氛围 ----
    @staticmethod
    def build_mood_layer(shot: ShotPromptInput) -> str:
        """Layer 3: Mood, emotion, and atmosphere"""
        parts = []

        if shot.emotion_tags:
            emotions = " → ".join(shot.emotion_tags)
            parts.append(f"emotional progression: {emotions}")

        if shot.narrative_function:
            parts.append(f"narrative beat: {shot.narrative_function}")

        effect = PromptBuilder._select(shot.atmospheric_effects, None)
        if effect:
            intensity = shot.effect_intensity or "moderate"
            parts.append(f"atmosphere: {effect} ({intensity})")

        return ", ".join(parts)

    # ---- Layer 5: 风格 ----
    @staticmethod
    def build_style_layer(shot: ShotPromptInput, profile: Optional[CinematographyProfile] = None) -> str:
        """Layer 5: Visual style"""
        style = shot.style or (profile.name if profile else "cinematic")
        return f"visual style: {style}"

    # ---- 尾帧推断 ----
    @staticmethod
    def infer_needs_end_frame(shot: ShotPromptInput) -> bool:
        """从镜头描述推断是否需要尾帧"""
        text = f"{shot.description} {shot.camera_movement or ''} {shot.focus_transition or ''} {shot.camera_rig or ''}"
        movement_keywords = ["走", "跑", "移", "转", "推", "拉", "飞", "跳", "起身", "坐下", "出现", "消失",
                            "walk", "run", "move", "turn", "push", "pull", "fly", "appear", "disappear"]
        transform_keywords = ["变", "化", "开", "关", "亮", "暗", "transform", "transition"]
        camera_keywords = ["360", "旋转", "环绕", "摇", "dolly", "crane", "drone", "orbit"]

        all_keywords = movement_keywords + transform_keywords + camera_keywords
        return any(kw in text for kw in all_keywords)

    # ---- 三层提示词生成 ----
    @staticmethod
    def build_image_prompt(shot: ShotPromptInput, profile: Optional[CinematographyProfile] = None) -> str:
        """生成首帧静态图像提示词"""
        layers = [
            PromptBuilder.build_camera_layer(shot, profile),
            PromptBuilder.build_lighting_layer(shot, profile),
            PromptBuilder.build_subject_layer(shot),
            PromptBuilder.build_mood_layer(shot),
            PromptBuilder.build_style_layer(shot, profile),
        ]
        prompt = ", ".join(l for l in layers if l)
        # 强调这是静态帧
        prompt += ", still frame, frozen moment, sharp focus, high quality"
        return prompt

    @staticmethod
    def build_video_prompt(shot: ShotPromptInput, profile: Optional[CinematographyProfile] = None) -> str:
        """生成视频动作提示词"""
        layers = [
            PromptBuilder.build_camera_layer(shot, profile),
            PromptBuilder.build_lighting_layer(shot, profile),
            PromptBuilder.build_subject_layer(shot),
            PromptBuilder.build_mood_layer(shot),
            PromptBuilder.build_style_layer(shot, profile),
        ]
        prompt = ", ".join(l for l in layers if l)
        # 强调这是动态视频
        if shot.needs_end_frame:
            prompt += ", smooth motion, dynamic movement, fluid animation"
        else:
            prompt += ", subtle motion, gentle movement, natural animation"
        return prompt

    @staticmethod
    def build_end_frame_prompt(shot: ShotPromptInput, profile: Optional[CinematographyProfile] = None) -> str:
        """生成尾帧提示词（仅当 needs_end_frame=True 时使用）"""
        layers = [
            PromptBuilder.build_camera_layer(shot, profile),
            PromptBuilder.build_lighting_layer(shot, profile),
            PromptBuilder.build_subject_layer(shot),
            PromptBuilder.build_style_layer(shot, profile),
        ]
        prompt = ", ".join(l for l in layers if l)
        prompt += ", end state, final position, still frame, sharp focus"
        return prompt

    # ---- 完整三层生成 ----
    @staticmethod
    def generate_all_prompts(shot: ShotPromptInput, profile: Optional[CinematographyProfile] = None) -> dict:
        """为镜头生成完整的三层提示词"""
        needs_end = PromptBuilder.infer_needs_end_frame(shot)
        shot.needs_end_frame = needs_end

        return {
            "image_prompt": PromptBuilder.build_image_prompt(shot, profile),
            "video_prompt": PromptBuilder.build_video_prompt(shot, profile),
            "end_frame_prompt": PromptBuilder.build_end_frame_prompt(shot, profile) if needs_end else None,
            "needs_end_frame": needs_end,
        }
