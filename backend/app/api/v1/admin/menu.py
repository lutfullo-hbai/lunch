from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile, status

from app.api.deps import DbSession
from app.schemas.common import Page, Pagination
from app.schemas.menu import MenuItemCreate, MenuItemOut, MenuItemUpdate
from app.services import menu as service

router = APIRouter(prefix="/menu", tags=["admin: menu"])


@router.get("")
async def list_items(
    db: DbSession,
    page: Pagination,
    category_id: int | None = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
    is_available: bool | None = None,
) -> Page[MenuItemOut]:
    return await service.list_items(db, page, category_id, search, is_available)


@router.get("/{item_id}")
async def get_item(item_id: int, db: DbSession) -> MenuItemOut:
    return service.to_out(await service.get_item(db, item_id))


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_item(data: MenuItemCreate, db: DbSession) -> MenuItemOut:
    return service.to_out(await service.create_item(db, data))


@router.patch("/{item_id}")
async def update_item(item_id: int, data: MenuItemUpdate, db: DbSession) -> MenuItemOut:
    return service.to_out(await service.update_item(db, item_id, data))


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: int, db: DbSession) -> None:
    await service.delete_item(db, item_id)


@router.put("/{item_id}/image")
async def upload_image(
    item_id: int, db: DbSession, image: Annotated[UploadFile, File()]
) -> MenuItemOut:
    return service.to_out(await service.set_image(db, item_id, image))


@router.delete("/{item_id}/image")
async def delete_image(item_id: int, db: DbSession) -> MenuItemOut:
    return service.to_out(await service.remove_image(db, item_id))
