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

Frontend (login, menyu, savat, buyurtmalar): http://localhost:8081. nginx frontend fayllarini beradi va `/api`, `/media` so'rovlarini API'ga uzatadi.

## Frontend

Build bosqichi yo'q: `frontend/` dagi HTML, CSS va JS to'g'ridan-to'g'ri beriladi, o'zgarish sahifani yangilashda ko'rinadi.

```bash
cd frontend && npm test     # imzo backend bilan bir xil chiqishini tekshiradi
```

Telegram ichida ochish uchun HTTPS manzil kerak (lokalda tunnel, masalan `cloudflared tunnel --url http://localhost:8081`). Shu manzilni BotFather'da bot uchun Menu Button qilib qo'ying.

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
