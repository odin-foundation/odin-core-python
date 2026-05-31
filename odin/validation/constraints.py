"""Constraint evaluation for ODIN schema validation."""
from __future__ import annotations

import re
from typing import Any, Optional, Union

from odin.types.schema import (
    BoundsConstraint,
    PatternConstraint,
    EnumConstraint,
    FormatConstraint,
)


_TEMPORAL_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}([T ][0-9:.+\-Zz]+)?$|^\d{2}:\d{2}(:\d{2})?$"
)


def check_bounds(value: Any, constraint: BoundsConstraint) -> bool:
    """Check if a value satisfies a bounds constraint."""
    if value is None:
        return True  # Null values are handled by required check

    # Temporal bounds: compare ISO literals chronologically.
    if _is_temporal_bound(constraint):
        v = _temporal_key(value)
        if v is None:
            return True
        if constraint.min is not None:
            mn = _temporal_key(constraint.min)
            if mn is not None and v < mn:
                return False
        if constraint.max is not None:
            mx = _temporal_key(constraint.max)
            if mx is not None and v > mx:
                return False
        return True

    # For strings, check length
    if isinstance(value, str):
        length = len(value)
        if constraint.min is not None and length < _to_number(constraint.min):
            return False
        if constraint.max is not None and length > _to_number(constraint.max):
            return False
        return True

    # For numbers
    num = _to_number(value)
    if num is None:
        return True
    if constraint.min is not None:
        min_val = _to_number(constraint.min)
        if min_val is not None and num < min_val:
            return False
    if constraint.max is not None:
        max_val = _to_number(constraint.max)
        if max_val is not None and num > max_val:
            return False
    return True


def check_pattern(value: Any, constraint: PatternConstraint) -> bool:
    """Check if a value matches a pattern constraint."""
    if value is None:
        return True
    s = str(value)
    try:
        return bool(re.search(constraint.pattern, s))
    except re.error:
        return True  # Invalid pattern - don't fail validation


def check_enum(value: Any, values: list) -> bool:
    """Check if a value is in an enumeration."""
    if value is None:
        return True
    return str(value) in values


def check_format(value: Any, format_name: str) -> bool:
    """Check if a value matches a format constraint."""
    if value is None:
        return True
    s = str(value)

    if format_name == "email":
        return bool(re.match(r'^[^@]+@[^@]+\.[^@]+$', s))
    if format_name == "url" or format_name == "uri":
        return s.startswith("http://") or s.startswith("https://")
    if format_name == "uuid":
        return bool(re.match(
            r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$', s
        ))
    if format_name == "ipv4":
        parts = s.split(".")
        if len(parts) != 4:
            return False
        return all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)

    return True  # Unknown format - pass


def _is_temporal_bound(constraint: BoundsConstraint) -> bool:
    """A bound is temporal when either edge is an ISO date/time/timestamp literal."""
    for edge in (constraint.min, constraint.max):
        if isinstance(edge, str) and _TEMPORAL_RE.match(edge.strip()):
            return True
    return False


def _temporal_key(value: Any) -> Optional[str]:
    """Normalize a temporal value to a comparable ISO string."""
    from datetime import date, datetime

    if isinstance(value, (date, datetime)):
        return value.isoformat()
    s = str(value).strip()
    return s if s else None


def _to_number(value: Any) -> Optional[Union[int, float]]:
    """Convert a value to a number."""
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return None
    return None
