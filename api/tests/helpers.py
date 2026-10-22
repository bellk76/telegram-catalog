from sqlalchemy.exc import OperationalError, ProgrammingError

from app.core.storage import StorageCorrupted, StorageNotFound, StorageUnavailable

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG_BYTES = b"\xff\xd8\xff" + b"\x00" * 32
WEBP_BYTES = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 32


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    async def download(self, key: str) -> tuple[bytes, str]:
        if key not in self.objects:
            raise StorageNotFound(key)
        return self.objects[key]

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    async def check(self) -> None:
        return None


class FailingStorage(FakeStorage):
    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        raise StorageUnavailable("upload failed")

    async def download(self, key: str) -> tuple[bytes, str]:
        raise StorageUnavailable("download failed")

    async def check(self) -> None:
        raise StorageUnavailable("storage is down")


class CorruptedStorage(FakeStorage):
    async def download(self, key: str) -> tuple[bytes, str]:
        raise StorageCorrupted("corrupted")


class BrokenSession:
    async def execute(self, *args: object, **kwargs: object) -> None:
        raise _database_error()

    async def scalar(self, *args: object, **kwargs: object) -> None:
        raise _database_error()


class FailingCommitSession(BrokenSession):
    def __init__(self) -> None:
        self.rollback_calls = 0

    def add(self, instance: object) -> None:
        pass

    async def rollback(self) -> None:
        self.rollback_calls += 1

    async def commit(self) -> None:
        raise _database_error()


class OfflineCommitSession(FailingCommitSession):
    async def commit(self) -> None:
        raise OSError("connection lost")


class ConfirmedMissingCommitSession(FailingCommitSession):
    async def scalar(self, *args: object, **kwargs: object) -> None:
        assert "products.image_key" in str(args[0])
        return None


class PersistedCommitSession(FailingCommitSession):
    async def scalar(self, *args: object, **kwargs: object) -> int:
        assert "products.image_key" in str(args[0])
        return 1


class BrokenProgrammingSession:
    async def execute(self, *args: object, **kwargs: object) -> None:
        raise ProgrammingError("SELECT 1", {}, Exception("bad statement"))


def _database_error() -> OperationalError:
    return OperationalError("SELECT 1", {}, Exception("database is down"))
