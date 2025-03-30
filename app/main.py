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
from app.core.custom_logging import logger


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
async def lifespan(a: FastAPI):
    if not hasattr(oauth, "yandex"):
        await async_logger.error("Yandex OAuth client not configured properly!")
    else:
        await async_logger.info("Yandex OAuth client initialized successfully")

    await async_logger.info("Startup application...")

    yield

    await async_logger.info("Shutdown application...")


def create_app() -> FastAPI:
    logger.info("Starting Audio API")
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
