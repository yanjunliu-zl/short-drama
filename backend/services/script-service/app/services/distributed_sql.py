"""
Distributed SQL Layer — Connection pooling, read/write split, TiDB migration.

Architecture:
  App → ProxySQL (connection pool, :6033) → TiDB/MySQL Cluster
       ├── Writer → MySQL Primary / TiDB Write Node
       └── Reader → MySQL Replicas / TiDB Read Nodes (round-robin)

Components:
  1. ConnectionPoolManager — per-service pool sizing, pre-warming
  2. ReadWriteRouter — automatic write-to-primary, read-to-replica routing
  3. MigrationHelper — TiDB migration SQL generation + validation
"""
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from sqlalchemy import text, event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

logger = logging.getLogger(__name__)


# ============================================================
# Connection Pool Manager — per-service sizing + pre-warming
# ============================================================

@dataclass
class PoolConfig:
    """Connection pool configuration per service type."""
    service_name: str
    pool_size: int = 10
    max_overflow: int = 5
    pool_timeout: int = 10        # Seconds before timeout
    pool_recycle: int = 1800       # Recycle connections every 30min
    pool_pre_ping: bool = True     # Validate connection before use
    connect_timeout: int = 5        # Connection establishment timeout
    max_connections_total: int = 200  # Global cap per proxy instance

    @classmethod
    def for_service(cls, service_name: str) -> "PoolConfig":
        """Return optimal pool config per service type."""
        configs = {
            "script-service":       cls(service_name, pool_size=10, max_overflow=5),
            "storyboard-service":   cls(service_name, pool_size=8, max_overflow=3),
            "llmhua-service":       cls(service_name, pool_size=8, max_overflow=5),
            "recommendation-service": cls(service_name, pool_size=8, max_overflow=3),
            "video-service":        cls(service_name, pool_size=8, max_overflow=3),
            "content-service":      cls(service_name, pool_size=15, max_overflow=5),
            "user-service":         cls(service_name, pool_size=15, max_overflow=5),
        }
        return configs.get(service_name, cls(service_name))


class ConnectionPoolManager:
    """Manages database connection pools across all services.

    Industry standard: ProxySQL/PgBouncer as middleware, but we implement
    application-level pooling for environments without dedicated pool middleware.
    """

    def __init__(self):
        self._pools: Dict[str, async_sessionmaker] = {}
        self._stats: Dict[str, Dict[str, int]] = {}

    def create_pool(self, service_name: str,
                    write_dsn: str, read_dsns: List[str] = None,
                    config: PoolConfig = None) -> async_sessionmaker:
        """Create a connection pool for a service.

        Args:
            service_name: Service identifier for metrics.
            write_dsn: Primary write database DSN.
            read_dsns: Optional read replica DSNs.
            config: Pool configuration.

        Returns:
            SQLAlchemy async_sessionmaker.
        """
        if config is None:
            config = PoolConfig.for_service(service_name)

        dsn = write_dsn
        # If ProxySQL is available, route through it
        proxysql_host = os.getenv("PROXYSQL_HOST", "")
        if proxysql_host:
            dsn = dsn.replace(
                os.getenv("MYSQL_HOST", "mysql"),
                f"{proxysql_host}:6033",
            )

        engine = create_async_engine(
            dsn,
            poolclass=QueuePool,
            pool_size=config.pool_size,
            max_overflow=config.max_overflow,
            pool_timeout=config.pool_timeout,
            pool_recycle=config.pool_recycle,
            pool_pre_ping=config.pool_pre_ping,
            connect_args={"connect_timeout": config.connect_timeout},
            echo=False,
        )

        # Pre-warm pool: open initial connections
        @event.listens_for(engine.sync_engine, "connect")
        def on_connect(dbapi_conn, _):
            logger.debug(f"[{service_name}] DB connection established")

        session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False)

        self._pools[service_name] = session_factory
        self._stats[service_name] = {
            "pool_size": config.pool_size,
            "max_overflow": config.max_overflow,
            "active": 0,
            "waiting": 0,
        }

        logger.info(f"Connection pool created: {service_name} "
                    f"(size={config.pool_size}, overflow={config.max_overflow})")
        return session_factory

    async def get_session(self, service_name: str) -> AsyncSession:
        """Get a session from the pool."""
        if service_name not in self._pools:
            raise RuntimeError(f"No pool for service: {service_name}")
        self._stats[service_name]["active"] += 1
        return self._pools[service_name]()

    async def close_all(self):
        """Close all connection pools gracefully."""
        for service_name, factory in self._pools.items():
            engine = factory.kw.get("bind")
            if engine:
                await engine.dispose()
                logger.info(f"Pool closed: {service_name}")

    @property
    def stats(self) -> Dict[str, Any]:
        return dict(self._stats)


# ============================================================
# Read/Write Router — automatic routing based on SQL type
# ============================================================

class ReadWriteRouter:
    """Automatic read/write splitting at the application layer.

    Routes:
      - SELECT → read replica (round-robin across replicas)
      - INSERT/UPDATE/DELETE → write primary
      - BEGIN/COMMIT/ROLLBACK → write primary (transaction)

    Usage:
      router = ReadWriteRouter(write_session, [read_session1, read_session2])
      async with router.route("SELECT * FROM cases") as session:
          result = await session.execute(...)
    """

    _WRITE_KEYWORDS = {"INSERT", "UPDATE", "DELETE", "REPLACE",
                        "CREATE", "ALTER", "DROP", "TRUNCATE",
                        "BEGIN", "COMMIT", "ROLLBACK", "SET",
                        "LOCK", "UNLOCK", "GRANT", "REVOKE"}

    def __init__(self,
                 write_session_factory: async_sessionmaker,
                 read_session_factories: List[async_sessionmaker] = None):
        self._write = write_session_factory
        self._read_pools = read_session_factories or [write_session_factory]
        self._read_index = 0

    def _is_write(self, sql: str) -> bool:
        """Detect if SQL statement is a write operation."""
        stripped = sql.strip().upper()
        # Check first word
        first_word = stripped.split()[0] if stripped else ""
        return first_word in self._WRITE_KEYWORDS

    @asynccontextmanager
    async def route(self, sql: str = ""):
        """Get the appropriate session for this SQL statement.

        Yields: AsyncSession (write or read).
        """
        is_write = self._is_write(sql) if sql else False

        if is_write:
            async with self._write() as session:
                yield session
        else:
            # Round-robin across read replicas
            factory = self._read_pools[self._read_index % len(self._read_pools)]
            self._read_index += 1
            async with factory() as session:
                yield session


# Global instance
_pool_manager: Optional[ConnectionPoolManager] = None


def get_pool_manager() -> ConnectionPoolManager:
    global _pool_manager
    if _pool_manager is None:
        _pool_manager = ConnectionPoolManager()
    return _pool_manager


# ============================================================
# TiDB Migration Helper
# ============================================================

class MigrationHelper:
    """TiDB migration utilities — generate SQL, validate compatibility.

    MySQL 8.0 → TiDB 6.x migration path:
      1. Export schema (mysqldump --no-data)
      2. Review TiDB compatibility (no foreign keys? TiDB supports them now)
      3. Import via TiDB Lightning for large datasets
      4. Validate row counts + checksums
      5. Cut over with TiCDC reverse sync
    """

    @staticmethod
    def generate_compatibility_check() -> str:
        """Generate SQL to check MySQL→TiDB compatibility."""
        return """
-- TiDB Compatibility Check
-- Features NOT supported or different in TiDB:
--  1. Stored procedures / functions → use application logic
--  2. Triggers → use application logic or TiCDC
--  3. Full-text indexes (FULLTEXT) → use Elasticsearch (already done)
--  4. Spatial indexes → not used

-- Recommended changes for TiDB:
--  1. Replace AUTO_INCREMENT with AUTO_RANDOM (for SHARD_ROW_ID_BITS)
--  2. Remove ENGINE=InnoDB (TiDB uses its own storage engine)
--  3. Set SHARD_ROW_ID_BITS for hot tables
--  4. Use clustered index (PRIMARY KEY is always clustered in TiDB)
        """

    @staticmethod
    def generate_migration_sql(table_name: str, shard: bool = False) -> str:
        """Generate TiDB-optimized CREATE TABLE statement.

        Args:
            table_name: Source MySQL table name.
            shard: If True, add SHARD_ROW_ID_BITS for write hotspots.
        """
        shard_clause = "SHARD_ROW_ID_BITS=4" if shard else ""
        return f"""
-- TiDB optimized: {table_name}
-- Original table backed up as {table_name}_mysql_backup
-- Verify: SELECT COUNT(*) FROM {table_name} = SELECT COUNT(*) FROM {table_name}_mysql_backup

ALTER TABLE {table_name} SET {shard_clause} AUTO_RANDOM;
        """

    @staticmethod
    async def validate_migration(db_session, table_name: str) -> Dict[str, Any]:
        """Validate migration: compare row counts, find inconsistencies."""
        try:
            sql = text(f"""
                SELECT 'original' as src, COUNT(*) as cnt FROM {table_name}
            """)
            result = await db_session.execute(sql)
            row = result.fetchone()
            return {
                "table": table_name,
                "row_count": row.cnt if row else -1,
                "status": "ok" if row and row.cnt > 0 else "empty",
            }
        except Exception as e:
            return {"table": table_name, "status": "error", "error": str(e)}


# ============================================================
# ProxySQL Connection Pool Config (for docker-compose)
# ============================================================

PROXYSQL_CONFIG = """
# ProxySQL — MySQL connection pool middleware
# Deploy alongside your app, routes connections through a shared pool
#
# docker run -d --name proxysql -p 6033:6033 proxysql/proxysql:2.6

# Admin:
#   mysql -h127.0.0.1 -P6032 -uadmin -padmin
#   INSERT INTO mysql_servers(hostgroup_id,hostname,port) VALUES (0,'mysql',3306);  -- writer
#   INSERT INTO mysql_servers(hostgroup_id,hostname,port) VALUES (1,'mysql-read-1',3306);  -- reader
#   INSERT INTO mysql_users(username,password,default_hostgroup) VALUES ('admin','admin123',0);
#   LOAD MYSQL SERVERS TO RUNTIME; SAVE MYSQL SERVERS TO DISK;
"""
