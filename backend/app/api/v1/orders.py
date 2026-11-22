"""User buyurtmalari (JWT + imzo)."""

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.order import MyOrderOut, OrderCreate
from app.services import user_orders

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_order(data: OrderCreate, user: CurrentUser, db: DbSession) -> MyOrderOut:
    return MyOrderOut.model_validate(await user_orders.create_order(db, user, data))
