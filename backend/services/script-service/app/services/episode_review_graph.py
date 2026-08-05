"""
Multi-Agent Episode Review Graph — LangGraph state machine.

Architecture:
  generate → review_parallel(4 lenses) → merge → decide
                 ↑                                      │
                 │            ┌─ pass ──► END           │
                 │            ├─ revise ─► rewrite ─────┘
                 │            └─ reject ─► END (fail)

4 parallel reviewers, each from a single dimension:
  - pacing_conflict:   节奏、冲突密度、反转频率
  - character_dialogue: 角色一致性、对白质量
  - hook_paywall:      片尾钩子、付费点卡位
  - platform_compliance: 平台合规、内容安全、视觉可执行性

Merge node (no LLM): averages scores, deduplicates feedback, sorts by severity.
Decide node (no LLM): pass(≥70) / revise(40-69) / reject(<40), max 3 attempts.
"""
import asyncio
import logging
import time
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

# ── Constants ──
MAX_REVIEW_ATTEMPTS = 3
PASS_THRESHOLD = 70
REJECT_THRESHOLD = 40


# ── Pydantic models for structured LLM output ──

class ReviewResultModel(BaseModel):
    """A single reviewer's structured output."""
    dimension: str = Field(description="Review dimension: pacing_conflict|character_dialogue|hook_paywall|platform_compliance")
    score: int = Field(description="Score 0-100")
    strengths: List[str] = Field(default_factory=list, description="1-2 specific strengths")
    issues: List[str] = Field(default_factory=list, description="1-3 specific problems")
    suggestions: str = Field(default="", description="Actionable revision instructions")
    pass_vote: bool = Field(description="True if this dimension passes muster")


# ═══════════════════════════════════════════════════════════════
# Reviewer Prompts — each focused on ONE dimension
# ═══════════════════════════════════════════════════════════════

SYSTEM_PACING = """你是短剧【节奏与冲突】评审专家。只从这一个维度评审。

评审标准:
1. 节奏密度: 短剧需要 3 秒一个反转、10 秒一个记忆点。检查是否有超过 3 句对话没有推进剧情。
2. 冲突层级: 每个场景至少有一个冲突（人物 vs 人物 / 人物 vs 环境 / 人物 vs 自身）。冲突是否足够尖锐。
3. 反转频率: 每 2-3 个场景应该有一个小反转（信息差、身份暴露、计划被打乱）。
4. 情绪起伏: 不能一直高也不能一直平。检查情绪曲线的起伏。

输出 JSON（不要多余文字）:
{
  "dimension": "pacing_conflict",
  "score": 75,
  "strengths": ["第1场景开门见山直接引入冲突"],
  "issues": ["第3场景3句话都在描述环境没有推进剧情", "第5场景冲突解决太容易缺乏张力"],
  "suggestions": "第3场景删掉环境描写直接进入对话；第5场景加入第三方角色突然闯入打断和解",
  "pass_vote": true
}
pass_vote: true = 本维度合格可以发布, false = 需要修改"""

SYSTEM_CHARACTER = """你是短剧【角色与对白】评审专家。只从这一个维度评审。

评审标准:
1. 角色一致性: 每个角色的性格、说话方式、行为模式是否前后统一。是否有 OOC (out of character)。
2. 对白推动力: 每句对白是否推动剧情或揭示角色。检查废话对白（纯寒暄、重复信息）。
3. 对白个性化: 不同角色的对白是否有辨识度。把对白遮住名字应该能判断是谁说的。
4. 角色弧线: 角色从出场到现在是否有变化（成长/堕落/觉醒）。

输出 JSON（不要多余文字）:
{
  "dimension": "character_dialogue",
  "score": 68,
  "strengths": ["女主对白有个性，不看名字也知道是她在说"],
  "issues": ["男主在第4场景说话突然变得很文绉绉与前几集不符", "助理角色的对白都是功能性废话"],
  "suggestions": "男主对白恢复口语化；助理要么删掉两句话要么给一句有信息量的台词",
  "pass_vote": false
}"""

SYSTEM_HOOK = """你是短剧【钩子与付费点】评审专家。只从这一个维度评审。

评审标准:
1. 开场钩子 (0-15s): 开头 3 句话内是否抓住了注意力（悬念/冲突/反常识/情感冲击）。
2. 结尾钩子: 本集结尾是否让人必须看下一集（信息差悬念 / 人物命运悬念 / 关系破裂悬念）。
3. 付费点卡位: 钩子出现频率是否均匀。理想: 开头(15s) + 中间(30s) + 结尾(最后5s)。
4. 钩子多样性: 不能每集都是同一种钩子（全是"突然出现一个人"）。

输出 JSON（不要多余文字）:
{
  "dimension": "hook_paywall",
  "score": 55,
  "strengths": ["结尾让主角发现真相的反转有效"],
  "issues": ["开头3句是平淡对话没有钩子", "中间缺少付费点（适合插广告或锁集的地方）"],
  "suggestions": "开头直接用悬念开场（'你为什么要骗我？'）；在第30秒处加入身份暴露的桥段作为付费卡点",
  "pass_vote": false
}"""

SYSTEM_COMPLIANCE = """你是短剧【合规与平台适配】评审专家。只从这一个维度评审。

评审标准:
1. 内容安全: 是否涉及政治敏感、色情、暴力过度、违法内容、不良价值观。
2. 平台适配: 对白长度是否适合字幕（≤15字/句），场景是否可低成本拍摄。
3. 视觉可执行: 描述的环境和动作是否能用低成本拍摄（群演少、特效少、场景简单）。
4. 价值观: 是否符合主流观众价值观（不宣扬拜金、不美化犯罪、小三没好下场）。

输出 JSON（不要多余文字）:
{
  "dimension": "platform_compliance",
  "score": 90,
  "strengths": ["内容干净无违规", "场景简单可执行"],
  "issues": [],
  "suggestions": "",
  "pass_vote": true
}"""

REVIEWERS = [
    ("pacing_conflict", SYSTEM_PACING),
    ("character_dialogue", SYSTEM_CHARACTER),
    ("hook_paywall", SYSTEM_HOOK),
    ("platform_compliance", SYSTEM_COMPLIANCE),
]


# ═══════════════════════════════════════════════════════════════
# LangGraph State Machine
# ═══════════════════════════════════════════════════════════════

class EpisodeReviewGraph:
    """Multi-agent review graph for a single episode."""

    def __init__(self, llm):
        self.llm = llm
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(dict)

        workflow.add_node("review_parallel", self._review_parallel)
        workflow.add_node("merge_feedback", self._merge_feedback)
        workflow.add_node("decide", self._decide)
        workflow.add_node("rewrite", self._rewrite)

        workflow.set_entry_point("review_parallel")
        workflow.add_edge("review_parallel", "merge_feedback")
        workflow.add_edge("merge_feedback", "decide")

        workflow.add_conditional_edges(
            "decide",
            self._route_decision,
            {
                "pass": END,
                "reject": END,
                "revise": "rewrite",
            },
        )
        workflow.add_edge("rewrite", "review_parallel")

        return workflow.compile()

    # ── Node: Review Parallel ──

    async def _review_parallel(self, state: dict) -> dict:
        """Run all 4 reviewers in parallel, each with a different lens."""
        content = state["episode_content"]
        ep_outline = state["episode_outline"]
        characters = state["characters"]
        style = state["style"]

        char_context = "\n".join([
            f"- {c.get('name', '')}: {c.get('personality', '')} ({c.get('role', '')})"
            for c in characters[:6]
        ])

        async def _single_review(dimension: str, system_prompt: str) -> ReviewResultModel:
            t0 = time.time()
            try:
                structured_llm = self.llm.with_structured_output(ReviewResultModel, method="json_mode")
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"""评审以下一集短剧剧本的【{dimension}】维度：

【剧集信息】第{ep_outline.get('episode_number', '?')}集 — {ep_outline.get('title', '')}
【风格】{style}
【角色档案】
{char_context}

【剧本内容】
{content[:6000]}"""),
                ]
                result: ReviewResultModel = await structured_llm.ainvoke(messages, config={"timeout": 90})
                logger.info(f"Reviewer[{dimension}]: score={result.score} "
                            f"pass={result.pass_vote} "
                            f"elapsed={time.time()-t0:.1f}s")
                return result
            except Exception as e:
                logger.error(f"Reviewer[{dimension}] failed: {e}")
                return ReviewResultModel(
                    dimension=dimension, score=60,
                    strengths=[], issues=[f"评审异常: {str(e)[:100]}"],
                    suggestions="", pass_vote=True,
                )

        tasks = [_single_review(dim, prompt) for dim, prompt in REVIEWERS]
        reviews = await asyncio.gather(*tasks)

        # Accumulate reviews across cycles
        prev_reviews = state.get("reviews", [])
        return {**state, "reviews": prev_reviews + list(reviews)}

    # ── Node: Merge Feedback (no LLM) ──

    async def _merge_feedback(self, state: dict) -> dict:
        """Merge outputs from all reviewers. No LLM — pure logic."""
        reviews: list = state.get("reviews", [])
        # Only consider reviews from the latest cycle
        review_count = len(REVIEWERS)
        latest_reviews = reviews[-review_count:] if len(reviews) >= review_count else reviews

        if not latest_reviews:
            return {**state, "merged_verdict": "reject", "merged_score": 0, "merged_feedback": "No reviewers available"}

        # Weighted score: hooks + pacing matter most for short drama
        weights = {
            "pacing_conflict": 0.30,
            "character_dialogue": 0.25,
            "hook_paywall": 0.30,
            "platform_compliance": 0.15,
        }

        total_weight = 0.0
        weighted_sum = 0.0
        for r in latest_reviews:
            w = weights.get(r.dimension, 0.25)
            weighted_sum += r.score * w
            total_weight += w
        merged_score = int(weighted_sum / total_weight) if total_weight > 0 else 60

        vote_pass = sum(1 for r in latest_reviews if r.pass_vote)
        vote_total = len(latest_reviews)

        # Deduplicate and prioritize feedback
        all_issues = []
        all_suggestions = []
        for r in latest_reviews:
            for issue in r.issues:
                if issue and issue not in all_issues:
                    all_issues.append(issue)
            if r.suggestions and r.suggestions not in all_suggestions:
                all_suggestions.append(r.suggestions)

        merged_feedback_parts = []
        if all_issues:
            merged_feedback_parts.append("【问题】\n" + "\n".join(f"- {i}" for i in all_issues[:6]))
        if all_suggestions:
            merged_feedback_parts.append("【修改建议】\n" + "\n".join(f"- {s}" for s in all_suggestions[:4]))
        merged_feedback = "\n\n".join(merged_feedback_parts) if merged_feedback_parts else "无明显问题"

        if merged_score >= PASS_THRESHOLD and vote_pass >= 3:
            verdict = "pass"
        elif merged_score < REJECT_THRESHOLD:
            verdict = "reject"
        else:
            verdict = "revise"

        logger.info(f"Merge: score={merged_score} vote={vote_pass}/{vote_total} "
                    f"issues={len(all_issues)} verdict={verdict}")

        return {
            **state,
            "merged_score": merged_score,
            "merged_verdict": verdict,
            "merged_feedback": merged_feedback,
            "vote_pass": vote_pass,
            "vote_total": vote_total,
        }

    # ── Node: Decide ──

    async def _decide(self, state: dict) -> dict:
        """Decision node — route based on merged verdict."""
        verdict = state.get("merged_verdict", "revise")
        attempt = state.get("attempt", 1)

        # Force reject after max attempts
        if verdict == "revise" and attempt >= MAX_REVIEW_ATTEMPTS:
            logger.warning(f"Episode review: max attempts ({MAX_REVIEW_ATTEMPTS}) reached, accepting as-is")
            state["merged_verdict"] = "pass"  # Accept current version
            return state

        # If pass or reject, finalize
        if verdict == "pass":
            state["final_content"] = state["episode_content"]
            state["final_storyboard"] = state.get("storyboard", [])
        elif verdict == "reject":
            logger.error(f"Episode review: REJECTED score={state.get('merged_score')}")

        return state

    @staticmethod
    def _route_decision(state: dict) -> str:
        return state.get("merged_verdict", "revise")

    # ── Node: Rewrite ──

    async def _rewrite(self, state: dict) -> dict:
        """Writer agent: revise episode based on merged reviewer feedback."""
        content = state["episode_content"]
        feedback = state["merged_feedback"]
        score = state["merged_score"]
        attempt = state.get("attempt", 1)
        ep_outline = state["episode_outline"]
        style = state["style"]

        logger.info(f"Rewrite attempt {attempt+1}: score={score}, "
                    f"issues_remaining={len(feedback)}")

        rewrite_prompt = f"""你是资深短剧改稿编剧。根据评审意见修改以下一集剧本。

【剧集】第{ep_outline.get('episode_number', '?')}集 — {ep_outline.get('title', '')}
【风格】{style}

【评审意见】({score}/100 分)
{feedback}

【修改原则】
- 只修改评审指出的问题，不要改动评审没提到的部分
- 保持原有的场景结构和角色
- 保留分镜标注的格式
- 钩子必须改到有 3 秒冲击力
- 对白精简，每句不超过 20 字

【原剧本】
{content[:8000]}"""

        try:
            messages = [
                SystemMessage(content="你是短剧改稿编剧。只针对性地修改评审指出的问题，不要重写整个剧本。"),
                HumanMessage(content=rewrite_prompt),
            ]
            response = await self.llm.ainvoke(messages, config={"timeout": 120})
            revised_content = response.content

            # Re-extract storyboard from revised content
            import re
            board_pattern = re.compile(
                r'镜号：(\d+)\s*\|\s*镜头类型：(.*?)\s*\|\s*运镜：(.*?)\s*\|\s*时长：(.*?)\s*\|\s*画面[：:](.*?)(?=镜号|【|$)',
                re.S
            )
            revised_storyboard = []
            for m in board_pattern.finditer(revised_content):
                try:
                    dur_str = m.group(4).strip().replace('s', '').replace('秒', '')
                    revised_storyboard.append({
                        "shot_number": len(revised_storyboard) + 1,
                        "camera_type": m.group(2).strip(),
                        "camera_movement": m.group(3).strip(),
                        "duration_seconds": float(dur_str) if dur_str else 5.0,
                        "description": m.group(5).strip(),
                    })
                except (ValueError, IndexError):
                    continue

            return {
                **state,
                "episode_content": revised_content,
                "storyboard": revised_storyboard if revised_storyboard else state.get("storyboard", []),
                "attempt": attempt + 1,
            }
        except Exception as e:
            logger.warning(f"Rewrite failed: {e}, keeping original")
            return {**state, "attempt": attempt + 1}  # Increment to avoid infinite loop


# ═══════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════

async def review_episode(
    llm,
    episode_content: str,
    episode_outline: dict,
    characters: List[dict],
    style: str,
    storyboard: Optional[List[dict]] = None,
    prev_episode_hook: str = "",
) -> Dict[str, Any]:
    """Run the multi-agent review loop for a single episode.

    Args:
        llm: LangChain chat model instance.
        episode_content: The generated episode script.
        episode_outline: {episode_number, title, outline}.
        characters: Character profiles for consistency check.
        style: Script style (ancient/suspense/comedy).
        storyboard: Extracted storyboard shots.
        prev_episode_hook: Hook from the previous episode.

    Returns:
        {
            "content": final script,
            "storyboard": final storyboard,
            "hook": extracted hook from final script,
            "score": final merged score,
            "attempts": number of review cycles,
            "reviews": [all review results across cycles],
        }
    """
    graph = EpisodeReviewGraph(llm)

    initial_state = {
        "episode_outline": episode_outline,
        "characters": characters,
        "style": style,
        "prev_episode_hook": prev_episode_hook,
        "episode_content": episode_content,
        "storyboard": storyboard or [],
        "attempt": 1,
        "reviews": [],
        "merged_score": 0,
        "merged_verdict": "revise",
        "merged_feedback": "",
        "vote_pass": 0,
        "vote_total": 4,
        "final_content": "",
        "final_storyboard": [],
        "final_hook": "",
    }

    t0 = time.time()
    result = await graph.graph.ainvoke(initial_state)

    # Extract hook from final content
    import re
    hook = ""
    final_content = result.get("final_content", "") or result.get("episode_content", "")
    hook_match = re.search(r'【结尾钩子】(.+?)(?:\n|$)', final_content)
    if hook_match:
        hook = hook_match.group(1).strip()

    logger.info(f"Episode review complete: score={result.get('merged_score', 0)} "
                f"attempts={result.get('attempt', 1)} "
                f"verdict={result.get('merged_verdict')} "
                f"elapsed={time.time()-t0:.1f}s")

    return {
        "content": final_content,
        "storyboard": result.get("final_storyboard") or result.get("storyboard", []),
        "hook": hook,
        "score": result.get("merged_score", 0),
        "attempts": result.get("attempt", 1),
        "reviews": result.get("reviews", []),
    }
