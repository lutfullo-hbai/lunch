from datetime import date
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi import status as http_status

from app.api.deps import DbSession, Sessions
from app.core.errors import validation_error
from app.models.enums import NotifyStatus, OrderStatus, PaymentMethod
from app.schemas.common import Page, Pagination
from app.schemas.order import OrderOut, OrderStatusUpdate
from app.schemas.types import Id
from app.services import order_notify
from app.services import orders as service
from app.services.orders import OrderFilters

router = APIRouter(prefix="/orders", tags=["admin: orders"])


def order_filters(
    status: OrderStatus | None = None,
    payment_method: PaymentMethod | None = None,
    user_id: Id | None = None,
    date_from: Annotated[date | None, Query(description="YYYY-MM-DD, TIMEZONE bo'yicha")] = None,
    date_to: Annotated[date | None, Query(description="YYYY-MM-DD, shu kun ham kiradi")] = None,
    notify_status: Annotated[
        NotifyStatus | None, Query(description="failed: guruhga yuborilmaganlar")
    ] = None,
) -> OrderFilters:
    if date_from and date_to and date_from > date_to:
        raise validation_error("date_from", "date_from date_to dan keyin bo'lmasligi kerak")
    return OrderFilters(status, payment_method, user_id, date_from, date_to, notify_status)


Filters = Annotated[OrderFilters, Depends(order_filters)]


@router.get("")
async def list_orders(db: DbSession, page: Pagination, filters: Filters) -> Page[OrderOut]:
    return Page[OrderOut].of(await service.list_orders(db, page, filters), page)


@router.get("/{order_id}")
async def get_order(order_id: Id, db: DbSession) -> OrderOut:
    return OrderOut.model_validate(await service.get_order(db, order_id))


@router.patch("/{order_id}/status")
async def set_status(order_id: Id, data: OrderStatusUpdate, db: DbSession) -> OrderOut:
    return OrderOut.model_validate(await service.set_status(db, order_id, data.status))


@router.post("/{order_id}/notify", status_code=http_status.HTTP_202_ACCEPTED)
async def resend_notification(
    order_id: Id, db: DbSession, sessions: Sessions, background: BackgroundTasks
) -> OrderOut:
    """Guruhga yuborilmagan buyurtmani qayta yuboradi (fonda, qayta urinishlar bilan)."""
    order = await service.prepare_resend(db, order_id)
    background.add_task(order_notify.notify_new_order, sessions, order.id)
    return OrderOut.model_validate(order)
