"""Unit tests for :literal segments with ${...} interpolation."""

import pytest

from odin.transform.transform_parser import parse_transform
from odin.transform.engine import TransformEngine
from odin.transform.verb_registry import create_default_registry


def _run(transform_text: str, source: dict):
    transform = parse_transform(transform_text)
    engine = TransformEngine(create_default_registry())
    return engine.execute(transform, source)


def _lines(transform_text: str, source: dict):
    result = _run(transform_text, source)
    assert not result.errors, result.errors
    return (result.formatted or "").splitlines()


_HEADER = (
    '{$}\n'
    'direction = "odin->fixed-width"\n'
    'target.format = "fixed-width"\n'
)


# ── Happy path ──────────────────────────────────────────────────────────────


class TestLiteralHappy:
    def test_path_interpolation(self):
        transform = _HEADER + (
            '{HDR}\n'
            ':literal\n'
            '"""\n'
            'HDR|${@policy.number}\n'
            '"""\n'
        )
        assert _lines(transform, {"policy": {"number": "P-100"}}) == ["HDR|P-100"]

    def test_verb_interpolation(self):
        transform = _HEADER + (
            '{HDR}\n'
            ':literal\n'
            '"""\n'
            'HDR|${%upper @policy.code}\n'
            '"""\n'
        )
        assert _lines(transform, {"policy": {"code": "abc"}}) == ["HDR|ABC"]

    def test_loop_renders_once_per_item(self):
        transform = _HEADER + (
            '{DET[]}\n'
            ':loop @items\n'
            ':literal\n'
            '"""\n'
            'DET|${@.sku}|${@.qty}\n'
            '"""\n'
        )
        source = {"items": [{"sku": "A1", "qty": "2"}, {"sku": "B2", "qty": "5"}]}
        assert _lines(transform, source) == ["DET|A1|2", "DET|B2|5"]


# ── Edge cases ──────────────────────────────────────────────────────────────


class TestLiteralEdge:
    def test_escapes(self):
        # \${ -> ${ (no interpolation); \$ -> $; live ${...} still interpolates.
        transform = _HEADER + (
            '{NOTE}\n'
            ':literal\n'
            '"""\n'
            'NOTE|literal:\\${@policy.number} dollar:\\$ value:${@policy.number}\n'
            '"""\n'
        )
        assert _lines(transform, {"policy": {"number": "P-100"}}) == [
            "NOTE|literal:${@policy.number} dollar:$ value:P-100",
        ]

    def test_backslash_escape(self):
        transform = _HEADER + (
            '{NOTE}\n'
            ':literal\n'
            '"""\n'
            'path:C:\\\\temp\n'
            '"""\n'
        )
        assert _lines(transform, {}) == ["path:C:\\temp"]

    def test_interior_blank_lines_preserved(self):
        transform = _HEADER + (
            '{BLK}\n'
            ':literal\n'
            '"""\n'
            'one\n'
            '\n'
            'two\n'
            '"""\n'
        )
        assert _lines(transform, {}) == ["one", "", "two"]

    def test_empty_loop_emits_no_lines(self):
        transform = _HEADER + (
            '{DET[]}\n'
            ':loop @items\n'
            ':literal\n'
            '"""\n'
            'DET|${@.sku}\n'
            '"""\n'
        )
        assert _lines(transform, {"items": []}) == []


# ── Error path ──────────────────────────────────────────────────────────────


class TestLiteralError:
    def test_nested_interpolation_is_t014(self):
        transform = _HEADER + (
            '{NOTE}\n'
            ':literal\n'
            '"""\n'
            'val:${@a ${@b}}\n'
            '"""\n'
        )
        result = _run(transform, {"a": "1", "b": "2"})
        assert any(e.code == "T014" for e in result.errors)
