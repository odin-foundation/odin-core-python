"""Coercion verbs: coerceString, coerceNumber, coerceInteger, coerceBoolean, coerceDate, etc."""

from __future__ import annotations

import math
import re
from typing import List

from odin.transform.dyn_value import DynValue, DynType
from odin.transform.verbs.helpers import coerce_str, coerce_num, is_truthy, numeric_result


def verb_coerce_string(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    if args[0].is_null():
        return DynValue.of_null()
    return DynValue.of_string(coerce_str(args[0]))


def verb_coerce_number(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    if args[0].is_null():
        return DynValue.of_null()
    n = coerce_num(args[0])
    if n is None:
        return DynValue.of_null()
    return numeric_result(n)


def verb_coerce_integer(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    if args[0].is_null():
        return DynValue.of_null()
    n = coerce_num(args[0])
    if n is None:
        return DynValue.of_null()
    return DynValue.of_integer(int(n))


def verb_coerce_boolean(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    v = args[0]
    if v.is_null():
        return DynValue.of_null()
    if v.type == DynType.BOOL:
        return v
    if v.type == DynType.INTEGER:
        return DynValue.of_bool(v._int_value != 0)
    if v.type in (DynType.FLOAT, DynType.CURRENCY, DynType.PERCENT):
        return DynValue.of_bool(v._float_value != 0.0)
    if v.type == DynType.STRING:
        s = (v._string_value or "").strip().lower()
        if s in ("false", "0", "no", "n", "off", ""):
            return DynValue.of_bool(False)
        return DynValue.of_bool(True)
    return DynValue.of_bool(is_truthy(v))


def verb_coerce_date(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    v = args[0]
    if v.is_null():
        return DynValue.of_null()
    if v.type == DynType.DATE:
        return v
    if v.type == DynType.TIMESTAMP:
        # Extract date part
        s = v._string_value or ""
        if "T" in s:
            s = s[:s.index("T")]
        dv = DynValue(DynType.DATE)
        dv._string_value = s
        return dv

    s = coerce_str(v)
    if not s:
        return DynValue.of_null()

    # Try yyyy-MM-dd
    if _is_valid_date_prefix(s):
        dv = DynValue(DynType.DATE)
        dv._string_value = s[:10]
        return dv

    # Try numeric (epoch seconds)
    try:
        epoch = float(s)
        from datetime import datetime, timezone
        threshold = 100_000_000_000
        if abs(epoch) < threshold:
            dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
        else:
            dt = datetime.fromtimestamp(epoch / 1000, tz=timezone.utc)
        dv = DynValue(DynType.DATE)
        dv._string_value = dt.strftime("%Y-%m-%d")
        return dv
    except (ValueError, OverflowError, OSError):
        pass

    return DynValue.of_null()


def verb_coerce_timestamp(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    v = args[0]
    if v.is_null():
        return DynValue.of_null()
    if v.type == DynType.TIMESTAMP:
        return v
    if v.type == DynType.DATE:
        s = v._string_value or ""
        dv = DynValue(DynType.TIMESTAMP)
        dv._string_value = s + "T00:00:00"
        return dv

    s = coerce_str(v)
    if not s:
        return DynValue.of_null()

    # Check for ISO timestamp with T
    if "T" in s and _is_valid_date_prefix(s):
        dv = DynValue(DynType.TIMESTAMP)
        dv._string_value = s
        return dv

    # Check plain date
    if _is_valid_date_prefix(s):
        dv = DynValue(DynType.TIMESTAMP)
        dv._string_value = s[:10] + "T00:00:00"
        return dv

    return DynValue.of_null()


def verb_try_coerce(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    v = args[0]
    if v.is_null():
        return v
    # Non-string types pass through
    if v.type != DynType.STRING:
        return v

    s = (v._string_value or "").strip()
    if not s:
        return v

    # Try boolean
    sl = s.lower()
    if sl == "true":
        return DynValue.of_bool(True)
    if sl == "false":
        return DynValue.of_bool(False)

    # Try integer
    try:
        iv = int(s)
        return DynValue.of_integer(iv)
    except ValueError:
        pass

    # Try float
    try:
        fv = float(s)
        if not math.isnan(fv) and not math.isinf(fv):
            return numeric_result(fv)
    except ValueError:
        pass

    # Try date
    if _is_valid_date_prefix(s):
        if "T" in s:
            dv = DynValue(DynType.TIMESTAMP)
            dv._string_value = s
            return dv
        else:
            dv = DynValue(DynType.DATE)
            dv._string_value = s[:10]
            return dv

    return v


def verb_to_array(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_array([])
    v = args[0]
    if v.is_null():
        return DynValue.of_array([])
    if v.is_array():
        return v
    return DynValue.of_array([v])


def verb_to_object(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    v = args[0]
    if v.is_null():
        return DynValue.of_null()
    if v.is_object():
        return v
    if v.is_array():
        result = {}
        for item in v.as_array():
            if item.is_array():
                arr = item.as_array()
                if len(arr) >= 2:
                    key = coerce_str(arr[0])
                    result[key] = arr[1]
            elif item.is_object():
                obj = item.as_object()
                key_v = obj.get("key")
                val_v = obj.get("value")
                if key_v is not None:
                    key = coerce_str(key_v)
                    result[key] = val_v if val_v is not None else DynValue.of_null()
        if result:
            return DynValue.of_object(result)
    return DynValue.of_null()


def _is_valid_date_prefix(s: str) -> bool:
    """Check if a string starts with yyyy-MM-dd format."""
    if len(s) < 10:
        return False
    return (s[4] == "-" and s[7] == "-"
            and s[0:4].isdigit() and s[5:7].isdigit() and s[8:10].isdigit())
