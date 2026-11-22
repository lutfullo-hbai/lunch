from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.config import BCRYPT_MAX_BYTES, get_settings
from app.models.enums import UserRole


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        min_length = get_settings().password_min_length
        if len(value) < min_length:
            raise ValueError(f"Parol kamida {min_length} belgidan iborat bo'lishi kerak")
        if len(value.encode()) > BCRYPT_MAX_BYTES:
            raise ValueError(f"Parol {BCRYPT_MAX_BYTES} baytdan oshmasligi kerak")
        return value


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)

    @field_validator("password")
    @classmethod
    def check_password_bytes(cls, value: str) -> str:
        # Belgi emas, bayt sanaladi: kirill harfi 2 bayt.
        if len(value.encode()) > BCRYPT_MAX_BYTES:
            raise ValueError(f"Parol {BCRYPT_MAX_BYTES} baytdan oshmasligi kerak")
        return value

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return value.lower()


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
