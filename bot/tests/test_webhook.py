import logging

import pytest
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiohttp.test_utils import TestClient, TestServer

from app.config import Settings
from app.errors import register_error_handler
from app.webhook import MAX_UPDATE_BYTES, create_web_app, secret_matches


def webhook_settings() -> Settings:
    return Settings(
        _env_file=None,
        telegram_webhook_url="https://example.com/telegram/webhook",
        telegram_webhook_secret="secret",
    )


def make_update(update_id: int = 1) -> dict[str, object]:
    return {
        "update_id": update_id,
        "message": {
            "message_id": 1,
            "date": 1700000000,
            "chat": {"id": 1, "type": "private"},
            "from": {"id": 1, "is_bot": False, "first_name": "A"},
            "text": "/start",
        },
    }


class DummyDispatcher:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.processed: list[tuple[Bot, object]] = []

    async def feed_webhook_update(self, bot: Bot, update: object) -> None:
        self.processed.append((bot, update))
        if self.error is not None:
            raise self.error


async def test_health() -> None:
    client = TestClient(TestServer(create_web_app(None, None, webhook_settings())))
    await client.start_server()
    try:
        response = await client.get("/health")
        assert response.status == 200
        assert await response.json() == {"status": "ok"}
    finally:
        await client.close()


async def test_webhook_requires_secret() -> None:
    client = TestClient(TestServer(create_web_app(None, None, webhook_settings())))
    await client.start_server()
    try:
        without_secret = await client.post("/telegram/webhook", json={})
        wrong_secret = await client.post(
            "/telegram/webhook",
            json={},
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
        )
    finally:
        await client.close()

    assert without_secret.status == 401
    assert wrong_secret.status == 401


async def test_webhook_requires_json() -> None:
    client = TestClient(TestServer(create_web_app(None, None, webhook_settings())))
    await client.start_server()
    try:
        response = await client.post(
            "/telegram/webhook",
            data="{}",
            headers={
                "X-Telegram-Bot-Api-Secret-Token": "secret",
                "Content-Type": "text/plain",
            },
        )
    finally:
        await client.close()

    assert response.status == 415


async def test_webhook_rejects_invalid_json() -> None:
    client = TestClient(TestServer(create_web_app(None, None, webhook_settings())))
    await client.start_server()
    try:
        response = await client.post(
            "/telegram/webhook",
            data="not json",
            headers={
                "X-Telegram-Bot-Api-Secret-Token": "secret",
                "Content-Type": "application/json",
            },
        )
    finally:
        await client.close()

    assert response.status == 400


async def test_webhook_rejects_oversized_update() -> None:
    client = TestClient(TestServer(create_web_app(None, None, webhook_settings())))
    await client.start_server()
    try:
        response = await client.post(
            "/telegram/webhook",
            data=b"x" * (MAX_UPDATE_BYTES + 1),
            headers={
                "X-Telegram-Bot-Api-Secret-Token": "secret",
                "Content-Type": "application/json",
            },
        )
    finally:
        await client.close()

    assert response.status == 413


def test_webhook_requires_configured_secret() -> None:
    with pytest.raises(RuntimeError):
        create_web_app(None, None, Settings(_env_file=None))


async def test_webhook_processes_valid_update() -> None:
    bot = Bot(token="123456:TESTTOKEN")
    dispatcher = DummyDispatcher()
    client = TestClient(TestServer(create_web_app(bot, dispatcher, webhook_settings())))
    await client.start_server()
    try:
        response = await client.post(
            "/telegram/webhook",
            json=make_update(update_id=42),
            headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
        )
        body = await response.json()
    finally:
        await client.close()
        await bot.session.close()

    assert response.status == 200
    assert body == {"ok": True}
    processed_bot, update = dispatcher.processed[0]
    assert processed_bot is bot
    assert update.update_id == 42
    assert update.bot is bot


async def test_webhook_acknowledges_handler_errors(caplog) -> None:
    caplog.set_level(logging.ERROR, logger="app.webhook")
    bot = Bot(token="123456:TESTTOKEN")
    dispatcher = DummyDispatcher(
        RuntimeError("https://api.telegram.org/file/bot123:SECRETTOKEN/photo.jpg"),
    )
    client = TestClient(TestServer(create_web_app(bot, dispatcher, webhook_settings())))
    await client.start_server()
    try:
        response = await client.post(
            "/telegram/webhook",
            json=make_update(update_id=43),
            headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
        )
    finally:
        await client.close()
        await bot.session.close()

    assert response.status == 200
    assert "failed to process update 43" in caplog.text
    assert "SECRETTOKEN" not in caplog.text


def test_secret_comparison_handles_non_ascii() -> None:
    assert secret_matches("secret", "secret")
    assert not secret_matches("токен", "secret")
    assert not secret_matches(None, "secret")
    assert not secret_matches("", "secret")


async def test_real_dispatcher_error_handler_does_not_leak(caplog) -> None:
    caplog.set_level(logging.DEBUG)
    secret = "https://api.telegram.org/file/bot123:SECRETTOKEN/photo.jpg"
    bot = Bot(token="123456:TESTTOKEN")
    dispatcher = Dispatcher()

    @dispatcher.message()
    async def failing_handler(message: Message) -> None:
        raise RuntimeError(secret)

    register_error_handler(dispatcher)
    client = TestClient(TestServer(create_web_app(bot, dispatcher, webhook_settings())))
    await client.start_server()
    try:
        response = await client.post(
            "/telegram/webhook",
            json=make_update(update_id=44),
            headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
        )
    finally:
        await client.close()
        await bot.session.close()

    assert response.status == 200
    assert "RuntimeError" in caplog.text
    assert "SECRETTOKEN" not in caplog.text
