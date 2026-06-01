"""Single-pass ODIN tokenizer — optimized for performance."""

from typing import List, Optional

from odin.parsing.tokens import Token, TokenType


class _InvalidEscape(Exception):
    """Internal exception for invalid escape sequences."""
    __slots__ = ('ch',)

    def __init__(self, ch: str):
        self.ch = ch


# ── Lookup tables (module-level for speed) ──────────────────────────────────

# Escape sequences: backslash + char -> replacement
_ESCAPE_MAP = {
    '"': '"',
    '\\': '\\',
    'n': '\n',
    't': '\t',
    'r': '\r',
    '0': '\0',
}

# Characters that terminate a bare string
_BARE_STRING_STOPS = frozenset('"=;{}<>\n\r')

# Characters valid in identifiers (beyond start)
_IDENT_CHARS = frozenset(
    'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-'
)

# Characters valid as identifier start
_IDENT_START = frozenset(
    'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_'
)

# Digit set
_DIGITS = frozenset('0123456789')

# Hex digit set
_HEX_DIGITS = frozenset('0123456789abcdefABCDEF')

# Duration component characters
_DURATION_CHARS = frozenset('0123456789YMDTHWS.')

# Single-char token dispatch (char -> TokenType, value)
_SINGLE_CHAR_TOKENS = {
    '{': (TokenType.HEADER_OPEN, '{'),
    '}': (TokenType.HEADER_CLOSE, '}'),
    '=': (TokenType.EQUALS, '='),
    '.': (TokenType.DOT, '.'),
    '?': (TokenType.PREFIX_BOOLEAN, '?'),
    '~': (TokenType.PREFIX_NULL, '~'),
    '^': (TokenType.PREFIX_BINARY, '^'),
    '&': (TokenType.PREFIX_EXTENSION, '&'),
    '$': (TokenType.PREFIX_META, '$'),
    '%': (TokenType.PREFIX_VERB, '%'),
    '!': (TokenType.MODIFIER_CRITICAL, '!'),
    '*': (TokenType.MODIFIER_REDACTED, '*'),
}

# Modifier targets: characters that follow - to make it a deprecated modifier
_DEPRECATED_NEXT = frozenset('"!*#?@^~&%')

# Whitespace
_WHITESPACE = frozenset(' \t')


def tokenize(source: str) -> List[Token]:
    """Tokenize ODIN source text into a list of tokens."""
    return Tokenizer(source).tokenize()


class Tokenizer:
    """Single-pass character scanner for ODIN notation.

    Optimized: uses direct text indexing, frozenset lookups, and minimizes
    method call overhead on hot paths.
    """

    __slots__ = (
        '_text', '_len', '_pos', '_line', '_col',
        '_after_equals', '_after_type_prefix',
    )

    def __init__(self, text: str) -> None:
        self._text = text
        self._len = len(text)
        self._pos = 0
        self._line = 1
        self._col = 1
        self._after_equals = False
        self._after_type_prefix = False

    # ── Public ────────────────────────────────────────────────────────────

    def tokenize(self) -> List[Token]:
        """Tokenize entire input into a token list."""
        tokens: List[Token] = []
        _append = tokens.append
        text = self._text
        text_len = self._len

        while self._pos < text_len:
            token = self._next_token()
            if token is not None:
                _append(token)

        _append(Token(TokenType.EOF, "", self._line, self._col))
        return tokens

    # ── Main dispatch ─────────────────────────────────────────────────────

    def _next_token(self) -> Optional[Token]:
        text = self._text
        pos = self._pos
        ch = text[pos]

        # Whitespace (skip spaces and tabs) — most common, check first
        if ch == ' ' or ch == '\t':
            pos += 1
            col = self._col + 1
            while pos < self._len and (text[pos] == ' ' or text[pos] == '\t'):
                pos += 1
                col += 1
            self._pos = pos
            self._col = col
            return None

        # Newlines
        if ch == '\n':
            line, col = self._line, self._col
            self._pos = pos + 1
            self._line = line + 1
            self._col = 1
            self._after_equals = False
            return Token(TokenType.NEWLINE, "\n", line, col)

        if ch == '\r':
            line, col = self._line, self._col
            pos += 1
            if pos < self._len and text[pos] == '\n':
                pos += 1
            self._pos = pos
            self._line = line + 1
            self._col = 1
            self._after_equals = False
            return Token(TokenType.NEWLINE, "\n", line, col)

        # Comment
        if ch == ';':
            return self._scan_comment()

        # Equals — set flag
        if ch == '=':
            self._after_equals = True
            col = self._col
            self._pos = pos + 1
            self._col = col + 1
            return Token(TokenType.EQUALS, '=', self._line, col)

        # Single-char tokens (dispatch table)
        single = _SINGLE_CHAR_TOKENS.get(ch)
        if single is not None:
            tt, val = single
            if ch == '{':
                self._after_equals = False
            col = self._col
            self._pos = pos + 1
            self._col = col + 1
            return Token(tt, val, self._line, col)

        # Array index [...]
        if ch == '[':
            return self._scan_array_index()

        # String
        if ch == '"':
            self._after_type_prefix = False
            return self._scan_string()

        # Hash prefix: #, ##, #$, #%
        if ch == '#':
            return self._scan_hash_prefix()

        # Reference @ or directive
        if ch == '@':
            return self._scan_at()

        # Dash: deprecated modifier, doc separator, or negative number
        if ch == '-':
            if self._after_type_prefix:
                self._after_type_prefix = False
                return self._scan_number(self._line, self._col)
            return self._scan_dash()

        # Identifier, keyword, number, or temporal
        if ch in _IDENT_START or ch in _DIGITS:
            self._after_type_prefix = False
            return self._scan_identifier_or_value()

        # Unknown character
        line, col = self._line, self._col
        self._pos = pos + 1
        self._col = col + 1
        return Token(TokenType.ERROR, ch, line, col)

    # ── Scanning methods ──────────────────────────────────────────────────

    def _scan_comment(self) -> Token:
        line, col = self._line, self._col
        self._pos += 1
        self._col += 1
        start = self._pos
        text = self._text
        pos = self._pos
        while pos < self._len:
            c = text[pos]
            if c == '\n' or c == '\r':
                break
            pos += 1
        comment_text = text[start:pos]
        self._col += pos - start
        self._pos = pos
        return Token(TokenType.COMMENT, ";" + comment_text, line, col)

    def _scan_array_index(self) -> Token:
        line, col = self._line, self._col
        self._pos += 1
        self._col += 1
        # Find closing ] using str.find — avoids char-by-char loop
        text = self._text
        close = text.find(']', self._pos)
        if close == -1:
            # No closing bracket — scan to end
            content = text[self._pos:]
            self._col += len(content)
            self._pos = self._len
        else:
            content = text[self._pos:close]
            self._col += len(content) + 1  # +1 for ]
            self._pos = close + 1
        return Token(TokenType.ARRAY_INDEX, content, line, col)

    def _scan_string(self) -> Token:
        line, col = self._line, self._col
        pos = self._pos + 1  # skip opening "
        self._col += 1

        # Check for multi-line """ or empty ""
        if pos < self._len and self._text[pos] == '"':
            if pos + 1 < self._len and self._text[pos + 1] == '"':
                # Triple quote
                self._pos = pos + 2
                self._col += 2
                return self._scan_multiline_string(line, col)
            else:
                # Empty string ""
                self._pos = pos + 1
                self._col += 1
                return Token(TokenType.STRING_QUOTED, "", line, col)

        self._pos = pos
        return self._scan_quoted_string(line, col)

    def _scan_quoted_string(self, line: int, col: int) -> Token:
        """Scan a single-line quoted string (opening " already consumed)."""
        text = self._text
        text_len = self._len
        pos = self._pos

        # Fast path: scan for end-of-string without escapes
        scan_start = pos
        while pos < text_len:
            ch = text[pos]
            if ch == '"':
                # No escapes — direct slice
                value = text[scan_start:pos]
                pos += 1
                self._col += pos - self._pos
                self._pos = pos
                return Token(TokenType.STRING_QUOTED, value, line, col)
            if ch == '\\':
                break  # Has escapes — fall through to slow path
            if ch == '\n' or ch == '\r':
                self._col += pos - self._pos
                self._pos = pos
                return Token(TokenType.ERROR, "Unterminated string", line, col)
            pos += 1

        # Slow path: string has escape sequences
        parts: list[str] = []
        if pos > scan_start:
            parts.append(text[scan_start:pos])

        while pos < text_len:
            ch = text[pos]
            if ch == '\n' or ch == '\r':
                self._col += pos - self._pos
                self._pos = pos
                return Token(TokenType.ERROR, "Unterminated string", line, col)
            if ch == '\\':
                pos += 1
                if pos >= text_len:
                    self._pos = pos
                    return Token(TokenType.ERROR, "Unterminated string", line, col)
                esc = text[pos]
                pos += 1
                mapped = _ESCAPE_MAP.get(esc)
                if mapped is not None:
                    parts.append(mapped)
                elif esc == '$':
                    # Literal dollar; keep the backslash before `${` so the
                    # interpolation layer recognizes the escaped marker.
                    if pos < text_len and text[pos] == '{':
                        parts.append('\\$')
                    else:
                        parts.append('$')
                elif esc == 'u':
                    # \uXXXX
                    if pos + 4 <= text_len:
                        hex_str = text[pos:pos + 4]
                        pos += 4
                        try:
                            parts.append(chr(int(hex_str, 16)))
                        except (ValueError, OverflowError):
                            parts.append('?')
                    else:
                        parts.append('?')
                        pos = text_len
                elif esc == 'U':
                    # \UXXXXXXXX
                    if pos + 8 <= text_len:
                        hex_str = text[pos:pos + 8]
                        pos += 8
                        try:
                            parts.append(chr(int(hex_str, 16)))
                        except (ValueError, OverflowError):
                            parts.append('?')
                    else:
                        parts.append('?')
                        pos = text_len
                else:
                    esc_col = self._col + (pos - self._pos) - 2
                    self._pos = pos
                    self._col = esc_col + 2
                    return Token(TokenType.ERROR, f"Invalid escape sequence: \\{esc}",
                                 line, esc_col)
            elif ch == '"':
                pos += 1
                self._col += pos - self._pos
                self._pos = pos
                return Token(TokenType.STRING_QUOTED, "".join(parts), line, col)
            else:
                # Batch non-escape characters
                batch_start = pos
                pos += 1
                while pos < text_len:
                    c = text[pos]
                    if c == '"' or c == '\\' or c == '\n' or c == '\r':
                        break
                    pos += 1
                parts.append(text[batch_start:pos])

        self._col += pos - self._pos
        self._pos = pos
        return Token(TokenType.ERROR, "Unterminated string", line, col)

    def _scan_multiline_string(self, line: int, col: int) -> Token:
        """Scan a triple-quoted string (opening \"\"\" already consumed).

        Content is captured verbatim and may span newlines; closes at the next `\"\"\"`.
        """
        text = self._text
        text_len = self._len
        content_start = self._pos
        pos = self._pos

        while pos < text_len:
            if (
                text[pos] == '"'
                and pos + 2 < text_len
                and text[pos + 1] == '"'
                and text[pos + 2] == '"'
            ):
                value = text[content_start:pos]
                pos += 3
                self._update_line_col_from(self._pos, pos)
                self._pos = pos
                return Token(TokenType.STRING_MULTILINE, value, line, col)
            pos += 1

        self._update_line_col_from(self._pos, pos)
        self._pos = pos
        return Token(TokenType.ERROR, "Unterminated multi-line string", line, col)

    def _update_line_col_from(self, start: int, end: int) -> None:
        """Update line/col by scanning text[start:end] for newlines."""
        text = self._text
        line = self._line
        col = self._col
        for i in range(start, end):
            if text[i] == '\n':
                line += 1
                col = 1
            else:
                col += 1
        self._line = line
        self._col = col

    def _scan_hash_prefix(self) -> Token:
        """Scan #, ##, #$, #% prefixes."""
        line, col = self._line, self._col
        pos = self._pos + 1
        self._col += 1

        if pos < self._len:
            next_ch = self._text[pos]
            if next_ch == '#':
                self._pos = pos + 1
                self._col += 1
                self._after_type_prefix = True
                return Token(TokenType.PREFIX_INTEGER, "##", line, col)
            if next_ch == '$':
                self._pos = pos + 1
                self._col += 1
                self._after_type_prefix = True
                return Token(TokenType.PREFIX_CURRENCY, "#$", line, col)
            if next_ch == '%':
                self._pos = pos + 1
                self._col += 1
                self._after_type_prefix = True
                return Token(TokenType.PREFIX_PERCENT, "#%", line, col)

        self._pos = pos
        self._after_type_prefix = True
        return Token(TokenType.PREFIX_NUMBER, "#", line, col)

    def _scan_at(self) -> Token:
        """Scan @ — either directive or reference prefix."""
        line, col = self._line, self._col

        # Directives only at column 1
        if col == 1:
            directive = self._try_scan_directive(line, col)
            if directive is not None:
                return directive

        self._pos += 1
        self._col += 1
        return Token(TokenType.PREFIX_REFERENCE, "@", line, col)

    def _try_scan_directive(self, line: int, col: int) -> Optional[Token]:
        """Try to parse @import, @schema, @if directives."""
        text = self._text
        pos = self._pos

        # Check @import (7 chars)
        if pos + 7 <= self._len and text[pos:pos + 7] == '@import':
            next_pos = pos + 7
            if next_pos >= self._len or text[next_pos] in (' ', '\t'):
                self._pos = next_pos
                self._col += 7
                rest = self._scan_to_eol()
                return Token(TokenType.DIRECTIVE_IMPORT, "@import" + rest, line, col)

        # Check @schema (7 chars)
        if pos + 7 <= self._len and text[pos:pos + 7] == '@schema':
            next_pos = pos + 7
            if next_pos >= self._len or text[next_pos] in (' ', '\t'):
                self._pos = next_pos
                self._col += 7
                rest = self._scan_to_eol()
                return Token(TokenType.DIRECTIVE_SCHEMA, "@schema" + rest, line, col)

        # Check @if (3 chars)
        if pos + 3 <= self._len and text[pos:pos + 3] == '@if':
            next_pos = pos + 3
            if next_pos >= self._len or text[next_pos] in (' ', '\t'):
                self._pos = next_pos
                self._col += 3
                rest = self._scan_to_eol()
                return Token(TokenType.DIRECTIVE_COND, "@if" + rest, line, col)

        return None

    def _scan_dash(self) -> Token:
        """Scan - which could be deprecated modifier, doc separator, or value."""
        text = self._text
        pos = self._pos
        line, col = self._line, self._col

        # Check for doc separator ---
        if pos + 2 < self._len and text[pos + 1] == '-' and text[pos + 2] == '-':
            self._pos = pos + 3
            self._col = col + 3
            return Token(TokenType.DOC_SEPARATOR, "---", line, col)

        # Look ahead
        if pos + 1 < self._len:
            next_ch = text[pos + 1]

            # Deprecated modifier: - before string, type prefix, modifier, null
            if next_ch in _DEPRECATED_NEXT:
                self._pos = pos + 1
                self._col = col + 1
                return Token(TokenType.MODIFIER_DEPRECATED, "-", line, col)

            # - followed by digit: could be deprecated + date
            if next_ch in _DIGITS:
                if self._looks_like_deprecated_date():
                    self._pos = pos + 1
                    self._col = col + 1
                    return Token(TokenType.MODIFIER_DEPRECATED, "-", line, col)

            # - before whitespace, newline, EOF, comment, colon
            if next_ch in (' ', '\t', '\n', '\r', ';', ':'):
                self._pos = pos + 1
                self._col = col + 1
                return Token(TokenType.MODIFIER_DEPRECATED, "-", line, col)

        # - at end of input
        if pos + 1 >= self._len:
            self._pos = pos + 1
            self._col = col + 1
            return Token(TokenType.MODIFIER_DEPRECATED, "-", line, col)

        # Fall through: treat as identifier/bare string
        return self._scan_identifier_or_value()

    def _looks_like_deprecated_date(self) -> bool:
        """Check if -DDDD-... looks like deprecated modifier + date."""
        text = self._text
        pos = self._pos + 1
        digit_count = 0
        while pos < self._len and text[pos] in _DIGITS:
            digit_count += 1
            pos += 1
        return digit_count == 4 and pos < self._len and text[pos] == '-'

    def _scan_identifier_or_value(self) -> Token:
        """Scan identifier, keyword (true/false), number, or temporal."""
        text = self._text
        line, col = self._line, self._col
        start = self._pos

        # If starts with digit, could be number or date/time
        if text[start] in _DIGITS:
            return self._scan_number_or_temporal(line, col)

        # Scan identifier characters using direct indexing
        pos = start
        while pos < self._len and text[pos] in _IDENT_CHARS:
            pos += 1

        self._col += pos - start
        self._pos = pos
        value = text[start:pos]

        # Keywords
        if value == "true" or value == "false":
            return Token(TokenType.BOOLEAN, value, line, col)

        # Temporal types
        if len(value) > 1:
            first = value[0]
            second = value[1]
            if first == 'T' and second in _DIGITS:
                self._pos = start
                self._col = col
                return self._scan_time(line, col)
            if first == 'P' and (second == 'T' or second in _DIGITS):
                self._pos = start
                self._col = col
                return self._scan_duration(line, col)

        # On value side: bare string
        if self._after_equals:
            self._pos = start
            self._col = col
            return self._scan_bare_string(line, col)

        return Token(TokenType.IDENTIFIER, value, line, col)

    def _scan_bare_string(self, line: int, col: int) -> Token:
        """Scan a bare (unquoted) string value."""
        text = self._text
        start = self._pos
        pos = start
        while pos < self._len and text[pos] not in _BARE_STRING_STOPS:
            pos += 1
        # rstrip whitespace
        end = pos
        while end > start and text[end - 1] in _WHITESPACE:
            end -= 1
        value = text[start:end]
        self._col += pos - start
        self._pos = pos
        return Token(TokenType.STRING_BARE, value, line, col)

    def _scan_number_or_temporal(self, line: int, col: int) -> Token:
        """Scan a number or date/timestamp starting with a digit."""
        text = self._text
        start = self._pos
        pos = start

        # Count leading digits
        while pos < self._len and text[pos] in _DIGITS:
            pos += 1
        digit_count = pos - start

        # Date pattern: 4 digits followed by -
        if digit_count == 4 and pos < self._len and text[pos] == '-':
            return self._scan_date_or_timestamp(line, col)

        # Number
        return self._scan_number(line, col)

    def _scan_number(self, line: int, col: int) -> Token:
        """Scan a numeric value."""
        text = self._text
        start = self._pos
        pos = start

        # Optional leading minus
        if pos < self._len and text[pos] == '-':
            pos += 1

        # Integer part
        while pos < self._len and text[pos] in _DIGITS:
            pos += 1

        # Fractional part
        if pos < self._len and text[pos] == '.':
            pos += 1
            while pos < self._len and text[pos] in _DIGITS:
                pos += 1

        # Currency code suffix :XXX
        if pos < self._len and text[pos] == ':':
            pos += 1
            while pos < self._len and text[pos].isalpha():
                pos += 1

        # Exponent
        if pos < self._len and (text[pos] == 'e' or text[pos] == 'E'):
            pos += 1
            if pos < self._len and (text[pos] == '+' or text[pos] == '-'):
                pos += 1
            while pos < self._len and text[pos] in _DIGITS:
                pos += 1

        value = text[start:pos]
        self._col += pos - start
        self._pos = pos
        return Token(TokenType.NUMBER, value, line, col)

    def _scan_date_or_timestamp(self, line: int, col: int) -> Token:
        """Scan a date (YYYY-MM-DD) or timestamp."""
        text = self._text
        start = self._pos
        pos = start

        # YYYY-MM-DD (10 chars minimum)
        pos += 4  # YYYY
        pos += 1  # -
        # MM
        while pos < self._len and text[pos] in _DIGITS:
            pos += 1
        # -
        if pos < self._len and text[pos] == '-':
            pos += 1
        # DD
        while pos < self._len and text[pos] in _DIGITS:
            pos += 1

        # Check for time component T
        if pos < self._len and text[pos] == 'T':
            pos += 1
            pos = self._scan_time_component_fast(pos)
            value = text[start:pos]
            self._col += pos - start
            self._pos = pos
            return Token(TokenType.TIMESTAMP, value, line, col)

        value = text[start:pos]
        self._col += pos - start
        self._pos = pos
        return Token(TokenType.DATE, value, line, col)

    def _scan_time_component_fast(self, pos: int) -> int:
        """Scan HH:MM:SS[.fraction][timezone], returns new pos."""
        text = self._text
        text_len = self._len

        # HH
        while pos < text_len and text[pos] in _DIGITS:
            pos += 1
        # :MM
        if pos < text_len and text[pos] == ':':
            pos += 1
            while pos < text_len and text[pos] in _DIGITS:
                pos += 1
        # :SS
        if pos < text_len and text[pos] == ':':
            pos += 1
            while pos < text_len and text[pos] in _DIGITS:
                pos += 1
        # .fractional
        if pos < text_len and text[pos] == '.':
            pos += 1
            while pos < text_len and text[pos] in _DIGITS:
                pos += 1
        # Timezone: Z or +/-HH:MM
        if pos < text_len and text[pos] == 'Z':
            pos += 1
        elif pos < text_len and (text[pos] == '+' or text[pos] == '-'):
            pos += 1
            while pos < text_len and text[pos] in _DIGITS:
                pos += 1
            if pos < text_len and text[pos] == ':':
                pos += 1
                while pos < text_len and text[pos] in _DIGITS:
                    pos += 1

        return pos

    def _scan_time(self, line: int, col: int) -> Token:
        """Scan a time value T10:30:00."""
        text = self._text
        start = self._pos
        pos = start + 1  # skip T
        pos = self._scan_time_component_fast(pos)
        value = text[start:pos]
        self._col += pos - start
        self._pos = pos
        return Token(TokenType.TIME, value, line, col)

    def _scan_duration(self, line: int, col: int) -> Token:
        """Scan a duration value P1Y2M3DT4H5M6S."""
        text = self._text
        start = self._pos
        pos = start + 1  # skip P

        while pos < self._len and text[pos] in _DURATION_CHARS:
            pos += 1

        value = text[start:pos]
        self._col += pos - start
        self._pos = pos
        return Token(TokenType.DURATION, value, line, col)

    # ── Utility methods ───────────────────────────────────────────────────

    def _scan_to_eol(self) -> str:
        """Scan remaining characters until end of line."""
        text = self._text
        start = self._pos
        pos = start
        while pos < self._len:
            c = text[pos]
            if c == '\n' or c == '\r':
                break
            pos += 1
        self._col += pos - start
        self._pos = pos
        return text[start:pos]

    def _advance(self) -> str:
        """Advance position and return the consumed character."""
        ch = self._text[self._pos]
        self._pos += 1
        if ch == '\n':
            self._line += 1
            self._col = 1
        else:
            self._col += 1
        return ch

    def _advance_pos(self) -> None:
        """Advance position without returning character."""
        ch = self._text[self._pos]
        self._pos += 1
        if ch == '\n':
            self._line += 1
            self._col = 1
        else:
            self._col += 1
