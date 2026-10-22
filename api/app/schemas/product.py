from datetime import datetime

from pydantic import BaseModel


class ProductRead(BaseModel):
    id: int
    title: str
    image_url: str
    created_at: datetime


class ProductList(BaseModel):
    items: list[ProductRead]
    total: int
