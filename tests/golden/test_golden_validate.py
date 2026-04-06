"""Golden validation tests from sdk/golden/validate/.

Tests V001-V013 validation error codes and format validators.
"""

import json
import os
import pytest
from pathlib import Path

import odin
from odin.types.options import ValidateOptions
from tests.golden.conftest import find_golden_dir


GOLDEN_DIR = find_golden_dir()


def load_validate_tests():
    """Load all validate test cases from golden/validate/."""
    tests = []
    validate_dir = GOLDEN_DIR / "validate"
    if not validate_dir.exists():
        return tests

    for json_file in sorted(validate_dir.rglob("*.json")):
        if json_file.name == "manifest.json":
            continue
        with open(json_file, encoding="utf-8") as f:
            suite = json.load(f)
        suite_name = suite.get("suite", json_file.stem)
        for test in suite.get("tests", []):
            test_id = f"{suite_name}::{test.get('id', 'unknown')}"
            test["_file_path"] = str(json_file)
            tests.append(pytest.param(test, id=test_id))
    return tests


@pytest.mark.golden
@pytest.mark.parametrize("test_case", load_validate_tests())
def test_golden_validate(test_case):
    """Run a single golden validate test case."""
    input_text = test_case.get("input", "")

    # Parse the document (empty string -> empty doc)
    if input_text == "":
        doc = odin.parse("{$}\nodin = \"1.0.0\"")
    else:
        doc = odin.parse(input_text)

    # Get schema text
    if "schemaFile" in test_case:
        schema_path = os.path.join(
            os.path.dirname(test_case["_file_path"]),
            test_case["schemaFile"],
        )
        with open(schema_path, encoding="utf-8") as f:
            schema_text = f.read()
    elif "schema" in test_case:
        schema_text = test_case["schema"]
    else:
        pytest.fail(f"[{test_case.get('id')}] No schema or schemaFile")
        return

    schema = odin.parse_schema(schema_text)

    # Build options
    options = None
    if "options" in test_case and test_case["options"].get("strict"):
        options = ValidateOptions(strict=True)

    result = odin.validate(doc, schema, options)

    expected = test_case.get("expected", {})

    if "valid" in expected:
        assert result.valid == expected["valid"], (
            f"[{test_case.get('id')}] Expected valid={expected['valid']}, "
            f"got valid={result.valid}, errors={[e.code for e in result.errors]}"
        )

    if "errors" in expected:
        for exp_error in expected["errors"]:
            if "code" in exp_error:
                codes = [e.code for e in result.errors]
                assert exp_error["code"] in codes, (
                    f"[{test_case.get('id')}] Expected error code "
                    f"{exp_error['code']}, got {codes}"
                )
            if "path" in exp_error:
                paths = [e.path for e in result.errors]
                assert exp_error["path"] in paths, (
                    f"[{test_case.get('id')}] Expected error path "
                    f"{exp_error['path']}, got {paths}"
                )

    if "expectError" in test_case:
        assert not result.valid
        exp = test_case["expectError"]
        if "code" in exp:
            codes = [e.code for e in result.errors]
            assert exp["code"] in codes
