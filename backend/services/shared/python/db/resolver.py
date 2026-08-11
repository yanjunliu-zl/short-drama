"""DBResolver — SQLAlchemy async read/write splitting.

Provides automatic routing of SELECT queries to read replicas
and INSERT/UPDATE/DELETE to the primary writer.

Usage:
    resolver = DBResolver(
        writer_url="mysql+aiomysql://user:pass@mysql:3306/shortdrama",
        reader_urls=[
            "mysql+aiomysql://user:pass@mysql-read-0.mysql-read:3306/shortdrama",
            "mysql+aiomysql://user:pass@mysql-read-1.mysql-read:3306/shortdrama",
        ],
    )
    # For writes:
    async with resolver.writer_session() as session: ...
    # For reads:
    async with resolver.reader_session() as session: ...
"""
import logging
import random
from contextlib import asynccontextmanager
from typing import AsyncGenerator, List

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)


class DBResolver:
    """Read/write splitting resolver for SQLAlchemy async engines.

    Holds one writer engine and N reader engines.
    Sessions are obtained via async context managers.
    """

    def __init__(
        self,
        writer_url: str,
        reader_urls: List[str],
        pool_size: int = 10,
        max_overflow: int = 5,
        pool_recycle: int = 3600,
        echo: bool = False,
    ):
        self.writer_engine = create_async_engine(
            writer_url,
            echo=echo,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=30,
            pool_recycle=pool_recycle,
            pool_pre_ping=True,
        )
        self.writer_sessionmaker = async_sessionmaker(
            self.writer_engine, class_=AsyncSession, expire_on_commit=False
        )

        self.reader_engines = []
        self.reader_sessionmakers = []
        for url in reader_urls:
            if url:
                engine = create_async_engine(
                    url,
                    echo=echo,
                    pool_size=max(pool_size // 2, 5),
                    max_overflow=max_overflow,
                    pool_timeout=30,
                    pool_recycle=pool_recycle,
                    pool_pre_ping=True,
                )
                self.reader_engines.append(engine)
                self.reader_sessionmakers.append(
                    async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
                )

        # Fallback: use writer for reads if no readers configured
        if not self.reader_sessionmakers:
            logger.warning("DBResolver: no read replicas configured, using writer for reads")
            self.reader_engines.append(self.writer_engine)
            self.reader_sessionmakers.append(self.writer_sessionmaker)

        logger.info(
            "DBResolver initialized: 1 writer, %d reader(s), pool_size=%d",
            len(self.reader_sessionmakers), pool_size,
        )

    @asynccontextmanager
    async def writer_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a session connected to the primary (writer)."""
        async with self.writer_sessionmaker() as session:
            yield session

    @asynccontextmanager
    async def reader_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a session connected to a random read replica."""
        sm = random.choice(self.reader_sessionmakers)
        async with sm() as session:
            yield session

    async def close(self):
        """Close all engine connections."""
        await self.writer_engine.dispose()
        for engine in self.reader_engines:
            if engine is not self.writer_engine:
                await engine.dispose()
        logger.info("DBResolver: all connections closed")
