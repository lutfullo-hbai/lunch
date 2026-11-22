"""User uchun menyu. Login qilgan har bir user ko'ra oladi (JWT + imzo)."""

from fastapi import APIRouter, Depends

from app.api.deps import DbSession, get_current_user
from app.schemas.category import CategoryPublicOut
from app.schemas.menu import MenuItemOut
from app.schemas.types import Id
from app.services import catalog

router = APIRouter(tags=["menu"], dependencies=[Depends(get_current_user)])


@router.get("/categories")
async def list_categories(db: DbSession) -> list[CategoryPublicOut]:
    return [CategoryPublicOut.model_validate(c) for c in await catalog.list_categories(db)]


@router.get("/menu")
async def list_items(db: DbSession, category_id: Id | None = None) -> list[MenuItemOut]:
    return [MenuItemOut.model_validate(i) for i in await catalog.list_items(db, category_id)]


@router.get("/menu/{item_id}")
async def get_item(item_id: Id, db: DbSession) -> MenuItemOut:
    return MenuItemOut.model_validate(await catalog.get_item(db, item_id))
