"""Login va register uchun oddiy rate limit (IP bo'yicha, qat'iy vaqt oynasi).

NonceStore kabi xotirada saqlanadi, ya'ni bitta jarayon uchun ishlaydi. Bir nechta
worker ishlatilsa, umumiy omborga (Redis) o'tkazish kerak.
"""

import math
import time
from dataclasses import dataclass


@dataclass
class _Window:
    started_at: float
    seconds: int  # har kalitning o'z oynasi: login va register oynalari har xil
    count: int

    def expired(self, now: float) -> bool:
        return now - self.started_at >= self.seconds


class RateLimiter:
    def __init__(self) -> None:
        self._windows: dict[str, _Window] = {}
        self._last_sweep = time.monotonic()

    def _sweep(self, now: float, interval: int) -> None:
        """Tugagan oynalarni o'chiradi, xotira cheksiz o'smasin.

        Har bir oyna o'z muddati bo'yicha tekshiriladi: qisqa oynali action (login)
        uzun oynali action (register) hisobini o'chirib yubormasin."""
        if now - self._last_sweep < interval:
            return
        self._last_sweep = now
        expired = [key for key, window in self._windows.items() if window.expired(now)]
        for key in expired:
            del self._windows[key]

    def hit(self, key: str, limit: int, window_seconds: int) -> int | None:
        """Urinishni hisoblaydi. Limitdan oshgan bo'lsa, qancha soniya kutish kerakligini
        qaytaradi, aks holda None."""
        now = time.monotonic()
        self._sweep(now, window_seconds)
        window = self._windows.get(key)
        if window is None or window.expired(now):
            self._windows[key] = _Window(started_at=now, seconds=window_seconds, count=1)
            return None
        if window.count >= limit:
            return max(1, math.ceil(window.started_at + window_seconds - now))
        window.count += 1
        return None
