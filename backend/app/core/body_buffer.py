"""So'rov tanasi (body) hajmini cheklaydigan va uni oldindan o'qib saqlaydigan ASGI middleware.

- Hamma so'rovlar kichik JSON: ularga MAX_REQUEST_KB chegarasi qo'yiladi.
- Katta chegara (MAX_UPLOAD_MB) faqat fayl yuklash yo'llariga (`upload_routes`) va faqat
  yaroqli access token bilan beriladi. Tokenning JWT imzosi va muddati shu yerda
  tekshiriladi (bazaga murojaat yo'q). Token bor-u yaroqsiz bo'lsa, body o'qilmasdan
  401 INVALID_TOKEN qaytadi: mijoz "fayl katta" deb emas, "token eskirgan" deb
  tushunib, tokenni yangilaydi.
- Chegara body o'qilishidan oldin tekshiriladi, katta so'rov oxirigacha o'qilmaydi.
- Body `scope["state"]` ga saqlanadi: FastAPI multipart'ni dependency'lardan oldin
  o'qib yuboradi, imzo tekshiruvi esa aynan shu baytlarni ishlatadi.
"""

import json
import re
from collections.abc import Iterable

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import AppError, error_body, unauthorized
from app.core.security import decode_access_token

RAW_BODY_STATE_KEY = "raw_body"
_BEARER_PREFIX = b"bearer "


def _bearer_token(headers: dict[bytes, bytes]) -> str | None:
    authorization = headers.get(b"authorization", b"")
    if not authorization.lower().startswith(_BEARER_PREFIX):
        return None
    return authorization[len(_BEARER_PREFIX) :].decode("latin-1").strip()


class BodyLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        max_bytes: int,
        upload_max_bytes: int,
        upload_routes: Iterable[tuple[str, re.Pattern[str]]],
    ) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.upload_max_bytes = upload_max_bytes
        self.upload_routes = list(upload_routes)

    def _is_upload(self, scope: Scope) -> bool:
        return any(
            scope["method"] == method and pattern.fullmatch(scope["path"])
            for method, pattern in self.upload_routes
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope["headers"])
        limit = self.max_bytes
        if self._is_upload(scope):
            token = _bearer_token(headers)
            if token is not None:
                if decode_access_token(token) is None:
                    await _send_error(
                        send,
                        unauthorized("INVALID_TOKEN", "Access token yaroqsiz yoki muddati o'tgan"),
                    )
                    return
                limit = self.upload_max_bytes

        # Mijoz hajmni oldindan aytgan bo'lsa, birorta bayt o'qimasdan rad etamiz.
        declared = headers.get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > limit:
            await _send_error(send, _too_large())
            return

        chunks: list[bytes] = []
        size = 0
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > limit:  # Content-Length yo'q yoki yolg'on bo'lsa
                await _send_error(send, _too_large())
                return
            chunks.append(chunk)
            more_body = message.get("more_body", False)

        body = b"".join(chunks)
        scope.setdefault("state", {})[RAW_BODY_STATE_KEY] = body

        sent = False

        async def replay() -> Message:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


def _too_large() -> AppError:
    return AppError(413, "REQUEST_TOO_LARGE", "So'rov hajmi juda katta")


async def _send_error(send: Send, error: AppError) -> None:
    """Javob ilovaga yetmasdan yuboriladi, shuning uchun ulanish yopiladi
    (o'qilmagan body keyingi so'rovga aralashmasin)."""
    content = json.dumps(
        error_body(error.code, error.message, error.details), ensure_ascii=False
    ).encode()
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(content)).encode()),
        (b"connection", b"close"),
        *((k.lower().encode(), v.encode()) for k, v in (error.headers or {}).items()),
    ]
    await send({"type": "http.response.start", "status": error.status_code, "headers": headers})
    await send({"type": "http.response.body", "body": content})
