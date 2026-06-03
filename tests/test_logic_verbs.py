"""Tests for logic verbs: and, or, not, xor, eq, ne, lt, lte, gt, gte, between, type checks, cond, switch."""

import math
import pytest
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


# ── and ───────────────────────────────────────────────────────────────────────

def test_and_true_true():
    assert invoke("and", True, True).as_bool() is True

def test_and_true_false():
    assert invoke("and", True, False).as_bool() is False

def test_and_false_true():
    assert invoke("and", False, True).as_bool() is False

def test_and_false_false():
    assert invoke("and", False, False).as_bool() is False

def test_and_too_few():
    assert invoke("and", True).is_null()


# ── or ────────────────────────────────────────────────────────────────────────

def test_or_true_true():
    assert invoke("or", True, True).as_bool() is True

def test_or_true_false():
    assert invoke("or", True, False).as_bool() is True

def test_or_false_true():
    assert invoke("or", False, True).as_bool() is True

def test_or_false_false():
    assert invoke("or", False, False).as_bool() is False

def test_or_too_few():
    assert invoke("or", True).is_null()


# ── not ───────────────────────────────────────────────────────────────────────

def test_not_true():
    assert invoke("not", True).as_bool() is False

def test_not_false():
    assert invoke("not", False).as_bool() is True

def test_not_null():
    assert invoke("not", None).as_bool() is True

def test_not_zero_int():
    assert invoke("not", 0).as_bool() is True

def test_not_nonzero_int():
    assert invoke("not", 1).as_bool() is False

def test_not_empty_string():
    assert invoke("not", "").as_bool() is True

def test_not_nonempty_string():
    assert invoke("not", "hello").as_bool() is False

def test_not_empty_array():
    # Arrays are always truthy in Java/TS
    assert invoke("not", _to_dyn([])).as_bool() is False

def test_not_no_args():
    assert invoke("not").is_null()


# ── xor ───────────────────────────────────────────────────────────────────────

def test_xor_true_false():
    assert invoke("xor", True, False).as_bool() is True

def test_xor_true_true():
    assert invoke("xor", True, True).as_bool() is False

def test_xor_false_false():
    assert invoke("xor", False, False).as_bool() is False

def test_xor_too_few():
    assert invoke("xor", True).is_null()


# ── eq / ne ───────────────────────────────────────────────────────────────────

def test_eq_ints_equal():
    assert invoke("eq", 42, 42).as_bool() is True

def test_eq_ints_not_equal():
    assert invoke("eq", 42, 43).as_bool() is False

def test_eq_strings_equal():
    assert invoke("eq", "hello", "hello").as_bool() is True

def test_eq_strings_not_equal():
    assert invoke("eq", "hello", "world").as_bool() is False

def test_eq_nulls():
    assert invoke("eq", None, None).as_bool() is True

def test_eq_null_vs_string():
    assert invoke("eq", None, "hello").as_bool() is False

def test_eq_cross_type_int_float():
    assert invoke("eq", 42, 42.0).as_bool() is True

def test_eq_string_number():
    assert invoke("eq", "42", 42).as_bool() is True

def test_eq_bools():
    assert invoke("eq", True, True).as_bool() is True

def test_eq_bools_different():
    assert invoke("eq", True, False).as_bool() is False

def test_eq_too_few():
    assert invoke("eq", 42).is_null()

def test_ne_different():
    assert invoke("ne", 42, 43).as_bool() is True

def test_ne_same():
    assert invoke("ne", 42, 42).as_bool() is False

def test_ne_nulls():
    assert invoke("ne", None, None).as_bool() is False


# ── lt / lte / gt / gte ──────────────────────────────────────────────────────

def test_lt_ints_less():
    assert invoke("lt", 1, 2).as_bool() is True

def test_lt_ints_equal():
    assert invoke("lt", 2, 2).as_bool() is False

def test_lt_ints_greater():
    assert invoke("lt", 3, 2).as_bool() is False

def test_lt_strings():
    assert invoke("lt", "abc", "def").as_bool() is True

def test_lte_less():
    assert invoke("lte", 1, 2).as_bool() is True

def test_lte_equal():
    assert invoke("lte", 2, 2).as_bool() is True

def test_lte_greater():
    assert invoke("lte", 3, 2).as_bool() is False

def test_gt_greater():
    assert invoke("gt", 3, 2).as_bool() is True

def test_gt_equal():
    assert invoke("gt", 2, 2).as_bool() is False

def test_gte_equal():
    assert invoke("gte", 2, 2).as_bool() is True

def test_gte_greater():
    assert invoke("gte", 3, 2).as_bool() is True

def test_gte_less():
    assert invoke("gte", 1, 2).as_bool() is False


# ── between ───────────────────────────────────────────────────────────────────

def test_between_in_range():
    assert invoke("between", 5, 1, 10).as_bool() is True

def test_between_at_min():
    assert invoke("between", 1, 1, 10).as_bool() is True

def test_between_at_max():
    assert invoke("between", 10, 1, 10).as_bool() is True

def test_between_below():
    assert invoke("between", 0, 1, 10).as_bool() is False

def test_between_above():
    assert invoke("between", 11, 1, 10).as_bool() is False

def test_between_strings():
    assert invoke("between", "c", "a", "z").as_bool() is True

def test_between_too_few():
    assert invoke("between", 5, 1).is_null()


# ── isNull ────────────────────────────────────────────────────────────────────

def test_is_null_null():
    assert invoke("isNull", None).as_bool() is True

def test_is_null_string():
    assert invoke("isNull", "hello").as_bool() is False

def test_is_null_int():
    assert invoke("isNull", 0).as_bool() is False

def test_is_null_empty_string():
    assert invoke("isNull", "").as_bool() is False

def test_is_null_no_args():
    assert invoke("isNull").is_null()


# ── isString ──────────────────────────────────────────────────────────────────

def test_is_string_string():
    assert invoke("isString", "hello").as_bool() is True

def test_is_string_empty():
    assert invoke("isString", "").as_bool() is True

def test_is_string_int():
    assert invoke("isString", 42).as_bool() is False

def test_is_string_null():
    assert invoke("isString", None).as_bool() is False

def test_is_string_no_args():
    assert invoke("isString").is_null()


# ── isNumber ──────────────────────────────────────────────────────────────────

def test_is_number_int():
    assert invoke("isNumber", 42).as_bool() is True

def test_is_number_float():
    assert invoke("isNumber", 3.14).as_bool() is True

def test_is_number_string():
    assert invoke("isNumber", "42").as_bool() is False

def test_is_number_null():
    assert invoke("isNumber", None).as_bool() is False

def test_is_number_no_args():
    assert invoke("isNumber").is_null()


# ── isBoolean ─────────────────────────────────────────────────────────────────

def test_is_boolean_true():
    assert invoke("isBoolean", True).as_bool() is True

def test_is_boolean_false():
    assert invoke("isBoolean", False).as_bool() is True

def test_is_boolean_string():
    assert invoke("isBoolean", "true").as_bool() is False

def test_is_boolean_no_args():
    assert invoke("isBoolean").is_null()


# ── isArray ───────────────────────────────────────────────────────────────────

def test_is_array_array():
    assert invoke("isArray", _to_dyn([1, 2, 3])).as_bool() is True

def test_is_array_empty():
    assert invoke("isArray", _to_dyn([])).as_bool() is True

def test_is_array_string_like():
    assert invoke("isArray", "[1, 2]").as_bool() is True

def test_is_array_non_array():
    assert invoke("isArray", 42).as_bool() is False

def test_is_array_no_args():
    assert invoke("isArray").is_null()


# ── isObject ──────────────────────────────────────────────────────────────────

def test_is_object_object():
    assert invoke("isObject", _to_dyn({"a": 1})).as_bool() is True

def test_is_object_string_like():
    assert invoke("isObject", '{"a": 1}').as_bool() is True

def test_is_object_non_object():
    assert invoke("isObject", 42).as_bool() is False

def test_is_object_no_args():
    assert invoke("isObject").is_null()


# ── isDate ────────────────────────────────────────────────────────────────────

def test_is_date_valid():
    dv = DynValue(DynType.DATE)
    dv._string_value = "2024-01-15"
    assert invoke("isDate", dv).as_bool() is True

def test_is_date_timestamp():
    dv = DynValue(DynType.TIMESTAMP)
    dv._string_value = "2024-01-15T10:30:00"
    assert invoke("isDate", dv).as_bool() is True

def test_is_date_string_valid():
    from datetime import date
    assert invoke("isDate", DynValue.of_date(date(2024, 1, 15))).as_bool() is True

def test_is_date_invalid():
    assert invoke("isDate", "not a date").as_bool() is False

def test_is_date_string_is_false():
    # A plain string is not a date type
    assert invoke("isDate", "2024-01-15").as_bool() is False

def test_is_date_no_args():
    assert invoke("isDate").is_null()


# ── typeOf ────────────────────────────────────────────────────────────────────

def test_type_of_null():
    assert invoke("typeOf", None).as_string() == "null"

def test_type_of_bool():
    assert invoke("typeOf", True).as_string() == "boolean"

def test_type_of_string():
    assert invoke("typeOf", "hello").as_string() == "string"

def test_type_of_integer():
    assert invoke("typeOf", 42).as_string() == "integer"

def test_type_of_float():
    assert invoke("typeOf", 3.14).as_string() == "number"

def test_type_of_array():
    assert invoke("typeOf", _to_dyn([1, 2])).as_string() == "array"

def test_type_of_object():
    assert invoke("typeOf", _to_dyn({"a": 1})).as_string() == "object"

def test_type_of_no_args():
    assert invoke("typeOf").is_null()


# ── cond ──────────────────────────────────────────────────────────────────────

def test_cond_first_true():
    assert invoke("cond", True, "yes", False, "no").as_string() == "yes"

def test_cond_second_true():
    assert invoke("cond", False, "no", True, "yes").as_string() == "yes"

def test_cond_default():
    assert invoke("cond", False, "no", False, "no", "default").as_string() == "default"

def test_cond_no_match():
    assert invoke("cond", False, "no", False, "no").is_null()

def test_cond_truthy_int():
    assert invoke("cond", 1, "yes").as_string() == "yes"

def test_cond_falsy_zero():
    assert invoke("cond", 0, "yes", "default").as_string() == "default"


# ── assert ────────────────────────────────────────────────────────────────────

def test_assert_truthy():
    r = invoke("assert", True)
    assert r.as_bool() is True

def test_assert_falsy():
    assert invoke("assert", False).is_null()

def test_assert_null():
    assert invoke("assert", None).is_null()

def test_assert_no_args():
    assert invoke("assert").is_null()

def test_assert_truthy_string():
    r = invoke("assert", "hello")
    assert r.as_string() == "hello"

def test_assert_falsy_empty():
    assert invoke("assert", "").is_null()


# ── switch ────────────────────────────────────────────────────────────────────

def test_switch_matches_first():
    assert invoke("switch", "a", "a", "found_a", "b", "found_b").as_string() == "found_a"

def test_switch_matches_second():
    assert invoke("switch", "b", "a", "found_a", "b", "found_b").as_string() == "found_b"

def test_switch_default():
    assert invoke("switch", "c", "a", "found_a", "b", "found_b", "default").as_string() == "default"

def test_switch_no_match_no_default():
    assert invoke("switch", "c", "a", "found_a", "b", "found_b").is_null()


# ── ifElse ────────────────────────────────────────────────────────────────────

def test_if_else_true():
    assert invoke("ifElse", True, "yes", "no").as_string() == "yes"

def test_if_else_false():
    assert invoke("ifElse", False, "yes", "no").as_string() == "no"

def test_if_else_truthy_int():
    assert invoke("ifElse", 1, "yes", "no").as_string() == "yes"

def test_if_else_falsy_zero():
    assert invoke("ifElse", 0, "yes", "no").as_string() == "no"

def test_if_else_null_falsy():
    assert invoke("ifElse", None, "yes", "no").as_string() == "no"

def test_if_else_too_few():
    assert invoke("ifElse", True, "yes").is_null()


# ── isFinite / isNaN ──────────────────────────────────────────────────────────

def test_is_finite_integer():
    assert invoke("isFinite", 42).as_bool() is True

def test_is_finite_float():
    assert invoke("isFinite", 3.14).as_bool() is True

def test_is_finite_infinity():
    assert invoke("isFinite", float("inf")).as_bool() is False

def test_is_finite_nan():
    assert invoke("isFinite", float("nan")).as_bool() is False

def test_is_finite_no_args():
    assert invoke("isFinite").is_null()

def test_is_nan_nan():
    assert invoke("isNaN", float("nan")).as_bool() is True

def test_is_nan_number():
    assert invoke("isNaN", 42.0).as_bool() is False

def test_is_nan_string():
    assert invoke("isNaN", "NaN").as_bool() is True
