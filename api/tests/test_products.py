import socket

from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.session as session_module
from app.core.storage import get_storage
from app.db.session import get_session
from app.main import MAX_MULTIPART_OVERHEAD, app
from tests.helpers import (
    JPEG_BYTES,
    PNG_BYTES,
    WEBP_BYTES,
    BrokenSession,
    CorruptedStorage,
    FailingStorage,
    FakeStorage,
)

TOKEN_HEADER = "X-Internal-Token"


async def post_product(
    client: AsyncClient,
    token: str,
    *,
    title: str = "Товар",
    data: bytes = PNG_BYTES,
    filename: str = "product.png",
    content_type: str = "image/png",
    idempotency_key: str | None = None,
) -> Response:
    headers = {TOKEN_HEADER: token}
    if idempotency_key is not None:
        headers["X-Idempotency-Key"] = idempotency_key
    return await client.post(
        "/api/products",
        headers=headers,
        data={"title": title},
        files={"image": (filename, data, content_type)},
    )


async def test_create_and_list_product(client: AsyncClient, token: str) -> None:
    created = await post_product(client, token, title="  Кружка  ")

    assert created.status_code == 201
    body = created.json()
    assert body["title"] == "Кружка"
    assert body["image_url"] == f"/api/products/{body['id']}/image"
    assert body["created_at"]

    listing = await client.get("/api/products")

    assert listing.status_code == 200
    payload = listing.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == body["id"]


async def test_jpeg_and_webp_are_accepted(client: AsyncClient, token: str) -> None:
    jpeg = await post_product(
        client,
        token,
        data=JPEG_BYTES,
        filename="photo.jpg",
        content_type="image/jpeg",
    )
    webp = await post_product(
        client,
        token,
        data=WEBP_BYTES,
        filename="photo.webp",
        content_type="image/webp",
    )

    assert jpeg.status_code == 201
    assert webp.status_code == 201


async def test_empty_catalog(client: AsyncClient) -> None:
    response = await client.get("/api/products")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


async def test_catalog_pagination(client: AsyncClient, token: str) -> None:
    first = await post_product(client, token, title="Первый")
    second = await post_product(client, token, title="Второй")
    assert first.status_code == 201
    assert second.status_code == 201

    response = await client.get("/api/products", params={"limit": 1, "offset": 1})

    payload = response.json()
    assert payload["total"] == 2
    assert len(payload["items"]) == 1
    assert payload["items"][0]["title"] == "Первый"


async def test_internal_token_is_required(client: AsyncClient) -> None:
    without_token = await client.post(
        "/api/products",
        data={"title": "Товар"},
        files={"image": ("product.png", PNG_BYTES, "image/png")},
    )
    wrong_token = await client.post(
        "/api/products",
        headers={TOKEN_HEADER: "wrong"},
        data={"title": "Товар"},
        files={"image": ("product.png", PNG_BYTES, "image/png")},
    )

    assert without_token.status_code == 401
    assert wrong_token.status_code == 401


async def test_non_ascii_internal_token_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/api/products",
        headers=[(b"X-Internal-Token", "токен".encode())],
        data={"title": "Товар"},
        files={"image": ("product.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 401


async def test_unsupported_image_type(client: AsyncClient, token: str) -> None:
    response = await post_product(
        client,
        token,
        data=b"GIF89a" + b"\x00" * 32,
        filename="product.gif",
        content_type="image/gif",
    )

    assert response.status_code == 415


async def test_content_type_must_match_bytes(client: AsyncClient, token: str) -> None:
    response = await post_product(
        client,
        token,
        data=PNG_BYTES,
        filename="product.jpg",
        content_type="image/jpeg",
    )

    assert response.status_code == 422


async def test_empty_image_is_rejected(client: AsyncClient, token: str) -> None:
    response = await post_product(client, token, data=b"")

    assert response.status_code == 422


async def test_image_size_limit(client: AsyncClient, token: str) -> None:
    response = await post_product(client, token, data=PNG_BYTES + b"\x00" * 4096)

    assert response.status_code == 413


async def test_title_validation(client: AsyncClient, token: str) -> None:
    spaces_only = await post_product(client, token, title="   ")
    too_long = await post_product(client, token, title="x" * 201)
    control_characters = await post_product(client, token, title="bad\x00title")
    delete_character = await post_product(client, token, title="bad\x7ftitle")
    missing = await client.post(
        "/api/products",
        headers={TOKEN_HEADER: token},
        files={"image": ("product.png", PNG_BYTES, "image/png")},
    )

    assert spaces_only.status_code == 422
    assert too_long.status_code == 422
    assert control_characters.status_code == 422
    assert delete_character.status_code == 422
    assert missing.status_code == 422


async def test_title_max_length_is_accepted(client: AsyncClient, token: str) -> None:
    response = await post_product(client, token, title="x" * 200)

    assert response.status_code == 201
    assert response.json()["title"] == "x" * 200


async def test_idempotency_key_returns_existing_product(
    client: AsyncClient,
    token: str,
    storage: FakeStorage,
) -> None:
    first = await post_product(client, token, title="Первый", idempotency_key="update-1")
    second = await post_product(client, token, title="Второй", idempotency_key="update-1")

    listing = await client.get("/api/products")

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["title"] == "Первый"
    assert listing.json()["total"] == 1
    assert len(storage.objects) == 1


async def test_different_idempotency_keys_create_products(
    client: AsyncClient,
    token: str,
) -> None:
    first = await post_product(client, token, idempotency_key="update-1")
    second = await post_product(client, token, idempotency_key="update-2")

    assert first.json()["id"] != second.json()["id"]
    assert (await client.get("/api/products")).json()["total"] == 2


async def test_idempotency_key_length_is_validated(client: AsyncClient, token: str) -> None:
    response = await post_product(client, token, idempotency_key="x" * 129)

    assert response.status_code == 422


async def test_pagination_bounds_are_validated(client: AsyncClient) -> None:
    assert (await client.get("/api/products", params={"limit": 0})).status_code == 422
    assert (await client.get("/api/products", params={"limit": 101})).status_code == 422
    assert (await client.get("/api/products", params={"offset": -1})).status_code == 422
    assert (await client.get("/api/products", params={"offset": 10**30})).status_code == 422


async def test_product_id_bounds_are_validated(client: AsyncClient) -> None:
    for product_id in (0, -1, 2**63, 10**30):
        response = await client.get(f"/api/products/{product_id}/image")
        assert response.status_code == 422


async def test_oversized_request_is_rejected_before_parsing(
    client: AsyncClient,
    token: str,
) -> None:
    body = b"x" * (2048 + MAX_MULTIPART_OVERHEAD + 1)

    response = await client.post(
        "/api/products",
        headers={
            TOKEN_HEADER: token,
            "Content-Type": "multipart/form-data; boundary=test",
            "Origin": "http://localhost:3000",
        },
        content=body,
    )

    assert response.status_code == 413
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


async def test_image_is_served(client: AsyncClient, token: str) -> None:
    created = await post_product(client, token)
    product_id = created.json()["id"]

    response = await client.get(f"/api/products/{product_id}/image")

    assert response.status_code == 200
    assert response.content == PNG_BYTES
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "public, max-age=3600"
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_missing_product_and_object(
    client: AsyncClient,
    token: str,
    storage: FakeStorage,
) -> None:
    created = await post_product(client, token)
    product_id = created.json()["id"]
    storage.objects.clear()

    missing_product = await client.get("/api/products/999999/image")
    missing_object = await client.get(f"/api/products/{product_id}/image")

    assert missing_product.status_code == 404
    assert missing_object.status_code == 404


async def test_storage_unavailable_on_upload(client: AsyncClient, token: str) -> None:
    app.dependency_overrides[get_storage] = lambda: FailingStorage()

    response = await post_product(client, token)

    assert response.status_code == 503


async def test_storage_unavailable_on_download(client: AsyncClient, token: str) -> None:
    created = await post_product(client, token)
    product_id = created.json()["id"]
    app.dependency_overrides[get_storage] = lambda: FailingStorage()

    response = await client.get(f"/api/products/{product_id}/image")

    assert response.status_code == 503


async def test_corrupted_storage_object(client: AsyncClient, token: str) -> None:
    created = await post_product(client, token)
    product_id = created.json()["id"]
    app.dependency_overrides[get_storage] = lambda: CorruptedStorage()

    response = await client.get(f"/api/products/{product_id}/image")

    assert response.status_code == 500


async def test_database_failure_maps_to_503(client: AsyncClient) -> None:
    async def broken_session() -> BrokenSession:
        yield BrokenSession()

    app.dependency_overrides[get_session] = broken_session

    response = await client.get("/api/products")

    assert response.status_code == 503


async def test_unreachable_database_maps_to_503(
    client: AsyncClient,
    monkeypatch,
) -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    engine = create_async_engine(
        f"postgresql+asyncpg://catalog:catalog@127.0.0.1:{port}/catalog_test",
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(session_module, "get_session_factory", lambda: factory)
    app.dependency_overrides.pop(get_session, None)

    try:
        health = await client.get("/health")
        catalog = await client.get("/api/products")
    finally:
        await engine.dispose()

    assert health.status_code == 503
    assert catalog.status_code == 503
