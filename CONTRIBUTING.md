# Jamoada ishlash qoidalari

## Branchlar

| Branch | Vazifasi | Qayerdan yangilanadi |
| --- | --- | --- |
| `main` | Production. Faqat ishlayotgan, sinalgan kod | `stage` dan PR orqali |
| `stage` | Production oldidan sinov (staging server) | `dev` dan PR orqali |
| `dev` | Asosiy ish branchi, hamma o'zgarishlar shu yerga yig'iladi | ish branchlaridan PR orqali |

`main`, `stage` va `dev` ga to'g'ridan-to'g'ri push qilinmaydi, faqat Pull Request orqali.

### Ish branchlari

Har doim `dev` dan ochiladi va `dev` ga PR qilinadi:

| Prefiks | Qachon | Misol |
| --- | --- | --- |
| `feature/` | Yangi funksiya | `feature/auth` |
| `fix/` | Xatoni tuzatish | `fix/refresh-token-expiry` |
| `chore/` | Sozlama, kutubxona, CI | `chore/ci-workflow` |
| `docs/` | Faqat hujjat | `docs/api-readme` |
| `hotfix/` | Production'dagi shoshilinch xato (`main` dan ochiladi) | `hotfix/order-crash` |

Branch nomi kichik harflarda, so'zlar `-` bilan ajratiladi.

## Commit xabarlari

[Conventional Commits](https://www.conventionalcommits.org/) formati:

```
<tur>(<qism>): <qisqa tavsif>
```

Turlar: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`.

```
feat(auth): register va login endpointlari
fix(orders): bekor qilingan buyurtma tushumga qo'shilmasin
test(menu): rasm yuklash testlari
```

Bitta commit = bitta mantiqiy o'zgarish.

## Pull Request

1. `dev` dan branch oching, ishlang, commit qiling.
2. Push qilishdan oldin `dev` ni o'zingizga torting: `git pull --rebase origin dev`.
3. PR oching (`dev` ga), shablonni to'ldiring.
4. CI (lint + testlar) yashil bo'lishi va kamida bitta review kerak.
5. Merge: **Squash and merge**, branch o'chiriladi.

Reliz: `dev` → `stage` PR (sinov serverida tekshiriladi), keyin `stage` → `main` PR.

## Kod qoidalari

- Sozlamalar, kalitlar, URL va limitlar kodga yozilmaydi: hammasi `.env` orqali `Settings` ga keladi. Yangi o'zgaruvchi qo'shilsa, `.env.example` ham yangilanadi.
- Router faqat HTTP bilan ishlaydi, biznes logika `services/` da.
- Har bir yangi endpoint yoki xato tuzatish uchun test yoziladi.
- Bazadagi har bir o'zgarish alohida Alembic migratsiyasi bilan.
- Sirlar (`.env`, tokenlar) hech qachon commit qilinmaydi.
