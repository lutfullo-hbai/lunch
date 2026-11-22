from enum import StrEnum


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"


class PaymentMethod(StrEnum):
    CASH = "cash"
    CARD = "card"


class OrderStatus(StrEnum):
    NEW = "new"
    ACCEPTED = "accepted"
    READY = "ready"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class NotifyStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
