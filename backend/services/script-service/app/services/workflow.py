import logging
from typing import Dict, Any, Optional, TypedDict, List, Annotated
from enum import Enum
from operator import add
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.services.ai_service import AIService
from app.services.cache_service import get_cache_service
from app.services.graphrag_service import get_graphrag_service

logger = logging.getLogger(__name__)


def _last(a, b):
    """Reducer: always take the last value"""
    return b

def _merge_dicts(a, b):
    """Reducer: merge dicts with b taking precedence"""
    if a is None:
        return b
    if b is None:
        return a
    return {**a, **b}

def _or_none(a, b):
    """Reducer: take b if not None, else a"""
    return b if b is not None else a

class WorkflowState(TypedDict):
    """工作流状态定义"""
    request: Annotated[Dict[str, Any], _merge_dicts]
    current_step: Annotated[str, _last]
    result: Annotated[Optional[str], _or_none]
    error: Annotated[Optional[str], _or_none]
    metadata: Annotated[Dict[str, Any], _merge_dicts]
    script_draft: Annotated[Optional[str], _or_none]
    script_analyzed: Annotated[Optional[Dict[str, Any]], _or_none]
    script_optimized: Annotated[Optional[str], _or_none]
    script_final: Annotated[Optional[str], _or_none]


class WorkflowStep(Enum):
    """工作流步骤枚举"""
    INITIALIZE = "initialize"
    PREPARE_INPUT = "prepare_input"
    GENERATE_DRAFT = "generate_draft"
    ANALYZE_STRUCTURE = "analyze_structure"
    OPTIMIZE_SCRIPT = "optimize_script"
    FINALIZE = "finalize"
    HANDLE_ERROR = "handle_error"


class ScriptWorkflow:
    """剧本生成工作流，使用LangGraph，支持缓存和GraphRag上下文管理"""

    # 工作流类型
    FROM_NOVEL = "from_novel"      # 从小说生成
    FROM_OUTLINE = "from_outline"  # 从大纲生成
    FROM_SCRATCH = "from_scratch"  # 从零生成

    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service
        self.cache_service = None
        self.graphrag_service = None
        self.graph = None
        self.checkpointer = None
        self._initialized = False

    async def initialize(self):
        """初始化工作流图"""
        if self._initialized:
            return

        try:
            logger.info("初始化剧本生成工作流...")

            # 初始化缓存服务
            try:
                self.cache_service = await get_cache_service()
                logger.info("缓存服务初始化成功")
            except Exception as e:
                logger.warning(f"缓存服务初始化失败，将禁用缓存: {e}")
                self.cache_service = None

            # 初始化 GraphRag 服务
            try:
                self.graphrag_service = await get_graphrag_service()
                logger.info("GraphRag 服务初始化成功")
            except Exception as e:
                logger.warning(f"GraphRag 服务初始化失败，将禁用图谱上下文管理: {e}")
                self.graphrag_service = None

            # 创建检查点保存器（使用内存）
            self.checkpointer = MemorySaver()

            # 创建状态图
            workflow = StateGraph(WorkflowState)

            # 添加节点
            workflow.add_node(WorkflowStep.INITIALIZE.value, self._initialize_step)
            workflow.add_node(WorkflowStep.PREPARE_INPUT.value, self._prepare_input_step)
            workflow.add_node(WorkflowStep.GENERATE_DRAFT.value, self._generate_draft_step)
            workflow.add_node(WorkflowStep.ANALYZE_STRUCTURE.value, self._analyze_structure_step)
            workflow.add_node(WorkflowStep.OPTIMIZE_SCRIPT.value, self._optimize_script_step)
            workflow.add_node(WorkflowStep.FINALIZE.value, self._finalize_step)
            workflow.add_node(WorkflowStep.HANDLE_ERROR.value, self._handle_error_step)

            # 设置入口点
            workflow.set_entry_point(WorkflowStep.INITIALIZE.value)

            # 定义边（正常流程）
            workflow.add_edge(WorkflowStep.INITIALIZE.value, WorkflowStep.PREPARE_INPUT.value)
            workflow.add_edge(WorkflowStep.PREPARE_INPUT.value, WorkflowStep.GENERATE_DRAFT.value)
            workflow.add_edge(WorkflowStep.GENERATE_DRAFT.value, WorkflowStep.ANALYZE_STRUCTURE.value)
            workflow.add_edge(WorkflowStep.ANALYZE_STRUCTURE.value, WorkflowStep.OPTIMIZE_SCRIPT.value)
            workflow.add_edge(WorkflowStep.OPTIMIZE_SCRIPT.value, WorkflowStep.FINALIZE.value)
            workflow.add_edge(WorkflowStep.FINALIZE.value, END)

            # 错误处理边
            workflow.add_edge(WorkflowStep.HANDLE_ERROR.value, END)

            # 创建条件边（根据分析结果决定是否优化）
            def should_optimize(state: WorkflowState) -> str:
                """决定是否需要进行优化"""
                analysis = state.get("script_analyzed")
                if not analysis or "error" in analysis:
                    return WorkflowStep.FINALIZE.value

                # 简单的优化判断逻辑
                scenes_count = analysis.get("scenes_count", 0)
                pace = analysis.get("pace", "")

                if scenes_count < 3 or "快" in pace or "慢" in pace:
                    return WorkflowStep.OPTIMIZE_SCRIPT.value
                else:
                    return WorkflowStep.FINALIZE.value

            workflow.add_conditional_edges(
                WorkflowStep.ANALYZE_STRUCTURE.value,
                should_optimize,
                {
                    WorkflowStep.OPTIMIZE_SCRIPT.value: WorkflowStep.OPTIMIZE_SCRIPT.value,
                    WorkflowStep.FINALIZE.value: WorkflowStep.FINALIZE.value,
                }
            )

            # 编译图
            self.graph = workflow.compile(checkpointer=self.checkpointer)
            self._initialized = True

            logger.info("剧本生成工作流初始化完成")

        except Exception as e:
            logger.error(f"工作流初始化失败: {e}")
            raise

    async def _initialize_step(self, state: WorkflowState) -> WorkflowState:
        """初始化步骤"""
        logger.info("工作流: 初始化步骤")
        try:
            # 验证请求参数
            request = state["request"]
            if not request.get("title"):
                raise ValueError("剧本标题不能为空")

            # 初始化AI服务
            await self.ai_service.initialize()

            # 确定工作流类型
            workflow_type = self._determine_workflow_type(request)

            return {
                **state,
                "current_step": WorkflowStep.INITIALIZE.value,
                "metadata": {
                    **state.get("metadata", {}),
                    "validated": True,
                    "workflow_type": workflow_type,
                    "timestamp": "开始生成时间"
                }
            }
        except Exception as e:
            logger.error(f"初始化步骤失败: {e}")
            return {
                **state,
                "current_step": WorkflowStep.HANDLE_ERROR.value,
                "error": str(e)
            }

    def _determine_workflow_type(self, request: Dict[str, Any]) -> str:
        """确定工作流类型"""
        # 从小说生成
        if request.get("novel_content"):
            return ScriptWorkflow.FROM_NOVEL
        # 从大纲生成
        elif request.get("outline"):
            return ScriptWorkflow.FROM_OUTLINE
        # 从零生成
        else:
            return ScriptWorkflow.FROM_SCRATCH

    async def _prepare_input_step(self, state: WorkflowState) -> WorkflowState:
        """准备输入步骤 - 根据工作流类型准备输入"""
        logger.info("工作流: 准备输入步骤")
        try:
            request = state["request"]
            metadata = state.get("metadata", {})
            workflow_type = metadata.get("workflow_type", ScriptWorkflow.FROM_SCRATCH)

            # 根据不同工作流类型准备输入
            if workflow_type == ScriptWorkflow.FROM_NOVEL:
                # 从小说生成，将novel_content转换为script格式
                request = self._prepare_novel_request(request)
            elif workflow_type == ScriptWorkflow.FROM_OUTLINE:
                # 从大纲生成，将outline转换为script格式
                request = self._prepare_outline_request(request)

            return {
                **state,
                "request": request,
                "current_step": WorkflowStep.PREPARE_INPUT.value,
                "metadata": {
                    **metadata,
                    "input_prepared": True,
                    "workflow_type": workflow_type
                }
            }
        except Exception as e:
            logger.error(f"准备输入步骤失败: {e}")
            return {
                **state,
                "current_step": WorkflowStep.HANDLE_ERROR.value,
                "error": str(e)
            }

    async def _generate_draft_step(self, state: WorkflowState) -> WorkflowState:
        """生成草稿步骤"""
        logger.info("工作流: 生成草稿步骤")
        try:
            request = state["request"]
            metadata = state.get("metadata", {})
            workflow_type = metadata.get("workflow_type", ScriptWorkflow.FROM_SCRATCH)

            # 根据工作流类型选择不同的生成方法
            if workflow_type == ScriptWorkflow.FROM_NOVEL:
                script_draft = await self.ai_service.novel_to_script(request)
            elif workflow_type == ScriptWorkflow.FROM_OUTLINE:
                script_draft = await self.ai_service.generate_script_from_outline(request)
            else:
                script_draft = await self.ai_service.generate_script(request)

            return {
                **state,
                "current_step": WorkflowStep.GENERATE_DRAFT.value,
                "script_draft": script_draft,
                "metadata": {
                    **metadata,
                    "draft_generated": True,
                    "draft_length": len(script_draft)
                }
            }
        except Exception as e:
            logger.error(f"生成草稿步骤失败: {e}")
            return {
                **state,
                "current_step": WorkflowStep.HANDLE_ERROR.value,
                "error": str(e)
            }

    async def _analyze_structure_step(self, state: WorkflowState) -> WorkflowState:
        """分析结构步骤"""
        logger.info("工作流: 分析结构步骤")
        try:
            script_draft = state.get("script_draft")
            if not script_draft:
                raise ValueError("没有可分析的剧本草稿")

            analysis_result = await self.ai_service.analyze_script_structure(script_draft)

            return {
                **state,
                "current_step": WorkflowStep.ANALYZE_STRUCTURE.value,
                "script_analyzed": analysis_result,
                "metadata": {
                    **state.get("metadata", {}),
                    "analyzed": True,
                    "analysis_result": analysis_result.get("analysis", "")[:100]
                }
            }
        except Exception as e:
            logger.error(f"分析结构步骤失败: {e}")
            return {
                **state,
                "current_step": WorkflowStep.HANDLE_ERROR.value,
                "error": str(e)
            }

    async def _optimize_script_step(self, state: WorkflowState) -> WorkflowState:
        """优化剧本步骤"""
        logger.info("工作流: 优化剧本步骤")
        try:
            script_draft = state.get("script_draft")
            analysis_result = state.get("script_analyzed", {})

            if not script_draft:
                raise ValueError("���有可优化的剧本草稿")

            # 根据分析结果生成优化反馈
            feedback = self._generate_optimization_feedback(analysis_result)
            optimized_script = await self.ai_service.optimize_script(script_draft, feedback)

            return {
                **state,
                "current_step": WorkflowStep.OPTIMIZE_SCRIPT.value,
                "script_optimized": optimized_script,
                "metadata": {
                    **state.get("metadata", {}),
                    "optimized": True,
                    "optimization_feedback": feedback[:100] if feedback else ""
                }
            }
        except Exception as e:
            logger.error(f"优化剧本步骤失败: {e}")
            return {
                **state,
                "current_step": WorkflowStep.HANDLE_ERROR.value,
                "error": str(e)
            }

    async def _finalize_step(self, state: WorkflowState) -> WorkflowState:
        """最终化步骤"""
        logger.info("工作流: 最终化步骤")
        try:
            # 选择最终剧本版本（优先使用优化版本）
            final_script = state.get("script_optimized") or state.get("script_draft")

            if not final_script:
                raise ValueError("没有可用的剧本内容")

            # 清理优化步骤可能产生的元注释
            import re
            # 去掉 "好的，作为剧本优化专家..." 这类开头
            final_script = re.sub(r'^.*?(?:\n|。)作为.*?专家.*?(?:\n|。)', '', final_script, count=1)
            # 去掉 "以下是优化后的" "以下是优化版" 等过渡
            final_script = re.sub(r'^[^\n]*?优化[^\n]{0,20}(?:剧本|版本|内容)[^\n]*\n+', '', final_script)
            # 去掉可能的 markdown 分隔线
            final_script = re.sub(r'^---+[\s\n]+', '', final_script)
            # 去掉可能的 "###" 前缀
            final_script = re.sub(r'^###\s*', '', final_script)
            final_script = final_script.strip()

            if not final_script:
                raise ValueError("没有可用的剧本内容")

            # 使用 GraphRag 分析最终剧本，确保上下文一致性
            if self.graphrag_service and final_script:
                try:
                    script_id = state.get("metadata", {}).get("script_id", "default")
                    analysis_result = await self.graphrag_service.analyze_script(
                        script_id=script_id,
                        script_content=final_script
                    )
                    logger.info(f"GraphRag 分析完成: {analysis_result}")

                    # 添加图谱分析信息到元数据
                    if "metadata" not in state:
                        state["metadata"] = {}
                    state["metadata"]["graphrag_analysis"] = analysis_result
                except Exception as e:
                    logger.warning(f"GraphRag 分析失败: {e}")

            return {
                **state,
                "current_step": WorkflowStep.FINALIZE.value,
                "script_final": final_script,
                "result": final_script,
                "metadata": {
                    **state.get("metadata", {}),
                    "finalized": True,
                    "final_length": len(final_script)
                }
            }
        except Exception as e:
            logger.error(f"最终化步骤失败: {e}")
            return {
                **state,
                "current_step": WorkflowStep.HANDLE_ERROR.value,
                "error": str(e)
            }

    async def _handle_error_step(self, state: WorkflowState) -> WorkflowState:
        """错误处理步骤"""
        logger.error(f"工作流: 错误处理步骤 - {state.get('error', '未知错误')}")
        return {
            **state,
            "current_step": WorkflowStep.HANDLE_ERROR.value,
            "result": None,
            "metadata": {
                **state.get("metadata", {}),
                "error_handled": True,
                "error_message": state.get("error", "未知错误")
            }
        }

    def _prepare_novel_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """准备从小说生成的请求"""
        # 从小说请求转换为通用脚本生成请求
        return {
            **request,
            "title": request.get("title", "改编剧本"),
            "theme": request.get("theme", "爱情"),
            "length": request.get("length", "短篇"),
            "setting": request.get("setting", "现代都市"),
            "style": request.get("style", "浪漫喜剧"),
            "characters": request.get("characters", []),
            "additional_notes": "请根据以下小说内容改编成剧本:\n\n" + request.get("novel_content", "")[:2000]
        }

    def _prepare_outline_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """准备从大纲生成的请求"""
        # 从大纲请求转换为通用脚本生成请求
        return {
            **request,
            "title": request.get("title", "剧本"),
            "theme": request.get("theme", "爱情"),
            "length": request.get("length", "短篇"),
            "setting": request.get("setting", "现代都市"),
            "style": request.get("style", "浪漫喜剧"),
            "characters": request.get("characters", []),
            "additional_notes": "请根据以下大纲扩展成完整剧本:\n\n" + request.get("outline", "")
        }

    def _generate_optimization_feedback(self, analysis_result: Dict[str, Any]) -> str:
        """根据分析结果生成优化反馈"""
        if not analysis_result or "error" in analysis_result:
            return "请改进剧本结构和对话流畅度。"

        scenes_count = analysis_result.get("scenes_count", 0)
        pace = analysis_result.get("pace", "")
        analysis_text = analysis_result.get("analysis", "")

        feedback_parts = []

        if scenes_count < 3:
            feedback_parts.append(f"场景数量较少（{scenes_count}个），建议增加1-2个关键场景来丰富故事。")

        if "快" in pace:
            feedback_parts.append("故事节奏偏快，建议增加一些细节描写和角色互动来放缓节奏。")
        elif "慢" in pace:
            feedback_parts.append("故事节奏偏慢，建议精简部分场景或增加冲突来提升节奏。")

        if analysis_text:
            # 提取分析中的关键建议
            if "改进" in analysis_text or "建议" in analysis_text:
                feedback_parts.append(analysis_text[:200])

        if not feedback_parts:
            return "剧本结构良好，但可以进一步优化角色对话和情感表达。"

        return " ".join(feedback_parts)

    async def execute(self, request: Dict[str, Any], thread_id: Optional[str] = None) -> Dict[str, Any]:
        """执行工作流"""
        if not self._initialized:
            await self.initialize()

        try:
            logger.info(f"执行剧本生成工作流，请求: {request.get('title', '未命名剧本')}")

            # 检查缓存
            if self.cache_service:
                cached_result = await self.cache_service.get_cached_workflow_result(request)
                if cached_result:
                    logger.info("缓存命中: 完整工作流结果")
                    # 添加缓存标识到元数据
                    if isinstance(cached_result, dict):
                        cached_result["metadata"] = {
                            **cached_result.get("metadata", {}),
                            "cached": True,
                            "cache_hit": True
                        }
                    return cached_result

            logger.info("缓存未命中，执行完整工作流...")

            # 初始状态
            initial_state: WorkflowState = {
                "request": request,
                "current_step": WorkflowStep.INITIALIZE.value,
                "result": None,
                "error": None,
                "metadata": {},
                "script_draft": None,
                "script_analyzed": None,
                "script_optimized": None,
                "script_final": None
            }

            # 执行工作流
            config = {"configurable": {"thread_id": thread_id or f"script_{request.get('title', 'default')}"}}
            final_state = await self.graph.ainvoke(initial_state, config)

            # 提取结果
            result = {
                "success": final_state.get("result") is not None and final_state.get("error") is None,
                "script": final_state.get("result"),
                "error": final_state.get("error"),
                "metadata": final_state.get("metadata", {}),
                "workflow_steps": final_state.get("current_step", ""),
                "draft": final_state.get("script_draft"),
                "analysis": final_state.get("script_analyzed"),
                "optimized_version": final_state.get("script_optimized"),
            }

            if result["success"]:
                logger.info(f"工作流执行成功，生成剧本长度: {len(result['script'])} 字符")

                # 使用 GraphRag 确保上下文一致性
                if self.graphrag_service and final_state.get("script_final"):
                    try:
                        script_id = thread_id or str(request.get("title", "default"))
                        consistency_check = await self.graphrag_service.check_consistency(
                            script_id=script_id,
                            new_content=result["script"],
                            characters=request.get("characters", [])
                        )
                        if consistency_check:
                            result["consistency_check"] = consistency_check
                            if not consistency_check.get("is_consistent", True):
                                logger.warning(f"剧本一致性检查发现不一致: {consistency_check.get('inconsistencies')}")
                    except Exception as e:
                        logger.warning(f"GraphRag 一致性检查失败: {e}")

                # 缓存成功的结果
                if self.cache_service:
                    cache_success = await self.cache_service.cache_workflow_result(request, result)
                    if cache_success:
                        logger.info("工作流结果已缓存")
                    else:
                        logger.warning("工作流结果缓存失败")
            else:
                logger.error(f"工作流执行失败: {result['error']}")

            return result

        except Exception as e:
            logger.error(f"工作流执行异常: {e}")
            return {
                "success": False,
                "script": None,
                "error": str(e),
                "metadata": {},
                "workflow_steps": "error",
            }