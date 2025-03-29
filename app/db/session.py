import logging
from collections.abc import AsyncGenerator

from prometheus_client import Counter
from prometheus_client import Gauge
from sqlalchemy import Engine
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.core.logging import log_decorator
from app.core.logging import logger

# Metrics (initialize only once)
CONNECTION_GAUGE = Gauge(
    "db_connection_pool", "Current connection pool status", ["state"]
)
CONNECTION_ERRORS = Counter(
    "db_connection_errors", "Database connection errors", ["type"]
)


def get_gauge_value(gauge: Gauge, *labels) -> float:
    """Safely gets current gauge value with fallbacks"""
    try:
        return gauge.labels(*labels)._value.get()
    except AttributeError:
        try:
            # Legacy client fallback
            collected = list(gauge.labels(*labels).collect())
            if collected and hasattr(collected[0], "samples"):
                samples = list(collected[0].samples)
                return samples[0].value if samples else 0.0
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to read gauge value: {e!s}")
        return 0.0


def monitor_connection_pool(eng: Engine) -> None:
    """Enhanced connection pool monitoring with fail-safe metrics"""

    @event.listens_for(eng, "connect")
    def track_connect(dbapi_conn, connection_record):
        idle_count = get_gauge_value(CONNECTION_GAUGE, "idle")
        logger.debug(f"Connection opened (Total idle: {idle_count})")
        CONNECTION_GAUGE.labels("idle").inc()

    @event.listens_for(eng, "checkout")
    def track_checkout(dbapi_conn, connection_record, connection_proxy):
        CONNECTION_GAUGE.labels("idle").dec()
        CONNECTION_GAUGE.labels("active").inc()
        logger.debug("Connection checked out")

    @event.listens_for(eng, "checkin")
    def track_checkin(dbapi_conn, connection_record):
        CONNECTION_GAUGE.labels("active").dec()
        CONNECTION_GAUGE.labels("idle").inc()
        logger.debug("Connection returned to pool")

    @event.listens_for(eng, "close")
    def track_close(dbapi_conn, connection_record):
        CONNECTION_GAUGE.labels("idle").dec()
        logger.debug("Connection closed")

    @event.listens_for(eng, "handle_error")
    def track_errors(exception_context):
        error_type = "unknown"
        try:
            error_type = type(exception_context.original_exception).__name__
        except AttributeError:
            pass
        CONNECTION_ERRORS.labels(error_type).inc()
        logger.error(f"DB error occurred: {error_type}")


engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={"server_settings": {"application_name": "audio_api"}},
)

monitor_connection_pool(engine.sync_engine)


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    class_=AsyncSession,
)


@log_decorator(level=logging.DEBUG)
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides database sessions with automatic cleanup.

    Usage in FastAPI:
    ```python
    @router.get("/")
    async def example(db: AsyncSession = Depends(get_db)):
        # Use db session
    ```
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
