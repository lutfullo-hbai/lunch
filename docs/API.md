# API qo'llanma

Barcha yo'llar `API_PREFIX` (default `/api/v1`) bilan boshlanadi. To'liq va doim yangi sxema: `/docs` (production'dan tashqari).

## Xato formati

```json
{"error": {"code": "INVALID_CREDENTIALS", "message": "Email yoki parol noto'g'ri", "details": null}}
```

Frontend `code` bo'yicha ishlaydi, `message` foydalanuvchiga ko'rsatish uchun.

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

## Admin

Hammasi imzo talab qiladi va faqat `admin` roli uchun ochiq, boshqalar 403 oladi. Ro'yxatlar `?page=&size=` bilan sahifalanadi va `{items, total, page, size}` qaytaradi.

| Bo'lim | Endpointlar |
| --- | --- |
| Kategoriyalar | `GET`, `POST /admin/categories`; `PATCH`, `DELETE /admin/categories/{id}` |
| Menyu | `GET`, `POST /admin/menu`; `GET`, `PATCH`, `DELETE /admin/menu/{id}`; `PUT`, `DELETE /admin/menu/{id}/image` |
| Userlar | `GET /admin/users`; `GET /admin/users/{id}`; `GET /admin/users/{id}/orders`; `PATCH /admin/users/{id}/status` |
| Buyurtmalar | `GET /admin/orders`; `GET /admin/orders/{id}`; `PATCH /admin/orders/{id}/status` |

Filtrlar:

- **Menyu:** `category_id`, `search`, `is_available`.
- **Userlar:** `search` (email, ism, telefon), `role`, `is_active`.
- **Buyurtmalar:** `status`, `payment_method`, `user_id`, `date_from`, `date_to`. Sanalar `YYYY-MM-DD` ko'rinishida va `TIMEZONE` bo'yicha hisoblanadi.

Qoidalar:

- **Kategoriya:** ichida ovqat bo'lsa o'chirilmaydi (409). Nomi katta-kichik harfdan qat'i nazar unique.
- **Ovqat:** o'chirilganda bazada qoladi (soft delete), eski buyurtmalar buzilmaydi.
- **Rasm:** faqat JPEG, PNG yoki WebP qabul qilinadi, hajmi `IMAGE_MAX_UPLOAD_MB` gacha. Server uni WebP'ga o'giradi, natijada `image_url` va `thumb_url` qaytadi.
- **Userni bloklash:** barcha sessiyalari darhol yopiladi. Adminni bloklab bo'lmaydi.
- **Buyurtma holati:** `new → accepted → ready → delivered` tartibida o'zgaradi, `delivered` gacha bekor qilish mumkin. Mumkin bo'lgan keyingi holatlar javobdagi `allowed_statuses` da keladi.
