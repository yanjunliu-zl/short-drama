"""
剧本导出服务 — 将内部剧本格式转换为下游 AI 成片工具的兼容格式。

支持目标平台:
  - 小云雀 (XiaoYunQue / ByteDance) — 纯文本 + 结构化 JSON
  - LibTV — 分镜工作流 JSON
  - 巨日禄 (JuRiLu) — 纯文本 + 角色资产 JSON

设计原则:
  - 不丢失原创信息
  - 适配各平台的格式约定和字符限制
  - 自动校验输出是否符合平台要求
"""
import logging
import json
import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# ── Platform limits ──
PLATFORM_LIMITS = {
    "xiaoyunque": {
        "max_chars": 100_000,       # 小云雀支持 10 万字
        "max_episodes": 100,
        "supported_markers": ["第N集", "【场景", "角色名：", "△"],
    },
    "libtv": {
        "max_chars": 200_000,       # 画布模式无硬限制
        "max_episodes": 200,
        "supported_markers": ["第N集", "【场景", "角色名：", "△", "分镜"],
    },
    "jurilu": {
        "max_chars": 50_000,        # 巨日禄建议 5 万字以内
        "max_episodes": 80,
        "supported_markers": ["第N集", "【场景", "角色名：", "△"],
    },
}


class ExportFormat(str, Enum):
    """导出格式"""
    RAW_TEXT = "raw_text"         # 纯文本（第N集标记格式）
    STRUCTURED_JSON = "structured_json"  # 结构化 JSON
    STORYBOARD_JSON = "storyboard_json"  # 分镜工作流 JSON (LibTV)


class ExportTarget(str, Enum):
    """目标平台"""
    XIAOYUNQUE = "xiaoyunque"
    LIBTV = "libtv"
    JURILU = "jurilu"


@dataclass
class ExportResult:
    """导出结果"""
    target: ExportTarget
    format: ExportFormat
    content: str                           # 导出文本内容
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    validation_passed: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target.value,
            "format": self.format.value,
            "content": self.content,
            "metadata": self.metadata,
            "warnings": self.warnings,
            "validation_passed": self.validation_passed,
        }


class ExportService:
    """剧本导出服务 — 多平台格式转换 + 验证"""

    # ── Public API ──

    def export(
        self,
        script_content: str,
        target: ExportTarget,
        format: ExportFormat = ExportFormat.RAW_TEXT,
        title: str = "",
        characters: Optional[List[Dict[str, Any]]] = None,
        episodes: Optional[List[Dict[str, Any]]] = None,
    ) -> ExportResult:
        """Main export entry point.

        Args:
            script_content: Full script text (multi-episode, with markers).
            target: Target platform.
            format: Desired output format.
            title: Script title.
            characters: Character list (optional — used for structured formats).
            episodes: Pre-split episodes (optional — avoids re-parsing).

        Returns:
            ExportResult with content, metadata, and validation warnings.
        """
        limits = PLATFORM_LIMITS[target.value]

        # 1. Pre-validate
        warnings = self._pre_validate(script_content, target, limits)

        # 2. Convert
        if format == ExportFormat.RAW_TEXT:
            content = self._export_raw_text(script_content, target, limits)
        elif format == ExportFormat.STRUCTURED_JSON:
            content = self._export_structured_json(
                script_content, target, title, characters, episodes
            )
        elif format == ExportFormat.STORYBOARD_JSON:
            content = self._export_storyboard_json(
                script_content, target, title, characters, episodes
            )
        else:
            raise ValueError(f"Unknown format: {format}")

        # 3. Post-validate
        post_warnings = self._post_validate(content, target, format, limits)
        warnings.extend(post_warnings)

        return ExportResult(
            target=target,
            format=format,
            content=content,
            metadata={
                "title": title,
                "char_count": len(script_content),
                "exported_char_count": len(content) if isinstance(content, str) else len(json.dumps(content, ensure_ascii=False)),
                "episode_count": len(episodes) if episodes else 0,
            },
            warnings=warnings,
            validation_passed=len([w for w in warnings if w.startswith("[ERROR]")]) == 0,
        )

    def export_all_formats(
        self,
        script_content: str,
        title: str = "",
        characters: Optional[List[Dict[str, Any]]] = None,
        episodes: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, ExportResult]:
        """Export to all three platforms in their recommended formats.

        Returns dict keyed by platform name.
        """
        results = {}
        # 小云雀: raw text (best compatibility)
        results["xiaoyunque"] = self.export(
            script_content, ExportTarget.XIAOYUNQUE, ExportFormat.RAW_TEXT,
            title, characters, episodes,
        )
        # LibTV: storyboard JSON (best integration)
        results["libtv"] = self.export(
            script_content, ExportTarget.LIBTV, ExportFormat.STORYBOARD_JSON,
            title, characters, episodes,
        )
        # 巨日禄: raw text (batch mode)
        results["jurilu"] = self.export(
            script_content, ExportTarget.JURILU, ExportFormat.RAW_TEXT,
            title, characters, episodes,
        )
        return results

    # ── Format Converters ──

    def _export_raw_text(
        self, content: str, target: ExportTarget, limits: dict
    ) -> str:
        """Export as raw text with standard markers.

        All three platforms accept this format natively.
        """
        # Truncate if exceeds platform limit
        max_chars = limits["max_chars"]
        if len(content) > max_chars:
            logger.warning(
                f"Script exceeds {target.value} limit ({len(content)} > {max_chars} chars), "
                f"truncating to fit. Consider splitting into batches."
            )
            # Smart truncation: find last complete episode boundary
            trunc_point = content.rfind("第", 0, max_chars)
            if trunc_point > max_chars * 0.8:
                content = content[:trunc_point].rstrip()
            else:
                content = content[:max_chars].rstrip()
            content += f"\n\n【注意：剧本因超出{target.value}平台字数限制已被截断】"

        # Normalize markers for platform compatibility
        content = self._normalize_markers(content, target)
        return content

    def _export_structured_json(
        self,
        content: str,
        target: ExportTarget,
        title: str,
        characters: Optional[List[Dict[str, Any]]],
        episodes: Optional[List[Dict[str, Any]]],
    ) -> str:
        """Export as structured JSON with episodes, scenes, and character data.

        Compatible with 小云雀 API and 巨日禄 structured import.
        """
        eps = episodes or self._parse_episodes(content)

        structured = {
            "format_version": "1.0",
            "target_platform": target.value,
            "title": title,
            "total_episodes": len(eps),
            "total_characters": len(characters) if characters else 0,
            "characters": self._normalize_characters(characters or []),
            "episodes": [],
        }

        for ep in eps:
            ep_data = {
                "episode_number": ep.get("episode_number", 0),
                "title": ep.get("title", ""),
                "scenes": self._parse_scenes(ep.get("content", "")),
                "character_count": len(characters) if characters else 0,
                "word_count": len(ep.get("content", "")),
            }
            structured["episodes"].append(ep_data)

        return json.dumps(structured, ensure_ascii=False, indent=2)

    def _export_storyboard_json(
        self,
        content: str,
        target: ExportTarget,
        title: str,
        characters: Optional[List[Dict[str, Any]]],
        episodes: Optional[List[Dict[str, Any]]],
    ) -> str:
        """Export as LibTV-compatible storyboard JSON.

        LibTV's script workflow expects:
        - Episodes with scene-level breakdown
        - Shot-level descriptions within each scene
        - Character references per scene
        - Location/time metadata per scene
        """
        eps = episodes or self._parse_episodes(content)

        storyboard = {
            "format_version": "libtv-script-1.0",
            "title": title,
            "total_episodes": len(eps),
            "characters": self._normalize_characters(characters or []),
            "episodes": [],
        }

        for ep in eps:
            ep_data = {
                "episode_number": ep.get("episode_number", 0),
                "title": ep.get("title", ""),
                "scenes": [],
            }

            scenes = self._parse_scenes(ep.get("content", ""))
            for scene in scenes:
                scene_data = {
                    "scene_title": scene.get("title", ""),
                    "location": scene.get("location", ""),
                    "time_of_day": scene.get("time", ""),
                    "characters_in_scene": scene.get("characters", []),
                    "description": scene.get("description", ""),
                    "shots": self._estimate_shots(scene),
                    "dialogue": scene.get("dialogue", []),
                }
                ep_data["scenes"].append(scene_data)

            storyboard["episodes"].append(ep_data)

        return json.dumps(storyboard, ensure_ascii=False, indent=2)

    # ── Parsing ──

    @staticmethod
    def _parse_episodes(content: str) -> List[Dict[str, Any]]:
        """Parse multi-episode script into episode list."""
        episodes = []
        pattern = re.compile(r'第\s*([一二三四五六七八九十百千万\d]+)\s*集', re.IGNORECASE)
        markers = list(pattern.finditer(content))

        if not markers:
            return [{"episode_number": 1, "title": "完整剧本", "content": content.strip()}]

        for i, match in enumerate(markers):
            start = match.end()
            end = markers[i + 1].start() if i + 1 < len(markers) else len(content)
            ep_num_str = match.group(1)
            ep_content = content[start:end].strip()
            if len(ep_content) < 50:
                continue
            episodes.append({
                "episode_number": _parse_chinese_num(ep_num_str),
                "title": f"第{ep_num_str}集",
                "content": ep_content,
            })
        return episodes

    @staticmethod
    def _parse_scenes(episode_content: str) -> List[Dict[str, Any]]:
        """Parse scenes within an episode."""
        scenes = []
        # Scene marker: 【场景X：地点—时间】
        scene_pattern = re.compile(
            r'【场景[^】]*[：:]([^—\n]+)(?:[—\-—]([^】]+))?】'
        )
        # Split by scene markers
        parts = scene_pattern.split(episode_content)
        if len(parts) <= 1:
            # No scene markers found — treat entire episode as one scene
            chars = re.findall(r'([^\s]{2,4})[：:]', episode_content)
            return [{
                "title": "Scene 1",
                "location": "",
                "time": "",
                "characters": list(set(chars)),
                "description": episode_content[:500],
                "dialogue": _extract_dialogue(episode_content),
            }]

        # Parse structured scenes
        scene_matches = list(scene_pattern.finditer(episode_content))
        pieces = scene_pattern.split(episode_content)

        for idx, match in enumerate(scene_matches):
            if idx + 1 < len(pieces):
                body = pieces[idx * 3 + 3] if (idx * 3 + 3) < len(pieces) else ""
            else:
                body = ""
            location = match.group(1).strip() if match.group(1) else ""
            time_of_day = match.group(2).strip() if match.group(2) else ""
            chars = re.findall(r'([^\s]{2,4})[：:]', body)
            scenes.append({
                "title": f"场景{idx + 1}",
                "location": location,
                "time": time_of_day,
                "characters": list(set(chars)),
                "description": body[:200].strip(),
                "dialogue": _extract_dialogue(body),
            })

        return scenes

    @staticmethod
    def _estimate_shots(scene: dict) -> List[Dict[str, Any]]:
        """Estimate shot list from scene description and dialogue.

        This is a heuristic — actual shot planning should use LibTV's
        3D Director or our storyboard service for precise shot design.
        """
        shots = []
        desc = scene.get("description", "")
        dialogue = scene.get("dialogue", [])
        shot_num = 1

        # Opening establishing shot
        if scene.get("location"):
            shots.append({
                "shot_number": shot_num,
                "type": "全景",
                "duration_seconds": 3.0,
                "description": f"Establishing: {scene.get('location')} — {scene.get('time', '')}",
            })
            shot_num += 1

        # Character introduction shot
        for char in scene.get("characters", [])[:3]:
            shots.append({
                "shot_number": shot_num,
                "type": "中景",
                "duration_seconds": 2.0,
                "description": f"{char} 出场",
            })
            shot_num += 1

        # Action/description shot
        if desc:
            shots.append({
                "shot_number": shot_num,
                "type": "中景",
                "duration_seconds": 3.0,
                "description": desc[:100],
            })
            shot_num += 1

        # Dialogue shots (one per 2-3 lines)
        for i in range(0, len(dialogue), 3):
            lines = dialogue[i:i+3]
            combined = " ".join([f"{d.get('character', '')}: {d.get('line', '')}" for d in lines])
            shots.append({
                "shot_number": shot_num,
                "type": "近景" if len(lines) == 1 else "中景",
                "duration_seconds": 2.0 * len(lines),
                "description": combined[:150],
            })
            shot_num += 1

        return shots

    # ── Normalization ──

    @staticmethod
    def _normalize_markers(content: str, target: ExportTarget) -> str:
        """Ensure script markers match platform expectations."""
        # All three platforms accept the same marker format.
        # Ensure consistent formatting:
        # - 第N集 (Arabic or Chinese numerals both accepted)
        # - 【场景X：地点—时间】
        # - 角色名：台词
        # - △ 动作描述

        # Ensure episode markers have proper formatting
        content = re.sub(r'第\s*(\d+)\s*集', r'第\1集', content)
        # Ensure scene markers have 【】
        # (most scripts already have this — normalize if not)
        return content

    @staticmethod
    def _normalize_characters(characters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize character data for downstream tool compatibility."""
        normalized = []
        for c in characters:
            if isinstance(c, str):
                normalized.append({"name": c, "role": "配角", "description": ""})
            else:
                normalized.append({
                    "name": c.get("name", ""),
                    "role": c.get("role", "配角"),
                    "gender": c.get("gender", ""),
                    "description": c.get("description", "")[:200],
                    "personality": c.get("personality", "")[:100],
                })
        return normalized

    # ── Validation ──

    def _pre_validate(
        self, content: str, target: ExportTarget, limits: dict
    ) -> List[str]:
        """Validate script before export."""
        warnings = []

        if not content or not content.strip():
            return ["[ERROR] Script content is empty"]

        # Length check
        if len(content) > limits["max_chars"]:
            warnings.append(
                f"[WARNING] Script length ({len(content)} chars) exceeds "
                f"{target.value} recommended limit ({limits['max_chars']} chars). "
                f"Content will be truncated."
            )

        # Episode count check
        episode_count = len(list(re.finditer(r'第\s*[一二三四五六七八九十百千\d]+\s*集', content)))
        if episode_count == 0:
            warnings.append("[WARNING] No episode markers (第N集) detected. "
                           "The platform may not auto-split episodes correctly.")
        elif episode_count > limits["max_episodes"]:
            warnings.append(
                f"[WARNING] {episode_count} episodes exceeds {target.value} "
                f"recommended limit ({limits['max_episodes']})."
            )

        # Scene marker check
        scene_count = len(re.findall(r'【场景', content))
        if scene_count == 0:
            warnings.append("[WARNING] No scene markers (【场景】) detected. "
                           "Video generation quality may be reduced without scene boundaries.")

        # Dialogue ratio check
        dialogue_lines = len(re.findall(r'[^\s]{2,4}[：:]', content))
        total_lines = max(content.count('\n'), 1)
        if total_lines > 0 and dialogue_lines / total_lines < 0.15:
            warnings.append("[WARNING] Low dialogue density detected. "
                           "Short drama platforms require ≥15% dialogue ratio.")

        return warnings

    def _post_validate(
        self, exported: str, target: ExportTarget,
        format: ExportFormat, limits: dict
    ) -> List[str]:
        """Validate exported content."""
        warnings = []

        if format == ExportFormat.RAW_TEXT:
            text = exported
            if len(text) > limits["max_chars"] + 1000:  # Allow small overflow
                warnings.append(
                    f"[ERROR] Exported text ({len(text)} chars) still exceeds limit. "
                    f"Truncation may have failed."
                )

        elif format in (ExportFormat.STRUCTURED_JSON, ExportFormat.STORYBOARD_JSON):
            try:
                data = json.loads(exported)
                if not data.get("episodes"):
                    warnings.append("[WARNING] Exported JSON has no episodes.")
            except json.JSONDecodeError as e:
                warnings.append(f"[ERROR] Exported JSON is malformed: {e}")

        return warnings


# ── Helpers ──

_CN_NUM_MAP = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
}


def _parse_chinese_num(s: str) -> int:
    """Parse Chinese numeral to integer."""
    s = s.strip()
    if s.isdigit():
        return int(s)
    if s in _CN_NUM_MAP:
        return _CN_NUM_MAP[s]
    if '十' in s:
        prefix, _, suffix = s.partition('十')
        base = _CN_NUM_MAP.get(prefix, 1) * 10
        if suffix:
            base += _CN_NUM_MAP.get(suffix, 0)
        return base
    if '百' in s:
        prefix, _, suffix = s.partition('百')
        base = _CN_NUM_MAP.get(prefix, 1) * 100
        if suffix:
            base += _parse_chinese_num(suffix)
        return base
    return 1


def _extract_dialogue(text: str) -> List[Dict[str, str]]:
    """Extract dialogue lines from script text."""
    dialogue = []
    for match in re.finditer(r'([^\s]{2,4})[：:]((?:[^\n]+\n?){1})', text):
        char = match.group(1)
        line = match.group(2).strip()
        if char and line and len(line) < 500:
            dialogue.append({"character": char, "line": line})
    return dialogue
