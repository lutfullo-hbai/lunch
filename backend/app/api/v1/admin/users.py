from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.models.enums import UserRole
from app.schemas.common import Page, Pagination
from app.schemas.user import AdminUserOut, UserStatusUpdate
from app.services import users as service

router = APIRouter(prefix="/users", tags=["admin: users"])


@router.get("")
async def list_users(
    db: DbSession,
    page: Pagination,
    search: Annotated[str | None, Query(max_length=100)] = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
) -> Page[AdminUserOut]:
    return await service.list_users(db, page, search, role, is_active)


@router.get("/{user_id}")
async def get_user(user_id: int, db: DbSession) -> AdminUserOut:
    return await service.get_user(db, user_id)


@router.patch("/{user_id}/status")
async def set_status(user_id: int, data: UserStatusUpdate, db: DbSession) -> AdminUserOut:
    return await service.set_status(db, user_id, data.is_active)
