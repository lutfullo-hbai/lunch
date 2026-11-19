"""So'rov tanasi (body) hajmini cheklaydigan va uni oldindan o'qib saqlaydigan ASGI middleware.

- Har bir so'rovga chegara qo'yiladi: imzolanganiga MAX_REQUEST_MB (rasm yuklash),
  imzosiziga (login, register) MAX_UNSIGNED_REQUEST_KB. Chegara ilova body'ni
  o'qishidan oldin tekshiriladi, katta so'rov oxirigacha o'qilmaydi.
- Body `scope["state"]` ga saqlanadi: FastAPI multipart'ni dependency'lardan oldin
  o'qib yuboradi, imzo tekshiruvi esa aynan shu baytlarni ishlatadi.
"""

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_body
from app.core.signature import SIGNATURE_HEADER

RAW_BODY_STATE_KEY = "raw_body"
_SIGNATURE_HEADER = SIGNATURE_HEADER.lower().encode()


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp, signed_max_bytes: int, unsigned_max_bytes: int) -> None:
        self.app = app
        self.signed_max_bytes = signed_max_bytes
        self.unsigned_max_bytes = unsigned_max_bytes

    def _limit(self, headers: dict[bytes, bytes]) -> int:
        return self.signed_max_bytes if _SIGNATURE_HEADER in headers else self.unsigned_max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope["headers"])
        limit = self._limit(headers)

        # Mijoz hajmni oldindan aytgan bo'lsa, birorta bayt o'qimasdan rad etamiz.
        declared = headers.get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > limit:
            await _reject_too_large(send)
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
                await _reject_too_large(send)
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


async def _reject_too_large(send: Send) -> None:
    content = json.dumps(
        error_body("REQUEST_TOO_LARGE", "So'rov hajmi juda katta"), ensure_ascii=False
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(content)).encode()),
                (b"connection", b"close"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": content})
