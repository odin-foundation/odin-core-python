"""Tests for coercion verbs."""

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


# ── coerceString ──────────────────────────────────────────────────────────────

def test_coerce_string_from_string():
    assert invoke("coerceString", "hello").as_string() == "hello"

def test_coerce_string_from_int():
    assert invoke("coerceString", 42).as_string() == "42"

def test_coerce_string_from_float():
    assert invoke("coerceString", 3.14).as_string() == "3.14"

def test_coerce_string_from_bool_true():
    assert invoke("coerceString", True).as_string() == "true"

def test_coerce_string_from_bool_false():
    assert invoke("coerceString", False).as_string() == "false"

def test_coerce_string_from_null():
    assert invoke("coerceString", None).is_null()

def test_coerce_string_no_args():
    assert invoke("coerceString").is_null()


# ── coerceNumber ──────────────────────────────────────────────────────────────

def test_coerce_number_from_int():
    r = invoke("coerceNumber", 42)
    assert r.as_int() == 42

def test_coerce_number_from_float():
    r = invoke("coerceNumber", 3.14)
    assert abs(r.as_float() - 3.14) < 0.001

def test_coerce_number_from_string():
    r = invoke("coerceNumber", "42")
    assert r.as_int() == 42

def test_coerce_number_from_bool_true():
    r = invoke("coerceNumber", True)
    assert r.as_int() == 1

def test_coerce_number_from_bool_false():
    r = invoke("coerceNumber", False)
    assert r.as_int() == 0

def test_coerce_number_from_null():
    assert invoke("coerceNumber", None).is_null()

def test_coerce_number_invalid_string():
    assert invoke("coerceNumber", "abc").is_null()

def test_coerce_number_no_args():
    assert invoke("coerceNumber").is_null()


# ── coerceInteger ─────────────────────────────────────────────────────────────

def test_coerce_integer_from_int():
    r = invoke("coerceInteger", 42)
    assert r.as_int() == 42

def test_coerce_integer_from_float():
    r = invoke("coerceInteger", 3.7)
    assert r.as_int() == 3

def test_coerce_integer_from_string():
    r = invoke("coerceInteger", "42")
    assert r.as_int() == 42

def test_coerce_integer_from_string_float():
    r = invoke("coerceInteger", "3.7")
    assert r.as_int() == 3

def test_coerce_integer_from_bool():
    r = invoke("coerceInteger", True)
    assert r.as_int() == 1

def test_coerce_integer_from_bool_false():
    r = invoke("coerceInteger", False)
    assert r.as_int() == 0

def test_coerce_integer_from_null():
    assert invoke("coerceInteger", None).is_null()

def test_coerce_integer_invalid():
    assert invoke("coerceInteger", "abc").is_null()

def test_coerce_integer_no_args():
    assert invoke("coerceInteger").is_null()


# ── coerceBoolean ─────────────────────────────────────────────────────────────

def test_coerce_boolean_true():
    r = invoke("coerceBoolean", True)
    assert r.as_bool() is True

def test_coerce_boolean_false():
    r = invoke("coerceBoolean", False)
    assert r.as_bool() is False

def test_coerce_boolean_string_true():
    assert invoke("coerceBoolean", "true").as_bool() is True

def test_coerce_boolean_string_false():
    assert invoke("coerceBoolean", "false").as_bool() is False

def test_coerce_boolean_string_zero():
    assert invoke("coerceBoolean", "0").as_bool() is False

def test_coerce_boolean_string_empty():
    assert invoke("coerceBoolean", "").as_bool() is False

def test_coerce_boolean_string_no():
    assert invoke("coerceBoolean", "no").as_bool() is False

def test_coerce_boolean_string_yes():
    assert invoke("coerceBoolean", "yes").as_bool() is True

def test_coerce_boolean_string_n():
    assert invoke("coerceBoolean", "n").as_bool() is False

def test_coerce_boolean_string_off():
    assert invoke("coerceBoolean", "off").as_bool() is False

def test_coerce_boolean_int_nonzero():
    assert invoke("coerceBoolean", 42).as_bool() is True

def test_coerce_boolean_int_zero():
    assert invoke("coerceBoolean", 0).as_bool() is False

def test_coerce_boolean_null():
    assert invoke("coerceBoolean", None).is_null()

def test_coerce_boolean_no_args():
    assert invoke("coerceBoolean").is_null()


# ── coerceDate ────────────────────────────────────────────────────────────────

def test_coerce_date_valid():
    r = invoke("coerceDate", "2024-01-15")
    assert r.type == DynType.DATE
    assert r._string_value == "2024-01-15"

def test_coerce_date_timestamp():
    r = invoke("coerceDate", "2024-01-15T10:30:00")
    assert r.type == DynType.DATE
    assert r._string_value == "2024-01-15"

def test_coerce_date_invalid():
    assert invoke("coerceDate", "not-a-date").is_null()

def test_coerce_date_null():
    assert invoke("coerceDate", None).is_null()

def test_coerce_date_no_args():
    assert invoke("coerceDate").is_null()


# ── coerceTimestamp ───────────────────────────────────────────────────────────

def test_coerce_timestamp_valid():
    r = invoke("coerceTimestamp", "2024-01-15T10:30:00")
    assert r.type == DynType.TIMESTAMP
    assert "2024-01-15T10:30:00" in r._string_value

def test_coerce_timestamp_from_date():
    r = invoke("coerceTimestamp", "2024-01-15")
    assert r.type == DynType.TIMESTAMP
    assert "2024-01-15T00:00:00" in r._string_value

def test_coerce_timestamp_invalid():
    assert invoke("coerceTimestamp", "not-a-date").is_null()

def test_coerce_timestamp_null():
    assert invoke("coerceTimestamp", None).is_null()

def test_coerce_timestamp_no_args():
    assert invoke("coerceTimestamp").is_null()


# ── tryCoerce ─────────────────────────────────────────────────────────────────

def test_try_coerce_integer():
    r = invoke("tryCoerce", "42")
    assert r.type == DynType.INTEGER
    assert r.as_int() == 42

def test_try_coerce_float():
    r = invoke("tryCoerce", "3.14")
    assert r.as_float() == pytest.approx(3.14)

def test_try_coerce_bool_true():
    r = invoke("tryCoerce", "true")
    assert r.type == DynType.BOOL
    assert r.as_bool() is True

def test_try_coerce_bool_false():
    r = invoke("tryCoerce", "false")
    assert r.type == DynType.BOOL
    assert r.as_bool() is False

def test_try_coerce_date():
    r = invoke("tryCoerce", "2024-01-15")
    assert r.type == DynType.DATE

def test_try_coerce_plain_string():
    r = invoke("tryCoerce", "hello")
    assert r.type == DynType.STRING
    assert r.as_string() == "hello"

def test_try_coerce_no_args():
    assert invoke("tryCoerce").is_null()

def test_try_coerce_passthrough_int():
    r = invoke("tryCoerce", _to_dyn(42))
    assert r.type == DynType.INTEGER

def test_try_coerce_passthrough_bool():
    r = invoke("tryCoerce", _to_dyn(True))
    assert r.type == DynType.BOOL


# ── toArray ───────────────────────────────────────────────────────────────────

def test_to_array_from_array():
    r = invoke("toArray", _to_dyn([1, 2, 3]))
    assert r.is_array()
    assert len(r.as_array()) == 3

def test_to_array_from_scalar():
    r = invoke("toArray", "hello")
    assert r.is_array()
    items = r.as_array()
    assert len(items) == 1
    assert items[0].as_string() == "hello"

def test_to_array_from_null():
    r = invoke("toArray", None)
    assert r.is_array()
    assert len(r.as_array()) == 0

def test_to_array_no_args():
    r = invoke("toArray")
    assert r.is_array()


# ── toObject ──────────────────────────────────────────────────────────────────

def test_to_object_from_pairs():
    pairs = _to_dyn([["name", "Alice"], ["age", 30]])
    r = invoke("toObject", pairs)
    assert r.is_object()
    obj = r.as_object()
    assert obj["name"].as_string() == "Alice"

def test_to_object_already_object():
    r = invoke("toObject", _to_dyn({"a": 1}))
    assert r.is_object()

def test_to_object_null():
    assert invoke("toObject", None).is_null()

def test_to_object_no_args():
    assert invoke("toObject").is_null()
