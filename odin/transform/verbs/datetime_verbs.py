"""DateTime verbs for the ODIN transform engine."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from odin.transform.dyn_value import DynValue, DynType
from odin.transform.verbs.helpers import coerce_num, coerce_str
from odin.utils.date_utils import (
    parse_iso_date, parse_iso_timestamp, format_iso_date, format_iso_timestamp,
    today_utc, now_utc, add_days, add_months, date_diff_days,
    is_leap_year, days_in_month, week_of_year,
)


def _parse_dt(s: str) -> Optional[datetime]:
    """Parse a date/time string to datetime (matches Java parseDt)."""
    return parse_iso_timestamp(s)


def _parse_date_val(v: DynValue) -> Optional[datetime]:
    """Extract datetime from a DynValue."""
    if v.is_null():
        return None
    s = coerce_str(v)
    if not s:
        return None
    return _parse_dt(s)


def _apply_date_format(dt: datetime, pattern: str) -> str:
    """Apply simple date format pattern (YYYY, MM, DD, HH, hh, mm, ss, SSS, A)."""
    result = pattern
    result = result.replace("YYYY", f"{dt.year:04d}")
    result = result.replace("MM", f"{dt.month:02d}")
    result = result.replace("DD", f"{dt.day:02d}")
    result = result.replace("HH", f"{dt.hour:02d}")
    # 12-hour format
    h12 = dt.hour % 12
    if h12 == 0:
        h12 = 12
    result = result.replace("hh", f"{h12:02d}")
    result = result.replace("mm", f"{dt.minute:02d}")
    result = result.replace("ss", f"{dt.second:02d}")
    result = result.replace("SSS", f"{dt.microsecond // 1000:03d}")
    result = result.replace("A", "AM" if dt.hour < 12 else "PM")
    return result


def _parse_with_pattern(s: str, pattern: str) -> Optional[datetime]:
    """Parse a date/time string using a simple pattern."""
    # Build a mapping of positions from the pattern
    try:
        year = month = day = 0
        hour = minute = second = 0

        # Find positions of tokens
        yp = pattern.find("YYYY")
        mp = pattern.find("MM")
        dp = pattern.find("DD")
        hp = pattern.find("HH")
        minp = pattern.find("mm")
        sp = pattern.find("ss")

        if yp >= 0 and yp + 4 <= len(s):
            year = int(s[yp:yp + 4])
        if mp >= 0 and mp + 2 <= len(s):
            month = int(s[mp:mp + 2])
        if dp >= 0 and dp + 2 <= len(s):
            day = int(s[dp:dp + 2])
        if hp >= 0 and hp + 2 <= len(s):
            hour = int(s[hp:hp + 2])
        if minp >= 0 and minp + 2 <= len(s):
            minute = int(s[minp:minp + 2])
        if sp >= 0 and sp + 2 <= len(s):
            second = int(s[sp:sp + 2])

        if year == 0 and month == 0 and day == 0:
            return None
        if month == 0:
            month = 1
        if day == 0:
            day = 1
        return datetime(year, month, day, hour, minute, second)
    except (ValueError, IndexError):
        return None


# ── Verb implementations ────────────────────────────────────────────

def verb_today(args: List[DynValue], ctx: object) -> DynValue:
    return DynValue.of_string(today_utc())


def verb_now(args: List[DynValue], ctx: object) -> DynValue:
    return DynValue.of_string(now_utc())


def verb_format_date(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    dt = _parse_date_val(args[0])
    if dt is None:
        return DynValue.of_null()
    pattern = coerce_str(args[1])
    return DynValue.of_string(_apply_date_format(dt, pattern))


def verb_parse_date(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    s = coerce_str(args[0])
    if not s:
        return DynValue.of_null()
    pattern = coerce_str(args[1]) if len(args) >= 2 else "YYYY-MM-DD"
    dt = _parse_with_pattern(s, pattern)
    if dt is None:
        dt = _parse_dt(s)
    if dt is None:
        return DynValue.of_null()
    return DynValue.of_string(format_iso_date(dt.date() if isinstance(dt, datetime) else dt))


def verb_format_time(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    dt = _parse_date_val(args[0])
    if dt is None:
        return DynValue.of_null()
    if len(args) >= 2:
        pattern = coerce_str(args[1])
        return DynValue.of_string(_apply_date_format(dt, pattern))
    return DynValue.of_string(f"{dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}")


def verb_format_timestamp(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    dt = _parse_date_val(args[0])
    if dt is None:
        return DynValue.of_null()
    if len(args) >= 2:
        pattern = coerce_str(args[1])
        return DynValue.of_string(_apply_date_format(dt, pattern))
    return DynValue.of_string(format_iso_timestamp(dt))


def verb_parse_timestamp(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    s = coerce_str(args[0])
    if not s:
        return DynValue.of_null()
    dt = _parse_dt(s)
    if dt is None:
        return DynValue.of_null()
    return DynValue.of_string(format_iso_timestamp(dt))


def verb_add_days(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    s = coerce_str(args[0])
    n = coerce_num(args[1])
    if not s or n is None:
        return DynValue.of_null()
    result = add_days(s, int(n))
    return DynValue.of_string(result) if result else DynValue.of_null()


def verb_add_months(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    s = coerce_str(args[0])
    n = coerce_num(args[1])
    if not s or n is None:
        return DynValue.of_null()
    result = add_months(s, int(n))
    return DynValue.of_string(result) if result else DynValue.of_null()


def verb_add_years(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    dt = _parse_date_val(args[0])
    n = coerce_num(args[1])
    if dt is None or n is None:
        return DynValue.of_null()
    try:
        new_year = dt.year + int(n)
        new_day = min(dt.day, days_in_month(new_year, dt.month))
        result = datetime(new_year, dt.month, new_day, dt.hour, dt.minute, dt.second, dt.microsecond)
        return DynValue.of_string(format_iso_date(result.date()))
    except (ValueError, OverflowError):
        return DynValue.of_null()


def verb_date_diff(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    s1 = coerce_str(args[0])
    s2 = coerce_str(args[1])
    if not s1 or not s2:
        return DynValue.of_null()
    # Check for optional unit argument (days, months, years)
    unit = "days"
    if len(args) >= 3:
        u = coerce_str(args[2])
        if u:
            unit = u.lower()
    if unit in ("months", "month"):
        dt1 = _parse_date_val(args[0])
        dt2 = _parse_date_val(args[1])
        if dt1 is None or dt2 is None:
            return DynValue.of_null()
        months = (dt2.year - dt1.year) * 12 + (dt2.month - dt1.month)
        return DynValue.of_integer(months)
    elif unit in ("years", "year"):
        dt1 = _parse_date_val(args[0])
        dt2 = _parse_date_val(args[1])
        if dt1 is None or dt2 is None:
            return DynValue.of_null()
        years = dt2.year - dt1.year
        # Adjust if the anniversary hasn't occurred yet
        if dt2.month < dt1.month or (dt2.month == dt1.month and dt2.day < dt1.day):
            years -= 1
        return DynValue.of_integer(years)
    elif unit in ("days", "day"):
        result = date_diff_days(s1, s2)
        if result is None:
            return DynValue.of_null()
        return DynValue.of_integer(result)
    else:
        # T011 INCOMPATIBLE_CONVERSION: unknown unit for dateDiff.
        # Verbs currently cannot push errors onto the context, so we
        # return null.  When VerbContext gains an errors list this
        # should emit:
        #   incompatible_conversion_error(
        #       "dateDiff",
        #       f"unknown unit '{unit}' (expected 'days', 'months', or 'years')",
        #   )
        return DynValue.of_null()


def verb_add_hours(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    dt = _parse_date_val(args[0])
    n = coerce_num(args[1])
    if dt is None or n is None:
        return DynValue.of_null()
    result = dt + timedelta(hours=n)
    return DynValue.of_string(format_iso_timestamp(result))


def verb_add_minutes(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    dt = _parse_date_val(args[0])
    n = coerce_num(args[1])
    if dt is None or n is None:
        return DynValue.of_null()
    result = dt + timedelta(minutes=n)
    return DynValue.of_string(format_iso_timestamp(result))


def verb_add_seconds(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    dt = _parse_date_val(args[0])
    n = coerce_num(args[1])
    if dt is None or n is None:
        return DynValue.of_null()
    result = dt + timedelta(seconds=n)
    return DynValue.of_string(format_iso_timestamp(result))


def verb_start_of_day(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    dt = _parse_date_val(args[0])
    if dt is None:
        return DynValue.of_null()
    result = datetime(dt.year, dt.month, dt.day, 0, 0, 0)
    return DynValue.of_string(format_iso_timestamp(result))


def verb_end_of_day(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    dt = _parse_date_val(args[0])
    if dt is None:
        return DynValue.of_null()
    result = datetime(dt.year, dt.month, dt.day, 23, 59, 59, 999000)
    return DynValue.of_string(format_iso_timestamp(result))


def verb_start_of_month(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    dt = _parse_date_val(args[0])
    if dt is None:
        return DynValue.of_null()
    return DynValue.of_string(format_iso_date(date(dt.year, dt.month, 1)))


def verb_end_of_month(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    dt = _parse_date_val(args[0])
    if dt is None:
        return DynValue.of_null()
    last_day = days_in_month(dt.year, dt.month)
    return DynValue.of_string(format_iso_date(date(dt.year, dt.month, last_day)))


def verb_start_of_year(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    dt = _parse_date_val(args[0])
    if dt is None:
        return DynValue.of_null()
    return DynValue.of_string(format_iso_date(date(dt.year, 1, 1)))


def verb_end_of_year(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    dt = _parse_date_val(args[0])
    if dt is None:
        return DynValue.of_null()
    return DynValue.of_string(format_iso_date(date(dt.year, 12, 31)))


def verb_day_of_week(args: List[DynValue], ctx: object) -> DynValue:
    """Returns day of week: 0=Sunday, 1=Monday, ..., 6=Saturday (matches .NET/Java)."""
    if len(args) < 1:
        return DynValue.of_null()
    dt = _parse_date_val(args[0])
    if dt is None:
        return DynValue.of_null()
    # Python weekday: 0=Mon, 6=Sun. Convert to 0=Sun, 1=Mon, ..., 6=Sat
    py_weekday = dt.weekday()  # 0=Mon
    result = (py_weekday + 1) % 7  # 0=Sun, 1=Mon, ..., 6=Sat
    return DynValue.of_integer(result)


def verb_day_of_month(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    dt = _parse_date_val(args[0])
    if dt is None:
        return DynValue.of_null()
    return DynValue.of_integer(dt.day)


def verb_day_of_year(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    dt = _parse_date_val(args[0])
    if dt is None:
        return DynValue.of_null()
    return DynValue.of_integer(dt.timetuple().tm_yday)


def verb_month_name(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    dt = _parse_date_val(args[0])
    if dt is None:
        return DynValue.of_null()
    names = ["", "January", "February", "March", "April", "May", "June",
             "July", "August", "September", "October", "November", "December"]
    return DynValue.of_string(names[dt.month])


def verb_week_of_year(args: List[DynValue], ctx: object) -> DynValue:
    """ISO 8601 week number (1-53)."""
    if len(args) < 1:
        return DynValue.of_null()
    dt = _parse_date_val(args[0])
    if dt is None:
        return DynValue.of_null()
    return DynValue.of_integer(week_of_year(dt.date() if isinstance(dt, datetime) else dt))


def verb_quarter(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    dt = _parse_date_val(args[0])
    if dt is None:
        return DynValue.of_null()
    return DynValue.of_integer((dt.month - 1) // 3 + 1)


def verb_is_leap_year(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    v = args[0]
    # Accept year as integer or date string
    n = coerce_num(v)
    if n is not None and n > 100:
        return DynValue.of_bool(is_leap_year(int(n)))
    dt = _parse_date_val(v)
    if dt is None:
        return DynValue.of_null()
    return DynValue.of_bool(is_leap_year(dt.year))


def verb_is_before(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    dt1 = _parse_date_val(args[0])
    dt2 = _parse_date_val(args[1])
    if dt1 is None or dt2 is None:
        return DynValue.of_null()
    return DynValue.of_bool(dt1 < dt2)


def verb_is_after(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    dt1 = _parse_date_val(args[0])
    dt2 = _parse_date_val(args[1])
    if dt1 is None or dt2 is None:
        return DynValue.of_null()
    return DynValue.of_bool(dt1 > dt2)


def verb_is_between(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 3:
        return DynValue.of_null()
    dt = _parse_date_val(args[0])
    start = _parse_date_val(args[1])
    end = _parse_date_val(args[2])
    if dt is None or start is None or end is None:
        return DynValue.of_null()
    return DynValue.of_bool(start <= dt <= end)


def verb_to_unix(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    dt = _parse_date_val(args[0])
    if dt is None:
        return DynValue.of_null()
    epoch = datetime(1970, 1, 1)
    seconds = int((dt - epoch).total_seconds())
    return DynValue.of_integer(seconds)


def verb_from_unix(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    n = coerce_num(args[0])
    if n is None:
        return DynValue.of_null()
    # Auto-detect seconds vs milliseconds
    ts = int(n)
    if abs(ts) > 100_000_000_000:
        # Milliseconds
        ts = ts // 1000
    try:
        dt = datetime(1970, 1, 1) + timedelta(seconds=ts)
        return DynValue.of_string(format_iso_timestamp(dt))
    except (OverflowError, ValueError):
        return DynValue.of_null()


def verb_days_between_dates(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    s1 = coerce_str(args[0])
    s2 = coerce_str(args[1])
    if not s1 or not s2:
        return DynValue.of_null()
    result = date_diff_days(s1, s2)
    if result is None:
        return DynValue.of_null()
    return DynValue.of_integer(result)


def verb_age_from_date(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    birth_dt = _parse_date_val(args[0])
    if birth_dt is None:
        return DynValue.of_null()
    # As-of date
    if len(args) >= 2:
        as_of = _parse_date_val(args[1])
    else:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        as_of = now
    if as_of is None:
        return DynValue.of_null()
    birth_d = birth_dt.date() if isinstance(birth_dt, datetime) else birth_dt
    as_of_d = as_of.date() if isinstance(as_of, datetime) else as_of
    age = as_of_d.year - birth_d.year
    # Adjust if birthday hasn't occurred yet this year
    if (as_of_d.month, as_of_d.day) < (birth_d.month, birth_d.day):
        age -= 1
    if age < 0:
        return DynValue.of_null()
    return DynValue.of_integer(age)


def verb_is_valid_date(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_bool(False)
    s = coerce_str(args[0])
    if not s:
        return DynValue.of_bool(False)
    d = parse_iso_date(s)
    if d is not None:
        return DynValue.of_bool(True)
    # Try with pattern
    if len(args) >= 2:
        pattern = coerce_str(args[1])
        dt = _parse_with_pattern(s, pattern)
        if dt is not None:
            return DynValue.of_bool(True)
    return DynValue.of_bool(False)


def verb_format_locale_date(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    dt = _parse_date_val(args[0])
    if dt is None:
        return DynValue.of_null()
    # Simple locale formatting - just return ISO date for Python
    if len(args) >= 3:
        fmt = coerce_str(args[2])
        if fmt:
            return DynValue.of_string(_apply_date_format(dt, fmt))
    return DynValue.of_string(format_iso_date(dt.date() if isinstance(dt, datetime) else dt))


# ── businessDays ──────────────────────────────────────────────────────────────


def verb_business_days(args: List[DynValue], ctx: object) -> DynValue:
    """Add N business days (skip weekends)."""
    if len(args) < 2:
        return DynValue.of_null()

    dt = _parse_date_val(args[0])
    if dt is None:
        return DynValue.of_null()

    count_f = coerce_num(args[1])
    if count_f is None:
        return DynValue.of_null()
    count = int(count_f)

    d = dt.date() if isinstance(dt, datetime) else dt
    direction = 1 if count >= 0 else -1
    abs_count = abs(count)

    # O(1) jump: 5 business days == 7 calendar days
    full_weeks = abs_count // 5
    remaining = abs_count % 5
    d += timedelta(days=direction * full_weeks * 7)

    # Loop only the remainder (0-4 business days)
    while remaining > 0:
        d += timedelta(days=direction)
        if d.weekday() < 5:  # 0=Mon, 4=Fri
            remaining -= 1

    return DynValue.of_string(format_iso_date(d))


# ── nextBusinessDay ───────────────────────────────────────────────────────────


def verb_next_business_day(args: List[DynValue], ctx: object) -> DynValue:
    """Next weekday (Mon-Fri). Returns same day if already weekday."""
    if len(args) < 1:
        return DynValue.of_null()

    dt = _parse_date_val(args[0])
    if dt is None:
        return DynValue.of_null()

    d = dt.date() if isinstance(dt, datetime) else dt
    dow = d.weekday()  # 0=Mon, 6=Sun

    if dow == 5:  # Saturday
        d = d + timedelta(days=2)
    elif dow == 6:  # Sunday
        d = d + timedelta(days=1)

    return DynValue.of_string(format_iso_date(d))


# ── formatDuration ────────────────────────────────────────────────────────────

import re as _re_dt


def verb_format_duration(args: List[DynValue], ctx: object) -> DynValue:
    """Format ISO 8601 duration as human-readable text."""
    if len(args) < 1:
        return DynValue.of_null()

    s = coerce_str(args[0])
    if not s:
        return DynValue.of_null()

    m = _re_dt.match(r"^P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?$", s)
    if not m:
        return DynValue.of_null()

    years = int(m.group(1) or 0)
    months = int(m.group(2) or 0)
    days_val = int(m.group(3) or 0)
    hours = int(m.group(4) or 0)
    minutes = int(m.group(5) or 0)
    seconds = float(m.group(6) or 0)

    parts = []
    if years > 0:
        parts.append(f"{years} {'year' if years == 1 else 'years'}")
    if months > 0:
        parts.append(f"{months} {'month' if months == 1 else 'months'}")
    if days_val > 0:
        parts.append(f"{days_val} {'day' if days_val == 1 else 'days'}")
    if hours > 0:
        parts.append(f"{hours} {'hour' if hours == 1 else 'hours'}")
    if minutes > 0:
        parts.append(f"{minutes} {'minute' if minutes == 1 else 'minutes'}")
    if seconds > 0:
        if seconds == int(seconds):
            sec_str = str(int(seconds))
        else:
            sec_str = f"{seconds:.1f}"
        parts.append(f"{sec_str} {'second' if seconds == 1.0 else 'seconds'}")

    if not parts:
        return DynValue.of_string("0 seconds")

    return DynValue.of_string(", ".join(parts))
