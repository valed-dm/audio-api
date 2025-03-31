import logging
import socket
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from prometheus_client import Counter
from prometheus_client import Gauge
from sqlalchemy import event
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import Pool

from app.core.config import settings
from app.core.custom_logging import log_execution
from app.core.custom_logging import logger
from app.models import Base

# Simplified metrics with thread-safe implementation
DB_CONNECTION_GAUGE = Gauge(
    "db_connection_pool",
    "Current connection pool status",
    ["state"],
    multiprocess_mode="liveall",
)

DB_CONNECTION_ERRORS = Counter(
    "db_connection_errors",
    "Database connection errors",
    ["type"],
)


class DatabaseHealth:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.engine = None
            cls._instance.sessionmaker = None
        return cls._instance

    @log_execution(level=logging.DEBUG, show_args=True)
    async def initialize(self):
        """Initialize the database connection pool with health checks"""
        self.engine = create_async_engine(settings.database_url)

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.debug(f"Attempting to connect to database at: {settings.database_url}")
        self.engine = create_async_engine(
            settings.database_url,
            echo=settings.DEBUG,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_pre_ping=True,
            pool_recycle=settings.DB_POOL_RECYCLE,
            connect_args={
                "server_settings": {"application_name": settings.APP_NAME},
                "timeout": settings.DB_CONNECT_TIMEOUT,
            },
        )

        # Verify DNS resolution before proceeding
        await self._verify_connection_parameters()

        self.sessionmaker = async_sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            autoflush=False,
            class_=AsyncSession,
        )

        # Setup minimal monitoring
        self._setup_pool_monitoring(self.engine)

        # Test connection immediately
        await self.test_connection()

    @staticmethod
    async def _verify_connection_parameters():
        """Verify DNS and connection parameters"""
        try:
            db_url = settings.database_url
            host = db_url.split("@")[1].split("/")[0].split(":")[0]
            port = (
                int(db_url.split("@")[1].split("/")[0].split(":")[1])
                if ":" in db_url.split("@")[1].split("/")[0]
                else None
            )

            logger.info(f"Resolving database host: {host}")
            ip_addr = socket.gethostbyname(host)
            logger.info(
                f"Database host resolved to: {ip_addr}{f':{port}' if port else ''}"
            )

        except Exception as e:
            logger.critical(f"Database connection configuration error: {e}")
            raise

    @log_execution(level=logging.DEBUG, show_args=True)
    async def test_connection(self):
        """Test the database connection"""
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Database connection test successful")
        except Exception as e:
            logger.critical(f"Database connection test failed: {e}")
            raise

    @staticmethod
    def _setup_pool_monitoring(engine):
        """Lightweight connection pool monitoring"""

        @event.listens_for(Pool, "checkout")
        def on_checkout(dbapi_conn, connection_record, connection_proxy):
            DB_CONNECTION_GAUGE.labels("active").inc()
            if settings.DEBUG:
                logger.debug(
                    f"Connection checked out. Active: {DB_CONNECTION_GAUGE.labels('active')._value.get()}"
                )

        @event.listens_for(Pool, "checkin")
        def on_checkin(dbapi_conn, connection_record):
            DB_CONNECTION_GAUGE.labels("active").dec()
            if settings.DEBUG:
                logger.debug(
                    f"Connection returned. Active: {DB_CONNECTION_GAUGE.labels('active')._value.get()}"
                )

        @event.listens_for(Pool, "connect")
        def on_connect(dbapi_conn, connection_record):
            DB_CONNECTION_GAUGE.labels("idle").inc()
            if settings.DEBUG:
                logger.debug("New connection created")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Safe session provider with built-in error handling"""
        if self.sessionmaker is None:
            await self.initialize()

        session = self.sessionmaker()
        try:
            yield session
        except Exception as e:
            await session.rollback()
            DB_CONNECTION_ERRORS.labels(type(e).__name__).inc()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()

    @staticmethod
    async def _handle_session_error(session: AsyncSession | None):
        """Handle session errors gracefully"""
        if session is not None:
            try:
                await session.rollback()
            except Exception as rollback_error:  # noqa: BLE001
                logger.error(f"Session rollback failed: {rollback_error}")

    @staticmethod
    async def _safe_close(session: AsyncSession | None):
        """Safely close session with error handling"""
        if session is not None:
            try:
                await session.close()
            except Exception as close_error:  # noqa: BLE001
                logger.error(f"Session close failed: {close_error}")


# Initialize the singleton instance
db_health = DatabaseHealth()


async def get_db() -> AsyncSession:
    """Dependency that provides a database session"""
    return await db_health.get_session().__aenter__()
