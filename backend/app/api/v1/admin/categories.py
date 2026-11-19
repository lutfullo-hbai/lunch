from fastapi import APIRouter, status

from app.api.deps import DbSession
from app.schemas.category import CategoryCreate, CategoryOut, CategoryUpdate
from app.services import categories as service
from app.services.categories import CategoryWithCount

router = APIRouter(prefix="/categories", tags=["admin: categories"])


def _to_out(row: CategoryWithCount) -> CategoryOut:
    category = row.category
    return CategoryOut(
        id=category.id,
        name=category.name,
        sort_order=category.sort_order,
        is_active=category.is_active,
        items_count=row.items_count,
    )


@router.get("")
async def list_categories(db: DbSession) -> list[CategoryOut]:
    return [_to_out(row) for row in await service.list_categories(db)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_category(data: CategoryCreate, db: DbSession) -> CategoryOut:
    return _to_out(await service.create_category(db, data))


@router.patch("/{category_id}")
async def update_category(category_id: int, data: CategoryUpdate, db: DbSession) -> CategoryOut:
    return _to_out(await service.update_category(db, category_id, data))


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: int, db: DbSession) -> None:
    await service.delete_category(db, category_id)
