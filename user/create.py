"""Create a new user module."""

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.auth import get_password_hash
from app.core.custom_logging import logger
from app.models.users import User
from app.schemas import UserCreate
from user.get import get_user


async def create_user(db: AsyncSession, user: UserCreate) -> User:
    """
    Create a new user in the database.

    Ensures that the username and email are unique before adding the user.
    Handles race conditions gracefully by catching database-level integrity
    errors and providing meaningful responses to the user.

    Args:
        db (AsyncSession): The SQLAlchemy async database session.
        user (UserCreate): The input data for creating a user.

    Returns:
        User: The newly created user object.

    Raises:
        HTTPException: If the username is already registered.
        HTTPException: If the email is already registered.
        HTTPException: For any unexpected database integrity errors.

    Example:
        ```python
        new_user = await create_user(
            db,
            UserCreate(
                username="new_user",
                email="new_user@example.com",
                password="securepassword123",
            ),
        )
        ```
    """
    db_user_by_username = await get_user(db, user.username)
    if db_user_by_username:
        raise HTTPException(status_code=400, detail="Username already registered")

    db_user_by_email = await db.execute(select(User).where(User.email == user.email))
    if db_user_by_email.scalars().first():
        raise HTTPException(status_code=400, detail="Email is already registered")

    hashed_password = get_password_hash(user.password)

    logger.info(f"user in create_user(user): ===> {user}")

    db_user = User()
    db_user.username = user.username
    db_user.email = str(user.email) if user.email else None
    db_user.hashed_password = hashed_password
    db_user.full_name = user.full_name
    db_user.disabled = user.disabled
    db_user.scopes = user.scopes or "me listener"
    db_user.is_oauth = user.is_oauth
    db_user.oauth_provider = user.oauth_provider
    db_user.oauth_id = user.oauth_id

    try:
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)

    except IntegrityError as e:
        # Rollback on any database integrity errors
        await db.rollback()
        logger.warning(
            "Database IntegrityError",
            extra={
                "constraint": str(e.orig),
                "username": user.username,
                "email": user.email,
            },
        )

        if "users_username_key" in str(e.orig):
            raise HTTPException(
                status_code=400,
                detail="Username already taken.",
            ) from e
        if "users_email_key" in str(e.orig):
            raise HTTPException(
                status_code=400,
                detail="Email already taken.",
            ) from e

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected database error occurred.",
        ) from e

    return db_user
