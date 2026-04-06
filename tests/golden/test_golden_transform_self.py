"""Golden self-testing transforms from sdk/golden/transform/verbs/*.test.odin

Each .test.odin file is a self-contained transform that runs with empty JSON input
and produces a TestResult section with success/passed/failed/total fields.
"""

import pytest

from tests.golden.conftest import find_golden_dir


def discover_self_tests():
    """Find all .test.odin files in golden/transform/verbs/."""
    try:
        golden = find_golden_dir()
    except RuntimeError:
        return []
    verb_dir = golden / "transform" / "verbs"
    if not verb_dir.is_dir():
        return []
    tests = []
    for f in sorted(verb_dir.glob("*.test.odin")):
        verb_name = f.stem.replace(".test", "")
        tests.append(pytest.param(f, id=f"self-test/{verb_name}"))
    return tests


@pytest.mark.golden
@pytest.mark.parametrize("test_file", discover_self_tests())
def test_golden_transform_self(test_file):
    """Execute self-testing transform with empty JSON input."""
    import odin

    transform_text = test_file.read_text(encoding="utf-8").replace("\r\n", "\n")
    transform = odin.parse_transform(transform_text)
    result = odin.execute_transform(transform, {})

    assert result.success, (
        f"Transform execution failed for {test_file.stem}: "
        + ", ".join(e.message for e in result.errors)
    )

    # Check the TestResult segment
    output = result.output
    assert output is not None, f"No output for {test_file.stem}"
    assert output.is_object(), f"Output is not an object for {test_file.stem}"

    test_result = output.get("TestResult")
    assert test_result is not None, f"No TestResult segment in output for {test_file.stem}"

    success_field = test_result.get("success")
    assert success_field is not None, f"No success field in TestResult for {test_file.stem}"

    passed_field = test_result.get("passed")
    failed_field = test_result.get("failed")
    total_field = test_result.get("total")

    passed = passed_field.as_int() if passed_field and not passed_field.is_null() else "?"
    failed = failed_field.as_int() if failed_field and not failed_field.is_null() else "?"
    total = total_field.as_int() if total_field and not total_field.is_null() else "?"

    detail = f"[{test_file.stem}] passed={passed}, failed={failed}, total={total}"

    # success should be true (boolean) or truthy
    success_val = success_field.as_bool() if success_field.is_bool() else False
    assert success_val, f"Self-test FAILED: {detail}"
