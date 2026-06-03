"""Logic verbs: and, or, not, xor, eq, ne, lt, lte, gt, gte, between, isNull, typeOf, cond, etc."""

from __future__ import annotations

import re
from typing import List

from odin.transform.dyn_value import DynValue, DynType
from odin.transform.verbs.helpers import (
    coerce_str, coerce_num, is_truthy, dyn_values_equal, to_f64_for_cmp,
)


def verb_and(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    return DynValue.of_bool(is_truthy(args[0]) and is_truthy(args[1]))


def verb_or(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    return DynValue.of_bool(is_truthy(args[0]) or is_truthy(args[1]))


def verb_not(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    return DynValue.of_bool(not is_truthy(args[0]))


def verb_xor(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    a = is_truthy(args[0])
    b = is_truthy(args[1])
    return DynValue.of_bool((a and not b) or (not a and b))


def verb_eq(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    return DynValue.of_bool(dyn_values_equal(args[0], args[1]))


def verb_ne(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    return DynValue.of_bool(not dyn_values_equal(args[0], args[1]))


def _compare(args: List[DynValue]) -> int | None:
    """Compare two values. Returns <0, 0, >0, or None if incomparable."""
    if len(args) < 2:
        return None
    a, b = args[0], args[1]
    # Try numeric comparison first
    an = to_f64_for_cmp(a)
    bn = to_f64_for_cmp(b)
    if an is not None and bn is not None:
        if an < bn:
            return -1
        if an > bn:
            return 1
        return 0
    # String comparison
    sa = coerce_str(a)
    sb = coerce_str(b)
    if sa < sb:
        return -1
    if sa > sb:
        return 1
    return 0


def verb_lt(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    c = _compare(args)
    return DynValue.of_bool(c is not None and c < 0)


def verb_lte(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    c = _compare(args)
    return DynValue.of_bool(c is not None and c <= 0)


def verb_gt(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    c = _compare(args)
    return DynValue.of_bool(c is not None and c > 0)


def verb_gte(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    c = _compare(args)
    return DynValue.of_bool(c is not None and c >= 0)


def verb_between(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 3:
        return DynValue.of_null()
    val, lo, hi = args[0], args[1], args[2]
    c_lo = _compare([val, lo])
    c_hi = _compare([val, hi])
    if c_lo is None or c_hi is None:
        return DynValue.of_bool(False)
    return DynValue.of_bool(c_lo >= 0 and c_hi <= 0)


def verb_is_null(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    return DynValue.of_bool(args[0].is_null())


def verb_is_string(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    return DynValue.of_bool(args[0].type == DynType.STRING)


def verb_is_number(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    return DynValue.of_bool(args[0].type in (DynType.INTEGER, DynType.FLOAT, DynType.CURRENCY))


def verb_is_boolean(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    return DynValue.of_bool(args[0].type == DynType.BOOL)


def verb_is_array(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    v = args[0]
    if v.type == DynType.ARRAY:
        return DynValue.of_bool(True)
    # String that looks like an array
    if v.type == DynType.STRING:
        s = (v._string_value or "").strip()
        if s.startswith("[") and s.endswith("]"):
            return DynValue.of_bool(True)
    return DynValue.of_bool(False)


def verb_is_object(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    v = args[0]
    if v.type == DynType.OBJECT:
        return DynValue.of_bool(True)
    if v.type == DynType.STRING:
        s = (v._string_value or "").strip()
        if s.startswith("{") and s.endswith("}"):
            return DynValue.of_bool(True)
    return DynValue.of_bool(False)


def verb_is_date(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    v = args[0]
    return DynValue.of_bool(v.type in (DynType.DATE, DynType.TIMESTAMP))


def verb_type_of(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    v = args[0]
    type_map = {
        DynType.NULL: "null",
        DynType.BOOL: "boolean",
        DynType.INTEGER: "integer",
        DynType.FLOAT: "number",
        DynType.FLOAT_RAW: "number",
        DynType.STRING: "string",
        DynType.ARRAY: "array",
        DynType.OBJECT: "object",
        DynType.DATE: "date",
        DynType.TIMESTAMP: "timestamp",
        DynType.TIME: "time",
        DynType.DURATION: "duration",
        DynType.CURRENCY: "currency",
        DynType.CURRENCY_RAW: "currency",
        DynType.PERCENT: "percent",
        DynType.REFERENCE: "reference",
        DynType.BINARY: "binary",
    }
    return DynValue.of_string(type_map.get(v.type, "unknown"))


def verb_cond(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    i = 0
    while i + 1 < len(args):
        if is_truthy(args[i]):
            return args[i + 1]
        i += 2
    # Odd number of args: last is default
    if len(args) % 2 == 1:
        return args[-1]
    return DynValue.of_null()


def verb_assert(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    if is_truthy(args[0]):
        return args[0]
    return DynValue.of_null()


def verb_switch(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 3:
        return DynValue.of_null()
    value = args[0]
    i = 1
    while i + 1 < len(args):
        if dyn_values_equal(value, args[i]):
            return args[i + 1]
        i += 2
    # Odd total args: last is default
    if len(args) % 2 == 0:
        return args[-1]
    return DynValue.of_null()


def verb_is_finite(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    v = args[0]
    if v.type == DynType.INTEGER:
        return DynValue.of_bool(True)
    if v.type == DynType.FLOAT:
        import math
        return DynValue.of_bool(math.isfinite(v._float_value))
    return DynValue.of_bool(False)


def verb_is_nan(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    v = args[0]
    if v.type == DynType.FLOAT:
        import math
        return DynValue.of_bool(math.isnan(v._float_value))
    if v.type == DynType.STRING:
        s = (v._string_value or "").strip().lower()
        return DynValue.of_bool(s == "nan")
    return DynValue.of_bool(False)
