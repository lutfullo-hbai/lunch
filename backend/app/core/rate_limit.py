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
    count: int


class RateLimiter:
    def __init__(self) -> None:
        self._windows: dict[str, _Window] = {}
        self._last_sweep = time.monotonic()

    def _sweep(self, now: float, window_seconds: int) -> None:
        """Tugagan oynalarni o'chiradi, xotira cheksiz o'smasin."""
        if now - self._last_sweep < window_seconds:
            return
        self._last_sweep = now
        expired = [k for k, w in self._windows.items() if now - w.started_at >= window_seconds]
        for key in expired:
            del self._windows[key]

    def hit(self, key: str, limit: int, window_seconds: int) -> int | None:
        """Urinishni hisoblaydi. Limitdan oshgan bo'lsa, qancha soniya kutish kerakligini
        qaytaradi, aks holda None."""
        now = time.monotonic()
        self._sweep(now, window_seconds)
        window = self._windows.get(key)
        if window is None or now - window.started_at >= window_seconds:
            self._windows[key] = _Window(started_at=now, count=1)
            return None
        if window.count >= limit:
            return max(1, math.ceil(window.started_at + window_seconds - now))
        window.count += 1
        return None
