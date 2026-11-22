import pytest

from app.core.config import get_settings
from app.core.rate_limit import RateLimiter

API = get_settings().api_prefix


@pytest.fixture(autouse=True)
def fresh_limiter(app):
    app.state.rate_limiter = RateLimiter()


async def test_login_is_limited_per_ip(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "login_rate_limit", 2)
    payload = {"email": "yoq@example.com", "password": "secret-pass"}

    codes = [(await client.post(f"{API}/auth/login", json=payload)).status_code for _ in range(3)]

    assert codes == [401, 401, 429]
    blocked = await client.post(f"{API}/auth/login", json=payload)
    assert blocked.json()["error"]["code"] == "TOO_MANY_REQUESTS"
    assert int(blocked.headers["Retry-After"]) >= 1


async def test_register_is_limited_per_ip(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "register_rate_limit", 1)

    async def register(email: str):
        return await client.post(
            f"{API}/auth/register",
            json={"full_name": "Ali Valiyev", "email": email, "password": "secret-pass"},
        )

    assert (await register("a@example.com")).status_code == 201
    assert (await register("b@example.com")).status_code == 429


def test_window_resets(monkeypatch):
    import app.core.rate_limit as module

    now = [1000.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    limiter = RateLimiter()

    assert limiter.hit("k", limit=1, window_seconds=60) is None
    assert limiter.hit("k", limit=1, window_seconds=60) == 60
    now[0] += 60
    assert limiter.hit("k", limit=1, window_seconds=60) is None


def test_short_window_sweep_keeps_long_windows(monkeypatch):
    """Login (60 s) sweep'i register (1 soat) hisobini o'chirmasligi kerak."""
    import app.core.rate_limit as module

    now = [1000.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    limiter = RateLimiter()

    assert limiter.hit("register:ip", limit=1, window_seconds=3600) is None
    assert limiter.hit("register:ip", limit=1, window_seconds=3600) is not None
    now[0] += 61
    limiter.hit("login:ip", limit=10, window_seconds=60)  # sweep'ni ishga tushiradi
    assert limiter.hit("register:ip", limit=1, window_seconds=3600) is not None


async def test_orders_are_limited_per_user(client, db, monkeypatch):
    from tests.helpers import admin_tokens, register, signed_request
    from tests.test_menu import make_category, make_item

    monkeypatch.setattr(get_settings(), "order_rate_limit", 2)
    admin = await admin_tokens(client, db)
    item = await make_item(client, admin, await make_category(client, admin, "Osh"), "Choy")
    payload = {"items": [{"menu_item_id": item["id"], "quantity": 1}], "payment_method": "cash"}

    ali = await register(client, email="ali@example.com")
    codes = [
        (await signed_request(client, ali, "POST", "/orders", payload)).status_code
        for _ in range(3)
    ]
    assert codes == [201, 201, 429]

    # Boshqa user (o'sha IP'dan bo'lsa ham) cheklanmaydi.
    vali = await register(client, email="vali@example.com")
    assert (await signed_request(client, vali, "POST", "/orders", payload)).status_code == 201
