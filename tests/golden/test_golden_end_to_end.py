"""Golden end-to-end tests from sdk/golden/end-to-end/

Tests transform pipelines across multiple categories:
  - import: external format -> ODIN
  - export: ODIN -> external format
  - roundtrip: format -> ODIN -> format
  - odin-export: direct ODIN export (toJSON, toXML)
"""

import json

import pytest

from tests.golden.conftest import find_golden_dir


def discover_end_to_end_tests():
    """Discover tests from manifest.json hierarchy."""
    try:
        golden = find_golden_dir()
    except RuntimeError:
        return []
    e2e_dir = golden / "end-to-end"
    manifest_file = e2e_dir / "manifest.json"
    if not manifest_file.exists():
        return []

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    tests = []

    for category in manifest.get("categories", []):
        cat_id = category["id"]
        cat_path = category["path"]
        cat_dir = e2e_dir / cat_path
        cat_manifest_path = cat_dir / "manifest.json"
        if not cat_manifest_path.exists():
            continue

        cat_data = json.loads(cat_manifest_path.read_text(encoding="utf-8"))
        for test in cat_data.get("tests", []):
            test_id = test["id"]
            tests.append(pytest.param(
                (cat_dir, test, cat_id),
                id=f"{cat_id}/{test_id}",
            ))

    return tests


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n").strip()


def _source_format(direction: str) -> str:
    parts = direction.split("->")
    return parts[0] if parts else "odin"


def _parse_input(raw: str, fmt: str):
    """Parse input data according to source format."""
    from odin.transform.dyn_value import DynValue

    if fmt == "json":
        from odin.transform.source_parsers.json_parser import parse_json
        return parse_json(raw)
    if fmt == "xml":
        from odin.transform.source_parsers.xml_parser import parse_xml
        return parse_xml(raw)
    if fmt == "yaml":
        from odin.transform.source_parsers.yaml_parser import parse_yaml
        return parse_yaml(raw)
    if fmt in ("flat", "properties", "flat-kvp"):
        from odin.transform.source_parsers.flat_parser import parse_flat
        return parse_flat(raw)
    if fmt == "odin":
        import odin as odin_mod
        doc = odin_mod.parse(raw)
        return _odin_doc_to_dyn(doc)
    if fmt == "csv":
        from odin.transform.source_parsers.csv_parser import parse_csv
        return parse_csv(raw)
    if fmt in ("fixed-width", "fwf"):
        # Fixed-width needs field definitions from the transform, pass raw string
        return DynValue.of_string(raw)
    # Unknown: pass raw string
    return DynValue.of_string(raw)


def _odin_doc_to_dyn(doc):
    """Convert an OdinDocument to a DynValue tree via toJSON (plain types).

    Matches TypeScript behavior: Odin.parse(input).toJSON() loses type info.
    Currency becomes plain number, date becomes string, etc.
    """
    import json as json_mod
    import odin as odin_mod
    from odin.transform.dyn_value import DynValue
    from odin.transform.source_parsers.json_parser import parse_json

    # Use to_json export to get plain JSON, then re-parse as JSON source
    json_str = odin_mod.to_json(doc, indent=None, omit_nulls=False)
    return parse_json(json_str)


def _dict_to_dyn(obj):
    """Recursively convert a nested dict (with DynValue leaves) to DynValue."""
    from odin.transform.dyn_value import DynValue

    if isinstance(obj, DynValue):
        return obj
    if isinstance(obj, dict):
        return DynValue.of_object({k: _dict_to_dyn(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return DynValue.of_array([_dict_to_dyn(v) for v in obj])
    return DynValue.of_string(str(obj))


def _set_nested(obj, path: str, value):
    """Set a value at a dotted/bracketed path in a nested dict/list structure."""
    segments = []
    i = 0
    while i < len(path):
        if path[i] == ".":
            i += 1
            continue
        if path[i] == "[":
            end = path.find("]", i)
            if end < 0:
                end = len(path)
            segments.append(path[i:end + 1])
            i = end + 1
        else:
            start = i
            while i < len(path) and path[i] != "." and path[i] != "[":
                i += 1
            segments.append(path[start:i])

    current = obj
    for idx, seg in enumerate(segments):
        is_last = idx == len(segments) - 1
        if seg.startswith("[") and seg.endswith("]"):
            # Array index
            try:
                arr_idx = int(seg[1:-1])
            except ValueError:
                return
            if not isinstance(current, list):
                return
            while len(current) <= arr_idx:
                current.append({})
            if is_last:
                current[arr_idx] = value
            else:
                if not isinstance(current[arr_idx], (dict, list)):
                    current[arr_idx] = {}
                current = current[arr_idx]
        elif is_last:
            if isinstance(current, dict):
                current[seg] = value
        else:
            if isinstance(current, dict):
                # Check if next segment is an array index
                next_seg = segments[idx + 1] if idx + 1 < len(segments) else None
                if next_seg and next_seg.startswith("[") and next_seg.endswith("]"):
                    # Need a list here
                    if seg not in current or not isinstance(current[seg], list):
                        current[seg] = []
                    current = current[seg]
                else:
                    if seg not in current or not isinstance(current[seg], dict):
                        current[seg] = {}
                    current = current[seg]


def _run_transform_test(test, cat_dir):
    """Run a standard transform test."""
    import odin

    test_id = test["id"]
    direction = test.get("direction", "odin->odin")
    src_fmt = _source_format(direction)

    input_path = cat_dir / test["input"]
    transform_path = cat_dir / test["transform"]
    expected_path = cat_dir / test["expected"]

    input_raw = _normalize(input_path.read_text(encoding="utf-8"))
    transform_text = _normalize(transform_path.read_text(encoding="utf-8"))
    expected = _normalize(expected_path.read_text(encoding="utf-8"))

    transform = odin.parse_transform(transform_text)
    source = _parse_input(input_raw, src_fmt)
    result = odin.execute_transform(transform, source)

    assert not result.errors, (
        f"[{test_id}] Transform failed: "
        + ", ".join(f"[{e.code}] {e.message}" if e.code else e.message for e in result.errors)
    )

    formatted = _normalize(result.formatted or "")
    assert formatted == expected, f"[{test_id}] Formatted output mismatch"


def _run_roundtrip_test(test, cat_dir):
    """Run a roundtrip test (import -> export)."""
    import odin

    test_id = test["id"]
    direction = test.get("direction", "fixed-width->fixed-width")
    src_fmt = _source_format(direction)

    input_path = cat_dir / test["input"]
    import_transform_path = cat_dir / test["importTransform"]
    export_transform_path = cat_dir / test["exportTransform"]
    expected_path = cat_dir / test["expected"]

    input_raw = _normalize(input_path.read_text(encoding="utf-8"))
    import_text = _normalize(import_transform_path.read_text(encoding="utf-8"))
    export_text = _normalize(export_transform_path.read_text(encoding="utf-8"))
    expected = _normalize(expected_path.read_text(encoding="utf-8"))

    # Step 1: Import
    import_transform = odin.parse_transform(import_text)
    source = _parse_input(input_raw, src_fmt)
    import_result = odin.execute_transform(import_transform, source)

    assert not import_result.errors, (
        f"[{test_id}] Import transform failed: "
        + ", ".join(e.message for e in import_result.errors)
    )

    import_output = import_result.output

    # Step 2: Export
    export_transform = odin.parse_transform(export_text)
    export_result = odin.execute_transform(export_transform, import_output)

    assert not export_result.errors, (
        f"[{test_id}] Export transform failed: "
        + ", ".join(e.message for e in export_result.errors)
    )

    formatted = _normalize(export_result.formatted or "")
    assert formatted == expected, f"[{test_id}] Roundtrip output mismatch"


def _run_direct_export_test(test, cat_dir):
    """Run a direct export test (toJSON, toXML)."""
    import odin

    test_id = test["id"]
    input_path = cat_dir / test["input"]
    expected_path = cat_dir / test["expected"]

    input_text = _normalize(input_path.read_text(encoding="utf-8"))
    expected = _normalize(expected_path.read_text(encoding="utf-8"))

    doc = odin.parse(input_text)

    method = test.get("method", "toJSON")
    if method == "toJSON":
        actual = odin.to_json(doc)
    elif method == "toXML":
        actual = odin.to_xml(doc)
    else:
        pytest.fail(f"[{test_id}] Unknown export method: {method}")
        return

    actual = _normalize(actual)
    assert actual == expected, f"[{test_id}] {method} output mismatch"


@pytest.mark.golden
@pytest.mark.parametrize("test_info", discover_end_to_end_tests())
def test_golden_end_to_end(test_info):
    """Execute end-to-end transform test."""
    cat_dir, test, cat_id = test_info

    if "method" in test and test["method"]:
        _run_direct_export_test(test, cat_dir)
    elif "importTransform" in test and "exportTransform" in test:
        _run_roundtrip_test(test, cat_dir)
    elif "transform" in test:
        _run_transform_test(test, cat_dir)
    else:
        pytest.fail(f"[{test['id']}] No transform/method specified")
