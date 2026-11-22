from fastapi import APIRouter, status

from app.api.deps import DbSession
from app.schemas.category import CategoryCreate, CategoryOut, CategoryUpdate
from app.schemas.types import Id
from app.services import categories as service

router = APIRouter(prefix="/categories", tags=["admin: categories"])


@router.get("")
async def list_categories(db: DbSession) -> list[CategoryOut]:
    return [CategoryOut.model_validate(c) for c in await service.list_categories(db)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_category(data: CategoryCreate, db: DbSession) -> CategoryOut:
    return CategoryOut.model_validate(await service.create_category(db, data))


@router.patch("/{category_id}")
async def update_category(category_id: Id, data: CategoryUpdate, db: DbSession) -> CategoryOut:
    return CategoryOut.model_validate(await service.update_category(db, category_id, data))


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: Id, db: DbSession) -> None:
    await service.delete_category(db, category_id)
