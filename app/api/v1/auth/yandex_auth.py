import secrets
import string
from typing import Annotated

import aiohttp
from authlib.integrations.base_client import MissingTokenError
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import EmailStr
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from starlette.responses import RedirectResponse

from app.api.v1.auth.auth_token import login_for_access_token
from app.auth.token_schema import Token
from app.auth.yandex_auth import oauth
from app.core.config import settings
from app.core.custom_logging import logger
from app.db.session import get_db
from app.models.users import User
from user.create import create_user
from user.user import AuthResponse
from user.user import UserCreate
from user.user import UserUpdate
from user.user import YandexUserInfo

yandex_auth_router = APIRouter()


def generate_strong_temp_password() -> str:
    """Generates a strong temporary password with mixed case, numbers and symbols"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(16))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in "!@#$%^&*" for c in password)
        ):
            return password


@yandex_auth_router.get("/auth/yandex")
# @log_execution(level=logging.DEBUG, show_args=True) # Add your decorator if needed
async def login_via_yandex(request: Request):
    """Initiates the Yandex OAuth flow."""
    redirect_uri = settings.YANDEX_REDIRECT_URI
    # Authlib's authorize_redirect will handle generating and storing the state
    logger.info(f"Initiating Yandex OAuth redirect to: {redirect_uri}")
    try:
        # The state parameter is optional here for authorize_redirect;
        # Authlib generates one if not provided and stores it.
        return await oauth.yandex.authorize_redirect(request, redirect_uri)
    except Exception as e:
        logger.error(f"Error during Yandex authorize_redirect: {e!s}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to initiate Yandex login."
        ) from e


@yandex_auth_router.get("/auth/yandex/callback", response_model=AuthResponse)
async def yandex_callback(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    code: str | None = None,
    error: str | None = None,
) -> AuthResponse | RedirectResponse:
    """Handles the callback from Yandex after user authentication."""
    try:
        # Log the incoming request details for debugging
        logger.debug(f"Yandex callback received. URL: {request.url}")
        logger.debug(f"Session contents on callback entry: {dict(request.session)}")
        incoming_state = request.query_params.get("state")
        logger.debug(f"Received state from URL: {incoming_state}")
        logger.debug(f"Received code from URL: {code}")
        logger.debug(f"Received error from URL: {error}")

        # 1. Check for errors from Yandex first
        if error:
            error_description = request.query_params.get(
                "error_description", "No description provided."
            )
            logger.error(f"Yandex returned an error: {error} - {error_description}")
            # Redirect to login page with error. Use RedirectResponse for redirects
            return RedirectResponse(
                url="/register?error=yandex_auth_failed",
                status_code=status.HTTP_302_FOUND,  # Use 302 for redirects
            )

        # 2. Check if code is missing
        if not code:
            logger.error("Yandex callback missing 'code' parameter without an 'error'.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,  # Use correct HTTP status code
                detail="Invalid callback request from Yandex: missing code.",
            )

        # 3. Exchange code for token with retry mechanism
        try:
            token = await oauth.yandex.authorize_access_token(request)
            logger.debug("Successfully obtained token via authorize_access_token.")
            logger.debug(
                f"Token data received (structure check): { {k: type(v).__name__ for k, v in token.items()} }"
            )
        except (TimeoutError, aiohttp.ClientError) as e:
            logger.error(f"Network error during token exchange: {e!s}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not connect to Yandex authentication service. Please try again later.",
            ) from e
        except Exception as e:
            logger.error(f"Error during token exchange: {e!s}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,  # Use correct HTTP status code
                detail="Failed to exchange code for access token.",
            ) from e

        # 4. Fetch user info with network error handling
        try:
            logger.info("Fetching user info using oauth.yandex.userinfo...")
            yandex_user_raw = await oauth.yandex.userinfo(token=token)
            yandex_user_raw = dict(yandex_user_raw)
            logger.info(f"Yandex user info parsed via userinfo: {yandex_user_raw}")
            logger.info(f"Yandex user info type: {type(yandex_user_raw)}")

            if not yandex_user_raw:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Empty user data received from Yandex",
                )

            # Validate and parse user data
            try:
                yandex_user = YandexUserInfo(**yandex_user_raw)
                logger.info(f"Yandex user: {type(yandex_user)}")
                logger.info(f"Yandex user data: {yandex_user.model_dump()}")
            except ValidationError as e:
                logger.error(f"Validation error for Yandex user data: {e!s}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid user data received from Yandex",
                ) from e

            # Check existing user by email
            try:
                db_user_by_email = await db.execute(
                    select(User).where(User.email == yandex_user.default_email)
                )
                existing_user = db_user_by_email.scalars().first()
            except SQLAlchemyError as e:
                logger.error(f"Database error when checking existing user: {e!s}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Database service unavailable",
                ) from e

            if existing_user:
                logger.info(f"User found: ===> {existing_user}")
                if not existing_user.is_oauth:
                    logger.warning(f"Email conflict: {yandex_user.default_email}")
                    # Redirect to login page with email conflict error
                    return RedirectResponse(
                        url="/register",
                        status_code=status.HTTP_302_FOUND,
                    )

                # OAuth login - bypass password check
                try:
                    # Log the OAuth2PasswordRequestForm data before sending it
                    form_data = OAuth2PasswordRequestForm(
                        username=existing_user.username,
                        password=settings.PASSWORD_STUB,
                    )
                    logger.debug(
                        f"OAuth2PasswordRequestForm data: username={form_data.username}, password={form_data.password}"
                    )  # Log data
                    token: Token = await login_for_access_token(
                        form_data, is_oauth=True
                    )  # Type hint for token

                    logger.debug(
                        f"Token received from login_for_access_token: {token}"
                    )  # Log token

                except Exception as e:
                    logger.error(f"Error generating access token: {e!s}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Error generating access token",
                    ) from e

                return AuthResponse(
                    access_token=token.access_token,
                    token_type=token.token_type,
                    user_info=UserUpdate(
                        username=existing_user.username,
                        email=existing_user.email,
                        full_name=existing_user.full_name,
                        password=settings.USE_VALID_PASWORD,
                    ),
                    is_temporary_password=False,
                )

            # New user creation
            temp_password = generate_strong_temp_password()

            # Create full name from first and last names if available
            full_name = (
                f"{yandex_user.first_name or ''} {yandex_user.last_name or ''}".strip()
            )
            if not full_name:
                full_name = yandex_user.display_name or yandex_user.login

            try:
                try:
                    email = EmailStr.validate(yandex_user.default_email)
                except ValueError as e:
                    logger.error(
                        f"Invalid email format from Yandex: {yandex_user.default_email}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid email address received from Yandex",
                    ) from e
                db_user = await create_user(
                    user=UserCreate(
                        username=yandex_user.login,
                        email=email,
                        full_name=full_name,
                        password=temp_password,
                        disabled=False,
                        scopes="me listener",
                        is_oauth=True,
                        oauth_provider="yandex",
                        oauth_id=yandex_user.id,
                    ),
                    db=db,
                )
                logger.info(f"New user created: ===> {db_user}, {temp_password}")

                # Generate access token
                try:
                    # Log the OAuth2PasswordRequestForm data before sending it.
                    form_data = OAuth2PasswordRequestForm(
                        username=db_user.username,
                        password=temp_password,  # Using temp password
                        scope="",  # Add scope
                    )
                    logger.debug(
                        f"OAuth2PasswordRequestForm data: username={form_data.username}, password=**TEMP_PASSWORD**"
                    )  # Log data
                    token: Token = await login_for_access_token(
                        form_data
                    )  # Type hint for token
                    logger.debug(
                        f"Token received from login_for_access_token: {token}"
                    )  # Log token

                except Exception as e:
                    logger.error(f"Error generating access token for new user: {e!s}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Error generating access token",
                    ) from e

                return AuthResponse(
                    access_token=token.access_token,
                    token_type=token.token_type,
                    user_info=UserUpdate(
                        username=db_user.username,
                        email=db_user.email,
                        full_name=db_user.full_name,
                        password=settings.TEMP_PASSWORD_REMINDER,
                    ),
                    temporary_password=temp_password,
                    is_temporary_password=True,
                )

            except SQLAlchemyError as e:
                logger.error(f"Database error when creating user: {e!s}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Database service unavailable",
                ) from e

        except (TimeoutError, aiohttp.ClientError) as e:
            logger.error(f"Network error during user info fetch: {e!s}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not connect to Yandex user info service. Please try again later.",
            ) from e

        except MissingTokenError as e:
            logger.error(f"Missing token error: {e!s}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token received from Yandex",
            ) from e

        except Exception as e:
            logger.error(f"Unexpected error during user processing: {e!s}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while processing your login.",
            ) from e

    except HTTPException:
        # Re-raise HTTPExceptions we've already handled
        raise
    except Exception as e:
        logger.error(f"Unexpected error in Yandex callback: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during authentication.",
        ) from e
