import re
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TELEGRAM_SECRET_RE = re.compile(r"^[A-Za-z0-9_-]{1,256}$")
LOCAL_HOSTS = {"localhost", "127.0.0.1"}
WEBHOOK_PATH = "/telegram/webhook"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    bot_token: SecretStr
    admin_ids: str = ""
    webapp_url: str
    api_internal_url: str = "http://api:8000"
    api_internal_token: SecretStr
    api_timeout: float = Field(default=15.0, gt=0)
    max_image_bytes: int = Field(default=5 * 1024 * 1024, gt=0)

    bot_mode: Literal["webhook", "polling"] = "webhook"
    allow_polling: bool = False
    telegram_webhook_url: str = ""
    telegram_webhook_secret: SecretStr = SecretStr("")

    bot_listen_host: str = "0.0.0.0"
    bot_port: int = Field(default=8080, ge=1, le=65535)

    @field_validator("bot_token", "api_internal_token")
    @classmethod
    def not_blank(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("must be configured")
        return value

    @field_validator("admin_ids")
    @classmethod
    def valid_admin_ids(cls, value: str) -> str:
        for chunk in value.split(","):
            chunk = chunk.strip()
            if chunk and not chunk.isdigit():
                raise ValueError("ADMIN_IDS must be comma-separated integers")
        return value

    @field_validator("webapp_url")
    @classmethod
    def valid_webapp_url(cls, value: str) -> str:
        parts = urlsplit(value)
        if not parts.netloc:
            raise ValueError("WEBAPP_URL must be an absolute URL")
        if parts.scheme == "https":
            return value
        if parts.scheme == "http" and parts.hostname in LOCAL_HOSTS:
            return value
        raise ValueError("WEBAPP_URL must use https")

    @field_validator("api_internal_url")
    @classmethod
    def valid_api_url(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ValueError("API_INTERNAL_URL must be an absolute http(s) URL")
        return value

    @model_validator(mode="after")
    def validate_webhook(self) -> "Settings":
        if self.bot_mode != "webhook" or not self.telegram_webhook_url:
            return self
        parts = urlsplit(self.telegram_webhook_url)
        if (
            parts.scheme != "https"
            or not parts.hostname
            or parts.path != WEBHOOK_PATH
            or parts.query
            or parts.fragment
        ):
            raise ValueError(
                "TELEGRAM_WEBHOOK_URL must be https://<host>/telegram/webhook",
            )
        secret = self.telegram_webhook_secret.get_secret_value()
        if not TELEGRAM_SECRET_RE.fullmatch(secret):
            raise ValueError(
                "TELEGRAM_WEBHOOK_SECRET must be 1-256 characters [A-Za-z0-9_-]",
            )
        return self

    @property
    def admin_id_set(self) -> frozenset[int]:
        return frozenset(
            int(chunk) for chunk in self.admin_ids.split(",") if chunk.strip()
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
