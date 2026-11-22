"""User buyurtmalari (JWT + imzo)."""

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Page, Pagination
from app.schemas.order import MyOrderOut, OrderCreate
from app.schemas.types import Id
from app.services import user_orders

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_order(data: OrderCreate, user: CurrentUser, db: DbSession) -> MyOrderOut:
    return MyOrderOut.model_validate(await user_orders.create_order(db, user, data))


@router.get("/me")
async def list_my_orders(user: CurrentUser, db: DbSession, page: Pagination) -> Page[MyOrderOut]:
    return Page[MyOrderOut].of(await user_orders.list_orders(db, user, page), page)


@router.get("/me/{order_id}")
async def get_my_order(order_id: Id, user: CurrentUser, db: DbSession) -> MyOrderOut:
    return MyOrderOut.model_validate(await user_orders.get_order(db, user, order_id))
