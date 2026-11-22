from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.config import check_bcrypt_length, get_settings
from app.models.enums import UserRole
from app.schemas.types import Text

# Email har doim kichik harfda: Ali@x.uz va ali@x.uz bitta akkaunt.
Email = Annotated[EmailStr, AfterValidator(str.lower)]
Password = Annotated[str, AfterValidator(check_bcrypt_length)]


class RegisterIn(BaseModel):
    full_name: Annotated[Text, Field(min_length=2, max_length=120)]
    email: Email
    password: Password

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("password")
    @classmethod
    def check_min_length(cls, value: str) -> str:
        min_length = get_settings().password_min_length
        if len(value) < min_length:
            raise ValueError(f"Parol kamida {min_length} belgidan iborat bo'lishi kerak")
        return value


class LoginIn(BaseModel):
    email: Email
    password: Annotated[Password, Field(min_length=1)]


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
