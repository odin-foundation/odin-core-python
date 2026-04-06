"""Golden JSON import tests from sdk/golden/json-import/.

Tests JSON type handling, extraction, and type preservation through transforms.
"""

import json
import math
import pytest
from pathlib import Path

import odin
from odin.transform.dyn_value import DynValue
from odin.transform.source_parsers.json_parser import parse_json
from tests.golden.conftest import find_golden_dir


GOLDEN_DIR = find_golden_dir()


def load_json_import_tests():
    """Load all json-import test cases."""
    tests = []
    import_dir = GOLDEN_DIR / "json-import"
    if not import_dir.exists():
        return tests

    for json_file in sorted(import_dir.rglob("*.json")):
        if json_file.name == "manifest.json":
            continue
        with open(json_file, encoding="utf-8") as f:
            suite = json.load(f)
        suite_name = suite.get("suite", json_file.stem)
        for test in suite.get("tests", []):
            test_id = f"{suite_name}::{test.get('id', 'unknown')}"
            tests.append(pytest.param(test, id=test_id))
    return tests


def _assert_value_matches(actual, expected, path=""):
    """Deep-compare a DynValue output against expected JSON value."""
    if expected is None:
        assert actual is None or actual.is_null(), (
            f"Expected null at {path}, got {actual}"
        )
    elif isinstance(expected, bool):
        assert actual is not None, f"Missing value at {path}"
        assert actual.as_bool() == expected, (
            f"Bool mismatch at {path}: {actual.as_bool()} != {expected}"
        )
    elif isinstance(expected, int):
        assert actual is not None, f"Missing value at {path}"
        assert actual.as_int() == expected, (
            f"Int mismatch at {path}: {actual.as_int()} != {expected}"
        )
    elif isinstance(expected, float):
        assert actual is not None, f"Missing value at {path}"
        assert math.isclose(actual.as_float(), expected, rel_tol=1e-5), (
            f"Float mismatch at {path}: {actual.as_float()} != {expected}"
        )
    elif isinstance(expected, str):
        assert actual is not None, f"Missing value at {path}"
        assert actual.as_string() == expected, (
            f"String mismatch at {path}: {actual.as_string()!r} != {expected!r}"
        )
    elif isinstance(expected, dict):
        assert actual is not None and actual.is_object(), (
            f"Expected object at {path}"
        )
        obj = actual.as_object()
        for key, exp_val in expected.items():
            _assert_value_matches(obj.get(key), exp_val, f"{path}.{key}")
    elif isinstance(expected, list):
        assert actual is not None and actual.is_array(), (
            f"Expected array at {path}"
        )
        arr = actual.as_array()
        assert len(arr) == len(expected), (
            f"Array length mismatch at {path}: {len(arr)} != {len(expected)}"
        )
        for i, exp_val in enumerate(expected):
            _assert_value_matches(arr[i], exp_val, f"{path}[{i}]")


@pytest.mark.golden
@pytest.mark.parametrize("test_case", load_json_import_tests())
def test_golden_json_import(test_case):
    """Run a single golden json-import test case."""
    transform_text = test_case["transform"]
    input_data = test_case["input"]
    expected = test_case.get("expected", {})

    transform = odin.parse_transform(transform_text)
    source = parse_json(input_data)
    result = odin.execute_transform(transform, source)

    assert not result.errors, (
        f"[{test_case.get('id')}] Transform failed: "
        + ", ".join(
            f"[{e.code}] {e.message}" if e.code else e.message
            for e in result.errors
        )
    )

    if "output" in expected:
        output = result.output
        assert output is not None, f"[{test_case.get('id')}] No output"
        # expected["output"] is e.g. {"result": "hello world"} which maps to
        # the {output} segment's fields. The DynValue output has structure
        # {output: {result: ...}}, so navigate into the "output" segment.
        out_seg = output.get("output") if output.is_object() else None
        assert out_seg is not None, (
            f"[{test_case.get('id')}] Missing 'output' segment in result"
        )
        _assert_value_matches(out_seg, expected["output"], "output")
