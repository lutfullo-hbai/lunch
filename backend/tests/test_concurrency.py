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


async def test_parallel_image_uploads_leave_no_orphans(live_client, tmp_path, monkeypatch):
    from decimal import Decimal

    from sqlalchemy import delete

    from app.db.session import SessionFactory
    from app.models import Category, MenuItem, User
    from app.models.enums import UserRole
    from tests.test_admin_menu import png_bytes, upload

    monkeypatch.setattr(get_settings(), "media_dir", tmp_path)
    admin = await register(live_client, email=f"admin@{LIVE_EMAIL_DOMAIN}")
    async with SessionFactory() as session:
        user = await session.get(User, admin["user"]["id"])
        user.role = UserRole.ADMIN
        category = Category(name=f"Parallel {admin['user']['id']}")
        item = MenuItem(category=category, name="Palov", price=Decimal("45000"))
        session.add(item)
        await session.commit()
        item_id, category_id = item.id, category.id

    try:
        responses = await asyncio.gather(
            upload(live_client, admin, item_id, png_bytes()),
            upload(live_client, admin, item_id, png_bytes()),
        )
        assert [r.status_code for r in responses] == [200, 200]
        # Faqat oxirgi rasm va uning thumb'i qoladi.
        assert len(list(tmp_path.rglob("*.webp"))) == 2
    finally:
        async with SessionFactory() as session:
            await session.execute(delete(MenuItem).where(MenuItem.id == item_id))
            await session.execute(delete(Category).where(Category.id == category_id))
            await session.commit()
