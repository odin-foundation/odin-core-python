"""JSON formatter - converts DynValue tree to JSON string."""

from __future__ import annotations

import json
import math
from typing import Any, Optional

from odin.transform.dyn_value import DynValue, DynType


def format_json(
    value: DynValue,
    indent: Optional[int] = None,
    omit_nulls: bool = False,
    omit_empty_arrays: bool = False,
) -> str:
    """Format a DynValue tree as a JSON string.

    Args:
        value: The DynValue to format
        indent: JSON indentation (None for compact, 0 for minified)
        omit_nulls: If True, recursively remove null-valued keys
        omit_empty_arrays: If True, recursively remove empty array properties

    Returns:
        JSON string
    """
    converted = _to_python(value)
    if omit_nulls or omit_empty_arrays:
        converted = _strip(converted, omit_nulls, omit_empty_arrays)
    if indent == 0:
        return json.dumps(converted, separators=(",", ":"), ensure_ascii=False)
    return json.dumps(converted, indent=indent, ensure_ascii=False)


def _strip(obj: Any, omit_nulls: bool, omit_empty_arrays: bool) -> Any:
    """Recursively strip nulls and/or empty arrays from a Python object."""
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if omit_nulls and v is None:
                continue
            v = _strip(v, omit_nulls, omit_empty_arrays)
            if omit_empty_arrays and isinstance(v, list) and len(v) == 0:
                continue
            result[k] = v
        return result
    if isinstance(obj, list):
        return [_strip(item, omit_nulls, omit_empty_arrays) for item in obj]
    return obj


def _to_python(value: DynValue) -> Any:
    """Convert DynValue to Python native types for json.dumps."""
    if value.type == DynType.NULL:
        return None
    if value.type == DynType.BOOL:
        return value.as_bool()
    if value.type == DynType.INTEGER:
        return value.as_int()
    if value.type == DynType.FLOAT:
        v = value.as_float()
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    if value.type == DynType.FLOAT_RAW:
        try:
            return float(value.as_string())
        except ValueError:
            return value.as_string()
    if value.type == DynType.STRING:
        return value.as_string()
    if value.type == DynType.ARRAY:
        return [_to_python(item) for item in value.as_array()]
    if value.type == DynType.OBJECT:
        return {k: _to_python(v) for k, v in value.as_object().items()}
    if value.type in (DynType.CURRENCY, DynType.PERCENT):
        v = value.as_float()
        if v == int(v) and abs(v) < 1e15:
            return int(v)
        return v
    if value.type == DynType.REFERENCE:
        return f"@{value.as_string()}"
    if value.type == DynType.BINARY:
        return value.as_string()
    # Date, Timestamp, Time, Duration: return string
    return value.as_string()
