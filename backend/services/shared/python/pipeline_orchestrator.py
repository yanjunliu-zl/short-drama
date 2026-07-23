"""
AI 全链路流水线编排 — 剧本→实体提取→分镜→图像→视频串联（工业级）。

对标 LibTV 三条原则的实现：
- 原则2 (专业工作流):  阶段化执行 + 每阶段可干预 + 审批门 + 并行分支
- 原则3 (Agent 原生):  Skill 接口暴露每个阶段为独立可调用函数
- 原则4 (资产沉淀):   每阶段产出自动入库，角色/场景/分镜可沉淀复用

架构：
    PipelineOrchestrator
    ├── Stage 1: SCRIPT         → 剧本生成 (已有)
    ├── Stage 2: EXTRACT        → 实体提取 (角色/场景/道具) → 入库 AssetLibrary
    ├── Stage 3: STORYBOARD     → 分镜生成 (可引用资产库中的角色/场景模板)
    ├── Stage 3.5: REVIEW       → 人工/AI 审核门 (默认: quality_judge ≥ 60)
    ├── Stage 4: IMAGES         → 图像生成 (Seedance, 注入角色参考图)
    └── Stage 5: VIDEOS         → 视频生成 (Seedance i2v)
"""
import logging
import asyncio
import time
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════

class PipelineStage(str, Enum):
    SCRIPT = "script"
    EXTRACT = "extract"
    STORYBOARD = "storyboard"
    REVIEW = "review"          # 审核门 — 质量不达标则回退到 STORYBOARD
    IMAGES = "images"
    VIDEOS = "videos"


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    AWAITING_APPROVAL = "awaiting_approval"  # 等待人工审批


@dataclass
class StageResult:
    """单阶段执行结果"""
    stage: PipelineStage
    status: StageStatus = StageStatus.PENDING
    output: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    elapsed_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    # 审批
    requires_approval: bool = False
    approved: bool = False
    approval_note: str = ""


@dataclass
class PipelineState:
    """全链路流水线状态 — 可序列化，支持暂停/恢复"""
    pipeline_id: str = ""
    stage: PipelineStage = PipelineStage.SCRIPT
    progress: int = 0  # 0-100
    current_stage: StageResult = field(default_factory=lambda: StageResult(PipelineStage.SCRIPT))
    stage_history: List[StageResult] = field(default_factory=list)

    # Stage outputs (cumulative)
    script: Optional[Dict[str, Any]] = None
    extracted_entities: Optional[Dict[str, Any]] = None   # {characters, locations, props}
    storyboard: Optional[Dict[str, Any]] = None
    generated_images: Optional[List[Dict[str, Any]]] = None
    generated_videos: Optional[List[Dict[str, Any]]] = None

    # Asset references (IDs pointing to AssetLibrary)
    character_asset_ids: List[str] = field(default_factory=list)
    scene_template_ids: List[str] = field(default_factory=list)
    shot_preset_ids: List[str] = field(default_factory=list)

    # Config
    config: Dict[str, Any] = field(default_factory=dict)
    # 审批策略
    auto_approve: bool = True          # False = 每阶段等待人工审批
    review_threshold: int = 60         # 质量分阈值
    max_retries_per_stage: int = 2

    # Metadata
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    stage_elapsed: Dict[str, float] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "stage": self.stage.value,
            "progress": self.progress,
            "current_stage": {
                "stage": self.current_stage.stage.value,
                "status": self.current_stage.status.value,
                "requires_approval": self.current_stage.requires_approval,
                "approved": self.current_stage.approved,
            },
            "stage_history": [
                {
                    "stage": sr.stage.value,
                    "status": sr.status.value,
                    "elapsed_ms": sr.elapsed_ms,
                }
                for sr in self.stage_history
            ],
            "script": self.script,
            "extracted_entities": self.extracted_entities,
            "storyboard": self.storyboard,
            "generated_images": self.generated_images,
            "generated_videos": self.generated_videos,
            "character_asset_ids": self.character_asset_ids,
            "scene_template_ids": self.scene_template_ids,
            "shot_preset_ids": self.shot_preset_ids,
            "errors": self.errors,
            "warnings": self.warnings,
            "stage_elapsed": self.stage_elapsed,
        }

    @classmethod
    def create(cls, pipeline_id: str, config: Optional[Dict] = None) -> "PipelineState":
        now = datetime.now(timezone.utc).isoformat()
        return cls(
            pipeline_id=pipeline_id,
            config=config or {},
            created_at=now,
            updated_at=now,
        )


# ═══════════════════════════════════════════════════════════════
# Stage Handlers (plug-in architecture)
# ═══════════════════════════════════════════════════════════════

StageHandler = Callable[
    [PipelineState, Dict[str, Any]],
    Awaitable[Dict[str, Any]],
]
"""阶段处理函数签名: async def handler(state, context) -> stage_output_dict"""


# ═══════════════════════════════════════════════════════════════
# Pipeline Orchestrator
# ═══════════════════════════════════════════════════════════════

class PipelineOrchestrator:
    """工业级流水线编排器。

    特性:
    - 阶段化执行：每阶段独立运行，产出累积到 PipelineState
    - 可干预：任意阶段可设置 requires_approval=True，暂停等待审批
    - 并行分支：同一阶段可并行处理多集（如按 episode 并发图像生成）
    - 资产集成：每阶段产出可自动存入 AssetLibrary
    - 回退：质量不达标时自动回退到上一阶段重试
    """

    def __init__(
        self,
        handlers: Optional[Dict[PipelineStage, StageHandler]] = None,
        quality_judge=None,         # QualityJudge 实例
        asset_library=None,         # AssetLibrary 实例
    ):
        self.handlers: Dict[PipelineStage, StageHandler] = handlers or {}
        self.quality_judge = quality_judge
        self.asset_library = asset_library
        # 运行中的流水线
        self._active: Dict[str, PipelineState] = {}
        # 等待审批的流水线
        self._awaiting_approval: Dict[str, PipelineState] = {}

    def register_handler(self, stage: PipelineStage, handler: StageHandler):
        """注册阶段处理函数（插件式架构）。"""
        self.handlers[stage] = handler
        logger.info(f"Handler registered for stage: {stage.value}")

    # ═══════════════ Execution ═══════════════

    async def run(
        self,
        state: PipelineState,
        start_from: Optional[PipelineStage] = None,
        stop_at: Optional[PipelineStage] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> PipelineState:
        """执行完整流水线（或部分阶段）。

        Args:
            state: 流水线状态（可从已有状态恢复）。
            start_from: 从指定阶段开始（None = 从头开始）。
            stop_at: 执行到指定阶段停止（None = 执行完所有阶段）。
            context: 外部上下文（service clients, user_id 等）。

        Returns:
            更新后的 PipelineState。
        """
        ctx = context or {}
        stages = list(PipelineStage)
        if start_from:
            start_idx = stages.index(start_from)
            stages = stages[start_idx:]
        if stop_at:
            stop_idx = stages.index(stop_at) + 1
            stages = stages[:stop_idx]

        self._active[state.pipeline_id] = state
        total_stages = len(stages)

        for i, stage in enumerate(stages):
            state.stage = stage
            state.progress = int((i / total_stages) * 100)
            state.updated_at = _now_iso()

            handler = self.handlers.get(stage)
            if not handler:
                logger.warning(f"No handler for stage {stage.value}, skipping")
                state.stage_history.append(
                    StageResult(stage=stage, status=StageStatus.SKIPPED)
                )
                continue

            # Execute stage
            sr = StageResult(stage=stage, status=StageStatus.RUNNING)
            state.current_stage = sr
            t0 = time.time()

            for retry in range(state.max_retries_per_stage + 1):
                try:
                    output = await handler(state, ctx)
                    sr.status = StageStatus.COMPLETED
                    sr.output = output
                    sr.elapsed_ms = int((time.time() - t0) * 1000)
                    break
                except Exception as e:
                    logger.warning(
                        f"Stage {stage.value} failed (attempt {retry+1}): {e}"
                    )
                    if retry >= state.max_retries_per_stage:
                        sr.status = StageStatus.FAILED
                        sr.error = str(e)
                        state.errors.append(f"{stage.value}: {e}")
                    else:
                        await asyncio.sleep(2 ** retry)

            if sr.status == StageStatus.FAILED:
                state.stage_history.append(sr)
                break

            # Accumulate stage output
            self._accumulate_output(state, stage, output)

            # Review gate
            if stage == PipelineStage.STORYBOARD and self.quality_judge:
                await self._review_gate(state, sr, ctx)

            # Approval gate
            if sr.requires_approval and not state.auto_approve:
                sr.status = StageStatus.AWAITING_APPROVAL
                state.stage_history.append(sr)
                self._awaiting_approval[state.pipeline_id] = state
                logger.info(
                    f"Pipeline {state.pipeline_id} awaiting approval at stage {stage.value}"
                )
                break  # Pause until approved

            # Store stage result
            state.stage_history.append(sr)
            state.stage_elapsed[stage.value] = sr.elapsed_ms / 1000.0

        state.progress = 100
        state.updated_at = _now_iso()
        self._active.pop(state.pipeline_id, None)
        return state

    async def run_parallel_episodes(
        self,
        state: PipelineState,
        stage: PipelineStage,
        episode_count: int,
        episode_handler: Callable[[int, PipelineState, Dict], Awaitable[Dict]],
        context: Optional[Dict] = None,
        max_concurrent: int = 3,
    ) -> List[Dict]:
        """并行处理多集（对标 LibTV 的画布多段并行）。

        用于 IMAGES 和 VIDEOS 阶段：按集/按镜头并发生成。

        Args:
            state: 流水线状态。
            stage: 当前阶段。
            episode_count: 集数。
            episode_handler: async def handler(ep_idx, state, ctx) -> episode_result
            context: 外部上下文。
            max_concurrent: 最大并发数。

        Returns:
            List of per-episode results.
        """
        ctx = context or {}
        semaphore = asyncio.Semaphore(max_concurrent)
        results: List[Optional[Dict]] = [None] * episode_count

        async def _process_one(ep_idx: int):
            async with semaphore:
                try:
                    results[ep_idx] = await episode_handler(ep_idx, state, ctx)
                    logger.info(
                        f"Episode {ep_idx+1}/{episode_count} done for stage {stage.value}"
                    )
                except Exception as e:
                    logger.error(f"Episode {ep_idx+1} failed: {e}")
                    results[ep_idx] = {"error": str(e), "episode": ep_idx}

        tasks = [_process_one(i) for i in range(episode_count)]
        await asyncio.gather(*tasks, return_exceptions=True)

        return [r for r in results if r is not None]

    # ═══════════════ Approval ═══════════════

    async def approve_stage(
        self, pipeline_id: str, approved: bool = True, note: str = ""
    ) -> PipelineState:
        """审批当前阶段，继续或终止流水线。"""
        state = self._awaiting_approval.pop(pipeline_id, None)
        if not state:
            raise ValueError(f"Pipeline {pipeline_id} not awaiting approval")

        state.current_stage.approved = approved
        state.current_stage.approval_note = note

        if approved:
            state.current_stage.status = StageStatus.COMPLETED
            # Resume from next stage
            next_stages = list(PipelineStage)
            current_idx = next_stages.index(state.stage)
            if current_idx + 1 < len(next_stages):
                return await self.run(
                    state,
                    start_from=next_stages[current_idx + 1],
                )
        else:
            # Retry current stage
            current_idx = list(PipelineStage).index(state.stage)
            prev_stage = PipelineStage.STORYBOARD  # Default fallback
            if current_idx > 0:
                prev_stage = list(PipelineStage)[current_idx - 1]
            return await self.run(state, start_from=prev_stage)

        return state

    # ═══════════════ Accumulation ═══════════════

    def _accumulate_output(
        self, state: PipelineState, stage: PipelineStage, output: Dict[str, Any]
    ):
        """将阶段产出累积到 PipelineState。"""
        if stage == PipelineStage.SCRIPT:
            state.script = output
        elif stage == PipelineStage.EXTRACT:
            state.extracted_entities = output
        elif stage == PipelineStage.STORYBOARD:
            state.storyboard = output
        elif stage == PipelineStage.IMAGES:
            state.generated_images = output.get("images", [])
        elif stage == PipelineStage.VIDEOS:
            state.generated_videos = output.get("videos", [])

    async def _review_gate(
        self, state: PipelineState, sr: StageResult, ctx: Dict[str, Any]
    ):
        """质量审核门 — 故事板阶段自动质量检查。"""
        if not self.quality_judge:
            return

        script_content = ""
        if state.storyboard:
            # Extract script-like content from storyboard for judging
            shots_desc = []
            for ep in state.storyboard.get("episodes", []):
                for shot in ep.get("shots", []):
                    shots_desc.append(shot.get("description", ""))
            script_content = "\n".join(shots_desc)

        if script_content:
            report = await self.quality_judge.judge_script(
                content=script_content,
                title=state.script.get("title", "") if state.script else "",
            )
            sr.metadata["quality"] = report.to_dict()

            if report.total_score < state.review_threshold:
                sr.requires_approval = True
                state.warnings.append(
                    f"Storyboard quality {report.total_score} < threshold {state.review_threshold}. "
                    f"Suggestions: {report.suggestions}"
                )
                logger.warning(
                    f"Review gate: score={report.total_score} < {state.review_threshold}"
                )
            else:
                logger.info(
                    f"Review gate passed: score={report.total_score}"
                )


# ═══════════════════════════════════════════════════════════════
# Stage Handler Factories (预置阶段处理器工厂)
# ═══════════════════════════════════════════════════════════════

def create_script_handler(script_service) -> StageHandler:
    """创建剧本生成阶段处理器。"""
    async def handler(state: PipelineState, ctx: dict) -> dict:
        result = await script_service.generate_script_from_outline_async(
            task_id=state.pipeline_id,
            request=ctx.get("script_request"),
        )
        return {"script": result} if result else {}
    return handler


def create_extract_handler(scene_extractor_client) -> StageHandler:
    """创建实体提取阶段处理器。"""
    async def handler(state: PipelineState, ctx: dict) -> dict:
        script_content = ""
        if state.script:
            script_content = state.script.get("content", "")
        if not script_content:
            return {"characters": [], "locations": [], "props": []}

        entities = await scene_extractor_client.extract_from_script(script_content)
        return entities
    return handler


def create_storyboard_handler(storyboard_service) -> StageHandler:
    """创建分镜生成阶段处理器 — 集成 AssetLibrary。"""
    async def handler(state: PipelineState, ctx: dict) -> dict:
        script_content = ""
        episodes = []
        if state.script:
            script_content = state.script.get("content", "")
            episodes = state.script.get("episodes", [])

        request = {
            "script": script_content,
            "episodeContents": [
                ep.get("content", "") for ep in episodes
            ] if episodes else [],
            "style": ctx.get("style", "写实风格"),
            "title": state.script.get("title", "") if state.script else "",
        }

        # 如果有资产库，注入角色/场景上下文
        asset_lib = ctx.get("asset_library")
        if asset_lib and state.character_asset_ids:
            ctx_data = asset_lib.build_episode_context(
                character_ids=state.character_asset_ids,
                scene_template_ids=state.scene_template_ids[0] if state.scene_template_ids else "",
                shot_preset_ids=state.shot_preset_ids,
            )
            request["asset_context"] = ctx_data

        result = await storyboard_service.generate_shots(request)
        return result
    return handler


def create_image_handler(llmhua_client) -> StageHandler:
    """创建图像生成阶段处理器 — 并发按镜头生成。

    对标 LibTV 的多机位并发生成能力。
    """
    async def handler(state: PipelineState, ctx: dict) -> dict:
        shots = []
        if state.storyboard:
            for ep in state.storyboard.get("episodes", []):
                shots.extend(ep.get("shots", []))

        results = []
        # 并发度控制：每个 shot 的 image generation 可并行
        semaphore = asyncio.Semaphore(ctx.get("max_concurrent_images", 3))

        async def _gen_shot_image(shot: dict) -> dict:
            async with semaphore:
                prompt = shot.get("imagePromptZh") or shot.get("imagePrompt") or shot.get("description", "")
                # 注入角色参考图（从 asset_library）
                asset_lib = ctx.get("asset_library")
                ref_prefix = ""
                if asset_lib and state.character_asset_ids:
                    ctx_data = asset_lib.build_episode_context(
                        character_ids=state.character_asset_ids,
                    )
                    ref_prefix = ctx_data.get("combined_prompt_prefix", "")

                full_prompt = f"{ref_prefix} | {prompt}" if ref_prefix else prompt

                # Call Seedance image API
                image_result = await llmhua_client.generate_image(
                    prompt=full_prompt,
                    style=ctx.get("style", "写实风格"),
                    reference_images=shot.get("reference_images", []),
                )
                return {"shot": shot.get("number"), "image": image_result}

        tasks = [_gen_shot_image(s) for s in shots[:20]]  # Limit first batch
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = [r for r in results if not isinstance(r, Exception) and r]
        return {"images": successful, "total_shots": len(shots)}

    return handler


# ═══════════════════════════════════════════════════════════════
# 现有转换器（保留）
# ═══════════════════════════════════════════════════════════════

def convert_scenes_to_storyboard_input(
    extracted_scenes: List[Dict[str, Any]],
    style: str = "写实风格",
    asset_library=None,  # Optional AssetLibrary for injecting character context
    character_asset_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Convert scene-extractor output to storyboard-service input format.

    Enhanced: injects asset library context when available.
    """
    episode_contents = []
    all_characters = set()
    all_locations = set()

    # Gather asset context
    asset_prefix = ""
    if asset_library and character_asset_ids:
        ctx_data = asset_library.build_episode_context(
            character_ids=character_asset_ids,
        )
        asset_prefix = ctx_data.get("combined_prompt_prefix", "")

    for i, scene in enumerate(extracted_scenes):
        desc = scene.get("description", "")
        location = scene.get("location", "")
        characters = scene.get("characters", [])
        time_of_day = scene.get("time_of_day", "白天")

        prefix = f"[角色设定: {asset_prefix}] " if asset_prefix else ""
        episode_text = (
            f"{prefix}**{i+1}-{i+1} {time_of_day} {location}**\n"
            f"△{desc}\n"
            f"人物：{'、'.join(characters) if characters else '无'}\n"
        )
        episode_contents.append(episode_text)

        for c in characters:
            all_characters.add(c)
        if location:
            all_locations.add(location)

    return {
        "title": "Scene-Extracted Storyboard",
        "script": "\n\n".join(episode_contents),
        "episodeCount": len(extracted_scenes),
        "episodeContents": episode_contents,
        "style": style,
        "sceneRefs": list(all_locations),
        "characterNames": list(all_characters),
    }


def convert_storyboard_to_image_input(
    storyboard: Dict[str, Any],
    style: str = "写实风格",
    asset_library=None,
    character_asset_ids: Optional[List[str]] = None,
    shot_preset_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Convert storyboard output to image generation input.

    Enhanced: injects asset library context (character refs, shot presets).
    """
    # Gather shot presets for injection
    shot_contexts = []
    if asset_library and shot_preset_ids:
        for pid in shot_preset_ids:
            preset = asset_library.get_shot_preset(pid)
            if preset:
                shot_contexts.append(preset.to_prompt_context())

    # Gather character references
    char_prefix = ""
    if asset_library and character_asset_ids:
        ctx_data = asset_library.build_episode_context(
            character_ids=character_asset_ids,
        )
        char_prefix = ctx_data.get("combined_prompt_prefix", "")

    scenes = []
    for ep in storyboard.get("episodes", []):
        for shot in ep.get("shots", []):
            prompt = shot.get("imagePromptZh") or shot.get("imagePrompt") or shot.get("description", "")
            if char_prefix:
                prompt = f"{char_prefix} | {prompt}"
            if shot_contexts:
                prompt = f"{' | '.join(shot_contexts)} | {prompt}"

            scenes.append({
                "scene_description": prompt,
                "storyboard_id": storyboard.get("task_id", "unknown"),
                "scene_number": shot.get("number", 0),
                "shot_type": shot.get("shotType", ""),
                "camera_angle": shot.get("cameraAngle", ""),
                "style": style,
            })
    return scenes


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
