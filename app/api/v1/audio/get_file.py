from pathlib import Path
from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.session import get_db
from app.models import AudioFile
from app.models import User
from user.get import get_current_active_user

get_file_router = APIRouter(prefix="/audio")


@get_file_router.get("/{audio_id}/file", response_class=FileResponse)
async def stream_audio_file(
    audio_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Stream audio file directly to client with proper headers.

    Returns:
        FileResponse: The audio file with content-disposition headers

    Raises:
        HTTPException 404: If file not found
        HTTPException 403: If unauthorized
    """
    result = await db.execute(
        select(AudioFile)
        .options(selectinload(AudioFile.authorized_users))
        .filter(AudioFile.id == audio_id)
    )
    audio_file = result.scalars().first()

    if not audio_file:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audio file not found")

    if (
        audio_file.owner_id != current_user.id
        and current_user not in audio_file.authorized_users
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized")

    file_path = Path(settings.STORAGE_PATH) / audio_file.path
    if not file_path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File missing on server")

    return FileResponse(
        path=file_path,
        media_type=audio_file.content_type.value,
        filename=audio_file.filename,
        headers={
            "Content-Disposition": f"inline; filename={audio_file.filename}",
            "Accept-Ranges": "bytes",
        },
    )
