"""Tests for ODIN tokenizer."""

import pytest
from odin.parsing.tokens import Token, TokenType
from odin.parsing.tokenizer import Tokenizer, tokenize


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def tok(text: str) -> list[Token]:
    """Tokenize text and return all tokens."""
    return tokenize(text)


def tok_types(text: str) -> list[TokenType]:
    """Return just the token types (excluding NEWLINE and EOF)."""
    return [t.type for t in tokenize(text) if t.type not in (TokenType.NEWLINE, TokenType.EOF)]


def tok_values(text: str) -> list[str]:
    """Return just the token values (excluding NEWLINE and EOF)."""
    return [t.value for t in tokenize(text) if t.type not in (TokenType.NEWLINE, TokenType.EOF)]


def find_token(tokens: list[Token], token_type: TokenType) -> Token:
    """Find first token of given type."""
    for t in tokens:
        if t.type == token_type:
            return t
    raise ValueError(f"No token of type {token_type} found")


# ─────────────────────────────────────────────────────────────────────────────
# EOF
# ─────────────────────────────────────────────────────────────────────────────


class TestEOF:
    def test_empty_input(self):
        tokens = tok("")
        assert tokens[-1].type == TokenType.EOF

    def test_eof_always_last(self):
        tokens = tok("x = #1")
        assert tokens[-1].type == TokenType.EOF


# ─────────────────────────────────────────────────────────────────────────────
# Headers
# ─────────────────────────────────────────────────────────────────────────────


class TestHeaders:
    def test_simple_header(self):
        tokens = tok("{Customer}")
        types = tok_types("{Customer}")
        assert TokenType.HEADER_OPEN in types
        assert TokenType.HEADER_CLOSE in types
        assert TokenType.IDENTIFIER in types

    def test_meta_header(self):
        types = tok_types("{$}")
        assert TokenType.HEADER_OPEN in types
        assert TokenType.PREFIX_META in types
        assert TokenType.HEADER_CLOSE in types

    def test_empty_header(self):
        types = tok_types("{}")
        assert types == [TokenType.HEADER_OPEN, TokenType.HEADER_CLOSE]

    def test_nested_header(self):
        types = tok_types("{Customer.Address}")
        assert TokenType.HEADER_OPEN in types
        assert TokenType.DOT in types
        assert TokenType.HEADER_CLOSE in types

    def test_relative_header(self):
        types = tok_types("{.relative}")
        assert TokenType.HEADER_OPEN in types
        assert TokenType.DOT in types
        assert TokenType.HEADER_CLOSE in types

    def test_meta_with_name(self):
        types = tok_types("{$target}")
        assert TokenType.HEADER_OPEN in types
        assert TokenType.PREFIX_META in types
        assert TokenType.IDENTIFIER in types
        assert TokenType.HEADER_CLOSE in types

    def test_header_with_array_index(self):
        types = tok_types("{items[0]}")
        assert TokenType.HEADER_OPEN in types
        assert TokenType.ARRAY_INDEX in types
        assert TokenType.HEADER_CLOSE in types


# ─────────────────────────────────────────────────────────────────────────────
# Path / Identifiers
# ─────────────────────────────────────────────────────────────────────────────


class TestPaths:
    def test_simple_path(self):
        tokens = tok("name = \"John\"")
        assert find_token(tokens, TokenType.IDENTIFIER).value == "name"

    def test_dotted_path(self):
        types = tok_types("address.city = \"NYC\"")
        assert types[0] == TokenType.IDENTIFIER
        assert types[1] == TokenType.DOT
        assert types[2] == TokenType.IDENTIFIER

    def test_array_index(self):
        types = tok_types("items[0] = \"a\"")
        assert TokenType.ARRAY_INDEX in types

    def test_array_index_value(self):
        tokens = tok("items[0] = \"a\"")
        idx = find_token(tokens, TokenType.ARRAY_INDEX)
        assert idx.value == "0"

    def test_complex_path(self):
        types = tok_types("a.b[0].c = \"x\"")
        assert types.count(TokenType.DOT) == 2
        assert TokenType.ARRAY_INDEX in types

    def test_identifier_with_underscore(self):
        tokens = tok("my_field = \"x\"")
        assert find_token(tokens, TokenType.IDENTIFIER).value == "my_field"

    def test_identifier_with_hyphen(self):
        tokens = tok("my-field = \"x\"")
        assert find_token(tokens, TokenType.IDENTIFIER).value == "my-field"


# ─────────────────────────────────────────────────────────────────────────────
# Equals
# ─────────────────────────────────────────────────────────────────────────────


class TestEquals:
    def test_equals_sign(self):
        types = tok_types("x = #1")
        assert TokenType.EQUALS in types


# ─────────────────────────────────────────────────────────────────────────────
# Strings
# ─────────────────────────────────────────────────────────────────────────────


class TestStrings:
    def test_quoted_string(self):
        tokens = tok('x = "hello"')
        s = find_token(tokens, TokenType.STRING_QUOTED)
        assert s.value == "hello"

    def test_empty_quoted_string(self):
        tokens = tok('x = ""')
        s = find_token(tokens, TokenType.STRING_QUOTED)
        assert s.value == ""

    def test_string_with_spaces(self):
        tokens = tok('x = "hello world"')
        s = find_token(tokens, TokenType.STRING_QUOTED)
        assert s.value == "hello world"

    def test_escape_quote(self):
        tokens = tok(r'x = "say \"hi\""')
        s = find_token(tokens, TokenType.STRING_QUOTED)
        assert s.value == 'say "hi"'

    def test_escape_backslash(self):
        tokens = tok('x = "a\\\\b"')
        s = find_token(tokens, TokenType.STRING_QUOTED)
        assert s.value == "a\\b"

    def test_escape_newline(self):
        tokens = tok('x = "line1\\nline2"')
        s = find_token(tokens, TokenType.STRING_QUOTED)
        assert s.value == "line1\nline2"

    def test_escape_tab(self):
        tokens = tok('x = "col1\\tcol2"')
        s = find_token(tokens, TokenType.STRING_QUOTED)
        assert s.value == "col1\tcol2"

    def test_escape_cr(self):
        tokens = tok('x = "a\\rb"')
        s = find_token(tokens, TokenType.STRING_QUOTED)
        assert s.value == "a\rb"

    def test_escape_unicode_4(self):
        tokens = tok('x = "\\u0041"')
        s = find_token(tokens, TokenType.STRING_QUOTED)
        assert s.value == "A"

    def test_escape_unicode_8(self):
        tokens = tok('x = "\\U0001F600"')
        s = find_token(tokens, TokenType.STRING_QUOTED)
        assert s.value == "\U0001F600"

    def test_escape_dollar_literal(self):
        tokens = tok('x = "Total: \\$5"')
        s = find_token(tokens, TokenType.STRING_QUOTED)
        assert s.value == "Total: $5"

    def test_escape_dollar_before_marker_preserves_backslash(self):
        tokens = tok('x = "\\${@.field}"')
        s = find_token(tokens, TokenType.STRING_QUOTED)
        assert s.value == "\\${@.field}"

    def test_escape_dollar_then_interpolation(self):
        tokens = tok('x = "\\$${@.amount}"')
        s = find_token(tokens, TokenType.STRING_QUOTED)
        assert s.value == "$${@.amount}"

    def test_bare_string(self):
        tokens = tok("x = hello")
        s = find_token(tokens, TokenType.STRING_BARE)
        assert s.value == "hello"

    def test_bare_string_trimmed(self):
        tokens = tok("x = hello world   ")
        s = find_token(tokens, TokenType.STRING_BARE)
        assert s.value == "hello world"

    def test_multi_line_string(self):
        tokens = tok('x = """line1\nline2\nline3"""')
        s = find_token(tokens, TokenType.STRING_MULTILINE)
        assert "line1" in s.value
        assert "line2" in s.value

    def test_multi_line_string_content(self):
        tokens = tok('x = """hello\nworld"""')
        s = find_token(tokens, TokenType.STRING_MULTILINE)
        assert s.value == "hello\nworld"


# ─────────────────────────────────────────────────────────────────────────────
# Numbers
# ─────────────────────────────────────────────────────────────────────────────


class TestNumbers:
    def test_number_prefix(self):
        types = tok_types("x = #3.14")
        assert TokenType.PREFIX_NUMBER in types
        assert TokenType.NUMBER in types

    def test_number_value(self):
        tokens = tok("x = #3.14")
        n = find_token(tokens, TokenType.NUMBER)
        assert n.value == "3.14"

    def test_integer_prefix(self):
        types = tok_types("x = ##42")
        assert TokenType.PREFIX_INTEGER in types
        assert TokenType.NUMBER in types

    def test_integer_value(self):
        tokens = tok("x = ##42")
        n = find_token(tokens, TokenType.NUMBER)
        assert n.value == "42"

    def test_negative_number(self):
        tokens = tok("x = #-3.14")
        n = find_token(tokens, TokenType.NUMBER)
        assert n.value == "-3.14"

    def test_scientific_notation(self):
        tokens = tok("x = #1.5e10")
        n = find_token(tokens, TokenType.NUMBER)
        assert n.value == "1.5e10"

    def test_scientific_negative_exponent(self):
        tokens = tok("x = #1.5e-3")
        n = find_token(tokens, TokenType.NUMBER)
        assert n.value == "1.5e-3"

    def test_zero(self):
        tokens = tok("x = #0")
        n = find_token(tokens, TokenType.NUMBER)
        assert n.value == "0"

    def test_negative_integer(self):
        tokens = tok("x = ##-7")
        n = find_token(tokens, TokenType.NUMBER)
        assert n.value == "-7"


# ─────────────────────────────────────────────────────────────────────────────
# Currency
# ─────────────────────────────────────────────────────────────────────────────


class TestCurrency:
    def test_currency_prefix(self):
        types = tok_types("x = #$99.99")
        assert TokenType.PREFIX_CURRENCY in types
        assert TokenType.NUMBER in types

    def test_currency_value(self):
        tokens = tok("x = #$99.99")
        n = find_token(tokens, TokenType.NUMBER)
        assert n.value == "99.99"

    def test_currency_with_code(self):
        tokens = tok("x = #$99.99:USD")
        n = find_token(tokens, TokenType.NUMBER)
        # The currency code is part of the number value or handled separately
        assert "99.99" in n.value


# ─────────────────────────────────────────────────────────────────────────────
# Percent
# ─────────────────────────────────────────────────────────────────────────────


class TestPercent:
    def test_percent_prefix(self):
        types = tok_types("x = #%50.5")
        assert TokenType.PREFIX_PERCENT in types
        assert TokenType.NUMBER in types

    def test_percent_value(self):
        tokens = tok("x = #%50.5")
        n = find_token(tokens, TokenType.NUMBER)
        assert n.value == "50.5"


# ─────────────────────────────────────────────────────────────────────────────
# Boolean
# ─────────────────────────────────────────────────────────────────────────────


class TestBoolean:
    def test_true(self):
        tokens = tok("x = true")
        b = find_token(tokens, TokenType.BOOLEAN)
        assert b.value == "true"

    def test_false(self):
        tokens = tok("x = false")
        b = find_token(tokens, TokenType.BOOLEAN)
        assert b.value == "false"

    def test_prefix_true(self):
        types = tok_types("x = ?true")
        assert TokenType.PREFIX_BOOLEAN in types
        assert TokenType.BOOLEAN in types

    def test_prefix_false(self):
        types = tok_types("x = ?false")
        assert TokenType.PREFIX_BOOLEAN in types
        assert TokenType.BOOLEAN in types


# ─────────────────────────────────────────────────────────────────────────────
# Null
# ─────────────────────────────────────────────────────────────────────────────


class TestNull:
    def test_null(self):
        types = tok_types("x = ~")
        assert TokenType.PREFIX_NULL in types


# ─────────────────────────────────────────────────────────────────────────────
# Reference
# ─────────────────────────────────────────────────────────────────────────────


class TestReference:
    def test_reference(self):
        types = tok_types("x = @other.path")
        assert TokenType.PREFIX_REFERENCE in types

    def test_reference_with_index(self):
        tokens = tok("x = @items[0]")
        assert TokenType.PREFIX_REFERENCE in [t.type for t in tokens]


# ─────────────────────────────────────────────────────────────────────────────
# Binary
# ─────────────────────────────────────────────────────────────────────────────


class TestBinary:
    def test_binary_prefix(self):
        types = tok_types("x = ^SGVsbG8=")
        assert TokenType.PREFIX_BINARY in types

    def test_binary_with_algo(self):
        tokens = tok("x = ^sha256:ABCD")
        assert TokenType.PREFIX_BINARY in [t.type for t in tokens]


# ─────────────────────────────────────────────────────────────────────────────
# Date / Time / Timestamp / Duration
# ─────────────────────────────────────────────────────────────────────────────


class TestTemporal:
    def test_date(self):
        tokens = tok("x = 2024-06-15")
        d = find_token(tokens, TokenType.DATE)
        assert d.value == "2024-06-15"

    def test_timestamp(self):
        tokens = tok("x = 2024-06-15T10:30:00Z")
        ts = find_token(tokens, TokenType.TIMESTAMP)
        assert ts.value == "2024-06-15T10:30:00Z"

    def test_timestamp_with_offset(self):
        tokens = tok("x = 2024-06-15T10:30:00+05:30")
        ts = find_token(tokens, TokenType.TIMESTAMP)
        assert "2024-06-15T10:30:00+05:30" == ts.value

    def test_timestamp_with_millis(self):
        tokens = tok("x = 2024-06-15T10:30:00.123Z")
        ts = find_token(tokens, TokenType.TIMESTAMP)
        assert "123" in ts.value

    def test_time(self):
        tokens = tok("x = T10:30:00")
        t = find_token(tokens, TokenType.TIME)
        assert t.value == "T10:30:00"

    def test_duration(self):
        tokens = tok("x = P1Y2M3D")
        d = find_token(tokens, TokenType.DURATION)
        assert d.value == "P1Y2M3D"

    def test_duration_with_time(self):
        tokens = tok("x = PT5H30M")
        d = find_token(tokens, TokenType.DURATION)
        assert d.value == "PT5H30M"

    def test_full_duration(self):
        tokens = tok("x = P1Y2M3W4DT5H6M7S")
        d = find_token(tokens, TokenType.DURATION)
        assert d.value == "P1Y2M3W4DT5H6M7S"


# ─────────────────────────────────────────────────────────────────────────────
# Verb
# ─────────────────────────────────────────────────────────────────────────────


class TestVerb:
    def test_verb_prefix(self):
        types = tok_types("x = %upper")
        assert TokenType.PREFIX_VERB in types

    def test_custom_verb(self):
        tokens = tok("x = %&myVerb")
        assert TokenType.PREFIX_VERB in [t.type for t in tokens]


# ─────────────────────────────────────────────────────────────────────────────
# Comments
# ─────────────────────────────────────────────────────────────────────────────


class TestComments:
    def test_line_comment(self):
        tokens = tok("; this is a comment")
        c = find_token(tokens, TokenType.COMMENT)
        assert "this is a comment" in c.value

    def test_inline_comment(self):
        tokens = tok('x = "hello" ; comment')
        c = find_token(tokens, TokenType.COMMENT)
        assert "comment" in c.value

    def test_comment_preserves_text(self):
        tokens = tok("; full text here")
        c = find_token(tokens, TokenType.COMMENT)
        assert "full text here" in c.value


# ─────────────────────────────────────────────────────────────────────────────
# Directives
# ─────────────────────────────────────────────────────────────────────────────


class TestDirectives:
    def test_import_directive(self):
        tokens = tok('@import "./other.odin"')
        d = find_token(tokens, TokenType.DIRECTIVE_IMPORT)
        assert "other.odin" in d.value

    def test_schema_directive(self):
        tokens = tok("@schema {MySchema}")
        d = find_token(tokens, TokenType.DIRECTIVE_SCHEMA)
        assert "MySchema" in d.value

    def test_if_directive(self):
        tokens = tok("@if condition")
        d = find_token(tokens, TokenType.DIRECTIVE_COND)
        assert "condition" in d.value


# ─────────────────────────────────────────────────────────────────────────────
# Modifiers
# ─────────────────────────────────────────────────────────────────────────────


class TestModifiers:
    def test_critical_modifier(self):
        types = tok_types('x = !"required"')
        assert TokenType.MODIFIER_CRITICAL in types

    def test_redacted_modifier(self):
        types = tok_types('x = *"secret"')
        assert TokenType.MODIFIER_REDACTED in types

    def test_deprecated_modifier(self):
        types = tok_types('x = -"old"')
        assert TokenType.MODIFIER_DEPRECATED in types

    def test_combined_modifiers(self):
        types = tok_types('x = !-*"value"')
        assert TokenType.MODIFIER_CRITICAL in types
        assert TokenType.MODIFIER_DEPRECATED in types
        assert TokenType.MODIFIER_REDACTED in types

    def test_deprecated_vs_negative_number(self):
        # -42 should be a negative number, not deprecated modifier
        tokens = tok("x = #-42")
        n = find_token(tokens, TokenType.NUMBER)
        assert n.value == "-42"

    def test_deprecated_before_string(self):
        types = tok_types('x = -"old value"')
        assert TokenType.MODIFIER_DEPRECATED in types
        assert TokenType.STRING_QUOTED in types

    def test_deprecated_before_null(self):
        types = tok_types("x = -~")
        assert TokenType.MODIFIER_DEPRECATED in types
        assert TokenType.PREFIX_NULL in types

    def test_deprecated_before_hash(self):
        types = tok_types("x = -#5")
        assert TokenType.MODIFIER_DEPRECATED in types
        assert TokenType.PREFIX_NUMBER in types


# ─────────────────────────────────────────────────────────────────────────────
# Line/Column Tracking
# ─────────────────────────────────────────────────────────────────────────────


class TestLineColumn:
    def test_first_token_line_1(self):
        tokens = tok("x = #1")
        assert tokens[0].line == 1
        assert tokens[0].column == 1

    def test_second_line(self):
        tokens = tok("x = #1\ny = #2")
        # Find the 'y' identifier
        y_tokens = [t for t in tokens if t.type == TokenType.IDENTIFIER and t.value == "y"]
        assert len(y_tokens) == 1
        assert y_tokens[0].line == 2

    def test_column_tracking(self):
        tokens = tok("abc = #1")
        eq = find_token(tokens, TokenType.EQUALS)
        assert eq.column == 5

    def test_multiline_tracking(self):
        text = "a = #1\nb = #2\nc = #3"
        tokens = tok(text)
        c_tok = [t for t in tokens if t.type == TokenType.IDENTIFIER and t.value == "c"]
        assert c_tok[0].line == 3
        assert c_tok[0].column == 1


# ─────────────────────────────────────────────────────────────────────────────
# Newlines
# ─────────────────────────────────────────────────────────────────────────────


class TestNewlines:
    def test_newline_token(self):
        tokens = tok("a = #1\nb = #2")
        newlines = [t for t in tokens if t.type == TokenType.NEWLINE]
        assert len(newlines) >= 1

    def test_crlf_handling(self):
        tokens = tok("a = #1\r\nb = #2")
        newlines = [t for t in tokens if t.type == TokenType.NEWLINE]
        assert len(newlines) >= 1

    def test_crlf_counted_as_one(self):
        tokens = tok("a = #1\r\nb = #2")
        b_tokens = [t for t in tokens if t.type == TokenType.IDENTIFIER and t.value == "b"]
        assert b_tokens[0].line == 2


# ─────────────────────────────────────────────────────────────────────────────
# Doc Separator
# ─────────────────────────────────────────────────────────────────────────────


class TestDocSeparator:
    def test_triple_dash(self):
        types = tok_types("---")
        assert TokenType.DOC_SEPARATOR in types


# ─────────────────────────────────────────────────────────────────────────────
# Error Cases
# ─────────────────────────────────────────────────────────────────────────────


class TestErrors:
    def test_unterminated_string(self):
        tokens = tok('x = "unterminated')
        error_tokens = [t for t in tokens if t.type == TokenType.ERROR]
        assert len(error_tokens) > 0

    def test_unterminated_multiline_string(self):
        tokens = tok('x = """unterminated')
        error_tokens = [t for t in tokens if t.type == TokenType.ERROR]
        assert len(error_tokens) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Full Document
# ─────────────────────────────────────────────────────────────────────────────


class TestFullDocument:
    def test_simple_document(self):
        text = """{$}
odin = "1.0.0"

{Customer}
name = "John"
age = ##30
active = true
"""
        tokens = tok(text)
        types = [t.type for t in tokens]
        assert TokenType.HEADER_OPEN in types
        assert TokenType.PREFIX_META in types
        assert TokenType.HEADER_CLOSE in types
        assert TokenType.STRING_QUOTED in types
        assert TokenType.PREFIX_INTEGER in types
        assert TokenType.BOOLEAN in types
        assert TokenType.EOF in types

    def test_document_with_all_types(self):
        text = """name = "Alice"
count = ##10
price = #$19.99
ratio = #3.14
pct = #%50
active = ?true
ref = @other.path
empty = ~
born = 2000-01-15
"""
        tokens = tok(text)
        types = set(t.type for t in tokens)
        assert TokenType.STRING_QUOTED in types
        assert TokenType.PREFIX_INTEGER in types
        assert TokenType.PREFIX_CURRENCY in types
        assert TokenType.PREFIX_NUMBER in types
        assert TokenType.PREFIX_PERCENT in types
        assert TokenType.PREFIX_BOOLEAN in types
        assert TokenType.PREFIX_REFERENCE in types
        assert TokenType.PREFIX_NULL in types
        assert TokenType.DATE in types

    def test_document_with_modifiers(self):
        text = '''name = !"required"
ssn = *"secret"
old = -"deprecated"
'''
        tokens = tok(text)
        types = [t.type for t in tokens]
        assert TokenType.MODIFIER_CRITICAL in types
        assert TokenType.MODIFIER_REDACTED in types
        assert TokenType.MODIFIER_DEPRECATED in types

    def test_document_with_comments(self):
        text = """; Header comment
{Customer}
name = "John" ; inline comment
"""
        tokens = tok(text)
        comments = [t for t in tokens if t.type == TokenType.COMMENT]
        assert len(comments) == 2

    def test_document_with_array(self):
        text = """items[0] = "a"
items[1] = "b"
items[2] = "c"
"""
        tokens = tok(text)
        indices = [t for t in tokens if t.type == TokenType.ARRAY_INDEX]
        assert len(indices) == 3
        assert indices[0].value == "0"
        assert indices[1].value == "1"
        assert indices[2].value == "2"


# ─────────────────────────────────────────────────────────────────────────────
# Extension prefix
# ─────────────────────────────────────────────────────────────────────────────


class TestExtension:
    def test_extension_prefix(self):
        types = tok_types("x = &custom")
        assert TokenType.PREFIX_EXTENSION in types


# ─────────────────────────────────────────────────────────────────────────────
# Whitespace handling
# ─────────────────────────────────────────────────────────────────────────────


class TestWhitespace:
    def test_leading_whitespace_skipped(self):
        tokens = tok("  x = #1")
        assert tokens[0].type == TokenType.IDENTIFIER

    def test_whitespace_around_equals(self):
        tokens = tok("x = #1")
        types = tok_types("x = #1")
        assert types == [TokenType.IDENTIFIER, TokenType.EQUALS, TokenType.PREFIX_NUMBER, TokenType.NUMBER]

    def test_tabs_handled(self):
        tokens = tok("\tx = #1")
        assert tokens[0].type == TokenType.IDENTIFIER


# ─────────────────────────────────────────────────────────────────────────────
# Edge Cases
# ─────────────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_only_whitespace(self):
        tokens = tok("   ")
        assert tokens[-1].type == TokenType.EOF

    def test_only_newlines(self):
        tokens = tok("\n\n\n")
        assert tokens[-1].type == TokenType.EOF

    def test_empty_lines_between_assignments(self):
        tokens = tok("x = #1\n\ny = #2")
        idents = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        assert len(idents) == 2

    def test_scientific_positive_exponent(self):
        tokens = tok("x = #1.5e+3")
        n = find_token(tokens, TokenType.NUMBER)
        assert n.value == "1.5e+3"

    def test_number_no_fractional(self):
        tokens = tok("x = #42")
        n = find_token(tokens, TokenType.NUMBER)
        assert n.value == "42"

    def test_negative_currency(self):
        tokens = tok("x = #$-10.50")
        n = find_token(tokens, TokenType.NUMBER)
        assert "-10.50" in n.value

    def test_time_with_fraction(self):
        tokens = tok("x = T10:30:00.500")
        t = find_token(tokens, TokenType.TIME)
        assert "500" in t.value

    def test_date_as_value_not_negative(self):
        # After deprecated modifier, 2024-01-01 should be a date
        types = tok_types("x = -2024-01-01")
        assert TokenType.MODIFIER_DEPRECATED in types
        assert TokenType.DATE in types

    def test_timestamp_negative_offset(self):
        tokens = tok("x = 2024-06-15T10:30:00-05:00")
        ts = find_token(tokens, TokenType.TIMESTAMP)
        assert "-05:00" in ts.value

    def test_multiple_headers(self):
        text = "{A}\nx = #1\n{B}\ny = #2"
        tokens = tok(text)
        opens = [t for t in tokens if t.type == TokenType.HEADER_OPEN]
        assert len(opens) == 2

    def test_boolean_bare_true(self):
        tokens = tok("x = true")
        b = find_token(tokens, TokenType.BOOLEAN)
        assert b.value == "true"

    def test_boolean_bare_false(self):
        tokens = tok("x = false")
        b = find_token(tokens, TokenType.BOOLEAN)
        assert b.value == "false"

    def test_string_with_unicode_content(self):
        tokens = tok('x = "café"')
        s = find_token(tokens, TokenType.STRING_QUOTED)
        assert s.value == "café"

    def test_reference_after_at(self):
        # @ not at column 1 is a reference prefix
        tokens = tok("x = @some.path")
        assert TokenType.PREFIX_REFERENCE in [t.type for t in tokens]

    def test_extension_prefix_value(self):
        tokens = tok("x = &myType")
        assert TokenType.PREFIX_EXTENSION in [t.type for t in tokens]

    def test_bare_string_stops_at_comment(self):
        tokens = tok("x = hello ; comment")
        s = find_token(tokens, TokenType.STRING_BARE)
        assert s.value == "hello"
        c = find_token(tokens, TokenType.COMMENT)
        assert "comment" in c.value

    def test_bare_string_with_multiple_words(self):
        tokens = tok("x = hello world foo")
        s = find_token(tokens, TokenType.STRING_BARE)
        assert s.value == "hello world foo"

    def test_negative_currency(self):
        tokens = tok("x = #$-5.00")
        assert TokenType.PREFIX_CURRENCY in [t.type for t in tokens]
        n = find_token(tokens, TokenType.NUMBER)
        assert n.value == "-5.00"

    def test_integer_zero(self):
        tokens = tok("x = ##0")
        n = find_token(tokens, TokenType.NUMBER)
        assert n.value == "0"

    def test_percent_integer(self):
        tokens = tok("x = #%100")
        n = find_token(tokens, TokenType.NUMBER)
        assert n.value == "100"

    def test_multiple_assignments_same_line_separated(self):
        text = "a = #1\nb = #2\nc = #3"
        tokens = tok(text)
        idents = [t for t in tokens if t.type == TokenType.IDENTIFIER]
        assert [i.value for i in idents] == ["a", "b", "c"]

    def test_header_reference_context(self):
        types = tok_types("{@ref}")
        assert TokenType.PREFIX_REFERENCE in types

    def test_deprecated_before_boolean(self):
        types = tok_types("x = -?true")
        assert TokenType.MODIFIER_DEPRECATED in types
        assert TokenType.PREFIX_BOOLEAN in types

    def test_string_escape_solidus(self):
        # Forward slash - not a special escape in ODIN but should pass through
        tokens = tok('x = "a/b"')
        s = find_token(tokens, TokenType.STRING_QUOTED)
        assert s.value == "a/b"

    def test_comment_only_semicolon(self):
        tokens = tok(";")
        c = find_token(tokens, TokenType.COMMENT)
        assert c.value == ";"

    def test_number_with_leading_zero(self):
        tokens = tok("x = #0.5")
        n = find_token(tokens, TokenType.NUMBER)
        assert n.value == "0.5"
