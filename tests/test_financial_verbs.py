"""Tests for financial verbs."""

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


def assert_numeric(result, expected, tol=0.01):
    n = result.as_float() if result.type in (DynType.FLOAT, DynType.INTEGER) else None
    assert n is not None, f"Expected numeric, got {result}"
    assert abs(n - expected) < tol, f"Expected {expected}, got {n}"


# ── compound ─────────────────────────────────────────────────────────

class TestCompound:
    def test_basic(self):
        r = invoke("compound", 1000.0, 0.05, 10)
        assert_numeric(r, 1000 * (1.05 ** 10))

    def test_zero_rate(self):
        r = invoke("compound", 1000.0, 0.0, 10)
        assert_numeric(r, 1000.0)

    def test_one_period(self):
        r = invoke("compound", 500.0, 0.10, 1)
        assert_numeric(r, 550.0)


# ── discount ─────────────────────────────────────────────────────────

class TestDiscount:
    def test_basic(self):
        r = invoke("discount", 1000.0, 0.05, 10)
        assert_numeric(r, 1000 / (1.05 ** 10))

    def test_one_period(self):
        r = invoke("discount", 1100.0, 0.10, 1)
        assert_numeric(r, 1000.0)


# ── pmt ──────────────────────────────────────────────────────────────

class TestPmt:
    def test_basic(self):
        r = invoke("pmt", 200000.0, 0.005, 360.0)
        n = r.as_float()
        assert n > 0
        assert n < 2000

    def test_zero_rate(self):
        r = invoke("pmt", 12000.0, 0.0, 12.0)
        assert_numeric(r, 1000.0)

    def test_null_periods(self):
        r = invoke("pmt", 1000.0, 0.05, 0.0)
        assert r.is_null()


# ── fv ───────────────────────────────────────────────────────────────

class TestFv:
    def test_zero_rate(self):
        r = invoke("fv", 100.0, 0.0, 12.0)
        assert_numeric(r, 1200.0)

    def test_with_rate(self):
        r = invoke("fv", 100.0, 0.01, 12.0)
        n = r.as_float()
        assert n > 1200  # With interest, should be more


# ── pv ───────────────────────────────────────────────────────────────

class TestPv:
    def test_basic(self):
        r = invoke("pv", 100.0, 0.01, 12.0)
        n = r.as_float()
        assert n > 0
        assert n < 1200  # With discounting, should be less


# ── npv ──────────────────────────────────────────────────────────────

class TestNpv:
    def test_basic(self):
        r = invoke("npv", 0.1, [-1000.0, 300.0, 400.0, 500.0])
        n = r.as_float()
        expected = -1000 + 300 / 1.1 + 400 / (1.1 ** 2) + 500 / (1.1 ** 3)
        assert_numeric(r, expected)

    def test_zero_rate(self):
        r = invoke("npv", 0.0, [-1000.0, 500.0, 500.0])
        assert_numeric(r, 0.0)

    def test_single_flow(self):
        r = invoke("npv", 0.1, [500.0])
        assert_numeric(r, 500.0)


# ── irr ──────────────────────────────────────────────────────────────

class TestIrr:
    def test_basic(self):
        r = invoke("irr", [-1000.0, 300.0, 400.0, 500.0])
        n = r.as_float()
        assert n is not None
        assert abs(n) < 1  # Should be a reasonable rate

    def test_too_few(self):
        r = invoke("irr", [100.0])
        assert r.is_null()


# ── rate ─────────────────────────────────────────────────────────────

class TestRate:
    def test_basic(self):
        r = invoke("rate", 10.0, -100.0, 1000.0, 0.0)
        n = r.as_float()
        assert n is not None
        assert math.isfinite(n)


# ── nper ─────────────────────────────────────────────────────────────

class TestNper:
    def test_zero_rate(self):
        r = invoke("nper", 0.0, -100.0, 5000.0)
        assert_numeric(r, 50.0)

    def test_with_rate(self):
        r = invoke("nper", 0.01, -100.0, 5000.0)
        n = r.as_float()
        assert n > 0


# ── depreciation ─────────────────────────────────────────────────────

class TestDepreciation:
    def test_basic(self):
        r = invoke("depreciation", 10000.0, 1000.0, 5.0)
        assert_numeric(r, 1800.0)

    def test_zero_life(self):
        r = invoke("depreciation", 10000.0, 1000.0, 0.0)
        assert r.is_null()


# ── variance / std ───────────────────────────────────────────────────

class TestStatistics:
    def test_variance_population(self):
        r = invoke("variance", [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        n = r.as_float()
        assert abs(n - 4.0) < 0.01

    def test_variance_sample(self):
        r = invoke("varianceSample", [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        n = r.as_float()
        assert n > 4.0  # Sample variance > population variance

    def test_std(self):
        r = invoke("std", [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        n = r.as_float()
        assert abs(n - 2.0) < 0.01

    def test_std_sample(self):
        r = invoke("stdSample", [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        n = r.as_float()
        assert n > 2.0

    def test_empty_array(self):
        r = invoke("variance", [])
        assert r.is_null()

    def test_single_item_sample(self):
        r = invoke("varianceSample", [5.0])
        assert r.is_null()


# ── median ───────────────────────────────────────────────────────────

class TestMedian:
    def test_odd(self):
        r = invoke("median", [1.0, 3.0, 2.0])
        assert_numeric(r, 2.0)

    def test_even(self):
        r = invoke("median", [1.0, 2.0, 3.0, 4.0])
        assert_numeric(r, 2.5)

    def test_empty(self):
        r = invoke("median", [])
        assert r.is_null()


# ── mode ─────────────────────────────────────────────────────────────

class TestMode:
    def test_basic(self):
        r = invoke("mode", [1.0, 2.0, 2.0, 3.0])
        assert_numeric(r, 2.0)

    def test_tie(self):
        r = invoke("mode", [1.0, 1.0, 2.0, 2.0, 3.0])
        # First mode wins
        assert_numeric(r, 1.0)


# ── percentile / quantile ───────────────────────────────────────────

class TestPercentile:
    def test_median_percentile(self):
        r = invoke("percentile", [1.0, 2.0, 3.0, 4.0, 5.0], 50.0)
        assert_numeric(r, 3.0)

    def test_quartile(self):
        r = invoke("quantile", [1.0, 2.0, 3.0, 4.0, 5.0], 0.25)
        n = r.as_float()
        assert abs(n - 2.0) < 0.01


# ── covariance / correlation ─────────────────────────────────────────

class TestCovCorr:
    def test_covariance(self):
        r = invoke("covariance", [1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
        n = r.as_float()
        assert n > 0

    def test_correlation_perfect(self):
        r = invoke("correlation", [1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
        assert_numeric(r, 1.0, tol=0.001)


# ── zscore ───────────────────────────────────────────────────────────

class TestZscore:
    def test_basic(self):
        r = invoke("zscore", 10.0, 5.0, 2.0)
        assert_numeric(r, 2.5)

    def test_zero_stddev(self):
        r = invoke("zscore", 10.0, 5.0, 0.0)
        assert r.is_null()


# ── interpolate ──────────────────────────────────────────────────────

class TestInterpolate:
    def test_midpoint(self):
        r = invoke("interpolate", 0.0, 10.0, 0.5)
        assert_numeric(r, 5.0)

    def test_endpoints(self):
        r = invoke("interpolate", 0.0, 10.0, 0.0)
        assert_numeric(r, 0.0)


# ── weightedAvg ──────────────────────────────────────────────────────

class TestWeightedAvg:
    def test_basic(self):
        r = invoke("weightedAvg", [80.0, 90.0], [1.0, 3.0])
        assert_numeric(r, 87.5)

    def test_empty(self):
        r = invoke("weightedAvg", [], [])
        assert r.is_null()
