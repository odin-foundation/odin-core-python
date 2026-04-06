"""Extended tests for logic verbs: and, or, not, xor, eq, ne, lt, lte, gt, gte, between,
isNull, isString, isNumber, isBoolean, isArray, isObject, isDate, typeOf, cond, assert, switch,
isFinite, isNaN.

Ported from Java LogicVerbTest + CoreVerbExtendedTest for cross-language parity.
"""

import math
import pytest
from decimal import Decimal
from datetime import date, datetime

from odin.transform.dyn_value import DynValue, DynType
from odin.transform.engine import TransformEngine, VerbContext
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


# =============================================================================
# and -- extended
# =============================================================================

class TestAndExtended:
    """Extended and verb tests."""

    def test_true_true(self):
        assert invoke("and", True, True).as_bool() is True

    def test_true_false(self):
        assert invoke("and", True, False).as_bool() is False

    def test_false_true(self):
        assert invoke("and", False, True).as_bool() is False

    def test_false_false(self):
        assert invoke("and", False, False).as_bool() is False

    def test_too_few_args(self):
        assert invoke("and", True).is_null()

    def test_no_args(self):
        assert invoke("and").is_null()

    def test_truthy_integers(self):
        # Python impl uses is_truthy which supports non-bool
        assert invoke("and", 1, 1).as_bool() is True

    def test_truthy_int_and_falsy_zero(self):
        assert invoke("and", 1, 0).as_bool() is False

    def test_null_first_arg(self):
        assert invoke("and", None, True).as_bool() is False

    def test_null_second_arg(self):
        assert invoke("and", True, None).as_bool() is False

    def test_both_null(self):
        assert invoke("and", None, None).as_bool() is False

    def test_string_truthy(self):
        assert invoke("and", "hello", "world").as_bool() is True

    def test_empty_string_falsy(self):
        assert invoke("and", "hello", "").as_bool() is False


# =============================================================================
# or -- extended
# =============================================================================

class TestOrExtended:
    """Extended or verb tests."""

    def test_true_true(self):
        assert invoke("or", True, True).as_bool() is True

    def test_true_false(self):
        assert invoke("or", True, False).as_bool() is True

    def test_false_true(self):
        assert invoke("or", False, True).as_bool() is True

    def test_false_false(self):
        assert invoke("or", False, False).as_bool() is False

    def test_too_few_args(self):
        assert invoke("or", True).is_null()

    def test_no_args(self):
        assert invoke("or").is_null()

    def test_null_null(self):
        assert invoke("or", None, None).as_bool() is False

    def test_null_true(self):
        assert invoke("or", None, True).as_bool() is True

    def test_true_null(self):
        assert invoke("or", True, None).as_bool() is True

    def test_truthy_integers(self):
        assert invoke("or", 0, 1).as_bool() is True

    def test_both_falsy_integers(self):
        assert invoke("or", 0, 0).as_bool() is False

    def test_string_truthy(self):
        assert invoke("or", "", "hello").as_bool() is True

    def test_both_empty_strings(self):
        assert invoke("or", "", "").as_bool() is False


# =============================================================================
# not -- extended
# =============================================================================

class TestNotExtended:
    """Extended not verb tests."""

    def test_true(self):
        assert invoke("not", True).as_bool() is False

    def test_false(self):
        assert invoke("not", False).as_bool() is True

    def test_null(self):
        assert invoke("not", None).as_bool() is True

    def test_zero_int(self):
        assert invoke("not", 0).as_bool() is True

    def test_nonzero_int(self):
        assert invoke("not", 1).as_bool() is False

    def test_negative_int(self):
        assert invoke("not", -1).as_bool() is False

    def test_zero_float(self):
        assert invoke("not", 0.0).as_bool() is True

    def test_nonzero_float(self):
        assert invoke("not", 1.5).as_bool() is False

    def test_empty_string(self):
        assert invoke("not", "").as_bool() is True

    def test_nonempty_string(self):
        assert invoke("not", "hello").as_bool() is False

    def test_string_false(self):
        # "false" is a non-empty string, truthy in Python impl
        assert invoke("not", "false").as_bool() is False

    def test_empty_array(self):
        # Arrays are truthy in Java/TS -- Python follows same pattern
        assert invoke("not", _to_dyn([])).as_bool() is False

    def test_nonempty_array(self):
        assert invoke("not", [1, 2]).as_bool() is False

    def test_object(self):
        assert invoke("not", {"a": 1}).as_bool() is False

    def test_empty_object(self):
        assert invoke("not", _to_dyn({})).as_bool() is False

    def test_no_args(self):
        assert invoke("not").is_null()


# =============================================================================
# xor -- extended
# =============================================================================

class TestXorExtended:
    """Extended xor verb tests."""

    def test_true_true(self):
        assert invoke("xor", True, True).as_bool() is False

    def test_true_false(self):
        assert invoke("xor", True, False).as_bool() is True

    def test_false_true(self):
        assert invoke("xor", False, True).as_bool() is True

    def test_false_false(self):
        assert invoke("xor", False, False).as_bool() is False

    def test_too_few_args(self):
        assert invoke("xor", True).is_null()

    def test_no_args(self):
        assert invoke("xor").is_null()

    def test_null_true(self):
        # null is falsy, true is truthy -> xor = true
        assert invoke("xor", None, True).as_bool() is True

    def test_null_null(self):
        # both falsy -> xor = false
        assert invoke("xor", None, None).as_bool() is False

    def test_truthy_ints(self):
        assert invoke("xor", 1, 0).as_bool() is True

    def test_both_truthy_ints(self):
        assert invoke("xor", 1, 1).as_bool() is False


# =============================================================================
# eq -- extended
# =============================================================================

class TestEqExtended:
    """Extended eq verb tests."""

    def test_same_integers(self):
        assert invoke("eq", 5, 5).as_bool() is True

    def test_different_integers(self):
        assert invoke("eq", 5, 6).as_bool() is False

    def test_same_strings(self):
        assert invoke("eq", "abc", "abc").as_bool() is True

    def test_different_strings(self):
        assert invoke("eq", "abc", "xyz").as_bool() is False

    def test_int_float_cross(self):
        assert invoke("eq", 5, 5.0).as_bool() is True

    def test_string_int_coercion(self):
        assert invoke("eq", "42", 42).as_bool() is True

    def test_null_null(self):
        assert invoke("eq", None, None).as_bool() is True

    def test_null_vs_string(self):
        assert invoke("eq", None, "hello").as_bool() is False

    def test_null_vs_empty_string(self):
        # null coerces to "" for string comparison, so they are equal
        assert invoke("eq", None, "").as_bool() is True

    def test_bools_same(self):
        assert invoke("eq", True, True).as_bool() is True

    def test_bools_different(self):
        assert invoke("eq", True, False).as_bool() is False

    def test_floats_equal(self):
        assert invoke("eq", 3.14, 3.14).as_bool() is True

    def test_floats_not_equal(self):
        assert invoke("eq", 3.14, 2.71).as_bool() is False

    def test_too_few_args(self):
        assert invoke("eq", 42).is_null()

    def test_no_args(self):
        assert invoke("eq").is_null()

    def test_int_string_no_match(self):
        assert invoke("eq", 42, "abc").as_bool() is False

    def test_negative_integers(self):
        assert invoke("eq", -5, -5).as_bool() is True

    def test_negative_positive(self):
        assert invoke("eq", -5, 5).as_bool() is False

    def test_zero_int_zero_float(self):
        assert invoke("eq", 0, 0.0).as_bool() is True

    def test_arrays_equal(self):
        a = _to_dyn([1, 2, 3])
        b = _to_dyn([1, 2, 3])
        assert invoke("eq", a, b).as_bool() is True

    def test_arrays_different_length(self):
        a = _to_dyn([1, 2])
        b = _to_dyn([1, 2, 3])
        assert invoke("eq", a, b).as_bool() is False


# =============================================================================
# ne -- extended
# =============================================================================

class TestNeExtended:
    """Extended ne verb tests."""

    def test_different_ints(self):
        assert invoke("ne", 5, 6).as_bool() is True

    def test_same_ints(self):
        assert invoke("ne", 5, 5).as_bool() is False

    def test_cross_type(self):
        assert invoke("ne", 5, 5.0).as_bool() is False

    def test_different_strings(self):
        assert invoke("ne", "abc", "xyz").as_bool() is True

    def test_same_strings(self):
        assert invoke("ne", "abc", "abc").as_bool() is False

    def test_null_null(self):
        assert invoke("ne", None, None).as_bool() is False

    def test_null_string(self):
        assert invoke("ne", None, "x").as_bool() is True

    def test_string_null(self):
        assert invoke("ne", "x", None).as_bool() is True

    def test_too_few_args(self):
        assert invoke("ne", 5).is_null()

    def test_no_args(self):
        assert invoke("ne").is_null()


# =============================================================================
# lt -- extended
# =============================================================================

class TestLtExtended:
    """Extended lt verb tests."""

    def test_ints_less(self):
        assert invoke("lt", 3, 5).as_bool() is True

    def test_ints_equal(self):
        assert invoke("lt", 5, 5).as_bool() is False

    def test_ints_greater(self):
        assert invoke("lt", 7, 5).as_bool() is False

    def test_floats_less(self):
        assert invoke("lt", 1.5, 2.5).as_bool() is True

    def test_floats_equal(self):
        assert invoke("lt", 2.5, 2.5).as_bool() is False

    def test_int_float_cross(self):
        assert invoke("lt", 3, 3.5).as_bool() is True

    def test_float_int_cross(self):
        assert invoke("lt", 3.5, 3).as_bool() is False

    def test_negative_ints(self):
        assert invoke("lt", -5, -3).as_bool() is True

    def test_strings(self):
        assert invoke("lt", "abc", "xyz").as_bool() is True

    def test_strings_equal(self):
        assert invoke("lt", "abc", "abc").as_bool() is False

    def test_too_few_args(self):
        assert invoke("lt", 1).is_null()

    def test_no_args(self):
        assert invoke("lt").is_null()


# =============================================================================
# lte -- extended
# =============================================================================

class TestLteExtended:
    """Extended lte verb tests."""

    def test_less(self):
        assert invoke("lte", 3, 5).as_bool() is True

    def test_equal(self):
        assert invoke("lte", 5, 5).as_bool() is True

    def test_greater(self):
        assert invoke("lte", 7, 5).as_bool() is False

    def test_strings_equal(self):
        assert invoke("lte", "abc", "abc").as_bool() is True

    def test_strings_less(self):
        assert invoke("lte", "abc", "xyz").as_bool() is True

    def test_floats_less(self):
        assert invoke("lte", 1.0, 2.0).as_bool() is True

    def test_floats_equal(self):
        assert invoke("lte", 3.14, 3.14).as_bool() is True

    def test_too_few_args(self):
        assert invoke("lte", 1).is_null()


# =============================================================================
# gt -- extended
# =============================================================================

class TestGtExtended:
    """Extended gt verb tests."""

    def test_greater(self):
        assert invoke("gt", 7, 5).as_bool() is True

    def test_equal(self):
        assert invoke("gt", 5, 5).as_bool() is False

    def test_less(self):
        assert invoke("gt", 3, 5).as_bool() is False

    def test_floats(self):
        assert invoke("gt", 5.5, 3.3).as_bool() is True

    def test_negative_ints(self):
        assert invoke("gt", -1, -5).as_bool() is True

    def test_strings(self):
        assert invoke("gt", "xyz", "abc").as_bool() is True

    def test_strings_equal(self):
        assert invoke("gt", "abc", "abc").as_bool() is False

    def test_too_few_args(self):
        assert invoke("gt", 1).is_null()


# =============================================================================
# gte -- extended
# =============================================================================

class TestGteExtended:
    """Extended gte verb tests."""

    def test_greater(self):
        assert invoke("gte", 7, 5).as_bool() is True

    def test_equal(self):
        assert invoke("gte", 5, 5).as_bool() is True

    def test_less(self):
        assert invoke("gte", 3, 5).as_bool() is False

    def test_floats_equal(self):
        assert invoke("gte", 5.0, 5.0).as_bool() is True

    def test_strings(self):
        assert invoke("gte", "xyz", "abc").as_bool() is True

    def test_strings_equal(self):
        assert invoke("gte", "abc", "abc").as_bool() is True

    def test_strings_less(self):
        assert invoke("gte", "abc", "xyz").as_bool() is False

    def test_too_few_args(self):
        assert invoke("gte", 1).is_null()


# =============================================================================
# between -- extended
# =============================================================================

class TestBetweenExtended:
    """Extended between verb tests."""

    def test_in_range(self):
        assert invoke("between", 5, 1, 10).as_bool() is True

    def test_at_min(self):
        assert invoke("between", 1, 1, 10).as_bool() is True

    def test_at_max(self):
        assert invoke("between", 10, 1, 10).as_bool() is True

    def test_below(self):
        assert invoke("between", 0, 1, 10).as_bool() is False

    def test_above(self):
        assert invoke("between", 11, 1, 10).as_bool() is False

    def test_floats_in_range(self):
        assert invoke("between", 5.5, 1.0, 10.0).as_bool() is True

    def test_float_outside(self):
        assert invoke("between", 0.5, 1.0, 10.0).as_bool() is False

    def test_negative_range(self):
        assert invoke("between", -5, -10, 0).as_bool() is True

    def test_negative_below(self):
        assert invoke("between", -11, -10, 0).as_bool() is False

    def test_strings(self):
        assert invoke("between", "dog", "cat", "fox").as_bool() is True

    def test_strings_outside(self):
        assert invoke("between", "ant", "cat", "fox").as_bool() is False

    def test_strings_at_min(self):
        assert invoke("between", "cat", "cat", "fox").as_bool() is True

    def test_strings_at_max(self):
        assert invoke("between", "fox", "cat", "fox").as_bool() is True

    def test_too_few_args(self):
        assert invoke("between", 5, 1).is_null()

    def test_no_args(self):
        assert invoke("between").is_null()

    def test_single_value_range(self):
        assert invoke("between", 5, 5, 5).as_bool() is True


# =============================================================================
# isNull -- extended
# =============================================================================

class TestIsNullExtended:
    """Extended isNull verb tests."""

    def test_null(self):
        assert invoke("isNull", None).as_bool() is True

    def test_string(self):
        assert invoke("isNull", "hi").as_bool() is False

    def test_empty_string(self):
        assert invoke("isNull", "").as_bool() is False

    def test_int(self):
        assert invoke("isNull", 0).as_bool() is False

    def test_float(self):
        assert invoke("isNull", 0.0).as_bool() is False

    def test_bool_false(self):
        assert invoke("isNull", False).as_bool() is False

    def test_bool_true(self):
        assert invoke("isNull", True).as_bool() is False

    def test_array(self):
        assert invoke("isNull", _to_dyn([])).as_bool() is False

    def test_object(self):
        assert invoke("isNull", _to_dyn({})).as_bool() is False

    def test_no_args(self):
        assert invoke("isNull").is_null()


# =============================================================================
# isString -- extended
# =============================================================================

class TestIsStringExtended:
    """Extended isString verb tests."""

    def test_string(self):
        assert invoke("isString", "hello").as_bool() is True

    def test_empty_string(self):
        assert invoke("isString", "").as_bool() is True

    def test_int(self):
        assert invoke("isString", 42).as_bool() is False

    def test_float(self):
        assert invoke("isString", 3.14).as_bool() is False

    def test_bool(self):
        assert invoke("isString", True).as_bool() is False

    def test_null(self):
        assert invoke("isString", None).as_bool() is False

    def test_array(self):
        assert invoke("isString", _to_dyn([1])).as_bool() is False

    def test_object(self):
        assert invoke("isString", _to_dyn({"a": 1})).as_bool() is False

    def test_no_args(self):
        assert invoke("isString").is_null()


# =============================================================================
# isNumber -- extended
# =============================================================================

class TestIsNumberExtended:
    """Extended isNumber verb tests."""

    def test_integer(self):
        assert invoke("isNumber", 42).as_bool() is True

    def test_float(self):
        assert invoke("isNumber", 3.14).as_bool() is True

    def test_negative(self):
        assert invoke("isNumber", -5).as_bool() is True

    def test_zero(self):
        assert invoke("isNumber", 0).as_bool() is True

    def test_string(self):
        assert invoke("isNumber", "42").as_bool() is False

    def test_bool(self):
        assert invoke("isNumber", True).as_bool() is False

    def test_null(self):
        assert invoke("isNumber", None).as_bool() is False

    def test_array(self):
        assert invoke("isNumber", _to_dyn([1])).as_bool() is False

    def test_no_args(self):
        assert invoke("isNumber").is_null()

    def test_currency(self):
        dv = DynValue.of_currency(Decimal("99.99"))
        assert invoke("isNumber", dv).as_bool() is True


# =============================================================================
# isBoolean -- extended
# =============================================================================

class TestIsBooleanExtended:
    """Extended isBoolean verb tests."""

    def test_true(self):
        assert invoke("isBoolean", True).as_bool() is True

    def test_false(self):
        assert invoke("isBoolean", False).as_bool() is True

    def test_string_true(self):
        assert invoke("isBoolean", "true").as_bool() is False

    def test_int(self):
        assert invoke("isBoolean", 1).as_bool() is False

    def test_null(self):
        assert invoke("isBoolean", None).as_bool() is False

    def test_no_args(self):
        assert invoke("isBoolean").is_null()

    def test_float(self):
        assert invoke("isBoolean", 1.0).as_bool() is False

    def test_array(self):
        assert invoke("isBoolean", _to_dyn([])).as_bool() is False


# =============================================================================
# isArray -- extended
# =============================================================================

class TestIsArrayExtended:
    """Extended isArray verb tests."""

    def test_array(self):
        assert invoke("isArray", _to_dyn([1, 2])).as_bool() is True

    def test_empty_array(self):
        assert invoke("isArray", _to_dyn([])).as_bool() is True

    def test_string_like_array(self):
        assert invoke("isArray", "[1,2,3]").as_bool() is True

    def test_string_like_empty_array(self):
        assert invoke("isArray", "[]").as_bool() is True

    def test_int(self):
        assert invoke("isArray", 42).as_bool() is False

    def test_string_not_array(self):
        assert invoke("isArray", "hello").as_bool() is False

    def test_null(self):
        assert invoke("isArray", None).as_bool() is False

    def test_object(self):
        assert invoke("isArray", _to_dyn({"a": 1})).as_bool() is False

    def test_no_args(self):
        assert invoke("isArray").is_null()


# =============================================================================
# isObject -- extended
# =============================================================================

class TestIsObjectExtended:
    """Extended isObject verb tests."""

    def test_object(self):
        assert invoke("isObject", _to_dyn({"a": 1})).as_bool() is True

    def test_empty_object(self):
        assert invoke("isObject", _to_dyn({})).as_bool() is True

    def test_string_like_object(self):
        assert invoke("isObject", '{"key":"val"}').as_bool() is True

    def test_string_like_empty(self):
        assert invoke("isObject", "{}").as_bool() is True

    def test_array(self):
        assert invoke("isObject", _to_dyn([])).as_bool() is False

    def test_int(self):
        assert invoke("isObject", 42).as_bool() is False

    def test_string_not_object(self):
        assert invoke("isObject", "hello").as_bool() is False

    def test_null(self):
        assert invoke("isObject", None).as_bool() is False

    def test_no_args(self):
        assert invoke("isObject").is_null()


# =============================================================================
# isDate -- extended
# =============================================================================

class TestIsDateExtended:
    """Extended isDate verb tests."""

    def test_valid_date_string(self):
        assert invoke("isDate", "2024-01-15").as_bool() is True

    def test_timestamp_string(self):
        assert invoke("isDate", "2024-01-15T10:30:00").as_bool() is True

    def test_invalid_string(self):
        assert invoke("isDate", "not-a-date").as_bool() is False

    def test_short_string(self):
        assert invoke("isDate", "2024").as_bool() is False

    def test_int(self):
        assert invoke("isDate", 20240115).as_bool() is False

    def test_null(self):
        assert invoke("isDate", None).as_bool() is False

    def test_no_args(self):
        assert invoke("isDate").is_null()

    def test_date_type_value(self):
        dv = DynValue(DynType.DATE)
        dv._string_value = "2024-01-15"
        assert invoke("isDate", dv).as_bool() is True

    def test_timestamp_type_value(self):
        dv = DynValue(DynType.TIMESTAMP)
        dv._string_value = "2024-01-15T10:30:00"
        assert invoke("isDate", dv).as_bool() is True

    def test_empty_string(self):
        assert invoke("isDate", "").as_bool() is False

    def test_partial_date(self):
        assert invoke("isDate", "2024-01").as_bool() is False


# =============================================================================
# typeOf -- extended
# =============================================================================

class TestTypeOfExtended:
    """Extended typeOf verb tests covering all DynType values."""

    def test_null(self):
        assert invoke("typeOf", None).as_string() == "null"

    def test_bool(self):
        assert invoke("typeOf", True).as_string() == "boolean"

    def test_bool_false(self):
        assert invoke("typeOf", False).as_string() == "boolean"

    def test_string(self):
        assert invoke("typeOf", "hello").as_string() == "string"

    def test_empty_string(self):
        assert invoke("typeOf", "").as_string() == "string"

    def test_integer(self):
        assert invoke("typeOf", 42).as_string() == "integer"

    def test_integer_zero(self):
        assert invoke("typeOf", 0).as_string() == "integer"

    def test_float(self):
        assert invoke("typeOf", 3.14).as_string() == "number"

    def test_float_zero(self):
        assert invoke("typeOf", 0.0).as_string() == "number"

    def test_array(self):
        assert invoke("typeOf", _to_dyn([1, 2])).as_string() == "array"

    def test_empty_array(self):
        assert invoke("typeOf", _to_dyn([])).as_string() == "array"

    def test_object(self):
        assert invoke("typeOf", _to_dyn({"a": 1})).as_string() == "object"

    def test_empty_object(self):
        assert invoke("typeOf", _to_dyn({})).as_string() == "object"

    def test_no_args(self):
        assert invoke("typeOf").is_null()

    def test_currency(self):
        dv = DynValue.of_currency(Decimal("99.99"))
        assert invoke("typeOf", dv).as_string() == "currency"

    def test_date(self):
        dv = DynValue(DynType.DATE)
        dv._string_value = "2024-01-01"
        assert invoke("typeOf", dv).as_string() == "date"

    def test_timestamp(self):
        dv = DynValue(DynType.TIMESTAMP)
        dv._string_value = "2024-01-01T00:00:00"
        assert invoke("typeOf", dv).as_string() == "timestamp"

    def test_time(self):
        dv = DynValue.of_time("10:30:00")
        assert invoke("typeOf", dv).as_string() == "time"

    def test_duration(self):
        dv = DynValue.of_duration("P1D")
        assert invoke("typeOf", dv).as_string() == "duration"

    def test_percent(self):
        dv = DynValue.of_percent(0.5)
        assert invoke("typeOf", dv).as_string() == "percent"

    def test_reference(self):
        dv = DynValue.of_reference("@parties[0]")
        assert invoke("typeOf", dv).as_string() == "reference"

    def test_binary(self):
        dv = DynValue.of_binary(b"hello")
        assert invoke("typeOf", dv).as_string() == "binary"


# =============================================================================
# cond -- extended
# =============================================================================

class TestCondExtended:
    """Extended cond verb tests."""

    def test_first_true(self):
        assert invoke("cond", True, "yes", False, "no").as_string() == "yes"

    def test_second_true(self):
        assert invoke("cond", False, "no", True, "yes").as_string() == "yes"

    def test_third_true(self):
        assert invoke("cond", False, "a", False, "b", True, "c").as_string() == "c"

    def test_default_value(self):
        assert invoke("cond", False, "no", "default").as_string() == "default"

    def test_all_false_with_default(self):
        assert invoke("cond", False, "a", False, "b", "default").as_string() == "default"

    def test_no_match_no_default(self):
        assert invoke("cond", False, "a", False, "b").is_null()

    def test_truthy_integer(self):
        assert invoke("cond", 1, "yes", "no").as_string() == "yes"

    def test_falsy_zero(self):
        assert invoke("cond", 0, "yes", "no").as_string() == "no"

    def test_truthy_string(self):
        assert invoke("cond", "hello", "yes", "no").as_string() == "yes"

    def test_falsy_empty_string(self):
        assert invoke("cond", "", "yes", "no").as_string() == "no"

    def test_empty_args(self):
        assert invoke("cond").is_null()

    def test_single_true_pair(self):
        assert invoke("cond", True, "yes").as_string() == "yes"

    def test_single_false_pair(self):
        assert invoke("cond", False, "yes").is_null()

    def test_returns_int_value(self):
        r = invoke("cond", True, 42)
        assert r.as_int() == 42


# =============================================================================
# assert -- extended
# =============================================================================

class TestAssertExtended:
    """Extended assert verb tests."""

    def test_truthy_bool(self):
        r = invoke("assert", True)
        assert r.as_bool() is True

    def test_falsy_bool(self):
        assert invoke("assert", False).is_null()

    def test_null(self):
        assert invoke("assert", None).is_null()

    def test_no_args(self):
        assert invoke("assert").is_null()

    def test_truthy_string(self):
        r = invoke("assert", "hello")
        assert r.as_string() == "hello"

    def test_falsy_empty_string(self):
        assert invoke("assert", "").is_null()

    def test_truthy_integer(self):
        r = invoke("assert", 42)
        assert r.as_int() == 42

    def test_falsy_zero(self):
        assert invoke("assert", 0).is_null()

    def test_truthy_float(self):
        r = invoke("assert", 3.14)
        assert r.as_float() == pytest.approx(3.14)

    def test_falsy_zero_float(self):
        assert invoke("assert", 0.0).is_null()

    def test_truthy_array(self):
        r = invoke("assert", [1, 2])
        assert r.type == DynType.ARRAY


# =============================================================================
# switch -- extended
# =============================================================================

class TestSwitchExtended:
    """Extended switch verb tests."""

    def test_matches_first(self):
        assert invoke("switch", "a", "a", "found_a", "b", "found_b").as_string() == "found_a"

    def test_matches_second(self):
        assert invoke("switch", "b", "a", "found_a", "b", "found_b").as_string() == "found_b"

    def test_default(self):
        assert invoke("switch", "c", "a", "found_a", "b", "found_b", "default").as_string() == "default"

    def test_no_match_no_default(self):
        assert invoke("switch", "c", "a", "found_a", "b", "found_b").is_null()

    def test_int_match(self):
        assert invoke("switch", 2, 1, "one", 2, "two").as_string() == "two"

    def test_int_default(self):
        assert invoke("switch", 3, 1, "one", "other").as_string() == "other"

    def test_single_value_no_pairs(self):
        assert invoke("switch", "x").is_null()

    def test_too_few_args(self):
        assert invoke("switch", "x", "y").is_null()

    def test_many_cases(self):
        assert invoke("switch", "d", "a", "1", "b", "2", "c", "3", "d", "4").as_string() == "4"

    def test_first_match_wins(self):
        assert invoke("switch", "a", "a", "first", "a", "second").as_string() == "first"

    def test_null_value_match(self):
        assert invoke("switch", None, None, "null_found", "a", "other").as_string() == "null_found"


# =============================================================================
# isFinite -- extended
# =============================================================================

class TestIsFiniteExtended:
    """Extended isFinite verb tests."""

    def test_integer(self):
        assert invoke("isFinite", 42).as_bool() is True

    def test_negative_integer(self):
        assert invoke("isFinite", -42).as_bool() is True

    def test_zero(self):
        assert invoke("isFinite", 0).as_bool() is True

    def test_float(self):
        assert invoke("isFinite", 3.14).as_bool() is True

    def test_negative_float(self):
        assert invoke("isFinite", -3.14).as_bool() is True

    def test_positive_infinity(self):
        assert invoke("isFinite", float("inf")).as_bool() is False

    def test_negative_infinity(self):
        assert invoke("isFinite", float("-inf")).as_bool() is False

    def test_nan(self):
        assert invoke("isFinite", float("nan")).as_bool() is False

    def test_string(self):
        # String is not numeric type, should be false
        assert invoke("isFinite", "42").as_bool() is False

    def test_bool(self):
        assert invoke("isFinite", True).as_bool() is False

    def test_null(self):
        assert invoke("isFinite", None).as_bool() is False

    def test_no_args(self):
        assert invoke("isFinite").is_null()


# =============================================================================
# isNaN -- extended
# =============================================================================

class TestIsNaNExtended:
    """Extended isNaN verb tests."""

    def test_nan(self):
        assert invoke("isNaN", float("nan")).as_bool() is True

    def test_number(self):
        assert invoke("isNaN", 42.0).as_bool() is False

    def test_integer(self):
        assert invoke("isNaN", 42).as_bool() is False

    def test_zero(self):
        assert invoke("isNaN", 0.0).as_bool() is False

    def test_infinity(self):
        assert invoke("isNaN", float("inf")).as_bool() is False

    def test_string_nan(self):
        assert invoke("isNaN", "NaN").as_bool() is True

    def test_string_nan_lowercase(self):
        assert invoke("isNaN", "nan").as_bool() is True

    def test_string_number(self):
        assert invoke("isNaN", "42").as_bool() is False

    def test_null(self):
        assert invoke("isNaN", None).as_bool() is False

    def test_no_args(self):
        assert invoke("isNaN").is_null()

    def test_bool(self):
        assert invoke("isNaN", True).as_bool() is False


# =============================================================================
# Parametrized truthiness tests across logic verbs
# =============================================================================

class TestTruthinessConsistency:
    """Verify truthiness is consistent across logic verbs that use is_truthy."""

    @pytest.mark.parametrize("value,expected_truthy", [
        (True, True),
        (False, False),
        (None, False),
        (0, False),
        (1, True),
        (-1, True),
        (0.0, False),
        (1.5, True),
        ("", False),
        ("hello", True),
        (" ", True),
    ])
    def test_not_consistency(self, value, expected_truthy):
        # not(value) should be the inverse of truthiness
        result = invoke("not", value).as_bool()
        assert result is (not expected_truthy)

    @pytest.mark.parametrize("value,expected_truthy", [
        (True, True),
        (False, False),
        (None, False),
        (0, False),
        (1, True),
        ("", False),
        ("hello", True),
    ])
    def test_ifElse_consistency(self, value, expected_truthy):
        result = invoke("ifElse", value, "yes", "no").as_string()
        assert result == ("yes" if expected_truthy else "no")


# =============================================================================
# Parametrized comparison tests
# =============================================================================

class TestComparisonParametrized:
    """Parametrized tests for comparison verbs."""

    @pytest.mark.parametrize("a,b,expected", [
        (1, 2, True),
        (2, 2, False),
        (3, 2, False),
        (-5, -3, True),
        (0, 1, True),
        (-1, 0, True),
    ])
    def test_lt_integers(self, a, b, expected):
        assert invoke("lt", a, b).as_bool() is expected

    @pytest.mark.parametrize("a,b,expected", [
        (1, 2, True),
        (2, 2, True),
        (3, 2, False),
    ])
    def test_lte_integers(self, a, b, expected):
        assert invoke("lte", a, b).as_bool() is expected

    @pytest.mark.parametrize("a,b,expected", [
        (3, 2, True),
        (2, 2, False),
        (1, 2, False),
    ])
    def test_gt_integers(self, a, b, expected):
        assert invoke("gt", a, b).as_bool() is expected

    @pytest.mark.parametrize("a,b,expected", [
        (3, 2, True),
        (2, 2, True),
        (1, 2, False),
    ])
    def test_gte_integers(self, a, b, expected):
        assert invoke("gte", a, b).as_bool() is expected

    @pytest.mark.parametrize("a,b,expected", [
        (1.0, 2.0, True),
        (2.0, 2.0, False),
        (3.0, 2.0, False),
    ])
    def test_lt_floats(self, a, b, expected):
        assert invoke("lt", a, b).as_bool() is expected

    @pytest.mark.parametrize("a,b,expected", [
        ("abc", "def", True),
        ("def", "abc", False),
        ("abc", "abc", False),
    ])
    def test_lt_strings(self, a, b, expected):
        assert invoke("lt", a, b).as_bool() is expected


# =============================================================================
# Type checking parametrized
# =============================================================================

class TestTypeCheckParametrized:
    """Parametrized type check tests."""

    @pytest.mark.parametrize("value,verb,expected", [
        ("hello", "isString", True),
        ("", "isString", True),
        (42, "isString", False),
        (None, "isString", False),
        (42, "isNumber", True),
        (3.14, "isNumber", True),
        ("42", "isNumber", False),
        (None, "isNumber", False),
        (True, "isBoolean", True),
        (False, "isBoolean", True),
        ("true", "isBoolean", False),
        (1, "isBoolean", False),
        (None, "isNull", True),
        ("", "isNull", False),
        (0, "isNull", False),
        (False, "isNull", False),
    ])
    def test_type_checks(self, value, verb, expected):
        assert invoke(verb, value).as_bool() is expected
