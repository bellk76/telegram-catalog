import logging

from httpx import AsyncClient

from app.core.storage import get_storage
from app.db.session import get_session
from app.main import app
from tests.helpers import BrokenProgrammingSession, BrokenSession, FailingStorage


async def test_health_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_ok(client: AsyncClient) -> None:
    response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_storage_failure(client: AsyncClient) -> None:
    app.dependency_overrides[get_storage] = FailingStorage

    response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "storage is unavailable"}


async def test_ready_database_failure(client: AsyncClient) -> None:
    async def broken_session() -> BrokenSession:
        yield BrokenSession()

    app.dependency_overrides[get_session] = broken_session

    response = await client.get("/ready")

    assert response.status_code == 503


async def test_health_database_failure(client: AsyncClient) -> None:
    async def broken_session() -> BrokenSession:
        yield BrokenSession()

    app.dependency_overrides[get_session] = broken_session

    response = await client.get("/health")

    assert response.status_code == 503


async def test_health_programming_error_is_logged(
    client: AsyncClient,
    caplog,
) -> None:
    caplog.set_level(logging.ERROR, logger="catalog.api")

    async def broken_session() -> BrokenProgrammingSession:
        yield BrokenProgrammingSession()

    app.dependency_overrides[get_session] = broken_session

    response = await client.get("/health")

    assert response.status_code == 500
    assert any("database error" in record.getMessage() for record in caplog.records)
