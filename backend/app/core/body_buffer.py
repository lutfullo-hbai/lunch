"""Imzolangan so'rov tanasini (body) oldindan o'qib saqlaydigan ASGI middleware.

FastAPI multipart (fayl) so'rovni dependency'lardan oldin o'qib yuboradi, shundan keyin
imzo tekshiruvi tanani qayta o'qiy olmaydi. Middleware tanani bir marta o'qiydi,
`scope["state"]` ga saqlaydi va ilovaga qayta uzatadi. Hajm chegarasi ham shu yerda.
"""

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_body
from app.core.signature import SIGNATURE_HEADER

RAW_BODY_STATE_KEY = "raw_body"
_SIGNATURE_HEADER = SIGNATURE_HEADER.lower().encode()


class SignedBodyBufferMiddleware:
    def __init__(self, app: ASGIApp, max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not any(
            name == _SIGNATURE_HEADER for name, _ in scope["headers"]
        ):
            await self.app(scope, receive, send)
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
            if size > self.max_body_bytes:
                await self._reject_too_large(send)
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

    @staticmethod
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
                ],
            }
        )
        await send({"type": "http.response.body", "body": content})
