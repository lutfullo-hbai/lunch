"""Telegram Bot API: guruhga xabar yuborish."""

import httpx

from app.core.config import get_settings

# Bot API cheklovi: bitta xabar matni shuncha belgidan oshmaydi.
MAX_MESSAGE_LENGTH = 4096

# Testlarda soxta transport qo'yiladi (haqiqiy Telegram'ga so'rov ketmasin).
transport: httpx.AsyncBaseTransport | None = None


class TelegramError(Exception):
    """Xabar yuborilmadi. Matnda bot tokeni bo'lmaydi."""


def is_configured() -> bool:
    settings = get_settings()
    return settings.bot_token is not None and settings.orders_group_chat_id is not None


async def send_to_orders_group(html: str) -> None:
    settings = get_settings()
    if settings.bot_token is None or settings.orders_group_chat_id is None:
        raise TelegramError("BOT_TOKEN yoki ORDERS_GROUP_CHAT_ID berilmagan")
    url = f"{settings.telegram_api_url}/bot{settings.bot_token.get_secret_value()}/sendMessage"
    payload = {
        "chat_id": settings.orders_group_chat_id,
        "text": html,
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True},
    }
    try:
        async with httpx.AsyncClient(
            timeout=settings.telegram_timeout_seconds, transport=transport
        ) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        # str(exc) da URL (ya'ni token) bo'lishi mumkin, shuning uchun faqat turi.
        raise TelegramError(type(exc).__name__) from None
    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code != httpx.codes.OK or not body.get("ok"):
        raise TelegramError(f"{response.status_code}: {body.get('description', '')}")
