"""Tests for numeric verbs."""

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


# ── formatNumber ─────────────────────────────────────────────────────

class TestFormatNumber:
    def test_zero_decimals(self):
        r = invoke("formatNumber", 3.14159, 0)
        assert r._string_value == "3"

    def test_two_decimals(self):
        r = invoke("formatNumber", 3.14159, 2)
        assert r._string_value == "3.14"

    def test_null_input(self):
        r = invoke("formatNumber", None, 2)
        assert r.is_null()

    def test_missing_args(self):
        r = invoke("formatNumber", 3.14)
        assert r.is_null()


# ── formatInteger ────────────────────────────────────────────────────

class TestFormatInteger:
    def test_basic(self):
        r = invoke("formatInteger", 3.7)
        assert r._string_value == "3"

    def test_null(self):
        r = invoke("formatInteger", None)
        assert r.is_null()


# ── formatCurrency ───────────────────────────────────────────────────

class TestFormatCurrency:
    def test_basic(self):
        r = invoke("formatCurrency", 1234.5)
        assert r._string_value == "1234.50"

    def test_null(self):
        r = invoke("formatCurrency", None)
        assert r.is_null()


# ── formatPercent ────────────────────────────────────────────────────

class TestFormatPercent:
    def test_basic(self):
        r = invoke("formatPercent", 0.85, 0)
        assert r._string_value == "85%"

    def test_with_decimals(self):
        r = invoke("formatPercent", 0.8567, 2)
        assert r._string_value == "85.67%"


# ── add, subtract, multiply, divide ─────────────────────────────────

class TestArithmetic:
    def test_add_integers(self):
        r = invoke("add", 3, 4)
        assert_numeric(r, 7)

    def test_subtract(self):
        r = invoke("subtract", 10, 3)
        assert_numeric(r, 7)

    def test_multiply(self):
        r = invoke("multiply", 3, 4)
        assert_numeric(r, 12)

    def test_divide(self):
        r = invoke("divide", 10, 2)
        assert_numeric(r, 5)

    def test_divide_by_zero(self):
        r = invoke("divide", 10, 0)
        assert r.is_null()

    def test_add_null(self):
        r = invoke("add", None, 4)
        assert r.is_null()

    def test_subtract_null(self):
        r = invoke("subtract", 10, None)
        assert r.is_null()

    def test_missing_args(self):
        r = invoke("add", 3)
        assert r.is_null()


# ── abs ──────────────────────────────────────────────────────────────

class TestAbs:
    def test_negative(self):
        r = invoke("abs", -5)
        assert_numeric(r, 5)

    def test_positive(self):
        r = invoke("abs", 5)
        assert_numeric(r, 5)

    def test_null(self):
        r = invoke("abs", None)
        assert r.is_null()


# ── floor, ceil ──────────────────────────────────────────────────────

class TestFloorCeil:
    def test_floor_positive(self):
        r = invoke("floor", 3.7)
        assert_numeric(r, 3)

    def test_floor_negative(self):
        r = invoke("floor", -3.2)
        assert_numeric(r, -4)

    def test_ceil_positive(self):
        r = invoke("ceil", 3.2)
        assert_numeric(r, 4)

    def test_ceil_negative(self):
        r = invoke("ceil", -3.7)
        assert_numeric(r, -3)


# ── round (away from zero) ──────────────────────────────────────────

class TestRound:
    def test_half_up(self):
        r = invoke("round", 2.5, 0)
        assert_numeric(r, 2)  # banker's rounding (half to even)

    def test_half_down_negative(self):
        r = invoke("round", -2.5, 0)
        assert_numeric(r, -2)  # banker's rounding (half to even)

    def test_with_decimals(self):
        r = invoke("round", 3.14159, 2)
        assert_numeric(r, 3.14)

    def test_no_decimals_arg(self):
        r = invoke("round", 3.7)
        assert_numeric(r, 4)


# ── mod ──────────────────────────────────────────────────────────────

class TestMod:
    def test_basic(self):
        r = invoke("mod", 10, 3)
        assert_numeric(r, 1)

    def test_zero_divisor(self):
        r = invoke("mod", 10, 0)
        assert r.is_null()


# ── negate, sign, trunc ──────────────────────────────────────────────

class TestMisc:
    def test_negate_positive(self):
        r = invoke("negate", 42)
        assert_numeric(r, -42)

    def test_negate_negative(self):
        r = invoke("negate", -5)
        assert_numeric(r, 5)

    def test_sign_positive(self):
        r = invoke("sign", 42.0)
        assert_numeric(r, 1)

    def test_sign_negative(self):
        r = invoke("sign", -3.0)
        assert_numeric(r, -1)

    def test_sign_zero(self):
        r = invoke("sign", 0)
        assert_numeric(r, 0)

    def test_trunc_positive(self):
        r = invoke("trunc", 3.9)
        assert_numeric(r, 3)

    def test_trunc_negative(self):
        r = invoke("trunc", -3.9)
        assert_numeric(r, -3)


# ── minOf, maxOf ─────────────────────────────────────────────────────

class TestMinMax:
    def test_min_of(self):
        r = invoke("minOf", 3, 1, 2)
        assert_numeric(r, 1)

    def test_max_of(self):
        r = invoke("maxOf", 3, 1, 2)
        assert_numeric(r, 3)

    def test_min_of_array(self):
        r = invoke("minOf", [3, 1, 2])
        assert_numeric(r, 1)

    def test_max_of_array(self):
        r = invoke("maxOf", [3, 1, 2])
        assert_numeric(r, 3)


# ── parseInt ─────────────────────────────────────────────────────────

class TestParseInt:
    def test_basic(self):
        r = invoke("parseInt", "42")
        assert r._int_value == 42

    def test_from_float(self):
        r = invoke("parseInt", 3.7)
        assert r._int_value == 3

    def test_null(self):
        r = invoke("parseInt", None)
        assert r.is_null()


# ── safeDivide ───────────────────────────────────────────────────────

class TestSafeDivide:
    def test_normal(self):
        r = invoke("safeDivide", 10.0, 2.0, -1.0)
        assert_numeric(r, 5)

    def test_by_zero(self):
        r = invoke("safeDivide", 10.0, 0.0, -1.0)
        assert_numeric(r, -1)


# ── log, ln, log10, exp, pow, sqrt ───────────────────────────────────

class TestMathFunctions:
    def test_log_base2(self):
        r = invoke("log", 8.0, 2.0)
        assert_numeric(r, 3.0)

    def test_ln_e(self):
        r = invoke("ln", math.e)
        assert_numeric(r, 1.0)

    def test_log10(self):
        r = invoke("log10", 100.0)
        assert_numeric(r, 2.0)

    def test_exp(self):
        r = invoke("exp", 0.0)
        assert_numeric(r, 1.0)

    def test_pow(self):
        r = invoke("pow", 2.0, 10.0)
        assert_numeric(r, 1024.0)

    def test_sqrt(self):
        r = invoke("sqrt", 144.0)
        assert_numeric(r, 12.0)

    def test_sqrt_negative(self):
        r = invoke("sqrt", -1.0)
        assert r.is_null()

    def test_log_negative(self):
        r = invoke("log", -1.0, 2.0)
        assert r.is_null()

    def test_ln_missing_args(self):
        r = invoke("ln")
        assert r.is_null()


# ── clamp ────────────────────────────────────────────────────────────

class TestClamp:
    def test_within_range(self):
        r = invoke("clamp", 5, 0, 10)
        assert_numeric(r, 5)

    def test_below_min(self):
        r = invoke("clamp", -5, 0, 10)
        assert_numeric(r, 0)

    def test_above_max(self):
        r = invoke("clamp", 15, 0, 10)
        assert_numeric(r, 10)


# ── pi, e ────────────────────────────────────────────────────────────

class TestConstants:
    def test_pi(self):
        r = invoke("pi")
        assert_numeric(r, math.pi, tol=1e-6)

    def test_e(self):
        r = invoke("e")
        assert_numeric(r, math.e, tol=1e-6)


# ── string coercion ──────────────────────────────────────────────────

class TestStringCoercion:
    def test_add_strings(self):
        r = invoke("add", "3", "4")
        assert_numeric(r, 7)

    def test_multiply_string(self):
        r = invoke("multiply", "5", "3")
        assert_numeric(r, 15)
