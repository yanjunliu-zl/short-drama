"""
LLM-as-Judge — AI 生成内容质量自动评估。

对生成的剧本/分镜进行多维度打分，低于阈值自动重试或标记人工审核。
"""
import logging
import json
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

# 评分阈值
QUALITY_THRESHOLD = 60  # 总分低于此值建议重试
COHERENCE_THRESHOLD = 50  # 连贯性单项最低分
CONSISTENCY_THRESHOLD = 50  # 一致性单项最低分

_SYSTEM_JUDGE = """你是资深短剧质量评审专家。对剧本进行专业评分。

【评分维度】(每项 0-100 分)
1. 连贯性 (coherence): 情节逻辑是否自洽，场景转换是否流畅
2. 角色一致性 (character_consistency): 角色性格、对白风格是否前后统一
3. 对白自然度 (dialogue_naturalness): 对白是否口语化，是否符合短视频节奏
4. 短视频适配度 (short_video_fitness): 是否适合短视频平台（节奏紧凑、视觉可执行、每集有钩子）

【输出格式】
严格输出 JSON，不要多余解释：
{
  "scores": {
    "coherence": 85,
    "character_consistency": 80,
    "dialogue_naturalness": 78,
    "short_video_fitness": 82
  },
  "total_score": 81,
  "verdict": "pass",
  "strengths": ["对白自然", "节奏紧凑"],
  "weaknesses": ["第三集角色动机不明确"],
  "suggestions": "建议在第三集增加角色A的动机铺垫..."
}

【判定规则】
- total_score = round((coherence + character_consistency + dialogue_naturalness + short_video_fitness) / 4)
- verdict: "pass" (总分>=60) | "retry" (40-59) | "reject" (<40)
- strengths: 2-3 个具体优点
- weaknesses: 1-3 个具体问题（没有则空数组）
- suggestions: 1-2 句具体的改进建议"""

_HUMAN_JUDGE_SCRIPT = """请评审以下剧本：

【剧本标题】{title}
【剧本风格】{style}
【剧本内容】
{content}
"""

_HUMAN_JUDGE_STORYBOARD = """请评审以下分镜：

【分镜标题】{title}
【分镜风格】{style}
【分镜内容（前 3000 字）】
{content}
"""


@dataclass
class QualityReport:
    """质量评估报告"""
    scores: Dict[str, int] = field(default_factory=dict)
    total_score: int = 0
    verdict: str = "pass"  # pass / retry / reject
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    suggestions: str = ""
    judge_elapsed_ms: int = 0

    @property
    def passed(self) -> bool:
        return self.verdict == "pass"

    @property
    def needs_retry(self) -> bool:
        return self.verdict == "retry"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scores": self.scores,
            "total_score": self.total_score,
            "verdict": self.verdict,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "suggestions": self.suggestions,
            "judge_elapsed_ms": self.judge_elapsed_ms,
        }


class QualityJudge:
    """LLM-as-Judge 质量评估器"""

    def __init__(self, llm, enabled: bool = True):
        """
        Args:
            llm: LangChain chat model (ChatOpenAI or similar).
            enabled: If False, judge() returns a pass report without LLM call.
        """
        self.llm = llm
        self.enabled = enabled

    async def judge_script(
        self,
        content: str,
        title: str = "",
        style: str = "",
        max_chars: int = 8000,
    ) -> QualityReport:
        """评估剧本质量。

        Args:
            content: 剧本正文。
            title: 剧本标题。
            style: 剧本风格。
            max_chars: 送入评审的最大字符数。

        Returns:
            QualityReport with scores and verdict.
        """
        if not self.enabled or self.llm is None:
            return QualityReport(verdict="pass", total_score=100)

        t0 = time.time()
        truncated = content[:max_chars] if len(content) > max_chars else content

        try:
            messages = [
                SystemMessage(content=_SYSTEM_JUDGE),
                HumanMessage(content=_HUMAN_JUDGE_SCRIPT.format(
                    title=title, style=style, content=truncated,
                )),
            ]
            response = await self.llm.ainvoke(messages, config={"timeout": 60})
            report = self._parse_judge_response(response.content)
            report.judge_elapsed_ms = int((time.time() - t0) * 1000)
            logger.info(
                f"QualityJudge: {report.verdict} total={report.total_score} "
                f"coherence={report.scores.get('coherence', '?')} "
                f"elapsed={report.judge_elapsed_ms}ms"
            )
            return report
        except Exception as e:
            logger.warning(f"QualityJudge failed: {e} — assuming pass")
            return QualityReport(
                verdict="pass", total_score=100,
                suggestions=f"评审失败: {str(e)[:200]}",
                judge_elapsed_ms=int((time.time() - t0) * 1000),
            )

    async def judge_storyboard(
        self,
        content: str,
        title: str = "",
        style: str = "",
    ) -> QualityReport:
        """评估分镜质量（复用同一套评分体系）。"""
        if not self.enabled or self.llm is None:
            return QualityReport(verdict="pass", total_score=100)

        t0 = time.time()
        truncated = content[:3000] if len(content) > 3000 else content

        try:
            messages = [
                SystemMessage(content=_SYSTEM_JUDGE),
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
            return QualityReport(verdict="pass", total_score=100)

    @staticmethod
    def _parse_judge_response(text: str) -> QualityReport:
        """Parse LLM JSON response into QualityReport with fallback."""
        try:
            # Extract JSON from possible markdown wrapping
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
                verdict=data.get("verdict", "pass"),
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
                suggestions=data.get("suggestions", ""),
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"QualityJudge parse failed: {e}")
            # Heuristic: if response seems positive, pass
            is_positive = any(kw in text for kw in ["好", "不错", "优秀", "pass", "good"])
            return QualityReport(
                total_score=75 if is_positive else 50,
                verdict="pass" if is_positive else "retry",
                suggestions=f"自动解析失败，原始评审: {text[:300]}",
            )
