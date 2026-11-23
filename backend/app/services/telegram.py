"""Telegram Bot API: guruhga xabar yuborish."""

import httpx

from app.core.config import get_settings

# Bot API cheklovi: bitta xabar matni shuncha belgidan oshmaydi.
MAX_MESSAGE_LENGTH = 4096

# Testlarda soxta transport qo'yiladi (haqiqiy Telegram'ga so'rov ketmasin).
transport: httpx.AsyncBaseTransport | None = None


class TelegramError(Exception):
    """Xabar yuborilmadi. Matnda bot tokeni bo'lmaydi.

    `retryable`: qayta urinish ma'noli (tarmoq, 5xx, 429). 400/403 kabi doimiy xatoda
    (chat topilmadi, bot guruhdan chiqarilgan) qayta urinish foydasiz.
    `retry_after`: 429 da Telegram aytgan kutish vaqti (soniya).
    """

    def __init__(self, message: str, *, retryable: bool = True, retry_after: float | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after


def is_configured() -> bool:
    settings = get_settings()
    return settings.bot_token is not None and settings.orders_group_chat_id is not None


async def send_to_orders_group(html: str) -> None:
    settings = get_settings()
    if settings.bot_token is None or settings.orders_group_chat_id is None:
        raise TelegramError("BOT_TOKEN yoki ORDERS_GROUP_CHAT_ID berilmagan", retryable=False)
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
    if response.status_code == httpx.codes.OK and body.get("ok"):
        return
    message = f"{response.status_code}: {body.get('description', '')}"
    if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
        retry_after = (body.get("parameters") or {}).get("retry_after")
        raise TelegramError(message, retry_after=float(retry_after) if retry_after else None)
    raise TelegramError(message, retryable=response.status_code >= 500)
