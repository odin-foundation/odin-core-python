"""Golden tests for ODIN canonical form."""
import hashlib
import json
import os
import pytest
import odin

GOLDEN_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'golden', 'canonical')


def _load_tests_from_file(filename):
    """Load test cases from a golden JSON file."""
    filepath = os.path.join(GOLDEN_DIR, filename)
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('tests', [])


def _load_all_canonical_tests():
    """Load all canonical text tests (all-types.json, normalization.json, tabular-expansion.json)."""
    tests = []
    for filename in ['all-types.json', 'normalization.json', 'tabular-expansion.json']:
        for tc in _load_tests_from_file(filename):
            if 'expected' in tc and isinstance(tc['expected'], str):
                tests.append(pytest.param(tc, id=tc['id']))
    return tests


def _load_binary_tests():
    """Load binary output tests."""
    tests = []
    for tc in _load_tests_from_file('binary-output.json'):
        if 'expected' in tc and isinstance(tc['expected'], dict):
            tests.append(pytest.param(tc, id=tc['id']))
    return tests


@pytest.mark.golden
class TestGoldenCanonicalText:
    """Golden tests: canonical text output."""

    @pytest.mark.parametrize("test_case", _load_all_canonical_tests())
    def test_canonical_text(self, test_case):
        doc = odin.parse(test_case['input'])
        result = odin.canonicalize(doc).decode('utf-8')
        assert result == test_case['expected'], (
            f"Test {test_case['id']}: expected {test_case['expected']!r}, got {result!r}"
        )


@pytest.mark.golden
class TestGoldenCanonicalBinary:
    """Golden tests: canonical binary output (hex, sha256, byte length)."""

    @pytest.mark.parametrize("test_case", _load_binary_tests())
    def test_canonical_binary(self, test_case):
        expected = test_case['expected']
        doc = odin.parse(test_case['input'])
        result = odin.canonicalize(doc)

        # Check hex
        assert result.hex() == expected['hex'], (
            f"Test {test_case['id']} hex mismatch: "
            f"expected {expected['hex']!r}, got {result.hex()!r}"
        )

        # Check byte length
        assert len(result) == expected['byteLength'], (
            f"Test {test_case['id']} byte length mismatch: "
            f"expected {expected['byteLength']}, got {len(result)}"
        )

        # Check SHA-256
        sha = hashlib.sha256(result).hexdigest()
        assert sha == expected['sha256'], (
            f"Test {test_case['id']} sha256 mismatch: "
            f"expected {expected['sha256']!r}, got {sha!r}"
        )
