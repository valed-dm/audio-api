import typing
from datetime import datetime

from pydantic import BaseModel
from pydantic import EmailStr
from pydantic import Field

if typing.TYPE_CHECKING:
    from app.schemas.audiofile import AudioFileSimple


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, examples=["music_lover"])
    email: EmailStr | None = Field(None, examples=["user@example.com"])
    full_name: str | None = Field(None, max_length=100, examples=["John Doe"])


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, examples=["securepassword123"])


class UserUpdate(BaseModel):
    username: str | None = Field(None, min_length=3, max_length=50)
    email: EmailStr | None = Field(None)
    full_name: str | None = Field(None, max_length=100)
    password: str | None = Field(None, min_length=8)


class UserInDBBase(UserBase):
    id: int
    disabled: bool = False
    scopes: str = ""
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserSimple(UserInDBBase):
    """Simplified user schema for relationships"""

    pass


class User(UserInDBBase):
    owned_files: list["AudioFileSimple"] = []
    accessible_files: list["AudioFileSimple"] = []
