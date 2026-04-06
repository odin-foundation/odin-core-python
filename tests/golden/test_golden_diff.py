"""Golden tests for ODIN diff operations."""

import json
import os
import pytest

import odin

GOLDEN_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "golden", "diff")
)


def _load_golden_suites():
    """Load all golden diff test suites."""
    tests = []
    if not os.path.isdir(GOLDEN_DIR):
        return tests
    for filename in sorted(os.listdir(GOLDEN_DIR)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(GOLDEN_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            suite = json.load(f)
        for tc in suite.get("tests", []):
            tc["_suite"] = suite.get("suite", filename)
            tc["_file"] = filename
            tests.append(tc)
    return tests


def _test_id(tc):
    return tc.get("id", tc.get("description", "unknown"))


_GOLDEN_TESTS = _load_golden_suites()


@pytest.mark.golden
@pytest.mark.parametrize("test_case", _GOLDEN_TESTS, ids=_test_id)
def test_golden_diff(test_case):
    doc1_text = test_case.get("doc1", "")
    doc2_text = test_case.get("doc2", "")
    expected = test_case["expected"]

    doc1 = odin.parse(doc1_text)
    doc2 = odin.parse(doc2_text)
    d = odin.diff(doc1, doc2)

    # Check isEmpty
    if "isEmpty" in expected:
        assert d.is_empty == expected["isEmpty"], (
            f"Expected isEmpty={expected['isEmpty']} but got {d.is_empty}"
        )

    # Check additions
    if "additions" in expected:
        expected_paths = {a["path"] for a in expected["additions"]}
        actual_paths = {a.path for a in d.additions}
        assert actual_paths == expected_paths, (
            f"Additions mismatch: expected {expected_paths}, got {actual_paths}"
        )

    # Check deletions
    if "deletions" in expected:
        expected_paths = {r["path"] for r in expected["deletions"]}
        actual_paths = {r.path for r in d.deletions}
        assert actual_paths == expected_paths, (
            f"Deletions mismatch: expected {expected_paths}, got {actual_paths}"
        )

    # Check modifications
    if "modifications" in expected:
        expected_paths = {m["path"] for m in expected["modifications"]}
        actual_paths = {m.path for m in d.modifications}
        assert actual_paths == expected_paths, (
            f"Modifications mismatch: expected {expected_paths}, got {actual_paths}"
        )

    # Check moves
    if "moves" in expected:
        expected_moves = {(m["fromPath"], m["toPath"]) for m in expected["moves"]}
        actual_moves = {(m.from_path, m.to_path) for m in d.moves}
        assert actual_moves == expected_moves, (
            f"Moves mismatch: expected {expected_moves}, got {actual_moves}"
        )
