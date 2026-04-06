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


def check_bounds(value: Any, constraint: BoundsConstraint) -> bool:
    """Check if a value satisfies a bounds constraint."""
    if value is None:
        return True  # Null values are handled by required check

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
