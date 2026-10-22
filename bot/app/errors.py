import logging

from aiogram import Dispatcher
from aiogram.types import ErrorEvent

logger = logging.getLogger(__name__)


def register_error_handler(dispatcher: Dispatcher) -> None:
    @dispatcher.errors()
    async def on_error(event: ErrorEvent) -> None:
        logger.error(
            "update processing failed: %s",
            type(event.exception).__name__,
        )
