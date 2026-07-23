"""
角色一致性引擎 v2 — 对标巨日禄 <3% 误差 + Sudowrite Story Bible。

跨多集剧本的角色一致性是短剧 AI 生成的头号痛点。
当前 V2 pipeline: 每章独立的 RAG 检索 → 角色描述可能因 LLM 随机性而漂移。

v2 方案:
1. 全局角色汇总 → 特征锁定（外貌锁/性格锁/对白锁）
2. 每章生成时强制注入锁定后的角色档案
3. 跨章一致性校验（QualityJudge character_consistency 维度）
4. 不达标 → 自动重写该章
"""
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════

@dataclass
class CharacterLock:
    """角色特征锁 — 在生成过程中不可变"""
    name: str
    role: str = "配角"                      # 主角/配角/反派

    # 外貌锁 — 视觉一致性
    appearance: str = ""                    # 核心外貌: 年龄/体型/脸型/发型/标志特征
    clothing: str = ""                      # 服装: 常穿什么
    distinctive_marks: List[str] = field(default_factory=list)  # 辨识特征: ["左眼角泪痣", "银色长发"]

    # 性格锁 — 行为一致性
    personality: str = ""                   # 核心性格: 三个词 + 一句话
    speech_style: str = ""                 # 说话风格: 用词习惯/句式/口头禅
    behavioral_rules: List[str] = field(default_factory=list)  # 行为规则: ["从不先动手", "对老人孩子格外温柔"]

    # 对白锁 — 语言一致性
    dialogue_traits: str = ""              # 对白特征: "简洁、克制、偶尔冷幽默"
    common_phrases: List[str] = field(default_factory=list)  # 口头禅: ["啧", "无所谓", "随便你"]
    forbidden_phrases: List[str] = field(default_factory=list)  # 绝不会说的话: ["我爱你"（前期）]

    # 关系锁
    relationships: Dict[str, str] = field(default_factory=dict)
    # {"沈惊澜": "前世为她而死的魔尊，今生最信任的人",
    #  "苏云锦": "表面温柔的师姐，前世背叛主谋之一"}

    # 弧光锁 — 角色成长
    arc_summary: str = ""                   # "从清冷疏离到学会信任，从独自复仇到为爱守护"
    arc_milestones: Dict[int, str] = field(default_factory=dict)
    # {6: "第一次主动求助", 12: "开始信任沈惊澜", 18: "为沈惊澜放弃复仇机会"}

    # 视觉提示
    seedance_prompt_hint: str = ""          # 给 Seedance 的视觉提示: "female, 15yo, white robe, tear mole, silver hair"

    def to_prompt_context(self) -> str:
        """生成注入到 LLM prompt 的角色约束上下文。

        这个上下文会被注入到每章剧本生成的 system prompt 中，
        确保 LLM 在所有章节中保持角色一致。
        """
        parts = [f"【角色锁定: {self.name}（{self.role}）】"]

        if self.appearance:
            parts.append(f"外貌: {self.appearance}")
        if self.clothing:
            parts.append(f"服装: {self.clothing}")
        if self.distinctive_marks:
            parts.append(f"辨识特征: {', '.join(self.distinctive_marks)}")

        if self.personality:
            parts.append(f"性格: {self.personality}")
        if self.behavioral_rules:
            parts.append(f"行为规则: {'; '.join(self.behavioral_rules)}")

        if self.speech_style:
            parts.append(f"说话风格: {self.speech_style}")
        if self.dialogue_traits:
            parts.append(f"对白特征: {self.dialogue_traits}")
        if self.common_phrases:
            parts.append(f"口头禅: {', '.join(self.common_phrases)}")
        if self.forbidden_phrases:
            parts.append(f"绝对不能说: {', '.join(self.forbidden_phrases)}")

        if self.relationships:
            rel_str = '; '.join(f"{k}: {v}" for k, v in self.relationships.items())
            parts.append(f"关系: {rel_str}")

        if self.arc_summary:
            parts.append(f"角色弧光: {self.arc_summary}")

        return "\n".join(parts)

    def to_compact_context(self) -> str:
        """紧凑版上下文 — 用于每章生成时的简短提醒。"""
        parts = [
            f"{self.name}: {self.appearance[:60]}",
            f"性格: {self.personality[:60]}" if self.personality else "",
            f"对白: {self.dialogue_traits[:60]}" if self.dialogue_traits else "",
        ]
        return " | ".join(p for p in parts if p)


@dataclass
class ConsistencyReport:
    """角色一致性校验报告"""
    character_name: str
    checked_chapters: List[int] = field(default_factory=list)
    violations: List[Dict[str, Any]] = field(default_factory=list)
    # [{"chapter": 5, "violation": "外貌飘逸: 左眼角泪痣未提及", "severity": "medium"}, ...]
    overall_score: int = 100       # 0-100，越高越一致
    needs_rewrite: bool = False
    rewrite_suggestions: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# CharacterConsistencyEngine
# ═══════════════════════════════════════════════════════════════

class CharacterConsistencyEngine:
    """角色一致性引擎 — 在 V2 pipeline 的每章生成前后介入。"""

    def __init__(self, quality_judge=None):
        self._locks: Dict[str, CharacterLock] = {}
        self._judge = quality_judge

    # ═══════════════ Lock Management ═══════════════

    def lock_character(self, lock: CharacterLock):
        """锁定一个角色的特征。"""
        self._locks[lock.name] = lock
        logger.info(f"Character locked: {lock.name} ({lock.role}) — "
                    f"{len(lock.distinctive_marks)} marks, "
                    f"{len(lock.behavioral_rules)} rules, "
                    f"{len(lock.arc_milestones)} arc milestones")

    def lock_from_extraction(
        self, characters: List[Dict[str, Any]], arc_milestones: Optional[Dict[str, Dict[int, str]]] = None
    ):
        """从 V2 pipeline 的全局角色提取结果批量锁定。

        Args:
            characters: V2 GlobalCharacter 列表
            arc_milestones: 可选的角色弧光里程碑 {角色名: {集号: 描述}}
        """
        for char in characters:
            lock = CharacterLock(
                name=char.get("name", ""),
                role=char.get("role", char.get("role_type", "配角")),
                appearance=char.get("appearance", char.get("description", "")),
                clothing=char.get("clothing", ""),
                distinctive_marks=char.get("distinctive_features", char.get("distinctive_marks", [])),
                personality=char.get("personality", ""),
                speech_style=char.get("speech_style", ""),
                dialogue_traits=char.get("dialogue_traits", ""),
                relationships=char.get("relationships", {}),
            )
            if arc_milestones and char["name"] in arc_milestones:
                lock.arc_milestones = arc_milestones[char["name"]]
                lock.arc_summary = self._build_arc_summary(
                    char["name"], arc_milestones[char["name"]]
                )
            self.lock_character(lock)

    def get_lock(self, name: str) -> Optional[CharacterLock]:
        return self._locks.get(name)

    def get_all_locks(self) -> List[CharacterLock]:
        return list(self._locks.values())

    # ═══════════════ Chapter-Level Injection ═══════════════

    def build_chapter_context(
        self,
        chapter_num: int,
        characters_in_scene: List[str],
        compact: bool = False,
    ) -> str:
        """构建单章的角色一致性约束上下文。

        在生成每章剧本前调用，将角色锁定信息注入 prompt。

        Args:
            chapter_num: 当前章节号
            characters_in_scene: 当前场景中出现的角色名列表
            compact: 是否使用紧凑格式

        Returns:
            注入到 system prompt 的角色约束文本
        """
        parts = []

        for name in characters_in_scene:
            lock = self._locks.get(name)
            if not lock:
                continue

            if compact:
                parts.append(lock.to_compact_context())
            else:
                parts.append(lock.to_prompt_context())

            # 注入弧光里程碑（如果当前章节是关键转折点）
            if chapter_num in lock.arc_milestones:
                milestone = lock.arc_milestones[chapter_num]
                parts.append(f"  ⚠ 角色弧光里程碑（第{chapter_num}集）: {milestone}")

        if parts:
            header = (
                "\n【角色一致性约束 — 必须严格遵守】\n"
                "以下角色特征在整部剧中保持不变。请在生成对白、描写行为时严格参考。\n\n"
            )
            return header + "\n\n".join(parts)
        return ""

    def build_global_context(self, compact: bool = True) -> str:
        """构建全剧角色约束上下文 — 注入到全局 system prompt。"""
        if not self._locks:
            return ""

        parts = ["\n【全剧角色锁定 — 所有章节通用】\n"]
        for lock in self._locks.values():
            if compact:
                parts.append(f"- {lock.to_compact_context()}")
            else:
                parts.append(lock.to_prompt_context())
                parts.append("---")
        return "\n".join(parts)

    # ═══════════════ Consistency Validation ═══════════════

    async def validate_chapter(
        self, chapter_num: int, chapter_content: str, characters: List[str]
    ) -> Dict[str, ConsistencyReport]:
        """校验单章的角色一致性。

        使用 QualityJudge 的 character_consistency 维度 + 规则检查。

        Args:
            chapter_num: 章节号
            chapter_content: 该章剧本内容
            characters: 该章出现的角色名列表

        Returns:
            {角色名: ConsistencyReport}
        """
        reports = {}

        for name in characters:
            lock = self._locks.get(name)
            if not lock:
                continue

            report = ConsistencyReport(
                character_name=name,
                checked_chapters=[chapter_num],
            )

            # Rule-based checks
            violations = self._rule_check(lock, chapter_content)
            report.violations = violations

            # Score: each violation deducts 5-15 points
            severity_penalty = {"low": 5, "medium": 10, "high": 15}
            for v in violations:
                report.overall_score -= severity_penalty.get(v.get("severity", "low"), 5)
            report.overall_score = max(0, report.overall_score)

            if report.overall_score < 70:
                report.needs_rewrite = True
                report.rewrite_suggestions = [
                    f"请确保{name}在第{chapter_num}集中: {v['violation']}"
                    for v in violations
                ]

            reports[name] = report

        # LLM-based check (if judge available)
        if self._judge:
            try:
                judge_report = await self._judge.judge_script(
                    content=chapter_content,
                    max_chars=4000,
                )
                char_score = judge_report.scores.get("character_consistency", 100)
                # Distribute the judge's score to all character reports
                for name in characters:
                    if name in reports:
                        reports[name].overall_score = min(
                            reports[name].overall_score, char_score
                        )
                        if char_score < 50:
                            reports[name].needs_rewrite = True
                            reports[name].rewrite_suggestions.append(
                                f"QualityJudge评分: 角色一致性={char_score}/100，建议重写"
                            )
            except Exception as e:
                logger.warning(f"Character consistency LLM check failed: {e}")

        return reports

    # ═══════════════ Helpers ═══════════════

    def _rule_check(self, lock: CharacterLock, content: str) -> List[Dict[str, Any]]:
        """基于规则的快速一致性检查。"""
        violations = []

        # Check distinctive marks
        for mark in lock.distinctive_marks:
            # Simple keyword check — in production, use NLP NER + coreference resolution
            if not any(kw in content for kw in mark.split()[:2]):
                violations.append({
                    "violation": f"辨识特征'{mark}'未在文本中体现",
                    "severity": "medium",
                })

        # Check forbidden phrases
        for phrase in lock.forbidden_phrases:
            if phrase in content and lock.name in content:
                violations.append({
                    "violation": f"角色说了不该说的话: '{phrase}'",
                    "severity": "high",
                })

        # Check common phrases (should appear at least once if character has dialogue)
        if lock.common_phrases and lock.name + "：" in content:
            found_any = any(phrase in content for phrase in lock.common_phrases)
            if not found_any:
                violations.append({
                    "violation": f"口头禅未出现: {', '.join(lock.common_phrases[:2])}",
                    "severity": "low",
                })

        return violations

    @staticmethod
    def _build_arc_summary(name: str, milestones: Dict[int, str]) -> str:
        sorted_ms = sorted(milestones.items())
        stages = [f"第{k}集: {v}" for k, v in sorted_ms]
        return f"{name}的角色弧光: {' → '.join(stages)}"


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════

def create_consistency_engine(quality_judge=None) -> CharacterConsistencyEngine:
    """Create a CharacterConsistencyEngine with optional QualityJudge integration."""
    engine = CharacterConsistencyEngine(quality_judge=quality_judge)

    # Pre-populate with common short drama archetype locks
    _preset_locks = [
        CharacterLock(
            name="顾清寒", role="主角",
            appearance="女，15岁，清冷面容，白色长袍，银色长发及腰，左眼角有极小泪痣",
            clothing="白色长袍，腰间束一条青色丝带，袖口绣有暗纹",
            distinctive_marks=["左眼角泪痣", "银色长发", "手指修长适合炼丹"],
            personality="外表清冷，内心重情。前世被背叛后极度警惕，但一旦信任会全力付出。",
            speech_style="简洁、克制、不废话。愤怒时不吼叫，而是用冰冷语调说最狠的话。",
            dialogue_traits="话少但精准，每句话都有信息量。对敌人:冷嘲热讽。对信任的人:简短但温暖。",
            common_phrases=["啧", "随便你", "无所谓"],
            forbidden_phrases=["求求你", "我不能没有你"],
            relationships={
                "沈惊澜": "前世为她而死，今生最信任的人——但内心害怕再次失去",
                "苏云锦": "前世背叛她的师姐，此生最痛恨的人",
            },
            arc_summary="从独自复仇到学会信任，从利用沈惊澜到真心相爱",
            arc_milestones={1: "重生，发誓复仇", 6: "第一次向沈惊澜求助",
                             12: "发现自己爱上了沈惊澜", 18: "为沈惊澜放弃复仇计划",
                             24: "复仇完成，选择与沈惊澜共度余生"},
        ),
        CharacterLock(
            name="沈惊澜", role="主角",
            appearance="男，约20岁外表，英俊但带邪气，黑色长袍，红色瞳孔（魔尊特征），右脸有细小疤痕",
            clothing="黑色长袍滚金边，腰间佩剑'惊澜'，偶尔穿暗红长衫",
            distinctive_marks=["红色瞳孔", "右脸细小疤痕", "左手戴一枚黑色戒指"],
            personality="对外冷酷，对顾清寒温柔到极致。有些独占欲，但克制自己不过度干涉。",
            speech_style="对外人:简洁冰冷。对顾清寒:温柔，偶尔带点调戏。盛怒时暴虐外露。",
            dialogue_traits="对外人话极少，对顾清寒会说情话但不肉麻——行动比语言多。",
            common_phrases=["随你", "我在", "别怕"],
            forbidden_phrases=["我不在乎你", "你走吧"],
        ),
        CharacterLock(
            name="苏云锦", role="反派",
            appearance="女，外表约18岁，温柔可亲，鹅蛋脸，粉色长裙，笑起来有两个酒窝——极具欺骗性",
            clothing="粉色系长裙，发间插一支白玉簪（前世是顾清寒送的）",
            distinctive_marks=["酒窝", "白玉簪"],
            personality="表面温柔，实则嫉妒成性。极度在乎他人评价，不能容忍有人比自己优秀。",
            speech_style="对大部分人:温声细语。对顾清寒:表面关心实则打压。翻脸时:尖酸刻薄。",
            dialogue_traits="总是用'我都是为你好'包装恶意。喜欢用问句——'你不觉得你应该...吗？'",
            common_phrases=["我都是为你好", "你不会怪我吧", "其实我也不想的"],
            forbidden_phrases=["我就是嫉妒你"],
        ),
    ]
    for lock in _preset_locks:
        engine.lock_character(lock)

    logger.info(f"ConsistencyEngine initialized with {len(engine.get_all_locks())} preset locks")
    return engine
