"""Extended tests for datetime verbs — ~250 tests covering all datetime verbs thoroughly."""

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


# ══════════════════════════════════════════════════════════════════════
# today / now
# ══════════════════════════════════════════════════════════════════════

class TestTodayExtended:
    def test_returns_string(self):
        r = invoke("today")
        assert r.type == DynType.STRING

    def test_format_yyyy_mm_dd(self):
        r = invoke("today")
        s = r.as_string()
        assert len(s) == 10
        parts = s.split("-")
        assert len(parts) == 3
        assert len(parts[0]) == 4
        assert len(parts[1]) == 2
        assert len(parts[2]) == 2

    def test_year_reasonable(self):
        r = invoke("today")
        year = int(r.as_string()[:4])
        assert 2020 <= year <= 2100

    def test_month_in_range(self):
        r = invoke("today")
        month = int(r.as_string()[5:7])
        assert 1 <= month <= 12

    def test_day_in_range(self):
        r = invoke("today")
        day = int(r.as_string()[8:10])
        assert 1 <= day <= 31

    def test_idempotent(self):
        r1 = invoke("today")
        r2 = invoke("today")
        assert r1.as_string() == r2.as_string()


class TestNowExtended:
    def test_returns_string(self):
        r = invoke("now")
        assert r.type == DynType.STRING

    def test_contains_t_separator(self):
        r = invoke("now")
        assert "T" in r.as_string()

    def test_has_date_part(self):
        r = invoke("now")
        s = r.as_string()
        date_part = s.split("T")[0]
        assert len(date_part) == 10

    def test_has_time_part(self):
        r = invoke("now")
        s = r.as_string()
        time_part = s.split("T")[1]
        assert ":" in time_part


# ══════════════════════════════════════════════════════════════════════
# formatDate
# ══════════════════════════════════════════════════════════════════════

class TestFormatDateExtended:
    @pytest.mark.parametrize("date_str,pattern,expected", [
        ("2024-03-15", "YYYY/MM/DD", "2024/03/15"),
        ("2024-03-15", "YYYY", "2024"),
        ("2024-03-15", "MM", "03"),
        ("2024-03-15", "DD", "15"),
        ("2024-03-15", "MM-DD-YYYY", "03-15-2024"),
        ("2024-03-15", "DD.MM.YYYY", "15.03.2024"),
        ("2024-01-01", "YYYY-MM-DD", "2024-01-01"),
        ("2024-12-31", "YYYY-MM-DD", "2024-12-31"),
    ])
    def test_patterns(self, date_str, pattern, expected):
        r = invoke("formatDate", date_str, pattern)
        assert r.as_string() == expected

    def test_null_input(self):
        r = invoke("formatDate", None, "YYYY")
        assert r.is_null()

    def test_null_pattern(self):
        r = invoke("formatDate", "2024-03-15", None)
        # pattern coerced to empty string, produces no tokens
        assert r.type == DynType.STRING

    def test_invalid_date(self):
        r = invoke("formatDate", "not-a-date", "YYYY-MM-DD")
        assert r.is_null()

    def test_timestamp_input(self):
        r = invoke("formatDate", "2024-03-15T14:30:00.000Z", "YYYY-MM-DD")
        assert r.as_string() == "2024-03-15"

    def test_year_only_from_timestamp(self):
        r = invoke("formatDate", "2024-06-20T10:00:00.000Z", "YYYY")
        assert r.as_string() == "2024"

    def test_month_day_pattern(self):
        r = invoke("formatDate", "2024-07-04", "MM/DD")
        assert r.as_string() == "07/04"


# ══════════════════════════════════════════════════════════════════════
# parseDate
# ══════════════════════════════════════════════════════════════════════

class TestParseDateExtended:
    @pytest.mark.parametrize("input_str,pattern,expected", [
        ("2024-03-15", "YYYY-MM-DD", "2024-03-15"),
        ("15/03/2024", "DD/MM/YYYY", "2024-03-15"),
        ("03-15-2024", "MM-DD-YYYY", "2024-03-15"),
        ("20240315", "YYYYMMDD", "2024-03-15"),
        ("01/01/2000", "DD/MM/YYYY", "2000-01-01"),
        ("12/31/2024", "MM/DD/YYYY", "2024-12-31"),
    ])
    def test_patterns(self, input_str, pattern, expected):
        r = invoke("parseDate", input_str, pattern)
        assert r.as_string() == expected

    def test_iso_without_pattern(self):
        r = invoke("parseDate", "2024-03-15")
        assert r.as_string() == "2024-03-15"

    def test_null_input(self):
        r = invoke("parseDate", None, "YYYY-MM-DD")
        assert r.is_null()

    def test_invalid_date(self):
        r = invoke("parseDate", "not-a-date", "YYYY-MM-DD")
        assert r.is_null()

    def test_empty_string(self):
        r = invoke("parseDate", "", "YYYY-MM-DD")
        assert r.is_null()

    def test_feb_29_leap(self):
        r = invoke("parseDate", "2024-02-29", "YYYY-MM-DD")
        assert r.as_string() == "2024-02-29"


# ══════════════════════════════════════════════════════════════════════
# formatTime
# ══════════════════════════════════════════════════════════════════════

class TestFormatTimeExtended:
    def test_from_timestamp_default(self):
        r = invoke("formatTime", "2024-03-15T14:30:00.000Z")
        assert r.as_string() == "14:30:00"

    def test_midnight(self):
        r = invoke("formatTime", "2024-03-15T00:00:00.000Z")
        assert r.as_string() == "00:00:00"

    def test_end_of_day(self):
        r = invoke("formatTime", "2024-03-15T23:59:59.000Z")
        assert r.as_string() == "23:59:59"

    def test_with_pattern(self):
        r = invoke("formatTime", "2024-03-15T14:30:45.000Z", "HH:mm:ss")
        assert r.as_string() == "14:30:45"

    def test_12_hour_format(self):
        r = invoke("formatTime", "2024-03-15T14:30:00.000Z", "hh:mm A")
        assert r.as_string() == "02:30 PM"

    def test_12_hour_am(self):
        r = invoke("formatTime", "2024-03-15T09:15:00.000Z", "hh:mm A")
        assert r.as_string() == "09:15 AM"

    def test_null_input(self):
        r = invoke("formatTime", None)
        assert r.is_null()

    def test_noon(self):
        r = invoke("formatTime", "2024-03-15T12:00:00.000Z")
        assert r.as_string() == "12:00:00"


# ══════════════════════════════════════════════════════════════════════
# formatTimestamp
# ══════════════════════════════════════════════════════════════════════

class TestFormatTimestampExtended:
    def test_custom_pattern(self):
        r = invoke("formatTimestamp", "2024-03-15T14:30:00.000Z", "YYYY-MM-DD HH:mm:ss")
        assert r.as_string() == "2024-03-15 14:30:00"

    def test_date_only_pattern(self):
        r = invoke("formatTimestamp", "2024-03-15T14:30:00.000Z", "YYYY-MM-DD")
        assert r.as_string() == "2024-03-15"

    def test_default_iso(self):
        r = invoke("formatTimestamp", "2024-03-15T14:30:00.000Z")
        s = r.as_string()
        assert "2024-03-15" in s
        assert "14:30:00" in s

    def test_null_input(self):
        r = invoke("formatTimestamp", None)
        assert r.is_null()

    def test_time_only_pattern(self):
        r = invoke("formatTimestamp", "2024-03-15T14:30:45.000Z", "HH:mm:ss")
        assert r.as_string() == "14:30:45"

    def test_milliseconds_pattern(self):
        r = invoke("formatTimestamp", "2024-03-15T14:30:45.123Z", "HH:mm:ss.SSS")
        assert r.as_string() == "14:30:45.123"


# ══════════════════════════════════════════════════════════════════════
# parseTimestamp
# ══════════════════════════════════════════════════════════════════════

class TestParseTimestampExtended:
    def test_iso_with_z(self):
        r = invoke("parseTimestamp", "2024-03-15T14:30:00Z")
        s = r.as_string()
        assert "2024-03-15" in s
        assert "14:30:00" in s

    def test_iso_with_millis(self):
        r = invoke("parseTimestamp", "2024-03-15T14:30:00.000Z")
        s = r.as_string()
        assert "2024-03-15" in s

    def test_null_input(self):
        r = invoke("parseTimestamp", None)
        assert r.is_null()

    def test_invalid_input(self):
        r = invoke("parseTimestamp", "not-a-timestamp")
        assert r.is_null()

    def test_empty_string(self):
        r = invoke("parseTimestamp", "")
        assert r.is_null()

    def test_date_only_string(self):
        r = invoke("parseTimestamp", "2024-03-15")
        s = r.as_string()
        assert "2024-03-15" in s


# ══════════════════════════════════════════════════════════════════════
# addDays
# ══════════════════════════════════════════════════════════════════════

class TestAddDaysExtended:
    @pytest.mark.parametrize("date_str,days,expected", [
        ("2024-01-01", 0, "2024-01-01"),
        ("2024-01-01", 1, "2024-01-02"),
        ("2024-01-01", 10, "2024-01-11"),
        ("2024-01-01", 31, "2024-02-01"),
        ("2024-01-01", 366, "2025-01-01"),  # 2024 is leap year
        ("2024-01-30", 5, "2024-02-04"),
        ("2024-02-28", 1, "2024-02-29"),    # leap year
        ("2023-02-28", 1, "2023-03-01"),    # non-leap year
        ("2024-12-31", 1, "2025-01-01"),    # year boundary
    ])
    def test_positive_days(self, date_str, days, expected):
        r = invoke("addDays", date_str, days)
        assert r.as_string() == expected

    @pytest.mark.parametrize("date_str,days,expected", [
        ("2024-03-15", -1, "2024-03-14"),
        ("2024-03-15", -15, "2024-02-29"),
        ("2024-01-01", -1, "2023-12-31"),
        ("2024-03-01", -1, "2024-02-29"),   # leap year
        ("2023-03-01", -1, "2023-02-28"),   # non-leap year
    ])
    def test_negative_days(self, date_str, days, expected):
        r = invoke("addDays", date_str, days)
        assert r.as_string() == expected

    def test_null_date(self):
        r = invoke("addDays", None, 5)
        assert r.is_null()

    def test_null_days(self):
        r = invoke("addDays", "2024-01-01", None)
        assert r.is_null()

    def test_large_offset(self):
        r = invoke("addDays", "2024-01-01", 365 * 10)
        s = r.as_string()
        assert s.startswith("203")


# ══════════════════════════════════════════════════════════════════════
# addMonths
# ══════════════════════════════════════════════════════════════════════

class TestAddMonthsExtended:
    @pytest.mark.parametrize("date_str,months,expected", [
        ("2024-01-15", 0, "2024-01-15"),
        ("2024-01-15", 1, "2024-02-15"),
        ("2024-01-15", 2, "2024-03-15"),
        ("2024-01-15", 12, "2025-01-15"),
        ("2024-11-15", 3, "2025-02-15"),
    ])
    def test_basic(self, date_str, months, expected):
        r = invoke("addMonths", date_str, months)
        assert r.as_string() == expected

    @pytest.mark.parametrize("date_str,months,expected", [
        ("2024-01-31", 1, "2024-02-29"),   # clamp to feb leap
        ("2023-01-31", 1, "2023-02-28"),   # clamp to feb non-leap
        ("2024-03-31", 1, "2024-04-30"),   # clamp to 30-day month
        ("2024-05-31", 1, "2024-06-30"),   # clamp to june
    ])
    def test_end_of_month_clamping(self, date_str, months, expected):
        r = invoke("addMonths", date_str, months)
        assert r.as_string() == expected

    @pytest.mark.parametrize("date_str,months,expected", [
        ("2024-03-15", -1, "2024-02-15"),
        ("2024-03-15", -3, "2023-12-15"),
        ("2024-01-31", -1, "2023-12-31"),
    ])
    def test_negative(self, date_str, months, expected):
        r = invoke("addMonths", date_str, months)
        assert r.as_string() == expected

    def test_null_input(self):
        r = invoke("addMonths", None, 1)
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# addYears
# ══════════════════════════════════════════════════════════════════════

class TestAddYearsExtended:
    @pytest.mark.parametrize("date_str,years,expected", [
        ("2024-03-15", 0, "2024-03-15"),
        ("2024-03-15", 1, "2025-03-15"),
        ("2024-03-15", 10, "2034-03-15"),
        ("2024-03-15", -1, "2023-03-15"),
        ("2024-03-15", -10, "2014-03-15"),
    ])
    def test_basic(self, date_str, years, expected):
        r = invoke("addYears", date_str, years)
        assert r.as_string() == expected

    def test_leap_to_non_leap(self):
        # Feb 29 on leap year -> Feb 28 on non-leap year
        r = invoke("addYears", "2024-02-29", 1)
        assert r.as_string() == "2025-02-28"

    def test_leap_to_leap(self):
        r = invoke("addYears", "2024-02-29", 4)
        assert r.as_string() == "2028-02-29"

    def test_null_input(self):
        r = invoke("addYears", None, 1)
        assert r.is_null()

    def test_null_years(self):
        r = invoke("addYears", "2024-03-15", None)
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# dateDiff
# ══════════════════════════════════════════════════════════════════════

class TestDateDiffExtended:
    @pytest.mark.parametrize("d1,d2,expected", [
        ("2024-01-01", "2024-01-01", 0),
        ("2024-01-01", "2024-01-11", 10),
        ("2024-01-11", "2024-01-01", -10),
        ("2024-01-01", "2024-02-01", 31),
        ("2024-01-01", "2025-01-01", 366),   # leap year
        ("2023-01-01", "2024-01-01", 365),   # non-leap year
    ])
    def test_days_unit(self, d1, d2, expected):
        r = invoke("dateDiff", d1, d2)
        assert r._int_value == expected

    @pytest.mark.parametrize("d1,d2,expected", [
        ("2024-01-15", "2024-03-15", 2),
        ("2024-01-15", "2024-01-15", 0),
        ("2024-03-15", "2024-01-15", -2),
        ("2024-01-01", "2025-01-01", 12),
    ])
    def test_months_unit(self, d1, d2, expected):
        r = invoke("dateDiff", d1, d2, "months")
        assert r._int_value == expected

    @pytest.mark.parametrize("d1,d2,expected", [
        ("2024-03-15", "2024-03-15", 0),
        ("2020-01-01", "2024-01-01", 4),
        ("2024-01-01", "2020-01-01", -4),
        ("2020-06-15", "2024-03-15", 3),  # birthday hasn't happened yet
    ])
    def test_years_unit(self, d1, d2, expected):
        r = invoke("dateDiff", d1, d2, "years")
        assert r._int_value == expected

    def test_null_first(self):
        r = invoke("dateDiff", None, "2024-01-01")
        assert r.is_null()

    def test_null_second(self):
        r = invoke("dateDiff", "2024-01-01", None)
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# addHours / addMinutes / addSeconds
# ══════════════════════════════════════════════════════════════════════

class TestAddHoursExtended:
    @pytest.mark.parametrize("hours,expected_time", [
        (0, "00:00:00"),
        (1, "01:00:00"),
        (5, "05:00:00"),
        (12, "12:00:00"),
        (23, "23:00:00"),
    ])
    def test_positive(self, hours, expected_time):
        r = invoke("addHours", "2024-03-15T00:00:00.000Z", hours)
        assert expected_time in r.as_string()

    def test_overflow_day(self):
        r = invoke("addHours", "2024-03-15T00:00:00.000Z", 25)
        s = r.as_string()
        assert "2024-03-16" in s
        assert "01:00:00" in s

    def test_negative(self):
        r = invoke("addHours", "2024-03-15T12:00:00.000Z", -3)
        assert "09:00:00" in r.as_string()

    def test_null(self):
        r = invoke("addHours", None, 5)
        assert r.is_null()


class TestAddMinutesExtended:
    @pytest.mark.parametrize("minutes,expected_time", [
        (0, "00:00:00"),
        (30, "00:30:00"),
        (60, "01:00:00"),
        (90, "01:30:00"),
        (120, "02:00:00"),
    ])
    def test_positive(self, minutes, expected_time):
        r = invoke("addMinutes", "2024-03-15T00:00:00.000Z", minutes)
        assert expected_time in r.as_string()

    def test_negative(self):
        r = invoke("addMinutes", "2024-03-15T01:00:00.000Z", -30)
        assert "00:30:00" in r.as_string()

    def test_null(self):
        r = invoke("addMinutes", None, 5)
        assert r.is_null()

    def test_overflow_hour(self):
        r = invoke("addMinutes", "2024-03-15T23:30:00.000Z", 60)
        s = r.as_string()
        assert "2024-03-16" in s
        assert "00:30:00" in s


class TestAddSecondsExtended:
    @pytest.mark.parametrize("seconds,expected_time", [
        (0, "00:00:00"),
        (30, "00:00:30"),
        (60, "00:01:00"),
        (3600, "01:00:00"),
        (3661, "01:01:01"),
    ])
    def test_positive(self, seconds, expected_time):
        r = invoke("addSeconds", "2024-03-15T00:00:00.000Z", seconds)
        assert expected_time in r.as_string()

    def test_negative(self):
        r = invoke("addSeconds", "2024-03-15T00:01:00.000Z", -30)
        assert "00:00:30" in r.as_string()

    def test_null(self):
        r = invoke("addSeconds", None, 5)
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# startOfDay / endOfDay
# ══════════════════════════════════════════════════════════════════════

class TestStartOfDayExtended:
    def test_date_input(self):
        r = invoke("startOfDay", "2024-03-15")
        assert "00:00:00" in r.as_string()
        assert "2024-03-15" in r.as_string()

    def test_timestamp_input(self):
        r = invoke("startOfDay", "2024-03-15T14:30:00.000Z")
        assert "00:00:00" in r.as_string()

    def test_null(self):
        r = invoke("startOfDay", None)
        assert r.is_null()

    def test_preserves_date(self):
        r = invoke("startOfDay", "2024-12-25T18:45:30.000Z")
        assert "2024-12-25" in r.as_string()


class TestEndOfDayExtended:
    def test_date_input(self):
        r = invoke("endOfDay", "2024-03-15")
        assert "23:59:59" in r.as_string()
        assert "2024-03-15" in r.as_string()

    def test_timestamp_input(self):
        r = invoke("endOfDay", "2024-03-15T08:00:00.000Z")
        assert "23:59:59" in r.as_string()

    def test_null(self):
        r = invoke("endOfDay", None)
        assert r.is_null()

    def test_preserves_date(self):
        r = invoke("endOfDay", "2024-07-04T10:00:00.000Z")
        assert "2024-07-04" in r.as_string()


# ══════════════════════════════════════════════════════════════════════
# startOfMonth / endOfMonth
# ══════════════════════════════════════════════════════════════════════

class TestStartOfMonthExtended:
    @pytest.mark.parametrize("date_str,expected", [
        ("2024-01-15", "2024-01-01"),
        ("2024-02-29", "2024-02-01"),
        ("2024-03-31", "2024-03-01"),
        ("2024-06-15", "2024-06-01"),
        ("2024-12-25", "2024-12-01"),
    ])
    def test_various_months(self, date_str, expected):
        r = invoke("startOfMonth", date_str)
        assert r.as_string() == expected

    def test_null(self):
        r = invoke("startOfMonth", None)
        assert r.is_null()

    def test_already_first(self):
        r = invoke("startOfMonth", "2024-05-01")
        assert r.as_string() == "2024-05-01"


class TestEndOfMonthExtended:
    @pytest.mark.parametrize("date_str,expected", [
        ("2024-01-15", "2024-01-31"),
        ("2024-02-10", "2024-02-29"),  # leap year
        ("2023-02-10", "2023-02-28"),  # non-leap year
        ("2024-03-01", "2024-03-31"),
        ("2024-04-15", "2024-04-30"),
        ("2024-06-01", "2024-06-30"),
        ("2024-09-10", "2024-09-30"),
        ("2024-11-20", "2024-11-30"),
        ("2024-12-01", "2024-12-31"),
    ])
    def test_various_months(self, date_str, expected):
        r = invoke("endOfMonth", date_str)
        assert r.as_string() == expected

    def test_null(self):
        r = invoke("endOfMonth", None)
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# startOfYear / endOfYear
# ══════════════════════════════════════════════════════════════════════

class TestStartOfYearExtended:
    @pytest.mark.parametrize("date_str,expected", [
        ("2024-06-15", "2024-01-01"),
        ("2024-01-01", "2024-01-01"),
        ("2024-12-31", "2024-01-01"),
        ("2023-07-20", "2023-01-01"),
    ])
    def test_various(self, date_str, expected):
        r = invoke("startOfYear", date_str)
        assert r.as_string() == expected

    def test_null(self):
        r = invoke("startOfYear", None)
        assert r.is_null()


class TestEndOfYearExtended:
    @pytest.mark.parametrize("date_str,expected", [
        ("2024-06-15", "2024-12-31"),
        ("2024-01-01", "2024-12-31"),
        ("2024-12-31", "2024-12-31"),
        ("2023-03-10", "2023-12-31"),
    ])
    def test_various(self, date_str, expected):
        r = invoke("endOfYear", date_str)
        assert r.as_string() == expected

    def test_null(self):
        r = invoke("endOfYear", None)
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# dayOfWeek
# ══════════════════════════════════════════════════════════════════════

class TestDayOfWeekExtended:
    # 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat
    @pytest.mark.parametrize("date_str,expected", [
        ("2024-03-17", 0),  # Sunday
        ("2024-03-18", 1),  # Monday
        ("2024-03-19", 2),  # Tuesday
        ("2024-03-20", 3),  # Wednesday
        ("2024-03-21", 4),  # Thursday
        ("2024-03-15", 5),  # Friday
        ("2024-03-16", 6),  # Saturday
    ])
    def test_all_days(self, date_str, expected):
        r = invoke("dayOfWeek", date_str)
        assert r._int_value == expected

    def test_jan_1_2024(self):
        # 2024-01-01 is Monday
        r = invoke("dayOfWeek", "2024-01-01")
        assert r._int_value == 1

    def test_null(self):
        r = invoke("dayOfWeek", None)
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# dayOfMonth
# ══════════════════════════════════════════════════════════════════════

class TestDayOfMonthExtended:
    @pytest.mark.parametrize("date_str,expected", [
        ("2024-01-01", 1),
        ("2024-01-15", 15),
        ("2024-01-31", 31),
        ("2024-02-29", 29),
        ("2024-12-25", 25),
    ])
    def test_various(self, date_str, expected):
        r = invoke("dayOfMonth", date_str)
        assert r._int_value == expected

    def test_null(self):
        r = invoke("dayOfMonth", None)
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# dayOfYear
# ══════════════════════════════════════════════════════════════════════

class TestDayOfYearExtended:
    @pytest.mark.parametrize("date_str,expected", [
        ("2024-01-01", 1),
        ("2024-02-01", 32),
        ("2024-03-01", 61),    # leap year: 31 + 29 + 1
        ("2024-03-15", 75),    # leap year: 31 + 29 + 15
        ("2024-12-31", 366),   # leap year last day
        ("2023-12-31", 365),   # non-leap year last day
        ("2023-03-01", 60),    # non-leap year: 31 + 28 + 1
    ])
    def test_various(self, date_str, expected):
        r = invoke("dayOfYear", date_str)
        assert r._int_value == expected

    def test_null(self):
        r = invoke("dayOfYear", None)
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# weekOfYear
# ══════════════════════════════════════════════════════════════════════

class TestWeekOfYearExtended:
    @pytest.mark.parametrize("date_str,expected", [
        ("2024-01-01", 1),
        ("2024-01-08", 2),
        ("2024-06-15", 24),
        ("2020-12-31", 53),   # ISO week 53
        ("2024-12-30", 1),    # ISO week 1 of next year
    ])
    def test_various(self, date_str, expected):
        r = invoke("weekOfYear", date_str)
        assert r._int_value == expected

    def test_null(self):
        r = invoke("weekOfYear", None)
        assert r.is_null()

    def test_mid_year(self):
        r = invoke("weekOfYear", "2024-07-01")
        assert 26 <= r._int_value <= 28


# ══════════════════════════════════════════════════════════════════════
# quarter
# ══════════════════════════════════════════════════════════════════════

class TestQuarterExtended:
    @pytest.mark.parametrize("date_str,expected", [
        ("2024-01-01", 1),
        ("2024-02-15", 1),
        ("2024-03-31", 1),
        ("2024-04-01", 2),
        ("2024-05-15", 2),
        ("2024-06-30", 2),
        ("2024-07-01", 3),
        ("2024-08-15", 3),
        ("2024-09-30", 3),
        ("2024-10-01", 4),
        ("2024-11-15", 4),
        ("2024-12-31", 4),
    ])
    def test_all_quarters(self, date_str, expected):
        r = invoke("quarter", date_str)
        assert r._int_value == expected

    def test_null(self):
        r = invoke("quarter", None)
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# isLeapYear
# ══════════════════════════════════════════════════════════════════════

class TestIsLeapYearExtended:
    @pytest.mark.parametrize("year,expected", [
        (2024, True),
        (2020, True),
        (2000, True),    # divisible by 400
        (1600, True),
        (2023, False),
        (2100, False),   # divisible by 100 but not 400
        (1900, False),
        (1800, False),
        (2004, True),
        (2001, False),
    ])
    def test_years(self, year, expected):
        r = invoke("isLeapYear", year)
        assert r._bool_value is expected

    def test_from_date_string(self):
        r = invoke("isLeapYear", "2024-03-15")
        assert r._bool_value is True

    def test_from_date_string_non_leap(self):
        r = invoke("isLeapYear", "2023-06-01")
        assert r._bool_value is False

    def test_null(self):
        r = invoke("isLeapYear", None)
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# isBefore / isAfter / isBetween
# ══════════════════════════════════════════════════════════════════════

class TestIsBeforeExtended:
    @pytest.mark.parametrize("d1,d2,expected", [
        ("2024-01-01", "2024-06-01", True),
        ("2024-06-01", "2024-01-01", False),
        ("2024-01-01", "2024-01-01", False),   # equal is not before
        ("2023-12-31", "2024-01-01", True),
        ("2024-01-01T00:00:00.000Z", "2024-01-01T00:00:01.000Z", True),
    ])
    def test_various(self, d1, d2, expected):
        r = invoke("isBefore", d1, d2)
        assert r._bool_value is expected

    def test_null_first(self):
        r = invoke("isBefore", None, "2024-01-01")
        assert r.is_null()

    def test_null_second(self):
        r = invoke("isBefore", "2024-01-01", None)
        assert r.is_null()


class TestIsAfterExtended:
    @pytest.mark.parametrize("d1,d2,expected", [
        ("2024-06-01", "2024-01-01", True),
        ("2024-01-01", "2024-06-01", False),
        ("2024-01-01", "2024-01-01", False),   # equal is not after
        ("2024-01-01", "2023-12-31", True),
    ])
    def test_various(self, d1, d2, expected):
        r = invoke("isAfter", d1, d2)
        assert r._bool_value is expected

    def test_null(self):
        r = invoke("isAfter", None, "2024-01-01")
        assert r.is_null()


class TestIsBetweenExtended:
    @pytest.mark.parametrize("d,start,end,expected", [
        ("2024-03-15", "2024-01-01", "2024-12-31", True),
        ("2024-01-01", "2024-01-01", "2024-12-31", True),   # inclusive start
        ("2024-12-31", "2024-01-01", "2024-12-31", True),   # inclusive end
        ("2023-12-31", "2024-01-01", "2024-12-31", False),  # before range
        ("2025-01-01", "2024-01-01", "2024-12-31", False),  # after range
        ("2024-06-15", "2024-06-15", "2024-06-15", True),   # single day range
    ])
    def test_various(self, d, start, end, expected):
        r = invoke("isBetween", d, start, end)
        assert r._bool_value is expected

    def test_null_date(self):
        r = invoke("isBetween", None, "2024-01-01", "2024-12-31")
        assert r.is_null()

    def test_null_start(self):
        r = invoke("isBetween", "2024-03-15", None, "2024-12-31")
        assert r.is_null()

    def test_null_end(self):
        r = invoke("isBetween", "2024-03-15", "2024-01-01", None)
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# toUnix / fromUnix
# ══════════════════════════════════════════════════════════════════════

class TestToUnixExtended:
    @pytest.mark.parametrize("ts,expected", [
        ("1970-01-01T00:00:00.000Z", 0),
        ("1970-01-01T00:01:00.000Z", 60),
        ("1970-01-01T01:00:00.000Z", 3600),
        ("1970-01-02T00:00:00.000Z", 86400),
        ("2000-01-01T00:00:00.000Z", 946684800),
    ])
    def test_various(self, ts, expected):
        r = invoke("toUnix", ts)
        assert r._int_value == expected

    def test_null(self):
        r = invoke("toUnix", None)
        assert r.is_null()


class TestFromUnixExtended:
    @pytest.mark.parametrize("epoch,expected_date", [
        (0, "1970-01-01"),
        (86400, "1970-01-02"),
        (946684800, "2000-01-01"),
    ])
    def test_various(self, epoch, expected_date):
        r = invoke("fromUnix", epoch)
        assert expected_date in r.as_string()

    def test_null(self):
        r = invoke("fromUnix", None)
        assert r.is_null()

    def test_negative_epoch(self):
        # Before Unix epoch
        r = invoke("fromUnix", -86400)
        assert "1969-12-31" in r.as_string()

    def test_milliseconds_auto_detect(self):
        # Large value should be detected as milliseconds
        r = invoke("fromUnix", 1000000000000)
        s = r.as_string()
        assert "2001-09-09" in s


# ══════════════════════════════════════════════════════════════════════
# daysBetweenDates
# ══════════════════════════════════════════════════════════════════════

class TestDaysBetweenDatesExtended:
    @pytest.mark.parametrize("d1,d2,expected", [
        ("2024-01-01", "2024-01-01", 0),
        ("2024-01-01", "2024-01-11", 10),
        ("2024-01-11", "2024-01-01", -10),
        ("2024-01-01", "2024-02-01", 31),
        ("2024-01-01", "2025-01-01", 366),
        ("2023-01-01", "2024-01-01", 365),
    ])
    def test_various(self, d1, d2, expected):
        r = invoke("daysBetweenDates", d1, d2)
        assert r._int_value == expected

    def test_null_first(self):
        r = invoke("daysBetweenDates", None, "2024-01-01")
        assert r.is_null()

    def test_null_second(self):
        r = invoke("daysBetweenDates", "2024-01-01", None)
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# ageFromDate
# ══════════════════════════════════════════════════════════════════════

class TestAgeFromDateExtended:
    def test_age_with_as_of(self):
        r = invoke("ageFromDate", "1990-06-15", "2024-06-15")
        assert r._int_value == 34

    def test_birthday_not_yet(self):
        r = invoke("ageFromDate", "1990-06-15", "2024-06-14")
        assert r._int_value == 33

    def test_birthday_passed(self):
        r = invoke("ageFromDate", "1990-06-15", "2024-06-16")
        assert r._int_value == 34

    def test_newborn(self):
        r = invoke("ageFromDate", "2024-01-01", "2024-01-01")
        assert r._int_value == 0

    def test_one_year_old(self):
        r = invoke("ageFromDate", "2023-01-01", "2024-01-01")
        assert r._int_value == 1

    def test_null_birthdate(self):
        r = invoke("ageFromDate", None, "2024-01-01")
        assert r.is_null()

    def test_no_as_of_uses_today(self):
        # Just make sure it returns a non-null integer
        r = invoke("ageFromDate", "2000-01-01")
        assert r.type == DynType.INTEGER
        assert r._int_value >= 0


# ══════════════════════════════════════════════════════════════════════
# isValidDate
# ══════════════════════════════════════════════════════════════════════

class TestIsValidDateExtended:
    @pytest.mark.parametrize("date_str,expected", [
        ("2024-03-15", True),
        ("2024-02-29", True),      # leap year
        ("2024-01-01", True),
        ("2024-12-31", True),
        ("not-a-date", False),
        ("", False),
        ("2024-13-01", False),     # invalid month
        ("2024-02-30", False),     # invalid day
        ("abcd-ef-gh", False),
    ])
    def test_various(self, date_str, expected):
        r = invoke("isValidDate", date_str)
        assert r._bool_value is expected

    def test_null(self):
        r = invoke("isValidDate", None)
        assert r._bool_value is False


# ══════════════════════════════════════════════════════════════════════
# monthName
# ══════════════════════════════════════════════════════════════════════

class TestMonthNameExtended:
    @pytest.mark.parametrize("date_str,expected", [
        ("2024-01-15", "January"),
        ("2024-02-15", "February"),
        ("2024-03-15", "March"),
        ("2024-04-15", "April"),
        ("2024-05-15", "May"),
        ("2024-06-15", "June"),
        ("2024-07-15", "July"),
        ("2024-08-15", "August"),
        ("2024-09-15", "September"),
        ("2024-10-15", "October"),
        ("2024-11-15", "November"),
        ("2024-12-15", "December"),
    ])
    def test_all_months(self, date_str, expected):
        r = invoke("monthName", date_str)
        assert r.as_string() == expected

    def test_null(self):
        r = invoke("monthName", None)
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# Null handling across all verbs
# ══════════════════════════════════════════════════════════════════════

class TestNullHandling:
    @pytest.mark.parametrize("verb", [
        "today", "now",
    ])
    def test_no_arg_verbs_return_string(self, verb):
        r = invoke(verb)
        assert r.type == DynType.STRING

    @pytest.mark.parametrize("verb,args", [
        ("formatDate", [None, "YYYY"]),
        ("addDays", [None, 5]),
        ("addMonths", [None, 1]),
        ("addYears", [None, 1]),
        ("dateDiff", [None, "2024-01-01"]),
        ("dateDiff", ["2024-01-01", None]),
        ("addHours", [None, 1]),
        ("addMinutes", [None, 1]),
        ("addSeconds", [None, 1]),
        ("startOfDay", [None]),
        ("endOfDay", [None]),
        ("startOfMonth", [None]),
        ("endOfMonth", [None]),
        ("startOfYear", [None]),
        ("endOfYear", [None]),
        ("dayOfWeek", [None]),
        ("dayOfMonth", [None]),
        ("dayOfYear", [None]),
        ("weekOfYear", [None]),
        ("quarter", [None]),
        ("toUnix", [None]),
        ("fromUnix", [None]),
        ("daysBetweenDates", [None, "2024-01-01"]),
        ("daysBetweenDates", ["2024-01-01", None]),
        ("monthName", [None]),
    ])
    def test_null_inputs_return_null(self, verb, args):
        r = invoke(verb, *args)
        assert r.is_null()
