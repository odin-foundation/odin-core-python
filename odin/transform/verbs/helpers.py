"""Shared helpers for verb implementations."""

from __future__ import annotations

import math
import re
from typing import List, Optional

from odin.transform.dyn_value import DynValue, DynType


def coerce_str(v: DynValue) -> str:
    """Convert a DynValue to a string representation."""
    if v.is_null():
        return ""
    if v.type == DynType.STRING:
        return v._string_value or ""
    if v.type == DynType.INTEGER:
        return str(v._int_value)
    if v.type == DynType.FLOAT:
        return _format_double(v._float_value)
    if v.type == DynType.BOOL:
        return "true" if v._bool_value else "false"
    if v.type in (DynType.CURRENCY, DynType.PERCENT):
        return _format_double(v._float_value)
    if v.type in (DynType.FLOAT_RAW, DynType.CURRENCY_RAW):
        return v._string_value or ""
    if v.type in (DynType.DATE, DynType.TIMESTAMP, DynType.TIME,
                  DynType.DURATION, DynType.REFERENCE, DynType.BINARY):
        return v._string_value or ""
    if v.type == DynType.ARRAY:
        arr = v._array_value or []
        return f"[{len(arr)} items]"
    if v.type == DynType.OBJECT:
        return "[object]"
    return ""


def coerce_num(v: DynValue) -> Optional[float]:
    """Convert a DynValue to a float, or None if not convertible."""
    if v.is_null():
        return None
    if v.type == DynType.INTEGER:
        return float(v._int_value)
    if v.type == DynType.FLOAT:
        return v._float_value
    if v.type in (DynType.CURRENCY, DynType.PERCENT):
        return v._float_value
    if v.type in (DynType.FLOAT_RAW, DynType.CURRENCY_RAW):
        try:
            return float(v._string_value or "0")
        except ValueError:
            return None
    if v.type == DynType.BOOL:
        return 1.0 if v._bool_value else 0.0
    if v.type == DynType.STRING:
        try:
            return float(v._string_value or "0")
        except ValueError:
            return None
    return None


def to_number(v: DynValue) -> float:
    """Convert a DynValue to a float, treating null and unparseable as 0."""
    n = coerce_num(v)
    return n if n is not None else 0.0


def to_boolean(v: DynValue) -> bool:
    """Convert a DynValue to bool using strict string semantics."""
    if v.type == DynType.STRING:
        s = (v._string_value or "").lower()
        return s in ("true", "yes", "y", "1")
    if v.is_null():
        return False
    if v.type == DynType.INTEGER:
        return v._int_value != 0
    if v.type in (DynType.FLOAT, DynType.CURRENCY, DynType.PERCENT):
        return v._float_value != 0.0
    if v.type == DynType.BOOL:
        return v._bool_value
    return is_truthy(v)


def coerce_int(v: DynValue) -> Optional[int]:
    """Convert a DynValue to an int, or None."""
    n = coerce_num(v)
    if n is None:
        return None
    return int(math.floor(n))


def coerce_bool(v: DynValue) -> bool:
    """Convert a DynValue to bool using truthiness rules."""
    return is_truthy(v)


def is_truthy(v: DynValue) -> bool:
    """Check if a DynValue is truthy."""
    if v.is_null():
        return False
    if v.type == DynType.BOOL:
        return v._bool_value
    if v.type == DynType.INTEGER:
        return v._int_value != 0
    if v.type == DynType.FLOAT:
        return v._float_value != 0.0
    if v.type in (DynType.CURRENCY, DynType.PERCENT):
        return v._float_value != 0.0
    if v.type in (DynType.FLOAT_RAW, DynType.CURRENCY_RAW):
        s = v._string_value or ""
        return s != "" and s != "0"
    if v.type == DynType.STRING:
        s = v._string_value or ""
        return s != ""
    if v.type in (DynType.DATE, DynType.TIMESTAMP, DynType.TIME,
                  DynType.DURATION, DynType.REFERENCE, DynType.BINARY):
        return (v._string_value or "") != ""
    if v.type == DynType.ARRAY:
        return True
    if v.type == DynType.OBJECT:
        return True
    return False


def is_numeric(v: DynValue) -> bool:
    """Check if a DynValue is numeric."""
    return v.type in (DynType.INTEGER, DynType.FLOAT, DynType.CURRENCY, DynType.PERCENT)


def numeric_result(v: float) -> DynValue:
    """Return Integer for whole numbers, Float otherwise.

    Uses epsilon tolerance for floating-point comparison.
    """
    if math.isnan(v) or math.isinf(v):
        return DynValue.of_float(v)
    rounded = round(v)
    if abs(v - rounded) < 1e-10:
        return DynValue.of_integer(int(rounded))
    return DynValue.of_float(v)


def dyn_values_equal(a: DynValue, b: DynValue) -> bool:
    """Cross-type equality comparison."""
    if a.type == b.type:
        if a.type == DynType.NULL:
            return True
        if a.type == DynType.BOOL:
            return a._bool_value == b._bool_value
        if a.type == DynType.INTEGER:
            return a._int_value == b._int_value
        if a.type == DynType.FLOAT:
            return a._float_value == b._float_value
        if a.type == DynType.STRING:
            return (a._string_value or "") == (b._string_value or "")
    # Both null
    if a.is_null() and b.is_null():
        return True
    # Cross-type numeric
    an = coerce_num(a) if is_numeric(a) else None
    bn = coerce_num(b) if is_numeric(b) else None
    if an is not None and bn is not None:
        return an == bn
    # String-number coercion
    if a.type == DynType.STRING and is_numeric(b):
        try:
            av = float(a._string_value or "")
            bv = coerce_num(b)
            if bv is not None:
                return av == bv
        except ValueError:
            pass
    if b.type == DynType.STRING and is_numeric(a):
        try:
            bv2 = float(b._string_value or "")
            av2 = coerce_num(a)
            if av2 is not None:
                return av2 == bv2
        except ValueError:
            pass
    # Compare as strings
    return coerce_str(a) == coerce_str(b)


def to_f64_for_cmp(v: DynValue) -> Optional[float]:
    """Convert to float for ordering comparison."""
    if v.type == DynType.INTEGER:
        return float(v._int_value)
    if v.type == DynType.FLOAT:
        return v._float_value
    if v.type in (DynType.CURRENCY, DynType.PERCENT):
        return v._float_value
    if v.type in (DynType.FLOAT_RAW, DynType.CURRENCY_RAW):
        try:
            return float(v._string_value or "0")
        except ValueError:
            return None
    if v.type == DynType.STRING:
        try:
            return float(v._string_value or "")
        except ValueError:
            return None
    return None


def _format_double(v: float) -> str:
    """Format a float, showing integers without decimal point."""
    if v == v and abs(v) < 1e15 and v == int(v):
        return str(int(v))
    return str(v)


def split_words(s: str) -> List[str]:
    """Split a string into words by delimiters and case boundaries."""
    if not s:
        return []
    # Replace common delimiters with spaces
    normalized = re.sub(r'[-_\s]+', ' ', s)
    # Boundary between lowercase and following uppercase (camelCase)
    normalized = re.sub(r'([a-z])([A-Z])', r'\1 \2', normalized)
    # Boundary inside acronym followed by a word (PascalCase acronyms)
    normalized = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', normalized)
    return [w for w in re.split(r'\s+', normalized) if w]
