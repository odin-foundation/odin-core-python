"""Tests for datetime verbs."""

import pytest
from odin.transform.dyn_value import DynValue, DynType
from odin.transform.engine import TransformEngine
from odin.transform.verb_registry import create_default_registry


def _engine():
    return TransformEngine(create_default_registry())


def invoke(verb_name, *raw_args):
    engine = _engine()
    args = [_to_dyn(a) for a in raw_args]
    return engine.invoke_verb(verb_name, args)


def _to_dyn(v):
    if isinstance(v, DynValue):
        return v
    if v is None:
        return DynValue.of_null()
    if isinstance(v, bool):
        return DynValue.of_bool(v)
    if isinstance(v, int):
        return DynValue.of_integer(v)
    if isinstance(v, float):
        return DynValue.of_float(v)
    if isinstance(v, str):
        return DynValue.of_string(v)
    if isinstance(v, list):
        return DynValue.of_array([_to_dyn(x) for x in v])
    if isinstance(v, dict):
        return DynValue.of_object({k: _to_dyn(val) for k, val in v.items()})
    return DynValue.of_string(str(v))


# ── today / now ──────────────────────────────────────────────────────

class TestTodayNow:
    def test_today_format(self):
        r = invoke("today")
        s = r.as_string()
        assert len(s) == 10
        assert s[4] == "-"

    def test_now_contains_t(self):
        r = invoke("now")
        s = r.as_string()
        assert "T" in s


# ── formatDate ───────────────────────────────────────────────────────

class TestFormatDate:
    def test_basic_pattern(self):
        r = invoke("formatDate", "2024-03-15", "YYYY/MM/DD")
        assert r.as_string() == "2024/03/15"

    def test_year_only(self):
        r = invoke("formatDate", "2024-03-15", "YYYY")
        assert r.as_string() == "2024"

    def test_null_input(self):
        r = invoke("formatDate", None, "YYYY")
        assert r.is_null()


# ── parseDate ────────────────────────────────────────────────────────

class TestParseDate:
    def test_basic(self):
        r = invoke("parseDate", "2024-03-15", "YYYY-MM-DD")
        assert r.as_string() == "2024-03-15"

    def test_slash_pattern(self):
        r = invoke("parseDate", "15/03/2024", "DD/MM/YYYY")
        assert r.as_string() == "2024-03-15"


# ── formatTime ───────────────────────────────────────────────────────

class TestFormatTime:
    def test_from_timestamp(self):
        r = invoke("formatTime", "2024-03-15T14:30:00.000Z")
        assert r.as_string() == "14:30:00"


# ── formatTimestamp ──────────────────────────────────────────────────

class TestFormatTimestamp:
    def test_basic_pattern(self):
        r = invoke("formatTimestamp", "2024-03-15T14:30:00.000Z", "YYYY-MM-DD HH:mm:ss")
        assert r.as_string() == "2024-03-15 14:30:00"

    def test_default_iso(self):
        r = invoke("formatTimestamp", "2024-03-15T14:30:00.000Z")
        s = r.as_string()
        assert "2024-03-15" in s
        assert "14:30:00" in s


# ── parseTimestamp ───────────────────────────────────────────────────

class TestParseTimestamp:
    def test_pattern(self):
        r = invoke("parseTimestamp", "2024-03-15 14:30:00", "YYYY-MM-DD HH:mm:ss")
        assert r.as_string() == "2024-03-15T14:30:00"


# ── addDays ──────────────────────────────────────────────────────────

class TestAddDays:
    def test_positive(self):
        r = invoke("addDays", "2024-01-01", 10)
        assert r.as_string() == "2024-01-11"

    def test_cross_month(self):
        r = invoke("addDays", "2024-01-30", 5)
        assert r.as_string() == "2024-02-04"

    def test_negative(self):
        r = invoke("addDays", "2024-03-15", -15)
        assert r.as_string() == "2024-02-29"

    def test_null(self):
        r = invoke("addDays", None, 5)
        assert r.is_null()


# ── addMonths ────────────────────────────────────────────────────────

class TestAddMonths:
    def test_basic(self):
        r = invoke("addMonths", "2024-01-15", 2)
        assert r.as_string() == "2024-03-15"

    def test_cross_year(self):
        r = invoke("addMonths", "2024-11-15", 3)
        assert r.as_string() == "2025-02-15"

    def test_end_of_month_clamp(self):
        r = invoke("addMonths", "2024-01-31", 1)
        assert r.as_string() == "2024-02-29"


# ── addYears ─────────────────────────────────────────────────────────

class TestAddYears:
    def test_basic(self):
        r = invoke("addYears", "2024-03-15", 1)
        assert r.as_string() == "2025-03-15"

    def test_negative(self):
        r = invoke("addYears", "2024-03-15", -1)
        assert r.as_string() == "2023-03-15"


# ── dateDiff ─────────────────────────────────────────────────────────

class TestDateDiff:
    def test_same_date(self):
        r = invoke("dateDiff", "2024-01-01", "2024-01-01")
        assert r._int_value == 0

    def test_positive(self):
        r = invoke("dateDiff", "2024-01-01", "2024-01-11")
        assert r._int_value == 10

    def test_negative(self):
        r = invoke("dateDiff", "2024-01-11", "2024-01-01")
        assert r._int_value == -10


# ── addHours, addMinutes, addSeconds ─────────────────────────────────

class TestTimeArithmetic:
    def test_add_hours(self):
        r = invoke("addHours", "2024-03-15T00:00:00.000Z", 5)
        assert "05:00:00" in r.as_string()

    def test_add_minutes(self):
        r = invoke("addMinutes", "2024-03-15T00:00:00.000Z", 90)
        assert "01:30:00" in r.as_string()

    def test_add_seconds(self):
        r = invoke("addSeconds", "2024-03-15T00:00:00.000Z", 3661)
        assert "01:01:01" in r.as_string()


# ── start/end of day/month/year ──────────────────────────────────────

class TestBoundaries:
    def test_start_of_day(self):
        r = invoke("startOfDay", "2024-03-15")
        assert "00:00:00" in r.as_string()

    def test_end_of_day(self):
        r = invoke("endOfDay", "2024-03-15")
        assert "23:59:59" in r.as_string()

    def test_start_of_month(self):
        r = invoke("startOfMonth", "2024-03-15")
        assert r.as_string() == "2024-03-01"

    def test_end_of_month_march(self):
        r = invoke("endOfMonth", "2024-03-15")
        assert r.as_string() == "2024-03-31"

    def test_end_of_month_feb_leap(self):
        r = invoke("endOfMonth", "2024-02-10")
        assert r.as_string() == "2024-02-29"

    def test_start_of_year(self):
        r = invoke("startOfYear", "2024-06-15")
        assert r.as_string() == "2024-01-01"

    def test_end_of_year(self):
        r = invoke("endOfYear", "2024-06-15")
        assert r.as_string() == "2024-12-31"


# ── dayOfWeek ────────────────────────────────────────────────────────

class TestDayOfWeek:
    def test_friday(self):
        # 2024-03-15 is a Friday -> 5 (0=Sun, 5=Fri)
        r = invoke("dayOfWeek", "2024-03-15")
        assert r._int_value == 5

    def test_sunday(self):
        # 2024-03-17 is Sunday -> ISO 7
        r = invoke("dayOfWeek", "2024-03-17")
        assert r._int_value == 7


# ── weekOfYear ───────────────────────────────────────────────────────

class TestWeekOfYear:
    def test_basic(self):
        r = invoke("weekOfYear", "2024-01-08")
        assert r._int_value == 2

    def test_dec_31_week_53(self):
        # 2020-12-31 is ISO week 53
        r = invoke("weekOfYear", "2020-12-31")
        assert r._int_value == 53


# ── quarter ──────────────────────────────────────────────────────────

class TestQuarter:
    def test_q1(self):
        r = invoke("quarter", "2024-02-15")
        assert r._int_value == 1

    def test_q4(self):
        r = invoke("quarter", "2024-12-01")
        assert r._int_value == 4


# ── isLeapYear ───────────────────────────────────────────────────────

class TestIsLeapYear:
    def test_leap(self):
        r = invoke("isLeapYear", 2024)
        assert r._bool_value is True

    def test_not_leap(self):
        r = invoke("isLeapYear", 2023)
        assert r._bool_value is False

    def test_century_not_leap(self):
        r = invoke("isLeapYear", 1900)
        assert r._bool_value is False

    def test_400_leap(self):
        r = invoke("isLeapYear", 2000)
        assert r._bool_value is True


# ── isBefore / isAfter / isBetween ──────────────────────────────────

class TestComparisons:
    def test_is_before(self):
        r = invoke("isBefore", "2024-01-01", "2024-06-01")
        assert r._bool_value is True

    def test_is_after(self):
        r = invoke("isAfter", "2024-06-01", "2024-01-01")
        assert r._bool_value is True

    def test_is_between(self):
        r = invoke("isBetween", "2024-03-15", "2024-01-01", "2024-12-31")
        assert r._bool_value is True


# ── toUnix / fromUnix ────────────────────────────────────────────────

class TestUnix:
    def test_to_unix(self):
        r = invoke("toUnix", "1970-01-01T00:00:00.000Z")
        assert r._int_value == 0

    def test_from_unix(self):
        r = invoke("fromUnix", 0)
        assert "1970-01-01" in r.as_string()


# ── daysBetweenDates ─────────────────────────────────────────────────

class TestDaysBetween:
    def test_basic(self):
        r = invoke("daysBetweenDates", "2024-01-01", "2024-01-11")
        assert r._int_value == 10

    def test_reverse_order(self):
        r = invoke("daysBetweenDates", "2024-01-11", "2024-01-01")
        assert r._int_value == -10  # preserves sign


# ── isValidDate ──────────────────────────────────────────────────────

class TestIsValidDate:
    def test_valid(self):
        r = invoke("isValidDate", "2024-03-15")
        assert r._bool_value is True

    def test_invalid(self):
        r = invoke("isValidDate", "not-a-date")
        assert r._bool_value is False


# ── monthName ────────────────────────────────────────────────────────

class TestMonthName:
    def test_march(self):
        r = invoke("monthName", "2024-03-15")
        assert r.as_string() == "March"

    def test_december(self):
        r = invoke("monthName", "2024-12-01")
        assert r.as_string() == "December"


# ── dayOfMonth / dayOfYear ───────────────────────────────────────────

class TestDayOf:
    def test_day_of_month(self):
        r = invoke("dayOfMonth", "2024-03-15")
        assert r._int_value == 15

    def test_day_of_year(self):
        r = invoke("dayOfYear", "2024-01-01")
        assert r._int_value == 1

    def test_day_of_year_march(self):
        # 2024 is leap year: Jan(31) + Feb(29) + 15 = 75
        r = invoke("dayOfYear", "2024-03-15")
        assert r._int_value == 75


# ── nextBusinessDay ──────────────────────────────────────────────────

class TestNextBusinessDay:
    def test_wednesday_to_thursday(self):
        r = invoke("nextBusinessDay", "2024-01-17")
        assert r.as_string() == "2024-01-18"

    def test_friday_to_monday(self):
        r = invoke("nextBusinessDay", "2024-01-19")
        assert r.as_string() == "2024-01-22"

    def test_saturday_to_monday(self):
        r = invoke("nextBusinessDay", "2024-01-20")
        assert r.as_string() == "2024-01-22"

    def test_sunday_to_monday(self):
        r = invoke("nextBusinessDay", "2024-01-21")
        assert r.as_string() == "2024-01-22"

    def test_no_args(self):
        r = invoke("nextBusinessDay")
        assert r.type == DynType.NULL


# ── formatDuration ───────────────────────────────────────────────────

class TestFormatDuration:
    def test_seconds_full(self):
        r = invoke("formatDuration", 90061)
        assert r.as_string() == "1 day, 1 hour, 1 minute, 1 second"

    def test_seconds_sub_day(self):
        r = invoke("formatDuration", 3661)
        assert r.as_string() == "1 hour, 1 minute, 1 second"

    def test_seconds_as_string(self):
        r = invoke("formatDuration", "3661")
        assert r.as_string() == "1 hour, 1 minute, 1 second"

    def test_iso_hours_minutes(self):
        r = invoke("formatDuration", "PT2H30M")
        assert r.as_string() == "2 hours, 30 minutes"

    def test_iso_day(self):
        r = invoke("formatDuration", "P1DT6H")
        assert r.as_string() == "1 day, 6 hours"

    def test_zero_seconds(self):
        r = invoke("formatDuration", 0)
        assert r.as_string() == "0 seconds"

    def test_negative_seconds_null(self):
        r = invoke("formatDuration", -5)
        assert r.type == DynType.NULL

    def test_invalid_string_null(self):
        r = invoke("formatDuration", "not-a-duration")
        assert r.type == DynType.NULL
