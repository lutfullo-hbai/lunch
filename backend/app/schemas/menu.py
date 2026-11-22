from decimal import Decimal
from typing import Annotated

from pydantic import AliasPath, BaseModel, ConfigDict, Field, StringConstraints, computed_field

from app.core.media import public_url, thumb_path
from app.schemas.types import Id, PatchModel

ItemName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
Portion = Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)]
Price = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]


class MenuItemCreate(BaseModel):
    category_id: Id
    name: ItemName
    description: str | None = None
    price: Price
    portion: Portion | None = None
    is_available: bool = True


class MenuItemUpdate(PatchModel):
    nullable = frozenset({"description", "portion"})

    category_id: Id | None = None
    name: ItemName | None = None
    description: str | None = None
    price: Price | None = None
    portion: Portion | None = None
    is_available: bool | None = None


class MenuItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int | None
    category_name: str | None = Field(default=None, validation_alias=AliasPath("category", "name"))
    name: str
    description: str | None
    price: Decimal
    portion: str | None
    is_available: bool
    image_path: str | None = Field(exclude=True)

    @computed_field
    @property
    def image_url(self) -> str | None:
        return public_url(self.image_path)

    @computed_field
    @property
    def thumb_url(self) -> str | None:
        return public_url(thumb_path(self.image_path)) if self.image_path else None
