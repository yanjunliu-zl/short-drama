import logging
from typing import Dict, Any, Optional
import asyncio
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.callbacks.base import BaseCallbackHandler

from app.core.config import settings
from app.services.cache_service import get_cache_service

logger = logging.getLogger(__name__)


class ScriptAICallbackHandler(BaseCallbackHandler):
    """AI回调处理器，用于跟踪剧本生成进度"""

    def __init__(self):
        self.current_step = 0
        self.total_steps = 4  # 生成步骤数
        self.progress_callbacks = []

    def on_llm_start(self, serialized: Dict[str, Any], prompts: list[str], **kwargs):
        """LLM开始处理时调用"""
        self.current_step += 1
        logger.info(f"AI生成步骤 {self.current_step}/{self.total_steps}: {prompts[0][:50]}...")

    def on_llm_end(self, response, **kwargs):
        """LLM处理结束时调用"""
        logger.info(f"AI生成步骤 {self.current_step}/{self.total_steps} 完成")


class AIService:
    """AI服务，封装LangChain和LangGraph功能，支持缓存"""

    def __init__(self):
        self.llm = None
        self.callback_handler = None
        self.cache_service = None
        self._initialized = False

    async def initialize(self):
        """初始化AI服务"""
        if self._initialized:
            return

        try:
            logger.info("初始化AI服务...")

            # 初始化缓存服务
            self.cache_service = await get_cache_service()

            # 初始化回调处理器
            self.callback_handler = ScriptAICallbackHandler()

            # 配置AI模型 - 优先使用DeepSeek，其次OpenAI
            llm_kwargs = {
                "model_name": settings.MODEL_NAME,
                "temperature": settings.OPENAI_TEMPERATURE,
                "max_tokens": settings.OPENAI_MAX_TOKENS,
                "timeout": settings.OPENAI_TIMEOUT,
                "streaming": False,
            }

            # 优先使用DeepSeek，其次OpenAI，否则使用Mock模式
            if settings.DEEPSEEK_API_KEY:
                llm_kwargs["openai_api_key"] = settings.DEEPSEEK_API_KEY
                llm_kwargs["openai_api_base"] = settings.DEEPSEEK_API_BASE
                llm_kwargs["model_name"] = settings.DEEPSEEK_MODEL
                logger.info(f"使用DeepSeek模型: {settings.DEEPSEEK_MODEL}")
                self.llm = ChatOpenAI(**llm_kwargs)
                self._mock_mode = False
            elif settings.OPENAI_API_KEY:
                llm_kwargs["openai_api_key"] = settings.OPENAI_API_KEY
                if settings.OPENAI_API_BASE:
                    llm_kwargs["openai_api_base"] = settings.OPENAI_API_BASE
                logger.info(f"使用OpenAI模型: {settings.MODEL_NAME}")
                self.llm = ChatOpenAI(**llm_kwargs)
                self._mock_mode = False
            else:
                logger.warning("未配置AI API密钥，使用Mock模式生成示例剧本")
                self.llm = None
                self._mock_mode = True

            # 配置LangChain追踪
            if settings.LANGCHAIN_TRACING and settings.LANGCHAIN_API_KEY:
                import os
                os.environ["LANGCHAIN_TRACING_V2"] = "true"
                os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT or "https://api.smith.langchain.com"
                os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
                os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT or "shortdrama-script-service"

            self._initialized = True
            logger.info("AI服务初始化完成")

        except Exception as e:
            logger.error(f"AI服务初始化失败: {e}")
            raise

    async def generate_script(self, request: Dict[str, Any]) -> str:
        """使用LangChain生成剧本，支持缓存。无API Key时使用Mock模式"""
        if not self._initialized:
            await self.initialize()

        try:
            logger.info(f"开始生成剧本: {request.get('title', '未命名剧本')}")

            # Mock模式：直接返回示例剧本
            if self._mock_mode:
                await asyncio.sleep(2)  # 模拟生成延迟
                return self._generate_mock_script(request)

            # 尝试从缓存获取
            if self.cache_service:
                cached_script = await self.cache_service.get_cached_script(request)
                if cached_script:
                    logger.info("缓存命中: 剧本生成结果")
                    return cached_script

            logger.info("缓存未命中，调用AI生成...")

            # 构建系统提示
            system_prompt = self._build_system_prompt(request)
            human_prompt = self._build_human_prompt(request)

            # 创建消息链
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]

            # 调用LLM
            logger.info("调用LLM生成剧本...")
            response = await self.llm.ainvoke(messages)

            script_content = response.content

            # 缓存结果
            if self.cache_service:
                await self.cache_service.cache_script_generation(request, script_content)
                logger.info("剧本生成结果已缓存")

            logger.info(f"剧本生成完成，长度: {len(script_content)} 字符")
            return script_content

        except Exception as e:
            logger.error(f"剧本生成失败: {e}")
            raise

    def _generate_mock_script(self, request: Dict[str, Any]) -> str:
        """生成Mock示例剧本（开发环境用）"""
        title = request.get('title', '未命名剧本')
        style = request.get('style', '浪漫喜剧')
        setting = request.get('setting', '现代都市')
        theme = request.get('theme', '爱情')

        return f'''第一集 - {title}

【场景一：{setting}的咖啡馆 - 白天】

（阳光透过落地窗洒在木质桌面上。咖啡馆里飘着咖啡的香气。）

女主角林小雨坐在靠窗的位置，手里握着一杯已经凉掉的拿铁。
她的目光一直盯着门口，似乎在等待什么人。

（门铃响起，一个身穿深色西装的男人走进来。）

男人：（环顾四周，目光落在林小雨身上）"抱歉，让你久等了。"

林小雨：（站起身，勉强挤出一个微笑）"没关系，沈先生。"

沈墨：他走到她对面坐下。"叫我沈墨就好。所以……你是从哪里找到我的联系方式的？"

林小雨：（深吸一口气）"我是你弟弟的女朋友。"她顿了顿，"至少，曾经是。"

（沈墨的表情瞬间凝固。）

沈墨："沈言的……女朋友？"

林小雨："我需要你的帮助。小言失踪前，留下了一个箱子。他说，如果出了什么事，就来找你。"

第二集 - 箱子里的秘密

【场景二：沈墨的公寓 - 夜晚】

（昏暗的灯光下，一个古旧的木箱放在茶几上。沈墨和林小雨面对面坐着。）

沈墨：（仔细检查箱子）"这上面有密码锁。"

林小雨从包里拿出一张纸条。"小言发给我的最后一条消息——'密码是你的生日'。"

（沈墨输入数字，箱子发出轻微的咔哒声。箱盖缓缓打开。）

（里面是一叠文件、几张照片，还有一个U盘。）

沈墨：（翻看文件，脸色越来越凝重）"这些是……"

林小雨凑过来看，突然倒吸一口冷气。

林小雨："这是公司的财务报表？小言怎么会有这些？"

沈墨合上文件，站起身走到窗边。窗外是城市璀璨的夜景，但他的眼神却异常冰冷。

沈墨："他知道了一些不该知道的事。这就是他失踪的原因。"

林小雨："那我们该怎么办？"

沈墨转身面对她，眼中闪过一丝决然。

沈墨："我们要找出真相。不管代价是什么。"

第三集 - 第一份线索

【场景三：沈氏集团总部 - 上午】

（高耸入云的玻璃大厦。沈墨和林小雨站在大楼入口前。）

林小雨：（紧张地整理衣领）"你真的确定让我假扮助理？"

沈墨："不用担心。我查过了，下个月要进行的项目涉及一笔巨额资金。"他压低声音，"而这些资金，正好和小言留下的账目对得上。"

（电梯门打开，两人走出，迎面撞上一个穿着时髦的女人。）

苏婉：（冷笑）"这不是沈墨吗？好久不见。这位是你的新女朋友？"她上下打量林小雨。

沈墨：（冷淡地）"这是我的助理。苏婉，你似乎对公司的事很感兴趣？"

苏婉的脸色微变，但很快恢复如常。

苏婉："我可是公司的副总裁。"她凑近沈墨耳边，轻声说："有些事，你最好别管。"

（她转身离开，高跟鞋在走廊里发出清脆的回响。）

林小雨：（看着苏婉远去的背影）"她肯定知道些什么。"

沈墨："她身上有香水味——玫瑰和檀香。和小言留下的那张名片上的香味一模一样。"

（两人交换了一个眼神。）

沈墨："看来，我们找对方向了。"'''

    def _build_system_prompt(self, request: Dict[str, Any]) -> str:
        """构建系统提示"""
        theme = request.get('theme', '爱情')
        length = request.get('length', '短篇')
        style = request.get('style', '浪漫喜剧')
        setting = request.get('setting', '现代都市')

        return f"""你是一个专业的剧本作家，专门创作{theme}主题的{style}剧本。

创作要求:
1. 剧本类型: {length}剧本
2. 故事背景: {setting}
3. 剧本风格: {style}
4. 目标观众: 短视频平台用户

剧本结构要求:
1. 必须有引人入胜的开场
2. 角色发展要有层次感
3. 冲突和转折要合理
4. 结局要符合{theme}主题

输出格式:
请按照标准的剧本格式输出，包括场景描述、角色对话和动作指示。
"""

    def _build_human_prompt(self, request: Dict[str, Any]) -> str:
        """构建用户提示"""
        title = request.get('title', '未命名剧本')
        characters = request.get('characters', [])
        additional_notes = request.get('additional_notes', '')

        character_str = "\n".join([f"- {char}" for char in characters]) if characters else "请自行设计2-3个主要角色"

        return f"""请创作一个名为《{title}》的剧本。

角色设定:
{character_str}

额外要求:
{additional_notes if additional_notes else '无特殊要求'}

请创作一个完整、吸引人且适合短视频平台的剧本。"""

    async def analyze_script_structure(self, script_content: str) -> Dict[str, Any]:
        """分析剧本结构，支持缓存"""
        if not self._initialized:
            await self.initialize()

        try:
            if self._mock_mode:
                return {"analysis": "剧本结构完整", "characters": 3, "scenes": 3, "quality": "good"}

            # 尝试从缓存获取
            if self.cache_service:
                cached_analysis = await self.cache_service.get_cached_analysis(script_content)
                if cached_analysis:
                    logger.info("缓存命中: 剧本分析结果")
                    return cached_analysis

            logger.info("缓存未命中，调用AI分析剧本结构...")

            prompt = f"""请分析以下剧本的结构:

{script_content[:1000]}...

请分析:
1. 主要场景数量
2. 角色数量
3. 故事节奏
4. 情感曲线
5. 建议改进点

请以JSON格式返回分析结果。"""

            messages = [
                SystemMessage(content="你是一个剧本分析师，擅长分析剧本结构和故事节奏。"),
                HumanMessage(content=prompt)
            ]

            response = await self.llm.ainvoke(messages)
            # 这里应该解析JSON，但简化处理
            analysis_result = {
                "analysis": response.content,
                "scenes_count": 4,  # 示例值
                "characters_count": 3,  # 示例值
                "pace": "适中",
            }

            # 缓存结果
            if self.cache_service:
                await self.cache_service.cache_script_analysis(script_content, analysis_result)
                logger.info("剧本分析结果已缓存")

            return analysis_result

        except Exception as e:
            logger.error(f"剧本分析失败: {e}")
            return {"error": str(e)}

    async def optimize_script(self, script_content: str, feedback: str) -> str:
        """优化剧本，支持缓存"""
        if not self._initialized:
            await self.initialize()

        try:
            if self._mock_mode:
                await asyncio.sleep(0.5)
                return script_content  # Mock: return original content as "optimized"

            # 尝试从缓存获取
            if self.cache_service:
                cached_optimization = await self.cache_service.get_cached_optimization(script_content, feedback)
                if cached_optimization:
                    logger.info("缓存命中: 剧本优化结果")
                    return cached_optimization

            logger.info("缓存未命中，调用AI优化剧本...")

            prompt = f"""请根据以下反馈优化剧本，直接返回优化后的完整剧本内容，不要添加任何解释、前言或后记：

反馈: {feedback}

原剧本:
{script_content[:3000]}

关键优化方向:
1. 对白口语化、自然
2. 情感层次丰富
3. 场景转换流畅
4. 视觉描写具体可执行

直接返回剧本正文："""

            messages = [
                SystemMessage(content="你是专业剧本编辑。直接返回优化后的剧本正文，禁止添加任何解释、评价或前言。"),
                HumanMessage(content=prompt)
            ]

            response = await self.llm.ainvoke(messages)
            optimized_script = response.content

            # 缓存结果
            if self.cache_service:
                await self.cache_service.cache_script_optimization(script_content, feedback, optimized_script)
                logger.info("剧本优化结果已缓存")

            return optimized_script

        except Exception as e:
            logger.error(f"剧本优化失败: {e}")
            raise

    async def novel_to_script(self, request: Dict[str, Any]) -> str:
        """将小说转换为剧本，支持缓存"""
        if not self._initialized:
            await self.initialize()

        try:
            logger.info(f"开始将小说转换为剧本: {request.get('title', '未命名剧本')}")

            if self._mock_mode:
                await asyncio.sleep(1.5)
                return self._generate_mock_script(request)

            # 尝试从缓存获取
            if self.cache_service:
                cached_script = await self.cache_service.get_cached_novel_to_script(request)
                if cached_script:
                    logger.info("缓存命中: 小说转剧本结果")
                    return cached_script

            logger.info("缓存未命中，调用AI转换...")

            # 构建系统提示
            system_prompt = self._build_novel_to_script_system_prompt(request)
            human_prompt = self._build_novel_to_script_human_prompt(request)

            # 创建消息链
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]

            # 调用LLM
            logger.info("调用LLM转换小说...")
            response = await self.llm.ainvoke(messages)

            script_content = response.content

            # 缓存结果
            if self.cache_service:
                await self.cache_service.cache_novel_to_script_generation(request, script_content)
                logger.info("小说转剧本结果已缓存")

            logger.info(f"小说转换完成，长度: {len(script_content)} 字符")
            return script_content

        except Exception as e:
            logger.error(f"小说转换失败: {e}")
            raise

    def _build_novel_to_script_system_prompt(self, request: Dict[str, Any]) -> str:
        """构建小说转剧本的系统提示"""
        theme = request.get('theme', '爱情')
        length = request.get('length', '短篇')
        style = request.get('style', '浪漫喜剧')
        setting = request.get('setting', '现代都市')

        return f"""你是一个专业的剧本改编专家，擅长将小说改编成适合短视频平台的剧本。

创作要求:
1. 剧本类型: {length}剧本
2. 故事背景: {setting}
3. 剧本风格: {style}
4. 目标观众: 短视频平台用户

剧本结构要求:
1. 保持小说的核心情节和情感线索
2. 适合短视频平台的快节奏叙事
3. 增加视觉化描述，便于拍摄
4. 对话要简洁有力，符合人物性格
5. 场景转换要自然流畅

输出格式:
请按照标准的剧本格式输出，包括场景描述、角色对话和动作指示。
"""

    def _build_novel_to_script_human_prompt(self, request: Dict[str, Any]) -> str:
        """构建小说转剧本的用户提示"""
        title = request.get('title', '未命名剧本')
        novel_content = request.get('novel_content', '')
        characters = request.get('characters', [])
        excerpt_ratio = request.get('excerpt_ratio', 0.3)

        # 如果小说太长，截取一部分
        max_length = 5000  # 最大输入长度
        if len(novel_content) > max_length:
            excerpt_length = int(max_length * excerpt_ratio)
            # 截取开头和结尾
            excerpt_length_per_part = excerpt_length // 2
            novel_content = novel_content[:excerpt_length_per_part] + "\n...\n(中间内容省略)\n...\n" + novel_content[-excerpt_length_per_part:]

        character_str = "\n".join([f"- {char}" for char in characters]) if characters else "请根据小说自行设计2-3个主要角色"

        return f"""请将以下小说内容改编成名为《{title}》的剧本。

小说内容:
{novel_content[:3000]}...

角色设定:
{character_str}

改编要求:
1. 保持原小说的核心情节和情感主线
2. 将叙述性文字转化为适合拍摄的剧本格式
3. 增加场景描述和视觉元素
4. 对话要符合人物性格
5. 适合短视频平台的节奏

请输出完整的剧本内容。"""

    async def generate_script_from_outline(self, request: Dict[str, Any]) -> str:
        """根据剧本大纲生成完整剧本，支持缓存"""
        if not self._initialized:
            await self.initialize()

        try:
            logger.info(f"开始根据大纲生成剧本: {request.get('title', '未命名剧本')}")

            if self._mock_mode:
                await asyncio.sleep(1)
                return self._generate_mock_script(request)

            # 尝试从缓存获取
            if self.cache_service:
                cached_script = await self.cache_service.get_cached_outline_to_script(request)
                if cached_script:
                    logger.info("缓存命中: 大纲生成剧本结果")
                    return cached_script

            logger.info("缓存未命中，调用AI生成...")

            # 构建系统提示
            system_prompt = self._build_outline_to_script_system_prompt(request)
            human_prompt = self._build_outline_to_script_human_prompt(request)

            # 创建消息链
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]

            # 调用LLM（5分钟超时，复杂生成需要较长时间）
            logger.info("调用LLM生成剧本...")
            response = await self.llm.ainvoke(messages, config={"timeout": 600})

            script_content = response.content

            # 缓存结果
            if self.cache_service:
                await self.cache_service.cache_outline_to_script_generation(request, script_content)
                logger.info("大纲生成剧本结果已缓存")

            logger.info(f"剧本生成完成，长度: {len(script_content)} 字符")
            return script_content

        except Exception as e:
            logger.error(f"剧本生成失败: {e}")
            raise

    def _build_outline_to_script_system_prompt(self, request: Dict[str, Any]) -> str:
        """构建大纲生成剧本的系统提示（移植自 moyin-creator 的专业格式规范）"""
        theme = request.get('theme', '爱情')
        length = request.get('length', '短篇')
        style = request.get('style', '浪漫喜剧')
        setting = request.get('setting', '现代都市')

        return f"""你是一位专业的短剧编剧，擅长根据创意想法扩展为完整的、可直接拍摄的短剧剧本。

【剧本类型】
- 类型：{length}短剧（短篇约5-8分钟 / 中篇约15-20分钟 / 长篇约30-40分钟）
- 风格：{style}
- 主题：{theme}
- 背景：{setting}
- 目标平台：短视频平台

【输出格式 — 严格控制】

《TITLE》

**大纲：**
[一句话概括故事主线]

**人物小传：**
角色A：[年龄]，[身份]，[性格特点]，[外貌特征]
角色B：[年龄]，[身份]，[性格特点]，[外貌特征]
（至少2-4个主要角色）

**第一集**

**1-1 日 内 地点名称**
人物：角色A、角色B

△场景环境、氛围、灯光的简要描述

角色A：（表情/动作）对白内容

角色B：（表情/动作）对白内容

**1-2 夜 外 地点名称**
人物：角色A

△场景描述

...

**第二集**

**2-1 日 外 地点名称**
...

【核心规则 — 必须遵守】
1. 每集必须以 **第N集** 作为独立标题行
2. 场景头格式：**N-N 昼/夜 内/外 地点名**
3. 每个场景必须有 人物： 行
4. 动作描述以 △ 开头
5. 对白格式：角色名：（表情/动作）对白
6. 根据大纲合理分配集数（短篇3-5集，中篇5-8集，长篇8-12集）
7. 每集2-4个场景，每集有独立的起承转合
8. **时代一致性**：服装、道具、建筑、语言必须严格符合{setting}的时代背景
9. **风格一致性**：全片保持{style}的视觉和叙事风格

【质量标准】
- 对白自然口语化，贴合角色性格
- 每集结尾留悬念或情感钩子
- 视觉描写具体可执行（导演和摄影可直接理解）
- 避免过度文学化描述，用画面语言写作
"""

    def _build_outline_to_script_human_prompt(self, request: Dict[str, Any]) -> str:
        """构建大纲生成剧本的用户提示"""
        title = request.get('title', '未命名剧本')
        outline = request.get('outline', '')
        characters = request.get('characters', [])

        character_str = "\n".join([f"- {char}" for char in characters]) if characters else "请根据大纲自行设计适合的主要角色"

        return f"""请根据以下创意想法，创作完整的短剧剧本。

【创意想法/大纲】
{outline}

【角色参考】
{character_str}

【创作指引】
1. 如果想法比较简短，请充分发挥创意，构建完整的故事世界
2. 设计有记忆点的角色，每个角色要有鲜明的性格和外貌特征
3. 合理安排集数和场景，确保节奏紧凑适合短视频平台
4. 每集要有独立的看点，同时推动整体剧情发展

请输出完整剧本（含标题、大纲、人物小传、全部集数和场景）。"""