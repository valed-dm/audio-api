import typing
from datetime import datetime
from enum import Enum

from pydantic import BaseModel
from pydantic import Field

if typing.TYPE_CHECKING:
    from user.user import UserSimple


class ContentType(str, Enum):
    """Supported audio file formats"""

    MP3 = "audio/mpeg"
    WAV = "audio/wav"
    OGG = "audio/ogg"
    FLAC = "audio/flac"
    AAC = "audio/aac"
    MP4_AUDIO = "audio/mp4"


class Genre(str, Enum):
    """Music genre classification"""

    POP = "pop"
    ROCK = "rock"
    JAZZ = "jazz"
    CLASSICAL = "classical"
    ELECTRONIC = "electronic"
    HIPHOP = "hiphop"
    COUNTRY = "country"
    RNB = "rnb"


class AudioFileBase(BaseModel):
    filename: str = Field(..., max_length=255, examples=["my_song.mp3"])
    content_type: ContentType = Field(..., examples=[ContentType.MP3])
    size: int = Field(..., gt=0, examples=[1024000])
    path: str = Field(..., max_length=512)
    genre: Genre | None = Field(None, examples=[Genre.JAZZ])


class AudioFileCreate(AudioFileBase):
    owner_id: int = Field(..., examples=[1])


class AudioFileUpdate(BaseModel):
    filename: str | None = Field(None, max_length=255)
    content_type: ContentType | None = Field(None, examples=[ContentType.MP3])
    genre: Genre | None = Field(None, examples=[Genre.ROCK])


class AudioFileInDBBase(AudioFileBase):
    id: int
    owner_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AudioFileSimple(AudioFileInDBBase):
    """Simplified audio file schema for relationships"""

    pass


class AudioFile(AudioFileInDBBase):
    owner: "UserSimple"
    authorized_users: list["UserSimple"] = []
