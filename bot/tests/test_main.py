import pytest

from app.config import Settings
from app.main import select_mode


def test_webhook_mode_requires_url(settings: Settings) -> None:
    with pytest.raises(RuntimeError):
        select_mode(settings)


def test_polling_requires_explicit_permission(settings: Settings) -> None:
    polling = Settings(_env_file=None, bot_mode="polling")
    with pytest.raises(RuntimeError):
        select_mode(polling)

    allowed = Settings(_env_file=None, bot_mode="polling", allow_polling=True)
    assert select_mode(allowed) == "polling"


def test_webhook_mode_is_selected() -> None:
    configured = Settings(
        _env_file=None,
        telegram_webhook_url="https://example.com/telegram/webhook",
        telegram_webhook_secret="secret",
    )

    assert select_mode(configured) == "webhook"
