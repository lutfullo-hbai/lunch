from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.types import Int32, NoNul, PatchModel

CategoryName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100), NoNul
]


class CategoryCreate(BaseModel):
    name: CategoryName
    sort_order: Int32 = 0
    is_active: bool = True


class CategoryUpdate(PatchModel):
    name: CategoryName | None = None
    sort_order: Int32 | None = None
    is_active: bool | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort_order: int
    is_active: bool
    items_count: int
