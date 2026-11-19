from decimal import Decimal

import pytest

from app.models import MenuItem
from tests.helpers import admin_tokens, register, signed_request


@pytest.fixture
async def admin(client, db) -> dict:
    return await admin_tokens(client, db)


async def create(client, admin, **payload):
    return await signed_request(client, admin, "POST", "/admin/categories", payload)


async def test_regular_user_gets_403(client):
    user = await register(client)
    response = await signed_request(client, user, "GET", "/admin/categories")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_create_and_list_sorted(client, admin):
    await create(client, admin, name="Ichimliklar", sort_order=2)
    created = await create(client, admin, name="  Osh  ", sort_order=1)
    assert created.status_code == 201
    assert created.json()["name"] == "Osh"

    listed = await signed_request(client, admin, "GET", "/admin/categories")
    assert [c["name"] for c in listed.json()] == ["Osh", "Ichimliklar"]


async def test_duplicate_name_case_insensitive(client, admin):
    await create(client, admin, name="Osh")
    response = await create(client, admin, name="OSH")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CATEGORY_EXISTS"


async def test_update(client, admin):
    category = (await create(client, admin, name="Osh")).json()
    response = await signed_request(
        client, admin, "PATCH", f"/admin/categories/{category['id']}", {"is_active": False}
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert response.json()["name"] == "Osh"


async def test_update_missing_returns_404(client, admin):
    response = await signed_request(client, admin, "PATCH", "/admin/categories/999999", {})
    assert response.status_code == 404


async def test_delete_blocked_when_has_items(client, admin, db):
    category = (await create(client, admin, name="Osh")).json()
    db.add(MenuItem(category_id=category["id"], name="Palov", price=Decimal("45000")))
    await db.commit()

    response = await signed_request(client, admin, "DELETE", f"/admin/categories/{category['id']}")
    assert response.status_code == 409
    assert response.json()["error"]["details"] == {"items_count": 1}


async def test_delete_empty_category(client, admin):
    category = (await create(client, admin, name="Osh")).json()
    response = await signed_request(client, admin, "DELETE", f"/admin/categories/{category['id']}")
    assert response.status_code == 204

    listed = await signed_request(client, admin, "GET", "/admin/categories")
    assert listed.json() == []
