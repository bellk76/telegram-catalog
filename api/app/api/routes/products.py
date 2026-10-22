import logging
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Path,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_internal_token
from app.core.config import get_settings
from app.core.images import (
    ImageTooLargeError,
    InvalidImageError,
    UnsupportedImageTypeError,
)
from app.core.storage import (
    StorageCorrupted,
    StorageNotFound,
    StorageService,
    StorageUnavailable,
    get_storage,
)
from app.db.session import get_session
from app.models.product import Product
from app.schemas.product import ProductList, ProductRead
from app.services.products import (
    InvalidTitleError,
    create_product,
    get_product,
    list_products,
)

router = APIRouter(prefix="/api", tags=["products"])

logger = logging.getLogger(__name__)

MAX_BIGINT = 2**63 - 1
MAX_OFFSET = 1_000_000


def to_read(product: Product) -> ProductRead:
    return ProductRead(
        id=product.id,
        title=product.title,
        image_url=f"/api/products/{product.id}/image",
        created_at=product.created_at,
    )


@router.post(
    "/products",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_internal_token)],
)
async def create_product_route(
    title: Annotated[str, Form(min_length=1)],
    image: Annotated[UploadFile, File()],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[StorageService, Depends(get_storage)],
    idempotency_key: Annotated[
        str | None,
        Header(alias="X-Idempotency-Key", max_length=128),
    ] = None,
) -> ProductRead:
    settings = get_settings()
    content_type = (image.content_type or "").split(";", 1)[0].strip().lower()
    data = await image.read(settings.max_image_bytes + 1)
    clean_idempotency_key = (idempotency_key or "").strip() or None

    try:
        product = await create_product(
            session,
            storage,
            title=title,
            data=data,
            content_type=content_type,
            max_bytes=settings.max_image_bytes,
            idempotency_key=clean_idempotency_key,
        )
    except UnsupportedImageTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="unsupported image type",
        ) from exc
    except ImageTooLargeError as exc:
        raise HTTPException(status_code=413, detail="image is too large") from exc
    except InvalidImageError as exc:
        raise HTTPException(status_code=422, detail="invalid image") from exc
    except InvalidTitleError as exc:
        raise HTTPException(status_code=422, detail="invalid title") from exc
    except StorageUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="storage is unavailable",
        ) from exc

    return to_read(product)


@router.get("/products", response_model=ProductList)
async def list_products_route(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=MAX_OFFSET)] = 0,
) -> ProductList:
    products, total = await list_products(session, limit=limit, offset=offset)
    return ProductList(items=[to_read(product) for product in products], total=total)


@router.get("/products/{product_id}/image")
async def product_image_route(
    product_id: Annotated[int, Path(ge=1, le=MAX_BIGINT)],
    session: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[StorageService, Depends(get_storage)],
) -> Response:
    product = await get_product(session, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="product not found",
        )

    try:
        data, detected_type = await storage.download(product.image_key)
    except StorageNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="image not found",
        ) from exc
    except StorageUnavailable as exc:
        logger.warning("storage unavailable while downloading %s", product.image_key)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="storage is unavailable",
        ) from exc
    except StorageCorrupted as exc:
        logger.error("stored image is corrupted: %s", product.image_key)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="stored image is corrupted",
        ) from exc

    return Response(
        content=data,
        media_type=detected_type,
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )
