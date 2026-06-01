"""Unit tests for nested :loop directives in transform segments."""

import pytest

from odin.transform.transform_parser import parse_transform
from odin.transform.engine import TransformEngine
from odin.transform.verb_registry import create_default_registry


def _run(transform_text: str, source: dict):
    transform = parse_transform(transform_text)
    engine = TransformEngine(create_default_registry())
    return engine.execute(transform, source)


def _dyn_to_py(dv):
    if dv is None or dv.is_null():
        return None
    if dv.is_array():
        return [_dyn_to_py(i) for i in dv.as_array()]
    if dv.is_object():
        return {k: _dyn_to_py(v) for k, v in dv.as_object().items()}
    if dv.is_integer():
        return dv.as_int()
    if dv.is_bool():
        return dv.as_bool()
    if dv.is_string():
        return dv.as_string()
    return dv.as_float()


def _rows(transform_text: str, source: dict):
    result = _run(transform_text, source)
    assert not result.errors, result.errors
    return _dyn_to_py(result.output)["rows"]


_HEADER = (
    '{$}\n'
    'direction = "json->json"\n'
    'target.format = "json"\n'
)


# ── Happy path ──────────────────────────────────────────────────────────────


class TestNestedLoopsHappy:
    def test_two_level_cross_product(self):
        transform = _HEADER + (
            '{rows[]}\n'
            ':loop vehicles :as veh\n'
            ':loop .coverages :as cov\n'
            'vin = "@veh.vin"\n'
            'code = "@cov.code"\n'
        )
        source = {"vehicles": [
            {"vin": "A", "coverages": [{"code": "x"}, {"code": "y"}]},
            {"vin": "B", "coverages": [{"code": "z"}]},
        ]}
        assert _rows(transform, source) == [
            {"vin": "A", "code": "x"},
            {"vin": "A", "code": "y"},
            {"vin": "B", "code": "z"},
        ]

    def test_three_level_cross_product(self):
        transform = _HEADER + (
            '{rows[]}\n'
            ':loop regions :as r\n'
            ':loop .stores :as s\n'
            ':loop .items :as i\n'
            'region = "@r.name"\n'
            'store = "@s.id"\n'
            'sku = "@i.sku"\n'
        )
        source = {"regions": [
            {"name": "West", "stores": [
                {"id": "S1", "items": [{"sku": "X"}, {"sku": "Y"}]},
            ]},
            {"name": "East", "stores": [
                {"id": "S2", "items": [{"sku": "Z"}]},
            ]},
        ]}
        assert _rows(transform, source) == [
            {"region": "West", "store": "S1", "sku": "X"},
            {"region": "West", "store": "S1", "sku": "Y"},
            {"region": "East", "store": "S2", "sku": "Z"},
        ]

    def test_counter_binds_innermost_index_and_resets_per_outer(self):
        transform = _HEADER + (
            '{rows[]}\n'
            ':loop vehicles :as veh\n'
            ':loop .coverages :as cov\n'
            ':counter idx\n'
            'vin = "@veh.vin"\n'
            'i = "@idx"\n'
        )
        source = {"vehicles": [
            {"vin": "A", "coverages": [{}, {}]},
            {"vin": "B", "coverages": [{}, {}, {}]},
        ]}
        rows = _rows(transform, source)
        assert [r["i"] for r in rows] == [0, 1, 0, 1, 2]
        assert [r["vin"] for r in rows] == ["A", "A", "B", "B", "B"]


# ── Edge cases ──────────────────────────────────────────────────────────────


class TestNestedLoopsEdge:
    def test_empty_inner_array_yields_no_rows(self):
        transform = _HEADER + (
            '{rows[]}\n'
            ':loop vehicles :as veh\n'
            ':loop .coverages :as cov\n'
            'vin = "@veh.vin"\n'
            'code = "@cov.code"\n'
        )
        source = {"vehicles": [
            {"vin": "V1", "coverages": [{"code": "A"}]},
            {"vin": "V2", "coverages": []},
            {"vin": "V3", "coverages": [{"code": "B"}]},
        ]}
        assert _rows(transform, source) == [
            {"vin": "V1", "code": "A"},
            {"vin": "V3", "code": "B"},
        ]

    def test_missing_inner_key_yields_no_rows(self):
        transform = _HEADER + (
            '{rows[]}\n'
            ':loop vehicles :as veh\n'
            ':loop .coverages :as cov\n'
            'vin = "@veh.vin"\n'
        )
        source = {"vehicles": [{"vin": "V1"}, {"vin": "V2", "coverages": [{}]}]}
        rows = _rows(transform, source)
        assert rows == [{"vin": "V2"}]

    def test_empty_outer_array_yields_empty_rows(self):
        transform = _HEADER + (
            '{rows[]}\n'
            ':loop vehicles :as veh\n'
            ':loop .coverages :as cov\n'
            'vin = "@veh.vin"\n'
        )
        assert _rows(transform, {"vehicles": []}) == []


# ── Error / non-array handling ───────────────────────────────────────────────


class TestNestedLoopsErrors:
    def test_non_array_inner_raises_t009(self):
        transform = _HEADER + (
            '{rows[]}\n'
            ':loop vehicles :as veh\n'
            ':loop .coverages :as cov\n'
            'vin = "@veh.vin"\n'
        )
        # `coverages` is a present scalar, not an array → T009.
        source = {"vehicles": [
            {"vin": "V1", "coverages": "not-an-array"},
            {"vin": "V2", "coverages": [{}]},
        ]}
        result = _run(transform, source)
        assert not result.success
        assert result.errors[0].code == "T009"

    def test_non_array_outer_raises_t009(self):
        transform = _HEADER + (
            '{rows[]}\n'
            ':loop vehicles :as veh\n'
            ':loop .coverages :as cov\n'
            'vin = "@veh.vin"\n'
        )
        result = _run(transform, {"vehicles": "scalar"})
        assert not result.success
        assert result.errors[0].code == "T009"

    def test_absent_loop_source_yields_no_rows_without_error(self):
        transform = _HEADER + (
            '{rows[]}\n'
            ':loop missing :as m\n'
            'vin = "@m.vin"\n'
        )
        result = _run(transform, {"other": 1})
        assert not result.errors
        assert _dyn_to_py(result.output)["rows"] == []
