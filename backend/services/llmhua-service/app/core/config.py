import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, validator


class Settings(BaseSettings):
    # 项目配置
    PROJECT_NAME: str = "Llmhua Video Generation Service"
    VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    API_V1_STR: str = "/api/v1"

    # 服务器配置
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8002))

    # 安全配置
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS配置
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:8000",
        "https://shortdrama.com",
    ]

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1", "0.0.0.0"]

    # 数据库配置
    DB_HOST: str = os.getenv("DB_HOST", "mysql")
    DB_PORT: int = int(os.getenv("DB_PORT", 3306))
    DB_USER: str = os.getenv("DB_USER", "admin")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "admin123")
    DB_NAME: str = os.getenv("DB_NAME", "shortdrama")

    # Redis配置
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD", None)
    REDIS_DB: int = int(os.getenv("REDIS_DB", 4))

    # Seedance/Seedream服务配置 (火山引擎 Ark API)
    SEEDANCE_API_URL: str = os.getenv("SEEDANCE_API_URL", "https://ark.cn-beijing.volces.com/api/v3")
    SEEDANCE_API_KEY: Optional[str] = os.getenv("SEEDANCE_API_KEY", None)
    SEEDANCE_IMAGE_MODEL: str = os.getenv("SEEDANCE_IMAGE_MODEL", "doubao-seedream-4-5-251128")
    SEEDANCE_VIDEO_MODEL: str = os.getenv("SEEDANCE_VIDEO_MODEL", "doubao-seedance-2-0-260128")
    SEEDANCE_TIMEOUT: int = int(os.getenv("SEEDANCE_TIMEOUT", 300))
    # Platform compliance — 红果短剧/快手短剧 standard
    PORTRAIT_MODE: bool = os.getenv("PORTRAIT_MODE", "true").lower() == "true"  # 9:16 vertical
    VIDEO_FPS: int = int(os.getenv("VIDEO_FPS", 30))  # 25 or 30 fps
    VIDEO_RESOLUTION: str = os.getenv("VIDEO_RESOLUTION", "720p")  # 720p or 1080p

    # 图像生成参数
    IMAGE_WIDTH: int = int(os.getenv("IMAGE_WIDTH", 1920))
    IMAGE_HEIGHT: int = int(os.getenv("IMAGE_HEIGHT", 1080))
    IMAGE_STEPS: int = int(os.getenv("IMAGE_STEPS", 30))
    IMAGE_SCALE: float = float(os.getenv("IMAGE_SCALE", 7.5))
    IMAGE_SAMPLER: str = os.getenv("IMAGE_SAMPLER", "DPM++ 2M Karras")

    # 视频生成参数
    VIDEO_FRAMERATE: int = int(os.getenv("VIDEO_FRAMERATE", 24))
    VIDEO_STEPS: int = int(os.getenv("VIDEO_STEPS", 30))
    VIDEO_SCALE: float = float(os.getenv("VIDEO_SCALE", 7.5))
    VIDEO_STRENGTH: float = float(os.getenv("VIDEO_STRENGTH", 0.75))

    # 缓存配置
    CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "True").lower() == "true"
    CACHE_DEFAULT_TTL: int = int(os.getenv("CACHE_DEFAULT_TTL", 3600))
    CACHE_IMAGE_TTL: int = int(os.getenv("CACHE_IMAGE_TTL", 7200))
    CACHE_VIDEO_TTL: int = int(os.getenv("CACHE_VIDEO_TTL", 86400))

    # Ceph/RGW 对象存储配置
    STORAGE_TYPE: str = os.getenv("STORAGE_TYPE", "ceph")  # ceph, s3, minio, local
    STORAGE_ENDPOINT: str = os.getenv("STORAGE_ENDPOINT", "http://ceph-rgw:7480")
    STORAGE_ACCESS_KEY: str = os.getenv("STORAGE_ACCESS_KEY", "admin")
    STORAGE_SECRET_KEY: str = os.getenv("STORAGE_SECRET_KEY", "admin123")
    STORAGE_BUCKET: str = os.getenv("STORAGE_BUCKET", "short-drama")
    STORAGE_REGION: str = os.getenv("STORAGE_REGION", "us-east-1")
    STORAGE_LOCAL_BASE_PATH: str = os.getenv("STORAGE_LOCAL_BASE_PATH", "/app/storage")
    STORAGE_PUBLIC_ENDPOINT: str = os.getenv("STORAGE_PUBLIC_ENDPOINT", "http://localhost:9000")

    # SSE streaming configuration
    SSE_STREAMING_ENABLED: bool = os.getenv("SSE_STREAMING_ENABLED", "True").lower() == "true"
    SSE_HEARTBEAT_INTERVAL: int = int(os.getenv("SSE_HEARTBEAT_INTERVAL", 15))

    # 日志配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()
