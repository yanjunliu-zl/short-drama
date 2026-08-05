"""
短剧情节结构模板 — 行业验证的"爽点节奏"编码。

每种短剧类型有经过市场验证的集级结构：
- 哪集该出现什么类型的情节
- 钩子放哪里
- 付费点放哪里
- 感情线 vs 事业线的比例

对标: Scrite 的 Save the Cat beat sheet + 创一 AI 的结构化流程

核心洞察: 短剧不是"自由创作"，而是"在严格结构中填内容"。
AI 随机发挥 → 可用率 30%；按模板填充 → 可用率 70%+。
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════

class BeatType(str, Enum):
    """情节节拍类型"""
    HOOK = "hook"                # 开篇钩子 — 必须在前 3 秒抓住用户
    SETUP = "setup"              # 建立世界观/人物关系
    CONFLICT = "conflict"        # 冲突升级
    REVERSAL = "reversal"        # 反转 — 用户预期被打破
    REVEAL = "reveal"            # 信息揭露 — 观众知道但角色不知道
    PAYWALL = "paywall"          # 付费点 — 卡在最想知道答案的地方
    CLIMAX = "climax"            # 阶段高潮
    ROMANCE = "romance"          # 感情线推进
    ACTION = "action"            # 动作/打斗场景
    EMOTIONAL = "emotional"      # 情感高潮
    RECOVERY = "recovery"        # 主角从低谷反弹
    TRAP = "trap"                # 主角设局/布局
    BETRAYAL = "betrayal"        # 背叛
    CLIFFHANGER = "cliffhanger"  # 悬念结尾


@dataclass
class EpisodeBeat:
    """单集节拍"""
    episode: int                       # 集号
    title_hint: str = ""               # 标题提示（如 "重生归来"）
    primary_beat: BeatType = BeatType.SETUP
    secondary_beats: List[BeatType] = field(default_factory=list)
    description: str = ""              # 该集应该发生什么
    cliffhanger: str = ""              # 该集的钩子
    dialogue_ratio: float = 0.45       # 对白占比（0-1）
    character_focus: List[str] = field(default_factory=list)  # 该集重点角色
    paywall: bool = False              # 是否为付费卡点


@dataclass
class PlotTemplate:
    """完整的情节模板"""
    template_id: str
    genre: str                         # 类型名称
    genre_cn: str                      # 中文类型名
    description: str
    total_episodes: int
    episodes: List[EpisodeBeat] = field(default_factory=list)

    # 角色原型
    character_archetypes: Dict[str, str] = field(default_factory=dict)
    # {"男主": "复仇者/霸总/战神", "女主": "重生者/灰姑娘/女强人"}

    # 通用设定
    common_settings: List[str] = field(default_factory=list)
    common_themes: List[str] = field(default_factory=list)

    # 节奏参数
    hook_intensity: str = "高"          # 钩子强度: 高/中/低
    reversal_frequency: str = "每5集"   # 反转频率
    romance_ratio: float = 0.3          # 感情线占比

    def to_prompt_context(self) -> str:
        """生成注入到 LLM prompt 的模板上下文。"""
        lines = [
            f"【剧本类型】{self.genre_cn}",
            f"【总集数】{self.total_episodes}集",
            f"【节奏要求】钩子强度={self.hook_intensity}，反转频率={self.reversal_frequency}，感情线占比={int(self.romance_ratio*100)}%",
            "",
            "【分集结构（严格遵循）】",
        ]
        for ep in self.episodes:
            paywall_mark = " 🔒付费点" if ep.paywall else ""
            focus = f" 重点角色: {', '.join(ep.character_focus)}" if ep.character_focus else ""
            lines.append(
                f"第{ep.episode}集「{ep.title_hint}」: {ep.description}"
                f" | 结尾钩子: {ep.cliffhanger}{paywall_mark}{focus}"
            )
        return "\n".join(lines)

    def get_episode(self, num: int) -> Optional[EpisodeBeat]:
        for ep in self.episodes:
            if ep.episode == num:
                return ep
        return None

    def get_paywall_positions(self) -> List[int]:
        return [ep.episode for ep in self.episodes if ep.paywall]


# ═══════════════════════════════════════════════════════════════
# 10+ 预置模板（基于 2025-2026 红果/快手/DramaBox 爆款分析）
# ═══════════════════════════════════════════════════════════════

PLOT_TEMPLATES: Dict[str, PlotTemplate] = {}

# ── 1. 重生复仇（最热门类型，占短剧 30%+） ──

PLOT_TEMPLATES["rebirth_revenge"] = PlotTemplate(
    template_id="rebirth_revenge",
    genre="Rebirth Revenge",
    genre_cn="重生复仇",
    description="主角重生回到过去，利用前世记忆复仇逆袭。核心爽点：'我知道你不知道的事'的信息差优势。",
    total_episodes=24,
    hook_intensity="极高",
    reversal_frequency="每3-4集",
    romance_ratio=0.25,
    character_archetypes={
        "男主": "前世被背叛而死，重生后步步为营 / 前世为救女主而死，重生后默默守护",
        "女主": "前世被渣男/闺蜜/宗门联手害死，重生后复仇 + 事业双线",
        "反派": "前世背叛主谋（师姐/闺蜜/合作伙伴），表面善良实则嫉妒成性",
    },
    common_settings=["修真世界/古代宫廷/现代都市（取决于子类型）"],
    common_themes=["复仇", "逆袭", "甜宠", "事业线"],
    episodes=[
        EpisodeBeat(1, "重生归来", BeatType.HOOK,
                    description="主角死亡+重生瞬间。闪回前世关键背叛画面。建立'我要改变一切'的核心动机。",
                    cliffhanger="'这一次，我要让所有人付出代价。'——主角发现重生的时间点恰好是命运转折的关键时刻。",
                    dialogue_ratio=0.3, character_focus=["主角"]),
        EpisodeBeat(2, "前世记忆", BeatType.SETUP,
                    description="利用前世记忆避开第一个陷阱。展示主角的前世知识优势。",
                    cliffhanger="意外遇到前世的关键人物——但这个人前世应该已经死了。",
                    dialogue_ratio=0.4, character_focus=["主角"]),
        EpisodeBeat(3, "初露锋芒", BeatType.REVERSAL,
                    description="第一次小胜利——主角利用前世记忆获得第一个优势（资源/人脉/能力）。",
                    cliffhanger="胜利的喜悦被一个细节打破——有人似乎也记得前世的事？",
                    dialogue_ratio=0.4, character_focus=["主角", "反派"]),
        EpisodeBeat(4, "建立盟友", BeatType.SETUP,
                    description="结识前世最重要的盟友。展示主角如何用前世知识赢得信任。",
                    cliffhanger="盟友对主角说了一句前世绝对不会说的话——蝴蝶效应已经开始。",
                    dialogue_ratio=0.5, character_focus=["主角", "盟友"]),
        EpisodeBeat(5, "布局开始", BeatType.TRAP,
                    description="主角开始布第一个局，目标是第一个背叛者。",
                    cliffhanger="布局即将完成时，反派似乎察觉到了什么。",
                    dialogue_ratio=0.4, character_focus=["主角", "反派"]),
        EpisodeBeat(6, "第一次交锋", BeatType.CONFLICT,
                    description="主角与反派的第一次正面对抗。主角赢，但赢得不轻松。",
                    cliffhanger="反派留下一句话：'你以为只有你知道未来吗？'",
                    dialogue_ratio=0.45, character_focus=["主角", "反派"]),
        EpisodeBeat(7, "感情萌芽", BeatType.ROMANCE,
                    description="与官配的感情线开始推进。主角在复仇的同时感受到久违的温暖。",
                    cliffhanger="官配的一个举动让主角回忆起前世——前世这个人是怎么死的？",
                    dialogue_ratio=0.55, character_focus=["主角", "官配"]),
        EpisodeBeat(8, "暗流涌动", BeatType.REVEAL,
                    description="发现反派背后还有更大的势力。复仇不能只针对表面敌人。",
                    cliffhanger="主角在前世记忆中翻找——这个人不止背叛了我一次。",
                    dialogue_ratio=0.4, character_focus=["主角"]),
        EpisodeBeat(9, "扩大优势", BeatType.ACTION,
                    description="利用前世记忆获取关键资源（秘籍/专利/内幕消息）。事业线上升。",
                    cliffhanger="资源到手了，但引来了新的敌人。",
                    dialogue_ratio=0.3, character_focus=["主角"]),
        EpisodeBeat(10, "付费点", BeatType.PAYWALL,
                    description="看似一切顺利时，反派发动总攻。主角陷入最大危机。",
                    cliffhanger="主角发现自己的前世记忆开始出现偏差——蝴蝶效应已经改变了太多。'如果未来不再可预测，我还能赢吗？'",
                    dialogue_ratio=0.4, character_focus=["主角", "反派"], paywall=True),
        EpisodeBeat(11, "崩溃与重建", BeatType.EMOTIONAL,
                    description="主角在低谷中重新审视自己的目标。前世记忆不是万能的。",
                    cliffhanger="在一个意想不到的地方找到了突破口。",
                    dialogue_ratio=0.5, character_focus=["主角", "官配"]),
        EpisodeBeat(12, "中点反转", BeatType.REVERSAL,
                    description="重大反转——发现最信任的人也参与过前世的背叛。或者发现最大的敌人其实是前世的爱人。",
                    cliffhanger="'原来你也是他们的人。'——这个反转必须让观众震惊。",
                    dialogue_ratio=0.45, character_focus=["主角", "盟友/官配"]),
        EpisodeBeat(13, "重新集结", BeatType.RECOVERY,
                    description="主角从打击中恢复，重新集结力量。不再依赖前世记忆，开始用真正的智慧布局。",
                    cliffhanger="一个全新的计划开始成型——这次不是依靠记忆，而是依靠成长。",
                    dialogue_ratio=0.4, character_focus=["主角"]),
        EpisodeBeat(14, "反击开始", BeatType.ACTION,
                    description="主角的新计划开始实施。第一阶段的复仇接近完成。",
                    cliffhanger="复仇即将完成，但主角发现自己并没有想象中的快乐。",
                    dialogue_ratio=0.4, character_focus=["主角", "反派"]),
        EpisodeBeat(15, "感情升温", BeatType.ROMANCE,
                    description="与官配的感情进入实质性阶段。感情线成为复仇之外的另一条主线。",
                    cliffhanger="官配发现了主角的秘密——'原来你一直都知道未来？'",
                    dialogue_ratio=0.6, character_focus=["主角", "官配"]),
        EpisodeBeat(16, "更大的阴谋", BeatType.REVEAL,
                    description="发现复仇只是冰山一角。背后的势力远比想象中强大。",
                    cliffhanger="主角意识到：如果只复仇，赢了也没有意义。需要改变整个格局。",
                    dialogue_ratio=0.4, character_focus=["主角"]),
        EpisodeBeat(17, "联盟扩大", BeatType.SETUP,
                    description="联合更多力量。前世分散的势力被主角凝聚起来。",
                    cliffhanger="新的联盟中潜伏着新的危险。",
                    dialogue_ratio=0.45, character_focus=["主角", "新角色"]),
        EpisodeBeat(18, "决战前夜", BeatType.CONFLICT,
                    description="与反派势力的大规模对抗。高潮前奏。",
                    cliffhanger="一切准备就绪，但主角收到一条消息：'如果你赢了，她/他会死。'",
                    dialogue_ratio=0.4, character_focus=["主角"]),
        EpisodeBeat(19, "生死抉择", BeatType.EMOTIONAL,
                    description="主角面临复仇与守护之间的选择。",
                    cliffhanger="主角做出了选择——这个选择让所有人都意外。",
                    dialogue_ratio=0.5, character_focus=["主角", "官配"]),
        EpisodeBeat(20, "付费点", BeatType.PAYWALL,
                    description="最终决战第一阶段。主角的优势化为乌有，所有人命悬一线。",
                    cliffhanger="在最绝望的时刻，前世那个为保护主角而死的人——出现了。'我说过，我会一直在。'",
                    dialogue_ratio=0.35, character_focus=["主角", "官配", "反派"], paywall=True),
        EpisodeBeat(21, "逆转战局", BeatType.CLIMAX,
                    description="决战高潮。主角用智慧和力量打破困局。",
                    cliffhanger="胜利在望，但代价是什么？",
                    dialogue_ratio=0.3, character_focus=["主角", "反派"]),
        EpisodeBeat(22, "复仇完成", BeatType.REVERSAL,
                    description="阶段性复仇完成。大反派受到应有的惩罚。",
                    cliffhanger="复仇完成了，但主角发现了新的线索——真正的幕后黑手另有其人。",
                    dialogue_ratio=0.4, character_focus=["主角"]),
        EpisodeBeat(23, "情感归宿", BeatType.ROMANCE,
                    description="感情线收束。在经历一切后，主角和官配的感情得到升华。",
                    cliffhanger="平静的生活中，一个新的神秘人物出现。",
                    dialogue_ratio=0.55, character_focus=["主角", "官配"]),
        EpisodeBeat(24, "新篇章", BeatType.CLIFFHANGER,
                    description="阶段性结局。复仇完成、感情稳固、事业有成。但更大的世界刚刚打开。",
                    cliffhanger="第二季伏笔：'你以为结束了？这个世界远比你想象的复杂。'",
                    dialogue_ratio=0.45, character_focus=["主角"]),
    ],
)

# ── 2. 霸总甜宠 ──

PLOT_TEMPLATES["ceo_romance"] = PlotTemplate(
    template_id="ceo_romance",
    genre="CEO Romance",
    genre_cn="霸总甜宠",
    description="霸道总裁与普通女孩的甜蜜爱情。核心爽点：权力不对等下的真心打动。",
    total_episodes=20,
    hook_intensity="中",
    reversal_frequency="每5集",
    romance_ratio=0.6,
    character_archetypes={
        "男主": "高冷霸总 / 亿万富豪继承人 / 表面冷酷实则温柔",
        "女主": "普通但坚强的女孩 / 实习生/小职员/单亲妈妈 / 善良但不傻白甜",
        "反派": "心机女二 / 商业对手 / 家族安排的政治联姻对象",
    },
    common_settings=["现代都市", "集团总部", "高档公寓", "度假海岛"],
    common_themes=["甜宠", "先婚后爱", "契约恋爱", "追妻火葬场"],
    episodes=[
        EpisodeBeat(1, "命运相遇", BeatType.HOOK,
                    description="男女主第一次相遇——误会/意外/被迫结合。男主冷漠，女主不屈。",
                    cliffhanger="'从今天起，你就是我的契约妻子。'",
                    dialogue_ratio=0.45, character_focus=["男主", "女主"]),
        EpisodeBeat(2, "被迫同居", BeatType.SETUP,
                    description="因契约/误会/工作需要住到一起。展示性格差异和日常冲突。",
                    cliffhanger="女主发现男主的一个不为人知的柔软面。",
                    dialogue_ratio=0.5, character_focus=["男主", "女主"]),
        EpisodeBeat(3, "初次心动", BeatType.ROMANCE,
                    description="男主在某个关键时刻出手相助。女主第一次感觉到'他好像不是那么冷'。",
                    cliffhanger="男主在女主看不到的地方，做出了保护她的举动。但被女二看到了。",
                    dialogue_ratio=0.5, character_focus=["男主", "女主"]),
        EpisodeBeat(4, "女二搅局", BeatType.CONFLICT,
                    description="女二出现，制造误会。女主以为男主有心上人。",
                    cliffhanger="女主决定离开——'既然你有喜欢的人，这个契约就到此为止。'",
                    dialogue_ratio=0.5, character_focus=["女主", "女二"]),
        EpisodeBeat(5, "追妻开始", BeatType.REVERSAL,
                    description="男主发现自己不能失去女主。开始放下身段追求。",
                    cliffhanger="男主当众表白——这是霸道总裁从未做过的事。",
                    dialogue_ratio=0.5, character_focus=["男主", "女主"]),
        EpisodeBeat(6, "甜蜜升温", BeatType.ROMANCE,
                    description="感情进入甜蜜期。日常发糖。",
                    cliffhanger="甜蜜背后，一个商业阴谋正在酝酿。",
                    dialogue_ratio=0.55, character_focus=["男主", "女主"]),
        EpisodeBeat(7, "事业危机", BeatType.CONFLICT,
                    description="男主的公司/家族遭遇商业危机。女主发现危机可能和自己有关。",
                    cliffhanger="'跟我在一起，你的事业会毁掉的。'——女主的内疚 vs 男主的坚持。",
                    dialogue_ratio=0.45, character_focus=["男主", "女主"]),
        EpisodeBeat(8, "不离不弃", BeatType.EMOTIONAL,
                    description="危机中女主展现能力和忠诚。两人并肩作战。",
                    cliffhanger="危机似乎解决了——但这是暴风雨前的宁静。",
                    dialogue_ratio=0.5, character_focus=["男主", "女主"]),
        EpisodeBeat(9, "家族反对", BeatType.CONFLICT,
                    description="男主家族/母亲出现，要求男主与门当户对的人结婚。",
                    cliffhanger="'你是要这个女人，还是要这个家？'",
                    dialogue_ratio=0.45, character_focus=["男主", "女主", "家族"]),
        EpisodeBeat(10, "付费点", BeatType.PAYWALL,
                    description="男主为女主放弃了家族继承权。女主不忍心，选择主动离开。",
                    cliffhanger="女主留下分手信离开。男主看到信的那一刻——'你以为这样就能保护我吗？'",
                    dialogue_ratio=0.5, character_focus=["男主", "女主"], paywall=True),
        EpisodeBeat(11, "各自成长", BeatType.RECOVERY,
                    description="分手后两人各自成长。女主事业起飞，男主解决家族问题。",
                    cliffhanger="两条平行线开始有了交集的可能。",
                    dialogue_ratio=0.4, character_focus=["女主"]),
        EpisodeBeat(12, "重新相遇", BeatType.ROMANCE,
                    description="重逢。两人都变了，但心没变。",
                    cliffhanger="'这一次，换我来追你。'——女主不再是那个被动的女孩。",
                    dialogue_ratio=0.55, character_focus=["男主", "女主"]),
        EpisodeBeat(13, "第二次追求", BeatType.ROMANCE,
                    description="女主反过来追求男主。角色对调的甜蜜感。",
                    cliffhanger="男主被感动——但他心里还有一个秘密没有告诉女主。",
                    dialogue_ratio=0.6, character_focus=["男主", "女主"]),
        EpisodeBeat(14, "秘密揭晓", BeatType.REVEAL,
                    description="男主当年的选择真相揭晓——他为女主做的比女主知道的更多。",
                    cliffhanger="'你为我做了这么多，为什么不告诉我？'",
                    dialogue_ratio=0.5, character_focus=["男主", "女主"]),
        EpisodeBeat(15, "终成眷属", BeatType.CLIMAX,
                    description="所有障碍解除。双方家庭认可。感情修成正果。",
                    cliffhanger="盛大的婚礼/求婚。但最后一个问题——前女二会善罢甘休吗？",
                    dialogue_ratio=0.5, character_focus=["男主", "女主"]),
        EpisodeBeat(16, "婚后生活", BeatType.ROMANCE,
                    description="婚后甜蜜日常。事业上的新挑战。",
                    cliffhanger="女主怀孕了——但公司面临最大的危机。",
                    dialogue_ratio=0.55, character_focus=["男主", "女主"]),
        EpisodeBeat(17, "最后考验", BeatType.CONFLICT,
                    description="旧敌卷土重来。男主必须在事业和家庭间找到平衡。",
                    cliffhanger="'我不会让你一个人面对的。'——怀孕的女主站在男主身边。",
                    dialogue_ratio=0.45, character_focus=["男主", "女主"]),
        EpisodeBeat(18, "联手破局", BeatType.ACTION,
                    description="夫妻联手解决最终问题。",
                    cliffhanger="所有敌人都被解决了。新生活开始。",
                    dialogue_ratio=0.4, character_focus=["男主", "女主"]),
        EpisodeBeat(19, "圆满结局", BeatType.EMOTIONAL,
                    description="孩子出生/事业成功/家庭和睦。一切圆满。",
                    cliffhanger="女主的最后一句独白——对这段旅程的感悟。",
                    dialogue_ratio=0.55, character_focus=["女主"]),
        EpisodeBeat(20, "番外", BeatType.ROMANCE,
                    description="婚后番外/平行世界/孩子视角的彩蛋。",
                    cliffhanger="'这就是爱情最好的样子。'（如果要做第二季，这里可以埋伏笔）",
                    dialogue_ratio=0.5, character_focus=["男主", "女主", "孩子"]),
    ],
)

# ── 3. 悬疑反转 ──

PLOT_TEMPLATES["mystery_thriller"] = PlotTemplate(
    template_id="mystery_thriller",
    genre="Mystery Thriller",
    genre_cn="悬疑反转",
    description="层层剥开的谜团，每个答案都引出更大的问题。核心爽点：'原来是这样！'的信息差释放。",
    total_episodes=16,
    hook_intensity="高",
    reversal_frequency="每2-3集",
    romance_ratio=0.1,
    character_archetypes={
        "男主/女主": "侦探/警察/记者/受害者家属——执着于真相的人",
        "反派": "表面无辜/德高望重/意想不到的熟人",
        "关键证人": "知道部分真相但不敢说的人",
    },
    common_settings=["现代都市", "小镇", "医院", "学校", "警察局"],
    common_themes=["破案", "反转", "人性", "正义"],
    episodes=[
        EpisodeBeat(1, "案件发生", BeatType.HOOK,
                    description="震惊的罪案。建立核心谜题。主角卷入案件。",
                    cliffhanger="第一个嫌疑人出现——但看起来太像巧合了。",
                    dialogue_ratio=0.35, character_focus=["主角"]),
        EpisodeBeat(2, "初步调查", BeatType.SETUP,
                    description="主角开始调查。发现第一层伪装。",
                    cliffhanger="关键证人被发现——死了。'这绝不是意外。'",
                    dialogue_ratio=0.4, character_focus=["主角"]),
        EpisodeBeat(3, "第一个嫌疑人", BeatType.REVEAL,
                    description="锁定第一个嫌疑人。证据似乎无懈可击。",
                    cliffhanger="主角发现嫌疑人有一个完美的不在场证明——但这个证明本身就有问题。",
                    dialogue_ratio=0.45, character_focus=["主角", "嫌疑人"]),
        EpisodeBeat(4, "反转：不是他", BeatType.REVERSAL,
                    description="第一个嫌疑人被排除。但排除的过程揭示了更大的谜团。",
                    cliffhanger="真正的凶手在暗处看着这一切——他知道主角在查他。",
                    dialogue_ratio=0.4, character_focus=["主角"]),
        EpisodeBeat(5, "第二个方向", BeatType.SETUP,
                    description="主角从新角度切入。发现案件与五年前的旧案有关联。",
                    cliffhanger="旧案的卷宗被调出来了——但关键页被人撕掉了。",
                    dialogue_ratio=0.4, character_focus=["主角"]),
        EpisodeBeat(6, "第二个嫌疑人", BeatType.CONFLICT,
                    description="锁定第二个嫌疑人。这个人比第一个更可疑。",
                    cliffhanger="审讯中嫌疑人说了一句话：'你确定你找的是一个人吗？'",
                    dialogue_ratio=0.45, character_focus=["主角", "嫌疑人"]),
        EpisodeBeat(7, "团火迷案", BeatType.REVEAL,
                    description="第二个嫌疑人被杀。现在主角面对的可能是团伙作案。",
                    cliffhanger="主角发现自己的搭档/上司似乎也在隐瞒什么。",
                    dialogue_ratio=0.4, character_focus=["主角"]),
        EpisodeBeat(8, "付费点", BeatType.PAYWALL,
                    description="主角被诬陷为凶手。所有人都在追捕他/她。孤立无援。",
                    cliffhanger="逃命中，主角发现了一个关键证据——'真相就藏在我眼前，我却一直没看到。'",
                    dialogue_ratio=0.35, character_focus=["主角"], paywall=True),
        EpisodeBeat(9, "重启调查", BeatType.RECOVERY,
                    description="主角洗清嫌疑后在暗中调查。用非正常手段获取信息。",
                    cliffhanger="一条看似无关的线索把所有碎片串起来了。",
                    dialogue_ratio=0.4, character_focus=["主角"]),
        EpisodeBeat(10, "逼近真相", BeatType.REVEAL,
                    description="拼图越来越完整。主角离真相只有一步之遥。",
                    cliffhanger="主角找到了一个意想不到的人证——'我知道是谁，但我不敢说。'",
                    dialogue_ratio=0.45, character_focus=["主角", "证人"]),
        EpisodeBeat(11, "证人消失", BeatType.BETRAYAL,
                    description="证人被杀/失踪。主角意识到身边有内鬼。",
                    cliffhanger="内鬼的身份让主角的心碎了——是最信任的那个人。",
                    dialogue_ratio=0.4, character_focus=["主角"]),
        EpisodeBeat(12, "第三幕反转", BeatType.REVERSAL,
                    description="重大反转——所有人设都翻过来了。凶手是所有人都没想到的人。",
                    cliffhanger="'为什么是你？''因为第一个受害者……是我女儿。'",
                    dialogue_ratio=0.45, character_focus=["主角", "真凶"]),
        EpisodeBeat(13, "追捕", BeatType.ACTION,
                    description="主角与凶手正面对抗。智慧与勇气的最终较量。",
                    cliffhanger="凶手挟持了人质——人质是主角最重要的人。",
                    dialogue_ratio=0.3, character_focus=["主角", "真凶"]),
        EpisodeBeat(14, "了结", BeatType.CLIMAX,
                    description="正义得到伸张。但主角的内心已经改变。",
                    cliffhanger="案件结束了——但主角在凶手的住处发现了一份名单。上面还有十几个名字。",
                    dialogue_ratio=0.4, character_focus=["主角"]),
        EpisodeBeat(15, "余波", BeatType.EMOTIONAL,
                    description="案件善后。主角处理内心的创伤。社会对案件的反思。",
                    cliffhanger="'这不是结束。这只是开始。'——主角决定继续追查名单。",
                    dialogue_ratio=0.5, character_focus=["主角"]),
        EpisodeBeat(16, "新开端", BeatType.CLIFFHANGER,
                    description="主角踏上新的追查之路。第二季伏笔。",
                    cliffhanger="名单上的第一个名字——主角认识这个人。而且昨天刚见过。",
                    dialogue_ratio=0.4, character_focus=["主角"]),
    ],
)

# ── 4-10: 其余模板使用工厂函数生成，避免文件过长 ──

def _build_quick_templates() -> Dict[str, PlotTemplate]:
    """构建简版模板（完整模板按需生成）。"""
    templates = {}

    # 4. 先婚后爱
    templates["contract_marriage"] = PlotTemplate(
        template_id="contract_marriage",
        genre="Contract Marriage",
        genre_cn="先婚后爱",
        description="因契约/误会/利益被迫结婚，在相处中产生真爱。",
        total_episodes=20, hook_intensity="中", reversal_frequency="每5集", romance_ratio=0.7,
        character_archetypes={"男主": "高冷/事业型，对婚姻不屑一顾", "女主": "被迫接受婚姻，独立有主见"},
        common_settings=["现代都市", "别墅", "公司"],
        episodes=[
            EpisodeBeat(1, "被迫结婚", BeatType.HOOK, description="契约/误会导致的被迫婚姻", cliffhanger="'从今天起，我们是夫妻。但仅此而已。'", dialogue_ratio=0.45),
            EpisodeBeat(3, "同居磨合", BeatType.SETUP, description="日常冲突中了解对方", cliffhanger="一个不经意的温柔举动改变了看法"),
            EpisodeBeat(5, "第一次心动", BeatType.ROMANCE, description="在关键时刻保护了对方", cliffhanger="'我好像……有点在乎你。'", paywall=False),
            EpisodeBeat(8, "情敌出现", BeatType.CONFLICT, description="第三者的出现催化了感情", cliffhanger="'她是我的妻子/他是我的丈夫'——第一次宣示主权"),
            EpisodeBeat(10, "契约到期", BeatType.PAYWALL, description="契约到期，但两人都不想说再见", cliffhanger="'我们可以……不离婚吗？'", paywall=True),
            EpisodeBeat(12, "真相大白", BeatType.REVEAL, description="契约背后的真相揭晓", cliffhanger="原来这场婚姻背后有更大的秘密"),
            EpisodeBeat(15, "患难与共", BeatType.EMOTIONAL, description="共同面对危机", cliffhanger="'这次，我不会放开你的手'"),
            EpisodeBeat(18, "重新开始", BeatType.ROMANCE, description="以真正的爱情重新开始", cliffhanger="'这一次，不是因为契约，是因为我爱你'"),
            EpisodeBeat(20, "完美结局", BeatType.CLIMAX, description="圆满结局", cliffhanger="婚后甜蜜日常 + 可能的第二季伏笔"),
        ],
    )

    # 5. 古装宫斗
    templates["palace_intrigue"] = PlotTemplate(
        template_id="palace_intrigue",
        genre="Palace Intrigue",
        genre_cn="古装宫斗",
        description="后宫/朝堂的权力斗争。核心爽点：智谋碾压、步步为营。",
        total_episodes=30, hook_intensity="中", reversal_frequency="每4-5集", romance_ratio=0.2,
        character_archetypes={"女主": "低微出身但聪慧过人，从底层爬到顶峰", "男主": "皇帝/王爷，在权力和感情间挣扎"},
        common_settings=["皇宫", "王府", "后宫", "御花园"],
        episodes=[
            EpisodeBeat(1, "入宫", BeatType.HOOK, description="女主因故入宫/入府。建立生存困境", cliffhanger="第一天就被人盯上了"),
            EpisodeBeat(5, "第一次胜利", BeatType.REVERSAL, description="用智慧化解第一次危机", cliffhanger="胜利引来了更大的敌人"),
            EpisodeBeat(10, "获得圣宠", BeatType.ROMANCE, description="获得皇帝/王爷的注意和信任", cliffhanger="'朕/本王从未见过像你这样的人'", paywall=True),
            EpisodeBeat(15, "跌落谷底", BeatType.BETRAYAL, description="被陷害，失去一切", cliffhanger="囚禁中，女主发现了翻盘的线索"),
            EpisodeBeat(20, "反击", BeatType.TRAP, description="精心布局后反击", cliffhanger="'你以为你赢了？我的局才刚开始。'", paywall=True),
            EpisodeBeat(25, "登顶", BeatType.CLIMAX, description="击败所有敌人，站到权力顶峰", cliffhanger="'最高的位置，也是最孤独的位置'"),
            EpisodeBeat(30, "结局", BeatType.EMOTIONAL, description="权力与情感的最终抉择", cliffhanger="女主的选择——留下还是离开？"),
        ],
    )

    # 6. 都市职场
    templates["workplace_drama"] = PlotTemplate(
        template_id="workplace_drama",
        genre="Workplace Drama",
        genre_cn="都市职场",
        description="普通人在职场中逆袭成长。核心爽点：能力证明、打脸逆袭。",
        total_episodes=18, hook_intensity="中", reversal_frequency="每4集", romance_ratio=0.35,
        character_archetypes={"女主/男主": "被低估的职场新人/中层，有隐藏才能", "反派": "职场霸凌者/空降的关系户"},
        common_settings=["写字楼", "会议室", "甲方现场"],
        episodes=[
            EpisodeBeat(1, "入职/重返", BeatType.HOOK, description="主角进入新环境/重返职场", cliffhanger="第一天就被判了死刑——'三个月试用期，你恐怕过不了'"),
            EpisodeBeat(4, "初战告捷", BeatType.REVERSAL, description="凭借能力解决第一个难题", cliffhanger="胜利让主角进入了高层的视线——也进入了某些人的黑名单"),
            EpisodeBeat(7, "团队组建", BeatType.SETUP, description="组建自己的团队，建立信任", cliffhanger="团队中最重要的人被挖走了"),
            EpisodeBeat(9, "付费点", BeatType.PAYWALL, description="公司/部门面临最大危机", cliffhanger="'如果这次输了，我们就都完了'", paywall=True),
            EpisodeBeat(12, "反败为胜", BeatType.CLIMAX, description="绝地反击，赢得关键战役", cliffhanger="胜利背后——主角发现公司高层才是真正的敌人"),
            EpisodeBeat(15, "终极对决", BeatType.CONFLICT, description="与最终 boss 的正面较量", cliffhanger="'你以为你赢了？看看这个吧'——BOSS亮出底牌"),
            EpisodeBeat(18, "新高度", BeatType.EMOTIONAL, description="事业新高度 + 感情归宿", cliffhanger="'这不是终点，是新的起点'"),
        ],
    )

    # 7. 穿越系统
    templates["system_transmigration"] = PlotTemplate(
        template_id="system_transmigration",
        genre="System Transmigration",
        genre_cn="穿越系统流",
        description="穿越到异世界/过去，携带系统/金手指。核心爽点：系统加持下的降维打击。",
        total_episodes=30, hook_intensity="极高", reversal_frequency="每3集", romance_ratio=0.3,
        character_archetypes={"主角": "穿越者，拥有系统/金手指/现代知识", "反派": "异世界的强大存在，看不起穿越者"},
        common_settings=["异世界", "古代", "游戏世界"],
        episodes=[
            EpisodeBeat(1, "穿越+系统激活", BeatType.HOOK, description="穿越瞬间+系统激活。建立世界观和系统规则", cliffhanger="'欢迎来到新世界。你的第一个任务：活过今晚。'"),
            EpisodeBeat(3, "第一桶金", BeatType.ACTION, description="利用系统完成第一个任务", cliffhanger="系统的下一个任务让主角倒吸一口凉气"),
            EpisodeBeat(6, "建立势力", BeatType.SETUP, description="积累资源，建立自己的势力", cliffhanger="势力初成，但引来了当地豪强的注意"),
            EpisodeBeat(10, "第一次危机", BeatType.CONFLICT, description="被当地势力围剿", cliffhanger="系统给出了一个不可能完成的任务——但奖励是'活下去'", paywall=True),
            EpisodeBeat(15, "区域霸主", BeatType.CLIMAX, description="成为地区霸主", cliffhanger="霸主之后——发现这个世界比自己想象的更大"),
            EpisodeBeat(20, "更大的世界", BeatType.REVEAL, description="进入更高层次的竞争", cliffhanger="'你以为你是穿越者？这里到处都是穿越者。'", paywall=True),
            EpisodeBeat(25, "系统真相", BeatType.REVERSAL, description="发现系统的真正目的", cliffhanger="系统不是帮助——它是牢笼"),
            EpisodeBeat(30, "打破系统", BeatType.CLIMAX, description="超越系统，获得真正的自由", cliffhanger="'这才是真正的开始'"),
        ],
    )

    # 8. 战神归来
    templates["war_god_returns"] = PlotTemplate(
        template_id="war_god_returns",
        genre="War God Returns",
        genre_cn="战神归来",
        description="曾经的无敌战神隐姓埋名回归都市/故乡。核心爽点：隐藏身份被揭穿时的震惊。",
        total_episodes=24, hook_intensity="高", reversal_frequency="每4集", romance_ratio=0.3,
        character_archetypes={"男主": "前战神/特种兵王/超级强者，隐姓埋名"},
        common_settings=["现代都市", "故乡小镇", "军区"],
        episodes=[
            EpisodeBeat(1, "归来", BeatType.HOOK, description="战神归来，化身为普通人", cliffhanger="'他们以为我死了。他们错了。'"),
            EpisodeBeat(4, "身份暴露", BeatType.REVERSAL, description="第一次被迫展示实力", cliffhanger="围观者的震惊——'他到底是什么人？'"),
            EpisodeBeat(8, "旧部集结", BeatType.SETUP, description="旧部闻讯而来", cliffhanger="旧部带来了一个坏消息——敌人也在找他"),
            EpisodeBeat(12, "付费点", BeatType.PAYWALL, description="敌人围攻，战神以一敌百", cliffhanger="'你们以为人多就有用吗？'", paywall=True),
            EpisodeBeat(16, "幕后黑手", BeatType.REVEAL, description="发现敌人的真正身份", cliffhanger="幕后黑手是战神最信任的人"),
            EpisodeBeat(20, "终极对决", BeatType.CLIMAX, description="最终决战", cliffhanger="'这一战，不是为了复仇，是为了守护'"),
            EpisodeBeat(24, "和平", BeatType.EMOTIONAL, description="战后的平静生活", cliffhanger="'战神的使命已经完成。但世界还需要守护者'"),
        ],
    )

    # 9. 虐恋情深
    templates["tragic_romance"] = PlotTemplate(
        template_id="tragic_romance",
        genre="Tragic Romance",
        genre_cn="虐恋情深",
        description="相爱但不能在一起的虐心爱情。核心爽点：情绪过山车带来的强烈情感体验。",
        total_episodes=30, hook_intensity="高", reversal_frequency="每4集", romance_ratio=0.8,
        character_archetypes={"男主": "深情但被命运/家族/身份束缚", "女主": "爱得深沉但自尊心强"},
        common_settings=["现代都市", "古代", "民国"],
        episodes=[
            EpisodeBeat(1, "相遇", BeatType.HOOK, description="命运般的相遇", cliffhanger="'我们不该相遇的——这是最大的错误'"),
            EpisodeBeat(6, "相爱的代价", BeatType.CONFLICT, description="两人在一起了，但代价巨大", cliffhanger="家族/命运的反扑开始了"),
            EpisodeBeat(12, "被迫分离", BeatType.EMOTIONAL, description="被外力强行分开", cliffhanger="'等我。我一定会回来。'——但这一等就是五年", paywall=True),
            EpisodeBeat(18, "重逢", BeatType.ROMANCE, description="五年后重逢。一切已变", cliffhanger="'你还是没变。''你变了。'"),
            EpisodeBeat(24, "真相大白", BeatType.REVEAL, description="发现当年分离的真相", cliffhanger="原来一切都是某个人在背后操纵"),
            EpisodeBeat(30, "终局", BeatType.CLIMAX, description="是HE还是BE？（模板支持两种结局）", cliffhanger="'这一生，我只爱过你一个人'"),
        ],
    )

    # 10. 搞钱经商
    templates["business_building"] = PlotTemplate(
        template_id="business_building",
        genre="Business Building",
        genre_cn="搞钱经商",
        description="从零开始建立商业帝国。核心爽点：财富积累的成就感+打脸看不起你的人。",
        total_episodes=24, hook_intensity="中", reversal_frequency="每5集", romance_ratio=0.25,
        character_archetypes={"主角": "被看不起的普通人，拥有商业头脑/未来知识/系统"},
        common_settings=["现代都市", "古代商道", "改革开放时代"],
        episodes=[
            EpisodeBeat(1, "一无所有", BeatType.HOOK, description="主角破产/被开除/身无分文", cliffhanger="'今天我失去的，明天我会百倍拿回来'"),
            EpisodeBeat(4, "第一个一百万", BeatType.REVERSAL, description="赚到第一桶金", cliffhanger="财富引来了眼红的人和更大的机会"),
            EpisodeBeat(8, "商业战争", BeatType.CONFLICT, description="被同行打压", cliffhanger="对手以为胜券在握——但他不知道主角留了后手"),
            EpisodeBeat(12, "付费点", BeatType.PAYWALL, description="公司/生意面临生死危机", cliffhanger="'我们只剩三天时间。'", paywall=True),
            EpisodeBeat(16, "绝地反击", BeatType.CLIMAX, description="翻盘，击败对手", cliffhanger="胜利的代价——主角失去了一个重要的人"),
            EpisodeBeat(20, "商业帝国", BeatType.SETUP, description="建立自己的商业帝国", cliffhanger="站在顶楼俯视城市——'这只是开始'"),
            EpisodeBeat(24, "新目标", BeatType.EMOTIONAL, description="财富自由后的新追求", cliffhanger="'钱已经赚够了。现在该做点什么了'"),
        ],
    )

    return templates


# Merge quick templates into main dict
PLOT_TEMPLATES.update(_build_quick_templates())


# ═══════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════

def get_template(template_id: str) -> Optional[PlotTemplate]:
    """Get a plot template by ID."""
    return PLOT_TEMPLATES.get(template_id)


def list_templates() -> List[Dict[str, str]]:
    """List all available plot templates."""
    return [
        {
            "template_id": t.template_id,
            "genre": t.genre,
            "genre_cn": t.genre_cn,
            "description": t.description,
            "total_episodes": t.total_episodes,
        }
        for t in PLOT_TEMPLATES.values()
    ]


def match_template(style: str, theme: str, outline: str = "") -> Optional[PlotTemplate]:
    """Auto-match the best template based on style/theme/outline keywords.

    Simple keyword matching — in production, use embedding similarity.
    """
    combined = f"{style} {theme} {outline}".lower()

    matchers = {
        "rebirth_revenge": ["重生", "复仇", "逆袭", "前世"],
        "ceo_romance": ["霸总", "总裁", "甜宠", "契约", "豪门"],
        "mystery_thriller": ["悬疑", "推理", "破案", "罪案", "凶杀"],
        "contract_marriage": ["先婚后爱", "契约婚姻", "闪婚", "形婚"],
        "palace_intrigue": ["宫斗", "古装宫廷", "后宫", "王府", "争宠"],
        "workplace_drama": ["职场", "上班", "升职", "办公室", "打工人"],
        "system_transmigration": ["系统", "穿越", "金手指", "异世界", "游戏世界"],
        "war_god_returns": ["战神", "归来", "兵王", "特种兵", "隐姓埋名"],
        "tragic_romance": ["虐恋", "虐心", "虐", "虐文", "言情虐"],
        "business_building": ["经商", "搞钱", "创业", "商战", "商业帝国"],
    }

    best_match = None
    best_score = 0
    for tid, keywords in matchers.items():
        score = sum(1 for kw in keywords if kw in combined)
        if score > best_score:
            best_score = score
            best_match = tid

    if best_match and best_score >= 2:
        return PLOT_TEMPLATES.get(best_match)
    return None
