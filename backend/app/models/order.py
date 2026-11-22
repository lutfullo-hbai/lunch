from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.db.types import pg_enum
from app.models.enums import NotifyStatus, OrderStatus, PaymentMethod

# Holatlar faqat oldinga yuradi. Yetkazilgan yoki bekor qilingan buyurtma yopiq.
STATUS_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.NEW: frozenset({OrderStatus.ACCEPTED, OrderStatus.CANCELLED}),
    OrderStatus.ACCEPTED: frozenset({OrderStatus.READY, OrderStatus.CANCELLED}),
    OrderStatus.READY: frozenset({OrderStatus.DELIVERED, OrderStatus.CANCELLED}),
    OrderStatus.DELIVERED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}

if TYPE_CHECKING:
    from app.models.menu import MenuItem
    from app.models.user import User


class Order(TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("total_price > 0", name="total_price_positive"),
        Index("ix_orders_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    payment_method: Mapped[PaymentMethod] = mapped_column(pg_enum(PaymentMethod, "payment_method"))
    status: Mapped[OrderStatus] = mapped_column(
        pg_enum(OrderStatus, "order_status"),
        default=OrderStatus.NEW,
        server_default=OrderStatus.NEW.value,
        index=True,
    )
    notify_status: Mapped[NotifyStatus] = mapped_column(
        pg_enum(NotifyStatus, "notify_status"),
        default=NotifyStatus.PENDING,
        server_default=NotifyStatus.PENDING.value,
    )

    user: Mapped["User"] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )

    @property
    def user_can_cancel(self) -> bool:
        """User o'z buyurtmasini faqat admin qabul qilmasidan oldin bekor qila oladi."""
        return self.status is OrderStatus.NEW

    @property
    def allowed_statuses(self) -> list[OrderStatus]:
        """Keyingi mumkin bo'lgan holatlar, enum tartibida (javob har doim bir xil bo'lsin)."""
        return [s for s in OrderStatus if s in STATUS_TRANSITIONS[self.status]]


class OrderItem(Base):
    """Buyurtma qatori. Nom va narx buyurtma paytidagi holatda saqlanadi (snapshot)."""

    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("price_snapshot > 0", name="price_snapshot_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id", ondelete="RESTRICT"))
    name_snapshot: Mapped[str] = mapped_column(String(150))
    price_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    quantity: Mapped[int] = mapped_column(Integer)

    order: Mapped[Order] = relationship(back_populates="items")
    menu_item: Mapped["MenuItem"] = relationship()

    @property
    def subtotal(self) -> Decimal:
        return self.price_snapshot * self.quantity
