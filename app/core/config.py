import os
from typing import Annotated

from pydantic import AnyHttpUrl
from pydantic import Field
from pydantic import TypeAdapter
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    STORAGE_PATH: str = "./storage"
    PROJECT_NAME: Annotated[str, Field(validation_alias="PROJECT_NAME")]
    SECRET_KEY: Annotated[str, Field(validation_alias="SECRET_KEY")]

    # JSON list of accepted CORS origins
    CORS_ORIGINS: list[AnyHttpUrl] = TypeAdapter(list[AnyHttpUrl]).validate_json(
        os.getenv("CORS_ORIGINS", "[]")
    )

    # Postgres
    POSTGRES_HOST: Annotated[str, Field(validation_alias="POSTGRES_HOST")]
    POSTGRES_USER: Annotated[str, Field(validation_alias="POSTGRES_USER")]
    POSTGRES_PASSWORD: Annotated[str, Field(validation_alias="POSTGRES_PASSWORD")]
    POSTGRES_PORT: Annotated[
        int, Field(default=5432, validation_alias="POSTGRES_PORT", gt=1024, lt=65536)
    ]
    POSTGRES_DB: Annotated[str, Field(validation_alias="POSTGRES_DB")]

    # Admin
    ADMIN_LOGIN: Annotated[str, Field(validation_alias="ADMIN_LOGIN")]
    ADMIN_PWD: Annotated[str, Field(validation_alias="ADMIN_PWD")]

    # JWT Token
    JWT_SECRET: Annotated[str, Field(validation_alias="JWT_SECRET", min_length=32)]
    JWT_TIMEOUT: Annotated[
        int, Field(default=300, validation_alias="JWT_TIMEOUT", gt=300)
    ]
    JWT_REFRESH_TIMEOUT: Annotated[int, Field(validation_alias="JWT_REFRESH_TIMEOUT")]

    @property
    def database_url(self) -> str:
        user = self.POSTGRES_USER
        password = self.POSTGRES_PASSWORD
        host = self.POSTGRES_HOST
        port = self.POSTGRES_PORT
        db = self.POSTGRES_DB
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"

    class Config:
        case_sensitive = True


settings = Settings()
