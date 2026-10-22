import asyncio
import logging
import signal
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiohttp import web

from app.api import ProductApi
from app.config import Settings, get_settings
from app.errors import register_error_handler
from app.handlers import router
from app.webhook import create_web_app

logger = logging.getLogger(__name__)


async def run_webhook(settings: Settings, bot: Bot, dispatcher: Dispatcher) -> None:
    app = create_web_app(bot, dispatcher, settings)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()

    try:
        site = web.TCPSite(runner, settings.bot_listen_host, settings.bot_port)
        await site.start()
        await bot.set_webhook(
            url=settings.telegram_webhook_url,
            secret_token=settings.telegram_webhook_secret.get_secret_value(),
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    except Exception:
        await runner.cleanup()
        raise

    logger.info("webhook server listening on port %s", settings.bot_port)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for handled_signal in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(handled_signal, stop_event.set)

    try:
        await stop_event.wait()
    finally:
        await runner.cleanup()


async def run_polling(bot: Bot, dispatcher: Dispatcher) -> None:
    logger.warning("polling mode is enabled for local debugging only")
    await bot.delete_webhook()
    await dispatcher.start_polling(
        bot,
        allowed_updates=dispatcher.resolve_used_update_types(),
    )


def select_mode(settings: Settings) -> str:
    if settings.bot_mode == "webhook":
        if not settings.telegram_webhook_url:
            raise RuntimeError("TELEGRAM_WEBHOOK_URL is required in webhook mode")
        return "webhook"
    if not settings.allow_polling:
        raise RuntimeError("polling is disabled; set ALLOW_POLLING=true for local debugging")
    return "polling"


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = get_settings()
    mode = select_mode(settings)

    bot = Bot(token=settings.bot_token.get_secret_value())
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    register_error_handler(dispatcher)
    dispatcher["settings"] = settings
    api = ProductApi(settings)
    dispatcher["api"] = api

    try:
        await bot.set_my_commands([BotCommand(command="start", description="Каталог товаров")])
        if mode == "webhook":
            await run_webhook(settings, bot, dispatcher)
        else:
            await run_polling(bot, dispatcher)
    finally:
        await api.aclose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
