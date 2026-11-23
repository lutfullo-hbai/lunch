"""Parolni almashtirish: yangi parol ishlaydi, boshqa sessiyalar yopiladi, xatolar 422."""

import pytest

from app.core.config import get_settings
from app.core.rate_limit import RateLimiter
from tests.helpers import register, signed_request

API = get_settings().api_prefix
OLD = "secret-pass"
NEW = "yangi-parol-2026"


async def login(client, password: str):
    return await client.post(
        f"{API}/auth/login", json={"email": "ali@example.com", "password": password}
    )


async def change(client, tokens, current: str, new: str):
    return await signed_request(
        client,
        tokens,
        "POST",
        "/auth/change-password",
        {"current_password": current, "new_password": new},
    )


def error_field(response) -> str:
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    return error["details"][0]["field"]


async def test_new_password_works_and_old_does_not(client):
    tokens = await register(client, password=OLD)
    response = await change(client, tokens, OLD, NEW)
    assert response.status_code == 204

    assert (await login(client, NEW)).status_code == 200
    old = await login(client, OLD)
    assert old.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_other_sessions_closed_current_kept(client):
    this_device = await register(client, password=OLD)
    other_device = (await login(client, OLD)).json()

    await change(client, this_device, OLD, NEW)

    assert (await signed_request(client, this_device, "GET", "/me")).status_code == 200
    other_me = await signed_request(client, other_device, "GET", "/me")
    assert other_me.json()["error"]["code"] == "SESSION_REVOKED"
    other_refresh = await client.post(
        f"{API}/auth/refresh", json={"refresh_token": other_device["refresh_token"]}
    )
    assert other_refresh.status_code == 401


async def test_wrong_current_password_is_422_and_nothing_changes(client):
    tokens = await register(client, password=OLD)
    response = await change(client, tokens, "notogri-parol", NEW)
    assert error_field(response) == "current_password"
    assert (await login(client, OLD)).status_code == 200


@pytest.mark.parametrize(
    "new_password",
    ["qisqa", "ж" * 40],  # 8 belgidan kam; 72 baytdan uzun (kirill harfi 2 bayt)
)
async def test_new_password_rules(client, new_password):
    tokens = await register(client, password=OLD)
    assert error_field(await change(client, tokens, OLD, new_password)) == "new_password"


async def test_same_password_is_rejected(client):
    tokens = await register(client, password=OLD)
    assert error_field(await change(client, tokens, OLD, OLD)) == "new_password"


async def test_requires_login_and_signature(client):
    anonymous = await client.post(
        f"{API}/auth/change-password", json={"current_password": OLD, "new_password": NEW}
    )
    assert anonymous.status_code == 401

    tokens = await register(client, password=OLD)
    unsigned = await client.post(
        f"{API}/auth/change-password",
        json={"current_password": OLD, "new_password": NEW},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert unsigned.json()["error"]["code"] == "SIGNATURE_MISSING"


async def test_guessing_is_rate_limited_per_user(client, app, monkeypatch):
    app.state.rate_limiter = RateLimiter()
    monkeypatch.setattr(get_settings(), "password_change_rate_limit", 2)
    tokens = await register(client, password=OLD)

    codes = [(await change(client, tokens, f"taxmin-{i}-parol", NEW)).status_code for i in range(3)]
    assert codes == [422, 422, 429]
