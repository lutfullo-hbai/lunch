from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Category, MenuItem, Order, OrderItem, User
from app.models.enums import NotifyStatus, OrderStatus, PaymentMethod, UserRole


def make_user(email: str = "ali@example.com") -> User:
    return User(email=email, password_hash="hash", full_name="Ali")


async def test_user_defaults(db):
    user = make_user()
    db.add(user)
    await db.flush()
    await db.refresh(user)

    assert user.role is UserRole.USER
    assert user.is_active is True
    assert user.created_at is not None


async def test_email_is_unique(db):
    db.add_all([make_user(), make_user()])
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_menu_item_price_must_be_positive(db):
    category = Category(name="Sho'rvalar")
    db.add(MenuItem(category=category, name="Mastava", price=Decimal("0")))
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_order_with_items(db):
    user = make_user()
    item = MenuItem(category=Category(name="Osh"), name="Palov", price=Decimal("45000"))
    order = Order(
        user=user,
        total_price=Decimal("90000"),
        payment_method=PaymentMethod.CARD,
        phone="+998901234567",
        address="Toshkent",
        items=[
            OrderItem(menu_item=item, name_snapshot="Palov", price_snapshot=item.price, quantity=2)
        ],
    )
    db.add(order)
    await db.flush()
    await db.refresh(order)

    assert order.status is OrderStatus.NEW
    assert order.notify_status is NotifyStatus.PENDING
