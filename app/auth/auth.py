"""User authentication module."""

from __future__ import annotations

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import TYPE_CHECKING

import jwt
from passlib.context import CryptContext

from app.core.config import settings
from user.get import get_user

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.users import User


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    """
    Verifies if the plain password matches the hashed password.

    Args:
        plain_password (str): The plain text password that needs to be verified.
        hashed_password (str): The hashed password stored in the database.

    Returns:
        bool: True if passwords match, False otherwise.
    """
    if not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hashes a plain password.

    Args:
        password (str): The plain password to be hashed.

    Returns:
        str: The hashed password.
    """
    return pwd_context.hash(password)


async def authenticate_user(
    db: AsyncSession,
    username: str,
    password: str,
) -> User | None:
    """
    Authenticates a user by verifying their username and password.

    This function checks if the username exists in the database and if the
    provided password matches the stored hashed password.

    Args:
        db (AsyncSession): The async database session used to interact with the
        database.
        username (str): The username provided by the user for authentication.
        password (str): The password provided by the user for authentication.

    Returns:
        Optional[User]: The authenticated user if successful, or None if authentication
        fails.
    """
    user = await get_user(db, username)
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Creates an access token (JWT) containing the specified data and an expiration time.

    Args:
        data (dict): The payload data to encode into the JWT (e.g., username, scopes).
        expires_delta (Optional[timedelta], optional):
        The expiration delta for the token. Defaults to 15 minutes if not provided.

    Returns:
        str: The encoded JWT token.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=15)
    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
