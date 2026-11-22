# Login, Dashboard va Admin panel — Reja

18.11.2026

## 1. Maqsad

Bu reja faqat login, admin dashboard va admin panelni qamraydi. Menyu va buyurtma sahifalari asosiy texnik rejada yozilgan.

## 2. Login qismi

User email va parol bilan kiradi va ikkita token oladi. Admin bo'lsa dashboardga, oddiy user menyuga o'tadi.

```
 Login sahifasi ──▶ POST /auth/login ──▶ Parol to'g'rimi? ── ha ──▶ Tokenlar beriladi
 (email + parol)    (bcrypt)                  │                   (access 1 kun, refresh 7 kun)
       ▲                                     yo'q                        │
       │                                      │                          ▼
       └──────── qayta urinish ───────────────┘                        Rol?
                                                                  user │      │ admin
                                                                       ▼      ▼
                                                            Menyu sahifasi   Admin dashboard
```

- **Register:** ism, email, parol. Parol bcrypt bilan hash qilinadi, email tasdiqlanmaydi.
- **Login:** email va parol.
- **Tokenlar:** access token (JWT) 1 kun, refresh token 7 kun. Refresh token har ishlatilganda yangisiga almashadi.
- **Logout:** refresh token bazada bekor qilinadi. Logout qilingan token bilan refresh rad etiladi, boshqa qurilmalar chiqib ketmaydi.
- **Imzo:** har bir so'rov HMAC-SHA256 bilan imzolanadi (`X-Timestamp`, `X-Nonce`, `X-Signature`). 60 soniyadan eski yoki takror so'rov rad etiladi. Imzo kaliti alohida `SIGNING_SECRET` dan hosil qilinadi.
- **Rate limit:** login va register IP bo'yicha cheklanadi, oshib ketsa `429`.
- **Super admin:** `.env` orqali bitta yaratiladi. Register orqali admin bo'lib bo'lmaydi.

## 3. Rollar

Ikki rol bor: **user** (register orqali) va **admin** (bitta, `.env` orqali). Barcha `/admin/*` endpointlari serverda `require_admin` bilan tekshiriladi, oddiy user `403` oladi.

## 4. Dashboard

Admin kirganda ochiladigan bosh sahifa. Ma'lumot `GET /admin/stats` dan keladi, davr filtri: bugun, 7 kun, 30 kun.

- **Kartalar:** buyurtmalar soni, tushum (naqd va karta alohida), yangi va jami userlar, kutilayotgan buyurtmalar.
- **Grafik:** kunlar bo'yicha buyurtmalar va tushum.
- **So'nggi buyurtmalar:** oxirgi 10 ta.

## 5. Admin panel

| Bo'lim | Nima qilinadi |
| --- | --- |
| Menyu | Ovqat qo'shish, tahrirlash, o'chirish: nom, narx, porsiya, kategoriya, rasm. "Sotuvda" belgisi bilan vaqtincha yashirish |
| Kategoriyalar | Qo'shish, tahrirlash, o'chirish, tartibi |
| Userlar | Ro'yxat, qidiruv, userning buyurtmalari, bloklash |
| Buyurtmalar | Ro'yxat, filtr (holat, to'lov turi, sana), tafsilot, holatni o'zgartirish |

## 6. Ma'lumotlar bazasi

PostgreSQL, 6 ta jadval. Sxemadagi har bir o'zgarish Alembic migratsiyasi bilan versiyalanadi.

| Jadval | Asosiy ustunlar |
| --- | --- |
| users | id, full_name, email (katta-kichik harfsiz unique), phone, password_hash, role (user / admin), is_active, last_login_at, created_at, updated_at |
| refresh_tokens | id, user_id → users, jti (unique), token_hash (unique), expires_at, revoked_at, replaced_by_jti, created_at |
| categories | id, name (katta-kichik harfsiz unique), sort_order, is_active, created_at, updated_at |
| menu_items | id, category_id → categories (o'chirilsa NULL), name, description, price, portion, image_path, is_available, deleted_at, created_at, updated_at |
| orders | id, user_id → users, total_price, payment_method (cash / card), status, notify_status, created_at, updated_at |
| order_items | id, order_id → orders, menu_item_id → menu_items, name_snapshot, price_snapshot, quantity |

Parol faqat hash ko'rinishida, refresh token ham faqat hash ko'rinishida saqlanadi. `order_items.name_snapshot` va `price_snapshot` buyurtma paytidagi nom va narxni saqlaydi, shuning uchun menyu o'zgarsa eski buyurtmalar o'zgarmaydi. Ovqat o'chirilganda qator qoladi (`deleted_at` to'ldiriladi), rasmi esa o'chiriladi. `refresh_tokens.replaced_by_jti` token almashtirilganini (rotation) logout'dan ajratadi.

## 7. API endpointlar

Barcha yo'llar `/api/v1` bilan boshlanadi. `/admin/*` faqat admin uchun.

| Guruh | Endpointlar |
| --- | --- |
| Auth | `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `GET /me` |
| Dashboard | `GET /admin/stats` |
| Menyu | `/admin/menu` (GET, POST, PATCH, DELETE), `PUT/DELETE /admin/menu/{id}/image` |
| Kategoriyalar | `/admin/categories` (GET, POST, PATCH, DELETE) |
| Userlar | `GET /admin/users`, `GET /admin/users/{id}`, `GET /admin/users/{id}/orders`, `PATCH /admin/users/{id}/status` |
| Buyurtmalar | `GET /admin/orders`, `GET /admin/orders/{id}`, `PATCH /admin/orders/{id}/status` |

## 8. Sahifalar

- `login.html`, `register.html` — hamma uchun.
- `admin/dashboard.html`, `menu.html`, `categories.html`, `users.html`, `orders.html` — faqat admin uchun.

Barcha so'rovlar `js/api.js` orqali ketadi: u token va imzoni qo'shadi, token eskirsa avtomatik yangilaydi.

## 9. Ish bosqichlari

| Bosqich | Natija |
| --- | --- |
| 1. Auth backend | Register, login, tokenlar va imzo ishlaydi |
| 2. Login sahifalari | User ro'yxatdan o'tib, tizimga kira oladi |
| 3. Admin panel | Menyu, kategoriya, user va buyurtmalar boshqariladi |
| 4. Dashboard | Statistika va grafik ko'rinadi |
