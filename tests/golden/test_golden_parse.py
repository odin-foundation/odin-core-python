"""Golden parse tests - cross-language test suite."""
import json
import math
import pytest
from decimal import Decimal
from pathlib import Path

import odin
from odin.types.values import (
    OdinNull, OdinBoolean, OdinString, OdinNumber, OdinInteger,
    OdinCurrency, OdinPercent, OdinDate, OdinTimestamp, OdinTime,
    OdinDuration, OdinReference, OdinBinary, OdinVerbExpression,
)
from odin.types.document import OdinModifiers


def find_golden_dir():
    """Locate sdk/golden/ directory."""
    candidates = [
        Path(__file__).parent.parent.parent.parent / "golden",
        Path(__file__).parent.parent.parent / ".." / "golden",
    ]
    for p in candidates:
        resolved = p.resolve()
        if resolved.is_dir():
            return resolved
    raise RuntimeError("Cannot find sdk/golden/ directory")


GOLDEN_DIR = find_golden_dir()


def load_parse_tests():
    """Load all parse test cases from golden/parse/."""
    tests = []
    parse_dir = GOLDEN_DIR / "parse"
    for json_file in sorted(parse_dir.rglob("*.json")):
        if json_file.name == "manifest.json":
            continue
        with open(json_file, encoding="utf-8") as f:
            suite = json.load(f)
        suite_name = suite.get("suite", json_file.stem)
        for test in suite.get("tests", []):
            if test.get("_comment") and "id" not in test:
                continue
            test_id = f"{suite_name}::{test.get('id', 'unknown')}"
            tests.append(pytest.param(test, id=test_id))
    return tests


def assert_value_matches(actual, expected, path=""):
    """Compare an OdinValue instance against the JSON expected format."""
    exp_type = expected.get("type")

    if exp_type == "null":
        assert isinstance(actual, OdinNull), f"Expected null at {path}, got {type(actual).__name__}"

    elif exp_type == "boolean":
        assert isinstance(actual, OdinBoolean), f"Expected boolean at {path}, got {type(actual).__name__}"
        assert actual.value == expected["value"], f"Boolean mismatch at {path}: {actual.value} != {expected['value']}"

    elif exp_type == "string":
        assert isinstance(actual, OdinString), f"Expected string at {path}, got {type(actual).__name__}"
        assert actual.value == expected["value"], f"String mismatch at {path}: {actual.value!r} != {expected['value']!r}"

    elif exp_type == "number":
        assert isinstance(actual, OdinNumber), f"Expected number at {path}, got {type(actual).__name__}"
        if "value" in expected:
            exp_val = expected["value"]
            assert math.isclose(actual.value, exp_val, rel_tol=1e-12), \
                f"Number mismatch at {path}: {actual.value} != {exp_val}"
        if "raw" in expected:
            assert actual.raw == expected["raw"], f"Raw mismatch at {path}: {actual.raw!r} != {expected['raw']!r}"

    elif exp_type == "integer":
        assert isinstance(actual, OdinInteger), f"Expected integer at {path}, got {type(actual).__name__}"
        if "value" in expected:
            assert actual.value == expected["value"], f"Integer mismatch at {path}: {actual.value} != {expected['value']}"
        if "raw" in expected:
            assert actual.raw == expected["raw"], f"Raw mismatch at {path}: {actual.raw!r} != {expected['raw']!r}"

    elif exp_type == "currency":
        assert isinstance(actual, OdinCurrency), f"Expected currency at {path}, got {type(actual).__name__}"
        if "value" in expected:
            exp_val = Decimal(str(expected["value"]))
            assert float(actual.value) == pytest.approx(float(exp_val), abs=1e-10), \
                f"Currency mismatch at {path}: {actual.value} != {exp_val}"
        if "decimalPlaces" in expected:
            assert actual.decimal_places == expected["decimalPlaces"], \
                f"Decimal places mismatch at {path}: {actual.decimal_places} != {expected['decimalPlaces']}"
        if "currencyCode" in expected:
            assert actual.currency_code == expected["currencyCode"], \
                f"Currency code mismatch at {path}: {actual.currency_code} != {expected['currencyCode']}"
        if "raw" in expected:
            assert actual.raw is not None

    elif exp_type == "percent":
        assert isinstance(actual, OdinPercent), f"Expected percent at {path}, got {type(actual).__name__}"
        if "value" in expected:
            assert math.isclose(actual.value, expected["value"], rel_tol=1e-12), \
                f"Percent mismatch at {path}: {actual.value} != {expected['value']}"

    elif exp_type == "date":
        assert isinstance(actual, OdinDate), f"Expected date at {path}, got {type(actual).__name__}"
        exp_raw = expected.get("raw") or expected.get("value")
        if exp_raw:
            assert actual.raw == exp_raw, f"Date raw mismatch at {path}: {actual.raw!r} != {exp_raw!r}"

    elif exp_type == "timestamp":
        assert isinstance(actual, OdinTimestamp), f"Expected timestamp at {path}, got {type(actual).__name__}"
        exp_raw = expected.get("raw") or expected.get("value")
        if exp_raw:
            assert actual.raw == exp_raw, f"Timestamp raw mismatch at {path}: {actual.raw!r} != {exp_raw!r}"

    elif exp_type == "time":
        assert isinstance(actual, OdinTime), f"Expected time at {path}, got {type(actual).__name__}"
        assert actual.value == expected["value"], f"Time mismatch at {path}: {actual.value!r} != {expected['value']!r}"

    elif exp_type == "duration":
        assert isinstance(actual, OdinDuration), f"Expected duration at {path}, got {type(actual).__name__}"
        assert actual.value == expected["value"], f"Duration mismatch at {path}: {actual.value!r} != {expected['value']!r}"

    elif exp_type == "reference":
        assert isinstance(actual, OdinReference), f"Expected reference at {path}, got {type(actual).__name__}"
        assert actual.path == expected["path"], f"Reference path mismatch at {path}: {actual.path!r} != {expected['path']!r}"

    elif exp_type == "binary":
        assert isinstance(actual, OdinBinary), f"Expected binary at {path}, got {type(actual).__name__}"
        if "algorithm" in expected:
            assert actual.algorithm == expected["algorithm"], \
                f"Algorithm mismatch at {path}: {actual.algorithm} != {expected['algorithm']}"

    elif exp_type == "verb":
        assert isinstance(actual, OdinVerbExpression), f"Expected verb at {path}, got {type(actual).__name__}"

    else:
        pytest.skip(f"Unknown type in golden test: {exp_type}")


@pytest.mark.golden
@pytest.mark.parametrize("test_case", load_parse_tests())
def test_golden_parse(test_case):
    """Run a single golden parse test case."""
    input_text = test_case["input"]

    # Error tests
    if "expectError" in test_case:
        with pytest.raises(odin.ParseError) as exc_info:
            odin.parse(input_text)
        if "code" in test_case["expectError"]:
            assert exc_info.value.code == test_case["expectError"]["code"], \
                f"Expected error code {test_case['expectError']['code']}, got {exc_info.value.code}: {exc_info.value}"
        return

    # Success tests
    expected = test_case.get("expected", {})

    # Multi-document tests use "documents" key
    if "documents" in expected:
        # For now, parse and validate the first document
        doc = odin.parse(input_text)

        first_doc_exp = expected["documents"][0]
        if "metadata" in first_doc_exp:
            for key, exp_val in first_doc_exp["metadata"].items():
                actual = doc.metadata.get(key)
                if actual is None:
                    actual = doc.get(f"$.{key}")
                assert actual is not None, f"Missing metadata key: {key}"
                if isinstance(exp_val, str):
                    assert isinstance(actual, OdinString), f"Expected string for metadata {key}"
                    assert actual.value == exp_val

        if "assignments" in first_doc_exp:
            for path, exp_val in first_doc_exp["assignments"].items():
                actual = doc.get(path)
                assert actual is not None, f"Missing path: {path}"
                assert_value_matches(actual, exp_val, path)
        return

    # Single document
    doc = odin.parse(input_text)

    if "assignments" in expected:
        for path, exp_val in expected["assignments"].items():
            actual = doc.get(path)
            assert actual is not None, f"Missing path: {path}"
            assert_value_matches(actual, exp_val, path)

    if "modifiers" in expected:
        for path, exp_mods in expected["modifiers"].items():
            actual_mods = doc.modifiers.get(path)
            assert actual_mods is not None, f"Missing modifiers for path: {path}"
            if "required" in exp_mods:
                assert actual_mods.required == exp_mods["required"], \
                    f"Required mismatch at {path}: {actual_mods.required} != {exp_mods['required']}"
            if "confidential" in exp_mods:
                assert actual_mods.confidential == exp_mods["confidential"], \
                    f"Confidential mismatch at {path}: {actual_mods.confidential} != {exp_mods['confidential']}"
            if "deprecated" in exp_mods:
                assert actual_mods.deprecated == exp_mods["deprecated"], \
                    f"Deprecated mismatch at {path}: {actual_mods.deprecated} != {exp_mods['deprecated']}"

    if "metadata" in expected:
        for key, exp_val in expected["metadata"].items():
            actual = doc.metadata.get(key)
            if actual is None:
                actual = doc.get(f"$.{key}")
            assert actual is not None, f"Missing metadata key: {key}"
