import pytest
from pydantic import ValidationError

from app.config import Settings


def test_admin_ids_are_parsed(settings: Settings) -> None:
    assert settings.admin_id_set == frozenset({1, 2})


def test_empty_admin_ids(settings: Settings) -> None:
    empty = Settings(_env_file=None, admin_ids="")

    assert empty.admin_id_set == frozenset()


def test_invalid_admin_ids() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, admin_ids="1,admin")


def test_invalid_webapp_url() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, webapp_url="example.com")

    with pytest.raises(ValidationError):
        Settings(_env_file=None, webapp_url="https://")

    with pytest.raises(ValidationError):
        Settings(_env_file=None, webapp_url="http://example.com")


def test_local_http_webapp_url_is_allowed() -> None:
    configured = Settings(_env_file=None, webapp_url="http://localhost:3000")

    assert configured.webapp_url == "http://localhost:3000"


def test_invalid_api_internal_url() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, api_internal_url="api:8000")

    with pytest.raises(ValidationError):
        Settings(_env_file=None, api_internal_url="http://[::1")


def test_webhook_requires_https_and_secret(settings: Settings) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, telegram_webhook_url="http://example.com/telegram/webhook")

    with pytest.raises(ValidationError):
        Settings(_env_file=None, telegram_webhook_url="https://example.com/telegram/webhook")

    configured = Settings(
        _env_file=None,
        telegram_webhook_url="https://example.com/telegram/webhook",
        telegram_webhook_secret="secret",
    )
    assert configured.telegram_webhook_url == "https://example.com/telegram/webhook"


def test_webhook_path_is_validated() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            telegram_webhook_url="https://example.com/hook",
            telegram_webhook_secret="secret",
        )

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            telegram_webhook_url="https://",
            telegram_webhook_secret="secret",
        )


def test_polling_ignores_webhook_settings() -> None:
    configured = Settings(
        _env_file=None,
        bot_mode="polling",
        telegram_webhook_url="https://example.com/not-the-webhook-path",
    )

    assert configured.bot_mode == "polling"


def test_webhook_secret_is_validated(settings: Settings) -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            telegram_webhook_url="https://example.com/telegram/webhook",
            telegram_webhook_secret="bad secret!",
        )


def test_bot_token_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BOT_TOKEN")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
