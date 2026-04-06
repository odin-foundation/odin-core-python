"""Tests for aggregation verbs."""

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


# ── sum ──────────────────────────────────────────────────────────────

class TestSum:
    def test_array(self):
        r = invoke("sum", [1, 2, 3, 4])
        assert r._int_value == 10

    def test_empty(self):
        r = invoke("sum", [])
        assert r._int_value == 0

    def test_with_nulls(self):
        r = invoke("sum", [1, None, 3])
        assert r._int_value == 4

    def test_floats(self):
        r = invoke("sum", [1.5, 2.5])
        assert abs(r.as_float() - 4.0) < 0.01


# ── count ────────────────────────────────────────────────────────────

class TestCount:
    def test_array(self):
        r = invoke("count", [1, 2, 3])
        assert r._int_value == 3

    def test_skips_nulls(self):
        r = invoke("count", [1, None, 3])
        assert r._int_value == 2

    def test_empty(self):
        r = invoke("count", [])
        assert r._int_value == 0


# ── min / max ────────────────────────────────────────────────────────

class TestMinMax:
    def test_min_array(self):
        r = invoke("min", [5, 3, 8, 1, 7])
        assert r._int_value == 1

    def test_max_array(self):
        r = invoke("max", [5, 3, 8, 1, 7])
        assert r._int_value == 8

    def test_min_empty(self):
        r = invoke("min", [])
        assert r.is_null()

    def test_max_empty(self):
        r = invoke("max", [])
        assert r.is_null()

    def test_min_varargs(self):
        r = invoke("min", 5, 3, 8)
        assert r._int_value == 3

    def test_max_varargs(self):
        r = invoke("max", 5, 3, 8)
        assert r._int_value == 8


# ── avg ──────────────────────────────────────────────────────────────

class TestAvg:
    def test_basic(self):
        r = invoke("avg", [2, 4, 6])
        assert abs(r.as_float() - 4.0) < 0.01

    def test_empty(self):
        r = invoke("avg", [])
        assert r.is_null()


# ── first / last ─────────────────────────────────────────────────────

class TestFirstLast:
    def test_first(self):
        r = invoke("first", [10, 20, 30])
        assert r._int_value == 10

    def test_last(self):
        r = invoke("last", [10, 20, 30])
        assert r._int_value == 30

    def test_first_empty(self):
        r = invoke("first", [])
        assert r.is_null()

    def test_last_empty(self):
        r = invoke("last", [])
        assert r.is_null()
