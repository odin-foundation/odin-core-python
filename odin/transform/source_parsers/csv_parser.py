"""CSV source parser - converts CSV string to DynValue array of objects."""

from __future__ import annotations

import re
from typing import List, Optional

from odin.transform.dyn_value import DynValue


def parse_csv(
    source: str,
    delimiter: str = ",",
    has_header: bool = True,
) -> DynValue:
    """Parse CSV input to DynValue tree.

    Args:
        source: CSV string
        delimiter: Field delimiter (default: comma)
        has_header: Whether first row is header (default: True)

    Returns:
        DynValue array of objects (with header) or array of arrays (without)
    """
    if not source.strip():
        return DynValue.of_array([])

    rows = _split_rows(source, delimiter)
    if not rows:
        return DynValue.of_array([])

    if has_header:
        headers = rows[0]
        data_rows = rows[1:]
        result = []
        for row in data_rows:
            obj = {}
            for i, header in enumerate(headers):
                val = row[i] if i < len(row) else ""
                obj[header] = _infer_type(val)
            result.append(DynValue.of_object(obj))
        dv = DynValue.of_array(result)
    else:
        result = []
        for row in rows:
            arr = [_infer_type(v) for v in row]
            result.append(DynValue.of_array(arr))
        dv = DynValue.of_array(result)

    # Stash raw source for multi-record discriminator access
    dv._raw_source = source
    return dv


def _split_rows(source: str, delimiter: str) -> List[List[str]]:
    """Split CSV into rows and fields, handling quotes."""
    rows: List[List[str]] = []
    current_row: List[str] = []
    current_field: List[str] = []
    in_quotes = False
    i = 0
    chars = source

    while i < len(chars):
        ch = chars[i]

        if in_quotes:
            if ch == '"':
                if i + 1 < len(chars) and chars[i + 1] == '"':
                    current_field.append('"')
                    i += 2
                    continue
                else:
                    in_quotes = False
                    i += 1
                    continue
            else:
                current_field.append(ch)
                i += 1
                continue

        if ch == '"':
            in_quotes = True
            i += 1
            continue

        if ch == delimiter:
            current_row.append("".join(current_field))
            current_field = []
            i += 1
            continue

        if ch == '\r':
            if i + 1 < len(chars) and chars[i + 1] == '\n':
                i += 1
            current_row.append("".join(current_field))
            current_field = []
            if current_row != [''] or len(current_row) > 1:
                rows.append(current_row)
            current_row = []
            i += 1
            continue

        if ch == '\n':
            current_row.append("".join(current_field))
            current_field = []
            if current_row != [''] or len(current_row) > 1:
                rows.append(current_row)
            current_row = []
            i += 1
            continue

        current_field.append(ch)
        i += 1

    # Handle last field/row
    if current_field or current_row:
        current_row.append("".join(current_field))
        if current_row != [''] or len(current_row) > 1:
            rows.append(current_row)

    return rows


def _infer_type(value: str) -> DynValue:
    """Infer the DynValue type from a string value."""
    if not value:
        return DynValue.of_null()

    lower = value.lower()
    if lower == "true":
        return DynValue.of_bool(True)
    if lower == "false":
        return DynValue.of_bool(False)
    if lower == "null":
        return DynValue.of_null()

    # Try integer
    try:
        return DynValue.of_integer(int(value))
    except ValueError:
        pass

    # Try float (only if contains ., e, E)
    if '.' in value or 'e' in value or 'E' in value:
        try:
            return DynValue.of_float(float(value))
        except ValueError:
            pass

    return DynValue.of_string(value)
