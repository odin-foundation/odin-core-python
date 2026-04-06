"""Tests for geo verbs."""

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


# ── distance ─────────────────────────────────────────────────────────

class TestDistance:
    def test_same_point(self):
        r = invoke("distance", 0.0, 0.0, 0.0, 0.0)
        assert abs(r.as_float()) < 0.01

    def test_known_distance(self):
        # New York to London approx 5570 km
        r = invoke("distance", 40.7128, -74.0060, 51.5074, -0.1278)
        d = r.as_float()
        assert 5500 < d < 5700

    def test_missing_args(self):
        r = invoke("distance", 0.0, 0.0)
        assert r.is_null()

    def test_invalid_lat(self):
        r = invoke("distance", 100.0, 0.0, 0.0, 0.0)
        assert r.is_null()


# ── inBoundingBox ────────────────────────────────────────────────────

class TestInBoundingBox:
    def test_inside(self):
        r = invoke("inBoundingBox", 5.0, 5.0, 0.0, 0.0, 10.0, 10.0)
        assert r._bool_value is True

    def test_outside(self):
        r = invoke("inBoundingBox", 15.0, 5.0, 0.0, 0.0, 10.0, 10.0)
        assert r._bool_value is False

    def test_on_edge(self):
        r = invoke("inBoundingBox", 10.0, 10.0, 0.0, 0.0, 10.0, 10.0)
        assert r._bool_value is True


# ── toRadians / toDegrees ────────────────────────────────────────────

class TestRadiansDegrees:
    def test_to_radians(self):
        r = invoke("toRadians", 180.0)
        assert abs(r.as_float() - math.pi) < 0.0001

    def test_to_degrees(self):
        r = invoke("toDegrees", math.pi)
        assert abs(r.as_float() - 180.0) < 0.0001

    def test_round_trip(self):
        r1 = invoke("toRadians", 45.0)
        r2 = invoke("toDegrees", r1.as_float())
        assert abs(r2.as_float() - 45.0) < 0.0001


# ── bearing ──────────────────────────────────────────────────────────

class TestBearing:
    def test_north(self):
        r = invoke("bearing", 0.0, 0.0, 1.0, 0.0)
        assert abs(r.as_float() - 0.0) < 1.0  # Roughly north

    def test_east(self):
        r = invoke("bearing", 0.0, 0.0, 0.0, 1.0)
        assert abs(r.as_float() - 90.0) < 1.0  # Roughly east

    def test_missing_args(self):
        r = invoke("bearing", 0.0, 0.0)
        assert r.is_null()


# ── midpoint ─────────────────────────────────────────────────────────

class TestMidpoint:
    def test_basic(self):
        r = invoke("midpoint", 0.0, 0.0, 10.0, 10.0)
        assert r.is_object()
        lat = r.get("lat").as_float()
        lon = r.get("lon").as_float()
        # Midpoint should be roughly (5, 5) but on great circle
        assert 4 < lat < 6
        assert 4 < lon < 6

    def test_same_point(self):
        r = invoke("midpoint", 45.0, 90.0, 45.0, 90.0)
        lat = r.get("lat").as_float()
        lon = r.get("lon").as_float()
        assert abs(lat - 45.0) < 0.01
        assert abs(lon - 90.0) < 0.01
