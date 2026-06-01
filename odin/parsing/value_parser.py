"""Value parser - converts tokens to typed OdinValue instances."""
from __future__ import annotations

import base64
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Tuple

from odin.parsing.tokens import Token, TokenType
from odin.types.errors import ParseError, ParseErrorCodes

# Token types that are prefixes and should be merged with the following token
_PREFIX_TOKEN_TYPES = frozenset({
    TokenType.PREFIX_VERB,
    TokenType.PREFIX_REFERENCE,
    TokenType.PREFIX_NUMBER,
    TokenType.PREFIX_INTEGER,
    TokenType.PREFIX_CURRENCY,
    TokenType.PREFIX_PERCENT,
    TokenType.PREFIX_BOOLEAN,
    TokenType.PREFIX_NULL,
    TokenType.PREFIX_BINARY,
    TokenType.PREFIX_EXTENSION,
    TokenType.MODIFIER_CRITICAL,
    TokenType.MODIFIER_REDACTED,
    TokenType.MODIFIER_DEPRECATED,
})
from odin.types.values import (
    NULL,
    TRUE,
    FALSE,
    OdinBinary,
    OdinBoolean,
    OdinCurrency,
    OdinDate,
    OdinDuration,
    OdinInteger,
    OdinNull,
    OdinNumber,
    OdinPercent,
    OdinReference,
    OdinString,
    OdinTime,
    OdinTimestamp,
    OdinValue,
    OdinVerbExpression,
)
from odin.types.document import OdinModifiers


def parse_value(tokens: List[Token], pos: int) -> Tuple[OdinValue, int]:
    """Parse a value starting at position pos in the token list.

    Returns (value, tokens_consumed).
    """
    if pos >= len(tokens):
        return OdinString(""), 0

    token = tokens[pos]
    tt = token.type

    # Null
    if tt == TokenType.PREFIX_NULL:
        return NULL, 1

    # Boolean - bare true/false keyword
    if tt == TokenType.BOOLEAN:
        return TRUE if token.value == "true" else FALSE, 1

    # Boolean prefix ?
    if tt == TokenType.PREFIX_BOOLEAN:
        # Check if next token is true/false
        if pos + 1 < len(tokens):
            nxt = tokens[pos + 1]
            if nxt.type == TokenType.BOOLEAN or (
                nxt.type == TokenType.IDENTIFIER and nxt.value in ("true", "false")
            ):
                return OdinBoolean(nxt.value == "true"), 2
        return TRUE, 1

    # Quoted string
    if tt == TokenType.STRING_QUOTED or tt == TokenType.STRING_MULTILINE:
        return OdinString(token.value), 1

    # Number #
    if tt == TokenType.PREFIX_NUMBER:
        coerced = _parse_prefixed_reference(tokens, pos, "number")
        if coerced is not None:
            return coerced
        return _parse_number_value(tokens, pos)

    # Integer ##
    if tt == TokenType.PREFIX_INTEGER:
        coerced = _parse_prefixed_reference(tokens, pos, "integer")
        if coerced is not None:
            return coerced
        return _parse_integer_value(tokens, pos)

    # Currency #$
    if tt == TokenType.PREFIX_CURRENCY:
        coerced = _parse_prefixed_reference(tokens, pos, "currency")
        if coerced is not None:
            return coerced
        return _parse_currency_value(tokens, pos)

    # Percent #%
    if tt == TokenType.PREFIX_PERCENT:
        coerced = _parse_prefixed_reference(tokens, pos, "percent")
        if coerced is not None:
            return coerced
        return _parse_percent_value(tokens, pos)

    # Reference @
    if tt == TokenType.PREFIX_REFERENCE:
        return _parse_reference_value(tokens, pos)

    # Binary ^
    if tt == TokenType.PREFIX_BINARY:
        return _parse_binary_value(tokens, pos)

    # Verb %
    if tt == TokenType.PREFIX_VERB:
        return _parse_verb_value(tokens, pos)

    # Date
    if tt == TokenType.DATE:
        return _parse_date_value(token), 1

    # Timestamp
    if tt == TokenType.TIMESTAMP:
        return _parse_timestamp_value(token), 1

    # Time
    if tt == TokenType.TIME:
        return OdinTime(token.value), 1

    # Duration
    if tt == TokenType.DURATION:
        return OdinDuration(token.value), 1

    # NUMBER token (after type prefix already consumed - from tokenizer)
    if tt == TokenType.NUMBER:
        return _parse_raw_number(token), 1

    # Bare string - error
    if tt == TokenType.STRING_BARE:
        raise ParseError(
            "Strings must be quoted",
            ParseErrorCodes.P002,
            token.line,
            token.column,
        )

    # Identifier in value position - check for temporal-like or error
    if tt == TokenType.IDENTIFIER:
        val = token.value
        if val in ("true", "false"):
            return OdinBoolean(val == "true"), 1
        raise ParseError(
            "Strings must be quoted",
            ParseErrorCodes.P002,
            token.line,
            token.column,
        )

    # Error token from tokenizer
    if tt == TokenType.ERROR:
        msg = token.value if token.value else "Unexpected character"
        if "Unterminated" in msg:
            raise ParseError(msg, ParseErrorCodes.P004, token.line, token.column)
        if "Invalid escape" in msg:
            raise ParseError(msg, ParseErrorCodes.P005, token.line, token.column)
        raise ParseError(msg, ParseErrorCodes.P001, token.line, token.column)

    # Newline/EOF means empty value
    if tt in (TokenType.NEWLINE, TokenType.EOF, TokenType.COMMENT):
        return OdinString(""), 0

    raise ParseError(
        "Unexpected token in value position",
        ParseErrorCodes.P001,
        token.line,
        token.column,
    )


def parse_modifiers(tokens: List[Token], pos: int) -> Tuple[OdinModifiers, int]:
    """Parse modifier tokens (!, *, -) starting at pos.

    Returns (modifiers, tokens_consumed).
    """
    required = False
    confidential = False
    deprecated = False
    consumed = 0

    while pos + consumed < len(tokens):
        t = tokens[pos + consumed]
        if t.type == TokenType.MODIFIER_CRITICAL:
            required = True
            consumed += 1
        elif t.type == TokenType.MODIFIER_REDACTED:
            confidential = True
            consumed += 1
        elif t.type == TokenType.MODIFIER_DEPRECATED:
            deprecated = True
            consumed += 1
        else:
            break

    return OdinModifiers(required=required, confidential=confidential, deprecated=deprecated), consumed


# ── Internal helpers ─────────────────────────────────────────────────────


def _consume_number_token(tokens: List[Token], pos: int, prefix_name: str) -> Tuple[str, int]:
    """Consume the numeric token after a type prefix.

    Returns (raw_string, tokens_consumed_including_prefix).
    """
    if pos + 1 >= len(tokens):
        raise ParseError(
            f"Invalid numeric format",
            ParseErrorCodes.P006,
            tokens[pos].line,
            tokens[pos].column,
        )

    nxt = tokens[pos + 1]

    # Check for negative sign (MODIFIER_DEPRECATED used as unary minus)
    if nxt.type == TokenType.MODIFIER_DEPRECATED:
        # Need a number after the minus
        if pos + 2 >= len(tokens):
            raise ParseError(
                "Invalid numeric format",
                ParseErrorCodes.P006,
                tokens[pos].line,
                tokens[pos].column,
            )
        num_token = tokens[pos + 2]
        if num_token.type == TokenType.NUMBER:
            raw = "-" + num_token.value
            return raw, 3
        elif num_token.type == TokenType.MODIFIER_DEPRECATED:
            # Double negative: #--5
            raise ParseError(
                "Invalid numeric format",
                ParseErrorCodes.P006,
                tokens[pos].line,
                tokens[pos].column,
            )
        else:
            raise ParseError(
                "Invalid numeric format",
                ParseErrorCodes.P006,
                tokens[pos].line,
                tokens[pos].column,
            )

    if nxt.type == TokenType.NUMBER:
        return nxt.value, 2

    if nxt.type in (TokenType.NEWLINE, TokenType.EOF, TokenType.COMMENT):
        raise ParseError(
            "Invalid numeric format",
            ParseErrorCodes.P006,
            tokens[pos].line,
            tokens[pos].column,
        )

    # Could be a PREFIX_INTEGER after PREFIX_NUMBER (#  ## → ###)
    if nxt.type == TokenType.PREFIX_INTEGER:
        raise ParseError(
            "Invalid type prefix",
            ParseErrorCodes.P006,
            tokens[pos].line,
            tokens[pos].column,
        )

    raise ParseError(
        "Invalid numeric format",
        ParseErrorCodes.P006,
        tokens[pos].line,
        tokens[pos].column,
    )


def _parse_number_value(tokens: List[Token], pos: int) -> Tuple[OdinNumber, int]:
    """Parse # prefix number."""
    raw, consumed = _consume_number_token(tokens, pos, "number")
    try:
        value = float(raw)
    except ValueError:
        raise ParseError(
            "Invalid numeric format",
            ParseErrorCodes.P006,
            tokens[pos].line,
            tokens[pos].column,
        )
    return OdinNumber(value=value, raw=raw), consumed


def _parse_integer_value(tokens: List[Token], pos: int) -> Tuple[OdinInteger, int]:
    """Parse ## prefix integer."""
    raw, consumed = _consume_number_token(tokens, pos, "integer")
    try:
        value = int(raw)
    except ValueError:
        # Not a plain integer literal; allow only integral floats (e.g. 1e3)
        try:
            fval = float(raw)
        except ValueError:
            raise ParseError(
                "Invalid integer format",
                ParseErrorCodes.P006,
                tokens[pos].line,
                tokens[pos].column,
            )
        if fval != int(fval):
            raise ParseError(
                f"Integer (##) value cannot have a fractional part: {raw}",
                ParseErrorCodes.P006,
                tokens[pos].line,
                tokens[pos].column,
            )
        value = int(fval)
    return OdinInteger(value=value, raw=raw), consumed


def _parse_currency_value(tokens: List[Token], pos: int) -> Tuple[OdinCurrency, int]:
    """Parse #$ prefix currency."""
    raw, consumed = _consume_number_token(tokens, pos, "currency")

    # Extract currency code if present (e.g., "99.99:USD")
    currency_code: Optional[str] = None
    num_part = raw
    colon_pos = raw.find(":")
    if colon_pos >= 0:
        num_part = raw[:colon_pos]
        currency_code = raw[colon_pos + 1:].upper()

    try:
        value = Decimal(num_part)
    except InvalidOperation:
        raise ParseError(
            "Invalid currency format",
            ParseErrorCodes.P006,
            tokens[pos].line,
            tokens[pos].column,
        )

    # Count decimal places
    dot_pos = num_part.find(".")
    if dot_pos >= 0:
        # Handle scientific notation
        lower = num_part.lower()
        e_pos = lower.find("e")
        check_part = num_part[:e_pos] if e_pos >= 0 else num_part
        d_pos = check_part.find(".")
        decimal_places = len(check_part) - d_pos - 1 if d_pos >= 0 else 2
    else:
        decimal_places = 2  # Default to 2 if no decimal point

    return OdinCurrency(
        value=value,
        currency_code=currency_code,
        decimal_places=decimal_places,
        raw=num_part,
    ), consumed


def _parse_percent_value(tokens: List[Token], pos: int) -> Tuple[OdinPercent, int]:
    """Parse #% prefix percent."""
    raw, consumed = _consume_number_token(tokens, pos, "percent")
    try:
        value = float(raw)
    except ValueError:
        raise ParseError(
            "Invalid percent format",
            ParseErrorCodes.P006,
            tokens[pos].line,
            tokens[pos].column,
        )
    return OdinPercent(value=value, raw=raw), consumed


def _parse_prefixed_reference(
    tokens: List[Token], pos: int, kind: str,
) -> Optional[Tuple[OdinReference, int]]:
    """Parse a numeric prefix applied to a reference (e.g. ##@.year).

    Produces a reference carrying a synthetic :type directive so the engine
    coerces the resolved value on output. Returns None when the prefix is not
    followed by a reference.
    """
    if pos + 1 >= len(tokens):
        return None
    if tokens[pos + 1].type != TokenType.PREFIX_REFERENCE:
        return None
    ref, ref_consumed = _parse_reference_value(tokens, pos + 1)
    path = f"{ref.path} :type {kind}"
    return OdinReference(path=path), ref_consumed + 1


def _parse_reference_value(tokens: List[Token], pos: int) -> Tuple[OdinReference, int]:
    """Parse @ prefix reference. Collect path tokens after @."""
    # Collect all path components
    parts: List[str] = []
    consumed = 1  # consume @
    i = pos + 1

    while i < len(tokens):
        t = tokens[i]
        if t.type == TokenType.IDENTIFIER:
            parts.append(t.value)
            consumed += 1
            i += 1
        elif t.type == TokenType.DOT:
            parts.append(".")
            consumed += 1
            i += 1
        elif t.type == TokenType.ARRAY_INDEX:
            idx_val = t.value.strip()
            if idx_val.isdigit():
                parts.append(f"[{int(idx_val)}]")
            else:
                parts.append(f"[{idx_val}]")
            consumed += 1
            i += 1
        elif t.type == TokenType.PREFIX_META:
            parts.append("$")
            consumed += 1
            i += 1
        elif t.type == TokenType.PREFIX_EXTENSION:
            parts.append("&")
            consumed += 1
            i += 1
        elif t.type == TokenType.STRING_BARE:
            # After @, the tokenizer may emit the whole path as a bare string
            parts.append(t.value)
            consumed += 1
            i += 1
            # Check if next token is a quoted string (directive value like :currencyCode "USD")
            while i < len(tokens) and tokens[i].type == TokenType.STRING_QUOTED:
                parts.append(' "' + tokens[i].value + '"')
                consumed += 1
                i += 1
            break  # bare string consumes the rest of the reference path
        elif t.type == TokenType.BOOLEAN:
            # Handle field names like 'true' in paths
            parts.append(t.value)
            consumed += 1
            i += 1
        else:
            break

    path = "".join(parts)
    # Normalize leading zeros in array indices: [007] -> [7]
    import re
    path = re.sub(r'\[(\d+)\]', lambda m: f'[{int(m.group(1))}]', path)
    if not path:
        # Bare @ followed by # is always invalid (e.g. @#$invalid)
        if i < len(tokens) and tokens[i].type in (
            TokenType.PREFIX_NUMBER, TokenType.PREFIX_INTEGER,
            TokenType.PREFIX_CURRENCY, TokenType.PREFIX_PERCENT,
        ):
            raise ParseError(
                "Unexpected character",
                ParseErrorCodes.P001,
                tokens[pos].line,
                tokens[pos].column,
            )
        # Bare @ alone is valid — means "current source root" in transforms
        path = ""
    return OdinReference(path=path), consumed


def _parse_binary_value(tokens: List[Token], pos: int) -> Tuple[OdinBinary, int]:
    """Parse ^ prefix binary value."""
    # Collect the base64 content after ^
    consumed = 1  # consume ^
    i = pos + 1

    # Gather all tokens that are part of the binary value
    parts: List[str] = []
    while i < len(tokens):
        t = tokens[i]
        if t.type in (TokenType.NEWLINE, TokenType.EOF, TokenType.COMMENT,
                      TokenType.HEADER_OPEN):
            break
        # Identifier, number, or other content tokens (base64 chars)
        if t.type in (TokenType.IDENTIFIER, TokenType.NUMBER, TokenType.STRING_BARE):
            parts.append(t.value)
            consumed += 1
            i += 1
        elif t.type == TokenType.DOT:
            parts.append(".")
            consumed += 1
            i += 1
        elif t.type == TokenType.EQUALS:
            # = is padding in base64
            parts.append("=")
            consumed += 1
            i += 1
        else:
            break

    raw = "".join(parts)

    if not raw:
        return OdinBinary(data=b""), consumed

    # Check for algorithm prefix (algo:data)
    algorithm: Optional[str] = None
    b64_data = raw
    colon_pos = raw.find(":")
    if colon_pos >= 0:
        # Check if before colon is a valid algorithm name (letters/digits)
        potential_algo = raw[:colon_pos]
        if potential_algo.isalnum():
            algorithm = potential_algo
            b64_data = raw[colon_pos + 1:]

    # Validate and decode base64
    if b64_data:
        _validate_base64(b64_data, tokens[pos].line, tokens[pos].column)

    try:
        data = base64.b64decode(b64_data) if b64_data else b""
    except Exception:
        data = _lenient_b64_decode(b64_data)

    return OdinBinary(data=data, algorithm=algorithm), consumed


_B64_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/")


def _validate_base64(s: str, line: int, col: int) -> None:
    """Validate base64 content, raising ParseError on invalid chars or padding."""
    padding_started = False
    for i, ch in enumerate(s):
        if ch in _B64_CHARS:
            if padding_started:
                raise ParseError(
                    "Invalid Base64 padding",
                    ParseErrorCodes.P001,
                    line,
                    col,
                )
        elif ch == "=":
            padding_started = True
        elif ch in ("\n", "\r"):
            continue
        else:
            raise ParseError(
                f"Invalid Base64 character at position {i}",
                ParseErrorCodes.P001,
                line,
                col,
            )


def _lenient_b64_decode(s: str) -> bytes:
    """Lenient base64 decode that skips invalid chars."""
    b64_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    buf = 0
    bits = 0
    result = bytearray()
    for ch in s:
        if ch in b64_chars:
            val = b64_chars.index(ch)
            buf = (buf << 6) | val
            bits += 6
            if bits >= 8:
                bits -= 8
                result.append((buf >> bits) & 0xFF)
                buf &= (1 << bits) - 1
    return bytes(result)


def _parse_verb_value(tokens: List[Token], pos: int) -> Tuple[OdinVerbExpression, int]:
    """Parse % prefix verb expression. Collect all tokens until newline."""
    consumed = 1  # consume %
    i = pos + 1

    # First collect the verb name
    verb_name = ""
    is_custom = False

    if i < len(tokens):
        t = tokens[i]
        if t.type == TokenType.PREFIX_EXTENSION:
            # Custom verb: %&namespace.verb
            is_custom = True
            consumed += 1
            i += 1
            # Collect the full verb name
            name_parts: List[str] = []
            while i < len(tokens):
                t = tokens[i]
                if t.type in (TokenType.IDENTIFIER, TokenType.NUMBER):
                    name_parts.append(t.value)
                    consumed += 1
                    i += 1
                elif t.type == TokenType.DOT:
                    name_parts.append(".")
                    consumed += 1
                    i += 1
                else:
                    break
            verb_name = "&" + "".join(name_parts)
        elif t.type == TokenType.IDENTIFIER:
            verb_name = t.value
            consumed += 1
            i += 1
        elif t.type == TokenType.STRING_BARE:
            verb_name = t.value
            consumed += 1
            i += 1

    # Collect remaining tokens as raw expression parts
    # We must merge prefix tokens (%, @, #, ##, #$, #%, ?, ~, ^, !, *, -)
    # with their following token so "%eq" doesn't become "% eq".
    # After a @ prefix merges with its first token, continue merging path
    # continuation tokens (DOT, IDENTIFIER, PREFIX_META, NUMBER, LBRACKET,
    # RBRACKET) so that "@$const.str_version" stays as one raw part.
    _PATH_CONTINUATION_TYPES = frozenset({
        TokenType.DOT,
        TokenType.IDENTIFIER,
        TokenType.PREFIX_META,
        TokenType.NUMBER,
        TokenType.ARRAY_INDEX,
        TokenType.STRING_BARE,
    })
    raw_parts: List[str] = [f"%{verb_name}"]
    pending_prefix = ""
    building_ref = False  # True when we just merged @ prefix and should continue path
    while i < len(tokens):
        t = tokens[i]
        if t.type in (TokenType.NEWLINE, TokenType.EOF, TokenType.COMMENT):
            break
        text = _token_to_text(t)
        if t.type in _PREFIX_TOKEN_TYPES:
            # Accumulate prefix - will be merged with next token
            pending_prefix += text
        elif building_ref and t.type in _PATH_CONTINUATION_TYPES:
            # Continue building the reference path
            raw_parts[-1] += text
        else:
            if pending_prefix:
                raw_parts.append(pending_prefix + text)
                # Start path continuation if we just merged a @ prefix
                building_ref = "@" in pending_prefix
                pending_prefix = ""
            else:
                raw_parts.append(text)
                building_ref = False
        consumed += 1
        i += 1

    # Flush any trailing prefix (unlikely but safe)
    if pending_prefix:
        raw_parts.append(pending_prefix)

    raw_expr = " ".join(raw_parts)
    return OdinVerbExpression(verb=raw_expr, is_custom=is_custom), consumed


def _token_to_text(t: Token) -> str:
    """Reconstruct token text with prefix."""
    tt = t.type
    if tt == TokenType.PREFIX_REFERENCE:
        return "@"
    if tt == TokenType.PREFIX_INTEGER:
        return "##"
    if tt == TokenType.PREFIX_NUMBER:
        return "#"
    if tt == TokenType.PREFIX_CURRENCY:
        return "#$"
    if tt == TokenType.PREFIX_PERCENT:
        return "#%"
    if tt == TokenType.PREFIX_BOOLEAN:
        return "?"
    if tt == TokenType.PREFIX_NULL:
        return "~"
    if tt == TokenType.PREFIX_BINARY:
        return "^"
    if tt == TokenType.PREFIX_VERB:
        return "%"
    if tt == TokenType.STRING_QUOTED:
        return f'"{t.value}"'
    if tt == TokenType.MODIFIER_CRITICAL:
        return "!"
    if tt == TokenType.MODIFIER_REDACTED:
        return "*"
    if tt == TokenType.MODIFIER_DEPRECATED:
        return "-"
    return t.value


def _parse_raw_number(token: Token) -> OdinNumber:
    """Parse a raw NUMBER token into OdinNumber."""
    try:
        value = float(token.value)
    except ValueError:
        value = 0.0
    return OdinNumber(value=value, raw=token.value)


_DAYS_IN_MONTH = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _is_leap_year(year: int) -> bool:
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


def _parse_date_value(token: Token) -> OdinDate:
    """Parse a date token into OdinDate with validation."""
    raw = token.value
    parts = raw.split("-")
    if len(parts) != 3:
        raise ParseError(
            f"Invalid date format: {raw}",
            ParseErrorCodes.P001,
            token.line,
            token.column,
        )

    try:
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
    except ValueError:
        raise ParseError(
            f"Invalid date format: {raw}",
            ParseErrorCodes.P001,
            token.line,
            token.column,
        )

    if month < 1 or month > 12:
        raise ParseError(
            f"Invalid month {month}",
            ParseErrorCodes.P001,
            token.line,
            token.column,
        )

    max_day = _DAYS_IN_MONTH[month]
    if month == 2 and _is_leap_year(year):
        max_day = 29

    if day < 1 or day > max_day:
        raise ParseError(
            f"Invalid day {day} for month {month}",
            ParseErrorCodes.P001,
            token.line,
            token.column,
        )

    d = date(year, month, day)
    return OdinDate(value=d, raw=raw)


def _parse_timestamp_value(token: Token) -> OdinTimestamp:
    """Parse a timestamp token into OdinTimestamp."""
    raw = token.value
    # Store raw value, parse datetime best-effort
    try:
        # Handle leap seconds by clamping 60 -> 59
        adjusted = raw
        # Check for :60 seconds (leap second)
        if "T" in adjusted:
            time_part = adjusted.split("T", 1)[1]
            if ":60" in time_part:
                adjusted = adjusted.replace(":60", ":59", 1)
        dt = datetime.fromisoformat(adjusted.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        dt = datetime(1970, 1, 1)
    return OdinTimestamp(value=dt, raw=raw)
