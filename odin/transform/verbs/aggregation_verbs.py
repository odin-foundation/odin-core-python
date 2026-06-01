"""Aggregation verbs for the ODIN transform engine."""

from __future__ import annotations

from typing import List, Optional

import math

from odin.transform.dyn_value import DynValue, DynType
from odin.transform.verbs.helpers import coerce_num, coerce_str, numeric_result
from odin.transform.errors import accumulator_overflow_error

# Largest integer magnitude representable without precision loss (2^53 - 1).
_MAX_SAFE_INTEGER = (1 << 53) - 1


def _extract_items(v: DynValue) -> Optional[List[DynValue]]:
    """Extract items from array or return None."""
    if v.is_array():
        return v.as_array()
    return None


def _to_double(v: DynValue) -> Optional[float]:
    return coerce_num(v)


# ── Verb implementations ────────────────────────────────────────────

def verb_sum(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_integer(0)
    # If first arg is array, sum its elements
    if args[0].is_array():
        items = args[0].as_array()
    else:
        items = args
    total = 0.0
    has_value = False
    for item in items:
        n = _to_double(item)
        if n is not None:
            total += n
            has_value = True
    if not has_value:
        return DynValue.of_integer(0)
    return numeric_result(total)


def verb_count(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_integer(0)
    if args[0].is_array():
        items = args[0].as_array()
        # Count non-null items
        count = sum(1 for item in items if not item.is_null())
        return DynValue.of_integer(count)
    return DynValue.of_integer(len(args))


def verb_min(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    if args[0].is_array():
        items = args[0].as_array()
    else:
        items = args
    result = None
    for item in items:
        n = _to_double(item)
        if n is not None:
            if result is None or n < result:
                result = n
    if result is None:
        return DynValue.of_null()
    return numeric_result(result)


def verb_max(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    if args[0].is_array():
        items = args[0].as_array()
    else:
        items = args
    result = None
    for item in items:
        n = _to_double(item)
        if n is not None:
            if result is None or n > result:
                result = n
    if result is None:
        return DynValue.of_null()
    return numeric_result(result)


def verb_avg(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    if args[0].is_array():
        items = args[0].as_array()
    else:
        items = args
    total = 0.0
    count = 0
    for item in items:
        n = _to_double(item)
        if n is not None:
            total += n
            count += 1
    if count == 0:
        return DynValue.of_null()
    return numeric_result(total / count)


def verb_first(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    if args[0].is_array():
        items = args[0].as_array()
        return items[0] if items else DynValue.of_null()
    return args[0]


def verb_last(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    if args[0].is_array():
        items = args[0].as_array()
        return items[-1] if items else DynValue.of_null()
    return args[-1]


def verb_accumulate(args: List[DynValue], ctx: object) -> DynValue:
    """Add to accumulator. accumulate(name, value) or accumulate(name, verb, value)."""
    if len(args) < 2:
        return DynValue.of_null()
    name = coerce_str(args[0])
    if not name:
        return DynValue.of_null()

    accs = getattr(ctx, 'accumulators', None)
    if accs is None:
        return DynValue.of_null()

    if len(args) >= 3:
        verb_name = coerce_str(args[1])
        value = args[2]
    else:
        verb_name = "sum"
        value = args[1]

    current = accs.get(name)
    n = _to_double(value)

    if verb_name == "sum":
        cur_n = _to_double(current) if current else 0.0
        if cur_n is None:
            cur_n = 0.0
        new_val = (cur_n or 0.0) + (n or 0.0)
        # T008: the running sum is no longer exactly representable (non-finite,
        # or an integer accumulator beyond safe-integer magnitude). Retain the
        # last valid value.
        integer_accumulator = current is not None and current.type == DynType.INTEGER
        if (not math.isfinite(new_val)
                or (integer_accumulator and abs(new_val) > _MAX_SAFE_INTEGER)):
            errors = getattr(ctx, "errors", None)
            if errors is not None:
                errors.append(accumulator_overflow_error(name, new_val))
            return current if current is not None else DynValue.of_null()
        result = numeric_result(new_val)
    elif verb_name == "count":
        cur_n = _to_double(current) if current else 0.0
        result = numeric_result((cur_n or 0.0) + 1)
    elif verb_name == "min":
        if current is None or current.is_null():
            result = value
        else:
            cur_n = _to_double(current)
            if n is not None and cur_n is not None and n < cur_n:
                result = value
            else:
                result = current
    elif verb_name == "max":
        if current is None or current.is_null():
            result = value
        else:
            cur_n = _to_double(current)
            if n is not None and cur_n is not None and n > cur_n:
                result = value
            else:
                result = current
    elif verb_name == "first":
        result = current if current and not current.is_null() else value
    elif verb_name == "last":
        result = value
    elif verb_name == "concat":
        if current is None or current.is_null():
            result = DynValue.of_string(coerce_str(value))
        else:
            result = DynValue.of_string(coerce_str(current) + coerce_str(value))
    else:
        # Default sum
        cur_n = _to_double(current) if current else 0.0
        result = numeric_result((cur_n or 0.0) + (n or 0.0))

    accs[name] = result
    return result


def verb_set(args: List[DynValue], ctx: object) -> DynValue:
    """Set accumulator to value."""
    if len(args) < 2:
        return DynValue.of_null()
    name = coerce_str(args[0])
    if not name:
        return DynValue.of_null()
    accs = getattr(ctx, 'accumulators', None)
    if accs is None:
        return DynValue.of_null()
    accs[name] = args[1]
    return args[1]
