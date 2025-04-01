from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas import UserCreate
from user.create import create_user
from user.user import UserUpdate

user_register_router = APIRouter()


@user_register_router.post("/register", response_model=UserUpdate)
async def register_user(
    user: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Register a new user in the system.

    This endpoint creates a new user by first ensuring that the username and email
    are unique. Then, it proceeds with hashing the password and storing the user's
    data in the database. If a user with the given username or email already exists,
    an appropriate error message is returned.

    Args:
        user (UserCreate): The data required to create the new user, such as
                            username, email, password, etc.
        db (AsyncSession): The database session used to interact with the database.

    Returns:
        UserOut: The newly created user information, as outputted by the UserOut
                 Pydantic model (response model).

    Raises:
        HTTPException: If the username or email is already taken, an HTTP error
                       is raised with an appropriate message.
    """
    return await create_user(db, user)
