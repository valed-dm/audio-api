from fastapi import APIRouter
from fastapi import Depends
from fastapi import File
from fastapi import HTTPException
from fastapi import UploadFile

from user.get import get_current_user

audio_router = APIRouter()


class AudioFileOut:
    pass


class AudioService:
    async def upload_audio(self, file, id):
        pass


@audio_router.post("/upload", response_model=AudioFileOut)
async def upload_audio(
    file: UploadFile = File(...),  # noqa: B008
    current_user=Depends(get_current_user),  # noqa: B008
    audio_service: AudioService = Depends(),  # noqa: B008
):
    if not file.content_type.startswith("audio/"):
        raise HTTPException(400, "File must be an audio file")

    return await audio_service.upload_audio(file, current_user.id)
