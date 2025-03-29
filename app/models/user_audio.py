from sqlalchemy import BigInteger
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Table
from sqlalchemy import UniqueConstraint

from app.models.base import Base

user_audio_association = Table(
    "user_audio_association",
    Base.metadata,
    Column(
        "user_id",
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "audio_file_id",
        BigInteger,
        ForeignKey("audio_files.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    UniqueConstraint(
        "user_id",
        "audio_file_id",
        name="uq_user_audio_pair",
    ),
    Index("ix_user_audio_user_id", "user_id"),
    Index("ix_user_audio_audio_file_id", "audio_file_id"),
)
