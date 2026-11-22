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
