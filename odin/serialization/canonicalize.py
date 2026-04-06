"""Produce deterministic canonical form for hashing and signatures."""
from __future__ import annotations

from decimal import Decimal
from typing import List, Optional, Tuple

from odin.types.document import OdinDocument, OdinModifiers
from odin.types.values import (
    OdinValue, OdinNull, OdinBoolean, OdinString, OdinNumber, OdinInteger,
    OdinCurrency, OdinPercent, OdinDate, OdinTimestamp, OdinTime, OdinDuration,
    OdinReference, OdinBinary, OdinVerbExpression, OdinArray, OdinObject,
)
from odin.utils.format_utils import (
    escape_odin_string, format_binary, format_modifier_prefix,
)


def canonicalize(doc: OdinDocument) -> bytes:
    """Produce canonical UTF-8 bytes of a document.

    Canonical form guarantees:
    - Identical documents produce identical bytes
    - Paths sorted using canonical comparison
    - No comments, no headers, flat path = value format
    - LF line endings only
    """
    entries: List[Tuple[str, OdinValue]] = []

    # Collect metadata entries
    for key, value in doc.metadata.items():
        entries.append(('$.' + key, value))

    # Collect data entries (skip $. prefixed paths already in metadata)
    for key, value in doc.assignments.items():
        if len(key) > 1 and key[0] == '$' and key[1] == '.':
            continue
        entries.append((key, value))

    # Sort using canonical path comparison
    entries.sort(key=lambda e: _canonical_sort_tuple(e[0]))

    lines: List[str] = []
    for path, value in entries:
        mods = doc.modifiers.get(path)
        lines.append(_format_canonical_assignment(path, value, mods))

    text = '\n'.join(lines) + ('\n' if lines else '')
    return text.encode('utf-8')


def _canonical_sort_tuple(path: str) -> tuple:
    """Pre-compute a sort key tuple for canonical ordering.

    Returns a tuple that sorts correctly with Python's default tuple comparison,
    avoiding per-comparison function calls.

    Order: $ metadata first, & extension last, then segment-by-segment
    with array indices as integers.
    """
    # Priority prefix: 0 = metadata ($), 1 = normal, 2 = extension (&)
    if path[:1] == '$':
        priority = 0
    elif path[:1] == '&':
        priority = 2
    else:
        priority = 1

    # Split into segments, converting array indices to ints
    segments: list = []
    i = 0
    start = 0
    path_len = len(path)
    while i < path_len:
        ch = path[i]
        if ch == '.':
            if i > start:
                segments.append((0, path[start:i]))
            start = i + 1
            i += 1
        elif ch == '[':
            if i > start:
                segments.append((0, path[start:i]))
            close = path.find(']', i)
            if close > i + 1:
                idx_str = path[i + 1:close]
                if idx_str.isdigit():
                    segments.append((1, int(idx_str)))
                else:
                    segments.append((1, idx_str))
            i = close + 1 if close > 0 else path_len
            start = i
        else:
            i += 1
    if start < path_len:
        segments.append((0, path[start:]))

    return (priority, segments)


class _CanonicalSortKey:
    """Comparable wrapper for canonical path sorting."""
    __slots__ = ('path',)

    def __init__(self, path: str) -> None:
        self.path = path

    def __lt__(self, other: _CanonicalSortKey) -> bool:
        return canonical_path_compare(self.path, other.path) < 0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _CanonicalSortKey):
            return NotImplemented
        return self.path == other.path

    def __le__(self, other: _CanonicalSortKey) -> bool:
        return canonical_path_compare(self.path, other.path) <= 0

    def __gt__(self, other: _CanonicalSortKey) -> bool:
        return canonical_path_compare(self.path, other.path) > 0

    def __ge__(self, other: _CanonicalSortKey) -> bool:
        return canonical_path_compare(self.path, other.path) >= 0


def canonical_path_compare(a: str, b: str) -> int:
    """Compare two ODIN paths for canonical sorting.

    Rules:
    1. $ metadata first
    2. Segment-by-segment comparison
    3. Array indices sort numerically
    4. Extension paths (&domain) sort last
    """
    # $ metadata paths sort first
    a_is_meta = a[:1] == '$'
    b_is_meta = b[:1] == '$'
    if a_is_meta and not b_is_meta:
        return -1
    if not a_is_meta and b_is_meta:
        return 1

    # Extension paths sort last
    a_is_ext = a[:1] == '&'
    b_is_ext = b[:1] == '&'
    if a_is_ext and not b_is_ext:
        return 1
    if not a_is_ext and b_is_ext:
        return -1

    # Fast path: no array brackets
    if '[' not in a and '[' not in b:
        if a < b:
            return -1
        if a > b:
            return 1
        return 0

    # Segment-by-segment comparison
    a_pos = 0
    b_pos = 0
    a_len = len(a)
    b_len = len(b)

    while a_pos < a_len and b_pos < b_len:
        # Skip leading dots
        if a_pos < a_len and a[a_pos] == '.':
            a_pos += 1
        if b_pos < b_len and b[b_pos] == '.':
            b_pos += 1
        if a_pos >= a_len or b_pos >= b_len:
            break

        # Both array indices
        if a_pos < a_len and b_pos < b_len and a[a_pos] == '[' and b[b_pos] == '[':
            a_close = a.find(']', a_pos)
            b_close = b.find(']', b_pos)
            if a_close > a_pos + 1 and b_close > b_pos + 1:
                a_val = 0
                for i in range(a_pos + 1, a_close):
                    a_val = a_val * 10 + (ord(a[i]) - 48)
                b_val = 0
                for i in range(b_pos + 1, b_close):
                    b_val = b_val * 10 + (ord(b[i]) - 48)
                if a_val != b_val:
                    return -1 if a_val < b_val else 1
                a_pos = a_close + 1
                b_pos = b_close + 1
                continue

        # Regular segments
        a_start = a_pos
        b_start = b_pos
        while a_pos < a_len and a[a_pos] != '.' and a[a_pos] != '[':
            a_pos += 1
        while b_pos < b_len and b[b_pos] != '.' and b[b_pos] != '[':
            b_pos += 1

        a_seg_len = a_pos - a_start
        b_seg_len = b_pos - b_start
        min_len = min(a_seg_len, b_seg_len)
        for i in range(min_len):
            ac = ord(a[a_start + i])
            bc = ord(b[b_start + i])
            if ac != bc:
                return -1 if ac < bc else 1
        if a_seg_len != b_seg_len:
            return -1 if a_seg_len < b_seg_len else 1

    return -1 if a_len < b_len else (1 if a_len > b_len else 0)


def _format_canonical_assignment(
    path: str,
    value: OdinValue,
    modifiers: Optional[OdinModifiers] = None,
) -> str:
    """Format a single assignment in canonical form."""
    return f'{path} = {format_modifier_prefix(modifiers)}{_format_canonical_value(value)}'


def _format_canonical_value(value: OdinValue) -> str:
    """Format a value in canonical form."""
    if isinstance(value, OdinNull):
        return '~'

    if isinstance(value, OdinBoolean):
        return 'true' if value.value else 'false'

    if isinstance(value, OdinString):
        return f'"{escape_odin_string(value.value, canonical=True)}"'

    if isinstance(value, OdinNumber):
        return f'#{_format_canonical_number(value.value)}'

    if isinstance(value, OdinInteger):
        return f'##{value.value}'

    if isinstance(value, OdinCurrency):
        dp = max(value.decimal_places, 2)
        # Format with exact decimal places
        fmt = f'{{:.{dp}f}}'
        num_str = fmt.format(float(value.value))
        result = f'#${num_str}'
        if value.currency_code:
            result += f':{value.currency_code.upper()}'
        return result

    if isinstance(value, OdinPercent):
        if value.raw is not None:
            return f'#%{value.raw}'
        return f'#%{value.value}'

    if isinstance(value, OdinDate):
        return value.raw

    if isinstance(value, OdinTimestamp):
        return value.raw

    if isinstance(value, OdinTime):
        return value.value

    if isinstance(value, OdinDuration):
        return value.value

    if isinstance(value, OdinReference):
        return f'@{value.path}'

    if isinstance(value, OdinBinary):
        return format_binary(value)

    if isinstance(value, OdinVerbExpression):
        return _format_canonical_verb(value)

    if isinstance(value, OdinArray):
        return '[]'

    if isinstance(value, OdinObject):
        return '{}'

    return ''


def _format_canonical_number(value: float) -> str:
    """Format number stripping trailing zeros."""
    if not isinstance(value, (int, float)) or not (value == value):  # NaN check
        raise ValueError('Non-finite numbers cannot be canonicalized')

    s = str(value)

    # Strip trailing zeros from decimal part (but not from scientific notation)
    if '.' in s and 'e' not in s and 'E' not in s:
        s = s.rstrip('0').rstrip('.')

    return s


def _format_canonical_verb(value: OdinVerbExpression) -> str:
    """Format verb expression in canonical form."""
    prefix = '%&' if value.is_custom else '%'
    result = f'{prefix}{value.verb}'
    for arg in value.args:
        result += ' ' + _format_canonical_verb_arg(arg)
    return result


def _format_canonical_verb_arg(value: OdinValue) -> str:
    """Format a verb argument in canonical form."""
    if isinstance(value, OdinReference):
        return f'@{value.path}'
    if isinstance(value, OdinString):
        return f'"{escape_odin_string(value.value, canonical=True)}"'
    if isinstance(value, OdinVerbExpression):
        return _format_canonical_verb(value)
    if isinstance(value, OdinNumber):
        if value.raw is not None:
            return f'#{value.raw}'
        return f'#{_format_canonical_number(value.value)}'
    if isinstance(value, OdinInteger):
        return f'##{value.value}'
    if isinstance(value, OdinCurrency):
        if value.raw is not None:
            num_str = value.raw
        else:
            fmt = f'{{:.{value.decimal_places}f}}'
            num_str = fmt.format(float(value.value))
        result = f'#${num_str}'
        if value.currency_code:
            result += f':{value.currency_code}'
        return result
    if isinstance(value, OdinPercent):
        if value.raw is not None:
            return f'#%{value.raw}'
        return f'#%{value.value}'
    if isinstance(value, OdinBoolean):
        return 'true' if value.value else 'false'
    if isinstance(value, OdinNull):
        return '~'
    return _format_canonical_value(value)
