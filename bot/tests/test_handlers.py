import logging
from types import SimpleNamespace

import pytest
from aiogram.exceptions import TelegramAPIError
from aiohttp import ClientError

from app.api import ApiRejected, ApiUnavailable, Product
from app.config import Settings
from app.handlers import (
    DOWNLOAD_FAILED_TEXT,
    NO_CAPTION_TEXT,
    NOT_ADMIN_TEXT,
    START_TEXT,
    UNAVAILABLE_TEXT,
    UNSUPPORTED_FILE_TEXT,
    handle_document,
    handle_photo,
    handle_start,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
IDEMPOTENCY_KEY = "tg:-100:10"


class FakeMessage:
    def __init__(
        self,
        *,
        user_id: int = 1,
        caption: str | None = "Товар",
        reply_error: Exception | None = None,
        document: object | None = None,
    ) -> None:
        self.from_user = SimpleNamespace(id=user_id, is_bot=False)
        self.chat = SimpleNamespace(id=-100)
        self.message_id = 10
        self.caption = caption
        self.photo = [SimpleNamespace(file_id="photo-id", width=1, height=1)]
        self.document = document
        self.reply_error = reply_error
        self.replies: list[tuple[str, object]] = []
        self.answers: list[tuple[str, object]] = []

    async def reply(self, text: str, reply_markup: object = None) -> None:
        if self.reply_error is not None:
            raise self.reply_error
        self.replies.append((text, reply_markup))

    async def answer(self, text: str, reply_markup: object = None) -> None:
        self.answers.append((text, reply_markup))


class FakeBot:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.downloads: list[object] = []

    async def download(self, file: object, destination: object) -> None:
        self.downloads.append(file)
        if self.error is not None:
            raise self.error
        destination.write(PNG_BYTES)


class FakeApi:
    def __init__(
        self,
        *,
        error: Exception | None = None,
        product: Product | None = None,
    ) -> None:
        self.error = error
        self.product = product or Product(id=1, title="Товар")
        self.calls: list[dict[str, object]] = []

    async def create_product(
        self,
        *,
        title: str,
        data: bytes,
        content_type: str,
        idempotency_key: str | None = None,
    ) -> Product:
        self.calls.append(
            {
                "title": title,
                "data": data,
                "content_type": content_type,
                "idempotency_key": idempotency_key,
            },
        )
        if self.error is not None:
            raise self.error
        return self.product


def document_message(
    *,
    mime_type: str | None = "image/png",
    caption: str | None = "Товар",
    user_id: int = 1,
    file_size: int | None = None,
) -> FakeMessage:
    message = FakeMessage(user_id=user_id, caption=caption)
    message.photo = None
    message.document = SimpleNamespace(
        file_id="document-id",
        mime_type=mime_type,
        file_name="product.bin",
        file_size=file_size,
    )
    return message


async def test_start_for_admin(settings: Settings) -> None:
    message = FakeMessage()

    await handle_start(message, settings)

    text, keyboard = message.answers[0]
    assert text.startswith(START_TEXT)
    assert "фото с подписью" in text
    assert keyboard.inline_keyboard[0][0].web_app.url == settings.webapp_url


async def test_start_for_non_admin(settings: Settings) -> None:
    message = FakeMessage(user_id=999)

    await handle_start(message, settings)

    text, keyboard = message.answers[0]
    assert text == START_TEXT
    assert keyboard.inline_keyboard[0][0].text == "Каталог"


async def test_non_admin_cannot_add_product(settings: Settings) -> None:
    message = FakeMessage(user_id=999)
    api = FakeApi()

    await handle_photo(message, FakeBot(), settings, api)

    assert message.replies[0][0] == NOT_ADMIN_TEXT
    assert api.calls == []


async def test_admin_needs_caption(settings: Settings) -> None:
    message = FakeMessage(caption=None)
    api = FakeApi()

    await handle_photo(message, FakeBot(), settings, api)

    assert message.replies[0][0] == NO_CAPTION_TEXT
    assert api.calls == []


async def test_admin_adds_product(settings: Settings) -> None:
    message = FakeMessage(caption="  Кружка  ")
    api = FakeApi(product=Product(id=5, title="Кружка"))

    await handle_photo(message, FakeBot(), settings, api)

    assert api.calls == [
        {
            "title": "Кружка",
            "data": PNG_BYTES,
            "content_type": "image/jpeg",
            "idempotency_key": IDEMPOTENCY_KEY,
        },
    ]
    assert message.replies[0][0] == "Товар «Кружка» добавлен."
    assert message.replies[0][1].inline_keyboard[0][0].web_app.url == settings.webapp_url


@pytest.mark.parametrize("mime_type", ["image/jpeg", "image/png", "image/webp"])
async def test_admin_adds_product_from_image_document(
    settings: Settings,
    mime_type: str,
) -> None:
    message = document_message(mime_type=mime_type, caption="  Байк  ")
    api = FakeApi(product=Product(id=8, title="Байк"))

    await handle_document(message, FakeBot(), settings, api)

    assert api.calls == [
        {
            "title": "Байк",
            "data": PNG_BYTES,
            "content_type": mime_type,
            "idempotency_key": IDEMPOTENCY_KEY,
        },
    ]
    assert message.replies[0][0] == "Товар «Байк» добавлен."
    assert message.replies[0][1].inline_keyboard[0][0].web_app.url == settings.webapp_url


async def test_document_needs_caption(settings: Settings) -> None:
    message = document_message(caption=None)
    api = FakeApi()

    await handle_document(message, FakeBot(), settings, api)

    assert message.replies[0][0] == NO_CAPTION_TEXT
    assert api.calls == []


async def test_non_admin_cannot_add_document(settings: Settings) -> None:
    message = document_message(user_id=999)
    api = FakeApi()

    await handle_document(message, FakeBot(), settings, api)

    assert message.replies[0][0] == NOT_ADMIN_TEXT
    assert api.calls == []


@pytest.mark.parametrize("mime_type", ["application/pdf", "image/gif", None])
async def test_unsupported_document_type_is_rejected(
    settings: Settings,
    mime_type: str | None,
) -> None:
    message = document_message(mime_type=mime_type)
    api = FakeApi()
    bot = FakeBot()

    await handle_document(message, bot, settings, api)

    assert message.replies[0][0] == UNSUPPORTED_FILE_TEXT
    assert bot.downloads == []
    assert api.calls == []


async def test_oversized_document_is_rejected_before_download(
    settings: Settings,
) -> None:
    message = document_message(file_size=settings.max_image_bytes + 1)
    api = FakeApi()
    bot = FakeBot()

    await handle_document(message, bot, settings, api)

    assert "Файл слишком большой" in message.replies[0][0]
    assert bot.downloads == []
    assert api.calls == []


async def test_document_download_failure_is_shown(settings: Settings) -> None:
    message = document_message()

    await handle_document(
        message,
        FakeBot(TelegramAPIError(None, "download failed")),
        settings,
        FakeApi(),
    )

    assert message.replies[0][0] == DOWNLOAD_FAILED_TEXT


async def test_api_rejection_is_shown(settings: Settings) -> None:
    message = FakeMessage()

    await handle_photo(
        message,
        FakeBot(),
        settings,
        FakeApi(error=ApiRejected(413, "too large")),
    )

    assert message.replies[0][0] == "Файл слишком большой."


async def test_authorization_error_is_logged(settings: Settings, caplog) -> None:
    caplog.set_level(logging.ERROR, logger="app.handlers")
    message = FakeMessage()

    await handle_photo(
        message,
        FakeBot(),
        settings,
        FakeApi(error=ApiRejected(403, "forbidden")),
    )

    assert "403" in caplog.text
    assert "настроен некорректно" in message.replies[0][0]


async def test_api_unavailable_is_shown(settings: Settings) -> None:
    message = FakeMessage()

    await handle_photo(
        message,
        FakeBot(),
        settings,
        FakeApi(error=ApiUnavailable("down")),
    )

    assert message.replies[0][0] == UNAVAILABLE_TEXT


async def test_download_failure_is_shown(settings: Settings) -> None:
    message = FakeMessage()

    await handle_photo(
        message,
        FakeBot(TelegramAPIError(None, "download failed")),
        settings,
        FakeApi(),
    )

    assert message.replies[0][0] == DOWNLOAD_FAILED_TEXT


async def test_download_error_does_not_leak_token(
    settings: Settings,
    caplog,
) -> None:
    caplog.set_level(logging.WARNING)
    message = FakeMessage()
    secret_url = "https://api.telegram.org/file/bot123:SECRETTOKEN/photo.jpg"

    await handle_photo(message, FakeBot(ClientError(secret_url)), settings, FakeApi())

    assert message.replies[0][0] == DOWNLOAD_FAILED_TEXT
    assert "SECRETTOKEN" not in caplog.text


async def test_confirmation_failure_after_creation_is_tolerated(
    settings: Settings,
) -> None:
    message = FakeMessage(
        reply_error=TelegramAPIError(None, "confirmation failed"),
    )
    api = FakeApi(product=Product(id=5, title="Кружка"))

    await handle_photo(message, FakeBot(), settings, api)

    assert len(api.calls) == 1
    assert message.replies == []
