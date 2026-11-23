from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
)

from app.core.config import check_bcrypt_length, get_settings
from app.models.enums import UserRole
from app.schemas.types import NoNul

# Email har doim kichik harfda: Ali@x.uz va ali@x.uz bitta akkaunt.
Email = Annotated[EmailStr, AfterValidator(str.lower)]
Password = Annotated[str, AfterValidator(check_bcrypt_length)]


def _check_min_length(value: str) -> str:
    min_length = get_settings().password_min_length
    if len(value) < min_length:
        raise ValueError(f"Parol kamida {min_length} belgidan iborat bo'lishi kerak")
    return value


# Yangi o'rnatiladigan parol (register, parolni almashtirish): uzunlik qoidalari bilan.
NewPassword = Annotated[Password, AfterValidator(_check_min_length)]


class RegisterIn(BaseModel):
    # Probellar uzunlik tekshiruvidan oldin olib tashlanadi: "   " ism bo'lib o'tmasin.
    full_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120), NoNul
    ]
    email: Email
    password: NewPassword


class LoginIn(BaseModel):
    email: Email
    password: Annotated[Password, Field(min_length=1)]


class ChangePasswordIn(BaseModel):
    current_password: Annotated[Password, Field(min_length=1)]
    new_password: NewPassword


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=1)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    phone: str | None
    role: UserRole


class TokenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 (parol emas, OAuth2 token turi)
    expires_in: int
    signing_key: str
    user: UserOut
