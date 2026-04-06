"""CSV formatter - converts DynValue array of objects to CSV string."""

from __future__ import annotations

from typing import List, Optional, Set

from odin.transform.dyn_value import DynValue, DynType


def format_csv(
    value: DynValue,
    delimiter: str = ",",
    include_header: bool = True,
) -> str:
    """Format a DynValue (array of objects) as a CSV string.

    Args:
        value: DynValue array of objects
        delimiter: Field delimiter
        include_header: Whether to include header row

    Returns:
        CSV string
    """
    if not value.is_array():
        # If it's an object, look for the first array child
        if value.is_object():
            for k, v in value.as_object().items():
                if v.is_array():
                    value = v
                    break
            else:
                return ""
        else:
            return ""

    items = value.as_array()
    if not items:
        return ""

    # Collect all column names in order
    columns: List[str] = []
    seen: Set[str] = set()
    for item in items:
        if item.is_object():
            for key in item.as_object():
                if key not in seen:
                    seen.add(key)
                    columns.append(key)

    if not columns:
        return ""

    parts: List[str] = []
    if include_header:
        parts.append(delimiter.join(_escape(c, delimiter) for c in columns))

    for item in items:
        if item.is_object():
            obj = item.as_object()
            fields = []
            for col in columns:
                val = obj.get(col)
                text = _format_value(val) if val else ""
                fields.append(_escape(text, delimiter))
            parts.append(delimiter.join(fields))

    return "\n".join(parts) + "\n"


def _format_value(value: Optional[DynValue]) -> str:
    """Convert a DynValue to its string representation for CSV."""
    if value is None or value.is_null():
        return ""
    if value.type == DynType.BOOL:
        return "true" if value.as_bool() else "false"
    if value.type == DynType.INTEGER:
        return str(value.as_int())
    if value.type in (DynType.FLOAT, DynType.FLOAT_RAW):
        if value.type == DynType.FLOAT_RAW:
            raw = value.as_string()
            if raw:
                return raw
        v = value.as_float()
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        return str(v)
    if value.type in (DynType.CURRENCY, DynType.CURRENCY_RAW):
        if value.type == DynType.CURRENCY_RAW:
            raw = value.as_string()
            if raw:
                return raw
        v = value.as_float()
        if v is not None:
            dp = value.get_decimal_places() if hasattr(value, 'get_decimal_places') else None
            if dp is not None and dp > 0:
                return f"{v:.{dp}f}"
            if v == int(v) and abs(v) < 1e15:
                return str(int(v))
            return str(v)
        return "0"
    if value.type == DynType.PERCENT:
        v = value.as_float()
        if v is not None:
            if v == int(v) and abs(v) < 1e15:
                return str(int(v))
            return str(v)
        return "0"
    return value.as_string()


def _escape(value: str, delimiter: str) -> str:
    """Escape a CSV field value."""
    if not value:
        return value
    needs_quote = delimiter in value or '"' in value or '\n' in value or '\r' in value
    if needs_quote:
        return '"' + value.replace('"', '""') + '"'
    return value
