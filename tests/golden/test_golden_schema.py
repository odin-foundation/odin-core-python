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

    # Value-level assertions: type kind, unions, defaults, constraints, conditionals, flags.
    _run_assertions(test_case, schema)


def _run_assertions(test_case, schema):
    """Assert constraint values declared under test['assert']."""
    assertions = test_case.get("assert")
    if not assertions:
        return

    for field_path, spec in assertions.get("fields", {}).items():
        _assert_field(schema.fields.get(field_path), spec, f"field '{field_path}'")

    for type_name, type_spec in assertions.get("types", {}).items():
        assert type_name in schema.types, f"type '{type_name}' should be defined"
        for field_key, spec in type_spec.get("fields", {}).items():
            _assert_field(
                schema.types[type_name].fields.get(field_key),
                spec,
                f"type '{type_name}' field '{field_key}'",
            )


def _assert_field(field, spec, label):
    """Assert a single parsed SchemaField against a value-level spec."""
    assert field is not None, f"{label} should be defined"
    ft = field.field_type

    if "typeKind" in spec:
        assert getattr(ft, "kind", None) == spec["typeKind"], f"{label} type kind"
    if "typeRefName" in spec:
        assert getattr(ft, "name", None) == spec["typeRefName"], f"{label} typeRef name"
    if "required" in spec:
        assert field.required == spec["required"], f"{label} required"
    if "nullable" in spec:
        assert field.nullable == spec["nullable"], f"{label} nullable"
    if "immutable" in spec:
        assert field.immutable == spec["immutable"], f"{label} immutable"
    if "computed" in spec:
        assert field.computed == spec["computed"], f"{label} computed"
    if "deprecated" in spec:
        assert field.deprecated == spec["deprecated"], f"{label} deprecated"

    if "union" in spec:
        assert getattr(ft, "kind", None) == "union", f"{label} should be a union"
        kinds = sorted(t.kind for t in ft.types)
        assert kinds == sorted(spec["union"]), f"{label} union members"

    if "default" in spec:
        default = field.default_value
        assert default is not None, f"{label} default value"
        for key, val in spec["default"].items():
            assert default.get(key) == val, f"{label} default.{key}"

    if "constraints" in spec:
        for expected_c in spec["constraints"]:
            found = any(
                all(_constraint_field(c, k) == v for k, v in expected_c.items())
                for c in field.constraints
            )
            assert found, f"{label} should have constraint {expected_c} (got {field.constraints})"

    if "conditionals" in spec:
        for expected_cond in spec["conditionals"]:
            found = any(
                all(getattr(c, k, None) == v for k, v in expected_cond.items())
                for c in field.conditionals
            )
            assert found, f"{label} should have conditional {expected_cond} (got {field.conditionals})"


def _constraint_field(constraint, key):
    """Read a constraint attribute by its assertion key."""
    return getattr(constraint, key, None)
