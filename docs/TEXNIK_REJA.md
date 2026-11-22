# Telegram Web App — Ovqat buyurtma tizimi: Texnik reja

18.11.2026

## 1. Loyiha haqida

Telegram bot ichida ochiladigan Web App orqali foydalanuvchi ovqat buyurtma qiladi, buyurtma esa darhol oshxona Telegram guruhiga to'lov turi (naqd yoki karta) bilan birga yuboriladi. Super admin menyuni (nomi, narxi, porsiyasi, rasmi) boshqaradi va dashboard orqali foydalanuvchilar hamda buyurtmalarni kuzatadi.

**Doiraga kiradi:** menyu CRUD, rasm yuklash, email (Gmail) va parol bilan ro'yxatdan o'tish va kirish, JWT, buyurtma, guruhga xabar, admin dashboard.

| Qatlam | Texnologiya | Izoh |
| --- | --- | --- |
| Backend API | Python 3.12, FastAPI | async, OpenAPI hujjat avtomatik |
| ORM | SQLAlchemy 2.0 + asyncpg | async sessiyalar |
| Migratsiya | Alembic | har bir sxema o'zgarishi versiyalanadi |
| Ma'lumotlar bazasi | PostgreSQL 16 | |
| Bot | aiogram 3 | `/start` va Web App tugmasi |
| Frontend | HTML, CSS, vanilla JS | `telegram-web-app.js` SDK |
| Auth | PyJWT, bcrypt (passlib), HMAC-SHA256 | email + parol, access + refresh token |
| Rasm ishlov | Pillow | o'lcham va format tekshiruvi |
| Ishga tushirish | Docker Compose, Nginx | HTTPS majburiy |

## 2. Rollar va huquqlar

Tizimda ikkita rol bor. Super admin `.env` faylidagi `SUPER_ADMIN_EMAIL` orqali aniqlanadi: ilova birinchi marta ishga tushganda shu email bilan admin hisobi avtomatik yaratiladi (seed). Oddiy ro'yxatdan o'tish orqali admin bo'lib bo'lmaydi.

| Amal | Oddiy user | Super admin |
| --- | --- | --- |
| Ro'yxatdan o'tish (email + parol) | Ha | Yo'q, seed orqali yaratiladi |
| Email va parol bilan kirish (JWT olish) | Ha | Ha |
| Menyuni ko'rish | Ha | Ha |
| Ovqat qo'shish, tahrirlash, o'chirish, rasm yuklash | Yo'q | Ha |
| Buyurtma berish (naqd yoki karta) | Ha | Ha |
| O'z buyurtmalarini ko'rish | Ha | Ha |
| Barcha buyurtmalar va holatini o'zgartirish | Yo'q | Ha |
| Ro'yxatdan o'tgan userlar ro'yxati | Yo'q | Ha |
| Dashboard statistikasi | Yo'q | Ha |

Admin panel ham Telegram Web App ichida ochiladi: admin tokenida `role=admin` bo'lsa, frontend admin sahifalarini ko'rsatadi, backend esa har bir `/admin/*` so'rovda rolni qayta tekshiradi.

## 3. Arxitektura

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

Foydalanuvchi botdagi tugma orqali Web App ni ochadi. Web App barcha so'rovlarni Nginx orqali FastAPI ga yuboradi. FastAPI ma'lumotlarni PostgreSQL ga, rasmlarni diskka yozadi va yangi buyurtmani guruhga yuboradi. Guruhdagi inline tugmalar bosilganda bot buyurtma holatini yangilaydi.

| Komponent | Vazifasi |
| --- | --- |
| Telegram bot (aiogram) | `/start`, Web App tugmasi, guruhdagi inline tugmalarni qayta ishlash |
| Web App | Foydalanuvchi va admin interfeysi, Telegram ichida ochiladi |
| Nginx | TLS, statik fayllar, `/media/` rasmlar, `/api/` ni uvicorn ga proksi qilish |
| FastAPI | Biznes logika, auth, validatsiya, notification |
| PostgreSQL | Barcha ma'lumotlar, Alembic orqali versiyalanadi |
| Disk (volume) | Ovqat rasmlari |

## 4. Xavfsizlik

Himoya uch qatlamdan iborat: email va parol foydalanuvchi kimligini tasdiqlaydi (parol bcrypt bilan hashlanadi), JWT sessiyani boshqaradi, HMAC-SHA256 imzo esa har bir API so'rovining yo'lda o'zgartirilmaganini kafolatlaydi.

### 4.1 Ro'yxatdan o'tish va login (email + parol)

1. **Ro'yxatdan o'tish:** foydalanuvchi `register.html` sahifasida faqat ism, email (masalan Gmail) va parolni kiritadi. Emailni kod orqali tasdiqlash talab qilinmaydi. Frontend ularni `POST /api/v1/auth/register` ga yuboradi.
2. Backend emailni kichik harfga o'tkazadi va formatini tekshiradi. Bunday email bazada allaqachon bo'lsa, `409` qaytaradi.
3. Parol kamida 8 belgidan iborat bo'lishi va ichida harf hamda raqam bo'lishi shart.
4. Parol **bcrypt** (cost 12) bilan hashlanadi va bazada faqat hash saqlanadi. Parol uchun SHA-256 ishlatilmaydi: u juda tez ishlaydi, shuning uchun parolni tanlab topish (brute-force) hujumiga chidamsiz.
5. **Login:** `login.html` email va parolni `POST /api/v1/auth/login` ga yuboradi. Backend parolni `bcrypt.verify` bilan tekshiradi va access token, refresh token hamda signing_key qaytaradi.
6. Xato bo'lsa javob har doim bir xil: "Email yoki parol noto'g'ri". Qaysi biri xato ekanligi aytilmaydi.
7. Parol ketma-ket 5 marta xato kiritilsa, hisob 15 daqiqaga bloklanadi.
8. **Parolni almashtirish:** `POST /auth/change-password` eski parolni so'raydi va userning barcha refresh tokenlarini bekor qiladi.

### 4.2 JWT: access va refresh token

| Token | Muddat | Qayerda saqlanadi | Tarkibi |
| --- | --- | --- | --- |
| Access | 15 daqiqa | Frontend xotirasida (JS o'zgaruvchi) | `sub` (user id), `role`, `type=access`, `exp`, `jti` |
| Refresh | 7 kun | Frontend `sessionStorage`; DB da faqat SHA-256 hashi | `sub`, `type=refresh`, `exp`, `jti` |

- Algoritm: HS256, kalit `JWT_SECRET` (kamida 32 bayt, `.env` da).
- **Refresh rotation:** `POST /auth/refresh` eski refresh tokenni bekor qiladi va yangi juftlik beradi.
- **Qayta ishlatishni aniqlash:** bekor qilingan refresh token yana kelsa, o'sha userning barcha refresh tokenlari bekor qilinadi.
- **Logout:** joriy refresh token `revoked=true` qilinadi.
- Access token muddati tugaganda frontend avtomatik refresh qiladi va so'rovni qaytaradi.

### 4.3 API so'rovlarini imzolash (HMAC-SHA256)

Har bir himoyalangan so'rov quyidagi sarlavhalar bilan keladi:

```
Authorization: Bearer <access_token>
X-Timestamp:   1763463120
X-Nonce:       9f1c2e7a-...
X-Signature:   hex(HMAC_SHA256(signing_key, METHOD + "\n" + PATH + "\n" + TIMESTAMP + "\n" + NONCE + "\n" + SHA256(BODY)))
```

- `signing_key` login paytida har bir sessiya uchun alohida yaratiladi va access token bilan birga qaytariladi. Shu sababli kalit frontend kodida ochiq turmaydi.
- Backend middleware imzoni qayta hisoblab `compare_digest` bilan solishtiradi.
- `X-Timestamp` 60 soniyadan eski bo'lsa yoki `X-Nonce` oldin ishlatilgan bo'lsa, so'rov `401` bilan rad etiladi (replay himoyasi).
- Fayl yuklash so'rovlarida body hashi multipart xom baytlaridan hisoblanadi.

### 4.4 Qo'shimcha choralar

- Faqat HTTPS (Telegram Web App boshqasini qabul qilmaydi); HSTS yoqiladi.
- CORS faqat `WEBAPP_ORIGIN` uchun ochiq.
- Rate limit: auth uchun daqiqasiga 10 ta, buyurtma uchun daqiqasiga 5 ta so'rov (slowapi).
- Barcha kiruvchi ma'lumotlar Pydantic sxemalari orqali tekshiriladi; SQL faqat ORM orqali.
- Narx frontenddan qabul qilinmaydi: buyurtma summasi har doim DB dagi narxdan hisoblanadi.
- Xatolar foydalanuvchiga ichki tafsilotlarsiz qaytariladi; to'liq xato logda qoladi.
- Sirlar (`BOT_TOKEN`, `JWT_SECRET`, DB paroli) faqat `.env` da turadi va repoga kiritilmaydi.

## 5. Ma'lumotlar bazasi (PostgreSQL + Alembic)

Bazada 6 ta jadval bo'ladi. Pul summalari `NUMERIC(12,2)` turida, vaqtlar `TIMESTAMPTZ` (UTC) da saqlanadi.

**users**

| Ustun | Tur | Izoh |
| --- | --- | --- |
| id | BIGSERIAL PK | |
| email | VARCHAR(254) UNIQUE NOT NULL | kichik harfda saqlanadi |
| password_hash | VARCHAR(255) NOT NULL | bcrypt hash |
| full_name | VARCHAR(128) | |
| phone | VARCHAR(20) | birinchi buyurtmada kiritiladi va saqlanadi |
| role | ENUM(user, admin) | default `user` |
| is_blocked | BOOLEAN | default false |
| failed_login_count | SMALLINT | ketma-ket xato urinishlar |
| locked_until | TIMESTAMPTZ | vaqtinchalik blok |
| created_at, last_login_at | TIMESTAMPTZ | |

**refresh_tokens**

| Ustun | Tur | Izoh |
| --- | --- | --- |
| id | BIGSERIAL PK | |
| user_id | FK → users ON DELETE CASCADE | indeks |
| jti | UUID UNIQUE | |
| token_hash | CHAR(64) | SHA-256, xom token saqlanmaydi |
| signing_key_enc | TEXT | sessiyaning HMAC kaliti |
| expires_at | TIMESTAMPTZ | |
| revoked_at | TIMESTAMPTZ | null = faol |

**categories**: `id`, `name` (UNIQUE), `sort_order`, `is_active`.

**menu_items**

| Ustun | Tur | Izoh |
| --- | --- | --- |
| id | BIGSERIAL PK | |
| category_id | FK → categories, null bo'lishi mumkin | |
| name | VARCHAR(120) NOT NULL | |
| description | TEXT | |
| price | NUMERIC(12,2) CHECK > 0 | so'm |
| portion | VARCHAR(50) | masalan "1 porsiya, 350 g" |
| image_path | VARCHAR(255) | diskdagi nisbiy yo'l |
| is_available | BOOLEAN | default true |
| deleted_at | TIMESTAMPTZ | soft delete: eski buyurtmalar buzilmaydi |
| created_at, updated_at | TIMESTAMPTZ | |

**orders**

| Ustun | Tur | Izoh |
| --- | --- | --- |
| id | BIGSERIAL PK | |
| user_id | FK → users | indeks |
| total_price | NUMERIC(12,2) | serverda hisoblanadi |
| payment_method | ENUM(cash, card) | NOT NULL |
| status | ENUM(new, accepted, cooking, delivered, cancelled) | default `new` |
| phone, address, comment | VARCHAR / TEXT | |
| notify_status | ENUM(pending, sent, failed) | guruhga yuborilganmi |
| created_at, updated_at | TIMESTAMPTZ | indeks `created_at` |

**order_items**: `id`, `order_id` (FK, CASCADE), `menu_item_id` (FK), `name_snapshot`, `price_snapshot`, `quantity` (CHECK 1–50). Snapshot ustunlari menyudagi narx keyinchalik o'zgarsa ham buyurtma tarixini to'g'ri saqlaydi.

### Alembic qoidalari

- Har bir model o'zgarishi alohida migratsiya: `alembic revision --autogenerate -m "add_orders"`.
- Avtomatik yaratilgan migratsiya commitdan oldin qo'lda ko'rib chiqiladi (ENUM va indekslar ko'pincha tuzatish talab qiladi).
- Har bir migratsiyada `downgrade()` ishlaydigan bo'lishi shart.
- `env.py` async engine bilan sozlanadi, DB manzili `.env` dan olinadi.
- Konteyner ishga tushganda `alembic upgrade head` avtomatik bajariladi.
- Boshlang'ich migratsiyalar: `0001_users_tokens`, `0002_menu`, `0003_orders`.

## 6. API endpointlari

Barcha endpointlar `/api/v1` prefiksi ostida joylashadi. "Himoya" ustunidagi **JWT+Sig** belgisi Bearer token va HMAC imzo ikkalasi ham talab qilinishini bildiradi.

| Metod | Yo'l | Himoya | Vazifa |
| --- | --- | --- | --- |
| POST | /auth/register | ochiq, rate limit | Yangi user: ism, email, parol |
| POST | /auth/login | ochiq, rate limit | Email + parol; access + refresh + signing_key qaytaradi |
| POST | /auth/refresh | refresh token | Tokenlarni almashtiradi (rotation) |
| POST | /auth/logout | JWT+Sig | Refresh tokenni bekor qiladi |
| POST | /auth/change-password | JWT+Sig | Parolni almashtiradi |
| GET | /me | JWT+Sig | Joriy user ma'lumoti |
| GET | /categories | JWT+Sig | Kategoriyalar ro'yxati |
| GET | /menu | JWT+Sig | Mavjud ovqatlar (`?category_id=`) |
| GET | /menu/{id} | JWT+Sig | Bitta ovqat |
| POST | /orders | JWT+Sig | Buyurtma yaratadi va guruhga xabar yuboradi |
| GET | /orders/me | JWT+Sig | O'z buyurtmalari (sahifalangan) |
| POST | /admin/menu | JWT+Sig, admin | Ovqat qo'shadi (multipart: maydonlar + rasm) |
| PUT | /admin/menu/{id} | JWT+Sig, admin | Ovqatni tahrirlaydi (rasm almashtirish ixtiyoriy) |
| DELETE | /admin/menu/{id} | JWT+Sig, admin | Soft delete |
| PATCH | /admin/menu/{id}/availability | JWT+Sig, admin | "Tugadi" yoki "bor" holatiga o'tkazadi |
| POST, PUT, DELETE | /admin/categories | JWT+Sig, admin | Kategoriya CRUD |
| GET | /admin/users | JWT+Sig, admin | Ro'yxatdan o'tgan userlar (qidiruv, sahifalash) |
| PATCH | /admin/users/{id}/block | JWT+Sig, admin | Userni bloklaydi yoki blokdan chiqaradi |
| GET | /admin/orders | JWT+Sig, admin | Barcha buyurtmalar (`?status=&payment=&date_from=`) |
| PATCH | /admin/orders/{id}/status | JWT+Sig, admin | Buyurtma holatini o'zgartiradi |
| GET | /admin/stats | JWT+Sig, admin | Dashboard ko'rsatkichlari |
| GET | /health | ochiq | Monitoring uchun |

**Javob formati:** muvaffaqiyatli javobda resursning o'zi qaytadi. Xatolik formati bir xil bo'ladi: `{"error": {"code": "MENU_NOT_FOUND", "message": "..."}}`. Ro'yxatlar `{"items": [...], "total": 120, "page": 1, "size": 20}` ko'rinishida qaytariladi.

**`/admin/stats` qaytaradigan ko'rsatkichlar:** jami userlar, bugungi yangi userlar, bugungi va oylik buyurtmalar soni, tushum (naqd va karta bo'yicha alohida), eng ko'p sotilgan 5 ta ovqat, so'nggi 7 kunlik buyurtmalar grafigi uchun ma'lumot.

## 7. Buyurtma oqimi va guruhga notification

Buyurtma DB ga tranzaksiya ichida yoziladi. Guruhga xabar undan keyin fonda yuboriladi, shuning uchun Telegram API vaqtincha ishlamasa ham buyurtma yo'qolmaydi.

### 7.1 Qadamlar

1. User savatni to'ldiradi, telefon raqami va manzilini kiritadi, so'ng **to'lov turini tanlaydi: Naqd yoki Karta** (majburiy maydon).
2. Frontend `POST /orders` yuboradi: `{items: [{menu_item_id, quantity}], payment_method: "cash"|"card", phone, address, comment}`.
3. Backend har bir ovqatning mavjudligini (`is_available`, `deleted_at IS NULL`) tekshiradi va narxni DB dan oladi.
4. `orders` va `order_items` bitta tranzaksiyada yoziladi; `notify_status = pending`.
5. User darhol `201 Created` javobini va buyurtma raqamini oladi.
6. Fon vazifasi (`BackgroundTasks`) Bot API `sendMessage` orqali guruhga xabar yuboradi. Ovqat rasmi kerak bo'lsa, `sendPhoto` ishlatiladi.
7. Muvaffaqiyatli bo'lsa `notify_status = sent`. Xato bo'lsa 3 marta qayta urinadi (2, 4, 8 soniya oraliqda), keyin `failed` qilib qo'yadi. Admin panelda bunday buyurtmalar ajratib ko'rsatiladi.
8. Xabar ostida inline tugmalar bo'ladi: **Qabul qilindi**, **Tayyor**, **Bekor qilish**. Ular bosilganda bot buyurtma holatini yangilaydi, userga esa shaxsiy xabar boradi.

### 7.2 Guruhga boradigan xabar shabloni

```
🆕 Yangi buyurtma #128

👤 Ali Valiyev (ali.valiyev@gmail.com)
📞 +998 90 123 45 67
📍 Chilonzor 9-kvartal, 12-uy

🍽 Osh × 2 — 60 000 so'm
🥗 Achchiq-chuchuk × 1 — 12 000 so'm
🥤 Choy × 1 — 5 000 so'm

💰 Jami: 77 000 so'm
💳 To'lov turi: KARTA
💬 Izoh: piyozsiz bo'lsin
🕒 18.11.2026 14:32
```

To'lov turi naqd bo'lsa, qatorda `💵 To'lov turi: NAQD` yoziladi. Xabar `parse_mode=HTML` bilan yuboriladi va user kiritgan matn (izoh, manzil) HTML-escape qilinadi.

### 7.3 Sozlamalar

- `ORDERS_GROUP_CHAT_ID`: guruh ID si (manfiy son, masalan `-1001234567890`).
- Bot guruhga qo'shilgan va xabar yuborish huquqiga ega bo'lishi kerak.
- Inline tugmalarni faqat `GROUP_ADMIN_TG_IDS` dagi a'zolar bosa oladi; boshqalarga "Ruxsat yo'q" javobi qaytadi.

## 8. Ovqat rasmlarini diskda saqlash

Rasmlar serverdagi `MEDIA_ROOT` papkasida (Docker volume) saqlanadi. DB ga faqat nisbiy yo'l yoziladi, fayllarni esa Nginx to'g'ridan-to'g'ri `/media/` manzili orqali beradi.

- **Yuklash:** `POST /admin/menu` va `PUT /admin/menu/{id}` so'rovlari `multipart/form-data` qabul qiladi, maydon nomi `image`.
- **Tekshiruv:** ruxsat etilgan formatlar JPEG, PNG va WebP; maksimal hajm 5 MB. Format fayl kengaytmasi orqali emas, Pillow yordamida faylning ichki tarkibidan aniqlanadi.
- **Qayta ishlash:** rasm 1200 px gacha kichraytiriladi va WebP formatiga (sifat 82) o'giriladi. Ro'yxat sahifasi uchun 400 px li thumbnail ham yaratiladi. EXIF ma'lumotlari (jumladan GPS) o'chiriladi.
- **Nomlash:** `menu/{yyyy}/{mm}/{uuid4}.webp` va `..._thumb.webp`. User bergan fayl nomi hech qachon ishlatilmaydi, bu path traversal hujumining oldini oladi.
- **Almashtirish va o'chirish:** yangi rasm yuklanganda eski fayl DB commit muvaffaqiyatli bo'lgandan keyin o'chiriladi. Ovqat soft delete qilinganda rasm saqlanib qoladi, chunki eski buyurtmalar unga murojaat qiladi.
- **Berish:** Nginx `location /media/` uchun `Cache-Control: public, max-age=2592000` sarlavhasini qo'yadi. Bu papkada skript bajarish o'chirilgan.
- **Zaxira nusxa:** `media` volume har kuni DB dump bilan birga arxivlanadi.
- **Kelajak:** keyinchalik S3 yoki MinIO ga o'tish oson bo'lishi uchun saqlash `StorageService` interfeysi orqali yoziladi.

## 9. Frontend sahifalari (HTML, CSS, JS)

Frontend build bosqichisiz oddiy statik fayllardan iborat va Nginx orqali beriladi. Ranglar Telegram mavzusidan (`--tg-theme-*` CSS o'zgaruvchilari) olinadi, shuning uchun ilova yorug' va qorong'i rejimga avtomatik moslashadi.

| Sahifa | Kim uchun | Tarkibi |
| --- | --- | --- |
| `login.html` (Kirish) | Hamma | Email, parol, "Ro'yxatdan o'tish" havolasi |
| `register.html` | Yangi user | Ism, email, parol |
| `index.html` (Menyu) | User | Kategoriya tablari, ovqat kartalari (rasm, nom, porsiya, narx), "+" va "−" tugmalari |
| `cart.html` (Savat) | User | Tanlangan ovqatlar, miqdor, jami summa, telefon, manzil, izoh, **Naqd / Karta tanlovi**, Telegram MainButton "Buyurtma berish" |
| `orders.html` | User | O'z buyurtmalari tarixi va holati |
| `admin/dashboard.html` | Admin | KPI kartalar (userlar, bugungi buyurtmalar, tushum naqd/karta), 7 kunlik grafik, top-5 ovqat |
| `admin/menu.html` | Admin | Ovqatlar jadvali (rasm, nom, narx, porsiya, holat), qidiruv, "Qo'shish" tugmasi |
| `admin/menu-form.html` | Admin | Qo'shish va tahrirlash formasi, rasm yuklash, oldindan ko'rish |
| `admin/users.html` | Admin | Ro'yxatdan o'tgan userlar: ism, email, telefon, ro'yxatdan o'tgan sana, buyurtmalar soni, bloklash |
| `admin/orders.html` | Admin | Buyurtmalar ro'yxati, filtrlar (holat, to'lov turi, sana), holatni o'zgartirish |

**Umumiy JS modullari (`assets/js/`):**

- `api.js`: `fetch` uchun o'ram. Tokenni qo'shadi, HMAC imzoni Web Crypto API (`crypto.subtle`) bilan hisoblaydi, `401` kelganda refresh qilib so'rovni qaytaradi.
- `auth.js`: login va register formalarini yuboradi va tokenlarni saqlaydi. Token bo'lmasa yoki refresh ishlamasa, foydalanuvchini `login.html` ga yo'naltiradi.
- `cart.js`: savat holati (`sessionStorage`).
- `ui.js`: toast xabarlar, yuklanish holati, `Telegram.WebApp.HapticFeedback`.

**Sifat talablari:** sahifalar 360 px kenglikdagi ekranda to'g'ri ko'rinadi, rasmlar `loading="lazy"` bilan yuklanadi, foydalanuvchi matni DOM ga `textContent` orqali qo'yiladi (`innerHTML` ishlatilmaydi, XSS dan himoya).

## 10. Papka tuzilmasi va konfiguratsiya

Kod qatlamlarga ajratilgan: routerlar faqat HTTP bilan, servislar biznes logika bilan, repozitoriylar DB bilan ishlaydi.

```
bot/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI ilova, middleware, routerlar
│   │   ├── core/
│   │   │   ├── config.py        # pydantic-settings, .env
│   │   │   ├── security.py      # JWT, bcrypt, HMAC imzo
│   │   │   └── deps.py          # get_db, get_current_user, require_admin
│   │   ├── db/                  # engine, session, Base
│   │   ├── models/              # user, token, category, menu_item, order
│   │   ├── schemas/             # Pydantic so'rov/javob sxemalari
│   │   ├── repositories/        # DB so'rovlari
│   │   ├── services/            # auth, menu, order, storage, notifier, stats
│   │   └── api/v1/              # auth, menu, orders, admin routerlari
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── tests/
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── Dockerfile
├── telegram_bot/
│   ├── main.py                  # aiogram: /start, Web App tugmasi, inline callbacklar
│   └── Dockerfile
├── web/
│   ├── login.html, register.html
│   ├── index.html, cart.html, orders.html
│   ├── admin/
│   └── assets/{css,js,img}/
├── nginx/
│   └── default.conf
├── docker-compose.yml
├── .env.example
└── README.md
```

**Muhit o'zgaruvchilari (`.env.example`):**

| O'zgaruvchi | Misol | Vazifa |
| --- | --- | --- |
| `BOT_TOKEN` | `123456:ABC...` | BotFather bergan token |
| `SUPER_ADMIN_EMAIL` | `admin@gmail.com` | Super admin hisobi (seed) |
| `SUPER_ADMIN_PASSWORD` | kuchli parol | Faqat birinchi ishga tushirishda ishlatiladi |
| `GROUP_ADMIN_TG_IDS` | `111111111,222222222` | Guruhdagi inline tugmalarni bosa oladiganlar |
| `ORDERS_GROUP_CHAT_ID` | `-1001234567890` | Buyurtmalar guruhi |
| `DATABASE_URL` | `postgresql+asyncpg://app:***@db:5432/food` | DB ulanishi |
| `JWT_SECRET` | 64 belgili tasodifiy qator | JWT imzo kaliti |
| `SIGNING_SECRET` | boshqa 64 belgili tasodifiy qator | So'rov imzosi kalitlari shundan hosil qilinadi |
| `BCRYPT_ROUNDS` | `12` | Parol hash kuchi |
| `ACCESS_TOKEN_TTL_MIN` | `15` | |
| `REFRESH_TOKEN_TTL_DAYS` | `7` | |
| `SIGNATURE_MAX_SKEW_SEC` | `60` | Imzo vaqt chegarasi |
| `WEBAPP_URL` | `https://food.example.uz` | Web App manzili va CORS |
| `MEDIA_ROOT` | `/data/media` | Rasmlar papkasi |
| `MAX_IMAGE_MB` | `5` | |

## 11. Ish bosqichlari va qabul mezonlari

Ish 9 bosqichga bo'lingan. Har bir bosqich tugaganda ishlaydigan natija bo'ladi va keyingi bosqich faqat oldingisining qabul mezonlari bajarilgandan keyin boshlanadi. Muddatlar hali kelishilmagan.

1. **Asos.** Papka tuzilmasi, `docker-compose` (api, db, bot, nginx), config, DB ulanishi, `/health` endpointi.
    - Qabul mezoni: `docker compose up` buyrug'idan keyin `/health` 200 qaytaradi, `alembic upgrade head` xatosiz o'tadi.
2. **Modellar va migratsiyalar.** 6 ta jadval, ENUM lar, indekslar, `0001`–`0003` migratsiyalari.
    - Qabul mezoni: `upgrade` va `downgrade` ikkala yo'nalishda ham ishlaydi.
3. **Auth.** Register va login (email + parol, bcrypt), JWT access va refresh, rotation, logout, HMAC imzo middleware'i, `require_admin`.
    - Qabul mezoni: noto'g'ri parol, muddati o'tgan token, noto'g'ri imzo va takroriy nonce testlarda `401` qaytaradi.
4. **Menyu CRUD va rasmlar.** Kategoriyalar, ovqatlar, rasm yuklash, WebP ga o'girish, soft delete.
    - Qabul mezoni: admin ovqat qo'sha oladi, tahrirlay oladi va o'chira oladi; oddiy user `403` oladi; 5 MB dan katta yoki rasm bo'lmagan fayl rad etiladi.
5. **Buyurtmalar va notification.** `POST /orders`, narxni server tomonida hisoblash, Naqd/Karta, guruhga xabar, qayta urinish, inline tugmalar.
    - Qabul mezoni: buyurtmadan keyin 5 soniya ichida guruhda to'lov turi ko'rsatilgan xabar paydo bo'ladi.
6. **Admin API.** Userlar ro'yxati, buyurtmalar filtri, holatni o'zgartirish, `/admin/stats`.
    - Qabul mezoni: statistika test ma'lumotlari bilan qo'lda hisoblangan natijaga mos keladi.
7. **Telegram bot.** `/start` buyrug'i, Web App menyu tugmasi, admin uchun qo'shimcha tugma.
8. **Frontend.** User sahifalari, keyin admin sahifalari, `api.js` imzo va avtomatik refresh bilan.
    - Qabul mezoni: to'liq ssenariy (ro'yxatdan o'tish → kirish → menyu → savat → karta tanlash → buyurtma) haqiqiy Telegram ilovasida Android va iOS da ishlaydi.
9. **Test, hujjat, deploy.** pytest bilan backend qoplamasi kamida 80%, README, server va domen, SSL sertifikati, zaxira nusxa.
    - Qabul mezoni: ishlab chiqarish serverida to'liq ssenariy ishlaydi va zaxira nusxadan tiklash sinab ko'rilgan.

## 12. Test, deploy va xavflar

### Test

- **Unit testlar:** register va login (to'g'ri parol, noto'g'ri parol, band email, bloklash), JWT yaratish va tekshirish, HMAC imzo, narx hisoblash.
- **Integratsion testlar:** test PostgreSQL bazasida (testcontainers yoki alohida compose servisi) har bir endpoint `httpx.AsyncClient` orqali sinaladi.
- **Mock:** Telegram Bot API soxta HTTP server bilan almashtiriladi; xabar matni va to'lov turi alohida tekshiriladi.
- **CI:** har bir push da ruff, mypy, pytest va `alembic upgrade head` ishga tushadi.

### Deploy

- Bitta VPS (2 vCPU, 2 GB RAM) 1-versiya uchun yetarli. Servislar Docker Compose bilan ishga tushiriladi.
- Nginx: TLS (Let's Encrypt), statik fayllar `web/`, `/media/`, `/api/` esa uvicorn ga proksi qilinadi.
- PostgreSQL faqat ichki tarmoqda, tashqariga port ochilmaydi.
- Zaxira nusxa: har kuni `pg_dump` va `media` arxivi, 14 kun saqlanadi.
- Loglar JSON formatida yoziladi; buyurtma notification xatolari alohida log darajasida.

### Xavflar va yechimlar

| Xavf | Ta'siri | Yechim |
| --- | --- | --- |
| Telegram API vaqtincha ishlamaydi | Guruh buyurtmani ko'rmaydi | Qayta urinish, `notify_status=failed`, admin panelda ogohlantirish |
| `BOT_TOKEN` yoki `JWT_SECRET` sizib chiqadi | Soxta foydalanuvchilar | Faqat `.env` da saqlash, almashtirish tartibi README da yoziladi |
| Parollarni tanlab topish (brute-force) | Hisob buziladi | bcrypt, 5 xatodan keyin 15 daqiqa blok, rate limit |
| Disk rasmlar bilan to'ladi | Yuklash ishlamay qoladi | WebP siqish, 5 MB chegara, disk monitoringi |
| Frontenddan narx o'zgartiriladi | Noto'g'ri summa | Narx faqat DB dan olinadi |
| Bitta server ishdan chiqadi | Xizmat to'xtaydi | Kunlik zaxira nusxa va hujjatlashtirilgan tiklash tartibi |

### Ochiq savollar

- Yetkazib berish narxi bormi yoki minimal buyurtma summasi bormi?
- Ish vaqti cheklovi kerakmi (masalan, 09:00–22:00 dan tashqarida buyurtma qabul qilinmasin)?
- Domen va server tayyormi yoki ularni ham sozlash kerakmi?
