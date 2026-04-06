"""Date utility helpers for the ODIN transform engine."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional, Tuple


def parse_iso_date(s: str) -> Optional[date]:
    """Parse an ISO 8601 date string (YYYY-MM-DD) to a date object."""
    if not s or len(s) < 10:
        return None
    try:
        # Take only the date portion
        ds = s[:10]
        parts = ds.split("-")
        if len(parts) != 3:
            return None
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        if not is_valid_date(y, m, d):
            return None
        return date(y, m, d)
    except (ValueError, IndexError):
        return None


def parse_iso_timestamp(s: str) -> Optional[datetime]:
    """Parse an ISO 8601 timestamp string to a datetime object (UTC).

    Supports:
      - YYYY-MM-DDTHH:MM:SS
      - YYYY-MM-DDTHH:MM:SSZ
      - YYYY-MM-DDTHH:MM:SS.sssZ
      - YYYY-MM-DD (date only -> midnight)
      - HH:MM:SS (time only -> today)
    """
    if not s:
        return None
    s = s.strip()
    try:
        # Try ISO timestamp
        if "T" in s or "t" in s:
            cleaned = s.replace("Z", "+00:00").replace("z", "+00:00")
            # Handle various formats
            if "+" in cleaned[10:] or cleaned.endswith("+00:00"):
                dt = datetime.fromisoformat(cleaned)
            else:
                dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        # Date only
        if len(s) >= 10 and s[4] == "-":
            d = parse_iso_date(s)
            if d:
                return datetime(d.year, d.month, d.day, 0, 0, 0)
        # Time only
        if ":" in s and len(s) <= 12:
            parts = s.split(":")
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            sec_parts = parts[2].split(".") if len(parts) > 2 else ["0"]
            sec = int(sec_parts[0])
            micro = 0
            if len(sec_parts) > 1:
                frac = sec_parts[1][:6].ljust(6, "0")
                micro = int(frac)
            today = date.today()
            return datetime(today.year, today.month, today.day, h, m, sec, micro)
        return None
    except (ValueError, IndexError, OverflowError):
        return None


def format_iso_date(d: date) -> str:
    """Format a date as ISO 8601 (YYYY-MM-DD)."""
    return f"{d.year:04d}-{d.month:02d}-{d.day:02d}"


def format_iso_timestamp(dt: datetime) -> str:
    """Format a datetime as ISO 8601 timestamp with Z suffix."""
    return (
        f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}"
        f"T{dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}"
        f".{dt.microsecond // 1000:03d}Z"
    )


def week_of_year(d: date) -> int:
    """ISO 8601 week number.

    Returns 1-53. Dec 31 can be week 53 in certain years.
    Uses ISO week date system (Monday start, 4-day rule).
    """
    return d.isocalendar()[1]


def is_leap_year(year: int) -> bool:
    """Check if a year is a leap year."""
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


def days_in_month(year: int, month: int) -> int:
    """Return the number of days in a given month."""
    if month in (4, 6, 9, 11):
        return 30
    if month == 2:
        return 29 if is_leap_year(year) else 28
    return 31


def is_valid_date(year: int, month: int, day: int) -> bool:
    """Validate a date."""
    if month < 1 or month > 12:
        return False
    if day < 1 or day > days_in_month(year, month):
        return False
    return True


def today_utc() -> str:
    """Current UTC date as YYYY-MM-DD."""
    d = datetime.now(timezone.utc).date()
    return format_iso_date(d)


def now_utc() -> str:
    """Current UTC timestamp as ISO 8601."""
    dt = datetime.now(timezone.utc).replace(tzinfo=None)
    return format_iso_timestamp(dt)


def add_days(date_str: str, days: int) -> Optional[str]:
    """Add days to a date string, return YYYY-MM-DD."""
    d = parse_iso_date(date_str)
    if d is None:
        return None
    result = d + timedelta(days=days)
    return format_iso_date(result)


def add_months(date_str: str, months: int) -> Optional[str]:
    """Add months to a date string, return YYYY-MM-DD."""
    d = parse_iso_date(date_str)
    if d is None:
        return None
    total_months = d.year * 12 + (d.month - 1) + months
    new_year = total_months // 12
    new_month = total_months % 12 + 1
    new_day = min(d.day, days_in_month(new_year, new_month))
    return format_iso_date(date(new_year, new_month, new_day))


def date_diff_days(date1_str: str, date2_str: str) -> Optional[int]:
    """Return date2 - date1 in days."""
    d1 = parse_iso_date(date1_str)
    d2 = parse_iso_date(date2_str)
    if d1 is None or d2 is None:
        return None
    return (d2 - d1).days
