"""So'rov imzosi (HMAC-SHA256).

Imzolanadigan matn:
    METHOD \\n PATH[?QUERY] \\n X-Timestamp \\n X-Nonce \\n sha256(body)
"""

import hashlib
import hmac
import time

TIMESTAMP_HEADER = "X-Timestamp"
NONCE_HEADER = "X-Nonce"
SIGNATURE_HEADER = "X-Signature"


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
        self._seen: dict[str, float] = {}

    def use(self, nonce: str) -> bool:
        """Nonce yangi bo'lsa True qaytaradi va uni band qiladi."""
        now = time.monotonic()
        self._seen = {n: exp for n, exp in self._seen.items() if exp > now}
        if nonce in self._seen:
            return False
        self._seen[nonce] = now + self._ttl
        return True
