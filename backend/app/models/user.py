from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, func, text, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.db.types import pg_enum
from app.models.enums import UserRole


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        # Email katta-kichik harfdan qat'i nazar unique: Ali@x.uz va ali@x.uz bir xil.
        Index("uq_users_email_lower", func.lower(text("email")), unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(32))
    role: Mapped[UserRole] = mapped_column(
        pg_enum(UserRole, "user_role"), default=UserRole.USER, server_default=UserRole.USER.value
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
