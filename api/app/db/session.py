import errno
import logging
import socket
from collections.abc import AsyncIterator
from contextlib import suppress
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

logger = logging.getLogger(__name__)

CONNECTION_ERRORS = (ConnectionError, TimeoutError, socket.gaierror)
CONNECTION_ERRNOS = {
    errno.ECONNREFUSED,
    errno.ETIMEDOUT,
    errno.ENETUNREACH,
    errno.EHOSTUNREACH,
}


class DatabaseUnavailable(Exception):
    pass


def is_connection_error(exc: OSError) -> bool:
    return isinstance(exc, CONNECTION_ERRORS) or exc.errno in CONNECTION_ERRNOS


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=1800,
        pool_timeout=10,
        connect_args={"timeout": 5, "command_timeout": 15},
    )


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        try:
            yield session
        except OSError as exc:
            with suppress(Exception):
                await session.rollback()
            if not is_connection_error(exc):
                raise
            logger.warning("database connection failed: %s", exc, exc_info=True)
            raise DatabaseUnavailable("database connection failed") from exc
        except Exception:
            with suppress(Exception):
                await session.rollback()
            raise
