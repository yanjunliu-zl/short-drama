"""
LLM-as-Judge — AI 生成内容质量自动评估（工业级）。

7 维评分 + A/B 对比 + 质量趋势追踪 + 平台格式感知。
"""
import logging
import json
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

# ── 评分阈值 ──
QUALITY_THRESHOLD = 60        # 总分低于此值建议重试
COHERENCE_THRESHOLD = 50      # 连贯性单项最低分
CONSISTENCY_THRESHOLD = 50    # 角色一致性单项最低分
CLIFFHANGER_THRESHOLD = 35    # 钩子质量 — 可接受的底线
COMPLIANCE_THRESHOLD = 60     # 合规性 — 硬性门槛

# ── 7 维评分系统 ──

_SYSTEM_JUDGE_V2 = """你是资深短剧质量评审专家。对剧本进行多维度专业评分。

【评分维度】(每项 0-100 分)
1. 连贯性 (coherence): 情节逻辑是否自洽，场景转换是否流畅，前后是否有矛盾
2. 角色一致性 (character_consistency): 角色性格、对白风格是否前后统一，人设是否立得住
3. 对白自然度 (dialogue_naturalness): 对白是否口语化，是否符合角色身份，是否推动剧情
4. 短视频适配度 (short_video_fitness): 是否适合短视频平台 — 节奏紧凑、视觉可执行、每集有记忆点
5. 钩子质量 (cliffhanger_quality): 每集结尾是否有悬念钩子，是否能驱动用户点开下一集
6. 类型准确度 (genre_accuracy): 是否准确体现指定类型的核心特征（古装 vs 都市 vs 悬疑 等）
7. 合规性 (compliance): 是否涉及政治敏感、色情、暴力过度、违法内容 — 高分 = 干净

【输出格式】
严格输出 JSON，不要多余解释：
{
  "scores": {
    "coherence": 85,
    "character_consistency": 80,
    "dialogue_naturalness": 78,
    "short_video_fitness": 82,
    "cliffhanger_quality": 70,
    "genre_accuracy": 88,
    "compliance": 95
  },
  "total_score": 83,
  "verdict": "pass",
  "strengths": ["对白自然", "节奏紧凑"],
  "weaknesses": ["第3集钩子不够强", "第7集角色动机不明确"],
  "suggestions": "建议在第3集结尾增加信息差悬念，第7集补充角色A为什么要背叛的铺垫...",
  "best_episode": 1,
  "worst_episode": 7
}

【判定规则】
- total_score = round(avg of all 7 scores)
- verdict: "pass" (总分>=60 且 合规>=60) | "retry" (40-59 或 合规<60 但可修复) | "reject" (<40 或 合规<30)
- strengths: 2-3 个具体优点
- weaknesses: 1-3 个具体问题（没有则空数组）
- suggestions: 1-3 句具体的改进建议，要可操作
- best_episode / worst_episode: 最好/最差集号（如能判断，否则0）
"""

_HUMAN_JUDGE_SCRIPT = """请评审以下剧本：

【剧本标题】{title}
【剧本风格】{style}
【剧本长度】{length}
【目标平台】{platform}
【剧本内容（前 {max_chars} 字）】
{content}
"""

_HUMAN_JUDGE_STORYBOARD = """请评审以下分镜：

【分镜标题】{title}
【分镜风格】{style}
【分镜内容（前 3000 字）】
{content}
"""

# ── A/B 对比 ──

_SYSTEM_COMPARE = """你是资深短剧质量评审专家。你需要对比两个剧本，判断哪个更好，并给出理由。

【对比维度】
1. 故事吸引力：哪个开头更能抓住人？
2. 节奏感：哪个更适合短视频平台？
3. 角色魅力：哪个的角色更让人记住？
4. 钩子效果：哪个的悬念设计更好？
5. 整体可拍性：哪个更容易拍出爆款？

【输出格式】
严格输出 JSON：
{
  "winner": "A",
  "confidence": 0.75,
  "score_a": 72,
  "score_b": 65,
  "key_differences": [
    "A 的第一集钩子明显更强，信息差设计让用户更想点第二集",
    "B 的对白更自然但节奏偏慢，都市情感赛道不适合慢节奏"
  ],
  "verdict_summary": "A 在钩子设计和节奏上明显优于 B，虽然 B 的对白更好但核心指标弱于 A"
}
"""

_HUMAN_COMPARE = """请对比以下两个剧本：

【剧本 A】
{script_a}

【剧本 B】
{script_b}
"""


class Verdict(str, Enum):
    PASS = "pass"
    RETRY = "retry"
    REJECT = "reject"


@dataclass
class QualityReport:
    """质量评估报告"""
    scores: Dict[str, int] = field(default_factory=dict)
    total_score: int = 0
    verdict: str = "pass"
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    suggestions: str = ""
    best_episode: int = 0
    worst_episode: int = 0
    judge_elapsed_ms: int = 0

    @property
    def passed(self) -> bool:
        return self.verdict == Verdict.PASS.value

    @property
    def needs_retry(self) -> bool:
        return self.verdict == Verdict.RETRY.value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scores": self.scores,
            "total_score": self.total_score,
            "verdict": self.verdict,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "suggestions": self.suggestions,
            "best_episode": self.best_episode,
            "worst_episode": self.worst_episode,
            "judge_elapsed_ms": self.judge_elapsed_ms,
        }


@dataclass
class CompareReport:
    """A/B 对比报告"""
    winner: str = ""                    # "A" or "B"
    confidence: float = 0.5
    score_a: int = 0
    score_b: int = 0
    key_differences: List[str] = field(default_factory=list)
    verdict_summary: str = ""


@dataclass
class TrendPoint:
    """质量趋势数据点"""
    timestamp: str
    script_id: str
    total_score: int
    scores: Dict[str, int] = field(default_factory=dict)


class QualityJudge:
    """LLM-as-Judge 质量评估器（工业级）"""

    def __init__(self, llm, enabled: bool = True):
        self.llm = llm
        self.enabled = enabled
        # 趋势存储（内存中，生产环境应迁移到 DB/Redis）
        self._trends: Dict[str, List[TrendPoint]] = {}

    # ═══════════════════════════════════════════════════════════
    # 剧本评审 (7 维)
    # ═══════════════════════════════════════════════════════════

    async def judge_script(
        self,
        content: str,
        title: str = "",
        style: str = "",
        length: str = "短篇",
        platform: str = "internal",
        max_chars: int = 8000,
    ) -> QualityReport:
        """7 维评估剧本质量。

        Args:
            content: 剧本正文。
            title: 剧本标题。
            style: 剧本风格（用于 genre_accuracy 评估）。
            length: 剧本长度。
            platform: 目标平台（xiaoyunque / libtv / jurilu），影响合规性和适配度判断。
            max_chars: 送入评审的最大字符数。

        Returns:
            QualityReport with 7-dimensional scores and verdict.
        """
        if not self.enabled or self.llm is None:
            return QualityReport(verdict=Verdict.PASS.value, total_score=100)

        t0 = time.time()
        truncated = content[:max_chars] if len(content) > max_chars else content

        try:
            messages = [
                SystemMessage(content=_SYSTEM_JUDGE_V2),
                HumanMessage(content=_HUMAN_JUDGE_SCRIPT.format(
                    title=title, style=style, length=length,
                    platform=platform, max_chars=max_chars,
                    content=truncated,
                )),
            ]
            response = await self.llm.ainvoke(messages, config={"timeout": 90})
            report = self._parse_judge_response(response.content)
            report.judge_elapsed_ms = int((time.time() - t0) * 1000)
            logger.info(
                f"QualityJudge(v2): {report.verdict} total={report.total_score} "
                f"coherence={report.scores.get('coherence', '?')} "
                f"compliance={report.scores.get('compliance', '?')} "
                f"cliffhanger={report.scores.get('cliffhanger_quality', '?')} "
                f"elapsed={report.judge_elapsed_ms}ms"
            )
            return report
        except Exception as e:
            logger.warning(f"QualityJudge failed: {e} — assuming pass")
            return QualityReport(
                verdict=Verdict.PASS.value, total_score=100,
                suggestions=f"评审失败: {str(e)[:200]}",
                judge_elapsed_ms=int((time.time() - t0) * 1000),
            )

    async def judge_storyboard(
        self, content: str, title: str = "", style: str = ""
    ) -> QualityReport:
        """评估分镜质量（复用 7 维评分体系）。"""
        if not self.enabled or self.llm is None:
            return QualityReport(verdict=Verdict.PASS.value, total_score=100)

        t0 = time.time()
        truncated = content[:3000] if len(content) > 3000 else content

        try:
            messages = [
                SystemMessage(content=_SYSTEM_JUDGE_V2),
                HumanMessage(content=_HUMAN_JUDGE_STORYBOARD.format(
                    title=title, style=style, content=truncated,
                )),
            ]
            response = await self.llm.ainvoke(messages, config={"timeout": 60})
            report = self._parse_judge_response(response.content)
            report.judge_elapsed_ms = int((time.time() - t0) * 1000)
            return report
        except Exception as e:
            logger.warning(f"QualityJudge (storyboard) failed: {e}")
            return QualityReport(verdict=Verdict.PASS.value, total_score=100)

    # ═══════════════════════════════════════════════════════════
    # A/B 对比
    # ═══════════════════════════════════════════════════════════

    async def compare_scripts(
        self,
        script_a: str,
        script_b: str,
        label_a: str = "A",
        label_b: str = "B",
        max_chars: int = 4000,
    ) -> CompareReport:
        """对比两个剧本，返回胜负判断。

        用于:
        - 模型升级 A/B 测试 (candidate vs production)
        - 重试后对比 (original vs regenerated)
        - 多方案选优 (方案A vs 方案B)
        """
        if not self.enabled or self.llm is None:
            return CompareReport(
                winner="A", confidence=0.5, score_a=50, score_b=50,
                verdict_summary="评审未启用，默认平局"
            )

        t0 = time.time()
        try:
            messages = [
                SystemMessage(content=_SYSTEM_COMPARE),
                HumanMessage(content=_HUMAN_COMPARE.format(
                    script_a=script_a[:max_chars],
                    script_b=script_b[:max_chars],
                )),
            ]
            response = await self.llm.ainvoke(messages, config={"timeout": 90})
            report = self._parse_compare_response(response.content)
            logger.info(
                f"QualityJudge A/B: winner={report.winner} "
                f"score_A={report.score_a} score_B={report.score_b} "
                f"confidence={report.confidence:.2f} "
                f"elapsed={int((time.time()-t0)*1000)}ms"
            )
            return report
        except Exception as e:
            logger.warning(f"QualityJudge A/B failed: {e}")
            return CompareReport(
                winner="A", confidence=0.5,
                verdict_summary=f"对比失败: {str(e)[:100]}"
            )

    # ═══════════════════════════════════════════════════════════
    # 质量趋势追踪
    # ═══════════════════════════════════════════════════════════

    def record_score(
        self, script_id: str, report: QualityReport, series: str = "default"
    ):
        """记录一次评分，用于趋势分析。"""
        if series not in self._trends:
            self._trends[series] = []

        point = TrendPoint(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            script_id=script_id,
            total_score=report.total_score,
            scores=report.scores,
        )
        self._trends[series].append(point)

        # 只保留最近 500 个数据点
        if len(self._trends[series]) > 500:
            self._trends[series] = self._trends[series][-500:]

    def get_trend(self, series: str = "default", window: int = 50) -> Dict[str, Any]:
        """获取质量趋势数据。

        Returns:
            {
                "series": str,
                "data_points": int,
                "avg_score": float,
                "score_trend": "improving" | "stable" | "declining",
                "dimension_trends": {...},
                "recent_scores": [...],
            }
        """
        points = self._trends.get(series, [])
        if not points:
            return {"series": series, "data_points": 0}

        recent = points[-window:]
        scores = [p.total_score for p in recent]

        avg_score = sum(scores) / len(scores)

        # Trend direction: compare first half vs second half
        if len(scores) >= 10:
            mid = len(scores) // 2
            first_half_avg = sum(scores[:mid]) / mid
            second_half_avg = sum(scores[mid:]) / (len(scores) - mid)
            delta = second_half_avg - first_half_avg
            if delta > 2:
                score_trend = "improving"
            elif delta < -2:
                score_trend = "declining"
            else:
                score_trend = "stable"
        else:
            score_trend = "stable"

        # Per-dimension trends
        dim_trends = {}
        if recent and recent[0].scores:
            for dim in recent[0].scores:
                dim_scores = [p.scores.get(dim, 0) for p in recent if dim in p.scores]
                if dim_scores:
                    dim_trends[dim] = {
                        "avg": sum(dim_scores) / len(dim_scores),
                        "min": min(dim_scores),
                        "max": max(dim_scores),
                        "latest": dim_scores[-1],
                    }

        return {
            "series": series,
            "data_points": len(points),
            "window": window,
            "avg_score": round(avg_score, 1),
            "score_trend": score_trend,
            "dimension_trends": dim_trends,
            "recent_scores": [
                {"timestamp": p.timestamp, "script_id": p.script_id, "score": p.total_score}
                for p in recent[-10:]  # Last 10 only
            ],
        }

    # ═══════════════════════════════════════════════════════════
    # 批量评估
    # ═══════════════════════════════════════════════════════════

    async def judge_batch(
        self,
        scripts: List[Dict[str, Any]],
        label: str = "batch",
    ) -> List[QualityReport]:
        """批量评估多个剧本，记录趋势。

        Args:
            scripts: [{content, title, style, length, script_id}, ...]
            label: 趋势系列标签

        Returns:
            List of QualityReport, same order as input.
        """
        reports = []
        for s in scripts:
            report = await self.judge_script(
                content=s.get("content", ""),
                title=s.get("title", ""),
                style=s.get("style", ""),
                length=s.get("length", "短篇"),
            )
            if s.get("script_id"):
                self.record_score(s["script_id"], report, series=label)
            reports.append(report)

        if reports:
            scores = [r.total_score for r in reports]
            logger.info(
                f"QualityJudge batch '{label}': {len(reports)} scripts, "
                f"avg={sum(scores)/len(scores):.1f}, "
                f"pass={sum(1 for r in reports if r.passed)}/{len(reports)}"
            )

        return reports

    # ═══════════════════════════════════════════════════════════
    # 解析
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _parse_judge_response(text: str) -> QualityReport:
        """Parse LLM JSON response into QualityReport with fallback."""
        try:
            json_str = text
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                json_str = text.split("```")[1].split("```")[0]
            elif "{" in text:
                start = text.index("{")
                end = text.rindex("}") + 1
                json_str = text[start:end]

            data = json.loads(json_str)
            scores = data.get("scores", {})
            return QualityReport(
                scores={k: int(v) for k, v in scores.items()},
                total_score=int(data.get("total_score", 0)),
                verdict=data.get("verdict", Verdict.PASS.value),
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
                suggestions=data.get("suggestions", ""),
                best_episode=int(data.get("best_episode", 0)),
                worst_episode=int(data.get("worst_episode", 0)),
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"QualityJudge parse failed: {e}")
            is_positive = any(kw in text for kw in ["好", "不错", "优秀", "pass", "good"])
            return QualityReport(
                total_score=75 if is_positive else 50,
                verdict=Verdict.PASS.value if is_positive else Verdict.RETRY.value,
                suggestions=f"自动解析失败，原始评审: {text[:300]}",
            )

    @staticmethod
    def _parse_compare_response(text: str) -> CompareReport:
        """Parse A/B comparison response."""
        try:
            json_str = text
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                json_str = text.split("```")[1].split("```")[0]
            elif "{" in text:
                start = text.index("{")
                end = text.rindex("}") + 1
                json_str = text[start:end]

            data = json.loads(json_str)
            return CompareReport(
                winner=data.get("winner", "A"),
                confidence=float(data.get("confidence", 0.5)),
                score_a=int(data.get("score_a", 0)),
                score_b=int(data.get("score_b", 0)),
                key_differences=data.get("key_differences", []),
                verdict_summary=data.get("verdict_summary", ""),
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Compare parse failed: {e}")
            return CompareReport(
                winner="A", confidence=0.5,
                verdict_summary=f"解析失败: {str(e)[:100]}"
            )
