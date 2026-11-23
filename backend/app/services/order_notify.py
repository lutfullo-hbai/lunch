"""Buyurtmalar guruhiga xabarlar: yangi buyurtma va user bekor qilgan buyurtma.

So'rov tugagach fonda ishlaydi: Telegram sekin yoki ishlamay qolsa ham user
javobni darhol oladi, buyurtma esa bazada saqlanib qoladi.
"""

import asyncio
import logging
from decimal import Decimal
from html import escape as _html_escape

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.session import SessionMaker
from app.models import Order
from app.models.enums import NotifyStatus, PaymentMethod
from app.services import telegram

logger = logging.getLogger(__name__)


def escape(text: str) -> str:
    """Telegram HTML uchun: faqat <, > va & (apostrof o'zgarmasin)."""
    return _html_escape(text, quote=False)


_PAYMENT_LINES = {
    PaymentMethod.CASH: "💵 To'lov turi: NAQD",
    PaymentMethod.CARD: "💳 To'lov turi: KARTA",
}


def _money(amount: Decimal) -> str:
    text = f"{amount:,.0f}" if amount == amount.to_integral_value() else f"{amount:,.2f}"
    return f"{text.replace(',', ' ')} {escape(get_settings().currency)}"


def _customer(order: Order) -> str:
    return f"👤 {escape(order.user.full_name)} ({escape(order.user.email)})"


def new_order_text(order: Order) -> str:
    created = order.created_at.astimezone(get_settings().tz)
    head = [f"🆕 <b>Yangi buyurtma #{order.id}</b>", "", _customer(order), ""]
    tail = [
        "",
        f"💰 Jami: <b>{_money(order.total_price)}</b>",
        _PAYMENT_LINES[order.payment_method],
        f"🕒 {created:%d.%m.%Y %H:%M}",
    ]
    lines = [
        f"🍽 {escape(item.name_snapshot)} × {item.quantity} — {_money(item.subtotal)}"
        for item in order.items
    ]
    # Telegram uzun xabarni qabul qilmaydi: sig'magan qatorlar o'rniga ularning soni yoziladi.
    hidden = 0
    while True:
        shown = lines[: len(lines) - hidden]
        more = [f"… va yana {hidden} ta ovqat (to'liq ro'yxat admin panelda)"] if hidden else []
        text = "\n".join([*head, *shown, *more, *tail])
        if len(text) <= telegram.MAX_MESSAGE_LENGTH or not shown:
            return text
        hidden += 1


def cancelled_order_text(order: Order) -> str | None:
    """Guruh bu buyurtmani ko'rmagan bo'lsa (xabar yetib bormagan), bekor xabari ham kerak emas."""
    if order.notify_status is not NotifyStatus.SENT:
        return None
    return "\n".join(
        [
            f"❌ <b>Buyurtma #{order.id} bekor qilindi</b> (user tomonidan)",
            "",
            _customer(order),
            f"💰 Jami: {_money(order.total_price)}",
        ]
    )


async def _load(db: AsyncSession, order_id: int) -> Order | None:
    return await db.scalar(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items), selectinload(Order.user))
        .execution_options(populate_existing=True)
    )


# 429 da Telegram so'ragan kutish shundan oshsa ham, shuncha kutamiz: fon vazifasi
# cheksiz osilib qolmasin (keyingi urinish yoki admin qayta yuborishi bor).
MAX_RETRY_AFTER_SECONDS = 30


async def _wait(seconds: float) -> None:
    """Qayta urinishdan oldin kutish (testlarda almashtiriladi)."""
    await asyncio.sleep(seconds)


async def _send_with_retry(text: str, order_id: int) -> bool:
    """Yuborildi: True. Urinishlar tugadi yoki xato doimiy: False."""
    delays = get_settings().notify_retry_delays
    for attempt in range(len(delays) + 1):
        try:
            await telegram.send_to_orders_group(text)
            return True
        except telegram.TelegramError as exc:
            logger.warning("Buyurtma #%s xabari yuborilmadi (%s): %s", order_id, attempt + 1, exc)
            if not exc.retryable or attempt == len(delays):
                return False
            wait = delays[attempt]
            if exc.retry_after is not None:
                wait = min(max(exc.retry_after, wait), MAX_RETRY_AFTER_SECONDS)
            await _wait(wait)
    return False


async def _build_text(sessions: SessionMaker, order_id: int, render) -> str | None:
    # Sessiya faqat o'qish uchun ochiladi: qayta urinishlar paytida ulanish band turmasin.
    async with sessions() as db:
        order = await _load(db, order_id)
        return None if order is None else render(order)


async def notify_new_order(sessions: SessionMaker, order_id: int) -> None:
    if not telegram.is_configured():
        logger.warning("BOT_TOKEN yoki ORDERS_GROUP_CHAT_ID yo'q: #%s xabari yuborilmadi", order_id)
        return
    try:
        text = await _build_text(sessions, order_id, new_order_text)
        if text is None:
            return
        sent = await _send_with_retry(text, order_id)
        async with sessions() as db:
            await db.execute(
                update(Order)
                .where(Order.id == order_id)
                .values(notify_status=NotifyStatus.SENT if sent else NotifyStatus.FAILED)
            )
            await db.commit()
    except Exception:  # fon vazifasi: xato hech kimga ko'rinmaydi, faqat logga
        logger.exception("Buyurtma #%s xabarini yuborishda kutilmagan xato", order_id)


async def notify_cancelled(sessions: SessionMaker, order_id: int) -> None:
    if not telegram.is_configured():
        return
    try:
        text = await _build_text(sessions, order_id, cancelled_order_text)
        if text is not None:
            await _send_with_retry(text, order_id)
    except Exception:
        logger.exception("Buyurtma #%s bekor xabarini yuborishda kutilmagan xato", order_id)
