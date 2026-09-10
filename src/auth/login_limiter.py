"""In-process sliding-window limiter for failed login attempts.

Single uvicorn worker (MVP). Keyed by client IP + normalized email so
unknown addresses are not a free path and existence is not leaked.
"""

from __future__ import annotations

import time

from src.core.config import get_settings


class LoginRateLimiter:
    """Count failed logins per (ip, email) inside a wall-clock window."""

    def __init__(self) -> None:
        self._failures: dict[tuple[str, str], list[float]] = {}

    def reset(self) -> None:
        """Drop all keys (tests)."""
        self._failures.clear()

    def _key(self, ip: str, email: str) -> tuple[str, str]:
        return ((ip or "unknown").strip(), (email or "").strip().lower())

    def _limits(self) -> tuple[int, int]:
        settings = get_settings()
        return settings.login_max_attempts, settings.login_window_seconds

    def _prune(self, key: tuple[str, str], now: float, window: int) -> list[float]:
        cutoff = now - window
        kept = [stamp for stamp in self._failures.get(key, []) if stamp > cutoff]
        if kept:
            self._failures[key] = kept
        else:
            self._failures.pop(key, None)
        return kept

    def blocked(self, ip: str, email: str, *, now: float | None = None) -> int | None:
        """Return Retry-After seconds when the cap is already reached."""
        _max_attempts, window = self._limits()
        stamp = time.monotonic() if now is None else now
        kept = self._prune(self._key(ip, email), stamp, window)
        if len(kept) < _max_attempts:
            return None
        retry = int(kept[0] + window - stamp) + 1
        return max(retry, 1)

    def record_failure(self, ip: str, email: str, *, now: float | None = None) -> None:
        """Record one failed attempt for this key."""
        _, window = self._limits()
        stamp = time.monotonic() if now is None else now
        key = self._key(ip, email)
        kept = self._prune(key, stamp, window)
        kept.append(stamp)
        self._failures[key] = kept

    def clear(self, ip: str, email: str) -> None:
        """Successful login resets this key."""
        self._failures.pop(self._key(ip, email), None)


login_limiter = LoginRateLimiter()
