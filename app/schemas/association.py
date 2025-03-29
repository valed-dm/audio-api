from datetime import datetime

from pydantic import BaseModel


class UserAudioLink(BaseModel):
    user_id: int
    audio_file_id: int
    created_at: datetime

    class Config:
        from_attributes = True
