#!/usr/bin/env python3
"""
缓存功能测试脚本

测试Redis缓存服务、AI服务缓存和工作流缓存功能。
在运行前，请确保Redis服务可用（可选）。
如果没有Redis，缓存服务将优雅降级。
"""

import asyncio
import os
import sys
import logging
import json
from typing import Dict, Any

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 设置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_cache_service():
    """测试缓存服务基本功能"""
    logger.info("=== 测试缓存服务基本功能 ===")

    try:
        from app.services.cache_service import CacheService

        # 创建缓存服务实例
        cache_service = CacheService()

        # 测试连接
        logger.info("测试Redis连接...")
        await cache_service.connect()

        # 检查缓存是否可用
        is_available = await cache_service.is_available()
        if is_available:
            logger.info("✅ Redis缓存服务可用")
        else:
            logger.warning("⚠️ Redis缓存服务不可用，后续测试将跳过实际缓存操作")

        # 测试基本缓存操作
        test_key = "test:basic"
        test_value = {"message": "Hello, Cache!", "number": 42}

        # 设置缓存
        set_success = await cache_service.set(test_key, test_value, ttl=10)
        if set_success:
            logger.info("✅ 缓存设置成功")
        else:
            logger.warning("⚠️ 缓存设置失败（可能Redis不可用）")

        # 获取缓存
        cached_value = await cache_service.get(test_key)
        if cached_value:
            logger.info(f"✅ 缓存获取成功: {cached_value}")
            assert cached_value["message"] == test_value["message"], "缓存值不匹配"
            assert cached_value["number"] == test_value["number"], "缓存值不匹配"
        else:
            logger.warning("⚠️ 缓存获取失败（可能Redis不可用或缓存未设置）")

        # 测试缓存存在检查
        exists = await cache_service.exists(test_key)
        logger.info(f"缓存键存在检查: {exists}")

        # 测试缓存删除
        delete_success = await cache_service.delete(test_key)
        if delete_success:
            logger.info("✅ 缓存删除成功")
        else:
            logger.warning("⚠️ 缓存删除失败")

        # 测试get_or_set
        async def expensive_operation(x: int) -> int:
            logger.info(f"执行昂贵操作: {x}")
            await asyncio.sleep(0.1)
            return x * 2

        result = await cache_service.get_or_set(
            "test:expensive", expensive_operation, ttl=5, x=21
        )
        logger.info(f"get_or_set结果: {result}")

        # 清理测试缓存
        await cache_service.clear_namespace("test")
        logger.info("测试缓存清理完成")

        # 断开连接
        await cache_service.disconnect()
        logger.info("✅ 缓存服务基本功能测试完成")

    except Exception as e:
        logger.error(f"❌ 缓存服务测试失败: {e}")
        import traceback
        traceback.print_exc()


async def test_ai_service_cache():
    """测试AI服务缓存功能"""
    logger.info("\n=== 测试AI服务缓存功能 ===")

    try:
        from app.services.ai_service import AIService

        # 创建AI服务实例
        ai_service = AIService()

        # 初始化AI服务（会同时初始化缓存服务）
        await ai_service.initialize()

        # 构建测试请求
        request = {
            "title": "测试剧本",
            "theme": "测试",
            "length": "短篇",
            "style": "测试风格",
            "setting": "测试背景",
            "characters": ["测试角色1", "测试角色2"],
            "additional_notes": "这是一个测试请求"
        }

        # 第一次调用 - 应该调用AI（或模拟）
        logger.info("第一次调用生成剧本...")
        try:
            script1 = await ai_service.generate_script(request)
            logger.info(f"第一次生成结果长度: {len(script1)} 字符")
        except Exception as e:
            # 如果没有OpenAI API密钥，会失败
            logger.warning(f"AI生成失败（可能需要API密钥）: {e}")
            # 使用模拟数据继续测试
            script1 = "模拟剧本内容"
            logger.info("使用模拟数据进行缓存测试")

        # 第二次调用 - 如果缓存可用，应该从缓存获取
        logger.info("第二次调用生成剧本...")
        script2 = await ai_service.generate_script(request)

        if script1 == script2:
            logger.info("✅ 两次调用结果相同（可能命中缓存）")
        else:
            logger.info("两次调用结果不同")

        # 测试分析缓存
        logger.info("测试剧本分析缓存...")
        analysis1 = await ai_service.analyze_script_structure(script1[:100])
        logger.info(f"分析结果: {analysis1}")

        analysis2 = await ai_service.analyze_script_structure(script1[:100])
        if analysis1 == analysis2:
            logger.info("✅ 两次分析结果相同（可能命中缓存）")
        else:
            logger.info("两次分析结果不同")

        # 测试优化缓存
        logger.info("测试剧本优化缓存...")
        feedback = "请改进角色对话"
        try:
            optimized1 = await ai_service.optimize_script(script1[:100], feedback)
            optimized2 = await ai_service.optimize_script(script1[:100], feedback)

            if optimized1 == optimized2:
                logger.info("✅ 两次优化结果相同（可能命中缓存）")
            else:
                logger.info("两次优化结果不同")
        except Exception as e:
            logger.warning(f"剧本优化测试跳过: {e}")

        logger.info("✅ AI服务缓存功能测试完成")

    except Exception as e:
        logger.error(f"❌ AI服务缓存测试失败: {e}")
        import traceback
        traceback.print_exc()


async def test_workflow_cache():
    """测试工作流缓存功能"""
    logger.info("\n=== 测试工作流缓存功能 ===")

    try:
        from app.services.ai_service import AIService
        from app.services.workflow import ScriptWorkflow

        # 创建AI服务和工作流
        ai_service = AIService()
        workflow = ScriptWorkflow(ai_service)

        # 初始化工作流
        await workflow.initialize()

        # 构建测试请求
        request = {
            "title": "工作流测试剧本",
            "theme": "爱情",
            "length": "短篇",
            "style": "浪漫喜剧",
            "setting": "现代都市",
            "characters": ["男主角", "女主角"],
            "additional_notes": "工作流缓存测试"
        }

        # 第一次执行工作流
        logger.info("第一次执行工作流...")
        result1 = await workflow.execute(request, thread_id="test_workflow_1")

        logger.info(f"第一次执行结果: 成功={result1.get('success')}, 步骤={result1.get('workflow_steps')}")

        # 检查是否有缓存标识
        if result1.get("metadata", {}).get("cached"):
            logger.info("⚠️ 第一次执行就命中了缓存（可能之前有残留缓存）")

        # 第二次执行相同请求 - 应该命中缓存
        logger.info("第二次执行相同请求...")
        result2 = await workflow.execute(request, thread_id="test_workflow_2")

        # 检查缓存命中
        if result2.get("metadata", {}).get("cache_hit"):
            logger.info("✅ 工作流缓存命中")
        else:
            logger.info("工作流缓存未命中")

        # 比较两次结果
        if result1.get("success") and result2.get("success"):
            script1 = result1.get("script", "")
            script2 = result2.get("script", "")
            if script1 and script2 and script1 == script2:
                logger.info("✅ 两次工作流结果相同")
            else:
                logger.info("两次工作流结果不同")

        # 测试不同请求不会命中缓存
        different_request = {**request, "title": "不同的剧本标题"}
        logger.info("执行不同请求...")
        result3 = await workflow.execute(different_request, thread_id="test_workflow_3")

        if result3.get("metadata", {}).get("cache_hit"):
            logger.warning("⚠️ 不同请求也命中了缓存（可能缓存键生成有问题）")
        else:
            logger.info("✅ 不同请求未命中缓存")

        # 清理工作流缓存
        if workflow.cache_service:
            cleared = await workflow.cache_service.clear_all_ai_cache()
            logger.info(f"清理AI缓存，删除了 {cleared} 个键")

        logger.info("✅ 工作流缓存功能测试完成")

    except Exception as e:
        logger.error(f"❌ 工作流缓存测试失败: {e}")
        import traceback
        traceback.print_exc()


async def test_cache_configuration():
    """测试缓存配置"""
    logger.info("\n=== 测试缓存配置 ===")

    try:
        from app.core.config import settings

        logger.info("缓存配置:")
        logger.info(f"  CACHE_ENABLED: {settings.CACHE_ENABLED}")
        logger.info(f"  CACHE_DEFAULT_TTL: {settings.CACHE_DEFAULT_TTL}")
        logger.info(f"  CACHE_SCRIPT_TTL: {settings.CACHE_SCRIPT_TTL}")
        logger.info(f"  CACHE_ANALYSIS_TTL: {settings.CACHE_ANALYSIS_TTL}")
        logger.info(f"  CACHE_OPTIMIZATION_TTL: {settings.CACHE_OPTIMIZATION_TTL}")
        logger.info(f"  CACHE_WORKFLOW_TTL: {settings.CACHE_WORKFLOW_TTL}")
        logger.info(f"  REDIS_HOST: {settings.REDIS_HOST}")
        logger.info(f"  REDIS_PORT: {settings.REDIS_PORT}")

        # 验证配置值
        assert isinstance(settings.CACHE_ENABLED, bool), "CACHE_ENABLED应该是布尔值"
        assert settings.CACHE_DEFAULT_TTL > 0, "CACHE_DEFAULT_TTL应该大于0"
        assert settings.CACHE_SCRIPT_TTL > 0, "CACHE_SCRIPT_TTL应该大于0"

        logger.info("✅ 缓存配置验证通过")

    except Exception as e:
        logger.error(f"❌ 缓存配置测试失败: {e}")
        import traceback
        traceback.print_exc()


async def test_cache_performance():
    """测试缓存性能"""
    logger.info("\n=== 测试缓存性能 ===")

    try:
        from app.services.cache_service import CacheService

        cache_service = CacheService()
        await cache_service.connect()

        if not await cache_service.is_available():
            logger.warning("Redis不可用，跳过性能测试")
            return

        # 测试缓存读写性能
        import time

        test_data = {"data": "x" * 1000}  # 1KB数据
        iterations = 100

        # 写入性能
        start = time.time()
        for i in range(iterations):
            key = f"perf:write:{i}"
            await cache_service.set(key, test_data, ttl=60)
        write_time = time.time() - start
        logger.info(f"写入 {iterations} 次耗时: {write_time:.3f}秒, 平均: {write_time/iterations*1000:.2f}毫秒/次")

        # 读取性能
        start = time.time()
        for i in range(iterations):
            key = f"perf:write:{i}"
            await cache_service.get(key)
        read_time = time.time() - start
        logger.info(f"读取 {iterations} 次耗时: {read_time:.3f}秒, 平均: {read_time/iterations*1000:.2f}毫秒/次")

        # 清理测试数据
        await cache_service.clear_namespace("perf")

        await cache_service.disconnect()
        logger.info("✅ 缓存性能测试完成")

    except Exception as e:
        logger.error(f"❌ 缓存性能测试失败: {e}")
        import traceback
        traceback.print_exc()


async def test_cache_edge_cases():
    """测试缓存边界情况"""
    logger.info("\n=== 测试缓存边界情况 ===")

    try:
        from app.services.cache_service import CacheService

        cache_service = CacheService()
        await cache_service.connect()

        # 测试空值缓存
        logger.info("测试空值缓存...")
        await cache_service.set("test:null", None, ttl=5)
        null_value = await cache_service.get("test:null")
        logger.info(f"空值缓存结果: {null_value}")

        # 测试大值缓存
        logger.info("测试大值缓存...")
        large_data = {"large": "x" * 10000}  # 10KB数据
        await cache_service.set("test:large", large_data, ttl=5)
        large_value = await cache_service.get("test:large")
        if large_value and len(str(large_value)) > 9000:
            logger.info("✅ 大值缓存成功")
        else:
            logger.warning("大值缓存可能有问题")

        # 测试特殊字符键
        logger.info("测试特殊字符键...")
        special_key = "test:special:!@#$%^&*()"
        await cache_service.set(special_key, "special", ttl=5)
        special_value = await cache_service.get(special_key)
        if special_value == "special":
            logger.info("✅ 特殊字符键缓存成功")
        else:
            logger.warning("特殊字符键缓存失败")

        # 测试缓存过期（模拟）
        logger.info("测试缓存过期...")
        await cache_service.set("test:expire", "expire_me", ttl=1)
        await asyncio.sleep(2)  # 等待过期
        expired_value = await cache_service.get("test:expire")
        if expired_value is None:
            logger.info("✅ 缓存过期功能正常")
        else:
            logger.warning("缓存可能未正确过期")

        # 清理
        await cache_service.clear_namespace("test")
        await cache_service.disconnect()

        logger.info("✅ 缓存边界情况测试完成")

    except Exception as e:
        logger.error(f"❌ 缓存边界情况测试失败: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主测试函数"""
    logger.info("=" * 60)
    logger.info("缓存优化功能测试")
    logger.info("=" * 60)

    # 运行所有测试
    await test_cache_configuration()
    await test_cache_service()
    await test_ai_service_cache()
    await test_workflow_cache()
    await test_cache_edge_cases()

    # 可选：性能测试（可能需要Redis）
    # await test_cache_performance()

    logger.info("\n" + "=" * 60)
    logger.info("所有缓存测试完成!")
    logger.info("=" * 60)

    # 总结建议
    logger.info("\n建议:")
    logger.info("1. 确保Redis服务运行: redis-server")
    logger.info("2. 设置环境变量: CACHE_ENABLED=true")
    logger.info("3. 调整缓存时间根据需求")
    logger.info("4. 监控缓存命中率优化性能")


if __name__ == "__main__":
    asyncio.run(main())