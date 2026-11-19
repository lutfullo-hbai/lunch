"""So'rov imzosi (HMAC-SHA256).

Imzolanadigan matn:
    METHOD \\n PATH[?QUERY] \\n X-Timestamp \\n X-Nonce \\n sha256(body)
"""

import hashlib
import hmac
import time
from collections import deque

TIMESTAMP_HEADER = "X-Timestamp"
NONCE_HEADER = "X-Nonce"
SIGNATURE_HEADER = "X-Signature"


def canonical_path(raw_path: bytes, query_string: bytes) -> str:
    """Imzolanadigan yo'l: mijoz yuborgan baytlar, dekodlanmagan holda."""
    path = raw_path.decode("latin-1")
    if query_string:
        path = f"{path}?{query_string.decode('latin-1')}"
    return path


def build_string_to_sign(method: str, path: str, timestamp: str, nonce: str, body: bytes) -> str:
    body_hash = hashlib.sha256(body).hexdigest()
    return "\n".join([method.upper(), path, timestamp, nonce, body_hash])


def compute_signature(key: str, string_to_sign: str) -> str:
    return hmac.new(key.encode(), string_to_sign.encode(), hashlib.sha256).hexdigest()


def is_timestamp_fresh(timestamp: str, max_skew_seconds: int) -> bool:
    try:
        return abs(time.time() - int(timestamp)) <= max_skew_seconds
    except ValueError:
        return False


class NonceStore:
    """Ishlatilgan nonce'larni eslab qoladi, takroriy so'rovni (replay) rad etadi.

    Xotirada saqlanadi, ya'ni bitta jarayon (process) uchun ishlaydi. Bir nechta
    worker ishlatilsa, uni Redis kabi umumiy omborga almashtirish kerak.
    """

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._seen: set[str] = set()
        # TTL hamma uchun bir xil, shuning uchun navbat muddat tartibida turadi
        # va eskilarini faqat boshidan o'chirish yetarli.
        self._queue: deque[tuple[float, str]] = deque()

    def _evict_expired(self, now: float) -> None:
        while self._queue and self._queue[0][0] <= now:
            _, nonce = self._queue.popleft()
            self._seen.discard(nonce)

    def use(self, nonce: str) -> bool:
        """Nonce yangi bo'lsa True qaytaradi va uni band qiladi."""
        now = time.monotonic()
        self._evict_expired(now)
        if nonce in self._seen:
            return False
        self._seen.add(nonce)
        self._queue.append((now + self._ttl, nonce))
        return True
