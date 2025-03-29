from sqlalchemy import BigInteger
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.models.timestamp import TimestampMixin
from app.models.user_audio import user_audio_association
from app.schemas.audiofile import ContentType
from app.schemas.audiofile import Genre


class AudioFile(Base, TimestampMixin):
    """Represents an audio file uploaded by a user in the system.

    Attributes:
        id: Primary key identifier
        filename: Unique filename of the audio file
        content_type: MIME type of the audio file
        size: File size in bytes
        path: Storage path of the file
        genre: Musical genre/category
        owner_id: Foreign key to the user who uploaded the file
        created_at: Timestamp of creation
        updated_at: Timestamp of last update
    """

    __tablename__ = "audio_files"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    content_type: Mapped[ContentType] = mapped_column(
        Enum(ContentType, name="content_type_enum"),
        nullable=False,
    )
    genre: Mapped[Genre] = mapped_column(
        Enum(Genre, name="genre_enum"),
        nullable=True,
    )
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    owner: Mapped["User"] = relationship(back_populates="owned_files")  # noqa
    authorized_users: Mapped[list["User"]] = relationship(  # noqa
        secondary=user_audio_association,
        back_populates="accessible_files",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<AudioFile(id={self.id}, genre='{self.genre.value if self.genre else None}')>"
