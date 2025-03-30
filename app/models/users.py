"""Users table model."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import BigInteger
from sqlalchemy import Boolean
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.models.timestamp import TimestampMixin
from app.models.user_audio import user_audio_association


class User(Base, TimestampMixin):
    """Represents a user account in the system.

    Attributes:
        id: Primary key identifier
        username: Unique username
        email: Optional unique email
        hashed_password: Securely hashed password
        full_name: Optional full name
        disabled: Account status flag
        scopes: Permission scopes
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    disabled: Mapped[bool] = mapped_column(
        Boolean,
        server_default=sa.text("false"),
        comment="Whether user account is disabled",
    )
    scopes: Mapped[str] = mapped_column(
        String(512),
        server_default="",
        comment="Space-separated list of access scopes",
    )
    is_oauth: Mapped[bool] = mapped_column(
        Boolean,
        server_default=sa.text("false"),
        comment="True if user registered via OAuth provider",
    )
    oauth_provider: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="'yandex', 'google', etc."
    )
    oauth_id: Mapped[str | None] = mapped_column(
        String(256), nullable=True, comment="User ID from OAuth provider"
    )

    owned_files: Mapped[list["AudioFile"]] = relationship(  # noqa
        back_populates="owner", cascade="all, delete-orphan"
    )

    accessible_files: Mapped[list["AudioFile"]] = relationship(  # noqa
        secondary=user_audio_association,
        back_populates="authorized_users",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"
