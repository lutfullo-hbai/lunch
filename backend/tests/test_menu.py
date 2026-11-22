"""User uchun menyu: faqat faol kategoriyalar va sotuvdagi ovqatlar ko'rinadi."""

import pytest

from app.core.config import get_settings
from tests.helpers import admin_tokens, register, signed_request

API = get_settings().api_prefix


@pytest.fixture
async def admin(client, db) -> dict:
    return await admin_tokens(client, db)


@pytest.fixture
async def user(client) -> dict:
    return await register(client, email="user@example.com")


async def make_category(client, admin, name: str, **extra) -> dict:
    response = await signed_request(
        client, admin, "POST", "/admin/categories", {"name": name, **extra}
    )
    return response.json()


async def make_item(client, admin, category: dict, name: str, **extra) -> dict:
    payload = {"category_id": category["id"], "name": name, "price": "10000", **extra}
    return (await signed_request(client, admin, "POST", "/admin/menu", payload)).json()


@pytest.fixture
async def menu(client, admin) -> dict:
    osh = await make_category(client, admin, "Osh", sort_order=1)
    ichimlik = await make_category(client, admin, "Ichimlik", sort_order=2)
    yopiq = await make_category(client, admin, "Yopiq", is_active=False)
    items = {
        "palov": await make_item(client, admin, osh, "Palov"),
        "lagmon": await make_item(client, admin, osh, "Lag'mon", is_available=False),
        "choy": await make_item(client, admin, ichimlik, "Choy"),
        "yashirin": await make_item(client, admin, yopiq, "Yashirin"),
        "ochirilgan": await make_item(client, admin, osh, "O'chirilgan"),
    }
    await signed_request(client, admin, "DELETE", f"/admin/menu/{items['ochirilgan']['id']}")
    return {"osh": osh, "ichimlik": ichimlik, "items": items}


async def test_menu_requires_login(client):
    for path in ("/categories", "/menu", "/menu/1"):
        response = await client.get(f"{API}{path}")
        assert response.status_code == 401


async def test_categories_only_active_sorted(client, user, menu):
    response = await signed_request(client, user, "GET", "/categories")
    assert [c["name"] for c in response.json()] == ["Osh", "Ichimlik"]
    assert set(response.json()[0]) == {"id", "name"}


async def test_menu_only_orderable_items(client, user, menu):
    response = await signed_request(client, user, "GET", "/menu")
    assert [i["name"] for i in response.json()] == ["Palov", "Choy"]


async def test_menu_filter_by_category(client, user, menu):
    response = await signed_request(
        client, user, "GET", f"/menu?category_id={menu['ichimlik']['id']}"
    )
    assert [i["name"] for i in response.json()] == ["Choy"]


@pytest.mark.parametrize("key", ["lagmon", "yashirin", "ochirilgan"])
async def test_hidden_item_detail_is_404(client, user, menu, key):
    item_id = menu["items"][key]["id"]
    response = await signed_request(client, user, "GET", f"/menu/{item_id}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "MENU_ITEM_NOT_FOUND"


async def test_item_detail(client, user, menu):
    item_id = menu["items"]["palov"]["id"]
    body = (await signed_request(client, user, "GET", f"/menu/{item_id}")).json()
    assert body["name"] == "Palov"
    assert body["category_name"] == "Osh"
