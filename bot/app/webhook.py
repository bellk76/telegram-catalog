import json
import logging
import secrets

from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiohttp import web
from pydantic import ValidationError

from app.config import WEBHOOK_PATH, Settings

logger = logging.getLogger(__name__)

SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"
MAX_UPDATE_BYTES = 64 * 1024


def secret_matches(provided: str | None, expected: str) -> bool:
    return secrets.compare_digest((provided or "").encode("utf-8"), expected.encode("utf-8"))


def create_web_app(bot: Bot, dispatcher: Dispatcher, settings: Settings) -> web.Application:
    expected_secret = settings.telegram_webhook_secret.get_secret_value()
    if not expected_secret:
        raise RuntimeError("TELEGRAM_WEBHOOK_SECRET must be configured")

    app = web.Application(client_max_size=MAX_UPDATE_BYTES)

    async def health(_: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def webhook(request: web.Request) -> web.Response:
        provided_secret = request.headers.get(SECRET_HEADER)
        if not secret_matches(provided_secret, expected_secret):
            raise web.HTTPUnauthorized(text="invalid secret")

        if request.content_type != "application/json":
            raise web.HTTPUnsupportedMediaType(text="application/json required")

        try:
            payload = await request.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise web.HTTPBadRequest(text="invalid update") from exc

        try:
            update = Update.model_validate(payload, context={"bot": bot})
        except ValidationError as exc:
            raise web.HTTPBadRequest(text="invalid update") from exc

        try:
            await dispatcher.feed_webhook_update(bot, update)
        except Exception as exc:
            logger.error(
                "failed to process update %s: %s",
                update.update_id,
                type(exc).__name__,
            )

        return web.json_response({"ok": True})

    app.router.add_get("/health", health)
    app.router.add_post(WEBHOOK_PATH, webhook)
    return app
