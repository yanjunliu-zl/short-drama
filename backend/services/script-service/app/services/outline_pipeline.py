"""
Outline → Script Pipeline (lightweight, no RAG overhead).

Internal implementation detail of ScriptGenerationEngine.
Exposed publicly as engine.generate_from_outline().
"""
import asyncio
import logging
import re
import time
from typing import Dict, Any, List, Optional, Callable, AsyncGenerator

from langchain_core.messages import SystemMessage, HumanMessage

from app.utils.sse import format_sse_event, EVENT_STAGE, EVENT_ERROR, EVENT_DONE
from app.services.quality_judge import QualityJudge
from app.services.content_safety import get_safety_checker

logger = logging.getLogger(__name__)

MAX_CONCURRENT_CHAPTERS = 3

# Chinese numerals for episode numbering (shared)
def _cn_numeral(n: int) -> str:
    """Convert an integer to Chinese numeral. Handles 1-9999."""
    if n <= 0:
        return str(n)
    digits = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九']
    if n < 10:
        return digits[n]
    if n < 20:
        return '十' + digits[n % 10]
    if n < 100:
        return digits[n // 10] + '十' + digits[n % 10]
    if n < 1000:
        result = digits[n // 100] + '百'
        remainder = n % 100
        if remainder == 0:
            return result
        if remainder < 10:
            return result + '零' + digits[remainder]
        return result + _cn_numeral(remainder)
    if n < 10000:
        result = digits[n // 1000] + '千'
        remainder = n % 1000
        if remainder == 0:
            return result
        if remainder < 100:
            result += '零'
        return result + _cn_numeral(remainder)
    return str(n)  # 万以上极少用于剧集标题


class OutlinePipeline:
    """Lightweight outline → script pipeline.

    Takes a ScriptGenerationEngine reference for LLM calls and shared utilities.
    Usage: engine.outline.generate(outline_text=..., style=..., target_episodes=...)
    """

    def __init__(self, engine):
        self._engine = engine  # ScriptGenerationEngine instance

    # ── Main entry point ──

    async def generate(
        self,
        outline_text: str,
        style: str = "",
        target_episodes: int = 10,
        progress_callback: Optional[Callable[[int, str], Any]] = None,
        user_context: str = "",
    ) -> Dict[str, Any]:
        """Execute a lightweight pipeline optimized for outlines/ideas.

        Unlike novels, outlines don't need semantic chunking, FAISS indexing,
        or RAG retrieval. The key step is story framework expansion:
        outline → rich story framework → per-episode generation.

        LLM calls: 1 (framework) + N (episodes) + 1 (quality) = N + 2
        """
        style = style or self._engine.default_style

        result: Dict[str, Any] = {
            "stages": {}, "script_scenes": [], "final_script": "",
            "characters": [], "character_graph": {"relationships": [], "key_scenes": [], "key_props": []},
            "entities": {"characters": [], "locations": [], "props": []},
            "storyboard": [],
        }

        t_total = time.time()

        # ── Stage A: Story Framework Expansion (1 LLM call) ──
        logger.info(f"=== Outline Stage A: Framework expansion (target={target_episodes} eps, input_len={len(outline_text)}) ===")
        if progress_callback:
            await progress_callback(10, "扩展故事框架")

        enriched_outline = f"{user_context}\n\n---\n\n{outline_text}" if user_context else outline_text
        framework = await self._engine._develop_story_framework(
            story_input=enriched_outline, target_episodes=target_episodes, style=style,
        )
        result["story_framework"] = framework
        result["stages"]["framework"] = {"length": len(framework)}

        # ── Stage B: Parse framework for structured data (no LLM) ──
        logger.info("=== Outline Stage B: Parsing framework structure ===")
        if progress_callback:
            await progress_callback(25, "解析故事结构")

        framework_data = self._parse_story_framework(framework, target_episodes)
        characters = framework_data.get("characters", [])
        key_scenes = framework_data.get("key_scenes", [])
        key_props = framework_data.get("key_props", [])
        episode_outlines = framework_data.get("episode_outlines", [])

        while len(episode_outlines) < target_episodes:
            ep_num = len(episode_outlines) + 1
            episode_outlines.append({
                "episode_number": ep_num, "title": f"第{ep_num}集",
                "outline": "继续推进主线剧情，发展角色关系。",
            })

        result["characters"] = characters
        result["character_graph"] = {
            "relationships": framework_data.get("relationships", []),
            "key_scenes": key_scenes,
            "key_props": key_props,
        }
        result["stages"]["parse"] = {
            "characters": len(characters), "scenes": len(key_scenes),
            "props": len(key_props), "episode_outlines": len(episode_outlines),
        }

        # ── Stage C: Per-episode generation (N LLM calls, concurrent) ──
        logger.info(f"=== Outline Stage C: Generating {len(episode_outlines)} episodes (max {MAX_CONCURRENT_CHAPTERS} concurrent) ===")
        if progress_callback:
            await progress_callback(30, f"逐集生成剧本({len(episode_outlines)}集)")

        sem = asyncio.Semaphore(MAX_CONCURRENT_CHAPTERS)
        completed = 0

        async def _gen_one(idx: int, ep_outline: dict) -> tuple:
            nonlocal completed
            async with sem:
                episode = await self._generate_episode_from_outline(
                    episode_outline=ep_outline, characters=characters, style=style,
                    story_framework=framework, episode_index=idx,
                    total_episodes=len(episode_outlines),
                )
            completed += 1
            if progress_callback and len(episode_outlines) > 1:
                pct = 30 + int(completed / len(episode_outlines) * 50)
                await progress_callback(pct, f"剧本生成 {completed}/{len(episode_outlines)}")
            return idx, episode

        tasks = [_gen_one(i, ep) for i, ep in enumerate(episode_outlines)]
        results_list = await asyncio.gather(*tasks)
        results_list.sort(key=lambda x: x[0])

        all_episodes = []
        all_storyboard = []
        for _, ep_data in results_list:
            all_episodes.append(ep_data)
            for shot in ep_data.get("storyboard", []):
                shot["_episode"] = ep_data.get("episode_number", 1)
                all_storyboard.append(shot)

        total_paywalls = sum(1 for ep in all_episodes for beat in ep.get("beat_sheet", []) if beat.get("is_paywall"))
        result["stages"]["generation"] = {"episodes_generated": len(all_episodes), "total_paywalls": total_paywalls}

        # ── Stage D: Cross-episode character consistency check ──
        if len(all_episodes) >= 3 and len(characters) >= 2:
            logger.info("=== Outline Stage D: Cross-episode character consistency ===")
            if progress_callback:
                await progress_callback(80, "跨集角色一致性检查")
            consistency = await self.check_cross_episode_consistency(
                episodes=all_episodes, characters=characters, style=style,
            )
            result["stages"]["consistency"] = consistency

            if not consistency["consistent"] and consistency.get("issues"):
                logger.warning(f"Cross-episode consistency: {len(consistency['issues'])} issue(s) found — fixing")
                if progress_callback:
                    await progress_callback(85, "修正角色一致性问题")
                all_episodes = await self.fix_consistency_issues(
                    episodes=all_episodes, issues=consistency["issues"],
                    characters=characters, style=style,
                )
                # Rebuild storyboard after fixes
                all_storyboard = []
                for ep_data in all_episodes:
                    for shot in ep_data.get("storyboard", []):
                        shot["_episode"] = ep_data.get("episode_number", 1)
                        all_storyboard.append(shot)
                result["stages"]["consistency"]["fixed"] = True
                result["stages"]["consistency"]["issues_fixed"] = len(consistency["issues"])

        # Build final script + episodes
        parts = []
        episodes_list = []
        for i, ep_data in enumerate(all_episodes):
            ep_num = i + 1
            ep_cn = _cn_numeral(ep_num)
            content = ep_data.get("content", "")
            parts.append(f"第{ep_cn}集\n\n{content}")
            episodes_list.append({
                "episode_number": ep_num,
                "title": ep_data.get("title", f"第{ep_cn}集"),
                "content": content,
            })

        result["final_script"] = "\n\n" + "—" * 40 + "\n\n".join(parts)
        result["episodes"] = episodes_list
        result["storyboard"] = all_storyboard

        # Aggregate entities from parsed framework (no separate LLM call)
        result["entities"] = {
            "characters": characters,
            "locations": [{"name": s.get("name", str(s)), "description": s.get("description", "") if isinstance(s, dict) else ""} for s in key_scenes],
            "props": [{"name": p.get("name", str(p)), "description": p.get("description", "") if isinstance(p, dict) else ""} for p in key_props],
        }
        result["stages"]["entities"] = {"characters": len(characters), "locations": len(key_scenes), "props": len(key_props)}

        # Per-episode review scores
        review_scores = [ep.get("review_score", 0) for ep in all_episodes if ep.get("review_score", 0) > 0]
        if review_scores:
            result["stages"]["quality"] = {
                "average_score": round(sum(review_scores) / len(review_scores), 1),
                "episodes_reviewed": len(review_scores),
                "total_attempts": sum(ep.get("review_attempts", 1) for ep in all_episodes),
            }

        result["stages"]["final"] = {"total_length": len(result["final_script"]), "total_elapsed": time.time() - t_total}

        # Content safety check
        try:
            safety = get_safety_checker(enabled=True)
            safety_report = safety.check_script(content=result["final_script"], title="outline-pipeline")
            result["safety_report"] = safety_report.to_dict()
        except Exception:
            pass

        logger.info(f"Outline pipeline complete: {len(all_episodes)} episodes, {len(all_storyboard)} shots, "
                    f"{len(result['final_script'])} chars, elapsed={time.time()-t_total:.1f}s")
        return result

    # ── SSE streaming wrapper ──

    async def generate_sse(
        self, outline_text: str, style: str = "",
        target_episodes: int = 10, user_context: str = "",
    ) -> AsyncGenerator[str, None]:
        """SSE streaming wrapper for run()."""
        queue: asyncio.Queue = asyncio.Queue()

        async def progress_callback(pct: int, stage_name: str):
            await queue.put(format_sse_event({"stage": stage_name, "progress": pct}, event=EVENT_STAGE))

        async def _run():
            try:
                result = await self.run(
                    outline_text=outline_text, style=style,
                    target_episodes=target_episodes, progress_callback=progress_callback,
                    user_context=user_context,
                )
                await queue.put(("__result__", result))
            except Exception as e:
                logger.error(f"Outline SSE error: {e}", exc_info=True)
                await queue.put(("__error__", str(e)))

        task = asyncio.create_task(_run())

        while True:
            item = await queue.get()
            if isinstance(item, tuple):
                kind, payload = item[0], item[1]
                if kind == "__result__":
                    yield format_sse_event({"status": "completed", "result": payload}, event=EVENT_DONE)
                    break
                elif kind == "__error__":
                    yield format_sse_event({"error": payload, "code": "PIPELINE_ERROR"}, event=EVENT_ERROR)
                    break
            else:
                yield item
        await task

    # ── Batch context summarization ──

    async def summarize_batch(self, episodes: list, characters: list) -> str:
        """Create a context summary of the last N episodes for the next batch.

        Captures: key events, character state changes, unresolved threads,
        and the final hook — everything the next batch needs to stay coherent.
        """
        if not episodes or len(episodes) < 3 or self._engine.mock_mode:
            return ""

        # Take last 5 episodes for summary (enough context, not too much)
        recent = episodes[-5:]
        combined = "\n\n---\n\n".join(
            f"第{ep.get('episode_number', '?')}集:\n{ep.get('content', '')[:2000]}"
            for ep in recent
        )

        char_names = "、".join(c.get("name", "") for c in characters[:5])

        try:
            messages = [
                SystemMessage(content="""总结以下剧集的关键信息，用于下一批剧集的续写上下文。只输出事实，不评价。

需要总结:
1. 最新进展: 最近几集发生了什么关键事件
2. 角色状态: 每个角色的当前位置、情绪、与他人的关系状态
3. 未解决线索: 哪些伏笔/冲突还没收
4. 最后钩子: 上一集结尾的悬念是什么（下一集必须承接）

输出格式（纯文本，200-500字）:
【最新进展】
...
【角色状态】
- 角色名: 当前状态
【待解决】
- 未收的线索
【承接钩子】
..."""),
                HumanMessage(content=f"""总结以下 {len(recent)} 集短剧内容:

【主要角色】{char_names}

【最近剧集内容】
{combined[:10000]}"""),
            ]
            response = await self._engine.llm.ainvoke(messages, config={"timeout": 45})
            summary = response.content.strip()[:800]
            logger.info(f"Batch summary: {len(summary)} chars from {len(recent)} episodes")
            return summary
        except Exception as e:
            logger.warning(f"Batch summarization failed ({e}) — skipping")
            return ""

    # ── Framework refresh for long series ──

    async def _refresh_framework(
        self, story_framework: str, recent_context: str, style: str,
        remaining_episodes: int, current_ep: int,
    ) -> str:
        """Rewrite remaining episode outlines based on actual story progress.

        After 2+ batches, the original framework's episode outlines become stale
        ("第61集：继续发展剧情"). This updates them based on what actually happened.
        """
        try:
            messages = [
                SystemMessage(content="""你是短剧编剧。故事已经写了前面部分，你需要根据实际进展重写剩余集数的大纲。

你的任务是更新故事框架中的【分集大纲】部分：
- 为剩余每集写具体的大纲（不是"继续发展"，是具体事件）
- 大纲要承接前文实际发生的事件和角色状态
- 每集包含: 标题、冲突、关键事件、结尾钩子
- 保持原框架的风格和角色设定

直接输出更新后的分集大纲，格式: 第N集标题 / 冲突 / 事件 / 钩子"""),
                HumanMessage(content=f"""【原始框架】
{story_framework[:5000]}

【前 {current_ep} 集实际进展】
{recent_context[:3000]}

【需要重写大纲的集数】
第 {current_ep + 1} ~ {current_ep + remaining_episodes} 集（共 {remaining_episodes} 集）

请输出更新后的分集大纲:"""),
            ]
            response = await self._engine.llm.ainvoke(messages, config={"timeout": 60})
            new_outlines = response.content.strip()
            logger.info(f"Framework refresh: {len(new_outlines)} chars for episodes "
                        f"{current_ep+1}-{current_ep+remaining_episodes}")
            return new_outlines
        except Exception as e:
            logger.warning(f"Framework refresh failed ({e}) — keeping original")
            return ""

    # ── Continuation: generate next batch of episodes ──

    async def continue_from(
        self,
        story_framework: str,
        characters: list,
        style: str,
        start_episode: int,
        additional_episodes: int,
        previous_context: str = "",
        previous_episodes: list = None,
        progress_callback=None,
    ) -> dict:
        """Continue generating episodes from a previous batch.

        For long series (>20 episodes), the story framework is generated once,
        then episodes are produced in batches via this method.

        Args:
            story_framework: The full framework from the initial generation.
            characters: Character profiles parsed from the framework.
            style: Script style.
            start_episode: First episode number of this batch (1-indexed).
            additional_episodes: How many new episodes to generate (max 20).
            progress_callback: Optional callback(pct, stage).

        Returns:
            {"episodes": [...], "storyboard": [...]} — appends to previous result.
        """
        additional_episodes = min(additional_episodes, 20)

        framework_data = self._parse_story_framework(story_framework, start_episode + additional_episodes - 1)

        # Extract episode outlines for our range
        all_outlines = framework_data.get("episode_outlines", [])
        batch_outlines = [
            o for o in all_outlines
            if start_episode <= o.get("episode_number", 0) < start_episode + additional_episodes
        ]

        # If framework doesn't have detailed outlines for these episodes, create generic ones
        if len(batch_outlines) < additional_episodes:
            for ep_num in range(start_episode, start_episode + additional_episodes):
                if not any(o.get("episode_number") == ep_num for o in batch_outlines):
                    batch_outlines.append({
                        "episode_number": ep_num,
                        "title": f"第{ep_num}集",
                        "outline": f"继续推进主线剧情，发展到第{ep_num}集的高潮或转折。",
                    })
        batch_outlines.sort(key=lambda x: x.get("episode_number", 0))

        logger.info(f"Continue: generating episodes {start_episode}-"
                    f"{start_episode + len(batch_outlines) - 1} "
                    f"({len(batch_outlines)} episodes, context={len(previous_context)} chars)")

        if progress_callback:
            await progress_callback(10, f"续写第{start_episode}集起")

        # ── Improvement 1: Refresh framework every 2 batches (40 episodes) ──
        enhanced_framework = story_framework
        if start_episode > 20 and start_episode % 20 == 1 and previous_context:
            # Every ~40 episodes, rewrite remaining outlines based on actual progress
            remaining = max(additional_episodes, 20)
            refreshed = await self._refresh_framework(
                story_framework=story_framework,
                recent_context=previous_context,
                style=style,
                remaining_episodes=remaining,
                current_ep=start_episode - 1,
            )
            if refreshed:
                enhanced_framework = refreshed
                logger.info(f"Framework refreshed at episode {start_episode}")

        # ── Improvement 2: Inject previous episode's ending for hook continuity ──
        prev_ending = ""
        if previous_episodes and len(previous_episodes) >= 1:
            last_ep = previous_episodes[-1]
            last_content = last_ep.get("content", "")
            # Take last ~200 chars — where the hook lives
            prev_ending = last_content[-250:] if len(last_content) > 250 else last_content
            # Try to break at a natural boundary
            for sep in ['【结尾钩子】', '【结尾']:
                idx = prev_ending.rfind(sep)
                if idx > 0:
                    prev_ending = prev_ending[idx:]
                    break

        # Build enhanced framework with context
        if previous_context:
            enhanced_framework = f"{enhanced_framework}\n\n【前情提要——已生成剧集实际进展】\n{previous_context}"
        if prev_ending:
            enhanced_framework = f"{enhanced_framework}\n\n【上一集结尾——必须承接】\n{prev_ending}"

        sem = asyncio.Semaphore(MAX_CONCURRENT_CHAPTERS)
        completed = 0

        async def _gen_one(idx: int, ep_outline: dict) -> tuple:
            nonlocal completed
            ep_num = ep_outline.get("episode_number", start_episode + idx)
            async with sem:
                episode = await self._generate_episode_from_outline(
                    episode_outline=ep_outline, characters=characters, style=style,
                    story_framework=enhanced_framework, episode_index=ep_num - 1,
                    total_episodes=start_episode + additional_episodes - 1,
                )
            completed += 1
            if progress_callback and len(batch_outlines) > 1:
                pct = 10 + int(completed / len(batch_outlines) * 70)
                await progress_callback(pct, f"续写 {completed}/{len(batch_outlines)}")
            return idx, episode

        tasks = [_gen_one(i, ep) for i, ep in enumerate(batch_outlines)]
        results_list = await asyncio.gather(*tasks)
        results_list.sort(key=lambda x: x[0])

        new_episodes = []
        new_storyboard = []
        for _, ep_data in results_list:
            new_episodes.append(ep_data)
            for shot in ep_data.get("storyboard", []):
                shot["_episode"] = ep_data.get("episode_number", start_episode)
                new_storyboard.append(shot)

        # Cross-episode consistency check (new batch + boundary with previous)
        if len(new_episodes) >= 3 and len(characters) >= 2:
            if progress_callback:
                await progress_callback(85, "跨集角色一致性检查")

            # Include recent episodes from previous batch for boundary check
            check_episodes = new_episodes
            if previous_episodes and len(previous_episodes) >= 2:
                # Take last 2 from previous batch + all new episodes
                boundary_eps = previous_episodes[-2:]
                # Adjust episode numbers to avoid confusion
                check_episodes = boundary_eps + new_episodes

            consistency = await self.check_cross_episode_consistency(
                episodes=check_episodes, characters=characters, style=style,
            )
            if not consistency["consistent"] and consistency.get("issues"):
                if progress_callback:
                    await progress_callback(90, "修正一致性问题")
                new_episodes = await self.fix_consistency_issues(
                    episodes=new_episodes, issues=consistency["issues"],
                    characters=characters, style=style,
                )

        episodes_list = []
        for ep_data in new_episodes:
            ep_num = ep_data.get("episode_number", start_episode)
            episodes_list.append({
                "episode_number": ep_num,
                "title": ep_data.get("title", f"第{ep_num}集"),
                "content": ep_data.get("content", ""),
            })

        logger.info(f"Continue complete: {len(episodes_list)} new episodes "
                    f"({start_episode}-{start_episode + len(episodes_list) - 1})")

        return {"episodes": episodes_list, "storyboard": new_episodes}

    # ── Per-episode generation with multi-agent review ──

    async def _generate_episode_from_outline(
        self, episode_outline: dict, characters: list, style: str,
        story_framework: str, episode_index: int, total_episodes: int,
    ) -> dict:
        """Generate a single episode with multi-agent review loop.

        Flow: generate → 4 parallel reviewers → merge → decide
                 ↑                                              │
                 └── rewrite ←── revise ←──────────────────────┘
        """
        ep_num = episode_outline.get("episode_number", episode_index + 1)
        ep_title = episode_outline.get("title", f"第{ep_num}集")
        ep_outline_text = episode_outline.get("outline", "")
        style_rule = self._engine._get_style_instructions(style)

        # Build character context
        char_context_parts = []
        for c in characters[:8]:
            lines = [f"  {c.get('name', '')}（{c.get('role', '')}）"]
            for field, label in [('surface_personality', '表面'), ('real_personality', '真实'),
                                  ('core_desire', '欲望'), ('key_flaw', '缺陷'),
                                  ('speaking_style', '说话'), ('character_arc', '弧线')]:
                if c.get(field):
                    lines.append(f"    {label}: {c[field]}")
            char_context_parts.append("\n".join(lines))
        char_context = "\n\n".join(char_context_parts) if char_context_parts else "（无预设角色）"

        prev_hint = f"这是第{ep_num}集，前面已讲了前{ep_num-1}集的内容" if ep_num > 1 else "这是第1集，开场要吸引眼球"
        next_hint = f"这是倒数第{total_episodes - ep_num + 1}集，要为结局做铺垫" if total_episodes - ep_num < 3 else ""
        mock_content = f"【场景地点】办公室 - 白天\n【场景类型】内景\n△{ep_title}的场景\n主角：（坚定）这就是大纲{ep_num}的内容。"

        if self._engine.mock_mode:
            return {"episode_number": ep_num, "title": ep_title, "content": mock_content,
                    "storyboard": [], "hook": "", "review_score": 0, "review_attempts": 0}

        # ── Generate initial draft ──
        try:
            prompt = f"""根据以下短剧故事框架中第{ep_num}集的大纲，创作完整的一集剧本。

【本集信息】第{ep_num}集 / 共{total_episodes}集 — {ep_title}
{prev_hint}{'，' + next_hint if next_hint else ''}

【本集大纲】
{ep_outline_text[:4000]}

【角色档案】
{char_context}

【台词风格】
{style_rule}

【输出格式】
【分集标题】（一句话概括本集核心冲突或转折，5-15字）
【节拍表】（必须放在剧本正文之前）
00:00-00:15 | 开场钩子 | （具体用什么抓住观众）
00:15-00:30 | 冲突推进 | （核心矛盾如何升级）
00:30-00:45 | 💰付费卡点 | （信息差悬念或情感爆发点，画面定格位置）
00:45-01:00 | 反转/高潮 | （本集最出人意料的事件）
01:00-01:15 | 结尾钩子 | （一句话悬念或新冲突引入）

【场景地点】地点名 - 白天/黑夜
【场景类型】外景/内景

△环境描写（一句话）

角色名：（情绪）对白内容
角色名：（情绪）对白内容
...

【结尾钩子】
一句话悬念提示或剧情爆点

【要求】
- 短剧风格：3秒一反转、10秒一记忆点
- 节拍表严格遵守格式，每个节拍都要写具体内容，不能留空
- 付费卡点必须放在剧情最关键的信息差时刻，画面突然定格
- 对白简洁有力，每句不超过20字，能用动作表达就不用台词
- 结尾钩子必须让人有「必须看下一集」的冲动（除非最后一集）
- 对白:动作:环境 = 5:3:2"""

            messages = [
                SystemMessage(content="你是资深短剧编剧，擅长快节奏、强冲突的短剧创作。每集必须输出完整的节拍表（含付费卡点），格式严格遵循提示中的时间标注。"),
                HumanMessage(content=prompt),
            ]
            response = await self._engine.llm.ainvoke(messages, config={"timeout": 120})
            draft_text = response.content

            # Parse initial storyboard
            board_pattern = re.compile(
                r'镜号：(\d+)\s*\|\s*镜头类型：(.*?)\s*\|\s*运镜：(.*?)\s*\|\s*时长：(.*?)\s*\|\s*画面[：:](.*?)(?=镜号|【|$)',
                re.S
            )
            initial_storyboard = []
            for m in board_pattern.finditer(draft_text):
                try:
                    dur_str = m.group(4).strip().replace('s', '').replace('秒', '')
                    initial_storyboard.append({
                        "shot_number": len(initial_storyboard) + 1,
                        "camera_type": m.group(2).strip(), "camera_movement": m.group(3).strip(),
                        "duration_seconds": float(dur_str) if dur_str else 5.0,
                        "description": m.group(5).strip(),
                    })
                except (ValueError, IndexError):
                    continue
        except Exception as e:
            logger.warning(f"Episode {ep_num} initial generation failed: {e}")
            return {"episode_number": ep_num, "title": ep_title,
                    "content": f"【场景地点】未知 - 白天\n△本集剧情概述：{ep_outline_text[:500]}",
                    "storyboard": [], "hook": "", "review_score": 0, "review_attempts": 0}

        # ── Multi-agent review loop ──
        try:
            from app.services.episode_review_graph import review_episode
            review_result = await review_episode(
                llm=self._engine.llm, episode_content=draft_text,
                episode_outline=episode_outline, characters=characters,
                style=style, storyboard=initial_storyboard,
            )
            beat_sheet = self._parse_beat_sheet(review_result["content"])
            rev_title_match = re.search(r'【分集标题】(.+?)(?:\n|$)', review_result["content"])
            logger.info(f"Episode {ep_num} review: score={review_result['score']} attempts={review_result['attempts']} beats={len(beat_sheet)}")
            return {
                "episode_number": ep_num,
                "title": rev_title_match.group(1).strip() if rev_title_match else ep_title,
                "content": review_result["content"], "storyboard": review_result["storyboard"],
                "hook": review_result["hook"], "beat_sheet": beat_sheet,
                "review_score": review_result["score"], "review_attempts": review_result["attempts"],
            }
        except ImportError:
            logger.warning("episode_review_graph not available — skipping review")
        except Exception as e:
            logger.warning(f"Episode {ep_num} review failed ({e}) — using draft")

        # Fallback: return initial draft
        # Extract title from AI output, fall back to outline title
        title_match = re.search(r'【分集标题】(.+?)(?:\n|$)', draft_text)
        if title_match:
            raw_title = title_match.group(1).strip()
            # If AI just repeated "第X集", treat as no title found
            if re.match(r'^第[一二三四五六七八九十百千\d]+集$', raw_title):
                final_title = ep_title if not re.match(r'^第[一二三四五六七八九十百千\d]+集$', ep_title) else f"第{ep_num}集"
            else:
                final_title = raw_title
        else:
            final_title = ep_title

        hook = ""
        hook_match = re.search(r'【结尾钩子】(.+?)(?:\n|$)', draft_text)
        if hook_match:
            hook = hook_match.group(1).strip()
        return {
            "episode_number": ep_num, "title": final_title,
            "content": draft_text, "storyboard": initial_storyboard,
            "hook": hook, "beat_sheet": self._parse_beat_sheet(draft_text),
            "review_score": 0, "review_attempts": 0,
        }

    # ── Framework parsing (no LLM) ──

    @staticmethod
    def _parse_story_framework(framework_text: str, target_episodes: int) -> dict:
        """Parse LLM-generated story framework into structured data."""
        result = {"characters": [], "relationships": [], "key_scenes": [], "key_props": [], "episode_outlines": []}

        # ── Extract episode outlines ──
        ep_pattern = re.compile(
            r'第\s*([一二三四五六七八九十百千\d]+)\s*集[：:：\s]*(.*?)(?=第\s*(?:[一二三四五六七八九十百千\d]+)\s*集|【核心场景|【核心道具|$)',
            re.DOTALL
        )
        for num_str, content in ep_pattern.findall(framework_text):
            ep_num = OutlinePipeline._parse_framework_ep_num(num_str)
            if ep_num <= 0:
                continue
            lines = content.strip().split("\n")
            title = lines[0].strip()[:50] if lines else f"第{ep_num}集"
            result["episode_outlines"].append({"episode_number": ep_num, "title": title, "outline": content.strip()})
        result["episode_outlines"].sort(key=lambda x: x["episode_number"])

        if not result["episode_outlines"]:
            segments = re.split(r'\n(?=\d+[\.、\)）]|\*{1,3}\s)', framework_text)
            for i, seg in enumerate(segments):
                if i >= target_episodes:
                    break
                lines = seg.strip().split("\n")
                result["episode_outlines"].append({"episode_number": i + 1, "title": lines[0].strip()[:50], "outline": seg.strip()})

        # ── Extract characters ──
        char_section = re.search(r'【角色设定】(.*?)(?=【分集大纲|【核心场景|【核心道具|$)', framework_text, re.DOTALL)
        if char_section:
            char_blocks = re.split(r'\n(?=(?:[-•]\s*)?[^\s：:]{2,8}[：:])', char_section.group(1))
            for block in char_blocks:
                block = block.strip().lstrip('-•').strip()
                if not block or len(block) < 5:
                    continue
                name_match = re.match(r'([^\s：:]{2,8})[：:]', block)
                if not name_match:
                    continue
                name = name_match.group(1).strip()
                if any(kw in name for kw in ['性格', '动机', '弧线', '关系', '角色', '表面', '真实', '核心', '关键', '说话', '人物']):
                    continue

                def _extract_field(text: str, field: str) -> str:
                    for kw in [f'{field}：', f'{field}:', f'- {field}：']:
                        idx = text.find(kw)
                        if idx >= 0:
                            start = idx + len(kw)
                            end = len(text)
                            for sep in ['\n- ', '\n', '。']:
                                pos = text.find(sep, start)
                                if pos > 0 and pos < end:
                                    end = pos
                            return text[start:end].strip()[:200]
                    return ""

                surface = _extract_field(block, '表面性格')
                real_personality = _extract_field(block, '真实性格')
                personality = surface or real_personality or block[name_match.end():].split('\n')[0].strip()[:100]

                role = "主角" if any(kw in block for kw in ['主角', '主人公', '男主', '女主']) else ("反派" if any(kw in block for kw in ['反派', '对手']) else "配角")

                result["characters"].append({
                    "name": name, "role": role, "personality": personality,
                    "surface_personality": surface, "real_personality": real_personality,
                    "core_desire": _extract_field(block, '核心欲望'),
                    "key_flaw": _extract_field(block, '关键缺陷'),
                    "speaking_style": _extract_field(block, '说话方式'),
                    "character_arc": _extract_field(block, '人物弧线'),
                })

        # ── Extract key scenes ──
        scene_section = re.search(r'【核心场景】(.*?)(?=【核心道具|$)', framework_text, re.DOTALL)
        if scene_section:
            scene_lines = [l.strip("- 0123456789.、)） ") for l in scene_section.group(1).split("\n") if l.strip()]
            result["key_scenes"] = [{"name": s[:60], "description": s} for s in scene_lines if len(s) > 2][:10]

        # ── Extract key props ──
        prop_section = re.search(r'【核心道具】(.*?)$', framework_text, re.DOTALL)
        if prop_section:
            prop_lines = [l.strip("- 0123456789.、)） ") for l in prop_section.group(1).split("\n") if l.strip()]
            result["key_props"] = [{"name": p[:60], "description": p} for p in prop_lines if len(p) > 2][:5]

        return result

    @staticmethod
    def _parse_framework_ep_num(num_str: str) -> int:
        """Parse Chinese or Arabic episode number."""
        num_str = num_str.strip()
        if num_str.isdigit():
            return int(num_str)
        cn_map = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
        if num_str in cn_map:
            return cn_map[num_str]
        if '十' in num_str:
            prefix, _, suffix = num_str.partition('十')
            base = cn_map.get(prefix, 1) * 10
            return base + cn_map.get(suffix, 0) if suffix else base
        return 0

    # ── Beat sheet parsing ──

    @staticmethod
    def _parse_beat_sheet(content: str) -> list:
        """Extract beat sheet from generated episode content.

        Returns list of {start, end, type, description, is_paywall}.
        """
        beats = []
        beat_pattern = re.compile(
            r'(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})\s*\|\s*💰?\s*(.{2,12}?)\s*\|\s*(.+?)(?=\d{2}:\d{2}|【|$)',
            re.DOTALL
        )
        for m in beat_pattern.finditer(content):
            beat_type = m.group(3).strip()
            beats.append({
                "start": m.group(1), "end": m.group(2),
                "type": beat_type, "description": m.group(4).strip()[:200],
                "is_paywall": "付费" in beat_type or "💰" in beat_type,
            })
        return beats

    # ── Cross-episode character consistency check ──

    async def check_cross_episode_consistency(
        self, episodes: list, characters: list, style: str,
    ) -> dict:
        """Check character consistency across all generated episodes.

        Each episode was independently reviewed, but no one checked whether
        the character in episode 3 talks/acts the same as in episode 8.

        This runs ONE LLM call that samples character appearances from
        early, middle, and late episodes for each main character,
        then checks: personality, speaking patterns, motivations.

        Returns:
          {
            "consistent": true/false,
            "issues": [
              {"character": "林婉儿", "episodes": [3, 8],
               "problem": "第3集说话短促冷硬，第8集突然变得温和啰嗦，性格断裂",
               "fix_suggestion": "第8集林婉儿对白改回短句风格，删掉多余解释"}
            ],
            "overall_score": 85
          }
        """
        if len(episodes) < 3 or len(characters) < 2:
            return {"consistent": True, "issues": [], "overall_score": 100}

        # Build character samples — early, middle, late episodes
        samples = []
        for c in characters[:5]:
            name = c.get("name", "")
            if not name:
                continue
            # Get episodes where this character likely appears
            # Sample: first, 1/3 point, 2/3 point, last
            indices = [0, len(episodes) // 3, len(episodes) * 2 // 3, len(episodes) - 1]
            indices = sorted(set(i for i in indices if 0 <= i < len(episodes)))
            char_samples = []
            for idx in indices:
                ep = episodes[idx]
                content = ep.get("content", "")
                # Extract lines where this character speaks or is mentioned
                char_lines = []
                for line in content.split("\n"):
                    if name in line and len(line.strip()) > 5:
                        char_lines.append(f"第{idx+1}集: {line.strip()[:120]}")
                if char_lines:
                    char_samples.extend(char_lines[:3])  # Up to 3 lines per episode
            if char_samples:
                samples.append(f"【{name}（{c.get('role', '')}）{{\n" + "\n".join(char_samples[:12]) + "\n}")

        if not samples:
            return {"consistent": True, "issues": [], "overall_score": 100}

        # LLM check
        char_sheet = "\n".join(samples)
        try:
            messages = [
                SystemMessage(content="""你是短剧角色一致性检查员。对照每个角色在其出场集中的言行，判断是否存在性格断裂或人设矛盾。

检查维度:
1. 性格一致性: 同一角色在不同集中是否表现出相同的核心性格特征
2. 说话方式: 对白风格是否统一（句长、语气、用词习惯）
3. 动机连续性: 角色的目标和驱动力是否连贯推进（可以演化，不能突变）
4. 关系一致性: 对待其他角色的态度和互动模式是否统一

注意: 合理的角色成长/变化不是问题——问题是无缘无故的性格突变。

输出 JSON:
{
  "consistent": true,
  "overall_score": 85,
  "issues": [
    {"character": "角色名", "episodes": [3, 8], "problem": "具体问题描述",
     "fix_suggestion": "修改建议"}
  ]
}
如果没有问题，issues 为空数组，consistent 为 true。"""),
                HumanMessage(content=f"""检查以下剧本的角色跨集一致性:

【风格】{style}
【共 {len(episodes)} 集】

【角色跨集言行采样】
{char_sheet}

请逐一检查每个角色，输出 JSON。"""),
            ]

            structured_llm = self._engine.llm.with_structured_output(
                type('ConsistencyResult', (), {
                    '__annotations__': {
                        'consistent': bool, 'overall_score': int,
                        'issues': list,
                    }
                }),
                method="json_mode",
            )
            result = await structured_llm.ainvoke(messages, config={"timeout": 60})

            issues = result.get("issues", []) if isinstance(result, dict) else []
            logger.info(f"Cross-episode consistency: score={result.get('overall_score', '?')} "
                        f"issues={len(issues)}")
            return {
                "consistent": result.get("consistent", len(issues) == 0) if isinstance(result, dict) else True,
                "overall_score": result.get("overall_score", 100) if isinstance(result, dict) else 100,
                "issues": issues,
            }
        except Exception as e:
            logger.warning(f"Cross-episode consistency check failed ({e}) — skipping")
            return {"consistent": True, "issues": [], "overall_score": 100}

    async def fix_consistency_issues(
        self, episodes: list, issues: list, characters: list, style: str,
    ) -> list:
        """Fix cross-episode character consistency issues.

        For each issue, rewrites the target episode's problematic sections
        while preserving everything else.
        """
        if not issues:
            return episodes

        fixed_count = 0
        for issue in issues:
            target_eps = issue.get("episodes", [])
            character = issue.get("character", "")
            problem = issue.get("problem", "")
            fix_suggestion = issue.get("fix_suggestion", "")

            for ep_num in target_eps:
                idx = ep_num - 1
                if idx < 0 or idx >= len(episodes):
                    continue
                ep = episodes[idx]
                content = ep.get("content", "")
                title = ep.get("title", f"第{ep_num}集")

                try:
                    messages = [
                        SystemMessage(content="你是短剧改稿编辑。只修改指定角色相关的对白和描写，保持剧本其余部分完全不变。"),
                        HumanMessage(content=f"""修改以下剧本片段，使角色「{character}」的言行保持跨集一致。

【问题】{problem}
【修改指导】{fix_suggestion}

【剧本】(第{ep_num}集 — {title})
{content[:6000]}

【要求】
- 只修改与「{character}」相关的对白和动作描写
- 保持节拍表、场景结构、其他角色的对话完全不变
- 保持原剧本的快节奏和钩子设计
- 直接返回修改后的完整剧本"""),
                    ]
                    response = await self._engine.llm.ainvoke(messages, config={"timeout": 120})
                    episodes[idx]["content"] = response.content
                    fixed_count += 1
                    logger.info(f"Fixed consistency issue: {character} in episode {ep_num}")
                except Exception as e:
                    logger.warning(f"Failed to fix episode {ep_num}: {e}")

        if fixed_count > 0:
            logger.info(f"Cross-episode consistency: fixed {fixed_count} episode(s)")

        return episodes
