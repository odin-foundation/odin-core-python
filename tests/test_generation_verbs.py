"""Tests for generation verbs."""

import re
import pytest
from odin.transform.dyn_value import DynValue, DynType
from odin.transform.engine import TransformEngine, VerbContext
from odin.transform.verb_registry import create_default_registry


def _engine():
    return TransformEngine(create_default_registry())


def invoke(verb_name, *raw_args, ctx=None):
    engine = _engine()
    args = [_to_dyn(a) for a in raw_args]
    return engine.invoke_verb(verb_name, args, ctx)


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


# ── uuid ──────────────────────────────────────────────────────────────────────

UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

def test_uuid_random():
    r = invoke("uuid")
    assert UUID_PATTERN.match(r.as_string())

def test_uuid_unique():
    r1 = invoke("uuid")
    r2 = invoke("uuid")
    assert r1.as_string() != r2.as_string()

def test_uuid_seeded_deterministic():
    r1 = invoke("uuid", "my-seed")
    r2 = invoke("uuid", "my-seed")
    assert r1.as_string() == r2.as_string()
    assert UUID_PATTERN.match(r1.as_string())

def test_uuid_seeded_different_seeds():
    r1 = invoke("uuid", "seed-a")
    r2 = invoke("uuid", "seed-b")
    assert r1.as_string() != r2.as_string()


# ── sequence ──────────────────────────────────────────────────────────────────

def test_sequence_basic():
    ctx = VerbContext()
    engine = _engine()
    r1 = engine.invoke_verb("sequence", [_to_dyn("counter")], ctx)
    r2 = engine.invoke_verb("sequence", [_to_dyn("counter")], ctx)
    r3 = engine.invoke_verb("sequence", [_to_dyn("counter")], ctx)
    assert r1.as_int() == 1
    assert r2.as_int() == 2
    assert r3.as_int() == 3

def test_sequence_custom_start():
    ctx = VerbContext()
    engine = _engine()
    r1 = engine.invoke_verb("sequence", [_to_dyn("counter"), _to_dyn(10)], ctx)
    r2 = engine.invoke_verb("sequence", [_to_dyn("counter")], ctx)
    assert r1.as_int() == 10
    assert r2.as_int() == 11

def test_sequence_independent_names():
    ctx = VerbContext()
    engine = _engine()
    r1 = engine.invoke_verb("sequence", [_to_dyn("a")], ctx)
    r2 = engine.invoke_verb("sequence", [_to_dyn("b")], ctx)
    r3 = engine.invoke_verb("sequence", [_to_dyn("a")], ctx)
    assert r1.as_int() == 1
    assert r2.as_int() == 1
    assert r3.as_int() == 2


# ── resetSequence ─────────────────────────────────────────────────────────────

def test_reset_sequence():
    ctx = VerbContext()
    engine = _engine()
    engine.invoke_verb("sequence", [_to_dyn("counter")], ctx)
    engine.invoke_verb("sequence", [_to_dyn("counter")], ctx)
    engine.invoke_verb("resetSequence", [_to_dyn("counter")], ctx)
    r = engine.invoke_verb("sequence", [_to_dyn("counter")], ctx)
    assert r.as_int() == 0

def test_reset_sequence_with_value():
    ctx = VerbContext()
    engine = _engine()
    engine.invoke_verb("sequence", [_to_dyn("counter")], ctx)
    engine.invoke_verb("resetSequence", [_to_dyn("counter"), _to_dyn(100)], ctx)
    r = engine.invoke_verb("sequence", [_to_dyn("counter")], ctx)
    assert r.as_int() == 100


# ── nanoid ────────────────────────────────────────────────────────────────────

NANOID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

def test_nanoid_default():
    r = invoke("nanoid")
    s = r.as_string()
    assert len(s) == 21
    assert NANOID_PATTERN.match(s)

def test_nanoid_custom_size():
    r = invoke("nanoid", 10)
    assert len(r.as_string()) == 10

def test_nanoid_seeded_deterministic():
    r1 = invoke("nanoid", 21, "seed")
    r2 = invoke("nanoid", 21, "seed")
    assert r1.as_string() == r2.as_string()

def test_nanoid_seeded_different():
    r1 = invoke("nanoid", 21, "seed-a")
    r2 = invoke("nanoid", 21, "seed-b")
    assert r1.as_string() != r2.as_string()

def test_nanoid_unique():
    r1 = invoke("nanoid")
    r2 = invoke("nanoid")
    assert r1.as_string() != r2.as_string()
