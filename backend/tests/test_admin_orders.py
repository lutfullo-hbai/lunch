from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.core.config import get_settings
from app.models import Category, MenuItem, Order, OrderItem
from app.models.enums import OrderStatus, PaymentMethod
from tests.helpers import admin_tokens, register, signed_request


@pytest.fixture
async def admin(client, db) -> dict:
    return await admin_tokens(client, db)


@pytest.fixture
async def customer(client) -> dict:
    return await register(client, email="mijoz@example.com")


@pytest.fixture
async def make_order(db, customer):
    item = MenuItem(category=Category(name="Osh"), name="Palov", price=Decimal("45000"))
    db.add(item)
    await db.flush()

    async def factory(
        payment: PaymentMethod = PaymentMethod.CASH,
        status: OrderStatus = OrderStatus.NEW,
        created_at: datetime | None = None,
        quantity: int = 2,
    ) -> Order:
        order = Order(
            user_id=customer["user"]["id"],
            total_price=item.price * quantity,
            payment_method=payment,
            status=status,
            phone="+998901234567",
            address="Toshkent, Chilonzor",
            items=[
                OrderItem(
                    menu_item_id=item.id,
                    name_snapshot=item.name,
                    price_snapshot=item.price,
                    quantity=quantity,
                )
            ],
        )
        if created_at is not None:
            order.created_at = created_at
        db.add(order)
        await db.commit()
        return order

    return factory


async def test_regular_user_forbidden(client, customer):
    response = await signed_request(client, customer, "GET", "/admin/orders")
    assert response.status_code == 403


async def test_order_detail(client, admin, make_order):
    order = await make_order(quantity=3)
    response = await signed_request(client, admin, "GET", f"/admin/orders/{order.id}")
    body = response.json()

    assert response.status_code == 200
    assert body["user"]["email"] == "mijoz@example.com"
    assert body["items"][0]["name"] == "Palov"
    assert Decimal(body["items"][0]["subtotal"]) == Decimal("135000")
    assert body["allowed_statuses"] == ["accepted", "cancelled"]


async def test_filters(client, admin, make_order):
    await make_order(payment=PaymentMethod.CASH)
    await make_order(payment=PaymentMethod.CARD)
    await make_order(payment=PaymentMethod.CARD, status=OrderStatus.DELIVERED)

    cards = (await signed_request(client, admin, "GET", "/admin/orders?payment_method=card")).json()
    assert cards["total"] == 2

    new_cards = (
        await signed_request(client, admin, "GET", "/admin/orders?payment_method=card&status=new")
    ).json()
    assert new_cards["total"] == 1


async def test_date_filter_uses_local_timezone(client, admin, make_order):
    tz = get_settings().tz
    today = datetime.now(tz).date()
    yesterday = today - timedelta(days=1)
    # Kecha mahalliy vaqt bilan 23:30. UTC bo'yicha hisoblansa, boshqa kunga tushib qolardi.
    late_yesterday = datetime.combine(yesterday, datetime.min.time(), tzinfo=tz) + timedelta(
        hours=23, minutes=30
    )
    await make_order(created_at=late_yesterday)
    await make_order()

    only_today = (
        await signed_request(client, admin, "GET", f"/admin/orders?date_from={today}")
    ).json()
    only_yesterday = (
        await signed_request(
            client, admin, "GET", f"/admin/orders?date_from={yesterday}&date_to={yesterday}"
        )
    ).json()
    assert only_today["total"] == 1
    assert only_yesterday["total"] == 1


async def test_invalid_date_range(client, admin):
    response = await signed_request(
        client, admin, "GET", "/admin/orders?date_from=2026-11-20&date_to=2026-11-19"
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_DATE_RANGE"


async def test_status_flow(client, admin, make_order):
    order = await make_order()
    path = f"/admin/orders/{order.id}/status"

    for status in ("accepted", "ready", "delivered"):
        response = await signed_request(client, admin, "PATCH", path, {"status": status})
        assert response.status_code == 200, response.text
        assert response.json()["status"] == status

    assert response.json()["allowed_statuses"] == []


async def test_invalid_transition(client, admin, make_order):
    order = await make_order()
    response = await signed_request(
        client, admin, "PATCH", f"/admin/orders/{order.id}/status", {"status": "delivered"}
    )
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "INVALID_STATUS_TRANSITION"
    assert error["details"]["allowed"] == ["accepted", "cancelled"]


async def test_cancelled_order_is_closed(client, admin, make_order):
    order = await make_order(status=OrderStatus.CANCELLED)
    response = await signed_request(
        client, admin, "PATCH", f"/admin/orders/{order.id}/status", {"status": "accepted"}
    )
    assert response.status_code == 409


async def test_missing_order(client, admin):
    response = await signed_request(client, admin, "GET", "/admin/orders/999999")
    assert response.status_code == 404


async def test_user_orders(client, admin, customer, make_order):
    await make_order()
    await make_order()
    user_id = customer["user"]["id"]

    orders = (await signed_request(client, admin, "GET", f"/admin/users/{user_id}/orders")).json()
    assert orders["total"] == 2

    user = (await signed_request(client, admin, "GET", f"/admin/users/{user_id}")).json()
    assert user["orders_count"] == 2

    missing = await signed_request(client, admin, "GET", "/admin/users/999999/orders")
    assert missing.status_code == 404
