from datetime import datetime

from pydantic import BaseModel

from app.models.enums import UserRole


class AdminUserOut(BaseModel):
    id: int
    email: str
    full_name: str
    phone: str | None
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None
    orders_count: int


class UserStatusUpdate(BaseModel):
    is_active: bool
