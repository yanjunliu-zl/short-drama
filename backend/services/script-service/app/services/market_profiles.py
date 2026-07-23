"""
海外市场文化档案 — 短剧本土化的"文化基因库"。

每个市场档案定义了:
- 角色原型 (当地观众共鸣的角色类型)
- 热门类型 (该市场最火的短剧类型)
- 叙事惯例 (节奏、悬念风格、情感表达方式)
- 禁忌话题 (内容合规红线)
- 文化锚点 (节日、食物、社交礼仪、地名)

数据来源: DramaBox/ReelShort 2025-2026 出海报告 + 各市场 Top100 短剧分析
"""
from typing import Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class MarketProfile:
    """市场文化档案"""
    locale: str                          # e.g. "en-US", "ar-SA", "tr-TR"
    market_name: str                     # e.g. "北美", "中东"
    language: str                        # 输出语言
    language_name: str                   # e.g. "English", "Arabic"

    # ── 角色原型 ──
    character_archetypes: List[Dict[str, str]] = field(default_factory=list)
    # [{"role": "男主", "archetype": "华尔街精英/科技新贵/退役特种兵",
    #   "traits": "alpha但尊重女性, 有脆弱面, 愿意改变"},
    #  {"role": "女主", "archetype": "独立创业者/单亲妈妈/小镇女孩",
    #   "traits": "坚强但不刻薄, 有梦想, 接地气"}]

    # ── 热门类型 ──
    popular_genres: List[str] = field(default_factory=list)
    # ["亿万富翁爱情", "狼人/吸血鬼 Romance", "小镇悬疑", "家庭伦理"]

    # ── 叙事惯例 ──
    episode_length_preferred: str = "1-2分钟"  # 每集时长偏好
    total_episodes_preferred: str = "60-80集"  # 总集数偏好
    pacing_style: str = ""                     # "快节奏反转" | "情感层层递进" | "悬念驱动"
    cliffhanger_style: str = ""                # "信息差悬念" | "生死抉择" | "关系破裂预告"
    romance_style: str = ""                    # "慢热暧昧" | "先婚后爱" | "破镜重圆" | "禁忌之恋"

    # ── 内容红线 ──
    taboo_topics: List[str] = field(default_factory=list)
    # ["宗教亵渎", "王室负面描写", "LGBTQ+(部分市场)", ...]
    sensitive_replacements: Dict[str, str] = field(default_factory=dict)
    # {"酒": "果汁", "猪肉": "羊肉", "赌博": "竞技游戏"}

    # ── 文化锚点 ──
    common_male_names: List[str] = field(default_factory=list)
    common_female_names: List[str] = field(default_factory=list)
    common_settings: List[str] = field(default_factory=list)
    # ["华尔街办公室", "Hamptons度假别墅", "曼哈顿顶层公寓"]
    cultural_events: List[str] = field(default_factory=list)
    # ["感恩节晚餐", "超级碗派对", "毕业舞会"]
    food_references: List[str] = field(default_factory=list)
    # ["拿铁", "牛油果吐司", "意面"]

    # ── 系统提示 ──
    system_prompt_override: str = ""           # 覆盖默认 system prompt


# ═══════════════════════════════════════════════════════════════
# 市场档案数据库
# ═══════════════════════════════════════════════════════════════

MARKET_PROFILES: Dict[str, MarketProfile] = {
    # ── 北美 (英语) ──
    "en-US": MarketProfile(
        locale="en-US",
        market_name="北美",
        language="English",
        language_name="English",
        character_archetypes=[
            {"role": "男主", "archetype": "Billionaire CEO / Tech Founder / Former Navy SEAL",
             "traits": "Alpha but emotionally available, has a soft spot for family, secretly vulnerable"},
            {"role": "女主", "archetype": "Independent entrepreneur / Single mother / Small-town girl with big dreams",
             "traits": "Strong but not cruel, relatable, has agency, doesn't wait to be rescued"},
            {"role": "反派", "archetype": "Corporate rival / Jealous ex / Scheming socialite",
             "traits": "Motivated by greed or insecurity, not pure evil"},
            {"role": "配角", "archetype": "Best friend / Loyal assistant / Sassy neighbor",
             "traits": "Comic relief but with depth, gives good advice"},
        ],
        popular_genres=[
            "Billionaire Romance", "Werewolf/Vampire Paranormal Romance",
            "Small Town Mystery", "Family Drama", "Second Chance Love",
            "Mafia/Bad Boy Romance", "Workplace Rivals to Lovers",
        ],
        episode_length_preferred="1-2 minutes",
        total_episodes_preferred="60-80 episodes",
        pacing_style="Fast-paced: hook in first 3 seconds, cliffhanger every episode, twist every 10 episodes",
        cliffhanger_style="Information asymmetry (viewer knows secret, character doesn't), relationship status cliffhangers, danger cliffhangers",
        romance_style="Slow burn with high tension. First kiss by episode 20-30. Enemies to lovers or contract marriage tropes are very popular.",
        taboo_topics=[
            "Religious blasphemy", "Explicit sexual content (platform policy)",
            "Glorification of school violence", "Child endangerment as plot device",
        ],
        sensitive_replacements={
            "KTV": "nightclub", "白酒": "whiskey",
            "红包": "Venmo transfer", "单位": "company",
        },
        common_male_names=["Liam", "Noah", "Ethan", "Mason", "Alexander", "Sebastian", "William", "James"],
        common_female_names=["Emma", "Olivia", "Ava", "Sophia", "Isabella", "Charlotte", "Amelia", "Mia"],
        common_settings=[
            "Manhattan penthouse office", "Hamptons beach house",
            "Silicon Valley startup campus", "Small-town coffee shop",
            "Charity gala ballroom", "Central Park",
        ],
        cultural_events=["Thanksgiving dinner", "Super Bowl party", "Christmas Eve", "Prom night", "Fourth of July"],
        food_references=["latte", "avocado toast", "pasta", "pancakes", "steak", "sushi takeout"],
    ),

    # ── 中东 (阿拉伯语) ──
    "ar-SA": MarketProfile(
        locale="ar-SA",
        market_name="中东",
        language="Arabic",
        language_name="العربية",
        character_archetypes=[
            {"role": "男主", "archetype": "Business tycoon / Sheikh / Successful professional",
             "traits": "Protective, family-oriented, respects tradition but modern, generous"},
            {"role": "女主", "archetype": "University graduate / Career woman / Strong family pillar",
             "traits": "Intelligent, dignified, balances tradition and ambition, loyal to family"},
            {"role": "反派", "archetype": "Business rival / Envious relative / Gold digger",
             "traits": "Motivated by greed or jealousy, schemes against family unity"},
        ],
        popular_genres=[
            "Family Drama", "Arranged Marriage Romance", "Business Empire",
            "Revenge Drama", "Cross-Class Love", "Desert Epic",
        ],
        episode_length_preferred="2-3 minutes",
        total_episodes_preferred="30-50 episodes (Ramadan specials: 30 episodes)",
        pacing_style="Emotionally layered. Family dynamics are central. Conflict often comes from family honor vs personal desire.",
        cliffhanger_style="Family secret reveals, honor at stake, 'who will she choose?' dilemmas",
        romance_style="Slow burn, restrained. Chemistry through glances and family interactions. Marriage is the goal, not casual dating.",
        taboo_topics=[
            "Religious criticism", "Premarital intimacy (depicted openly)",
            "Alcohol/drugs (positive portrayal)", "Disrespect to elders/parents",
            "Royal family negative portrayal (GCC markets)",
        ],
        sensitive_replacements={
            "酒吧": "café", "喝酒": "drink tea", "一夜情": "secret meeting",
            "猪肉": "lamb", "赌博": "business deal",
        },
        common_male_names=["Omar", "Khalid", "Mohammed", "Ali", "Hassan", "Youssef", "Ibrahim", "Fahad"],
        common_female_names=["Fatima", "Aisha", "Noora", "Layla", "Maryam", "Sara", "Amal", "Hind"],
        common_settings=[
            "Dubai skyscraper office", "Family majlis (sitting room)",
            "Riyadh luxury mall", "Desert camp resort",
            "Jeddah waterfront", "Cairo family home",
        ],
        cultural_events=["Ramadan iftar", "Eid al-Fitr celebration", "Family wedding", "Hajj season"],
        food_references=["dates and Arabic coffee", "mandi rice", "baklava", "shawarma", "hummus"],
    ),

    # ── 土耳其 ──
    "tr-TR": MarketProfile(
        locale="tr-TR",
        market_name="土耳其",
        language="Turkish",
        language_name="Türkçe",
        character_archetypes=[
            {"role": "男主", "archetype": "Powerful businessman / Mafia boss / Army officer",
             "traits": "Dominant, possessive, but deeply loyal, will sacrifice everything for love"},
            {"role": "女主", "archetype": "Poor but proud / University student / Betrayed wife seeking revenge",
             "traits": "Strong-willed, emotional, fights back, traditional values but modern spirit"},
        ],
        popular_genres=[
            "Mafia Romance", "Rich-Poor Love", "Revenge Drama",
            "Forced Marriage", "Family Saga", "Betrayal & Redemption",
        ],
        episode_length_preferred="2-3 minutes (match Turkish dizi pacing)",
        total_episodes_preferred="50-100 episodes (Turkish audience prefers longer arcs)",
        pacing_style="Highly emotional, dramatic confrontations, tears and passion. Slow-burn revenge plots are extremely popular.",
        cliffhanger_style="Shocking reveals (secret child, hidden identity), gun-to-the-head moments, 'who is the traitor?'",
        romance_style="Intense, possessive love. Jealousy is romantic. Grand gestures. 'I will burn the world for you.'",
        taboo_topics=[
            "Blasphemy", "Anti-national sentiment", "Explicit content",
        ],
        sensitive_replacements={
            "白酒": "rakı", "红包": "gold coin / altın",
        },
        common_male_names=["Emir", "Kemal", "Can", "Deniz", "Yusuf", "Barış", "Arda", "Efe"],
        common_female_names=["Zeynep", "Elif", "Defne", "Aslı", "Ece", "İpek", "Sude", "Cemre"],
        common_settings=[
            "Bosphorus mansion", "Istanbul high-rise office",
            "Bodrum summer villa", "Cappadocia hot air balloon scene",
            "Grand Bazaar shop", "Black Sea village",
        ],
        cultural_events=["Bayram family gathering", "Engagement ceremony with red ribbon", "Turkish coffee fortune telling"],
        food_references=["Turkish coffee", "baklava", "simit", "kumpir", "mantı", "çay (tea)"],
    ),

    # ── 日本 ──
    "ja-JP": MarketProfile(
        locale="ja-JP",
        market_name="日本",
        language="Japanese",
        language_name="日本語",
        character_archetypes=[
            {"role": "男主", "archetype": "Elite salaryman / Cool senpai / Kind-hearted shop owner",
             "traits": "Reserved, hardworking, shows love through actions not words, honorable"},
            {"role": "女主", "archetype": "Office worker / Cafe owner / Transfer student",
             "traits": "Kind, diligent, quietly strong, relatable, finds joy in small things"},
        ],
        popular_genres=[
            "Office Romance", "Slice of Life", "Food & Love",
            "Healing Drama", "Mystery Thriller", "Coming of Age",
        ],
        episode_length_preferred="1-2 minutes (compatible with LINE/TikTok shorts)",
        total_episodes_preferred="30-50 episodes",
        pacing_style="Subtle, quiet moments are valued. Emotional payoffs are earned slowly. 'Kizuki' (realization) moments are key turning points.",
        cliffhanger_style="Gentle cliffhangers: a confession half-made, a letter discovered, a sudden encounter. Not aggressive.",
        romance_style="Pure, awkward, slow-burn. Hand-holding is a milestone. Confession scenes are climactic. 'Kokuhaku' (confession) is the peak.",
        taboo_topics=[
            "Yakuza glorification", "Underage drinking/smoking (if glamorized)",
            "Excessive violence against vulnerable", "Bullying glorification",
        ],
        sensitive_replacements={
            "干杯": "cheers / 乾杯", "红包": "お年玉 (otoshidama)",
        },
        common_male_names=["Ren", "Haruto", "Yuto", "Sota", "Riku", "Takumi", "Kaito", "Sho"],
        common_female_names=["Yui", "Sakura", "Hina", "Mio", "Riko", "Mei", "Aoi", "Rin"],
        common_settings=[
            "Tokyo office tower", "Small neighborhood café",
            "Shimokitazawa vintage shop", "Train station platform at sunset",
            "Convenience store at midnight", "Traditional ryokan inn",
        ],
        cultural_events=["Cherry blossom viewing (hanami)", "Summer festival (matsuri)", "New Year shrine visit", "Valentine's chocolate giving"],
        food_references=["onigiri", "ramen", "convenience store bento", "matcha latte", "takoyaki", "sushi"],
    ),

    # ── 韩国 ──
    "ko-KR": MarketProfile(
        locale="ko-KR",
        market_name="韩国",
        language="Korean",
        language_name="한국어",
        character_archetypes=[
            {"role": "男主", "archetype": "Chaebol heir / Star prosecutor / Top star",
             "traits": "Cold exterior, warm heart. Secretly protective. Tragic backstory."},
            {"role": "女主", "archetype": "Poor but spirited / Intern / Makeup artist",
             "traits": "Plucky, hardworking, stands up to bullies, cries but never gives up"},
        ],
        popular_genres=[
            "Chaebol Romance", "Contract Marriage", "Revenge Drama",
            "Fantasy Romance (goblin/nine-tailed fox)", "Office Romance",
            "Campus Love", "Time Slip / Reincarnation",
        ],
        episode_length_preferred="1-2 minutes",
        total_episodes_preferred="50-80 episodes",
        pacing_style="K-drama style: dramatic reveals every 10 eps, wrist-grab moments, slow-motion rain scenes. OST-worthy emotional peaks.",
        cliffhanger_style="Shocking identity reveals, truck-of-doom near-misses, kiss interruptions, 'I am your brother' reveals",
        romance_style="High drama, fate-driven. Childhood connection trope is mandatory. Piggyback rides, wrist grabs, umbrella sharing.",
        taboo_topics=[
            "North Korea positive portrayal (sensitive)", "Draft dodging glorification",
            "Historical revisionism about Japan/Korea relations",
        ],
        sensitive_replacements={
            "路边摊": "pojangmacha tent bar", "红包": "cash envelope / 세뱃돈",
        },
        common_male_names=["Jun-ho", "Tae-oh", "Seo-jun", "Min-hyuk", "Ji-hoon", "Hyun-woo", "Do-hyun"],
        common_female_names=["Seo-yeon", "Ji-woo", "Ha-eun", "Da-in", "Soo-ah", "Ye-eun", "Mi-so"],
        common_settings=[
            "Gangnam high-rise office", "Han River park bench",
            "Jeju Island resort", "Hongdae café", "Itaewon rooftop bar",
            "Traditional hanok house", "Convenience store ramen date",
        ],
        cultural_events=["Chuseok family gathering", "Couple's 100-day anniversary", "MT (membership training) retreat", "Company dinner (회식)"],
        food_references=["soju and samgyeopsal", "tteokbokki", "ramyun", "kimchi jjigae", "fried chicken and beer (chimaek)"],
    ),

    # ── 拉美 (西班牙语) ──
    "es-MX": MarketProfile(
        locale="es-MX",
        market_name="拉美",
        language="Spanish",
        language_name="Español",
        character_archetypes=[
            {"role": "男主", "archetype": "Rich rancher / Hotel empire heir / Mysterious stranger",
             "traits": "Passionate, protective, family is everything, jealous but loyal"},
            {"role": "女主", "archetype": "Humble worker / Runaway bride / Single mother fighting back",
             "traits": "Fiery, resilient, loves deeply, won't be disrespected, stands up for family"},
            {"role": "反派", "archetype": "Evil twin / Greedy stepmother / Corrupt business rival",
             "traits": "Classic telenovela villain: dramatic, scheming, eventually gets karma"},
        ],
        popular_genres=[
            "Telenovela Romance", "Family Legacy Drama", "Rich vs Poor Love",
            "Revenge & Justice", "Second Chance Love", "Small Town Secrets",
        ],
        episode_length_preferred="1-2 minutes",
        total_episodes_preferred="60-100 episodes (market expects long arcs)",
        pacing_style="High emotion, dramatic confrontations. Face-slaps and dramatic reveals. Family loyalty is paramount.",
        cliffhanger_style="Identity reveals, secret pregnancies, 'I am your real mother!', wedding interruptions, 'he's not dead!'",
        romance_style="Passionate, dramatic, grand gestures. Love triangles. The more obstacles, the better.",
        taboo_topics=[
            "Religious disrespect (Catholicism is sensitive in many markets)",
            "Cartel glorification (varies by country, sensitive in Mexico/Colombia)",
        ],
        sensitive_replacements={
            "茅台": "tequila", "茶馆": "café", "红包": "sobre con dinero",
        },
        common_male_names=["Alejandro", "Santiago", "Mateo", "Diego", "Carlos", "Miguel", "Fernando", "Rafael"],
        common_female_names=["Sofía", "Valentina", "Isabella", "Camila", "María", "Luciana", "Gabriela", "Elena"],
        common_settings=[
            "Hacienda (family ranch)", "Mexico City penthouse",
            "Cancún beach resort", "Colonial town plaza",
            "Abuela's kitchen", "Buenos Aires café",
        ],
        cultural_events=["Quinceañera (15th birthday)", "Día de los Muertos", "Navidad family dinner", "Sunday family barbecue"],
        food_references=["tacos", "tamales", "empanadas", "guacamole", "churros", "abuela's secret recipe"],
    ),

    # ── 东南亚 (泰语为代表) ──
    "th-TH": MarketProfile(
        locale="th-TH",
        market_name="东南亚",
        language="Thai",
        language_name="ไทย",
        character_archetypes=[
            {"role": "男主", "archetype": "Hotel chain heir / Successful businessman / Kind-hearted doctor",
             "traits": "Gentlemanly, respectful of elders, generous, protective without being controlling"},
            {"role": "女主", "archetype": "Small business owner / Teacher / Village girl in the city",
             "traits": "Optimistic, hardworking, kind to everyone, stands up for what's right"},
        ],
        popular_genres=[
            "Lakorn-style Romance", "Family Comedy", "Ghost Love Story",
            "Cross-Class Love", "Heartwarming Drama", "Food Business Romance",
        ],
        episode_length_preferred="1-2 minutes",
        total_episodes_preferred="40-60 episodes",
        pacing_style="Gentle pace with comedic moments. Slapstick humor balanced with sincere emotions. Karma works visibly.",
        cliffhanger_style="Misunderstandings, 'wrong place wrong time', family disapproval cliffhangers",
        romance_style="Sweet, playful. Lots of teasing and accidental encounters. Food is a love language.",
        taboo_topics=[
            "Royal family (strictly off-limits in Thailand)", "Religious mockery",
            "School uniform inappropriate depictions",
        ],
        sensitive_replacements={},
        common_male_names=["Than", "Nat", "Pete", "Kong", "Bank", "Mark", "Gun", "Earth"],
        common_female_names=["Mai", "Fern", "Mook", "Pim", "Nam", "Fa", "Bua", "Praew"],
        common_settings=[
            "Bangkok rooftop restaurant", "Floating market stall",
            "Chiang Mai mountain resort", "Family-run street food cart",
            "Temple fair", "Beachfront bungalow in Phuket",
        ],
        cultural_events=["Songkran (water festival)", "Loy Krathong (lantern festival)", "Mother's Day temple visit"],
        food_references=["pad thai", "mango sticky rice", "tom yum", "street food skewers", "Thai iced tea"],
    ),
}


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def get_profile(locale: str) -> MarketProfile:
    """Get market profile, falling back to en-US if unknown."""
    return MARKET_PROFILES.get(locale, MARKET_PROFILES["en-US"])


def list_locales() -> List[Dict[str, str]]:
    """List all supported locales."""
    return [
        {"locale": p.locale, "market": p.market_name, "language": p.language_name}
        for p in MARKET_PROFILES.values()
    ]


ALL_LOCALES = list(MARKET_PROFILES.keys())
