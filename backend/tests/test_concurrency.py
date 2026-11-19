"""Haqiqiy commit va `FOR UPDATE` lock'lari bilan ishlaydigan testlar."""

import asyncio

from app.core.config import get_settings
from tests.conftest import LIVE_EMAIL_DOMAIN
from tests.helpers import register, signed_request

API = get_settings().api_prefix


async def test_parallel_refresh_does_not_log_out_everywhere(live_client):
    first_device = await register(live_client, email=f"ali@{LIVE_EMAIL_DOMAIN}")
    login = await live_client.post(
        f"{API}/auth/login", json={"email": f"ali@{LIVE_EMAIL_DOMAIN}", "password": "secret-pass"}
    )
    second_device = login.json()

    payload = {"refresh_token": first_device["refresh_token"]}
    responses = await asyncio.gather(
        live_client.post(f"{API}/auth/refresh", json=payload),
        live_client.post(f"{API}/auth/refresh", json=payload),
    )
    codes = sorted(r.status_code for r in responses)
    assert codes == [200, 401]
    loser = next(r for r in responses if r.status_code == 401)
    assert loser.json()["error"]["code"] == "REFRESH_TOKEN_ROTATED"

    # Yutgan so'rovning yangi tokeni va boshqa qurilma ishlashda davom etadi.
    winner = next(r for r in responses if r.status_code == 200).json()
    assert (await signed_request(live_client, winner, "GET", "/me")).status_code == 200
    assert (await signed_request(live_client, second_device, "GET", "/me")).status_code == 200


async def test_parallel_register_same_email_returns_409(live_client):
    payload = {"full_name": "Ali", "email": f"race@{LIVE_EMAIL_DOMAIN}", "password": "secret-pass"}
    responses = await asyncio.gather(
        live_client.post(f"{API}/auth/register", json=payload),
        live_client.post(
            f"{API}/auth/register", json={**payload, "email": payload["email"].upper()}
        ),
    )
    assert sorted(r.status_code for r in responses) == [201, 409]
