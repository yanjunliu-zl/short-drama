import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, validator


class Settings(BaseSettings):
    # 项目配置
    PROJECT_NAME: str = "Script Generation Service"
    VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    API_V1_STR: str = "/api/v1"

    # 服务器配置
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))
    WORKERS: int = int(os.getenv("WORKERS", 4))  # Gunicorn workers数量
    THREADS: int = int(os.getenv("THREADS", 2))  # Gunicorn threads数量

    # 安全配置
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS配置
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "https://shortdrama.com",
    ]

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    ALLOWED_HOSTS: List[str] = ["*"]

    # 数据库配置 - 集群部署支持
    DB_HOST: str = os.getenv("DB_HOST", "mysql")
    DB_PORT: int = int(os.getenv("DB_PORT", 3306))
    DB_USER: str = os.getenv("DB_USER", "admin")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "admin123")
    DB_NAME: str = os.getenv("DB_NAME", "shortdrama")
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", 20))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", 10))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", 30))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", 3600))

    # Redis配置 - 支持集群部署
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD", None)
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
    REDIS_POOL_SIZE: int = int(os.getenv("REDIS_POOL_SIZE", 50))
    REDIS_CLUSTER_ENABLED: bool = os.getenv("REDIS_CLUSTER_ENABLED", "False").lower() == "true"
    REDIS_CLUSTER_NODES: List[str] = [
        node.strip() for node in os.getenv("REDIS_CLUSTER_NODES", "").split(",") if node.strip()
    ]

    # 缓存配置
    CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "True").lower() == "true"
    CACHE_DEFAULT_TTL: int = int(os.getenv("CACHE_DEFAULT_TTL", 3600))  # 默认1小时
    CACHE_SCRIPT_TTL: int = int(os.getenv("CACHE_SCRIPT_TTL", 7200))  # 剧本缓存2小时
    CACHE_ANALYSIS_TTL: int = int(os.getenv("CACHE_ANALYSIS_TTL", 3600))  # 分析缓存1小时
    CACHE_OPTIMIZATION_TTL: int = int(os.getenv("CACHE_OPTIMIZATION_TTL", 5400))  # 优化缓存1.5小时
    CACHE_WORKFLOW_TTL: int = int(os.getenv("CACHE_WORKFLOW_TTL", 10800))  # 工作流缓存3小时

    # RabbitMQ配置 - 集群部署支持
    RABBITMQ_HOST: str = os.getenv("RABBITMQ_HOST", "rabbitmq")
    RABBITMQ_PORT: int = int(os.getenv("RABBITMQ_PORT", 5672))
    RABBITMQ_USER: str = os.getenv("RABBITMQ_USER", "admin")
    RABBITMQ_PASSWORD: str = os.getenv("RABBITMQ_PASSWORD", "admin123")
    RABBITMQ_VHOST: str = os.getenv("RABBITMQ_VHOST", "/")
    RABBITMQ_HEARTBEAT: int = int(os.getenv("RABBITMQ_HEARTBEAT", 30))
    RABBITMQ_CHANNEL_MAX: int = int(os.getenv("RABBITMQ_CHANNEL_MAX", 65535))

    # AI模型配置
    MODEL_PATH: str = os.getenv("MODEL_PATH", "/app/models")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "deepseek-chat")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY", None)
    OPENAI_API_BASE: Optional[str] = os.getenv("OPENAI_API_BASE", None)
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", 16000))
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", 0.7))
    OPENAI_TIMEOUT: int = int(os.getenv("OPENAI_TIMEOUT", 600))
    # DeepSeek配置
    DEEPSEEK_API_KEY: Optional[str] = os.getenv("DEEPSEEK_API_KEY", None)
    DEEPSEEK_API_BASE: str = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    LANGCHAIN_TRACING: bool = os.getenv("LANGCHAIN_TRACING", "False").lower() == "true"
    LANGCHAIN_ENDPOINT: Optional[str] = os.getenv("LANGCHAIN_ENDPOINT", None)
    LANGCHAIN_API_KEY: Optional[str] = os.getenv("LANGCHAIN_API_KEY", None)
    LANGCHAIN_PROJECT: Optional[str] = os.getenv("LANGCHAIN_PROJECT", None)

    # Celery配置
    CELERY_BROKER_URL: str = os.getenv(
        "CELERY_BROKER_URL",
        f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}//"
    )
    CELERY_RESULT_BACKEND: str = os.getenv(
        "CELERY_RESULT_BACKEND",
        f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    )

    # 日志配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # 监控配置
    PROMETHEUS_ENABLED: bool = os.getenv("PROMETHEUS_ENABLED", "True").lower() == "true"
    PROMETHEUS_PORT: int = int(os.getenv("PROMETHEUS_PORT", 8001))

    # 限流配置
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "True").lower() == "true"
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", 100))
    RATE_LIMIT_PERIOD: int = int(os.getenv("RATE_LIMIT_PERIOD", 60))  # 秒

    # JWT配置
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # 重试配置
    RETRY_MAX_ATTEMPTS: int = int(os.getenv("RETRY_MAX_ATTEMPTS", 3))
    RETRY_INITIAL_DELAY: float = float(os.getenv("RETRY_INITIAL_DELAY", 0.5))
    RETRY_MAX_DELAY: float = float(os.getenv("RETRY_MAX_DELAY", 5.0))
    RETRY_BACKOFF_FACTOR: float = float(os.getenv("RETRY_BACKOFF_FACTOR", 2.0))

    # 超时配置
    REQUEST_TIMEOUT: float = float(os.getenv("REQUEST_TIMEOUT", 30.0))
    RESPONSE_TIMEOUT: float = float(os.getenv("RESPONSE_TIMEOUT", 60.0))

    # 熔断器配置
    CIRCUIT_BREAKER_ENABLED: bool = os.getenv("CIRCUIT_BREAKER_ENABLED", "True").lower() == "true"
    CIRCUIT_BREAKER_ERROR_THRESHOLD: int = int(os.getenv("CIRCUIT_BREAKER_ERROR_THRESHOLD", 5))
    CIRCUIT_BREAKER_RESET_TIMEOUT: int = int(os.getenv("CIRCUIT_BREAKER_RESET_TIMEOUT", 30))

    # 服务发现（Consul）
    CONSUL_ENABLED: bool = os.getenv("CONSUL_ENABLED", "True").lower() == "true"
    CONSUL_HOST: str = os.getenv("CONSUL_HOST", "consul")
    CONSUL_PORT: int = int(os.getenv("CONSUL_PORT", 8500))
    CONSUL_DATA_CENTER: str = os.getenv("CONSUL_DATA_CENTER", "dc1")

    # GraphRag 配置
    GRAPHRAG_ENABLED: bool = os.getenv("GRAPHRAG_ENABLED", "True").lower() == "true"
    GRAPHRAG_NEO4J_URI: str = os.getenv("GRAPHRAG_NEO4J_URI", "bolt://localhost:7687")
    GRAPHRAG_NEO4J_USERNAME: str = os.getenv("GRAPHRAG_NEO4J_USERNAME", "neo4j")
    GRAPHRAG_NEO4J_PASSWORD: str = os.getenv("GRAPHRAG_NEO4J_PASSWORD", "password")
    GRAPHRAG_VECTOR_DB: str = os.getenv("GRAPHRAG_VECTOR_DB", "memory")  # memory, chroma, pinecone

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()
