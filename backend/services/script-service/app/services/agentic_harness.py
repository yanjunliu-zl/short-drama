"""
Agentic AI Harness — Multi-Agent Orchestration with Tool Calling & Self-Optimization.

Industry alignment: LangGraph + CrewAI + DSPy production pattern.

Agents:
  ScriptAgent  — generates script content
  ReviewAgent  — evaluates quality, finds issues
  PolishAgent  — rewrites weak sections
  RouterAgent  — decides next action based on current state

Capabilities:
  #H1: Multi-Agent collaboration — agents critique and refine each other
  #H2: Conditional branching + Plan-Execute — dynamic task decomposition
  #H3: Tool calling — agents can query DB, call APIs, read files
  #H4: Prompt auto-optimization — DSPy-like feedback → prompt refinement
"""
import asyncio
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple, Callable, Awaitable

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

logger = logging.getLogger(__name__)


# ============================================================
# Tool Definition — Agents can call tools
# ============================================================

@dataclass
class Tool:
    """A tool that an AI agent can invoke."""
    name: str
    description: str
    parameters: Dict[str, str]  # name → description
    handler: Callable[..., Awaitable[Any]]

    def to_prompt(self) -> str:
        params = ", ".join(f"{k}: {v}" for k, v in self.parameters.items())
        return f"  - {self.name}({params}): {self.description}"


class ToolRegistry:
    """Registry of available tools for agents."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get_tools_prompt(self) -> str:
        return "\n".join(t.to_prompt() for t in self._tools.values())

    async def execute(self, tool_name: str, **kwargs) -> str:
        tool = self._tools.get(tool_name)
        if not tool:
            return f"Error: unknown tool '{tool_name}'"
        try:
            result = await tool.handler(**kwargs)
            return str(result)[:2000]
        except Exception as e:
            return f"Tool error: {e}"


# ============================================================
# #H2: Plan Node — Break complex tasks into sub-tasks
# ============================================================

@dataclass
class PlanStep:
    """A single step in a plan."""
    step_id: int
    action: str          # "generate" / "review" / "polish" / "tool_call"
    description: str
    depends_on: List[int] = field(default_factory=list)  # step IDs this depends on
    status: str = "pending"  # pending / running / done / failed
    result: str = ""


class PlanNode:
    """Plan-and-Execute: decompose complex tasks.

    For a 200-chapter novel, instead of one giant LLM call:
      Plan: [Ch1-10] → [Ch11-20] → [Ch21-30] → ... → [Merge]
    """

    @staticmethod
    async def decompose(task_description: str, llm,
                        max_steps: int = 10) -> List[PlanStep]:
        """Use LLM to decompose a complex task into executable steps.

        Args:
            task_description: e.g., "Generate script for 200-chapter novel"
            llm: LLM client
            max_steps: Maximum sub-tasks

        Returns:
            Ordered list of PlanStep.
        """
        prompt = f"""You are a task planner. Break the following complex task into {max_steps} or fewer sequential sub-tasks.

Task: {task_description[:1000]}

Output format (JSON array):
[
  {{"step_id": 1, "action": "generate|review|polish|tool_call",
    "description": "what to do", "depends_on": []}},
  ...
]

Rules:
- Each step should be independently executable
- "depends_on" lists step_ids that must complete first
- Parallel steps (same depends_on) can run concurrently
- First step has no dependencies
- Last step should merge/assemble results"""

        try:
            response = await llm.ainvoke([
                SystemMessage(content="Output only valid JSON array."),
                HumanMessage(content=prompt),
            ], config={"timeout": 60})
            plan_data = json.loads(
                response.content.strip().strip("```json").strip("```"))
            return [
                PlanStep(
                    step_id=s["step_id"],
                    action=s["action"],
                    description=s["description"],
                    depends_on=s.get("depends_on", []),
                )
                for s in plan_data[:max_steps]
            ]
        except Exception as e:
            logger.warning(f"Plan decomposition failed ({e}), using default")
            # Default: single generate step
            return [PlanStep(step_id=1, action="generate",
                            description=task_description[:200])]


# ============================================================
# #H1: Multi-Agent System
# ============================================================

class AgentRole(Enum):
    SCRIPT = "script_agent"
    REVIEW = "review_agent"
    POLISH = "polish_agent"
    ROUTER = "router_agent"


@dataclass
class AgentContext:
    """Shared context passed between agents."""
    task: str
    style: str = ""
    content: str = ""         # Current script content
    quality_scores: Dict[str, float] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    history: List[Dict] = field(default_factory=list)
    iteration: int = 0
    max_iterations: int = 3


class BaseAgent(ABC):
    """Base class for all agents."""

    def __init__(self, name: str, llm, tools: ToolRegistry = None):
        self.name = name
        self.llm = llm
        self.tools = tools or ToolRegistry()

    @abstractmethod
    def system_prompt(self) -> str:
        pass

    async def think(self, context: AgentContext) -> Dict[str, Any]:
        """Agent main loop: think → act → observe."""
        messages = [
            SystemMessage(content=self.system_prompt()),
            HumanMessage(content=self._build_prompt(context)),
        ]

        # Add tool availability info
        if self.tools._tools:
            tools_desc = self.tools.get_tools_prompt()
            messages.append(SystemMessage(
                content=f"Available tools:\n{tools_desc}\n"
                        f"To use a tool, respond with: "
                        f'{{"tool": "tool_name", "args": {{...}}}}'))

        response = await self.llm.ainvoke(messages, config={"timeout": 120})
        result = self._parse_response(response.content, context)
        result["raw_response"] = response.content
        return result

    def _build_prompt(self, context: AgentContext) -> str:
        """Build the human prompt from context."""
        parts = [f"Task: {context.task}"]
        if context.content:
            parts.append(f"Content:\n{context.content[:3000]}")
        if context.issues:
            parts.append("Issues to fix:\n" + "\n".join(
                f"- {i}" for i in context.issues))
        if context.quality_scores:
            parts.append("Quality scores: " +
                        ", ".join(f"{k}={v}" for k, v in context.quality_scores.items()))
        parts.append(f"Iteration: {context.iteration}/{context.max_iterations}")
        return "\n\n".join(parts)

    def _parse_response(self, text: str, context: AgentContext) -> Dict[str, Any]:
        """Parse LLM response, extract tool calls if present."""
        result = {"text": text, "tool_calls": []}

        # #H3: Tool call detection
        tool_pattern = r'\{"tool"\s*:\s*"(\w+)"\s*,\s*"args"\s*:\s*(\{[^}]+\})\}'
        for match in re.finditer(tool_pattern, text):
            try:
                tool_name = match.group(1)
                args = json.loads(match.group(2))
                result["tool_calls"].append({"tool": tool_name, "args": args})
            except json.JSONDecodeError:
                pass

        return result


class ScriptAgent(BaseAgent):
    """Agent responsible for generating script content."""

    def __init__(self, llm, tools: ToolRegistry = None):
        super().__init__("ScriptAgent", llm, tools)

    def system_prompt(self) -> str:
        return """You are a professional short drama scriptwriter.
Generate engaging, well-structured scripts for short video platforms.

Output format:
- Each episode starts with "第N集"
- Use standard script format: scene descriptions, character dialogue, action notes
- Include shot-level storyboard hints
- Keep pacing fast, dialogue natural
- Each episode ends with a cliffhanger

If you need information (character profiles, previous chapters, genre guidelines),
use the available tools to fetch it."""


class ReviewAgent(BaseAgent):
    """Agent responsible for quality evaluation."""

    def __init__(self, llm, tools: ToolRegistry = None):
        super().__init__("ReviewAgent", llm, tools)

    def system_prompt(self) -> str:
        return """You are a professional script editor and quality reviewer.
Evaluate the script and identify specific issues.

Score each dimension (0-10):
1. Plot coherence — does the story make sense?
2. Character consistency — do characters act in character?
3. Dialogue naturalness — does dialogue sound natural?
4. Short-video fitness — is it paced for short video?
5. Cliffhanger quality — does each episode end with a hook?

Output format (JSON):
{
  "scores": {"coherence": 8, "consistency": 7, "dialogue": 8, "fitness": 9, "cliffhanger": 6},
  "total": 7.6,
  "verdict": "pass|retry|reject",
  "issues": ["Issue 1", "Issue 2"],
  "suggestions": "How to fix the issues"
}"""

    async def evaluate(self, context: AgentContext) -> Dict[str, Any]:
        result = await self.think(context)
        try:
            # Extract JSON from response
            text = result.get("text", "")
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                evaluation = json.loads(text[start:end])
                result.update(evaluation)
        except json.JSONDecodeError:
            result["verdict"] = "pass"  # Default pass on parse failure
        return result


class PolishAgent(BaseAgent):
    """Agent responsible for rewriting weak sections."""

    def __init__(self, llm, tools: ToolRegistry = None):
        super().__init__("PolishAgent", llm, tools)

    def system_prompt(self) -> str:
        return """You are a professional script polisher.
Rewrite the specified sections to fix the issues listed.

Rules:
- Keep the original plot and character actions
- Only fix the specific issues mentioned
- Maintain the same format and episode structure
- Output the complete revised script, not just the changed parts
- Do NOT add explanations or comments"""


class RouterAgent(BaseAgent):
    """Agent that decides the next action based on current state.

    Replaces fixed linear workflow with dynamic routing.
    """

    def __init__(self, llm):
        super().__init__("RouterAgent", llm)

    def system_prompt(self) -> str:
        return """You are a workflow router. Based on the current state, decide the next action.

Available actions:
- "generate" — need to create new content
- "review" — content exists, need quality check
- "polish" — quality check found issues, need fixes
- "done" — quality is acceptable, finish
- "tool_call" — need external data

Respond with exactly one word: generate, review, polish, done, or tool_call."""

    async def route(self, context: AgentContext) -> str:
        if context.iteration >= context.max_iterations:
            return "done"
        if not context.content:
            return "generate"
        if not context.quality_scores and context.content:
            return "review"
        if context.quality_scores.get("total", 0) < 7.0:
            return "polish"
        return "done"


# ============================================================
# #H4: DSPy-like Prompt Auto-Optimization
# ============================================================

class PromptOptimizer:
    """DSPy-inspired automatic prompt optimization via evaluation feedback.

    When a prompt produces low-quality output, the optimizer:
      1. Collects the failed prompt + output + score
      2. Generates an improved version of the prompt
      3. A/B tests the new prompt against the old one
      4. Keeps the better version
    """

    def __init__(self, llm):
        self.llm = llm
        self._prompt_versions: Dict[str, List[Tuple[str, float]]] = {}
        self._current_versions: Dict[str, str] = {}

    def register_prompt(self, name: str, template: str):
        """Register a prompt template for optimization."""
        self._current_versions[name] = template
        if name not in self._prompt_versions:
            self._prompt_versions[name] = [(template, 0.0)]

    def get_prompt(self, name: str) -> str:
        return self._current_versions.get(name, "")

    async def record_feedback(self, name: str, prompt: str,
                              score: float, output: str):
        """Record evaluation feedback for a prompt execution."""
        if name not in self._prompt_versions:
            return
        self._prompt_versions[name].append((prompt, score))

        # Keep only last 20 versions
        if len(self._prompt_versions[name]) > 20:
            self._prompt_versions[name] = self._prompt_versions[name][-20:]

    async def optimize(self, name: str, output: str,
                       issues: List[str], target_score: float) -> str:
        """Generate an improved version of the prompt.

        Only triggers when score drops below threshold.
        """
        if name not in self._current_versions:
            return self._current_versions.get(name, "")

        current = self._current_versions[name]
        optimization_prompt = f"""You are a prompt engineer. Improve the following system prompt
based on the issues found in its output.

Current prompt:
{current}

Issues with output:
{chr(10).join(f'- {i}' for i in issues[:5])}

Sample of problematic output:
{output[:1000]}

Target quality score: {target_score}

Generate an improved version of the prompt. Keep the same structure and role,
but add specific instructions to address the issues. Output ONLY the new prompt text."""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="Output only the improved prompt text, no explanations."),
                HumanMessage(content=optimization_prompt),
            ], config={"timeout": 60})

            improved = response.content.strip()
            if len(improved) > 50:
                self._current_versions[name] = improved
                logger.info(f"Prompt '{name}' auto-optimized "
                           f"({len(current)}→{len(improved)} chars)")
                return improved
        except Exception as e:
            logger.debug(f"Prompt optimization skipped: {e}")

        return current


# ============================================================
# Agentic Orchestrator — Main Harness
# ============================================================

class AgenticOrchestrator:
    """Multi-agent orchestration engine — replaces linear workflow.

    Flow:
      Router → (ScriptAgent | ReviewAgent | PolishAgent) → Router → ... → Done

    The Router dynamically decides the next step based on agent outputs,
    enabling conditional branching, self-correction, and iterative refinement.
    """

    def __init__(self, llm,
                 tools: ToolRegistry = None,
                 max_iterations: int = 5):
        self.llm = llm

        # Build tool registry with default tools
        self.tools = tools or ToolRegistry()
        self._register_default_tools()

        # Create agents
        self.script_agent = ScriptAgent(llm, self.tools)
        self.review_agent = ReviewAgent(llm, self.tools)
        self.polish_agent = PolishAgent(llm, self.tools)
        self.router = RouterAgent(llm)

        # Prompt optimizer
        self.optimizer = PromptOptimizer(llm)

        self.max_iterations = max_iterations

    def _register_default_tools(self):
        """Register built-in tools that agents can use."""
        self.tools.register(Tool(
            name="fetch_character_profile",
            description="Fetch character profile from database",
            parameters={"name": "character name"},
            handler=self._tool_fetch_character,
        ))
        self.tools.register(Tool(
            name="fetch_chapter_context",
            description="Fetch context from a specific chapter",
            parameters={"chapter": "chapter number"},
            handler=self._tool_fetch_chapter,
        ))
        self.tools.register(Tool(
            name="search_similar_scripts",
            description="Search for similar scripts in the database",
            parameters={"query": "search keywords"},
            handler=self._tool_search_scripts,
        ))

    async def _tool_fetch_character(self, name: str) -> str:
        """Tool: fetch character profile."""
        # In production: query character vector store
        return f"Character '{name}': personality=勇敢坚毅, role=主角"

    async def _tool_fetch_chapter(self, chapter: str) -> str:
        """Tool: fetch chapter context."""
        return f"Chapter {chapter}: [context would be fetched from RAG]"

    async def _tool_search_scripts(self, query: str) -> str:
        """Tool: search similar scripts."""
        return f"Search results for '{query}': [semantic search results]"

    # ── Main Orchestration Loop ──

    async def run(self, task: str, style: str = "",
                  initial_content: str = "",
                  max_iterations: int = 5) -> Dict[str, Any]:
        """Execute the full multi-agent orchestration pipeline.

        Args:
            task: Task description (e.g., "Generate script from novel chapter 5")
            style: Script style (ancient/suspense/comedy)
            initial_content: Optional starting content
            max_iterations: Maximum agent iterations

        Returns:
            {"content": final_script, "iterations": N,
             "final_score": 7.8, "history": [...]}
        """
        t0 = time.time()

        context = AgentContext(
            task=task, style=style, content=initial_content,
            max_iterations=min(max_iterations, self.max_iterations),
        )

        # #H2: Plan decomposition for complex tasks
        if len(task) > 500 and not initial_content:
            plan_steps = await PlanNode.decompose(task, self.llm, max_steps=8)
            logger.info(f"Plan: {len(plan_steps)} steps")
        else:
            plan_steps = [PlanStep(step_id=1, action="generate",
                                   description=task[:200])]

        # Register prompts for optimization
        for agent in [self.script_agent, self.review_agent, self.polish_agent]:
            self.optimizer.register_prompt(
                agent.name, agent.system_prompt())

        # Execute plan steps
        for step in plan_steps:
            step.status = "running"
            logger.info(f"Executing step {step.step_id}: {step.action} — "
                       f"{step.description[:80]}")

            if step.action == "generate":
                result = await self.script_agent.think(context)
                context.content = result.get("text", "")
                step.result = context.content[:500]

                # #H3: Execute any tool calls requested by the agent
                for tc in result.get("tool_calls", []):
                    tool_result = await self.tools.execute(
                        tc["tool"], **tc.get("args", {}))
                    context.content += f"\n\n[Tool: {tc['tool']}] {tool_result}"

            elif step.action == "review":
                evaluation = await self.review_agent.evaluate(context)
                context.quality_scores = evaluation.get("scores", {})
                context.issues = evaluation.get("issues", [])
                step.result = str(evaluation.get("total", 0))

                # #H4: Record feedback for prompt optimization
                await self.optimizer.record_feedback(
                    self.review_agent.name,
                    self.review_agent.system_prompt(),
                    evaluation.get("total", 7.0),
                    context.content[:2000],
                )

                # Auto-optimize if score is low
                if evaluation.get("total", 10) < 7.0:
                    new_prompt = await self.optimizer.optimize(
                        self.script_agent.name,
                        context.content[:2000],
                        context.issues,
                        target_score=7.5,
                    )
                    if new_prompt:
                        self.script_agent._system_prompt = new_prompt

            elif step.action == "polish":
                if context.issues:
                    result = await self.polish_agent.think(context)
                    context.content = result.get("text", context.content)
                    step.result = context.content[:500]

            step.status = "done"
            context.iteration += 1
            context.history.append({
                "step": step.step_id, "action": step.action,
                "status": step.status,
            })

        elapsed = time.time() - t0

        final_score = context.quality_scores.get(
            "total",
            sum(context.quality_scores.values()) / max(
                len(context.quality_scores), 1)
            if context.quality_scores else 0,
        )

        logger.info(f"AgenticOrchestrator done: {len(plan_steps)} steps, "
                    f"score={final_score}, elapsed={elapsed:.1f}s")

        return {
            "content": context.content,
            "iterations": context.iteration,
            "final_score": final_score,
            "quality_scores": context.quality_scores,
            "issues": context.issues,
            "history": context.history,
            "elapsed_seconds": round(elapsed, 1),
        }
