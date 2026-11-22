"""User buyurtmasi: narx serverda, miqdor tekshiruvi, sotuvda yo'q ovqat."""

from decimal import Decimal

import pytest

from app.core.config import get_settings
from tests.helpers import admin_tokens, register, signed_request
from tests.test_menu import make_category, make_item

API = get_settings().api_prefix


@pytest.fixture
async def admin(client, db) -> dict:
    return await admin_tokens(client, db)


@pytest.fixture
async def user(client) -> dict:
    return await register(client, email="user@example.com")


@pytest.fixture
async def menu(client, admin) -> dict:
    osh = await make_category(client, admin, "Osh")
    return {
        "palov": await make_item(client, admin, osh, "Palov", price="45000"),
        "choy": await make_item(client, admin, osh, "Choy", price="5000"),
        "tugagan": await make_item(client, admin, osh, "Tugagan", is_available=False),
    }


async def order(client, user, items, payment_method="cash"):
    return await signed_request(
        client, user, "POST", "/orders", {"items": items, "payment_method": payment_method}
    )


def line(item: dict, quantity: int = 1) -> dict:
    return {"menu_item_id": item["id"], "quantity": quantity}


async def test_create_order(client, user, menu):
    response = await order(client, user, [line(menu["palov"], 2), line(menu["choy"])], "card")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "new"
    assert body["payment_method"] == "card"
    assert Decimal(body["total_price"]) == Decimal("95000")
    assert {(i["name"], i["quantity"]) for i in body["items"]} == {("Palov", 2), ("Choy", 1)}


async def test_client_price_is_ignored(client, user, menu):
    items = [{**line(menu["choy"]), "price": "1"}]
    body = (await order(client, user, items)).json()
    assert Decimal(body["total_price"]) == Decimal("5000")


async def test_same_item_lines_are_merged(client, user, menu):
    body = (await order(client, user, [line(menu["choy"], 1), line(menu["choy"], 2)])).json()
    assert [(i["name"], i["quantity"]) for i in body["items"]] == [("Choy", 3)]


async def test_order_requires_login(client, menu):
    response = await client.post(f"{API}/orders", json={"items": [], "payment_method": "cash"})
    assert response.status_code == 401


async def test_unavailable_item_rejected(client, admin, user, menu):
    await signed_request(client, admin, "DELETE", f"/admin/menu/{menu['choy']['id']}")
    response = await order(
        client, user, [line(menu["palov"]), line(menu["tugagan"]), line(menu["choy"])]
    )
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "ITEMS_UNAVAILABLE"
    assert error["details"]["menu_item_ids"] == sorted([menu["tugagan"]["id"], menu["choy"]["id"]])


@pytest.mark.parametrize("quantity", [0, -1])
async def test_quantity_below_one_rejected(client, user, menu, quantity):
    response = await order(client, user, [line(menu["palov"], quantity)])
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "items.0.quantity"


@pytest.mark.parametrize(
    "payload",
    [
        {"items": [], "payment_method": "cash"},
        {"items": [{"menu_item_id": 1, "quantity": 1}], "payment_method": "crypto"},
        {"items": [{"menu_item_id": 1, "quantity": 1}]},
    ],
)
async def test_invalid_payload_rejected(client, user, payload):
    response = await signed_request(client, user, "POST", "/orders", payload)
    assert response.status_code == 422


async def test_too_many_lines_rejected(client, user, menu, monkeypatch):
    monkeypatch.setattr(get_settings(), "order_max_lines", 1)
    response = await order(client, user, [line(menu["palov"]), line(menu["choy"])])
    assert response.status_code == 422


async def test_total_too_large_rejected(client, user, menu):
    response = await order(client, user, [line(menu["palov"], 2**31 - 1)])
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "items"


async def test_new_order_visible_to_admin_as_pending(client, admin, user, menu):
    created = (await order(client, user, [line(menu["palov"])])).json()
    detail = (await signed_request(client, admin, "GET", f"/admin/orders/{created['id']}")).json()
    assert detail["notify_status"] == "pending"
    assert detail["user"]["email"] == "user@example.com"


async def test_my_orders_newest_first_and_only_mine(client, user, menu):
    first = (await order(client, user, [line(menu["palov"])])).json()
    second = (await order(client, user, [line(menu["choy"])])).json()
    other = await register(client, email="other@example.com")
    await order(client, other, [line(menu["choy"])])

    body = (await signed_request(client, user, "GET", "/orders/me")).json()
    assert body["total"] == 2
    assert [o["id"] for o in body["items"]] == [second["id"], first["id"]]


async def test_my_order_detail(client, user, menu):
    created = (await order(client, user, [line(menu["palov"], 2)])).json()
    body = (await signed_request(client, user, "GET", f"/orders/me/{created['id']}")).json()
    assert body["items"][0]["subtotal"] == "90000.00"


async def test_someone_elses_order_is_404(client, user, menu):
    other = await register(client, email="other@example.com")
    created = (await order(client, other, [line(menu["choy"])])).json()
    response = await signed_request(client, user, "GET", f"/orders/me/{created['id']}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORDER_NOT_FOUND"
