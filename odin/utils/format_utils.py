"""Shared formatting utilities for ODIN values."""
from __future__ import annotations

import base64
from decimal import Decimal
from typing import Optional

from odin.types.document import OdinModifiers
from odin.types.values import (
    OdinValue, OdinNull, OdinBoolean, OdinString, OdinNumber, OdinInteger,
    OdinCurrency, OdinPercent, OdinDate, OdinTimestamp, OdinTime, OdinDuration,
    OdinReference, OdinBinary, OdinVerbExpression, OdinArray, OdinObject,
)


# Translation table for string escaping (used by str.translate)
_ESCAPE_TABLE = str.maketrans({
    '\\': '\\\\',
    '"': '\\"',
    '\n': '\\n',
    '\r': '\\r',
    '\t': '\\t',
})

# Characters that need escaping (for fast check)
_NEEDS_ESCAPE = frozenset('\\"\n\r\t')


def escape_odin_string(value: str, canonical: bool = False) -> str:
    """Escape special characters in a quoted ODIN string.

    Returns the escaped string WITHOUT surrounding quotes.
    Uses str.translate() for O(n) performance.
    """
    if canonical:
        return value.translate(_ESCAPE_TABLE)

    # Fast path: check if any escaping is needed
    for ch in value:
        if ch in _NEEDS_ESCAPE:
            return value.translate(_ESCAPE_TABLE)

    return value


# Pre-computed modifier prefix lookup (index = required*4 + confidential*2 + deprecated)
_MODIFIER_PREFIXES = ['', '-', '*', '*-', '!', '!-', '!*', '!*-']


def format_modifier_prefix(modifiers: Optional[OdinModifiers]) -> str:
    """Format modifier prefix string: !, *, - in correct order."""
    if modifiers is None:
        return ''
    idx = 0
    if modifiers.required:
        idx |= 4
    if modifiers.confidential:
        idx |= 2
    if modifiers.deprecated:
        idx |= 1
    return _MODIFIER_PREFIXES[idx]


def has_any_modifier(modifiers: Optional[OdinModifiers]) -> bool:
    """Check if any modifier is set."""
    if modifiers is None:
        return False
    return modifiers.required or modifiers.confidential or modifiers.deprecated


def format_binary(value: OdinBinary) -> str:
    """Format binary value with optional algorithm prefix."""
    b64 = base64.b64encode(value.data).decode('ascii')
    if value.algorithm:
        return f'^{value.algorithm}:{b64}'
    return f'^{b64}'


def format_string(value: str) -> str:
    """Format a quoted ODIN string."""
    return f'"{escape_odin_string(value)}"'


def format_currency(value: OdinCurrency) -> str:
    """Format currency value with #$ prefix."""
    if value.raw is not None:
        num_part = value.raw
    else:
        num_part = str(value.value.quantize(Decimal(10) ** -value.decimal_places))
    code_part = f':{value.currency_code}' if value.currency_code else ''
    return f'#${num_part}{code_part}'


def format_percent(value: OdinPercent) -> str:
    """Format percent value with #% prefix."""
    if value.raw is not None:
        return f'#%{value.raw}'
    return f'#%{value.value}'


def format_verb_expression(value: OdinVerbExpression) -> str:
    """Format a verb expression value."""
    prefix = '%&' if value.is_custom else '%'
    result = f'{prefix}{value.verb}'
    for arg in value.args:
        result += ' ' + format_verb_argument(arg)
    return result


def format_verb_argument(value: OdinValue) -> str:
    """Format a single verb argument."""
    if isinstance(value, OdinReference):
        return f'@{value.path}'
    if isinstance(value, OdinString):
        return format_string(value.value)
    if isinstance(value, OdinVerbExpression):
        return format_verb_expression(value)
    if isinstance(value, OdinNumber):
        return f'#{value.raw}' if value.raw is not None else f'#{value.value}'
    if isinstance(value, OdinInteger):
        return f'##{value.raw}' if value.raw is not None else f'##{value.value}'
    if isinstance(value, OdinCurrency):
        return format_currency(value)
    if isinstance(value, OdinPercent):
        return format_percent(value)
    if isinstance(value, OdinBoolean):
        return '?true' if value.value else '?false'
    if isinstance(value, OdinNull):
        return '~'
    return format_value(value)


def _fmt_null(v: OdinNull) -> str:
    return '~'

def _fmt_bool(v: OdinBoolean) -> str:
    return '?true' if v.value else '?false'

def _fmt_str(v: OdinString) -> str:
    return format_string(v.value)

def _fmt_num(v: OdinNumber) -> str:
    return f'#{v.raw}' if v.raw is not None else f'#{v.value}'

def _fmt_int(v: OdinInteger) -> str:
    return f'##{v.raw}' if v.raw is not None else f'##{v.value}'

def _fmt_cur(v: OdinCurrency) -> str:
    return format_currency(v)

def _fmt_pct(v: OdinPercent) -> str:
    return format_percent(v)

def _fmt_date(v: OdinDate) -> str:
    return v.raw

def _fmt_ts(v: OdinTimestamp) -> str:
    return v.raw

def _fmt_time(v: OdinTime) -> str:
    return v.value

def _fmt_dur(v: OdinDuration) -> str:
    return v.value

def _fmt_ref(v: OdinReference) -> str:
    return f'@{v.path}'

def _fmt_bin(v: OdinBinary) -> str:
    return format_binary(v)

def _fmt_verb(v: OdinVerbExpression) -> str:
    return format_verb_expression(v)

def _fmt_arr(v: OdinArray) -> str:
    return '[]'

def _fmt_obj(v: OdinObject) -> str:
    return '{}'


# Type dispatch dict — O(1) lookup instead of isinstance chain
_VALUE_FORMATTERS = {
    OdinNull: _fmt_null,
    OdinBoolean: _fmt_bool,
    OdinString: _fmt_str,
    OdinNumber: _fmt_num,
    OdinInteger: _fmt_int,
    OdinCurrency: _fmt_cur,
    OdinPercent: _fmt_pct,
    OdinDate: _fmt_date,
    OdinTimestamp: _fmt_ts,
    OdinTime: _fmt_time,
    OdinDuration: _fmt_dur,
    OdinReference: _fmt_ref,
    OdinBinary: _fmt_bin,
    OdinVerbExpression: _fmt_verb,
    OdinArray: _fmt_arr,
    OdinObject: _fmt_obj,
}


def format_value(value: OdinValue) -> str:
    """Format any OdinValue to its ODIN text representation."""
    formatter = _VALUE_FORMATTERS.get(type(value))
    if formatter is not None:
        return formatter(value)
    return ''


def is_primitive_value(value: OdinValue) -> bool:
    """Check if a value is primitive (eligible for tabular)."""
    return not isinstance(value, (OdinArray, OdinObject))
