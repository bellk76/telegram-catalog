import os

from sqlalchemy.engine import make_url

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://catalog:catalog@localhost:5433/catalog_test",
)
TEST_DATABASE_NAME = make_url(TEST_DATABASE_URL).database or ""
if not TEST_DATABASE_NAME.endswith("_test"):
    raise RuntimeError("TEST_DATABASE_URL must point to a *_test database")

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["MINIO_APP_PASSWORD"] = "test-minio-password"
os.environ["API_INTERNAL_TOKEN"] = "test-internal-token"
os.environ["MAX_IMAGE_BYTES"] = "2048"
os.environ["CORS_ORIGINS"] = '["http://localhost:3000"]'

from collections.abc import AsyncIterator  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings  # noqa: E402
from app.core.storage import get_storage  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.main import app  # noqa: E402
from tests.helpers import FakeStorage  # noqa: E402


@pytest.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(TEST_DATABASE_URL)
    try:
        async with engine.connect() as connection:
            current_database = await connection.scalar(text("SELECT current_database()"))
        if not current_database or not str(current_database).endswith("_test"):
            raise RuntimeError("refusing to reset a non-test database")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
async def client(
    storage: FakeStorage,
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as http_client:
            yield http_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def token() -> str:
    return get_settings().api_internal_token.get_secret_value()
