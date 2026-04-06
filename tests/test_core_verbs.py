"""Tests for core verbs: concat, upper, lower, trim, coalesce, ifNull, ifEmpty, ifElse."""

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


# ── concat ────────────────────────────────────────────────────────────────────

class TestConcat:
    def test_two_strings(self):
        r = invoke("concat", "hello", " world")
        assert r.as_string() == "hello world"

    def test_multiple_args(self):
        r = invoke("concat", "a", "b", "c")
        assert r.as_string() == "abc"

    def test_skips_null(self):
        r = invoke("concat", "hello", None, " world")
        assert r.as_string() == "hello world"

    def test_all_null(self):
        r = invoke("concat", None, None)
        assert r.as_string() == ""

    def test_numbers_coerced(self):
        r = invoke("concat", "val=", 42)
        assert r.as_string() == "val=42"

    def test_empty_args(self):
        r = invoke("concat")
        assert r.as_string() == ""


# ── upper ─────────────────────────────────────────────────────────────────────

class TestUpper:
    def test_happy_path(self):
        assert invoke("upper", "hello").as_string() == "HELLO"

    def test_null_passthrough(self):
        assert invoke("upper", None).is_null()

    def test_no_args(self):
        assert invoke("upper").is_null()

    def test_empty_string(self):
        assert invoke("upper", "").as_string() == ""

    def test_mixed_case(self):
        assert invoke("upper", "Hello World").as_string() == "HELLO WORLD"

    def test_integer_coerced(self):
        assert invoke("upper", 42).as_string() == "42"


# ── lower ─────────────────────────────────────────────────────────────────────

class TestLower:
    def test_happy_path(self):
        assert invoke("lower", "HELLO").as_string() == "hello"

    def test_null_passthrough(self):
        assert invoke("lower", None).is_null()

    def test_no_args(self):
        assert invoke("lower").is_null()

    def test_integer_coerced(self):
        assert invoke("lower", 42).as_string() == "42"


# ── trim ──────────────────────────────────────────────────────────────────────

class TestTrim:
    def test_happy_path(self):
        assert invoke("trim", "  hello  ").as_string() == "hello"

    def test_null_passthrough(self):
        assert invoke("trim", None).is_null()

    def test_no_args(self):
        assert invoke("trim").is_null()

    def test_trim_left(self):
        assert invoke("trimLeft", "  hello  ").as_string() == "hello  "

    def test_trim_left_null(self):
        assert invoke("trimLeft", None).is_null()

    def test_trim_right(self):
        assert invoke("trimRight", "  hello  ").as_string() == "  hello"

    def test_trim_right_null(self):
        assert invoke("trimRight", None).is_null()


# ── coalesce ──────────────────────────────────────────────────────────────────

class TestCoalesce:
    def test_returns_first_non_null(self):
        r = invoke("coalesce", None, "hello")
        assert r.as_string() == "hello"

    def test_skips_empty_string(self):
        r = invoke("coalesce", "", "fallback")
        assert r.as_string() == "fallback"

    def test_all_null(self):
        assert invoke("coalesce", None, None).is_null()

    def test_returns_integer(self):
        r = invoke("coalesce", None, 42)
        assert r.as_int() == 42

    def test_returns_first_value(self):
        r = invoke("coalesce", "first", "second")
        assert r.as_string() == "first"


# ── ifNull ────────────────────────────────────────────────────────────────────

class TestIfNull:
    def test_null_returns_default(self):
        r = invoke("ifNull", None, "default")
        assert r.as_string() == "default"

    def test_non_null_returns_first(self):
        r = invoke("ifNull", "value", "default")
        assert r.as_string() == "value"

    def test_too_few_args(self):
        assert invoke("ifNull", "only_one").is_null()

    def test_empty_string_not_null(self):
        r = invoke("ifNull", "", "default")
        assert r.as_string() == ""

    def test_zero_not_null(self):
        r = invoke("ifNull", 0, "default")
        assert r.as_int() == 0

    def test_false_not_null(self):
        r = invoke("ifNull", False, "default")
        assert r.as_bool() is False


# ── ifEmpty ───────────────────────────────────────────────────────────────────

class TestIfEmpty:
    def test_null_returns_default(self):
        r = invoke("ifEmpty", None, "default")
        assert r.as_string() == "default"

    def test_empty_string_returns_default(self):
        r = invoke("ifEmpty", "", "default")
        assert r.as_string() == "default"

    def test_non_empty_returns_first(self):
        r = invoke("ifEmpty", "value", "default")
        assert r.as_string() == "value"

    def test_too_few_args(self):
        assert invoke("ifEmpty").is_null()

    def test_int_not_empty(self):
        r = invoke("ifEmpty", 42, "default")
        assert r.as_int() == 42

    def test_bool_not_empty(self):
        r = invoke("ifEmpty", True, "default")
        assert r.as_bool() is True


# ── ifElse ────────────────────────────────────────────────────────────────────

class TestIfElse:
    def test_truthy_returns_then(self):
        r = invoke("ifElse", True, "yes", "no")
        assert r.as_string() == "yes"

    def test_falsy_returns_else(self):
        r = invoke("ifElse", False, "yes", "no")
        assert r.as_string() == "no"

    def test_null_is_falsy(self):
        r = invoke("ifElse", None, "yes", "no")
        assert r.as_string() == "no"

    def test_non_zero_is_truthy(self):
        r = invoke("ifElse", 1, "yes", "no")
        assert r.as_string() == "yes"

    def test_zero_is_falsy(self):
        r = invoke("ifElse", 0, "yes", "no")
        assert r.as_string() == "no"

    def test_too_few_args(self):
        assert invoke("ifElse", True, "yes").is_null()

    def test_truthy_string(self):
        r = invoke("ifElse", "hello", "yes", "no")
        assert r.as_string() == "yes"

    def test_empty_string_falsy(self):
        r = invoke("ifElse", "", "yes", "no")
        assert r.as_string() == "no"
