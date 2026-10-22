import httpx
import pytest

from app.api import ApiRejected, ApiUnavailable, ProductApi
from app.config import Settings

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture
async def make_api(settings: Settings):
    clients: list[ProductApi] = []

    def factory(transport: httpx.AsyncBaseTransport | None = None) -> ProductApi:
        api = ProductApi(settings, transport=transport)
        clients.append(api)
        return api

    yield factory

    for api in clients:
        await api.aclose()


async def test_create_product_sends_multipart(make_api) -> None:
    captured: dict[str, httpx.Request] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            201,
            json={"id": 7, "title": "Кружка", "image_url": "/api/products/7/image"},
        )

    api = make_api(httpx.MockTransport(handler))

    product = await api.create_product(
        title="Кружка",
        data=PNG_BYTES,
        content_type="image/png",
        idempotency_key="tg:1:2",
    )

    assert product.id == 7
    assert product.title == "Кружка"
    request = captured["request"]
    assert request.method == "POST"
    assert request.url.path == "/api/products"
    assert request.headers["x-internal-token"] == "test-internal-token"
    assert request.headers["x-idempotency-key"] == "tg:1:2"
    assert b'name="title"' in request.content
    assert "Кружка".encode() in request.content
    assert PNG_BYTES in request.content


@pytest.mark.parametrize(
    ("status_code", "message"),
    [
        (413, "Файл слишком большой."),
        (415, "Поддерживаются только JPEG, PNG и WebP."),
        (422, "Не удалось добавить товар"),
        (401, "настроен некорректно"),
        (403, "настроен некорректно"),
    ],
)
async def test_rejected_requests(
    make_api,
    status_code: int,
    message: str,
) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(status_code, json={"detail": "rejected"}),
    )
    api = make_api(transport)

    with pytest.raises(ApiRejected) as error:
        await api.create_product(title="Товар", data=PNG_BYTES, content_type="image/png")

    assert error.value.status_code == status_code
    assert message in error.value.user_message
    assert "test-internal-token" not in str(error.value)


async def test_server_error_is_unavailable(make_api) -> None:
    api = make_api(httpx.MockTransport(lambda request: httpx.Response(503)))

    with pytest.raises(ApiUnavailable):
        await api.create_product(title="Товар", data=PNG_BYTES, content_type="image/png")


async def test_timeout_is_unavailable(make_api) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    api = make_api(httpx.MockTransport(handler))

    with pytest.raises(ApiUnavailable):
        await api.create_product(title="Товар", data=PNG_BYTES, content_type="image/png")


async def test_invalid_payload_is_unavailable(make_api) -> None:
    api = make_api(
        httpx.MockTransport(lambda request: httpx.Response(201, content=b"not-json")),
    )

    with pytest.raises(ApiUnavailable):
        await api.create_product(title="Товар", data=PNG_BYTES, content_type="image/png")


async def test_connection_error_is_unavailable(make_api) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    api = make_api(httpx.MockTransport(handler))

    with pytest.raises(ApiUnavailable):
        await api.create_product(title="Товар", data=PNG_BYTES, content_type="image/png")

