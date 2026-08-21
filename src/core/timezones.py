"""IANA timezones for user-local wall clocks."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def parse_iana_timezone(value: str) -> str:
    """Return a canonical IANA name or raise ``ValueError``."""
    name = (value or "").strip()
    if not name or len(name) > 64:
        raise ValueError("Invalid timezone")
    if any(ch.isspace() or ch in "\\;" for ch in name):
        raise ValueError("Invalid timezone")
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, KeyError) as exc:
        raise ValueError("Unknown IANA timezone") from exc
    return name


def zoneinfo_or_utc(name: str | None) -> ZoneInfo:
    """Resolve an IANA name; unknown or empty falls back to UTC."""
    if not name:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, KeyError):
        return ZoneInfo("UTC")


def to_utc(dt: datetime) -> datetime:
    """Convert a datetime to UTC (naive values are treated as UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)
