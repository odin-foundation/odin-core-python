"""Unit tests for triple-quoted multiline string literals."""

import pytest

import odin
from odin.parsing.tokenizer import tokenize
from odin.parsing.tokens import TokenType
from odin.types.values import OdinString
from odin.types.errors import ParseError, ParseErrorCodes


def _value(text: str):
    return odin.parse(text).get("field")


# ── Happy path ──────────────────────────────────────────────────────────────


class TestMultilineHappy:
    def test_spans_newlines(self):
        val = _value('field = """hello\nworld"""')
        assert isinstance(val, OdinString)
        assert val.value == "hello\nworld"

    def test_single_line(self):
        assert _value('field = """one line"""').value == "one line"

    def test_leading_and_trailing_newline_retained(self):
        assert _value('field = """\ninner\n"""').value == "\ninner\n"

    def test_dedicated_token_type(self):
        tokens = tokenize('field = """body"""')
        types = [t.type for t in tokens]
        assert TokenType.STRING_MULTILINE in types


# ── Edge cases ──────────────────────────────────────────────────────────────


class TestMultilineEdge:
    def test_empty(self):
        assert _value('field = """"""').value == ""

    def test_verbatim_backslash_and_quotes(self):
        # Backslashes and embedded single/double quotes are kept verbatim.
        assert _value('field = """C:\\path say "hi" done"""').value == (
            'C:\\path say "hi" done'
        )

    def test_interior_blank_lines_preserved(self):
        assert _value('field = """a\n\nb"""').value == "a\n\nb"

    def test_dollar_sequences_verbatim(self):
        assert _value('field = """x \\${y} z"""').value == "x \\${y} z"


# ── Error path ──────────────────────────────────────────────────────────────


class TestMultilineError:
    def test_unterminated_is_p004(self):
        with pytest.raises(ParseError) as exc:
            odin.parse('field = """never closed\n')
        assert exc.value.code == ParseErrorCodes.P004

    def test_unterminated_at_eof_is_p004(self):
        with pytest.raises(ParseError) as exc:
            odin.parse('field = """open')
        assert exc.value.code == ParseErrorCodes.P004
