import logging
from io import BytesIO

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import CommandStart
from aiogram.types import Document, Message, PhotoSize
from aiohttp import ClientError

from app.api import ApiRejected, ApiUnavailable, ProductApi
from app.config import Settings
from app.keyboards import catalog_keyboard

logger = logging.getLogger(__name__)

router = Router(name="catalog")

START_TEXT = "У меня есть товар"
ADMIN_HINT = (
    "Чтобы добавить товар, отправьте фото с подписью "
    "(или изображение файлом) в одном сообщении."
)
NO_CAPTION_TEXT = "Добавьте к изображению подпись — название товара."
NOT_ADMIN_TEXT = "Добавлять товары может только администратор."
UNAVAILABLE_TEXT = "Сервис каталога временно недоступен, попробуйте позже."
DOWNLOAD_FAILED_TEXT = "Не удалось получить изображение из Telegram, попробуйте ещё раз."
UNSUPPORTED_FILE_TEXT = "Поддерживаются только JPEG, PNG и WebP."
ALLOWED_DOCUMENT_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
MIME_ALIASES = {
    "image/jpg": "image/jpeg",
    "image/pjpeg": "image/jpeg",
    "image/x-png": "image/png",
}


@router.message(CommandStart())
async def handle_start(message: Message, settings: Settings) -> None:
    is_admin = message.from_user is not None and message.from_user.id in settings.admin_id_set
    text = f"{START_TEXT}\n\n{ADMIN_HINT}" if is_admin else START_TEXT
    await message.answer(text, reply_markup=catalog_keyboard(settings.webapp_url))


def _is_admin(message: Message, settings: Settings) -> bool:
    user = message.from_user
    return user is not None and user.id in settings.admin_id_set


def _caption_title(message: Message) -> str:
    return (message.caption or "").strip()


async def _create_product(
    message: Message,
    bot: Bot,
    settings: Settings,
    api: ProductApi,
    *,
    title: str,
    file: PhotoSize | Document,
    content_type: str,
) -> None:
    user = message.from_user
    if user is None:
        return

    buffer = BytesIO()
    try:
        await bot.download(file, destination=buffer)
    except (TelegramAPIError, ClientError, TimeoutError) as exc:
        logger.warning(
            "failed to download image for user %s: %s",
            user.id,
            type(exc).__name__,
        )
        await message.reply(DOWNLOAD_FAILED_TEXT)
        return

    try:
        product = await api.create_product(
            title=title,
            data=buffer.getvalue(),
            content_type=content_type,
            idempotency_key=f"tg:{message.chat.id}:{message.message_id}",
        )
    except ApiUnavailable as exc:
        logger.warning("catalog API is unavailable: %s", exc)
        await message.reply(UNAVAILABLE_TEXT)
        return
    except ApiRejected as exc:
        log = logger.error if exc.status_code in (401, 403) else logger.info
        log(
            "catalog API rejected product from user %s: %s %s",
            user.id,
            exc.status_code,
            exc.detail,
        )
        await message.reply(exc.user_message)
        return

    try:
        await message.reply(
            f"Товар «{product.title}» добавлен.",
            reply_markup=catalog_keyboard(settings.webapp_url),
        )
    except TelegramAPIError:
        logger.warning(
            "product %s created, but confirmation was not delivered",
            product.id,
        )


@router.message(F.photo)
async def handle_photo(
    message: Message,
    bot: Bot,
    settings: Settings,
    api: ProductApi,
) -> None:
    if not _is_admin(message, settings):
        await message.reply(NOT_ADMIN_TEXT)
        return

    title = _caption_title(message)
    if not title:
        await message.reply(NO_CAPTION_TEXT)
        return

    await _create_product(
        message,
        bot,
        settings,
        api,
        title=title,
        file=message.photo[-1],
        content_type="image/jpeg",
    )


@router.message(F.document)
async def handle_document(
    message: Message,
    bot: Bot,
    settings: Settings,
    api: ProductApi,
) -> None:
    if not _is_admin(message, settings):
        await message.reply(NOT_ADMIN_TEXT)
        return

    title = _caption_title(message)
    if not title:
        await message.reply(NO_CAPTION_TEXT)
        return

    document = message.document
    if document is None:
        return

    if document.file_size is not None and document.file_size > settings.max_image_bytes:
        limit_mib = settings.max_image_bytes // (1024 * 1024)
        await message.reply(f"Файл слишком большой: максимум {limit_mib} МиБ.")
        return

    raw_type = (document.mime_type or "").split(";", 1)[0].strip().lower()
    content_type = MIME_ALIASES.get(raw_type, raw_type)
    if content_type not in ALLOWED_DOCUMENT_TYPES:
        await message.reply(UNSUPPORTED_FILE_TEXT)
        return

    await _create_product(
        message,
        bot,
        settings,
        api,
        title=title,
        file=document,
        content_type=content_type,
    )
