import uuid
from pathlib import Path
from typing import Annotated

import aiofiles
from fastapi import APIRouter
from fastapi import Depends
from fastapi import File
from fastapi import HTTPException
from fastapi import UploadFile
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.config import settings
from app.db.session import get_db
from app.models import AudioFile
from app.models import User
from app.models import user_audio_association
from app.schemas import ContentType
from app.schemas import Genre
from user.get import get_current_active_user

upload_file_router = APIRouter(prefix="/audio")

SUPPORTED_EXTENSIONS = {
    ContentType.MP3: ".mp3",
    ContentType.WAV: ".wav",
    ContentType.OGG: ".ogg",
    ContentType.FLAC: ".flac",
    ContentType.AAC: ".aac",
    ContentType.MP4_AUDIO: ".mp4",
}
DEFAULT_GENRE = None


@upload_file_router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_audio_file(
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    genre: Genre | None = DEFAULT_GENRE,
):
    """Upload an audio file to the server with metadata.

    Processes audio file uploads with the following features:
    - Secure file type validation
    - Automatic UUID filename generation
    - Chunked async file saving
    - Metadata storage (genre, content type, size)
    - Automatic owner assignment
    - Access control list management

    Args:
        file: The audio file to upload (MP3, WAV, OGG, FLAC, AAC, or MP4 audio)
        genre: Optional genre classification from predefined enum values
        current_user: Authenticated user (automatically injected)
        db: Async database session (automatically injected)

    Returns:
        dict: Upload metadata including:
            - id: Database ID of the audio file
            - filename: Generated unique filename
            - content_type: Detected MIME type
            - genre: Selected genre if provided
            - download_url: URL to access the uploaded file
            - size_mb: File size in megabytes

    Raises:
        HTTPException 400: For invalid file types or data
        HTTPException 500: For server errors during file processing
    """

    if not file.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only audio files allowed"
        )

    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS.values():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supported formats: MP3, WAV, OGG, FLAC, AAC, MP4_AUDIO",
        )

    unique_name = f"{uuid.uuid4()}{ext}"
    save_path = Path(settings.STORAGE_PATH) / unique_name

    try:
        async with aiofiles.open(save_path, "wb") as f:
            while chunk := await file.read(16 * 1024):  # 16KB chunks
                await f.write(chunk)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="File save failed"
        ) from e

    # Explicit attribute assignments for Alembic compatibility
    audio_file = AudioFile()
    audio_file.filename = unique_name
    audio_file.content_type = ContentType(file.content_type)
    audio_file.size = save_path.stat().st_size
    audio_file.path = str(unique_name)
    audio_file.genre = Genre(genre) if genre else None
    audio_file.owner = current_user
    audio_file.owner_id = current_user.id
    audio_file.authorized_users = [current_user]

    try:
        db.add(audio_file)
        await db.commit()
        await db.refresh(audio_file)
        stmt = insert(user_audio_association).values(
            user_id=current_user.id, audio_file_id=audio_file.id
        )
        await db.execute(stmt)
        await db.commit()

    except ValueError as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid data: {e!s}"
        ) from e
    except Exception as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed",
        ) from e

    return {
        "id": audio_file.id,
        "filename": audio_file.filename,
        "content_type": audio_file.content_type if audio_file.content_type else None,
        "genre": audio_file.genre if audio_file.genre else None,
        "download_url": f"/audio/{audio_file.id}/file",
        "size_mb": round(audio_file.size / (1024 * 1024), 2),
    }
