"""Dashboard ko'rsatkichlari: qo'lda hisoblangan natija bilan solishtiriladi.

"Bugun" = 2026-11-20 (Asia/Tashkent, UTC+5). Buyurtmalar:

| Buyurtma | Mahalliy vaqt     | Holat     | To'lov | Ovqat      | Summa  |
| A        | 11-20 10:00       | delivered | naqd   | Palov × 2  | 90 000 |
| B        | 11-20 23:30       | delivered | karta  | Choy × 1   |  5 000 |
| D        | 11-20 00:10 (UTC 11-19!) | new | naqd   | Palov × 1  | 45 000 |
| G        | 11-19 23:30       | delivered | naqd   | Palov × 1  | 45 000 |
| E        | 11-18 12:00       | cancelled | karta  | Palov × 1  | 45 000 |
| F        | 11-14 12:00       | delivered | naqd   | Choy × 1   |  5 000 |
| H        | 11-01 12:00       | accepted  | karta  | Choy × 2   | 10 000 |
"""

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import Category, MenuItem, Order, OrderItem, User
from app.models.enums import OrderStatus, PaymentMethod
from app.services import stats
from tests.helpers import admin_tokens, register, signed_request

TODAY = date(2026, 11, 20)


def local(month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=ZoneInfo(get_settings().timezone))


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch):
    monkeypatch.setattr(stats, "local_today", lambda: TODAY)


@pytest.fixture
async def admin(client, db) -> dict:
    return await admin_tokens(client, db)


@pytest.fixture
async def data(db):
    users = [
        User(
            email=f"u{i}@example.com",
            full_name=f"User {i}",
            password_hash=hash_password("x" * 8),
            created_at=created,
        )
        for i, created in enumerate([local(11, 20, 9), local(11, 15, 9), local(11, 1, 9)])
    ]
    palov = MenuItem(category=Category(name="Osh"), name="Palov", price=Decimal("45000"))
    choy = MenuItem(category=Category(name="Ichimlik"), name="Choy", price=Decimal("5000"))
    db.add_all([*users, palov, choy])
    await db.flush()

    def order(created, status, payment, item, quantity):
        return Order(
            user_id=users[0].id,
            total_price=item.price * quantity,
            payment_method=payment,
            status=status,
            created_at=created,
            items=[
                OrderItem(
                    menu_item_id=item.id,
                    name_snapshot=item.name,
                    price_snapshot=item.price,
                    quantity=quantity,
                )
            ],
        )

    cash, card = PaymentMethod.CASH, PaymentMethod.CARD
    db.add_all(
        [
            order(local(11, 20, 10), OrderStatus.DELIVERED, cash, palov, 2),  # A
            order(local(11, 20, 23, 30), OrderStatus.DELIVERED, card, choy, 1),  # B
            order(local(11, 20, 0, 10), OrderStatus.NEW, cash, palov, 1),  # D
            order(local(11, 19, 23, 30), OrderStatus.DELIVERED, cash, palov, 1),  # G
            order(local(11, 18, 12), OrderStatus.CANCELLED, card, palov, 1),  # E
            order(local(11, 14, 12), OrderStatus.DELIVERED, cash, choy, 1),  # F
            order(local(11, 1, 12), OrderStatus.ACCEPTED, card, choy, 2),  # H
        ]
    )
    await db.commit()
    return {"palov": palov.id, "choy": choy.id}


async def get_stats(client, admin, period: str) -> dict:
    response = await signed_request(client, admin, "GET", f"/admin/stats?period={period}")
    assert response.status_code == 200, response.text
    return response.json()


def money(value: str) -> Decimal:
    return Decimal(value)


async def test_today(client, admin, data):
    body = await get_stats(client, admin, "today")

    assert (body["date_from"], body["date_to"]) == ("2026-11-20", "2026-11-20")
    # D (00:10 mahalliy) UTC bo'yicha 19-noyabr, lekin bugungi kunga tushadi.
    assert body["orders"]["total"] == 3
    assert body["orders"]["by_status"] == {
        "new": 1,
        "accepted": 0,
        "ready": 0,
        "delivered": 2,
        "cancelled": 0,
    }
    assert money(body["revenue"]["cash"]) == Decimal("90000")
    assert money(body["revenue"]["card"]) == Decimal("5000")
    assert money(body["revenue"]["total"]) == Decimal("95000")
    assert [(d["date"], d["orders"], money(d["revenue"])) for d in body["daily"]] == [
        ("2026-11-20", 3, Decimal("95000"))
    ]
    assert [(t["name"], t["quantity"], money(t["revenue"])) for t in body["top_items"]] == [
        ("Palov", 3, Decimal("135000")),
        ("Choy", 1, Decimal("5000")),
    ]
    assert body["users"] == {"total": 3, "new": 1}  # admin hisobga kirmaydi
    assert body["pending_orders"] == 2  # D va H: davrdan qat'i nazar


async def test_seven_days(client, admin, data):
    body = await get_stats(client, admin, "7d")

    assert (body["date_from"], body["date_to"]) == ("2026-11-14", "2026-11-20")
    assert body["orders"]["total"] == 6
    assert body["orders"]["by_status"]["delivered"] == 4
    assert body["orders"]["by_status"]["cancelled"] == 1
    # Tushum faqat yetkazilganlardan: A + G + F naqd, B karta. E (bekor) kirmaydi.
    assert money(body["revenue"]["cash"]) == Decimal("140000")
    assert money(body["revenue"]["card"]) == Decimal("5000")
    assert [(d["date"], d["orders"], money(d["revenue"])) for d in body["daily"]] == [
        ("2026-11-14", 1, Decimal("5000")),
        ("2026-11-15", 0, Decimal("0")),
        ("2026-11-16", 0, Decimal("0")),
        ("2026-11-17", 0, Decimal("0")),
        ("2026-11-18", 1, Decimal("0")),  # faqat bekor qilingan
        ("2026-11-19", 1, Decimal("45000")),
        ("2026-11-20", 3, Decimal("95000")),
    ]
    assert [(t["name"], t["quantity"]) for t in body["top_items"]] == [("Palov", 4), ("Choy", 2)]
    assert body["users"]["new"] == 2


async def test_thirty_days(client, admin, data):
    body = await get_stats(client, admin, "30d")

    assert (body["date_from"], body["date_to"]) == ("2026-10-22", "2026-11-20")
    assert len(body["daily"]) == 30
    assert body["orders"]["total"] == 7
    assert body["orders"]["by_status"]["accepted"] == 1
    assert money(body["revenue"]["total"]) == Decimal("145000")  # H yetkazilmagan
    assert body["users"]["new"] == 3


async def test_empty_database_gives_zeros(client, admin):
    body = await get_stats(client, admin, "30d")
    assert body["orders"]["total"] == 0
    assert money(body["revenue"]["total"]) == 0
    assert body["top_items"] == []
    assert len(body["daily"]) == 30
    assert all(d["orders"] == 0 for d in body["daily"])


async def test_default_period_is_today(client, admin):
    response = await signed_request(client, admin, "GET", "/admin/stats")
    assert response.json()["period"] == "today"


async def test_invalid_period_is_422(client, admin):
    response = await signed_request(client, admin, "GET", "/admin/stats?period=year")
    assert response.status_code == 422


async def test_regular_user_gets_403(client):
    user = await register(client)
    response = await signed_request(client, user, "GET", "/admin/stats")
    assert response.status_code == 403


async def test_top_items_keep_the_name_at_order_time(client, admin, data, db):
    from sqlalchemy import update

    await db.execute(
        update(MenuItem).where(MenuItem.id == data["palov"]).values(name="Yangi palov")
    )
    await db.commit()
    body = await get_stats(client, admin, "7d")
    assert body["top_items"][0]["name"] == "Palov"
