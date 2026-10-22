from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import StorageService, StorageUnavailable, get_storage
from app.db.session import get_session
from app.schemas.health import HealthStatus

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
async def health_route(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HealthStatus:
    await session.execute(text("SELECT 1"))
    return HealthStatus(status="ok")


@router.get("/ready", response_model=HealthStatus)
async def ready_route(
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[StorageService, Depends(get_storage)],
) -> HealthStatus:
    await session.execute(text("SELECT 1"))
    try:
        await storage.check()
    except StorageUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="storage is unavailable",
        ) from exc
    return HealthStatus(status="ok")
