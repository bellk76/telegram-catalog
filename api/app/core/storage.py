import asyncio
import io
import logging
from functools import lru_cache

import urllib3
from minio import Minio
from minio.error import InvalidResponseError, S3Error, ServerError

from app.core.config import get_settings
from app.core.images import detect_image_type, validate_image

logger = logging.getLogger(__name__)

NOT_FOUND_CODES = {"NoSuchKey", "NoSuchObject", "NoSuchVersion"}


class StorageError(Exception):
    pass


class StorageNotFound(StorageError):
    pass


class StorageCorrupted(StorageError):
    pass


class StorageUnavailable(StorageError):
    pass


class StorageService:
    def __init__(self, client: Minio, bucket: str, max_bytes: int) -> None:
        self._client = client
        self._bucket = bucket
        self._max_bytes = max_bytes

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        validate_image(data, content_type, self._max_bytes)

        def put() -> None:
            self._client.put_object(
                self._bucket,
                key,
                io.BytesIO(data),
                length=len(data),
                content_type=content_type,
            )

        try:
            await asyncio.to_thread(put)
        except (InvalidResponseError, ServerError, S3Error, urllib3.exceptions.HTTPError) as exc:
            raise StorageUnavailable("failed to upload object") from exc

    async def check(self) -> None:
        def bucket_exists() -> bool:
            return self._client.bucket_exists(self._bucket)

        try:
            exists = await asyncio.to_thread(bucket_exists)
        except (InvalidResponseError, ServerError, S3Error, urllib3.exceptions.HTTPError) as exc:
            raise StorageUnavailable("failed to check storage") from exc
        if not exists:
            raise StorageUnavailable("bucket is missing")

    async def download(self, key: str) -> tuple[bytes, str]:
        def get() -> tuple[bytes, str]:
            response = self._client.get_object(self._bucket, key, length=self._max_bytes + 1)
            try:
                data = response.read(self._max_bytes + 1)
            finally:
                response.close()
                response.release_conn()

            if len(data) > self._max_bytes:
                raise StorageCorrupted("stored object is too large")
            detected = detect_image_type(data)
            if detected is None:
                raise StorageCorrupted("stored object is not a supported image")
            return data, detected

        try:
            return await asyncio.to_thread(get)
        except S3Error as exc:
            if exc.code in NOT_FOUND_CODES:
                raise StorageNotFound(key) from exc
            logger.warning("storage download failed for %s: %s", key, exc.code)
            raise StorageUnavailable("failed to download object") from exc
        except (InvalidResponseError, ServerError, urllib3.exceptions.HTTPError) as exc:
            raise StorageUnavailable("failed to download object") from exc

    async def delete(self, key: str) -> None:
        try:
            await asyncio.to_thread(self._client.remove_object, self._bucket, key)
        except (InvalidResponseError, ServerError, S3Error, urllib3.exceptions.HTTPError) as exc:
            raise StorageUnavailable("failed to delete object") from exc


@lru_cache
def get_minio_client() -> Minio:
    settings = get_settings()
    http_client = urllib3.PoolManager(
        timeout=urllib3.Timeout(connect=2.0, read=10.0),
        retries=urllib3.Retry(total=2, backoff_factor=0.2),
    )
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_app_user,
        secret_key=settings.minio_app_password.get_secret_value(),
        secure=settings.minio_secure,
        http_client=http_client,
    )


def get_storage() -> StorageService:
    settings = get_settings()
    return StorageService(get_minio_client(), settings.minio_bucket, settings.max_image_bytes)


__all__ = [
    "StorageCorrupted",
    "StorageError",
    "StorageNotFound",
    "StorageService",
    "StorageUnavailable",
    "get_storage",
]
