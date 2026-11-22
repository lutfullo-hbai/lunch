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
