from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Security
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.models.users import User as DBUser
from user.get import get_current_active_user
from user.user import UserAdminUpdate

admin_router = APIRouter()


@admin_router.get("/users/", response_model=list[UserAdminUpdate])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[DBUser, Security(get_current_active_user, scopes=["superuser"])],
    limit: int = 10,
    offset: int = 0,
):
    """
    List all users with pagination. Accessible by superusers only.

    Args:
        db: AsyncSession.
        _: Grants access only to superusers.
        limit (int): Maximum number of users to return. Default is 10.
        offset (int): Number of users to skip before starting to collect the result.
        Default is 0.
    """
    async with db.begin():
        stmt = select(DBUser).limit(limit).offset(offset)
        result = await db.execute(stmt)

    return result.scalars().all()


@admin_router.patch("/users/{user_id}", response_model=UserAdminUpdate)
async def update_user(
    user_id: int,
    user_update: UserAdminUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[DBUser, Security(get_current_active_user, scopes=["superuser"])],
):
    """
    Update a user's details. Only accessible by superusers.
    """
    async with db.begin():
        # Fetch the user
        stmt = select(DBUser).where(DBUser.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"User with ID {user_id} not found.",
            )

        # Update user details
        for key, value in user_update.model_dump(exclude_unset=True).items():
            setattr(user, key, value)

    await db.refresh(user)
    return user


@admin_router.get("/status/")
async def read_system_status(
    current_user: Annotated[
        DBUser,
        Security(get_current_active_user, scopes=["superuser"]),
    ],
):
    """Available for admins only!"""
    return {"status": "ok", "superuser": current_user.username}
