"""Flat KVP source parser - converts key=value pairs to DynValue tree."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple, Union

from odin.transform.dyn_value import DynValue


def parse_flat(source: str) -> DynValue:
    """Parse flat key=value pairs to DynValue tree.

    Supports:
        - Dot notation: person.name = John
        - Array indices: items[0] = a
        - Mixed: employees[0].name = John
        - Comments: # or ; at line start
        - Quoted strings: "value"
        - Type inference: bool, null, int, float, string

    Args:
        source: Flat KVP string

    Returns:
        DynValue object with nested structure
    """
    if not source.strip():
        return DynValue.of_object({})

    root = DynValue.of_object({})

    for line in source.split('\n'):
        line = line.rstrip('\r').strip()
        if not line or line.startswith('#') or line.startswith(';'):
            continue

        # Split on first = (but not inside brackets)
        eq_pos = _find_equals(line)
        if eq_pos < 0:
            continue

        key = line[:eq_pos].strip()
        value_str = line[eq_pos + 1:].strip()

        if not key:
            continue

        parsed_value = _infer_type(value_str)
        segments = _parse_path(key)
        _set_path(root, segments, parsed_value)

    return root


def _find_equals(line: str) -> int:
    """Find the first = sign not inside brackets."""
    depth = 0
    in_quote = False
    quote_char = ''
    for i, ch in enumerate(line):
        if in_quote:
            if ch == quote_char:
                in_quote = False
            continue
        if ch in ('"', "'"):
            in_quote = True
            quote_char = ch
            continue
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
        elif ch == '=' and depth == 0:
            return i
    return -1


def _parse_path(path: str) -> List[Union[str, int]]:
    """Parse a dot/bracket path into segments."""
    segments: List[Union[str, int]] = []
    current: List[str] = []

    i = 0
    while i < len(path):
        ch = path[i]
        if ch == '.':
            if current:
                segments.append("".join(current))
                current = []
            i += 1
        elif ch == '[':
            if current:
                segments.append("".join(current))
                current = []
            # Read index
            i += 1
            idx_chars: List[str] = []
            while i < len(path) and path[i] != ']':
                idx_chars.append(path[i])
                i += 1
            if i < len(path):
                i += 1  # skip ]
            idx_str = "".join(idx_chars)
            try:
                segments.append(int(idx_str))
            except ValueError:
                segments.append(idx_str)
            # Skip dot after bracket
            if i < len(path) and path[i] == '.':
                i += 1
        else:
            current.append(ch)
            i += 1

    if current:
        segments.append("".join(current))

    return segments


def _set_path(root: DynValue, segments: List[Union[str, int]], value: DynValue):
    """Set a value at a nested path, creating containers as needed."""
    current = root
    for i, seg in enumerate(segments[:-1]):
        next_seg = segments[i + 1]
        if isinstance(seg, str):
            obj = current.as_object()
            if seg not in obj:
                if isinstance(next_seg, int):
                    obj[seg] = DynValue.of_array([])
                else:
                    obj[seg] = DynValue.of_object({})
            current = obj[seg]
        elif isinstance(seg, int):
            arr = current.as_array()
            while len(arr) <= seg:
                arr.append(DynValue.of_null())
            if arr[seg].is_null():
                if isinstance(next_seg, int):
                    arr[seg] = DynValue.of_array([])
                else:
                    arr[seg] = DynValue.of_object({})
            current = arr[seg]
            # Update the array reference
            current._array_value = current.as_array() if current.is_array() else None

    last = segments[-1]
    if isinstance(last, str):
        current.as_object()[last] = value
    elif isinstance(last, int):
        arr = current.as_array()
        while len(arr) <= last:
            arr.append(DynValue.of_null())
        arr[last] = value


def _infer_type(value: str) -> DynValue:
    """Infer the DynValue type from a string value."""
    if not value:
        return DynValue.of_null()

    # Null
    if value == '~' or value.lower() == 'null':
        return DynValue.of_null()

    # Quoted string
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        return DynValue.of_string(value[1:-1])

    # Boolean
    lower = value.lower()
    if lower == 'true':
        return DynValue.of_bool(True)
    if lower == 'false':
        return DynValue.of_bool(False)

    # Integer
    try:
        return DynValue.of_integer(int(value))
    except ValueError:
        pass

    # Float
    if '.' in value or 'e' in value or 'E' in value:
        try:
            return DynValue.of_float(float(value))
        except ValueError:
            pass

    return DynValue.of_string(value)
