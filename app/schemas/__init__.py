from .audiofile import AudioFile
from .audiofile import AudioFileCreate
from .audiofile import AudioFileSimple
from .audiofile import AudioFileUpdate
from .audiofile import ContentType
from .audiofile import Genre
from .user import User
from .user import UserCreate
from .user import UserSimple
from .user import UserUpdate

# --- Call model_rebuild() AFTER all imports ---
# Pydantic V2 searches the module scope where rebuild is called and globals.
# By calling it here, both UserSimple and AudioFileSimple are known.
User.model_rebuild()
AudioFile.model_rebuild()

__all__ = [
    "AudioFile",
    "AudioFileCreate",
    "AudioFileSimple",
    "AudioFileUpdate",
    "ContentType",
    "Genre",
    "User",
    "UserCreate",
    "UserSimple",
    "UserUpdate",
]
