import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import (
    DBAPIError,
    DisconnectionError,
    OperationalError,
    SQLAlchemyError,
)
from sqlalchemy.exc import (
    TimeoutError as SATimeoutError,
)

from app.api.routes import health, products
from app.core.config import get_settings
from app.db.session import DatabaseUnavailable, get_engine

logger = logging.getLogger("catalog.api")

settings = get_settings()

MAX_MULTIPART_OVERHEAD = 64 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await get_engine().dispose()


app = FastAPI(title="catalog-api", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def limit_product_upload(request: Request, call_next):
    if request.method == "POST" and request.url.path == "/api/products":
        raw_length = request.headers.get("content-length")
        if raw_length is None:
            return JSONResponse(status_code=413, content={"detail": "image is too large"})
        try:
            content_length = int(raw_length)
        except ValueError:
            return JSONResponse(status_code=413, content={"detail": "image is too large"})
        if content_length < 0 or content_length > settings.max_image_bytes + MAX_MULTIPART_OVERHEAD:
            return JSONResponse(status_code=413, content={"detail": "image is too large"})
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Internal-Token", "X-Idempotency-Key"],
)


def _database_unavailable(exc: SQLAlchemyError) -> bool:
    if isinstance(exc, (OperationalError, DisconnectionError, SATimeoutError)):
        return True
    return isinstance(exc, DBAPIError) and exc.connection_invalidated


@app.exception_handler(DatabaseUnavailable)
async def database_unavailable_handler(request: Request, exc: DatabaseUnavailable) -> JSONResponse:
    logger.warning("database unavailable on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=503, content={"detail": "database is unavailable"})


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    if _database_unavailable(exc):
        logger.warning("database unavailable on %s: %s", request.url.path, exc)
        return JSONResponse(status_code=503, content={"detail": "database is unavailable"})
    logger.exception("database error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "internal server error"})


app.include_router(health.router)
app.include_router(products.router)
