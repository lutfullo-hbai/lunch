from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi import status as http_status

from app.api.deps import DbSession
from app.core.errors import AppError
from app.models.enums import OrderStatus, PaymentMethod
from app.schemas.common import Page, Pagination
from app.schemas.order import OrderOut, OrderStatusUpdate
from app.services import orders as service
from app.services.orders import OrderFilters

router = APIRouter(prefix="/orders", tags=["admin: orders"])


def order_filters(
    status: OrderStatus | None = None,
    payment_method: PaymentMethod | None = None,
    user_id: int | None = None,
    date_from: Annotated[date | None, Query(description="YYYY-MM-DD, TIMEZONE bo'yicha")] = None,
    date_to: Annotated[date | None, Query(description="YYYY-MM-DD, shu kun ham kiradi")] = None,
) -> OrderFilters:
    if date_from and date_to and date_from > date_to:
        raise AppError(
            http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            "INVALID_DATE_RANGE",
            "date_from date_to dan keyin bo'lmasligi kerak",
        )
    return OrderFilters(status, payment_method, user_id, date_from, date_to)


Filters = Annotated[OrderFilters, Depends(order_filters)]


@router.get("")
async def list_orders(db: DbSession, page: Pagination, filters: Filters) -> Page[OrderOut]:
    return await service.list_orders(db, page, filters)


@router.get("/{order_id}")
async def get_order(order_id: int, db: DbSession) -> OrderOut:
    return service.to_out(await service.get_order(db, order_id))


@router.patch("/{order_id}/status")
async def change_status(order_id: int, data: OrderStatusUpdate, db: DbSession) -> OrderOut:
    return service.to_out(await service.change_status(db, order_id, data.status))
