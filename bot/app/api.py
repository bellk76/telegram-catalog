from dataclasses import dataclass

import httpx

from app.config import Settings


@dataclass(frozen=True)
class Product:
    id: int
    title: str


class ApiError(Exception):
    pass


class ApiUnavailable(ApiError):
    pass


class ApiRejected(ApiError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail

    @property
    def user_message(self) -> str:
        if self.status_code in (401, 403):
            return "Сервис каталога настроен некорректно, обратитесь к администратору."
        if self.status_code == 413:
            return "Файл слишком большой."
        if self.status_code == 415:
            return "Поддерживаются только JPEG, PNG и WebP."
        if self.status_code == 422:
            return "Не удалось добавить товар: проверьте название и изображение."
        return "Не удалось добавить товар."


class ProductApi:
    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._token = settings.api_internal_token.get_secret_value()
        self._client = httpx.AsyncClient(
            base_url=settings.api_internal_url.rstrip("/"),
            timeout=settings.api_timeout,
            transport=transport,
        )

    async def __aenter__(self) -> "ProductApi":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def create_product(
        self,
        *,
        title: str,
        data: bytes,
        content_type: str,
        idempotency_key: str | None = None,
    ) -> Product:
        headers = {"X-Internal-Token": self._token}
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        extension = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }.get(content_type, "")
        files = {"image": (f"product{extension}", data, content_type)}

        try:
            response = await self._client.post(
                "/api/products",
                headers=headers,
                data={"title": title},
                files=files,
            )
        except (httpx.HTTPError, httpx.InvalidURL) as exc:
            raise ApiUnavailable("API request failed") from exc

        if response.status_code >= 500:
            raise ApiUnavailable(f"API returned {response.status_code}")
        if response.status_code >= 400:
            raise ApiRejected(response.status_code, self._detail(response))

        try:
            payload = response.json()
            return Product(id=int(payload["id"]), title=str(payload["title"]))
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ApiUnavailable("API returned an invalid payload") from exc

    @staticmethod
    def _detail(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text[:200]
        if isinstance(payload, dict) and "detail" in payload:
            return str(payload["detail"])[:200]
        return "request rejected"
