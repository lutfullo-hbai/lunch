from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.models.enums import UserRole
from app.schemas.common import Page, Pagination
from app.schemas.order import OrderOut
from app.schemas.user import AdminUserOut, UserStatusUpdate
from app.services import orders as orders_service
from app.services import users as service
from app.services.orders import OrderFilters

router = APIRouter(prefix="/users", tags=["admin: users"])


@router.get("")
async def list_users(
    db: DbSession,
    page: Pagination,
    search: Annotated[str | None, Query(max_length=100)] = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
) -> Page[AdminUserOut]:
    result = await service.list_users(db, page, search, role, is_active)
    return Page[AdminUserOut].of(result, page)


@router.get("/{user_id}")
async def get_user(user_id: int, db: DbSession) -> AdminUserOut:
    return AdminUserOut.model_validate(await service.get_user(db, user_id))


@router.get("/{user_id}/orders")
async def user_orders(user_id: int, db: DbSession, page: Pagination) -> Page[OrderOut]:
    await service.get_user(db, user_id)  # user yo'q bo'lsa 404
    result = await orders_service.list_orders(db, page, OrderFilters(user_id=user_id))
    return Page[OrderOut].of(result, page)


@router.patch("/{user_id}/status")
async def set_status(user_id: int, data: UserStatusUpdate, db: DbSession) -> AdminUserOut:
    return AdminUserOut.model_validate(await service.set_status(db, user_id, data.is_active))
