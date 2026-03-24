#!/usr/bin/env python3
"""
LangChain和LangGraph集成使用示例

此脚本展示了如何在script-service中使用LangChain和LangGraph进行剧本生成。
在运行前，请确保已安装依赖：
pip install -r requirements.txt
"""

import asyncio
import os
import sys
import logging
from typing import Dict, Any

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def example_ai_service():
    """示例1: 使用AIService直接生成剧本"""
    logger.info("=== 示例1: 使用AIService直接生成剧本 ===")

    try:
        from app.services.ai_service import AIService

        # 创建AI服务实例
        ai_service = AIService()

        # 注意: 在实际使用中需要设置DEEPSEEK_API_KEY或OPENAI_API_KEY环境变量
        # 这里使用模拟模式，如果没有API密钥，将使用模拟数据

        # 构建剧本生成请求
        request = {
            "title": "咖啡馆的邂逅",
            "theme": "爱情",
            "length": "短篇",
            "style": "浪漫喜剧",
            "setting": "现代都市",
            "characters": ["阳光开朗的咖啡师", "内向害羞的作家"],
            "additional_notes": "希望有一个反转结局"
        }

        logger.info(f"请求参数: {request}")

        try:
            # 尝试初始化AI服务
            await ai_service.initialize()

            # 生成剧本
            script = await ai_service.generate_script(request)
            logger.info(f"生成的剧本 (前500字符):\n{script[:500]}...")

            # 分析剧本结构
            analysis = await ai_service.analyze_script_structure(script[:1000])
            logger.info(f"剧本分析结果: {analysis}")

        except Exception as e:
            logger.warning(f"AI服务调用失败 (可能需要API密钥): {e}")
            logger.info("在真实环境中，请设置DEEPSEEK_API_KEY或OPENAI_API_KEY环境变量")

    except ImportError as e:
        logger.error(f"导入失败: {e}")
        logger.info("请确保已安装所有依赖: pip install -r requirements.txt")


async def example_workflow():
    """示例2: 使用LangGraph工作流生成剧本"""
    logger.info("\n=== 示例2: 使用LangGraph工作流生成剧本 ===")

    try:
        from app.services.ai_service import AIService
        from app.services.workflow import ScriptWorkflow

        # 创建AI服务和工作流
        ai_service = AIService()
        workflow = ScriptWorkflow(ai_service)

        # 初始化工作流
        await workflow.initialize()

        # 构建请求
        request = {
            "title": "时光旅行的爱情",
            "theme": "科幻爱情",
            "length": "中篇",
            "style": "科幻浪漫",
            "setting": "未来世界",
            "characters": ["时间旅行者", "历史学家"],
            "additional_notes": "包含时间悖论元素"
        }

        logger.info(f"工作流请求: {request}")

        try:
            # 执行工作流
            result = await workflow.execute(request, thread_id="example_workflow_1")

            if result["success"]:
                logger.info("工作流执行成功!")
                logger.info(f"生成状态: {result.get('workflow_steps')}")
                logger.info(f"元数据: {result.get('metadata', {})}")

                if result.get("script"):
                    script = result["script"]
                    logger.info(f"最终剧本 (前300字符):\n{script[:300]}...")

                # 展示工作流中间结果
                if result.get("draft"):
                    logger.info(f"草稿版本已生成，长度: {len(result['draft'])} 字符")

                if result.get("analysis"):
                    logger.info(f"分析结果: {result['analysis']}")

                if result.get("optimized_version"):
                    logger.info(f"优化版本已生成，长度: {len(result['optimized_version'])} 字符")

            else:
                logger.error(f"工作流执行失败: {result.get('error')}")

        except Exception as e:
            logger.warning(f"工作流执行失败 (可能需要API密钥): {e}")
            logger.info("在真实环境中，请设置DEEPSEEK_API_KEY或OPENAI_API_KEY环境变量")

    except ImportError as e:
        logger.error(f"导入失败: {e}")
        logger.info("请确保已安装所有依赖: pip install -r requirements.txt")


async def example_script_service():
    """示例3: 使用完整的ScriptService（集成工作流）"""
    logger.info("\n=== 示例3: 使用完整的ScriptService ===")

    try:
        from app.services.script_service import ScriptService
        from app.schemas.script import ScriptGenerationRequest

        # 创建剧本服务
        script_service = ScriptService()

        # 初始化服务
        await script_service.initialize()

        # 创建请求对象
        request = ScriptGenerationRequest(
            title="校园青春物语",
            theme="青春",
            length="短篇",
            characters=["学霸班长", "体育特长生"],
            setting="高中校园",
            style="青春励志",
            user_id="test_user_123"
        )

        logger.info(f"剧本生成请求: {request.dict()}")

        # 模拟异步生成（在实际API中，这会触发后台任务）
        task_id = "test_task_001"

        # 注意: 这里仅演示，实际使用时通过API端点调用
        logger.info("在实际使用中，通过以下API端点生成剧本:")
        logger.info("POST /api/v1/scripts/generate")
        logger.info(f"请求体示例: {request.dict()}")

        # 演示获取剧本状态
        status = await script_service.get_generation_status(task_id)
        if status:
            logger.info(f"任务状态: {status}")
        else:
            logger.info("任务不存在（这是正常的，因为我们没有实际启动任务）")

        # 演示其他功能
        logger.info("\nScriptService其他功能:")
        logger.info("- generate_script_async(): 异步生成剧本")
        logger.info("- get_script(): 获取剧本详情")
        logger.info("- list_scripts(): 列出剧本")
        logger.info("- update_script(): 更新剧本")
        logger.info("- delete_script(): 删除剧本")
        logger.info("- regenerate_script(): 重新生成剧本")

    except ImportError as e:
        logger.error(f"导入失败: {e}")
        logger.info("请确保已安装所有依赖: pip install -r requirements.txt")


async def environment_setup_guide():
    """环境设置指南"""
    logger.info("\n" + "="*60)
    logger.info("环境设置指南")
    logger.info("="*60)

    logger.info("\n1. 安装依赖:")
    logger.info("   pip install -r requirements.txt")

    logger.info("\n2. 设置环境变量 (创建.env文件):")
    logger.info("""
   # AI配置 - 优先使用DeepSeek (推荐)
   DEEPSEEK_API_KEY=your_deepseek_api_key_here
   DEEPSEEK_API_BASE=https://api.deepseek.com
   DEEPSEEK_MODEL=deepseek-chat

   # OpenAI配置 (备用)
   OPENAI_API_KEY=your_openai_api_key_here
   MODEL_NAME=deepseek-chat
   OPENAI_MAX_TOKENS=2000
   OPENAI_TEMPERATURE=0.7

   # 可选: LangChain追踪（用于调试）
   LANGCHAIN_TRACING=false
   LANGCHAIN_API_KEY=your_langchain_api_key_here
   LANGCHAIN_PROJECT=shortdrama-script-service

   # 其他配置
   DEBUG=true
   LOG_LEVEL=INFO
   """)

    logger.info("\n3. 启动服务:")
    logger.info("   uvicorn main:app --host 0.0.0.0 --port 8000 --reload")

    logger.info("\n4. 测试API端点:")
    logger.info("   POST http://localhost:8000/api/v1/scripts/generate")
    logger.info("   GET  http://localhost:8000/api/v1/scripts/{script_id}")
    logger.info("   GET  http://localhost:8000/api/v1/scripts/{task_id}/status")

    logger.info("\n5. 工作流步骤说明:")
    logger.info("   - initialize: 验证请求并初始化")
    logger.info("   - generate_draft: 生成剧本草稿")
    logger.info("   - analyze_structure: 分析剧本结构")
    logger.info("   - optimize_script: 根据分析结果优化剧本")
    logger.info("   - finalize: 生成最终剧本")


async def main():
    """主函数"""
    logger.info("LangChain和LangGraph集成演示")
    logger.info("="*60)

    # 运行示例
    await example_ai_service()
    await example_workflow()
    await example_script_service()

    # 显示环境设置指南
    await environment_setup_guide()

    logger.info("\n" + "="*60)
    logger.info("演示完成!")
    logger.info("要实际使用，请设置DEEPSEEK_API_KEY或OPENAI_API_KEY环境变量并启动服务。")


if __name__ == "__main__":
    asyncio.run(main())