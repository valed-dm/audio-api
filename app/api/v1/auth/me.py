from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Security
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.users import User as DBUser
from user.get import get_current_active_user
from user.user import UserInDBBase
from user.user import UserUpdate

user_me_router = APIRouter()


@user_me_router.get("/users/me/", response_model=UserInDBBase)
async def read_users_me(
    current_user: Annotated[DBUser, Security(get_current_active_user, scopes=["me"])],
):
    return current_user


@user_me_router.put("/users/me/update/", response_model=UserUpdate, status_code=200)
async def update_own_user(
    user_update: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        DBUser,
        Security(get_current_active_user, scopes=["me read"]),
    ],
):
    """
    Allow a user to update their own data: username, email, and full_name.

    Args:
        user_update (UserUpdate): Updated user data.
        db (AsyncSession): Database session.
        current_user (User): Current authenticated user.

    Returns:
        UserUpdate: Updated user data.
    """
    async with db.begin():
        stmt = select(DBUser).where(DBUser.id == current_user.id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        # Update user fields if provided
        if user_update.username:
            user.username = user_update.username
        if user_update.email:
            user.email = str(user_update.email)
        if user_update.full_name:
            user.full_name = user_update.full_name

        db.add(user)

    return user
