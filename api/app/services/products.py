import asyncio
import logging
from contextlib import suppress
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.images import validate_image
from app.core.storage import StorageService
from app.models.product import Product

logger = logging.getLogger(__name__)

TITLE_MAX_LENGTH = 200


class InvalidTitleError(ValueError):
    pass


async def create_product(
    session: AsyncSession,
    storage: StorageService,
    *,
    title: str,
    data: bytes,
    content_type: str,
    max_bytes: int,
    idempotency_key: str | None = None,
) -> Product:
    clean_title = title.strip()
    if not clean_title:
        raise InvalidTitleError("title is required")
    if len(clean_title) > TITLE_MAX_LENGTH:
        raise InvalidTitleError("title is too long")
    if any(ord(character) < 32 or 0x7F <= ord(character) <= 0x9F for character in clean_title):
        raise InvalidTitleError("title contains control characters")

    if idempotency_key is not None:
        existing = await _find_by_idempotency_key(session, idempotency_key)
        if existing is not None:
            return existing

    extension = validate_image(data, content_type, max_bytes)
    image_key = f"products/{uuid4().hex}{extension}"

    try:
        await storage.upload(image_key, data, content_type)
    except BaseException:
        await _remove_uploaded_image(storage, image_key)
        raise

    product = Product(
        title=clean_title,
        image_key=image_key,
        image_content_type=content_type,
        image_size=len(data),
        idempotency_key=idempotency_key,
    )
    try:
        session.add(product)
        await session.commit()
    except IntegrityError:
        with suppress(Exception):
            await session.rollback()
        await _cleanup_after_failed_commit(session, storage, image_key)
        if idempotency_key is not None:
            existing = await _find_by_idempotency_key(session, idempotency_key)
            if existing is not None:
                return existing
        raise
    except (Exception, asyncio.CancelledError):
        with suppress(Exception):
            await session.rollback()
        await _cleanup_after_failed_commit(session, storage, image_key)
        raise

    return product


async def _cleanup_after_failed_commit(
    session: AsyncSession,
    storage: StorageService,
    image_key: str,
) -> None:
    try:
        persisted = await session.scalar(
            select(Product.id).where(Product.image_key == image_key),
        )
    except Exception:
        logger.warning(
            "commit failed and database state is unknown; keeping image %s",
            image_key,
        )
        return
    if persisted is None:
        await _remove_uploaded_image(storage, image_key)


async def _find_by_idempotency_key(
    session: AsyncSession,
    idempotency_key: str,
) -> Product | None:
    return await session.scalar(
        select(Product).where(Product.idempotency_key == idempotency_key),
    )


async def _remove_uploaded_image(storage: StorageService, image_key: str) -> None:
    try:
        await storage.delete(image_key)
    except Exception:
        logger.warning("failed to delete orphan image %s", image_key)


async def list_products(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
) -> tuple[list[Product], int]:
    total = await session.scalar(select(func.count()).select_from(Product))
    result = await session.scalars(
        select(Product)
        .order_by(Product.created_at.desc(), Product.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result), int(total or 0)


async def get_product(session: AsyncSession, product_id: int) -> Product | None:
    return await session.get(Product, product_id)
