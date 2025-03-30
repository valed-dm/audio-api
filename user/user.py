import typing
from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import EmailStr
from pydantic import Field

if typing.TYPE_CHECKING:
    from app.schemas.audiofile import AudioFileSimple


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, examples=["music_lover"])
    email: EmailStr | None = Field(None, examples=["user@example.com"])
    full_name: str | None = Field(None, max_length=100, examples=["John Doe"])
    disabled: bool = False
    scopes: str = ""
    is_oauth: bool = False
    oauth_provider: str | None = None
    oauth_id: str | None = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, examples=["securepassword123"])


class UserUpdate(BaseModel):
    username: str | None = Field(None, min_length=3, max_length=50)
    email: EmailStr | None = Field(None)
    full_name: str | None = Field(None, max_length=100)
    password: str | None = Field(None, min_length=8)

    Config: typing.ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class UserAdminUpdate(UserUpdate):
    disabled: bool | None = None
    scopes: str | None = None

    def model_dump(self, *args, **kwargs):
        """Override serialization to exclude password."""
        kwargs.setdefault("exclude", set())
        kwargs["exclude"].add("password")
        return super().model_dump(*args, **kwargs)


class UserInDBBase(UserBase):
    id: int
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


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user_info: UserUpdate
    temporary_password: str | None = None
    is_temporary_password: bool


class YandexUserInfo(BaseModel):
    id: str
    login: str
    client_id: str
    display_name: str
    real_name: str
    first_name: str
    last_name: str
    sex: str
    default_email: str
    emails: list
    psuid: str
