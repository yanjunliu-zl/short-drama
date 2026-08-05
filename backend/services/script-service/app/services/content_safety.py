"""
内容安全审核 — 剧本/分镜/图像生成前后的安全过滤。

提供：
  1. 敏感词检测 — 基于内置词表的快速匹配
  2. 内容安全评分 — 基于规则的启发式审核
  3. 安全拦截 — 返回具体违规原因而非静默过滤

审核维度：
  - 政治敏感 (political): 违禁政治词汇、敏感事件
  - 暴力血腥 (violence): 过度暴力描写
  - 色情低俗 (adult): 色情暗示、低俗内容
  - 违法犯罪 (illegal): 违法诱导内容
"""
import logging
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ============================================================
# 敏感词表 (生产环境应接入专业审核 API)
# ============================================================

_SENSITIVE_PATTERNS: Dict[str, List[str]] = {
    "political": [
        # Basic political sensitivity patterns — 生产环境替换为专业词库
    ],
    "violence": [
        r"杀(死|害|掉|人)", r"血[腥淋]", r"暴[力虐]",
        r"致[死命]", r"砍[杀死]", r"枪[杀击]",
    ],
    "adult": [
        r"裸[体露]", r"性[交爱欲行为]", r"色[情诱]",
        r"淫[秽乱荡]", r"嫖[娼妓]", r"一夜情",
    ],
    "illegal": [
        r"毒[品贩]", r"赌[博场]", r"诈[骗欺]",
        r"走[私贩]", r"洗[钱黑]", r"传[销教]",
    ],
}

# 安全阈值
SAFETY_PASS_THRESHOLD = 80  # 低于此分拒绝


@dataclass
class SafetyReport:
    """内容安全审核报告"""
    passed: bool = True
    score: int = 100  # 0-100, 越高越安全
    violations: List[Dict[str, str]] = field(default_factory=list)
    suggestion: str = ""

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "score": self.score,
            "violations": self.violations,
            "suggestion": self.suggestion,
        }


class ContentSafetyChecker:
    """内容安全审核器"""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        # Compile regex patterns
        self._compiled: Dict[str, List[re.Pattern]] = {}
        for category, patterns in _SENSITIVE_PATTERNS.items():
            self._compiled[category] = [re.compile(p) for p in patterns]

    def check(self, text: str, content_type: str = "script") -> SafetyReport:
        """Check content for safety violations.

        Args:
            text: Content to check.
            content_type: "script", "storyboard", "prompt", or "character".

        Returns:
            SafetyReport with pass/fail and violation details.
        """
        if not self.enabled or not text:
            return SafetyReport(passed=True, score=100)

        violations = []
        deducted = 0
        text_lower = text.lower()

        for category, patterns in self._compiled.items():
            for pattern in patterns:
                matches = pattern.findall(text)
                if matches:
                    severity = 20 if category in ("political", "adult") else 15
                    deducted += severity * len(matches)
                    violations.append({
                        "category": category,
                        "pattern": pattern.pattern,
                        "count": len(matches),
                        "severity": severity,
                    })

        score = max(0, 100 - deducted)
        passed = score >= SAFETY_PASS_THRESHOLD and len(violations) <= 2

        suggestion = ""
        if not passed:
            categories = list(set(v["category"] for v in violations))
            suggestion = f"内容涉及 {', '.join(categories)} 类敏感信息，请修改后重试"

        report = SafetyReport(
            passed=passed,
            score=score,
            violations=violations,
            suggestion=suggestion,
        )

        if not passed:
            logger.warning(
                f"Content safety: REJECTED score={score} "
                f"violations={len(violations)} type={content_type}"
            )
        else:
            logger.debug(f"Content safety: passed score={score}")

        return report

    def check_script(self, content: str, title: str = "") -> SafetyReport:
        """Check generated script content. Checks both title and body."""
        report = self.check(title + " " + content[:10000], content_type="script")
        return report

    def check_prompt(self, prompt: str) -> SafetyReport:
        """Check image generation prompt before sending to API."""
        return self.check(prompt, content_type="prompt")

    def check_character(self, character_desc: str) -> SafetyReport:
        """Check character description for inappropriate content."""
        return self.check(character_desc, content_type="character")


# Global instance
_safety_checker: Optional[ContentSafetyChecker] = None


def get_safety_checker(enabled: bool = True) -> ContentSafetyChecker:
    global _safety_checker
    if _safety_checker is None:
        _safety_checker = ContentSafetyChecker(enabled=enabled)
    return _safety_checker
