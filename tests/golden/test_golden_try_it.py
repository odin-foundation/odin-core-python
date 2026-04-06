"""Golden try-it verb tests from sdk/golden/transform/verbs/try-it/

Each verb has three companion files:
  {verb}.input.json   - input data
  {verb}.transform.odin - transformation definition
  {verb}.expected.odin  - expected ODIN output
"""

import json

import pytest

from tests.golden.conftest import find_golden_dir


def discover_try_it_tests():
    """Find verb triplets in golden/transform/verbs/try-it/."""
    try:
        golden = find_golden_dir()
    except RuntimeError:
        return []
    try_it_dir = golden / "transform" / "verbs" / "try-it"
    if not try_it_dir.is_dir():
        return []
    tests = []
    for expected_file in sorted(try_it_dir.glob("*.expected.odin")):
        verb_name = expected_file.name.replace(".expected.odin", "")
        input_file = try_it_dir / f"{verb_name}.input.json"
        transform_file = try_it_dir / f"{verb_name}.transform.odin"
        if input_file.exists() and transform_file.exists():
            tests.append(pytest.param(
                (input_file, transform_file, expected_file),
                id=f"try-it/{verb_name}",
            ))
    return tests


@pytest.mark.golden
@pytest.mark.parametrize("triplet", discover_try_it_tests())
def test_golden_try_it(triplet):
    """Execute verb try-it test and compare formatted ODIN output."""
    import odin

    input_file, transform_file, expected_file = triplet
    verb_name = transform_file.stem.replace(".transform", "")

    source = json.loads(input_file.read_text(encoding="utf-8"))
    transform_text = transform_file.read_text(encoding="utf-8").replace("\r\n", "\n")
    expected_odin = expected_file.read_text(encoding="utf-8").replace("\r\n", "\n")

    transform = odin.parse_transform(transform_text)
    # Force target format to odin (matching Java behavior)
    if not transform.target:
        from odin.transform.types import TransformTargetConfig
        transform.target = TransformTargetConfig(format="odin")
    else:
        transform.target.format = "odin"
    result = odin.execute_transform(transform, source)

    assert not result.errors, (
        f"Transform failed for verb '{verb_name}': "
        + ", ".join(e.message for e in result.errors)
    )

    assert result.formatted is not None, (
        f"No formatted output for verb '{verb_name}'"
    )

    actual = result.formatted.replace("\r\n", "\n").strip()
    expected = expected_odin.strip()

    assert actual == expected, (
        f"Output mismatch for verb '{verb_name}':\n"
        f"  EXPECTED:\n{expected}\n"
        f"  ACTUAL:\n{actual}"
    )
