"""
SQLAlchemy 数据库连接管理

提供异步 MySQL 连接引擎、会话工厂和依赖注入工具。
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# 构建异步数据库 URL
DATABASE_URL = (
    f"mysql+aiomysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    f"?charset=utf8mb4"
)

# 创建异步引擎
engine = create_async_engine(
    DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,  # 连接前检测可用性
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""
    pass


async def init_db():
    """初始化数据库 — 创建所有表"""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库表创建/验证完成")

        # Ensure V2 columns exist on existing tables (safe ALTER for upgrades)
        from sqlalchemy import text
        alter_sqls = [
            "ALTER TABLE scripts ADD COLUMN IF NOT EXISTS pdf_path VARCHAR(512) NULL",
            "ALTER TABLE scripts ADD COLUMN IF NOT EXISTS excel_path VARCHAR(512) NULL",
            "ALTER TABLE scripts ADD COLUMN IF NOT EXISTS character_graph JSON NULL",
            "ALTER TABLE scripts ADD COLUMN IF NOT EXISTS pipeline_version VARCHAR(10) NULL DEFAULT 'v1'",
            "ALTER TABLE scripts ADD COLUMN IF NOT EXISTS storyboard JSON NULL",
        ]
        async with engine.begin() as conn:
            for sql in alter_sqls:
                try:
                    await conn.execute(text(sql))
                except Exception:
                    pass  # MySQL < 8.0 or MariaDB doesn't support IF NOT EXISTS
        logger.info("数据库迁移检查完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise


async def close_db():
    """关闭数据库连接"""
    await engine.dispose()
    logger.info("数据库连接已关闭")


async def get_db() -> AsyncSession:
    """获取数据库会话（FastAPI 依赖注入）"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
