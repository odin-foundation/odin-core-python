"""Unit tests for semantic validation of timestamp and time components."""
import pytest

import odin
from odin.types.values import OdinTime, OdinTimestamp

# ── Happy path: valid components accepted ──────────────────────────────────


class TestTimestampValid:
    def test_basic_timestamp_with_z(self):
        doc = odin.parse("ts = 2024-06-15T10:30:00Z")
        assert isinstance(doc.get("ts"), OdinTimestamp)
        assert doc.get("ts").raw == "2024-06-15T10:30:00Z"

    def test_positive_offset(self):
        doc = odin.parse("ts = 2024-06-15T10:30:00+05:30")
        assert doc.get("ts").raw == "2024-06-15T10:30:00+05:30"

    def test_negative_offset(self):
        doc = odin.parse("ts = 2024-06-15T10:30:00-08:00")
        assert doc.get("ts").raw == "2024-06-15T10:30:00-08:00"

    def test_fractional_seconds(self):
        doc = odin.parse("ts = 2024-06-15T10:30:00.123456Z")
        assert doc.get("ts").raw == "2024-06-15T10:30:00.123456Z"

    def test_end_of_day(self):
        doc = odin.parse("ts = 2024-06-15T23:59:59Z")
        assert doc.get("ts").raw == "2024-06-15T23:59:59Z"

    def test_no_seconds(self):
        doc = odin.parse("ts = 2024-06-15T10:30Z")
        assert doc.get("ts").raw == "2024-06-15T10:30Z"

    def test_max_offset(self):
        doc = odin.parse("ts = 2024-06-15T10:30:00+23:59")
        assert doc.get("ts").raw == "2024-06-15T10:30:00+23:59"


class TestTimeValid:
    def test_basic_time(self):
        doc = odin.parse("t = T14:30:00")
        assert isinstance(doc.get("t"), OdinTime)
        assert doc.get("t").value == "T14:30:00"

    def test_no_seconds(self):
        doc = odin.parse("t = T14:30")
        assert doc.get("t").value == "T14:30"

    def test_midnight(self):
        doc = odin.parse("t = T00:00:00")
        assert doc.get("t").value == "T00:00:00"

    def test_milliseconds(self):
        doc = odin.parse("t = T14:30:00.123")
        assert doc.get("t").value == "T14:30:00.123"


# ── Intentional leniency: leap second and hour-24 midnight ─────────────────


class TestLeniency:
    def test_timestamp_leap_second(self):
        doc = odin.parse("ts = 2016-12-31T23:59:60Z")
        assert doc.get("ts").raw == "2016-12-31T23:59:60Z"

    def test_time_leap_second(self):
        doc = odin.parse("t = T23:59:60")
        assert doc.get("t").value == "T23:59:60"

    def test_time_hour_24_midnight(self):
        doc = odin.parse("t = T24:00:00")
        assert doc.get("t").value == "T24:00:00"


# ── Error path: malformed components raise P001 ────────────────────────────


class TestTimestampErrors:
    def test_bad_date_portion(self):
        with pytest.raises(odin.ParseError) as exc:
            odin.parse("ts = 2024-13-40T10:30:00Z")
        assert exc.value.code == "P001"

    def test_bad_hour(self):
        with pytest.raises(odin.ParseError) as exc:
            odin.parse("ts = 2024-06-15T25:30:00Z")
        assert exc.value.code == "P001"

    def test_bad_minute(self):
        with pytest.raises(odin.ParseError) as exc:
            odin.parse("ts = 2024-06-15T10:61:00Z")
        assert exc.value.code == "P001"

    def test_bad_second(self):
        with pytest.raises(odin.ParseError) as exc:
            odin.parse("ts = 2024-06-15T10:30:61Z")
        assert exc.value.code == "P001"

    def test_bad_offset_hour(self):
        with pytest.raises(odin.ParseError) as exc:
            odin.parse("ts = 2024-06-15T10:30:00+25:00")
        assert exc.value.code == "P001"

    def test_bad_offset_minute(self):
        with pytest.raises(odin.ParseError) as exc:
            odin.parse("ts = 2024-06-15T10:30:00+05:99")
        assert exc.value.code == "P001"

    def test_fully_malformed(self):
        with pytest.raises(odin.ParseError) as exc:
            odin.parse("ts = 2024-13-40T99:99:99Z")
        assert exc.value.code == "P001"

    def test_explicit_p001_code(self):
        with pytest.raises(odin.ParseError) as exc:
            odin.parse("ts = 2024-06-15T25:00:00Z")
        assert exc.value.code == "P001"


class TestTimeErrors:
    def test_bad_hour(self):
        with pytest.raises(odin.ParseError) as exc:
            odin.parse("t = T25:00:00")
        assert exc.value.code == "P001"

    def test_hour_24_nonzero_minutes(self):
        with pytest.raises(odin.ParseError) as exc:
            odin.parse("t = T24:30:00")
        assert exc.value.code == "P001"

    def test_hour_24_nonzero_seconds(self):
        with pytest.raises(odin.ParseError) as exc:
            odin.parse("t = T24:00:30")
        assert exc.value.code == "P001"

    def test_bad_minute(self):
        with pytest.raises(odin.ParseError) as exc:
            odin.parse("t = T14:61:00")
        assert exc.value.code == "P001"

    def test_bad_second(self):
        with pytest.raises(odin.ParseError) as exc:
            odin.parse("t = T14:30:61")
        assert exc.value.code == "P001"


# ── Edge cases ─────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_second_60_is_leap_not_error(self):
        # 60 is the only second above 59 that is allowed
        assert odin.parse("t = T10:00:60").get("t").value == "T10:00:60"
        with pytest.raises(odin.ParseError):
            odin.parse("t = T10:00:61")

    def test_fractional_seconds_stripped_before_bounds(self):
        # Fractional part must not affect the second bounds check
        doc = odin.parse("ts = 2024-06-15T10:30:60.500Z")
        assert doc.get("ts").raw == "2024-06-15T10:30:60.500Z"

    def test_z_offset_not_range_checked(self):
        doc = odin.parse("ts = 2024-06-15T00:00:00Z")
        assert doc.get("ts").raw == "2024-06-15T00:00:00Z"

    def test_hour_23_boundary(self):
        assert odin.parse("t = T23:00:00").get("t").value == "T23:00:00"

    def test_minute_59_boundary(self):
        assert odin.parse("t = T10:59:00").get("t").value == "T10:59:00"
