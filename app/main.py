from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1.admin.users import admin_router
from app.api.v1.auth.auth_token import user_token_router
from app.api.v1.auth.me import user_me_router
from app.api.v1.auth.register import user_register_router
from app.api.v1.auth.yandex_auth import yandex_auth_router
from app.auth.yandex_auth import oauth
from app.core.config import settings
from app.core.custom_logging import async_logger
from app.core.custom_logging import configure_logging
from app.core.custom_logging import logger

configure_logging()


def configure_cors(a: FastAPI) -> None:
    if not settings.CORS_ORIGINS:
        return
    a.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def setup_routers(a: FastAPI) -> None:
    a.include_router(yandex_auth_router, tags=["Yandex Authorization"], prefix="/api/v1")
    a.include_router(admin_router, tags=["Admin"])
    a.include_router(user_register_router, tags=["Users"])
    a.include_router(user_token_router, tags=["Users"])
    a.include_router(user_me_router, tags=["Users"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Asynchronous context manager for FastAPI lifespan events (startup, shutdown).
    """
    try:
        oauth_configured = hasattr(oauth, "yandex")
        log_message = (
            "Yandex OAuth client initialized successfully"
            if oauth_configured
            else "Yandex OAuth client not configured properly!"
        )

        if not oauth_configured:
            if async_logger:
                await async_logger.error(log_message)
            else:
                logger.error(log_message)
        else:
            if async_logger:
                await async_logger.info(log_message)
            else:
                logger.info(log_message)

        if async_logger:
            await async_logger.info("Startup application...")
        else:
            logger.info("Startup application...")

        yield  # Application is starting up

    finally:
        if async_logger:
            await async_logger.info("Shutdown application...")
            async_logger.shutdown()  # Properly shut down the async logger
        else:
            logger.info("Shutdown application...")


def create_app() -> FastAPI:
    logger.info("Starting Audio API")  # Use logger here (synchronous)
    application = FastAPI(
        title=settings.PROJECT_NAME,
        summary="Service for audio file uploads",
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    application.add_middleware(
        SessionMiddleware,
        secret_key=settings.SECRET_KEY,
        session_cookie="yandex_oauth_session",
        max_age=settings.SESSION_LIFETIME,
        same_site="lax",
        https_only=not settings.DEBUG,
    )

    configure_cors(application)
    setup_routers(application)

    return application


app = create_app()


# Example route (demonstrates logging)
@app.get("/")
async def read_root():
    """
    Example API endpoint.
    """
    logger.info("Accessed the root endpoint (synchronous)")
    if async_logger:
        await async_logger.debug(
            "Accessed the root endpoint (asynchronous)"
        )  # Example of async logging
    return {"Hello": "World"}
