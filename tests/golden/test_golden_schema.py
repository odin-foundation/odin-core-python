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
