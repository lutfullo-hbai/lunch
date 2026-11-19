from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Category(TimestampMixin, Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    items: Mapped[list["MenuItem"]] = relationship(back_populates="category")


class MenuItem(TimestampMixin, Base):
    """Menyudagi ovqat. O'chirilganda `deleted_at` to'ldiriladi (eski buyurtmalar buzilmasin)."""

    __tablename__ = "menu_items"
    __table_args__ = (CheckConstraint("price > 0", name="price_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    portion: Mapped[str | None] = mapped_column(String(50))
    image_path: Mapped[str | None] = mapped_column(String(255))
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    category: Mapped[Category] = relationship(back_populates="items")
