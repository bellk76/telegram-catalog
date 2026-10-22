import asyncio

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.products import create_product
from tests.helpers import (
    PNG_BYTES,
    ConfirmedMissingCommitSession,
    FailingCommitSession,
    FakeStorage,
    OfflineCommitSession,
    PersistedCommitSession,
)


class BarrierStorage(FakeStorage):
    def __init__(self) -> None:
        super().__init__()
        self.barrier = asyncio.Barrier(2)
        self.deleted: list[str] = []

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        await self.barrier.wait()
        await super().upload(key, data, content_type)

    async def delete(self, key: str) -> None:
        self.deleted.append(key)
        await super().delete(key)


class FailingUploadStorage(FakeStorage):
    def __init__(self) -> None:
        super().__init__()
        self.deleted: list[str] = []

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        raise OSError("disk is full")

    async def delete(self, key: str) -> None:
        self.deleted.append(key)


@pytest.mark.parametrize(
    ("session_class", "expected_error", "expected_objects"),
    [
        (FailingCommitSession, OperationalError, 1),
        (OfflineCommitSession, OSError, 1),
        (ConfirmedMissingCommitSession, OperationalError, 0),
        (PersistedCommitSession, OperationalError, 1),
    ],
)
async def test_commit_failure_cleanup_uses_database_state(
    session_class: type[FailingCommitSession],
    expected_error: type[Exception],
    expected_objects: int,
) -> None:
    storage = FakeStorage()
    session = session_class()

    with pytest.raises(expected_error):
        await create_product(
            session,
            storage,
            title="Тестовый",
            data=PNG_BYTES,
            content_type="image/png",
            max_bytes=2048,
        )

    assert session.rollback_calls == 1
    assert len(storage.objects) == expected_objects


async def test_concurrent_same_idempotency_key(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    storage = BarrierStorage()

    async def add(title: str):
        async with session_factory() as session:
            return await create_product(
                session,
                storage,
                title=title,
                data=PNG_BYTES,
                content_type="image/png",
                max_bytes=2048,
                idempotency_key="same-key",
            )

    first, second = await asyncio.gather(add("Первый"), add("Второй"))

    assert first.id == second.id
    assert first.title == second.title
    assert first.title in {"Первый", "Второй"}
    assert len(storage.objects) == 1
    assert len(storage.deleted) == 1


async def test_upload_failure_cleans_up_partial_object() -> None:
    storage = FailingUploadStorage()

    with pytest.raises(OSError):
        await create_product(
            FailingCommitSession(),
            storage,
            title="Товар",
            data=PNG_BYTES,
            content_type="image/png",
            max_bytes=2048,
        )

    assert storage.objects == {}
    assert len(storage.deleted) == 1
