"""Core verbs: concat, upper, lower, trim, coalesce, ifNull, ifEmpty, ifElse, lookup, lookupDefault."""

from __future__ import annotations

from typing import List

from odin.transform.dyn_value import DynValue, DynType
from odin.transform.verbs.helpers import coerce_str, is_truthy
from odin.transform.errors import (
    lookup_key_not_found_error, lookup_key_not_found_warning,
    lookup_table_not_found_error, lookup_table_not_found_warning,
)


def _report_lookup_miss(ctx: object, table_name: str, key: str) -> None:
    """Report a lookup miss honoring the onMissing policy (default: silent null)."""
    policy = getattr(ctx, "on_missing", None)
    if policy == "fail":
        errors = getattr(ctx, "errors", None)
        if errors is not None:
            errors.append(lookup_key_not_found_error(table_name, key))
    elif policy == "warn":
        warnings = getattr(ctx, "warnings", None)
        if warnings is not None:
            warnings.append(lookup_key_not_found_warning(table_name, key))


def _report_table_not_found(ctx: object, table_name: str) -> None:
    """Report a missing lookup table (T003) honoring the onMissing policy.

    Distinct from a missing key (T004): the referenced table was never declared.
    """
    policy = getattr(ctx, "on_missing", None)
    if policy == "fail":
        errors = getattr(ctx, "errors", None)
        if errors is not None:
            errors.append(lookup_table_not_found_error(table_name))
    elif policy == "warn":
        warnings = getattr(ctx, "warnings", None)
        if warnings is not None:
            warnings.append(lookup_table_not_found_warning(table_name))


def verb_concat(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_string("")
    parts = []
    for a in args:
        if a.is_null():
            parts.append("")
        else:
            parts.append(coerce_str(a))
    return DynValue.of_string("".join(parts))


def verb_upper(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    return DynValue.of_string(coerce_str(args[0]).upper())


def verb_lower(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    return DynValue.of_string(coerce_str(args[0]).lower())


def verb_trim(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    return DynValue.of_string(coerce_str(args[0]).strip())


def verb_trim_left(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    return DynValue.of_string(coerce_str(args[0]).lstrip())


def verb_trim_right(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    return DynValue.of_string(coerce_str(args[0]).rstrip())


def verb_coalesce(args: List[DynValue], ctx: object) -> DynValue:
    for a in args:
        if not a.is_null():
            # Skip empty strings too
            if a.type == DynType.STRING and (a._string_value or "") == "":
                continue
            return a
    return DynValue.of_null()


def verb_if_null(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    return args[1] if args[0].is_null() else args[0]


def verb_if_empty(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    v = args[0]
    if v.is_null():
        return args[1]
    if v.type == DynType.STRING and (v._string_value or "") == "":
        return args[1]
    return args[0]


def verb_if_else(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 3:
        return DynValue.of_null()
    return args[1] if is_truthy(args[0]) else args[2]


def verb_lookup(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    return _do_lookup(args, ctx, None)


def verb_lookup_default(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 3:
        return DynValue.of_null()
    default_val = args[-1]
    lookup_args = args[:-1]
    result = _do_lookup(lookup_args, ctx, default_val)
    return result


def _row_val_to_str(val) -> str:
    """Extract a string from a table row value (DynValue or OdinValue)."""
    if isinstance(val, DynValue):
        return coerce_str(val)
    # OdinValue types have a .value attribute
    if hasattr(val, "value"):
        return str(val.value)
    return str(val)


def _row_val_to_dyn(val) -> DynValue:
    """Convert a table row value to DynValue."""
    if isinstance(val, DynValue):
        return val
    if hasattr(val, "value"):
        v = val.value
        if isinstance(v, bool):
            return DynValue.of_bool(v)
        if isinstance(v, int):
            return DynValue.of_integer(v)
        if isinstance(v, float):
            return DynValue.of_float(v)
        if isinstance(v, str):
            return DynValue.of_string(v)
    return DynValue.of_string(_row_val_to_str(val))


def _do_lookup(args: List[DynValue], ctx: object, default: DynValue | None) -> DynValue:
    """Perform a table lookup.

    Two modes:
      1. Key-based: %lookup TABLE.returnCol keyVal1 keyVal2 ...
         Search by all non-return columns.
      2. Reverse:   %lookup TABLE.returnCol "searchCol" "searchVal"
         When 2 extra args are given and the first names a column in the table,
         search that specific column for the value.
    """
    table_ref = coerce_str(args[0])
    if "." not in table_ref:
        return default if default is not None else DynValue.of_null()

    table_name, col_name = table_ref.split(".", 1)
    keys = args[1:]
    match_key = ", ".join(coerce_str(k) for k in keys)

    tables = getattr(ctx, "tables", {})
    table = tables.get(table_name)
    if table is None:
        if default is None:
            _report_table_not_found(ctx, table_name)
        return default if default is not None else DynValue.of_null()

    columns = getattr(table, "columns", [])
    rows = getattr(table, "rows", [])

    # Find the return column index
    return_idx = -1
    for i, col in enumerate(columns):
        if col == col_name:
            return_idx = i
            break
    if return_idx < 0:
        if default is None:
            _report_lookup_miss(ctx, table_name, match_key)
        return default if default is not None else DynValue.of_null()

    # Check for reverse lookup: 2 extra args where first arg names a column
    if len(keys) == 2:
        search_col_name = coerce_str(keys[0])
        search_col_idx = -1
        for i, col in enumerate(columns):
            if col == search_col_name:
                search_col_idx = i
                break
        if search_col_idx >= 0:
            # Reverse lookup: search by named column
            search_val = coerce_str(keys[1])
            for row in rows:
                if len(row) != len(columns):
                    continue
                row_str = _row_val_to_str(row[search_col_idx])
                if row_str == search_val:
                    return _row_val_to_dyn(row[return_idx])
            if default is None:
                _report_lookup_miss(ctx, table_name, match_key)
            return default if default is not None else DynValue.of_null()

    # Key-based lookup: key columns = all columns except the return column
    key_col_indices = [i for i in range(len(columns)) if i != return_idx]

    for row in rows:
        if len(row) != len(columns):
            continue
        match = True
        for ki, kci in enumerate(key_col_indices):
            if ki >= len(keys):
                match = False
                break
            row_str = _row_val_to_str(row[kci])
            key_val = coerce_str(keys[ki])
            if row_str != key_val:
                match = False
                break
        if match:
            return _row_val_to_dyn(row[return_idx])

    if default is None:
        _report_lookup_miss(ctx, table_name, match_key)
    return default if default is not None else DynValue.of_null()
