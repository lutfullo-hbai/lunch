"""Ilova sozlamalari. Barcha qiymatlar muhit o'zgaruvchilaridan (.env) olinadi."""

from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# bcrypt faqat birinchi 72 baytni hisobga oladi (bcrypt 5 esa uzunrog'ida xato beradi).
# Bu algoritm cheklovi, sozlama emas.
BCRYPT_MAX_BYTES = 72


def check_bcrypt_length(password: str) -> str:
    """Belgi emas, bayt sanaladi: kirill harfi 2 bayt."""
    if len(password.encode()) > BCRYPT_MAX_BYTES:
        raise ValueError(f"Parol {BCRYPT_MAX_BYTES} baytdan oshmasligi kerak")
    return password


class Settings(BaseSettings):
    # Bo'sh qiymat (masalan `BOT_TOKEN=`) "berilmagan" deb hisoblanadi va default olinadi.
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", env_ignore_empty=True
    )

    app_name: str = "Lunch API"
    environment: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    # Sana filtrlari (masalan "bugungi buyurtmalar") shu zonada hisoblanadi.
    timezone: str = "Asia/Tashkent"

    database_url: str
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)

    # --- Auth ---
    jwt_secret: SecretStr = Field(min_length=32)
    # So'rov imzosi kalitlari shundan hosil qilinadi. JWT_SECRET'dan farqli bo'lishi shart:
    # biri sizib chiqsa, ikkinchisi xavfsiz qoladi.
    signing_secret: SecretStr = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = Field(default=1440, ge=1)  # 1 kun
    refresh_token_ttl_days: int = Field(default=7, ge=1)
    # Shu vaqt ichida almashtirilgan token qayta kelsa, bu o'g'irlik emas, parallel
    # so'rov deb hisoblanadi (masalan ikki tab bir vaqtda refresh qildi).
    refresh_reuse_grace_seconds: int = Field(default=30, ge=0)
    # Eskirgan va bekor qilingan sessiyalar shuncha kundan keyin bazadan o'chiriladi.
    token_retention_days: int = Field(default=30, ge=1)
    bcrypt_rounds: int = Field(default=12, ge=4, le=16)
    password_min_length: int = Field(default=8, ge=6)

    # Oddiy so'rovlar kichik JSON, katta body kerak emas.
    max_request_kb: int = Field(default=64, ge=1)
    # Rasm yuklash so'rovining maksimal hajmi (faqat yaroqli access token bilan).
    max_upload_mb: int = Field(default=6, ge=1)

    # --- Rate limit (IP bo'yicha): oynada ruxsat etilgan urinishlar soni ---
    login_rate_limit: int = Field(default=10, ge=1)
    login_rate_window_seconds: int = Field(default=60, ge=1)
    register_rate_limit: int = Field(default=5, ge=1)
    register_rate_window_seconds: int = Field(default=3600, ge=1)

    # --- Rasmlar ---
    media_dir: Path = Path("media")
    media_url_prefix: str = "/media"
    image_max_upload_mb: int = Field(default=5, ge=1)
    # "Decompression bomb"dan himoya: 16 MP RGBA rasm ochilganda ~64 MB xotira oladi.
    image_max_pixels: int = Field(default=16_000_000, ge=1)
    # Bir vaqtda nechta rasm qayta ishlanadi (har biri yuzlab MB xotira olishi mumkin).
    image_max_parallel: int = Field(default=2, ge=1)
    image_size: int = Field(default=1200, ge=100)
    image_thumb_size: int = Field(default=400, ge=50)
    image_quality: int = Field(default=85, ge=1, le=100)

    # --- Buyurtma ---
    # Bitta buyurtmadagi har xil ovqatlar soni (juda katta so'rovdan himoya).
    order_max_lines: int = Field(default=50, ge=1)
    currency: str = "so'm"

    # --- Telegram: buyurtmalar guruhiga xabar ---
    # Ikkalasi berilmasa, xabar yuborilmaydi (buyurtma baribir qabul qilinadi).
    bot_token: SecretStr | None = None
    orders_group_chat_id: int | None = None
    telegram_api_url: str = "https://api.telegram.org"
    telegram_timeout_seconds: float = Field(default=10, gt=0)
    # Yuborilmasa, shuncha soniyadan keyin qayta uriniladi; hammasi tugasa `failed`.
    notify_retry_delays: list[float] = [2, 4, 8]

    # --- Sahifalash ---
    page_size_default: int = Field(default=20, ge=1)
    page_size_max: int = Field(default=100, ge=1)
    page_number_max: int = Field(default=10_000, ge=1)  # juda katta OFFSET'dan himoya

    # --- So'rov imzosi (HMAC-SHA256) ---
    signature_max_skew_seconds: int = Field(default=60, ge=1)
    nonce_max_length: int = Field(default=128, ge=16)

    # --- Super admin (ilova ishga tushganda yaratiladi) ---
    super_admin_email: str | None = None
    super_admin_password: SecretStr | None = None
    super_admin_full_name: str = "Super Admin"

    # Vergul bilan ajratilgan ro'yxat: "https://a.uz,https://b.uz"
    cors_origins: str = ""

    @field_validator("super_admin_password")
    @classmethod
    def check_admin_password(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None:
            check_bcrypt_length(value.get_secret_value())
        return value

    @model_validator(mode="after")
    def check_secrets_differ(self) -> "Settings":
        if self.signing_secret.get_secret_value() == self.jwt_secret.get_secret_value():
            raise ValueError("SIGNING_SECRET JWT_SECRET bilan bir xil bo'lmasligi kerak")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
