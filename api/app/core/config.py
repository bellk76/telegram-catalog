from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    database_url: SecretStr

    minio_endpoint: str = "minio:9000"
    minio_app_user: str = "catalog-app"
    minio_app_password: SecretStr
    minio_bucket: str = "product-images"
    minio_secure: bool = False

    api_internal_token: SecretStr
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    max_image_bytes: int = Field(default=5 * 1024 * 1024, gt=0)
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=10, ge=0, le=100)

    @field_validator("minio_app_password", "api_internal_token")
    @classmethod
    def not_blank(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("must be configured")
        return value

    @field_validator("database_url")
    @classmethod
    def valid_database_url(cls, value: SecretStr) -> SecretStr:
        url = value.get_secret_value().strip()
        if not url.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use postgresql+asyncpg")
        return SecretStr(url)


@lru_cache
def get_settings() -> Settings:
    return Settings()
