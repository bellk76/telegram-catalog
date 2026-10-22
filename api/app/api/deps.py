import secrets

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def require_internal_token(
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
) -> None:
    expected = get_settings().api_internal_token.get_secret_value()
    provided_bytes = (x_internal_token or "").encode("utf-8")
    expected_bytes = expected.encode("utf-8")
    if not x_internal_token or not secrets.compare_digest(provided_bytes, expected_bytes):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid internal token",
        )
