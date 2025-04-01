from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.auth import create_access_token
from app.auth.auth import verify_password
from app.auth.token_schema import Token
from app.core.config import settings
from app.core.custom_logging import logger
from app.db.session import get_db
from user.get import get_user

user_token_router = APIRouter()


@user_token_router.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    is_oauth: bool = False,
) -> Token:
    """
    Login for access token using either:
    - Username and password (regular login)
    - Just username (OAuth login)

    Args:
        form_data: Contains username, password, and optional scopes
        db: Database session
        is_oauth: Flag indicating OAuth login (bypasses password check)

    Returns:
        Token: JWT access token

    Raises:
        HTTPException: 401 if authentication fails
    """
    # Get user from database
    user = await get_user(db, form_data.username)

    if not user:
        logger.warning(f"Failed login attempt for username: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Handle OAuth users differently
    if user.is_oauth and not is_oauth:
        logger.warning(f"OAuth user attempted password login: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please login using your OAuth provider",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify credentials
    if not is_oauth:
        if not verify_password(form_data.password, user.hashed_password):
            logger.warning(f"Invalid password for user: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Check if user is disabled
    if user.disabled:
        logger.warning(f"Disabled user attempted login: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    # Create token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "scopes": form_data.scopes or user.scopes or ""},
        expires_delta=access_token_expires,
    )

    logger.info(f"Successful login for user: {user.username}")
    return Token(access_token=access_token, token_type=settings.TOKEN_TYPE)
