"""OpenTelemetry 链路追踪 — 自动探针 FastAPI, HTTP, DB"""
import os
import logging

logger = logging.getLogger(__name__)


def init_tracing(service_name: str, otlp_endpoint: str = None):
    """初始化 OpenTelemetry 链路追踪。
    通过环境变量 OTEL_EXPORTER_OTLP_ENDPOINT 配置 Collector 地址。
    自动探针: FastAPI, httpx, aiohttp, sqlalchemy, redis, celery
    """
    if os.getenv("OTEL_SDK_DISABLED", "").lower() == "true":
        logger.info(f"OpenTelemetry 已禁用 (OTEL_SDK_DISABLED=true)")
        return

    endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4318")
    os.environ.setdefault("OTEL_SERVICE_NAME", service_name)
    os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", endpoint)
    os.environ.setdefault("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf")
    os.environ.setdefault("OTEL_TRACES_SAMPLER", "parentbased_always_on")

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        # 创建 TracerProvider
        resource = Resource.create({SERVICE_NAME: service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        # 自动探针 — 覆盖所有 I/O 路径
        HTTPXClientInstrumentor().instrument()
        AioHttpClientInstrumentor().instrument()  # 跨服务调用 trace 传播
        RedisInstrumentor().instrument()
        SQLAlchemyInstrumentor().instrument()

        logger.info(f"OpenTelemetry 已初始化: {service_name} -> {endpoint}")
    except ImportError as e:
        logger.warning(f"OpenTelemetry 初始化跳过（缺少依赖）: {e}")
    except Exception as e:
        logger.warning(f"OpenTelemetry 初始化失败: {e}")


def instrument_fastapi(app):
    """在 FastAPI 应用上注册探针（需在 app 创建后调用）"""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI 探针已注册")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"FastAPI 探针注册失败: {e}")
