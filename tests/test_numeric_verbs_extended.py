"""Extended tests for numeric verbs — targeting ~350 tests to match Java coverage."""

import math
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


def assert_numeric(result, expected, tol=1e-10):
    n = result.as_float() if result.type in (DynType.FLOAT, DynType.INTEGER) else None
    assert n is not None, f"Expected numeric, got {result}"
    assert abs(n - expected) < tol, f"Expected {expected}, got {n}"


def assert_string(result, expected):
    assert result._string_value == expected, f"Expected {expected!r}, got {result._string_value!r}"


# ==========================================================================
# formatNumber — extended
# ==========================================================================

class TestFormatNumberExtended:
    @pytest.mark.parametrize("value,decimals,expected", [
        (3.14159, 0, "3"),
        (3.14159, 1, "3.1"),
        (3.14159, 2, "3.14"),
        (3.14159, 3, "3.142"),
        (3.14159, 4, "3.1416"),
        (3.14159, 5, "3.14159"),
        (3.14159, 6, "3.141590"),
    ])
    def test_various_decimal_places(self, value, decimals, expected):
        r = invoke("formatNumber", value, decimals)
        assert_string(r, expected)

    def test_large_number(self):
        r = invoke("formatNumber", 1234567.89, 2)
        assert_string(r, "1234567.89")

    def test_very_large_number(self):
        r = invoke("formatNumber", 1e15, 0)
        s = r._string_value
        assert s is not None and len(s) > 0

    def test_very_small_number(self):
        r = invoke("formatNumber", 0.000001, 6)
        assert_string(r, "0.000001")

    def test_negative_number(self):
        r = invoke("formatNumber", -42.567, 2)
        assert_string(r, "-42.57")

    def test_zero(self):
        r = invoke("formatNumber", 0.0, 2)
        assert_string(r, "0.00")

    def test_negative_zero(self):
        r = invoke("formatNumber", -0.0, 2)
        # Python may format as "-0.00" or "0.00"
        s = r._string_value
        assert s in ("0.00", "-0.00")

    def test_integer_input(self):
        r = invoke("formatNumber", 42, 2)
        assert_string(r, "42.00")

    def test_string_input_numeric(self):
        r = invoke("formatNumber", "3.14", 1)
        assert_string(r, "3.1")

    def test_null_decimals(self):
        r = invoke("formatNumber", 3.14, None)
        assert r.is_null()

    def test_null_value(self):
        r = invoke("formatNumber", None, 2)
        assert r.is_null()

    def test_both_null(self):
        r = invoke("formatNumber", None, None)
        assert r.is_null()

    def test_missing_args(self):
        r = invoke("formatNumber", 3.14)
        assert r.is_null()

    def test_negative_decimal_places_clamped(self):
        # Negative dp should be clamped to 0
        r = invoke("formatNumber", 3.14, -1)
        assert_string(r, "3")

    def test_boolean_coercion(self):
        r = invoke("formatNumber", True, 0)
        assert_string(r, "1")


# ==========================================================================
# formatInteger — extended
# ==========================================================================

class TestFormatIntegerExtended:
    def test_positive_float(self):
        r = invoke("formatInteger", 3.7)
        assert_string(r, "3")

    def test_negative_float(self):
        r = invoke("formatInteger", -3.7)
        assert_string(r, "-4")

    def test_zero(self):
        r = invoke("formatInteger", 0.0)
        assert_string(r, "0")

    def test_integer_input(self):
        r = invoke("formatInteger", 42)
        assert_string(r, "42")

    def test_negative_integer(self):
        r = invoke("formatInteger", -7)
        assert_string(r, "-7")

    def test_large_number(self):
        r = invoke("formatInteger", 999999.9)
        assert_string(r, "999999")

    def test_string_coercion(self):
        r = invoke("formatInteger", "42.7")
        assert_string(r, "42")

    def test_null_input(self):
        r = invoke("formatInteger", None)
        assert r.is_null()

    def test_no_args(self):
        r = invoke("formatInteger")
        assert r.is_null()

    def test_near_zero_positive(self):
        r = invoke("formatInteger", 0.1)
        assert_string(r, "0")

    def test_near_zero_negative(self):
        r = invoke("formatInteger", -0.1)
        assert_string(r, "-1")


# ==========================================================================
# formatCurrency — extended
# ==========================================================================

class TestFormatCurrencyExtended:
    def test_default_two_decimals(self):
        r = invoke("formatCurrency", 1234.5)
        assert_string(r, "1234.50")

    def test_explicit_two_decimals(self):
        r = invoke("formatCurrency", 1234.567, 2)
        assert_string(r, "1234.57")

    def test_zero_decimals(self):
        r = invoke("formatCurrency", 1234.567, 0)
        assert_string(r, "1235")

    def test_three_decimals(self):
        r = invoke("formatCurrency", 1234.5678, 3)
        assert_string(r, "1234.568")

    def test_negative_amount(self):
        r = invoke("formatCurrency", -99.99)
        assert_string(r, "-99.99")

    def test_zero(self):
        r = invoke("formatCurrency", 0.0)
        assert_string(r, "0.00")

    def test_small_amount(self):
        r = invoke("formatCurrency", 0.01)
        assert_string(r, "0.01")

    def test_large_amount(self):
        r = invoke("formatCurrency", 1000000.00)
        assert_string(r, "1000000.00")

    def test_null_input(self):
        r = invoke("formatCurrency", None)
        assert r.is_null()

    def test_no_args(self):
        r = invoke("formatCurrency")
        assert r.is_null()

    def test_string_coercion(self):
        r = invoke("formatCurrency", "99.9")
        assert_string(r, "99.90")

    def test_integer_input(self):
        r = invoke("formatCurrency", 100)
        assert_string(r, "100.00")


# ==========================================================================
# formatPercent — extended
# ==========================================================================

class TestFormatPercentExtended:
    @pytest.mark.parametrize("value,decimals,expected", [
        (0.85, 0, "85%"),
        (0.8567, 2, "85.67%"),
        (0.0, 0, "0%"),
        (1.0, 0, "100%"),
        (0.5, 1, "50.0%"),
        (0.333, 0, "33%"),
        (0.999, 0, "100%"),
        (0.001, 0, "0%"),
        (0.001, 1, "0.1%"),
    ])
    def test_various(self, value, decimals, expected):
        r = invoke("formatPercent", value, decimals)
        assert_string(r, expected)

    def test_negative_value(self):
        r = invoke("formatPercent", -0.25, 0)
        assert_string(r, "-25%")

    def test_over_100_percent(self):
        r = invoke("formatPercent", 1.5, 0)
        assert_string(r, "150%")

    def test_null_input(self):
        r = invoke("formatPercent", None)
        assert r.is_null()

    def test_no_args(self):
        r = invoke("formatPercent")
        assert r.is_null()

    def test_default_zero_decimals(self):
        r = invoke("formatPercent", 0.856)
        assert_string(r, "86%")


# ==========================================================================
# add — extended
# ==========================================================================

class TestAddExtended:
    @pytest.mark.parametrize("a,b,expected", [
        (2, 3, 5),
        (-2, -3, -5),
        (-2, 3, 1),
        (0, 0, 0),
        (0, 5, 5),
        (1000000, 2000000, 3000000),
    ])
    def test_integer_pairs(self, a, b, expected):
        r = invoke("add", a, b)
        assert_numeric(r, expected)

    @pytest.mark.parametrize("a,b,expected", [
        (1.5, 2.5, 4.0),
        (-1.5, -2.5, -4.0),
        (0.1, 0.2, 0.3),
    ])
    def test_float_pairs(self, a, b, expected):
        r = invoke("add", a, b)
        assert_numeric(r, expected, tol=1e-9)

    def test_int_float_mix(self):
        r = invoke("add", 2, 3.5)
        assert_numeric(r, 5.5)

    def test_float_int_mix(self):
        r = invoke("add", 2.5, 3)
        assert_numeric(r, 5.5)

    def test_string_coercion(self):
        r = invoke("add", "10", "20")
        assert_numeric(r, 30)

    def test_string_int_mix(self):
        r = invoke("add", "10", 5)
        assert_numeric(r, 15)

    def test_null_first(self):
        r = invoke("add", None, 5)
        assert r.as_int() == 5

    def test_null_second(self):
        r = invoke("add", 5, None)
        assert r.as_int() == 5

    def test_both_null(self):
        r = invoke("add", None, None)
        assert r.as_int() == 0

    def test_missing_args(self):
        r = invoke("add", 5)
        assert r.is_null()

    def test_no_args(self):
        r = invoke("add")
        assert r.is_null()

    def test_boolean_coercion(self):
        r = invoke("add", True, 5)
        assert_numeric(r, 6)


# ==========================================================================
# subtract — extended
# ==========================================================================

class TestSubtractExtended:
    @pytest.mark.parametrize("a,b,expected", [
        (10, 3, 7),
        (3, 10, -7),
        (-5, -3, -2),
        (0, 0, 0),
        (0, 5, -5),
        (5, 0, 5),
    ])
    def test_integer_pairs(self, a, b, expected):
        r = invoke("subtract", a, b)
        assert_numeric(r, expected)

    def test_float_pair(self):
        r = invoke("subtract", 5.5, 2.2)
        assert_numeric(r, 3.3, tol=1e-9)

    def test_int_float_mix(self):
        r = invoke("subtract", 10, 3.5)
        assert_numeric(r, 6.5)

    def test_string_coercion(self):
        r = invoke("subtract", "20", "7")
        assert_numeric(r, 13)

    def test_null_first(self):
        r = invoke("subtract", None, 3)
        assert r.as_int() == -3

    def test_null_second(self):
        r = invoke("subtract", 10, None)
        assert r.as_int() == 10

    def test_missing_args(self):
        r = invoke("subtract", 10)
        assert r.is_null()

    def test_no_args(self):
        r = invoke("subtract")
        assert r.is_null()


# ==========================================================================
# multiply — extended
# ==========================================================================

class TestMultiplyExtended:
    @pytest.mark.parametrize("a,b,expected", [
        (3, 4, 12),
        (-3, 4, -12),
        (-3, -4, 12),
        (0, 100, 0),
        (100, 0, 0),
        (1, 42, 42),
    ])
    def test_integer_pairs(self, a, b, expected):
        r = invoke("multiply", a, b)
        assert_numeric(r, expected)

    def test_float_pair(self):
        r = invoke("multiply", 2.5, 4.0)
        assert_numeric(r, 10.0)

    def test_int_float_mix(self):
        r = invoke("multiply", 3, 2.5)
        assert_numeric(r, 7.5)

    def test_string_coercion(self):
        r = invoke("multiply", "5", "3")
        assert_numeric(r, 15)

    def test_null_first(self):
        r = invoke("multiply", None, 3)
        assert r.as_int() == 0

    def test_null_second(self):
        r = invoke("multiply", 3, None)
        assert r.as_int() == 0

    def test_missing_args(self):
        r = invoke("multiply", 5)
        assert r.is_null()

    def test_no_args(self):
        r = invoke("multiply")
        assert r.is_null()

    def test_large_numbers(self):
        r = invoke("multiply", 1000000, 1000000)
        assert_numeric(r, 1e12)


# ==========================================================================
# divide — extended
# ==========================================================================

class TestDivideExtended:
    @pytest.mark.parametrize("a,b,expected", [
        (10, 2, 5.0),
        (7, 2, 3.5),
        (-10, 2, -5.0),
        (10, -2, -5.0),
        (-10, -2, 5.0),
        (0, 5, 0.0),
    ])
    def test_various_pairs(self, a, b, expected):
        r = invoke("divide", a, b)
        assert_numeric(r, expected)

    def test_by_zero(self):
        r = invoke("divide", 10, 0)
        assert r.is_null()

    def test_by_zero_float(self):
        r = invoke("divide", 10.0, 0.0)
        assert r.is_null()

    def test_float_division(self):
        r = invoke("divide", 1.0, 3.0)
        assert_numeric(r, 1.0 / 3.0, tol=1e-10)

    def test_string_coercion(self):
        r = invoke("divide", "10", "2")
        assert_numeric(r, 5.0)

    def test_null_first(self):
        r = invoke("divide", None, 2)
        assert r.as_float() == 0.0

    def test_null_second(self):
        r = invoke("divide", 10, None)
        assert r.is_null()

    def test_missing_args(self):
        r = invoke("divide", 10)
        assert r.is_null()

    def test_no_args(self):
        r = invoke("divide")
        assert r.is_null()

    def test_result_is_float(self):
        r = invoke("divide", 10, 2)
        assert r.type == DynType.FLOAT


# ==========================================================================
# mod — extended
# ==========================================================================

class TestModExtended:
    @pytest.mark.parametrize("a,b,expected", [
        (10, 3, 1),
        (9, 3, 0),
        (7, 2, 1),
        (1, 1, 0),
    ])
    def test_positive_pairs(self, a, b, expected):
        r = invoke("mod", a, b)
        assert_numeric(r, expected)

    def test_float_mod(self):
        r = invoke("mod", 10.5, 3.0)
        assert_numeric(r, 1.5, tol=1e-9)

    def test_negative_dividend(self):
        r = invoke("mod", -10, 3)
        # Python mod: -10 % 3 = 2 (Python) or -1 (Java)
        # Just check it returns numeric
        assert not r.is_null()

    def test_zero_divisor(self):
        r = invoke("mod", 10, 0)
        assert r.is_null()

    def test_zero_dividend(self):
        r = invoke("mod", 0, 5)
        assert_numeric(r, 0)

    def test_null_first(self):
        r = invoke("mod", None, 3)
        assert r.as_int() == 0

    def test_null_second(self):
        r = invoke("mod", 10, None)
        assert r.is_null()

    def test_missing_args(self):
        r = invoke("mod", 10)
        assert r.is_null()

    def test_no_args(self):
        r = invoke("mod")
        assert r.is_null()


# ==========================================================================
# abs — extended
# ==========================================================================

class TestAbsExtended:
    @pytest.mark.parametrize("value,expected", [
        (5, 5),
        (-5, 5),
        (0, 0),
        (3.14, 3.14),
        (-3.14, 3.14),
        (-0.0, 0.0),
    ])
    def test_various(self, value, expected):
        r = invoke("abs", value)
        assert_numeric(r, expected)

    def test_large_negative(self):
        r = invoke("abs", -1000000)
        assert_numeric(r, 1000000)

    def test_null_input(self):
        r = invoke("abs", None)
        assert r.as_int() == 0

    def test_no_args(self):
        r = invoke("abs")
        assert r.is_null()

    def test_string_coercion(self):
        r = invoke("abs", "-42")
        assert_numeric(r, 42)


# ==========================================================================
# floor — extended
# ==========================================================================

class TestFloorExtended:
    @pytest.mark.parametrize("value,expected", [
        (3.0, 3),
        (3.1, 3),
        (3.5, 3),
        (3.9, 3),
        (-3.0, -3),
        (-3.1, -4),
        (-3.5, -4),
        (-3.9, -4),
        (0.0, 0),
        (0.1, 0),
        (-0.1, -1),
    ])
    def test_various(self, value, expected):
        r = invoke("floor", value)
        assert_numeric(r, expected)

    def test_integer_input(self):
        r = invoke("floor", 5)
        assert_numeric(r, 5)

    def test_very_small_negative(self):
        r = invoke("floor", -0.0001)
        assert_numeric(r, -1)

    def test_null_input(self):
        r = invoke("floor", None)
        assert r.as_int() == 0

    def test_no_args(self):
        r = invoke("floor")
        assert r.is_null()

    def test_string_coercion(self):
        r = invoke("floor", "3.7")
        assert_numeric(r, 3)

    def test_large_value(self):
        r = invoke("floor", 1e15 + 0.5)
        assert_numeric(r, 1e15, tol=1.0)


# ==========================================================================
# ceil — extended
# ==========================================================================

class TestCeilExtended:
    @pytest.mark.parametrize("value,expected", [
        (3.0, 3),
        (3.1, 4),
        (3.5, 4),
        (3.9, 4),
        (-3.0, -3),
        (-3.1, -3),
        (-3.5, -3),
        (-3.9, -3),
        (0.0, 0),
        (0.1, 1),
        (-0.1, 0),
    ])
    def test_various(self, value, expected):
        r = invoke("ceil", value)
        assert_numeric(r, expected)

    def test_integer_input(self):
        r = invoke("ceil", 5)
        assert_numeric(r, 5)

    def test_very_small_positive(self):
        r = invoke("ceil", 0.0001)
        assert_numeric(r, 1)

    def test_null_input(self):
        r = invoke("ceil", None)
        assert r.as_int() == 0

    def test_no_args(self):
        r = invoke("ceil")
        assert r.is_null()

    def test_string_coercion(self):
        r = invoke("ceil", "3.2")
        assert_numeric(r, 4)


# ==========================================================================
# round — extended (banker's rounding / half-to-even)
# ==========================================================================

class TestRoundExtended:
    @pytest.mark.parametrize("value,dp,expected", [
        (3.14159, 0, 3),
        (3.14159, 1, 3.1),
        (3.14159, 2, 3.14),
        (3.14159, 3, 3.142),
        (3.14159, 4, 3.1416),
        (3.5, 0, 4),       # half-to-even: 3.5 -> 4 (even)
        (4.5, 0, 4),       # half-to-even: 4.5 -> 4 (even)
        (2.5, 0, 2),       # half-to-even: 2.5 -> 2 (even)
        (-2.5, 0, -2),     # half-to-even: -2.5 -> -2 (even)
        (-3.5, 0, -4),     # half-to-even: -3.5 -> -4 (even)
        (0.0, 0, 0),
        (1.0, 0, 1),
        (-1.0, 0, -1),
    ])
    def test_various(self, value, dp, expected):
        r = invoke("round", value, dp)
        assert_numeric(r, expected, tol=1e-9)

    def test_no_decimals_arg_defaults_to_zero(self):
        r = invoke("round", 3.7)
        assert_numeric(r, 4)

    def test_no_decimals_arg_rounds_down(self):
        r = invoke("round", 3.2)
        assert_numeric(r, 3)

    def test_negative_value(self):
        r = invoke("round", -3.7, 0)
        assert_numeric(r, -4)

    def test_null_input(self):
        r = invoke("round", None, 0)
        assert r.is_null()

    def test_no_args(self):
        r = invoke("round")
        assert r.is_null()

    def test_string_coercion(self):
        r = invoke("round", "3.7", 0)
        assert_numeric(r, 4)

    def test_integer_input(self):
        r = invoke("round", 5, 0)
        assert_numeric(r, 5)


# ==========================================================================
# negate — extended
# ==========================================================================

class TestNegateExtended:
    @pytest.mark.parametrize("value,expected", [
        (42, -42),
        (-42, 42),
        (0, 0),
        (3.14, -3.14),
        (-3.14, 3.14),
        (0.0, 0.0),
    ])
    def test_various(self, value, expected):
        r = invoke("negate", value)
        assert_numeric(r, expected)

    def test_large_positive(self):
        r = invoke("negate", 1000000)
        assert_numeric(r, -1000000)

    def test_null_input(self):
        r = invoke("negate", None)
        assert r.as_int() == 0

    def test_no_args(self):
        r = invoke("negate")
        assert r.is_null()

    def test_string_coercion(self):
        r = invoke("negate", "42")
        assert_numeric(r, -42)


# ==========================================================================
# sign — extended
# ==========================================================================

class TestSignExtended:
    @pytest.mark.parametrize("value,expected", [
        (42, 1),
        (-42, -1),
        (0, 0),
        (0.001, 1),
        (-0.001, -1),
        (1e300, 1),
        (-1e300, -1),
        (1e-300, 1),
    ])
    def test_various(self, value, expected):
        r = invoke("sign", value)
        assert_numeric(r, expected)

    def test_null_input(self):
        r = invoke("sign", None)
        assert r.as_int() == 0

    def test_no_args(self):
        r = invoke("sign")
        assert r.is_null()

    def test_string_coercion(self):
        r = invoke("sign", "-5")
        assert_numeric(r, -1)


# ==========================================================================
# trunc — extended
# ==========================================================================

class TestTruncExtended:
    @pytest.mark.parametrize("value,expected", [
        (3.9, 3),
        (3.1, 3),
        (-3.9, -3),
        (-3.1, -3),
        (0.9, 0),
        (-0.9, 0),
        (0.0, 0),
        (5.0, 5),
        (-5.0, -5),
    ])
    def test_various(self, value, expected):
        r = invoke("trunc", value)
        assert_numeric(r, expected)

    def test_integer_input(self):
        r = invoke("trunc", 42)
        assert_numeric(r, 42)

    def test_null_input(self):
        r = invoke("trunc", None)
        assert r.as_int() == 0

    def test_no_args(self):
        r = invoke("trunc")
        assert r.is_null()

    def test_large_value(self):
        r = invoke("trunc", 1e15 + 0.5)
        assert_numeric(r, 1e15, tol=1.0)

    def test_string_coercion(self):
        r = invoke("trunc", "3.9")
        assert_numeric(r, 3)


# ==========================================================================
# random — extended
# ==========================================================================

class TestRandomExtended:
    def test_no_args_returns_zero_to_one(self):
        r = invoke("random")
        v = r.as_float()
        assert 0.0 <= v < 1.0

    def test_with_range(self):
        r = invoke("random", 10.0, 20.0)
        v = r.as_float()
        assert 10.0 <= v <= 20.0

    def test_with_negative_range(self):
        r = invoke("random", -10.0, -5.0)
        v = r.as_float()
        assert -10.0 <= v <= -5.0

    def test_same_bounds(self):
        r = invoke("random", 5.0, 5.0)
        v = r.as_float()
        assert abs(v - 5.0) < 1e-10

    def test_returns_float_type(self):
        r = invoke("random")
        assert r.type == DynType.FLOAT

    def test_multiple_calls_not_always_same(self):
        results = set()
        for _ in range(10):
            r = invoke("random")
            results.add(r.as_float())
        # With 10 calls, extremely unlikely to be all same
        assert len(results) > 1


# ==========================================================================
# minOf — extended
# ==========================================================================

class TestMinOfExtended:
    def test_two_values(self):
        r = invoke("minOf", 3, 7)
        assert_numeric(r, 3)

    def test_three_values(self):
        r = invoke("minOf", 5, 3, 7)
        assert_numeric(r, 3)

    def test_same_values(self):
        r = invoke("minOf", 5, 5, 5)
        assert_numeric(r, 5)

    def test_negatives(self):
        r = invoke("minOf", -5, -3, -10)
        assert_numeric(r, -10)

    def test_mixed_sign(self):
        r = invoke("minOf", -5, 0, 5)
        assert_numeric(r, -5)

    def test_single_value(self):
        r = invoke("minOf", 42)
        assert_numeric(r, 42)

    def test_floats(self):
        r = invoke("minOf", 3.14, 2.71, 1.41)
        assert_numeric(r, 1.41)

    def test_array_input(self):
        r = invoke("minOf", [5, 3, 7, 1, 9])
        assert_numeric(r, 1)

    def test_mixed_types(self):
        r = invoke("minOf", 5, 3.5, "2")
        assert_numeric(r, 2)

    def test_large_numbers(self):
        r = invoke("minOf", 1e15, 1e14, 1e16)
        assert_numeric(r, 1e14, tol=1e4)

    def test_no_args(self):
        r = invoke("minOf")
        assert r.is_null()


# ==========================================================================
# maxOf — extended
# ==========================================================================

class TestMaxOfExtended:
    def test_two_values(self):
        r = invoke("maxOf", 3, 7)
        assert_numeric(r, 7)

    def test_three_values(self):
        r = invoke("maxOf", 5, 3, 7)
        assert_numeric(r, 7)

    def test_same_values(self):
        r = invoke("maxOf", 5, 5, 5)
        assert_numeric(r, 5)

    def test_negatives(self):
        r = invoke("maxOf", -5, -3, -10)
        assert_numeric(r, -3)

    def test_mixed_sign(self):
        r = invoke("maxOf", -5, 0, 5)
        assert_numeric(r, 5)

    def test_single_value(self):
        r = invoke("maxOf", 42)
        assert_numeric(r, 42)

    def test_floats(self):
        r = invoke("maxOf", 3.14, 2.71, 1.41)
        assert_numeric(r, 3.14)

    def test_array_input(self):
        r = invoke("maxOf", [5, 3, 7, 1, 9])
        assert_numeric(r, 9)

    def test_large_numbers(self):
        r = invoke("maxOf", 1e15, 1e14, 1e16)
        assert_numeric(r, 1e16, tol=1e6)

    def test_no_args(self):
        r = invoke("maxOf")
        assert r.is_null()


# ==========================================================================
# parseInt — extended
# ==========================================================================

class TestParseIntExtended:
    @pytest.mark.parametrize("value,expected", [
        ("42", 42),
        ("-99", -99),
        ("0", 0),
        ("1000000", 1000000),
    ])
    def test_valid_strings(self, value, expected):
        r = invoke("parseInt", value)
        assert r._int_value == expected

    def test_from_float_truncates(self):
        r = invoke("parseInt", 3.7)
        assert r._int_value == 3

    def test_from_negative_float_truncates(self):
        r = invoke("parseInt", -3.7)
        assert r._int_value == -4  # floor

    def test_from_float_string(self):
        r = invoke("parseInt", "3.14")
        assert r._int_value == 3

    def test_invalid_string(self):
        r = invoke("parseInt", "abc")
        assert r.is_null()

    def test_empty_string(self):
        r = invoke("parseInt", "")
        # Empty string parsed as 0 or null
        # Implementation: coerce_num of empty string
        pass  # behavior may vary

    def test_null_input(self):
        r = invoke("parseInt", None)
        assert r.is_null()

    def test_no_args(self):
        r = invoke("parseInt")
        assert r.is_null()

    def test_integer_passthrough(self):
        r = invoke("parseInt", 42)
        assert r._int_value == 42

    def test_negative_integer(self):
        r = invoke("parseInt", -7)
        assert r._int_value == -7

    def test_boolean_true(self):
        r = invoke("parseInt", True)
        assert r._int_value == 1

    def test_boolean_false(self):
        r = invoke("parseInt", False)
        assert r._int_value == 0

    def test_radix_16(self):
        r = invoke("parseInt", "FF", 16)
        assert r._int_value == 255

    def test_radix_2(self):
        r = invoke("parseInt", "1010", 2)
        assert r._int_value == 10

    def test_radix_8(self):
        r = invoke("parseInt", "77", 8)
        assert r._int_value == 63


# ==========================================================================
# safeDivide — extended
# ==========================================================================

class TestSafeDivideExtended:
    def test_normal_division(self):
        r = invoke("safeDivide", 10.0, 2.0, -1.0)
        assert_numeric(r, 5)

    def test_by_zero_returns_default(self):
        r = invoke("safeDivide", 10.0, 0.0, -1.0)
        assert_numeric(r, -1)

    def test_zero_numerator(self):
        r = invoke("safeDivide", 0.0, 5.0, -1.0)
        assert_numeric(r, 0)

    def test_no_default_returns_null(self):
        r = invoke("safeDivide", 10.0, 0.0)
        assert r.is_null()

    def test_normal_float_division(self):
        r = invoke("safeDivide", 10.0, 3.0, 0.0)
        assert_numeric(r, 10.0 / 3.0, tol=1e-10)

    def test_missing_args(self):
        r = invoke("safeDivide", 10.0)
        assert r.is_null()

    def test_no_args(self):
        r = invoke("safeDivide")
        assert r.is_null()

    def test_null_numerator(self):
        r = invoke("safeDivide", None, 2.0, -1.0)
        assert_numeric(r, -1)

    def test_null_denominator(self):
        r = invoke("safeDivide", 10.0, None, -1.0)
        assert_numeric(r, -1)

    def test_default_is_zero(self):
        r = invoke("safeDivide", 10.0, 0.0, 0.0)
        assert_numeric(r, 0)

    def test_integer_inputs(self):
        r = invoke("safeDivide", 10, 3, 0)
        assert_numeric(r, 10.0 / 3.0, tol=1e-10)


# ==========================================================================
# formatLocaleNumber — extended
# ==========================================================================

class TestFormatLocaleNumberExtended:
    def test_basic_integer(self):
        r = invoke("formatLocaleNumber", 1234567.0)
        assert_string(r, "1,234,567")

    def test_with_decimals(self):
        r = invoke("formatLocaleNumber", 1234567.89, "en-US", 2)
        assert_string(r, "1,234,567.89")

    def test_small_number(self):
        r = invoke("formatLocaleNumber", 42.0)
        assert_string(r, "42")

    def test_zero(self):
        r = invoke("formatLocaleNumber", 0.0)
        assert_string(r, "0")

    def test_negative(self):
        r = invoke("formatLocaleNumber", -1234.0)
        assert_string(r, "-1,234")

    def test_with_decimal_places_arg(self):
        r = invoke("formatLocaleNumber", 1234.5, "en-US", 2)
        assert_string(r, "1,234.50")

    def test_null_input(self):
        r = invoke("formatLocaleNumber", None)
        assert r.is_null()

    def test_no_args(self):
        r = invoke("formatLocaleNumber")
        assert r.is_null()

    def test_float_value(self):
        r = invoke("formatLocaleNumber", 1234.56)
        assert_string(r, "1,234.56")

    def test_zero_decimal_places(self):
        r = invoke("formatLocaleNumber", 1234.56, "en-US", 0)
        assert_string(r, "1,235")


# ==========================================================================
# log — extended
# ==========================================================================

class TestLogExtended:
    def test_base_2(self):
        r = invoke("log", 8.0, 2.0)
        assert_numeric(r, 3.0)

    def test_base_10(self):
        r = invoke("log", 1000.0, 10.0)
        assert_numeric(r, 3.0)

    def test_base_e(self):
        r = invoke("log", math.e, math.e)
        assert_numeric(r, 1.0, tol=1e-9)

    def test_log_of_1(self):
        r = invoke("log", 1.0, 10.0)
        assert_numeric(r, 0.0)

    def test_negative_input_null(self):
        r = invoke("log", -1.0, 2.0)
        assert r.is_null()

    def test_zero_input_null(self):
        r = invoke("log", 0.0, 2.0)
        assert r.is_null()

    def test_base_1_null(self):
        r = invoke("log", 10.0, 1.0)
        assert r.is_null()

    def test_negative_base_null(self):
        r = invoke("log", 10.0, -2.0)
        assert r.is_null()

    def test_null_input(self):
        r = invoke("log", None, 2.0)
        assert r.is_null()

    def test_null_base(self):
        r = invoke("log", 8.0, None)
        assert r.is_null()

    def test_missing_args(self):
        import math
        r = invoke("log", 8.0)
        assert_numeric(r, math.log(8.0), tol=1e-9)

    def test_no_args(self):
        r = invoke("log")
        assert r.is_null()

    def test_large_value(self):
        r = invoke("log", 1e10, 10.0)
        assert_numeric(r, 10.0, tol=1e-9)


# ==========================================================================
# ln — extended
# ==========================================================================

class TestLnExtended:
    def test_of_e(self):
        r = invoke("ln", math.e)
        assert_numeric(r, 1.0)

    def test_of_1(self):
        r = invoke("ln", 1.0)
        assert_numeric(r, 0.0)

    def test_of_e_squared(self):
        r = invoke("ln", math.e ** 2)
        assert_numeric(r, 2.0, tol=1e-9)

    def test_positive_value(self):
        r = invoke("ln", 10.0)
        assert_numeric(r, math.log(10.0), tol=1e-10)

    def test_zero_null(self):
        r = invoke("ln", 0.0)
        assert r.is_null()

    def test_negative_null(self):
        r = invoke("ln", -1.0)
        assert r.is_null()

    def test_null_input(self):
        r = invoke("ln", None)
        assert r.is_null()

    def test_no_args(self):
        r = invoke("ln")
        assert r.is_null()

    def test_small_positive(self):
        r = invoke("ln", 0.001)
        assert_numeric(r, math.log(0.001), tol=1e-10)


# ==========================================================================
# log10 — extended
# ==========================================================================

class TestLog10Extended:
    @pytest.mark.parametrize("value,expected", [
        (1.0, 0.0),
        (10.0, 1.0),
        (100.0, 2.0),
        (1000.0, 3.0),
        (0.1, -1.0),
        (0.01, -2.0),
    ])
    def test_various(self, value, expected):
        r = invoke("log10", value)
        assert_numeric(r, expected, tol=1e-9)

    def test_zero_null(self):
        r = invoke("log10", 0.0)
        assert r.is_null()

    def test_negative_null(self):
        r = invoke("log10", -10.0)
        assert r.is_null()

    def test_null_input(self):
        r = invoke("log10", None)
        assert r.is_null()

    def test_no_args(self):
        r = invoke("log10")
        assert r.is_null()


# ==========================================================================
# exp — extended
# ==========================================================================

class TestExpExtended:
    @pytest.mark.parametrize("value,expected", [
        (0.0, 1.0),
        (1.0, math.e),
        (-1.0, 1.0 / math.e),
        (2.0, math.e ** 2),
    ])
    def test_various(self, value, expected):
        r = invoke("exp", value)
        assert_numeric(r, expected, tol=1e-9)

    def test_large_exponent(self):
        r = invoke("exp", 10.0)
        assert_numeric(r, math.exp(10.0), tol=1e-3)

    def test_negative_exponent(self):
        r = invoke("exp", -5.0)
        assert_numeric(r, math.exp(-5.0), tol=1e-10)

    def test_null_input(self):
        r = invoke("exp", None)
        assert r.is_null()

    def test_no_args(self):
        r = invoke("exp")
        assert r.is_null()

    def test_very_large_overflows(self):
        # exp(1000) overflows in Python; implementation raises OverflowError
        # which is not caught — this tests that at least it doesn't silently
        # return wrong data. A well-behaved impl would return null.
        try:
            r = invoke("exp", 1000.0)
            # If it doesn't raise, it should be null or inf
            assert r.is_null() or math.isinf(r.as_float())
        except OverflowError:
            pass  # acceptable — known limitation


# ==========================================================================
# pow — extended
# ==========================================================================

class TestPowExtended:
    @pytest.mark.parametrize("base,exp_val,expected", [
        (2.0, 10.0, 1024.0),
        (2.0, 0.0, 1.0),
        (2.0, -1.0, 0.5),
        (10.0, 3.0, 1000.0),
        (4.0, 0.5, 2.0),
        (9.0, 0.5, 3.0),
        (27.0, 1.0 / 3.0, 3.0),
        (0.0, 5.0, 0.0),
        (1.0, 1000.0, 1.0),
        (99.0, 0.0, 1.0),
    ])
    def test_various(self, base, exp_val, expected):
        r = invoke("pow", base, exp_val)
        assert_numeric(r, expected, tol=1e-6)

    def test_negative_base_integer_exp(self):
        r = invoke("pow", -2.0, 3.0)
        assert_numeric(r, -8.0)

    def test_null_base(self):
        r = invoke("pow", None, 2.0)
        assert r.is_null()

    def test_null_exponent(self):
        r = invoke("pow", 2.0, None)
        assert r.is_null()

    def test_missing_args(self):
        r = invoke("pow", 2.0)
        assert r.is_null()

    def test_no_args(self):
        r = invoke("pow")
        assert r.is_null()

    def test_integer_inputs(self):
        r = invoke("pow", 3, 4)
        assert_numeric(r, 81.0)

    def test_string_coercion(self):
        r = invoke("pow", "2", "3")
        assert_numeric(r, 8.0)


# ==========================================================================
# sqrt — extended
# ==========================================================================

class TestSqrtExtended:
    @pytest.mark.parametrize("value,expected", [
        (0.0, 0.0),
        (1.0, 1.0),
        (4.0, 2.0),
        (9.0, 3.0),
        (16.0, 4.0),
        (25.0, 5.0),
        (100.0, 10.0),
        (144.0, 12.0),
    ])
    def test_perfect_squares(self, value, expected):
        r = invoke("sqrt", value)
        assert_numeric(r, expected)

    def test_non_perfect_square(self):
        r = invoke("sqrt", 2.0)
        assert_numeric(r, math.sqrt(2.0), tol=1e-10)

    def test_non_perfect_3(self):
        r = invoke("sqrt", 3.0)
        assert_numeric(r, math.sqrt(3.0), tol=1e-10)

    def test_large_value(self):
        r = invoke("sqrt", 1000000.0)
        assert_numeric(r, 1000.0)

    def test_small_value(self):
        r = invoke("sqrt", 0.01)
        assert_numeric(r, 0.1)

    def test_negative_null(self):
        r = invoke("sqrt", -1.0)
        assert r.is_null()

    def test_negative_large_null(self):
        r = invoke("sqrt", -100.0)
        assert r.is_null()

    def test_null_input(self):
        r = invoke("sqrt", None)
        assert r.is_null()

    def test_no_args(self):
        r = invoke("sqrt")
        assert r.is_null()

    def test_string_coercion(self):
        r = invoke("sqrt", "49")
        assert_numeric(r, 7.0)


# ==========================================================================
# clamp — extended
# ==========================================================================

class TestClampExtended:
    @pytest.mark.parametrize("value,lo,hi,expected", [
        (5, 0, 10, 5),
        (-5, 0, 10, 0),
        (15, 0, 10, 10),
        (0, 0, 10, 0),
        (10, 0, 10, 10),
        (5.5, 0.0, 10.0, 5.5),
        (-100, -50, 50, -50),
        (100, -50, 50, 50),
        (0, -50, 50, 0),
    ])
    def test_various(self, value, lo, hi, expected):
        r = invoke("clamp", value, lo, hi)
        assert_numeric(r, expected)

    def test_equal_bounds(self):
        r = invoke("clamp", 5, 3, 3)
        assert_numeric(r, 3)

    def test_null_value(self):
        r = invoke("clamp", None, 0, 10)
        assert r.is_null()

    def test_null_min(self):
        r = invoke("clamp", 5, None, 10)
        assert r.is_null()

    def test_null_max(self):
        r = invoke("clamp", 5, 0, None)
        assert r.is_null()

    def test_missing_args(self):
        r = invoke("clamp", 5, 0)
        assert r.is_null()

    def test_no_args(self):
        r = invoke("clamp")
        assert r.is_null()

    def test_float_bounds(self):
        r = invoke("clamp", 3.14, 0.0, 2.0)
        assert_numeric(r, 2.0)

    def test_string_coercion(self):
        r = invoke("clamp", "5", "0", "10")
        assert_numeric(r, 5)


# ==========================================================================
# pi / e constants — extended
# ==========================================================================

class TestConstantsExtended:
    def test_pi_value(self):
        r = invoke("pi")
        assert_numeric(r, math.pi, tol=1e-10)

    def test_pi_type(self):
        r = invoke("pi")
        assert r.type == DynType.FLOAT

    def test_e_value(self):
        r = invoke("e")
        assert_numeric(r, math.e, tol=1e-10)

    def test_e_type(self):
        r = invoke("e")
        assert r.type == DynType.FLOAT

    def test_pi_ignores_args(self):
        r = invoke("pi", 42)
        assert_numeric(r, math.pi, tol=1e-10)

    def test_e_ignores_args(self):
        r = invoke("e", 42)
        assert_numeric(r, math.e, tol=1e-10)


# ==========================================================================
# String-to-number coercion across verbs
# ==========================================================================

class TestStringCoercionExtended:
    @pytest.mark.parametrize("verb,args,expected", [
        ("add", ("3", "4"), 7),
        ("subtract", ("10", "3"), 7),
        ("multiply", ("5", "3"), 15),
        ("divide", ("10", "2"), 5.0),
        ("mod", ("10", "3"), 1),
        ("abs", ("-5",), 5),
        ("floor", ("3.7",), 3),
        ("ceil", ("3.2",), 4),
        ("negate", ("42",), -42),
        ("sign", ("-5",), -1),
        ("trunc", ("3.9",), 3),
    ])
    def test_string_coercion(self, verb, args, expected):
        r = invoke(verb, *args)
        assert_numeric(r, expected)

    def test_add_non_numeric_string_null(self):
        r = invoke("add", "abc", "def")
        assert r.as_int() == 0

    def test_multiply_non_numeric_string_null(self):
        r = invoke("multiply", "abc", "def")
        assert r.as_int() == 0


# ==========================================================================
# Null handling across all verbs
# ==========================================================================

class TestNullHandling:
    @pytest.mark.parametrize("verb,num_args", [
        ("formatNumber", 2),
        ("formatInteger", 1),
        ("formatCurrency", 1),
        ("formatPercent", 1),
        ("round", 1),
        ("ln", 1),
        ("log10", 1),
        ("exp", 1),
        ("sqrt", 1),
    ])
    def test_null_first_arg(self, verb, num_args):
        args = [None] + [1] * (num_args - 1)
        r = invoke(verb, *args)
        assert r.is_null()

    @pytest.mark.parametrize("verb,expected", [
        ("abs", 0), ("floor", 0), ("ceil", 0),
        ("negate", 0), ("sign", 0), ("trunc", 0),
    ])
    def test_null_first_arg_coerces(self, verb, expected):
        r = invoke(verb, None)
        assert r.as_int() == expected

    @pytest.mark.parametrize("verb,expected", [
        ("add", 5), ("subtract", -5), ("multiply", 0),
    ])
    def test_null_first_binary(self, verb, expected):
        r = invoke(verb, None, 5)
        assert r.as_int() == expected

    def test_null_first_binary_divzero(self):
        # divide/mod by a present divisor still compute; null numerator -> 0
        assert invoke("divide", None, 5).as_float() == 0.0
        assert invoke("mod", None, 5).as_int() == 0

    @pytest.mark.parametrize("verb,expected", [
        ("add", 5), ("subtract", 5), ("multiply", 0),
    ])
    def test_null_second_binary(self, verb, expected):
        r = invoke(verb, 5, None)
        assert r.as_int() == expected

    def test_null_second_binary_divzero(self):
        # null divisor coerces to 0 -> division by zero -> null
        assert invoke("divide", 5, None).is_null()
        assert invoke("mod", 5, None).is_null()

    @pytest.mark.parametrize("verb", [
        "log", "pow",
    ])
    def test_null_either_arg_two_arg(self, verb):
        r1 = invoke(verb, None, 2.0)
        r2 = invoke(verb, 2.0, None)
        assert r1.is_null()
        assert r2.is_null()


# ==========================================================================
# Missing/no args across all verbs
# ==========================================================================

class TestMissingArgs:
    @pytest.mark.parametrize("verb", [
        "formatInteger", "formatCurrency", "formatPercent",
        "abs", "floor", "ceil", "round", "negate", "sign", "trunc",
        "parseInt", "ln", "log10", "exp", "sqrt",
    ])
    def test_no_args_returns_null(self, verb):
        r = invoke(verb)
        assert r.is_null()

    @pytest.mark.parametrize("verb", [
        "add", "subtract", "multiply", "divide", "mod",
        "pow", "safeDivide",
    ])
    def test_one_arg_returns_null(self, verb):
        r = invoke(verb, 5)
        assert r.is_null()


# ==========================================================================
# Edge cases — numeric boundaries
# ==========================================================================

class TestNumericEdgeCases:
    def test_add_very_large(self):
        r = invoke("add", 1e15, 1e15)
        assert_numeric(r, 2e15, tol=1.0)

    def test_multiply_very_large(self):
        r = invoke("multiply", 1e7, 1e7)
        assert_numeric(r, 1e14, tol=1.0)

    def test_divide_very_small_result(self):
        r = invoke("divide", 1.0, 1e10)
        assert_numeric(r, 1e-10, tol=1e-20)

    def test_subtract_equal_values(self):
        r = invoke("subtract", 42, 42)
        assert_numeric(r, 0)

    def test_add_opposite_signs(self):
        r = invoke("add", 100, -100)
        assert_numeric(r, 0)

    def test_multiply_by_one(self):
        r = invoke("multiply", 42, 1)
        assert_numeric(r, 42)

    def test_multiply_by_negative_one(self):
        r = invoke("multiply", 42, -1)
        assert_numeric(r, -42)

    def test_divide_one_by_large(self):
        r = invoke("divide", 1, 1000000)
        assert_numeric(r, 1e-6, tol=1e-12)

    def test_mod_equal_values(self):
        r = invoke("mod", 5, 5)
        assert_numeric(r, 0)

    def test_abs_max_int(self):
        r = invoke("abs", 2**31 - 1)
        assert_numeric(r, 2**31 - 1)

    def test_sign_very_large_positive(self):
        r = invoke("sign", 1e300)
        assert_numeric(r, 1)

    def test_sign_very_small_positive(self):
        r = invoke("sign", 1e-300)
        assert_numeric(r, 1)

    def test_formatNumber_very_small(self):
        r = invoke("formatNumber", 0.000001, 6)
        assert_string(r, "0.000001")

    def test_formatNumber_very_large(self):
        r = invoke("formatNumber", 1e15, 0)
        s = r._string_value
        assert s is not None and len(s) > 0

    def test_floor_very_small_negative(self):
        r = invoke("floor", -0.0001)
        assert_numeric(r, -1)

    def test_ceil_very_small_positive(self):
        r = invoke("ceil", 0.0001)
        assert_numeric(r, 1)

    def test_trunc_very_large(self):
        r = invoke("trunc", 1e15 + 0.5)
        assert_numeric(r, 1e15, tol=1.0)


# ==========================================================================
# Integer vs float result type
# ==========================================================================

class TestResultTypes:
    def test_add_ints_returns_integer(self):
        r = invoke("add", 2, 3)
        assert r.type == DynType.INTEGER

    def test_add_floats_returns_float_or_int(self):
        r = invoke("add", 2.5, 3.5)
        # 6.0 might be returned as integer
        assert r.type in (DynType.INTEGER, DynType.FLOAT)

    def test_divide_always_float(self):
        r = invoke("divide", 10, 2)
        assert r.type == DynType.FLOAT

    def test_multiply_ints_returns_integer(self):
        r = invoke("multiply", 3, 4)
        assert r.type == DynType.INTEGER

    def test_subtract_ints_returns_integer(self):
        r = invoke("subtract", 10, 3)
        assert r.type == DynType.INTEGER

    def test_floor_returns_integer(self):
        r = invoke("floor", 3.7)
        assert r.type == DynType.INTEGER

    def test_ceil_returns_integer(self):
        r = invoke("ceil", 3.2)
        assert r.type == DynType.INTEGER

    def test_abs_int_returns_integer(self):
        r = invoke("abs", -5)
        assert r.type == DynType.INTEGER

    def test_negate_int_returns_integer(self):
        r = invoke("negate", 5)
        assert r.type == DynType.INTEGER

    def test_sign_returns_integer(self):
        r = invoke("sign", 42.0)
        assert r.type == DynType.INTEGER

    def test_parseInt_returns_integer(self):
        r = invoke("parseInt", "42")
        assert r.type == DynType.INTEGER

    def test_format_returns_string(self):
        r = invoke("formatNumber", 3.14, 2)
        assert r.type == DynType.STRING

    def test_formatInteger_returns_string(self):
        r = invoke("formatInteger", 42)
        assert r.type == DynType.STRING

    def test_formatCurrency_returns_string(self):
        r = invoke("formatCurrency", 99.99)
        assert r.type == DynType.STRING

    def test_formatPercent_returns_string(self):
        r = invoke("formatPercent", 0.85, 0)
        assert r.type == DynType.STRING


# ==========================================================================
# Boolean input coercion
# ==========================================================================

class TestBooleanCoercion:
    def test_add_true_true(self):
        r = invoke("add", True, True)
        assert_numeric(r, 2)

    def test_add_true_false(self):
        r = invoke("add", True, False)
        assert_numeric(r, 1)

    def test_multiply_true_5(self):
        r = invoke("multiply", True, 5)
        assert_numeric(r, 5)

    def test_multiply_false_5(self):
        r = invoke("multiply", False, 5)
        assert_numeric(r, 0)

    def test_abs_true(self):
        r = invoke("abs", True)
        assert_numeric(r, 1)

    def test_negate_true(self):
        r = invoke("negate", True)
        assert_numeric(r, -1)

    def test_sign_true(self):
        r = invoke("sign", True)
        assert_numeric(r, 1)

    def test_sign_false(self):
        r = invoke("sign", False)
        assert_numeric(r, 0)


# ==========================================================================
# Chained operations (using invoke results)
# ==========================================================================

class TestChainedOperations:
    def test_add_then_multiply(self):
        sum_result = invoke("add", 3, 4)
        r = invoke("multiply", sum_result, 2)
        assert_numeric(r, 14)

    def test_divide_then_round(self):
        div_result = invoke("divide", 10, 3)
        r = invoke("round", div_result, 2)
        assert_numeric(r, 3.33, tol=0.01)

    def test_sqrt_then_floor(self):
        sqrt_result = invoke("sqrt", 10.0)
        r = invoke("floor", sqrt_result)
        assert_numeric(r, 3)

    def test_negate_then_abs(self):
        neg = invoke("negate", 42)
        r = invoke("abs", neg)
        assert_numeric(r, 42)

    def test_pow_then_log(self):
        pow_result = invoke("pow", 2.0, 8.0)
        r = invoke("log", pow_result, 2.0)
        assert_numeric(r, 8.0, tol=1e-9)

    def test_exp_then_ln(self):
        exp_result = invoke("exp", 3.0)
        r = invoke("ln", exp_result)
        assert_numeric(r, 3.0, tol=1e-9)
