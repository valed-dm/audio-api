"""Get current authorized user module."""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Security
from fastapi import status
from fastapi.security import SecurityScopes
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.token_schema import TokenData
from app.auth.token_schema import oauth2_scheme
from app.core.config import settings
from app.db.session import get_db
from app.models.users import User


async def get_user(db: AsyncSession, username: str | None) -> User | None:
    """
    Retrieve a user from the database based on their username.

    Args:
        db (AsyncSession): The database session to use for queries.
        username (str | None): The username to search for in the database.
        If None, returns None immediately.

    Returns:
        User | None: The user object if found, otherwise None.
    """
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        stmt = select(User).where(User.username == username)
        result = await db.execute(stmt)
        user = result.scalars().first()
    except SQLAlchemyError as e:
        exc_info = f"Database error: {e!s}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc_info,
        ) from e
    else:
        return user


async def get_current_user(
    security_scopes: SecurityScopes,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Retrieve the current user by decoding the provided JWT token, verifying its
    validity, and ensuring the user has the required security scopes.

    Args:
        security_scopes (SecurityScopes): SecurityScopes object to specify which scopes
        are required.
        token (str): The JWT token provided for authentication.
        db (AsyncSession): The database session used to verify the user.

    Returns:
        User: The authenticated and authorized user object if the token is valid and
        scopes are correct.

    Raises:
        HTTPException: If credentials are invalid or the user does not have enough
        permissions.
    """
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    else:
        authenticate_value = "Bearer"

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")

        if username is None:
            raise credentials_exception

        token_scopes = payload.get("scopes", "")
        token_data = TokenData(scopes=token_scopes, username=username)

    except (InvalidTokenError, ValidationError) as err:
        raise credentials_exception from err

    user = await get_user(db, username=token_data.username)

    if user is None:
        raise credentials_exception

    for scope in security_scopes.scopes:
        if scope not in token_data.scopes:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not enough permissions",
                headers={"WWW-Authenticate": authenticate_value},
            )

    return user


async def get_current_active_user(
    current_user: Annotated[User, Security(get_current_user, scopes=["me"])],
):
    """
    Retrieve the current active user from the authentication context,
    ensuring the user is not disabled.

    Args:
        current_user (User): The current authenticated user,
        injected via the `Security` dependency.

    Returns:
        User: The active user if the user is not disabled.

    Raises:
        HTTPException: If the user is disabled or inactive.
    """
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
