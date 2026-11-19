from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

ItemName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
Portion = Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)]
Price = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]


class MenuItemCreate(BaseModel):
    category_id: int
    name: ItemName
    description: str | None = None
    price: Price
    portion: Portion | None = None
    is_available: bool = True


class MenuItemUpdate(BaseModel):
    category_id: int | None = None
    name: ItemName | None = None
    description: str | None = None
    price: Price | None = None
    portion: Portion | None = None
    is_available: bool | None = None


class MenuItemOut(BaseModel):
    id: int
    category_id: int | None
    category_name: str | None
    name: str
    description: str | None
    price: Decimal
    portion: str | None
    is_available: bool
    image_url: str | None
    thumb_url: str | None
