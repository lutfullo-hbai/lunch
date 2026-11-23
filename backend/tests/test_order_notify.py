"""Buyurtmalar guruhiga Telegram xabari: matn, qayta urinish, failed, token sir qolishi."""

import json
import logging

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import get_settings
from app.services import telegram
from tests.helpers import admin_tokens, signed_request
from tests.test_menu import make_category, make_item

TOKEN = "123456:secret-bot-token"
CHAT_ID = -1001234567890


class FakeTelegram:
    def __init__(self, fail_times: int = 0, error: Exception | None = None) -> None:
        self.fail_times = fail_times
        self.error = error
        self.sent: list[dict] = []
        self.calls = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        if self.error is not None:
            raise self.error
        if self.calls <= self.fail_times:
            return httpx.Response(502, json={"ok": False, "description": "Bad Gateway"})
        self.sent.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "result": {}})


@pytest.fixture
def configure(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "bot_token", SecretStr(TOKEN))
    monkeypatch.setattr(settings, "orders_group_chat_id", CHAT_ID)
    monkeypatch.setattr(settings, "notify_retry_delays", [0, 0, 0])

    def install(fake: FakeTelegram) -> FakeTelegram:
        monkeypatch.setattr(telegram, "transport", httpx.MockTransport(fake.handler))
        return fake

    return install


@pytest.fixture
async def admin(client, db) -> dict:
    return await admin_tokens(client, db)


@pytest.fixture
async def user(client) -> dict:
    response = await client.post(
        f"{get_settings().api_prefix}/auth/register",
        json={"full_name": "Ali <Vali>", "email": "ali@example.com", "password": "secret-pass"},
    )
    return response.json()


@pytest.fixture
async def menu(client, admin) -> dict:
    osh = await make_category(client, admin, "Osh")
    return {
        "palov": await make_item(client, admin, osh, "Palov & salat", price="45000"),
        "choy": await make_item(client, admin, osh, "Choy", price="5000"),
    }


async def place_order(client, user, menu, payment_method="card") -> dict:
    items = [
        {"menu_item_id": menu["palov"]["id"], "quantity": 2},
        {"menu_item_id": menu["choy"]["id"], "quantity": 1},
    ]
    response = await signed_request(
        client, user, "POST", "/orders", {"items": items, "payment_method": payment_method}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def notify_status(client, admin, order_id: int) -> str:
    detail = await signed_request(client, admin, "GET", f"/admin/orders/{order_id}")
    return detail.json()["notify_status"]


async def test_new_order_message_sent(client, admin, user, menu, configure):
    fake = configure(FakeTelegram())
    order = await place_order(client, user, menu)

    assert len(fake.sent) == 1
    message = fake.sent[0]
    assert message["chat_id"] == CHAT_ID
    assert message["parse_mode"] == "HTML"
    text = message["text"]
    assert f"#{order['id']}" in text
    assert "Ali &lt;Vali&gt; (ali@example.com)" in text  # user matni HTML-escape qilinadi
    assert "Palov &amp; salat × 2 — 90 000 so'm" in text
    assert "Choy × 1 — 5 000 so'm" in text
    assert "Jami: <b>95 000 so'm</b>" in text
    assert "KARTA" in text
    assert await notify_status(client, admin, order["id"]) == "sent"


async def test_cash_order_says_naqd(client, user, menu, configure):
    fake = configure(FakeTelegram())
    await place_order(client, user, menu, payment_method="cash")
    assert "NAQD" in fake.sent[0]["text"]


async def test_retries_then_sent(client, admin, user, menu, configure):
    fake = configure(FakeTelegram(fail_times=2))
    order = await place_order(client, user, menu)
    assert fake.calls == 3
    assert await notify_status(client, admin, order["id"]) == "sent"


async def test_all_attempts_fail_marks_failed(client, admin, user, menu, configure):
    fake = configure(FakeTelegram(fail_times=100))
    order = await place_order(client, user, menu)
    assert fake.calls == 1 + len(get_settings().notify_retry_delays)
    assert await notify_status(client, admin, order["id"]) == "failed"


async def test_network_error_does_not_leak_token(client, admin, user, menu, configure, caplog):
    error = httpx.ConnectError(f"cannot connect to https://api.telegram.org/bot{TOKEN}/x")
    configure(FakeTelegram(error=error))
    with caplog.at_level(logging.DEBUG):
        order = await place_order(client, user, menu)
    assert await notify_status(client, admin, order["id"]) == "failed"
    assert TOKEN not in caplog.text


async def test_not_configured_sends_nothing(client, admin, user, menu, monkeypatch):
    monkeypatch.setattr(get_settings(), "bot_token", None)
    fake = FakeTelegram()
    monkeypatch.setattr(telegram, "transport", httpx.MockTransport(fake.handler))
    order = await place_order(client, user, menu)
    assert fake.calls == 0
    assert await notify_status(client, admin, order["id"]) == "pending"


async def test_user_cancel_message_sent(client, user, menu, configure):
    fake = configure(FakeTelegram())
    order = await place_order(client, user, menu)
    await signed_request(client, user, "POST", f"/orders/me/{order['id']}/cancel")
    assert len(fake.sent) == 2
    assert f"Buyurtma #{order['id']} bekor qilindi" in fake.sent[1]["text"]


async def test_admin_filters_failed_and_resends(client, admin, user, menu, configure):
    fake = configure(FakeTelegram(fail_times=100))
    failed = await place_order(client, user, menu)
    fake.fail_times = 0  # Telegram yana ishlay boshladi
    await place_order(client, user, menu)

    listed = await signed_request(client, admin, "GET", "/admin/orders?notify_status=failed")
    assert [o["id"] for o in listed.json()["items"]] == [failed["id"]]

    response = await signed_request(client, admin, "POST", f"/admin/orders/{failed['id']}/notify")
    assert response.status_code == 202
    assert await notify_status(client, admin, failed["id"]) == "sent"
    assert f"#{failed['id']}" in fake.sent[-1]["text"]


async def test_resend_already_sent_is_409(client, admin, user, menu, configure):
    configure(FakeTelegram())
    order = await place_order(client, user, menu)
    response = await signed_request(client, admin, "POST", f"/admin/orders/{order['id']}/notify")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ORDER_ALREADY_NOTIFIED"


async def test_resend_without_telegram_config_is_503(client, admin, user, menu, monkeypatch):
    monkeypatch.setattr(get_settings(), "bot_token", None)
    order = await place_order(client, user, menu)
    response = await signed_request(client, admin, "POST", f"/admin/orders/{order['id']}/notify")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "TELEGRAM_NOT_CONFIGURED"


def test_long_order_fits_telegram_limit():
    from datetime import UTC, datetime
    from decimal import Decimal
    from types import SimpleNamespace

    from app.models.enums import PaymentMethod
    from app.services.order_notify import new_order_text

    item = SimpleNamespace(name_snapshot="X" * 150, quantity=999, subtotal=Decimal("123456789.99"))
    order = SimpleNamespace(
        id=7,
        user=SimpleNamespace(full_name="Ali", email="ali@example.com"),
        items=[item] * 50,
        total_price=Decimal("9999999999"),
        payment_method=PaymentMethod.CASH,
        created_at=datetime.now(UTC),
    )
    text = new_order_text(order)
    assert len(text) <= telegram.MAX_MESSAGE_LENGTH
    assert "va yana" in text
    assert "Jami:" in text


async def set_order(db, order_id: int, **values) -> None:
    from sqlalchemy import update

    from app.models import Order

    await db.execute(update(Order).where(Order.id == order_id).values(**values))
    await db.commit()


async def test_resend_while_sending_is_409(client, admin, user, menu, configure, db):
    configure(FakeTelegram())
    order = await place_order(client, user, menu)
    await set_order(db, order["id"], notify_status="pending")  # hozir yuborilmoqda

    response = await signed_request(client, admin, "POST", f"/admin/orders/{order['id']}/notify")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ORDER_NOTIFY_IN_PROGRESS"


async def test_stale_pending_can_be_resent(client, admin, user, menu, configure, db):
    from datetime import UTC, datetime, timedelta

    fake = configure(FakeTelegram())
    order = await place_order(client, user, menu)
    long_ago = datetime.now(UTC) - timedelta(seconds=get_settings().notify_stale_seconds + 60)
    await set_order(db, order["id"], notify_status="pending", updated_at=long_ago)

    response = await signed_request(client, admin, "POST", f"/admin/orders/{order['id']}/notify")
    assert response.status_code == 202
    assert await notify_status(client, admin, order["id"]) == "sent"
    assert len(fake.sent) == 2  # yaratilganda + qayta yuborilganda


@pytest.mark.parametrize("status", ["cancelled", "delivered"])
async def test_closed_order_is_not_resent(client, admin, user, menu, configure, db, status):
    fake = configure(FakeTelegram(fail_times=100))
    order = await place_order(client, user, menu)
    await set_order(db, order["id"], status=status)
    fake.fail_times = 0

    response = await signed_request(client, admin, "POST", f"/admin/orders/{order['id']}/notify")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ORDER_CLOSED"
    assert fake.sent == []


async def test_no_cancel_message_if_group_never_saw_the_order(client, user, menu, configure):
    fake = configure(FakeTelegram(fail_times=100))  # yangi buyurtma xabari yetib bormaydi
    order = await place_order(client, user, menu)
    calls_before = fake.calls

    await signed_request(client, user, "POST", f"/orders/me/{order['id']}/cancel")
    assert fake.calls == calls_before  # bekor xabari yuborishga ham urinilmadi


class StatusTelegram(FakeTelegram):
    """Belgilangan HTTP status bilan javob beradi."""

    def __init__(self, status: int, body: dict) -> None:
        super().__init__()
        self.status, self.body = status, body

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        return httpx.Response(self.status, json=self.body)


async def test_permanent_error_is_not_retried(client, admin, user, menu, configure):
    fake = configure(StatusTelegram(403, {"ok": False, "description": "bot was kicked"}))
    order = await place_order(client, user, menu)
    assert fake.calls == 1
    assert await notify_status(client, admin, order["id"]) == "failed"


async def test_rate_limit_waits_as_telegram_asks(client, admin, user, menu, configure, monkeypatch):
    from app.services import order_notify

    waits: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(order_notify, "_wait", fake_sleep)
    fake = configure(StatusTelegram(429, {"ok": False, "parameters": {"retry_after": 7}}))
    await place_order(client, user, menu)
    assert fake.calls == 1 + len(get_settings().notify_retry_delays)
    assert waits == [7, 7, 7]  # sozlamadagi 0 o'rniga Telegram aytgan 7 soniya
