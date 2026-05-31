"""Golden schema composition tests from sdk/golden/schema/."""

import json
import pytest
from pathlib import Path

import odin
from tests.golden.conftest import find_golden_dir


GOLDEN_DIR = find_golden_dir()


def load_schema_tests():
    """Load all schema test cases from golden/schema/."""
    tests = []
    schema_dir = GOLDEN_DIR / "schema"
    if not schema_dir.exists():
        return tests

    for json_file in sorted(schema_dir.rglob("*.json")):
        if json_file.name == "manifest.json":
            continue
        with open(json_file, encoding="utf-8") as f:
            suite = json.load(f)
        suite_name = suite.get("suite", json_file.stem)
        for test in suite.get("tests", []):
            test_id = f"{suite_name}::{test.get('id', 'unknown')}"
            tests.append(pytest.param(test, id=test_id))
    return tests


@pytest.mark.golden
@pytest.mark.parametrize("test_case", load_schema_tests())
def test_golden_schema(test_case):
    """Run a single golden schema test case."""
    input_text = test_case.get("input") or test_case.get("schema") or ""

    if "expectError" in test_case:
        with pytest.raises(Exception):
            odin.parse_schema(input_text)
        return

    schema = odin.parse_schema(input_text)
    assert schema is not None

    # Structural cases assert parsed type/root field keys; others are parse-success only.
    if test_case.get("structural"):
        expected = test_case.get("expected", {})
        for type_name, type_spec in expected.get("types", {}).items():
            assert type_name in schema.types, f"missing type {type_name}"
            parsed_fields = schema.types[type_name].fields
            for key in type_spec.get("fields", {}):
                assert key in parsed_fields, f"missing field {key} in type {type_name}"
        for key in expected.get("fields", {}):
            assert key in schema.fields, f"missing root field {key}"
