# lunch

Telegram Web App orqali ovqat buyurtma qilish tizimi: menyu, savat, naqd yoki karta bilan buyurtma, buyurtmalar Telegram guruhga yuboriladi, admin panel.

## Hujjatlar

- [Umumiy reja](docs/UMUMIY_REJA.md)
- [Texnik reja](docs/TEXNIK_REJA.md)
- [Login va admin panel rejasi](docs/LOGIN_ADMIN_REJA.md)
- [API qo'llanma](docs/API.md)
- [Jamoada ishlash qoidalari](CONTRIBUTING.md)

## Ishga tushirish (Docker)

```bash
cp .env.example .env      # qiymatlarni o'zgartiring
docker compose up -d --build
curl http://localhost:8080/health
```

API hujjati (production'dan tashqari): http://localhost:8080/docs

## Backend'ni lokal ishlab chiqish

[uv](https://docs.astral.sh/uv/) kerak.

```bash
cd backend
uv sync
docker compose up -d db                 # faqat PostgreSQL
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Tekshiruvlar (CI ham shularni ishlatadi):

```bash
uv run ruff check . && uv run ruff format --check .
DATABASE_URL=postgresql+asyncpg://... uv run pytest
```

Testlar alohida test bazasida ishga tushirilishi kerak: `DATABASE_URL` ni test bazasiga yo'naltiring.
