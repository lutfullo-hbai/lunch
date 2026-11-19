import pytest

from app.core.config import get_settings
from tests.helpers import admin_tokens, register, signed_request


@pytest.fixture
async def admin(client, db) -> dict:
    return await admin_tokens(client, db)


async def test_regular_user_forbidden(client):
    user = await register(client)
    response = await signed_request(client, user, "GET", "/admin/users")
    assert response.status_code == 403


async def test_list_and_search(client, admin):
    await register(client, email="vali@example.com")
    await register(client, email="sardor@example.com")

    everyone = (await signed_request(client, admin, "GET", "/admin/users")).json()
    assert everyone["total"] == 3

    found = (await signed_request(client, admin, "GET", "/admin/users?search=SARDOR")).json()
    assert [u["email"] for u in found["items"]] == ["sardor@example.com"]

    admins = (await signed_request(client, admin, "GET", "/admin/users?role=admin")).json()
    assert [u["email"] for u in admins["items"]] == ["admin@example.com"]


async def test_get_user(client, admin):
    user = await register(client, email="vali@example.com")
    response = await signed_request(client, admin, "GET", f"/admin/users/{user['user']['id']}")
    assert response.status_code == 200
    assert response.json()["orders_count"] == 0


async def test_get_missing_user(client, admin):
    response = await signed_request(client, admin, "GET", "/admin/users/999999")
    assert response.status_code == 404


async def test_block_user_closes_sessions_and_login(client, admin):
    user = await register(client, email="vali@example.com")
    path = f"/admin/users/{user['user']['id']}/status"

    blocked = await signed_request(client, admin, "PATCH", path, {"is_active": False})
    assert blocked.json()["is_active"] is False

    # Ochiq sessiyasi yopildi va qayta kira olmaydi.
    me = await signed_request(client, user, "GET", "/me")
    assert me.json()["error"]["code"] == "SESSION_REVOKED"
    login = await client.post(
        f"{get_settings().api_prefix}/auth/login",
        json={"email": "vali@example.com", "password": "secret-pass"},
    )
    assert login.json()["error"]["code"] == "USER_INACTIVE"

    unblocked = await signed_request(client, admin, "PATCH", path, {"is_active": True})
    assert unblocked.json()["is_active"] is True


async def test_cannot_block_admin(client, admin):
    response = await signed_request(
        client, admin, "PATCH", f"/admin/users/{admin['user']['id']}/status", {"is_active": False}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CANNOT_BLOCK_ADMIN"
