"""Add audio_files table

Revision ID: 3e0211f260db
Revises: 748f46223309
Create Date: 2025-03-29 15:22:02.960411

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3e0211f260db"
down_revision: str | None = "748f46223309"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "audio_files",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column(
            "content_type",
            sa.Enum(
                "MP3", "WAV", "OGG", "FLAC", "AAC", "MP4_AUDIO", name="content_type_enum"
            ),
            nullable=False,
        ),
        sa.Column(
            "genre",
            sa.Enum(
                "POP",
                "ROCK",
                "JAZZ",
                "CLASSICAL",
                "ELECTRONIC",
                "HIPHOP",
                "COUNTRY",
                "RNB",
                name="genre_enum",
            ),
            nullable=True,
        ),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_audio_files_filename"), "audio_files", ["filename"], unique=True
    )
    op.create_index(op.f("ix_audio_files_id"), "audio_files", ["id"], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_audio_files_id"), table_name="audio_files")
    op.drop_index(op.f("ix_audio_files_filename"), table_name="audio_files")
    op.drop_table("audio_files")
    # ### end Alembic commands ###
