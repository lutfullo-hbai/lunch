# Ovqat buyurtma boti — Umumiy reja

18.11.2026

## 1. Loyiha maqsadi

Mijozlar Telegram ichidan to'g'ridan-to'g'ri ovqat buyurtma qila olishi kerak. Har bir buyurtma oshxona guruhiga darhol yetib boradi va unda to'lov turi (naqd yoki karta) ko'rsatiladi.

Admin menyuni o'zi boshqaradi: ovqat qo'shadi, nomi, narxi, porsiyasi va rasmini o'zgartiradi. Dashboard orqali mijozlar va savdoni kuzatib boradi.

## 2. Kimlar foydalanadi

| Kim | Nima qiladi |
| --- | --- |
| Mijoz | Email (Gmail) va parol bilan ro'yxatdan o'tadi, menyuni ko'radi, buyurtma beradi, to'lov turini tanlaydi, buyurtmalari tarixini ko'radi |
| Super admin | Menyuni boshqaradi (qo'shish, tahrirlash, o'chirish, rasm), mijozlar ro'yxatini va buyurtmalarni ko'radi, statistikani kuzatadi |
| Oshxona guruhi | Telegram guruhda yangi buyurtmalarni oladi va "Qabul qilindi", "Tayyor" tugmalarini bosadi |

## 3. Texnologiyalar

| Qism | Texnologiya |
| --- | --- |
| Backend API | Python, FastAPI |
| Ma'lumotlar bazasi | PostgreSQL, SQLAlchemy |
| Migratsiyalar | Alembic |
| Frontend (Web App) | HTML, CSS, JavaScript |
| Telegram bot | aiogram |
| Auth | JWT (access + refresh), bcrypt, HMAC-SHA256 |
| Ishga tushirish | Docker Compose, Nginx (HTTPS) |

## 4. Arxitektura

```
 Foydalanuvchi (Telegram) ── /start ──▶ Telegram bot (aiogram)
        │                                        ▲
   Web App ochadi                        inline tugmalar
        ▼                                        │
 Web App (HTML/CSS/JS) ── HTTPS ──▶ Nginx    Buyurtmalar guruhi
                                     │            ▲
                                  /api/v1         │ yangi buyurtma (Naqd/Karta)
                                     ▼            │
                                  FastAPI (JWT + HMAC-SHA256) ──┘
                                   │          │
                                  SQL    rasm fayllari
                                   ▼          ▼
                             PostgreSQL    Disk (/media)
                             (Alembic)     (WebP, volume)
```

- **Telegram bot** foydalanuvchiga Web App ni ochadigan tugma beradi.
- **Web App** (HTML/CSS/JS) barcha so'rovlarni HTTPS orqali **FastAPI** ga yuboradi.
- **FastAPI** biznes logikani bajaradi: ma'lumotlarni **PostgreSQL** ga, ovqat rasmlarini **serverdagi diskka** yozadi.
- Yangi buyurtma bo'lganda FastAPI Telegram Bot API orqali **buyurtmalar guruhiga** xabar yuboradi.
- **Nginx** HTTPS, statik fayllar va rasmlarni beradi hamda so'rovlarni API ga yo'naltiradi.

## 5. Asosiy modullar

**Auth**

- Ro'yxatdan o'tish: ism, email, parol. Email kod bilan tasdiqlanmaydi.
- Login: email va parol. Parollar bazada bcrypt hash ko'rinishida saqlanadi.
- Login muvaffaqiyatli bo'lsa, qisqa muddatli access token va uzoq muddatli refresh token beriladi.
- API so'rovlari HMAC-SHA256 imzo bilan himoyalanadi.
- Super admin `.env` faylida ko'rsatilgan email orqali yaratiladi.

**Menyu (CRUD)**

- Admin ovqat qo'shadi, tahrirlaydi va o'chiradi. Har bir ovqatda nom, narx, porsiya va rasm bor.
- Rasmlar serverdagi diskda saqlanadi, bazaga faqat fayl yo'li yoziladi.

**Buyurtma va notification**

- Mijoz savatni to'ldiradi, telefon va manzilni kiritadi, to'lov turini tanlaydi: **naqd** yoki **karta**.
- Buyurtma summasi serverda, bazadagi narxlar asosida hisoblanadi.
- Buyurtma saqlangach, Telegram guruhga ovqatlar ro'yxati, jami summa va to'lov turi bilan xabar yuboriladi.

**Admin dashboard**

- Ro'yxatdan o'tgan userlar ro'yxati.
- Barcha buyurtmalar va ularning holati.
- Statistika: userlar soni, buyurtmalar soni, tushum (naqd va karta alohida).

## 6. Ma'lumotlar bazasi

Bazada 6 ta asosiy jadval bor. Sxemaga kiritilgan har bir o'zgarish Alembic migratsiyasi orqali versiyalanadi.

| Jadval | Nima saqlanadi |
| --- | --- |
| users | Ism, email, parol hashi, rol |
| refresh_tokens | Faol sessiyalar |
| categories | Ovqat kategoriyalari |
| menu_items | Nom, narx, porsiya, rasm yo'li |
| orders | Buyurtma, jami summa, to'lov turi, holat |
| order_items | Buyurtmadagi ovqatlar va miqdori |

## 7. Ish bosqichlari

Ish 6 bosqichda bajariladi. Muddatlar hali kelishilmagan.

| Bosqich | Nima qilinadi | Natija |
| --- | --- | --- |
| 1. Asos | FastAPI loyiha tuzilmasi, PostgreSQL, Alembic, Docker Compose | Loyiha ishga tushadi, migratsiyalar ishlaydi |
| 2. Auth | Register, login, JWT access/refresh, bcrypt, HMAC imzo | Userlar ro'yxatdan o'tib, tizimga kira oladi |
| 3. Menyu | Menyu CRUD API, rasm yuklash | Admin menyuni boshqaradi |
| 4. Buyurtma | Buyurtma API, naqd/karta, guruhga notification | Buyurtma guruhga yetib keladi |
| 5. Frontend va bot | HTML/CSS sahifalar (user va admin), aiogram bot | Telegram ichida to'liq ishlaydi |
| 6. Test va deploy | Testlar, server, HTTPS, zaxira nusxa | Tizim ishga tushiriladi |

## 8. Boshlash uchun kerakli narsalar

- [ ] Telegram bot tokeni (BotFather)
- [ ] Buyurtmalar guruhi va unga qo'shilgan bot
- [ ] Super admin email manzili
- [ ] Server va domen (Web App faqat HTTPS bilan ishlaydi)
- [ ] Boshlang'ich menyu: nomlar, narxlar, porsiyalar, rasmlar

**Ochiq savollar:** yetkazib berish narxi yoki minimal buyurtma summasi bormi? Ish vaqti cheklovi kerakmi?

Batafsil texnik tafsilotlar: [TEXNIK_REJA.md](TEXNIK_REJA.md).
