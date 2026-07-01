"""Transform execution guard: fuel budget (T016), wall-clock timeout (T017),
and expression-depth enforcement (T018).

Guards charge only when their limit is set (> 0); depth uses its standing
default. Aborts are not downgraded by onError and surface as a failed
TransformResult, never thrown past execute.
"""

from __future__ import annotations

import pytest

from odin.transform import engine as engine_module
from odin.transform import limits
from odin.transform.engine import TransformEngine
from odin.transform.transform_parser import parse_transform
from odin.transform.verb_registry import create_default_registry

HEADER = '{$}\nodin = "1.0.0"\ntransform = "1.0.0"\ndirection = "json->json"\n\n'


def header_with(on_error: str) -> str:
    return (
        HEADER
        + f'{{$target}}\nformat = "json"\nonError = "{on_error}"\n\n'
    )


def run(body, source=None, head=HEADER, **opts):
    transform = parse_transform(head + body)
    engine = TransformEngine(create_default_registry(), **opts)
    return engine.execute(transform, source if source is not None else {})


def nest_abs(n: int) -> str:
    """Chain of n nested unary verbs, evaluated one level per node."""
    return "{out}\nr = " + "%abs " * n + "##1"


@pytest.fixture(autouse=True)
def restore_limits():
    """Save and restore the module-level limits around each test."""
    saved = (
        limits.MAX_TRANSFORM_FUEL,
        limits.TRANSFORM_TIMEOUT_MS,
        limits.MAX_EXPRESSION_DEPTH,
    )
    original_now = engine_module._now_ms
    yield
    (
        limits.MAX_TRANSFORM_FUEL,
        limits.TRANSFORM_TIMEOUT_MS,
        limits.MAX_EXPRESSION_DEPTH,
    ) = saved
    engine_module._now_ms = original_now


class TestUnboundedWhenUnset:
    def test_runs_a_normal_transform_to_completion(self):
        r = run('{out}\nr = %upper "hi"')
        assert r.success is True
        assert len(r.errors) == 0

    def test_does_not_charge_fuel_when_cap_is_zero(self):
        limits.MAX_TRANSFORM_FUEL = 0
        big = list(range(500, 0, -1))
        r = run("{out}\nr = %sort @big", {"big": big})
        assert r.success is True


class TestFuelBudget:
    def test_aborts_over_computing_transform_with_failed_result(self):
        limits.MAX_TRANSFORM_FUEL = 50
        big = list(range(200, 0, -1))
        r = run("{out}\nr = %sort @big", {"big": big})
        assert r.success is False
        assert any(e.code == "T016" for e in r.errors)

    def test_charges_array_verbs_proportional_to_width(self):
        limits.MAX_TRANSFORM_FUEL = 50
        small = run("{out}\nr = %sort @big", {"big": [3, 1, 2]})
        assert small.success is True
        large = run("{out}\nr = %sort @big", {"big": list(range(200, 0, -1))})
        assert large.success is False
        assert any(e.code == "T016" for e in large.errors)


class TestWallClockTimeout:
    def test_aborts_when_elapsed_exceeds_timeout(self):
        limits.TRANSFORM_TIMEOUT_MS = 100
        # Each read advances well past the bound, so any read after start
        # reports elapsed > timeout regardless of call ordering.
        state = {"clock": 0.0}

        def fake_now():
            state["clock"] += 10_000.0
            return state["clock"]

        engine_module._now_ms = fake_now
        big = list(range(300, 0, -1))
        r = run("{out}\nr = %sort @big", {"big": big})
        assert r.success is False
        assert any(e.code == "T017" for e in r.errors)


class TestExpressionDepth:
    def test_yields_a_clean_depth_error_under_a_low_cap(self):
        limits.MAX_EXPRESSION_DEPTH = 8
        r = run(nest_abs(30))
        assert r.success is False
        assert any(e.code == "T018" for e in r.errors)

    def test_converts_deep_nesting_into_typed_error_not_stack_overflow(self):
        # Standing default (32); deep nesting must not raise RecursionError.
        r = run(nest_abs(200))
        assert r.success is False
        assert any(e.code == "T018" for e in r.errors)


class TestNonSwallowableAbort:
    def test_is_not_downgraded_to_a_warning_by_on_error(self):
        limits.MAX_TRANSFORM_FUEL = 50
        big = list(range(200, 0, -1))
        r = run("{out}\nr = %sort @big", {"big": big}, header_with("warn"))
        assert r.success is False
        assert any(e.code == "T016" for e in r.errors)
        assert not any(w.code == "T016" for w in r.warnings)


class TestPerCallOverrides:
    def test_per_call_fuel_budget_aborts_with_no_global_limit(self):
        big = list(range(200, 0, -1))
        r = run("{out}\nr = %sort @big", {"big": big}, max_transform_fuel=50)
        assert r.success is False
        assert any(e.code == "T016" for e in r.errors)

    def test_per_call_fuel_overrides_a_set_global_limit(self):
        limits.MAX_TRANSFORM_FUEL = 50
        big = list(range(200, 0, -1))
        r = run("{out}\nr = %sort @big", {"big": big}, max_transform_fuel=1_000_000)
        assert r.success is True

    def test_per_call_zero_opts_a_call_out_of_a_global_fuel_cap(self):
        limits.MAX_TRANSFORM_FUEL = 50
        big = list(range(200, 0, -1))
        r = run("{out}\nr = %sort @big", {"big": big}, max_transform_fuel=0)
        assert r.success is True

    def test_per_call_expression_depth_cap_yields_t018(self):
        r = run(nest_abs(30), max_expression_depth=8)
        assert r.success is False
        assert any(e.code == "T018" for e in r.errors)

    def test_per_call_timeout_yields_t017(self):
        state = {"clock": 0.0}

        def fake_now():
            state["clock"] += 10_000.0
            return state["clock"]

        engine_module._now_ms = fake_now
        big = list(range(300, 0, -1))
        r = run("{out}\nr = %sort @big", {"big": big}, transform_timeout_ms=100)
        assert r.success is False
        assert any(e.code == "T017" for e in r.errors)
