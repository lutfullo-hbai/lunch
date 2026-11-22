# API qo'llanma

Barcha yo'llar `API_PREFIX` (default `/api/v1`) bilan boshlanadi. To'liq va doim yangi sxema: `/docs` (production'dan tashqari).

## Xato formati

```json
{"error": {"code": "INVALID_CREDENTIALS", "message": "Email yoki parol noto'g'ri", "details": null}}
```

Frontend `code` bo'yicha ishlaydi, `message` foydalanuvchiga ko'rsatish uchun. Har bir `code` doim bitta HTTP status bilan keladi.

Noto'g'ri kiritilgan ma'lumot (jumladan body'dagi mavjud bo'lmagan `category_id`, juda katta `page`, `date_from > date_to`) `422 VALIDATION_ERROR` qaytaradi, `details` da maydon nomi bo'ladi:

```json
{"error": {"code": "VALIDATION_ERROR", "message": "Ma'lumotlar noto'g'ri", "details": [{"field": "category_id", "message": "Kategoriya topilmadi"}]}}
```

URL'dagi ID topilmasa `404 <ENTITY>_NOT_FOUND` qaytadi.

## So'rov hajmi

- **Oddiy so'rovlar:** `MAX_REQUEST_KB` gacha. Bu barcha JSON so'rovlari, login qilingan user'niki ham.
- **Rasm yuklash** (`PUT /admin/menu/{id}/image`): `MAX_UPLOAD_MB` gacha, faqat yaroqli access token bilan. Token muddati o'tgan yoki yaroqsiz bo'lsa, body o'qilmasdan `401 INVALID_TOKEN` qaytadi: tokenni yangilab, qayta yuboring.

Chegaradan katta so'rov `413 REQUEST_TOO_LARGE` bilan rad etiladi. Production'da nginx'ga ham `client_max_body_size` qo'ying.

## Auth

| Endpoint | Imzo | Javob |
| --- | --- | --- |
| `POST /auth/register` `{full_name, email, password}` | yo'q | 201, tokenlar |
| `POST /auth/login` `{email, password}` | yo'q | tokenlar |
| `POST /auth/refresh` `{refresh_token}` | yo'q | yangi tokenlar |
| `POST /auth/logout` | bor | 204 |
| `GET /me` | bor | user |

Tokenlar javobi: `access_token`, `refresh_token`, `expires_in` (soniya), `signing_key`, `user`.

- Refresh token har ishlatilganda almashadi, eskisini saqlab qo'ymang.
- Bir vaqtda faqat bitta refresh so'rovi yuboring: tablar orasida umumiy, "single-flight". Agar `REFRESH_TOKEN_ROTATED` kelsa, token boshqa so'rovda allaqachon yangilangan bo'ladi. Saqlangan eng oxirgi tokenni oling va so'rovni qaytaring.
- Eski token `REFRESH_REUSE_GRACE_SECONDS` dan keyin qayta ishlatilsa, o'g'irlangan deb hisoblanadi va userning barcha sessiyalari yopiladi.
- `signing_key` ham har login/refresh'da yangilanadi.
- Logout qilingan refresh token shunchaki `INVALID_REFRESH_TOKEN` oladi, boshqa sessiyalar yopilmaydi.
- **Rate limit:** login va register IP bo'yicha cheklanadi (`LOGIN_RATE_*`, `REGISTER_RATE_*`). Oshib ketsa `429 TOO_MANY_REQUESTS` va `Retry-After` header keladi. IP proxy ortida `--proxy-headers` orqali olinadi, shuning uchun proxy manzili `FORWARDED_ALLOW_IPS` da bo'lishi kerak (compose'da default `172.16.0.0/12`, Docker bridge tarmog'i). Aks holda hamma userlar proxy IP'si ostida bitta limitga tushadi. `*` qo'yilmaydi: unda `X-Forwarded-For` ni soxtalashtirib limitni aylanib o'tish mumkin.

## So'rov imzosi

Login qilingan har bir so'rovga quyidagi headerlar qo'shiladi:

```
Authorization: Bearer <access_token>
X-Timestamp:   <unix vaqt, soniya>
X-Nonce:       <har so'rovda yangi tasodifiy satr>
X-Signature:   hex(HMAC_SHA256(signing_key, string_to_sign))
```

```
string_to_sign = METHOD + "\n" + PATH + "\n" + X-Timestamp + "\n" + X-Nonce + "\n" + hex(SHA256(body))
```

- `PATH` prefix bilan birga, query bo'lsa `?` va query ham qo'shiladi: `/api/v1/admin/menu?page=2`.
- `PATH` va query aynan HTTP so'rovda yuboriladigan ko'rinishda imzolanadi (`%20` kabi kodlangan belgilar ham shundayligicha). Query'ni yuborishdan oldin yasang, keyin imzolang.
- Proxy (nginx) path yoki query'ni o'zgartirmasligi kerak: prefix qirqilmaydi va URL qayta kodlanmaydi. Aks holda imzo mos kelmaydi.
- Body bo'lmasa, bo'sh satrning SHA256 hashi olinadi.
- Fayl yuklashda yuboriladigan multipart baytlarning o'zi imzolanadi.
- Nonce uzunligi `NONCE_MAX_LENGTH` gacha bo'lishi kerak (tavsiya: 32 ta hex belgi).
- Vaqt farqi `SIGNATURE_MAX_SKEW_SECONDS` dan oshsa yoki nonce takrorlansa, so'rov 401 bilan rad etiladi.
- **Cheklov:** ishlatilgan nonce'lar server xotirasida saqlanadi, shuning uchun API bitta worker bilan ishlaydi (`scripts/start.sh`). Bir nechta worker yoki server kerak bo'lsa, `NonceStore` umumiy omborga (Redis) o'tkazilishi kerak.

Xato kodlari: `SIGNATURE_MISSING`, `SIGNATURE_EXPIRED`, `SIGNATURE_INVALID`, `SIGNATURE_REPLAYED`, `SESSION_REVOKED`.

## Menyu va buyurtmalar (user)

Hammasi login va imzo talab qiladi.

| Endpoint | Javob |
| --- | --- |
| `GET /categories` | Faol kategoriyalar: `[{id, name}]` |
| `GET /menu?category_id=` | Buyurtma qilish mumkin bo'lgan ovqatlar ro'yxati |
| `GET /menu/{id}` | Bitta ovqat. Sotuvda bo'lmasa 404 |
| `POST /orders` `{items: [{menu_item_id, quantity}], payment_method}` | 201, buyurtma |
| `GET /orders/me` | O'z buyurtmalari, sahifalangan, yangisi birinchi |
| `GET /orders/me/{id}` | Bitta buyurtma. Boshqaning buyurtmasi 404 |
| `POST /orders/me/{id}/cancel` | Bekor qilingan buyurtma |

Buyurtma javobi: `id`, `status`, `payment_method` (`cash` yoki `card`), `total_price`, `created_at`, `items` (`name`, `price`, `quantity`, `subtotal`), `can_cancel`.

- **Narx** bazadan olinadi, mijoz yuborgan narx e'tiborga olinmaydi. Bir xil ovqat ikki qatorda kelsa, bitta qatorga qo'shiladi.
- **Miqdor** kamida 1. Bitta buyurtmada ko'pi bilan `ORDER_MAX_LINES` xil ovqat.
- **Sotuvda yo'q ovqat:** `409 ITEMS_UNAVAILABLE`, `details.menu_item_ids` da qaysilari. Savatni yangilab, qayta yuboring.
- **Bekor qilish** faqat `new` holatida mumkin (`can_cancel`), aks holda `409 ORDER_NOT_CANCELLABLE`.
- **Guruhga xabar:** buyurtma yaratilgach (va user bekor qilganda) fonda `ORDERS_GROUP_CHAT_ID` guruhiga yuboriladi. Yuborilmasa `NOTIFY_RETRY_DELAYS` bo'yicha qayta uriniladi, keyin `notify_status = failed`. `BOT_TOKEN` berilmasa xabar yuborilmaydi, buyurtma baribir qabul qilinadi.

## Admin

Hammasi imzo talab qiladi va faqat `admin` roli uchun ochiq, boshqalar 403 oladi. Ro'yxatlar `?page=&size=` bilan sahifalanadi va `{items, total, page, size}` qaytaradi.

| Bo'lim | Endpointlar |
| --- | --- |
| Kategoriyalar | `GET`, `POST /admin/categories`; `PATCH`, `DELETE /admin/categories/{id}` |
| Menyu | `GET`, `POST /admin/menu`; `GET`, `PATCH`, `DELETE /admin/menu/{id}`; `PUT`, `DELETE /admin/menu/{id}/image` |
| Userlar | `GET /admin/users`; `GET /admin/users/{id}`; `GET /admin/users/{id}/orders`; `PATCH /admin/users/{id}/status` |
| Buyurtmalar | `GET /admin/orders`; `GET /admin/orders/{id}`; `PATCH /admin/orders/{id}/status`; `POST /admin/orders/{id}/notify` |

Filtrlar:

- **Menyu:** `category_id`, `search`, `is_available`.
- **Userlar:** `search` (email, ism, telefon), `role`, `is_active`.
- **Buyurtmalar:** `status`, `payment_method`, `user_id`, `notify_status`, `date_from`, `date_to`. Sanalar `YYYY-MM-DD` ko'rinishida va `TIMEZONE` bo'yicha hisoblanadi.

Qoidalar:

- **Kategoriya:** ichida ovqat bo'lsa o'chirilmaydi (409). Nomi katta-kichik harfdan qat'i nazar unique.
- **Ovqat:** o'chirilganda bazada qoladi (soft delete), eski buyurtmalar buzilmaydi.
- **Rasm:** faqat JPEG, PNG yoki WebP qabul qilinadi, hajmi `IMAGE_MAX_UPLOAD_MB` gacha. Server uni WebP'ga o'giradi, natijada `image_url` va `thumb_url` qaytadi.
- **Userni bloklash:** barcha sessiyalari darhol yopiladi. Adminni bloklab bo'lmaydi.
- **Buyurtma holati:** `new → accepted → ready → delivered` tartibida o'zgaradi, `delivered` gacha bekor qilish mumkin. Mumkin bo'lgan keyingi holatlar javobdagi `allowed_statuses` da keladi.
- **Guruhga qayta yuborish:** `POST /admin/orders/{id}/notify` (202) `failed` yoki `pending` buyurtmani fonda qayta yuboradi. Yuborilgan bo'lsa `409 ORDER_ALREADY_NOTIFIED`, bot sozlanmagan bo'lsa `503 TELEGRAM_NOT_CONFIGURED`.
