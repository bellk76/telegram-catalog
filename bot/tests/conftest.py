import os

os.environ.setdefault("BOT_TOKEN", "123456:TESTTOKEN")
os.environ.setdefault("ADMIN_IDS", "1, 2")
os.environ.setdefault("WEBAPP_URL", "https://example.com/")
os.environ.setdefault("API_INTERNAL_URL", "http://api:8000")
os.environ.setdefault("API_INTERNAL_TOKEN", "test-internal-token")
os.environ.setdefault("TELEGRAM_WEBHOOK_URL", "")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "")

import pytest  # noqa: E402

from app.config import Settings  # noqa: E402


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)
