"""Tests for object verbs."""

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


# ── keys ─────────────────────────────────────────────────────────────

class TestKeys:
    def test_basic(self):
        r = invoke("keys", {"a": 1, "b": 2, "c": 3})
        strs = [item.as_string() for item in r.as_array()]
        assert "a" in strs
        assert "b" in strs
        assert "c" in strs

    def test_empty_object(self):
        r = invoke("keys", {})
        assert len(r.as_array()) == 0

    def test_non_object(self):
        r = invoke("keys", 42)
        assert len(r.as_array()) == 0


# ── values ───────────────────────────────────────────────────────────

class TestValues:
    def test_basic(self):
        r = invoke("values", {"a": 1, "b": 2})
        arr = r.as_array()
        assert len(arr) == 2


# ── entries ──────────────────────────────────────────────────────────

class TestEntries:
    def test_basic(self):
        r = invoke("entries", {"a": 1, "b": 2})
        arr = r.as_array()
        assert len(arr) == 2
        # Each entry is [key, value]
        first = arr[0].as_array()
        assert first[0].as_string() in ("a", "b")

    def test_empty(self):
        r = invoke("entries", {})
        assert len(r.as_array()) == 0


# ── has ──────────────────────────────────────────────────────────────

class TestHas:
    def test_existing(self):
        r = invoke("has", {"name": "Alice"}, "name")
        assert r._bool_value is True

    def test_missing(self):
        r = invoke("has", {"name": "Alice"}, "age")
        assert r._bool_value is False

    def test_non_object(self):
        r = invoke("has", 42, "x")
        assert r._bool_value is False

    def test_proto_blocked(self):
        r = invoke("has", {"__proto__": "evil"}, "__proto__")
        assert r._bool_value is False


# ── get ──────────────────────────────────────────────────────────────

class TestGet:
    def test_existing(self):
        r = invoke("get", {"name": "Alice", "age": 30}, "name")
        assert r.as_string() == "Alice"

    def test_missing_with_default(self):
        r = invoke("get", {"name": "Alice"}, "age", 0)
        assert r._int_value == 0

    def test_missing_no_default(self):
        r = invoke("get", {"name": "Alice"}, "age")
        assert r.is_null()

    def test_nested(self):
        r = invoke("get", {"a": {"b": 42}}, "a.b")
        assert r._int_value == 42

    def test_non_object(self):
        r = invoke("get", 42, "x", "default")
        assert r.as_string() == "default"


# ── merge ────────────────────────────────────────────────────────────

class TestMerge:
    def test_two_objects(self):
        r = invoke("merge", {"a": 1}, {"b": 2})
        assert r.is_object()
        assert r.get("a")._int_value == 1
        assert r.get("b")._int_value == 2

    def test_override(self):
        r = invoke("merge", {"a": 1}, {"a": 2})
        assert r.get("a")._int_value == 2

    def test_non_objects(self):
        r = invoke("merge", 42, "hello")
        assert r.is_null()

    def test_three_objects(self):
        r = invoke("merge", {"a": 1}, {"b": 2}, {"c": 3})
        assert r.is_object()
        obj = r.as_object()
        assert len(obj) == 3
