import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, validator


class Settings(BaseSettings):
    PROJECT_NAME: str = "Search Service"
    VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    API_V1_STR: str = "/api/v1"

    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("SEARCH_SERVICE_PORT", 8005))

    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = [
        "http://localhost:3000", "http://localhost:8080",
        "https://shortdrama.com",
    ]

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB: int = int(os.getenv("REDIS_DB", 12))

    CONTENT_SERVICE_URL: str = os.getenv(
        "CONTENT_SERVICE_URL", "http://content-service:8081"
    )

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()
