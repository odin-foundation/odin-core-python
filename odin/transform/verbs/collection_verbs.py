"""Collection verbs for the ODIN transform engine."""

from __future__ import annotations

import random
from typing import List, Optional

from odin.transform.dyn_value import DynValue, DynType
from odin.transform.verbs.helpers import (
    coerce_num, coerce_str, dyn_values_equal, is_truthy, numeric_result,
    to_f64_for_cmp,
)


def _extract_array(v: DynValue) -> List[DynValue]:
    """Extract array from DynValue."""
    if v.is_array():
        return list(v.as_array())
    return []


def _get_field(item: DynValue, field: str) -> DynValue:
    """Get a field from an object DynValue, supporting dot notation."""
    if not field:
        return item
    parts = field.split(".")
    current = item
    for part in parts:
        if current.is_object():
            val = current.get(part)
            if val is None:
                return DynValue.of_null()
            current = val
        else:
            return DynValue.of_null()
    return current


def _compare_values(a: DynValue, b: DynValue) -> int:
    """Compare two DynValues for sorting. Nulls last."""
    if a.is_null() and b.is_null():
        return 0
    if a.is_null():
        return 1
    if b.is_null():
        return -1
    an = to_f64_for_cmp(a)
    bn = to_f64_for_cmp(b)
    if an is not None and bn is not None:
        return (an > bn) - (an < bn)
    sa = coerce_str(a)
    sb = coerce_str(b)
    return (sa > sb) - (sa < sb)


def _check_filter_condition(item_val: DynValue, op: str, cmp_val: DynValue) -> bool:
    """Check a filter condition."""
    if op == "=" or op == "==":
        return dyn_values_equal(item_val, cmp_val)
    if op == "!=" or op == "<>":
        return not dyn_values_equal(item_val, cmp_val)
    an = to_f64_for_cmp(item_val)
    bn = to_f64_for_cmp(cmp_val)
    if an is not None and bn is not None:
        if op == "<":
            return an < bn
        if op == "<=":
            return an <= bn
        if op == ">":
            return an > bn
        if op == ">=":
            return an >= bn
    sa = coerce_str(item_val)
    sb = coerce_str(cmp_val)
    if op == "contains":
        return sb in sa
    if op == "startsWith":
        return sa.startswith(sb)
    if op == "endsWith":
        return sa.endswith(sb)
    if op == "<":
        return sa < sb
    if op == "<=":
        return sa <= sb
    if op == ">":
        return sa > sb
    if op == ">=":
        return sa >= sb
    return False


# ── Verb implementations ────────────────────────────────────────────

def verb_filter(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_array([])
    arr = _extract_array(args[0])
    if len(args) >= 4:
        # 4-arg: array, field, op, value
        field = coerce_str(args[1])
        op = coerce_str(args[2])
        cmp_val = args[3]
        result = []
        for item in arr:
            item_val = _get_field(item, field)
            if _check_filter_condition(item_val, op, cmp_val):
                result.append(item)
        return DynValue.of_array(result)
    elif len(args) >= 2:
        # 2-arg: filter by field truthiness
        field = coerce_str(args[1])
        result = []
        for item in arr:
            item_val = _get_field(item, field) if field else item
            if is_truthy(item_val):
                result.append(item)
        return DynValue.of_array(result)
    else:
        # 1-arg: filter truthy
        return DynValue.of_array([item for item in arr if is_truthy(item)])


def verb_flatten(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_array([])
    arr = _extract_array(args[0])
    result: List[DynValue] = []
    for item in arr:
        if item.is_array():
            result.extend(item.as_array())
        else:
            result.append(item)
    return DynValue.of_array(result)


def verb_distinct(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_array([])
    arr = _extract_array(args[0])
    seen: set = set()
    result: List[DynValue] = []
    for item in arr:
        key = coerce_str(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return DynValue.of_array(result)


def verb_unique(args: List[DynValue], ctx: object) -> DynValue:
    return verb_distinct(args, ctx)


def verb_sort(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    arr = _extract_array(args[0])
    import functools
    sorted_arr = sorted(arr, key=functools.cmp_to_key(_compare_values))
    return DynValue.of_array(sorted_arr)


def verb_sort_desc(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    arr = _extract_array(args[0])
    import functools
    sorted_arr = sorted(arr, key=functools.cmp_to_key(lambda a, b: -_compare_values(a, b)))
    return DynValue.of_array(sorted_arr)


def verb_sort_by(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    arr = _extract_array(args[0])
    field = coerce_str(args[1])
    if not field:
        return DynValue.of_array(list(arr))
    import functools
    sorted_arr = sorted(
        arr,
        key=functools.cmp_to_key(lambda a, b: _compare_values(_get_field(a, field), _get_field(b, field)))
    )
    return DynValue.of_array(sorted_arr)


def verb_map(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    arr = _extract_array(args[0])
    if len(args) < 2:
        return DynValue.of_array(list(arr))
    field = coerce_str(args[1])
    if not field:
        return DynValue.of_array(list(arr))
    return DynValue.of_array([_get_field(item, field) for item in arr])


def verb_pluck(args: List[DynValue], ctx: object) -> DynValue:
    return verb_map(args, ctx)


def verb_index_of(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_integer(-1)
    arr = _extract_array(args[0])
    target = args[1]
    for i, item in enumerate(arr):
        if dyn_values_equal(item, target):
            return DynValue.of_integer(i)
    return DynValue.of_integer(-1)


def verb_at(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    arr = _extract_array(args[0])
    idx_num = coerce_num(args[1])
    if idx_num is None:
        return DynValue.of_null()
    idx = int(idx_num)
    if idx < 0:
        idx = len(arr) + idx
    if idx < 0 or idx >= len(arr):
        return DynValue.of_null()
    return arr[idx]


def verb_slice(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_array([])
    arr = _extract_array(args[0])
    start_num = coerce_num(args[1])
    if start_num is None:
        return DynValue.of_array([])
    start = int(start_num)
    if start < 0:
        start = max(0, len(arr) + start)
    end = len(arr)
    if len(args) >= 3:
        end_num = coerce_num(args[2])
        if end_num is not None:
            end = int(end_num)
            if end < 0:
                end = max(0, len(arr) + end)
    start = max(0, min(start, len(arr)))
    end = max(0, min(end, len(arr)))
    return DynValue.of_array(arr[start:end])


def verb_reverse(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    arr = _extract_array(args[0])
    return DynValue.of_array(list(reversed(arr)))


def verb_every(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_bool(True)
    arr = _extract_array(args[0])
    field = coerce_str(args[1]) if len(args) >= 2 else ""
    for item in arr:
        val = _get_field(item, field) if field else item
        if not is_truthy(val):
            return DynValue.of_bool(False)
    return DynValue.of_bool(True)


def verb_some(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_bool(False)
    arr = _extract_array(args[0])
    field = coerce_str(args[1]) if len(args) >= 2 else ""
    for item in arr:
        val = _get_field(item, field) if field else item
        if is_truthy(val):
            return DynValue.of_bool(True)
    return DynValue.of_bool(False)


def verb_find(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    arr = _extract_array(args[0])
    field = coerce_str(args[1]) if len(args) >= 2 else ""
    for item in arr:
        val = _get_field(item, field) if field else item
        if is_truthy(val):
            return item
    return DynValue.of_null()


def verb_find_index(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_integer(-1)
    arr = _extract_array(args[0])
    field = coerce_str(args[1]) if len(args) >= 2 else ""
    for i, item in enumerate(arr):
        val = _get_field(item, field) if field else item
        if is_truthy(val):
            return DynValue.of_integer(i)
    return DynValue.of_integer(-1)


def verb_includes(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_bool(False)
    arr = _extract_array(args[0])
    target = args[1]
    for item in arr:
        if dyn_values_equal(item, target):
            return DynValue.of_bool(True)
    return DynValue.of_bool(False)


def verb_concat_arrays(args: List[DynValue], ctx: object) -> DynValue:
    result: List[DynValue] = []
    for arg in args:
        if arg.is_array():
            result.extend(arg.as_array())
    return DynValue.of_array(result)


def verb_zip(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_array([])
    arrays = [_extract_array(a) for a in args]
    max_len = max((len(a) for a in arrays), default=0)
    result: List[DynValue] = []
    for i in range(max_len):
        pair: List[DynValue] = []
        for arr in arrays:
            if i < len(arr):
                pair.append(arr[i])
            else:
                pair.append(DynValue.of_null())
        result.append(DynValue.of_array(pair))
    return DynValue.of_array(result)


def verb_group_by(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    arr = _extract_array(args[0])
    field = coerce_str(args[1])
    if not field:
        return DynValue.of_null()
    groups: dict = {}
    for item in arr:
        key = coerce_str(_get_field(item, field))
        if key not in groups:
            groups[key] = []
        groups[key].append(item)
    return DynValue.of_object({k: DynValue.of_array(v) for k, v in groups.items()})


def verb_partition(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_array([DynValue.of_array([]), DynValue.of_array([])])
    arr = _extract_array(args[0])
    field = coerce_str(args[1]) if len(args) >= 2 else ""
    passing: List[DynValue] = []
    failing: List[DynValue] = []
    for item in arr:
        val = _get_field(item, field) if field else item
        if is_truthy(val):
            passing.append(item)
        else:
            failing.append(item)
    return DynValue.of_array([DynValue.of_array(passing), DynValue.of_array(failing)])


def verb_take(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_array([])
    arr = _extract_array(args[0])
    n = coerce_num(args[1])
    if n is None:
        return DynValue.of_array([])
    count = max(0, min(int(n), len(arr)))
    return DynValue.of_array(arr[:count])


def verb_drop(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_array([])
    arr = _extract_array(args[0])
    n = coerce_num(args[1])
    if n is None:
        return DynValue.of_array([])
    count = max(0, min(int(n), len(arr)))
    return DynValue.of_array(arr[count:])


def verb_chunk(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    arr = _extract_array(args[0])
    size_num = coerce_num(args[1])
    if size_num is None or size_num <= 0:
        return DynValue.of_null()
    size = int(size_num)
    result: List[DynValue] = []
    for i in range(0, len(arr), size):
        result.append(DynValue.of_array(arr[i:i + size]))
    return DynValue.of_array(result)


def verb_range(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_array([])
    if len(args) == 1:
        end_n = coerce_num(args[0])
        if end_n is None:
            return DynValue.of_array([])
        start, end, step = 0.0, end_n, 1.0
    elif len(args) == 2:
        start_n = coerce_num(args[0])
        end_n = coerce_num(args[1])
        if start_n is None or end_n is None:
            return DynValue.of_array([])
        start, end, step = start_n, end_n, 1.0
    else:
        start_n = coerce_num(args[0])
        end_n = coerce_num(args[1])
        step_n = coerce_num(args[2])
        if start_n is None or end_n is None or step_n is None or step_n == 0:
            return DynValue.of_array([])
        start, end, step = start_n, end_n, step_n

    result: List[DynValue] = []
    current = start
    max_items = 10000
    while len(result) < max_items:
        if step > 0 and current >= end:
            break
        if step < 0 and current <= end:
            break
        result.append(numeric_result(current))
        current += step
    return DynValue.of_array(result)


def verb_compact(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    arr = _extract_array(args[0])
    result = [item for item in arr if not item.is_null() and not (item.is_string() and not item._string_value)]
    return DynValue.of_array(result)


def verb_row_number(args: List[DynValue], ctx: object) -> DynValue:
    # Requires accumulator context — increment _rowNumber
    if hasattr(ctx, 'accumulators'):
        accs = ctx.accumulators
        key = "_rowNumber"
        current = accs.get(key, DynValue.of_integer(0))
        n = current._int_value if current.type == DynType.INTEGER else 0
        n += 1
        accs[key] = DynValue.of_integer(n)
        return DynValue.of_integer(n)
    return DynValue.of_integer(1)


def _string_to_seed(s: str) -> int:
    """DJB2 hash starting at 0, matching TypeScript/Rust stringToSeed."""
    h = 0
    for ch in s:
        h = ((h << 5) - h + ord(ch)) & 0xFFFFFFFF
    return h


class _Mulberry32:
    """Seeded 32-bit PRNG (Mulberry32), matching TypeScript/Rust."""

    def __init__(self, seed: int) -> None:
        self._state = seed & 0xFFFFFFFF

    def next_float(self) -> float:
        self._state = (self._state + 0x6D2B79F5) & 0xFFFFFFFF
        t = self._state
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t = (t ^ (t + ((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0


def verb_sample(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_array([])
    arr = _extract_array(args[0])
    n = coerce_num(args[1])
    if n is None:
        return DynValue.of_array([])
    count = max(0, min(int(n), len(arr)))
    # Seeded sampling: 3rd arg is seed string
    if len(args) >= 3 and args[2].is_string():
        seed_str = coerce_str(args[2])
        seed_val = _string_to_seed(seed_str)
        rng = _Mulberry32(seed_val)
        # Fisher-Yates shuffle with Mulberry32
        items = list(arr)
        for i in range(len(items) - 1, 0, -1):
            j = int(rng.next_float() * (i + 1))
            items[i], items[j] = items[j], items[i]
        return DynValue.of_array(items[:count])
    sampled = random.sample(arr, count) if count <= len(arr) else list(arr)
    return DynValue.of_array(sampled)


def verb_limit(args: List[DynValue], ctx: object) -> DynValue:
    return verb_take(args, ctx)


def verb_dedupe(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    arr = _extract_array(args[0])
    if not arr:
        return DynValue.of_array([])
    result: List[DynValue] = [arr[0]]
    for i in range(1, len(arr)):
        if not dyn_values_equal(arr[i], arr[i - 1]):
            result.append(arr[i])
    return DynValue.of_array(result)


def verb_cumsum(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_array([])
    arr = _extract_array(args[0])
    result: List[DynValue] = []
    running = 0.0
    for item in arr:
        n = coerce_num(item)
        if n is None:
            result.append(DynValue.of_null())
        else:
            running += n
            result.append(numeric_result(running))
    return DynValue.of_array(result)


def verb_cumprod(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_array([])
    arr = _extract_array(args[0])
    result: List[DynValue] = []
    running = 1.0
    for item in arr:
        n = coerce_num(item)
        if n is None:
            result.append(DynValue.of_null())
        else:
            running *= n
            result.append(numeric_result(running))
    return DynValue.of_array(result)


def verb_diff(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_array([])
    arr = _extract_array(args[0])
    result: List[DynValue] = []
    for i, item in enumerate(arr):
        if i == 0:
            result.append(DynValue.of_null())
            continue
        curr = coerce_num(item)
        prev = coerce_num(arr[i - 1])
        if curr is None or prev is None:
            result.append(DynValue.of_null())
        else:
            result.append(numeric_result(curr - prev))
    return DynValue.of_array(result)


def verb_pct_change(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_array([])
    arr = _extract_array(args[0])
    result: List[DynValue] = []
    for i, item in enumerate(arr):
        if i == 0:
            result.append(DynValue.of_null())
            continue
        curr = coerce_num(item)
        prev = coerce_num(arr[i - 1])
        if curr is None or prev is None or prev == 0:
            result.append(DynValue.of_null())
        else:
            result.append(DynValue.of_float((curr - prev) / prev))
    return DynValue.of_array(result)


def verb_shift(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_array([])
    arr = _extract_array(args[0])
    n = 1
    if len(args) >= 2:
        n_val = coerce_num(args[1])
        if n_val is not None:
            n = int(n_val)
    if n == 0 or not arr:
        return DynValue.of_array(list(arr))
    result: List[DynValue] = []
    if n > 0:
        result = [DynValue.of_null()] * min(n, len(arr)) + arr[:max(0, len(arr) - n)]
    else:
        skip = min(-n, len(arr))
        result = arr[skip:] + [DynValue.of_null()] * min(-n, len(arr))
    return DynValue.of_array(result)


def verb_lag(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_array([])
    arr_arg = args[0]
    n = 1
    if len(args) >= 2:
        n_val = coerce_num(args[1])
        if n_val is not None:
            n = int(n_val)
    return verb_shift([arr_arg, DynValue.of_integer(n)], ctx)


def verb_lead(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_array([])
    arr_arg = args[0]
    n = 1
    if len(args) >= 2:
        n_val = coerce_num(args[1])
        if n_val is not None:
            n = int(n_val)
    return verb_shift([arr_arg, DynValue.of_integer(-n)], ctx)


def verb_rank(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_array([])
    arr = _extract_array(args[0])
    if not arr:
        return DynValue.of_array([])
    # Get numeric values with original indices
    indexed = []
    for i, item in enumerate(arr):
        n = coerce_num(item)
        indexed.append((i, n))
    # Sort descending by value (nulls last)
    indexed.sort(key=lambda x: (x[1] is None, -(x[1] or 0)))
    ranks = [0] * len(arr)
    current_rank = 1
    for j, (orig_idx, val) in enumerate(indexed):
        if j > 0:
            prev_val = indexed[j - 1][1]
            if val != prev_val:
                current_rank = j + 1
        ranks[orig_idx] = current_rank
    return DynValue.of_array([DynValue.of_integer(r) for r in ranks])


def verb_fill_missing(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_array([])
    arr = _extract_array(args[0])
    strategy = coerce_str(args[1])
    fill_value = args[2] if len(args) >= 3 else DynValue.of_null()

    result = list(arr)
    if strategy == "forward":
        last_valid = DynValue.of_null()
        for i in range(len(result)):
            if result[i].is_null():
                result[i] = last_valid
            else:
                last_valid = result[i]
    elif strategy == "backward":
        next_valid = DynValue.of_null()
        for i in range(len(result) - 1, -1, -1):
            if result[i].is_null():
                result[i] = next_valid
            else:
                next_valid = result[i]
    else:
        # Fill with value
        for i in range(len(result)):
            if result[i].is_null():
                result[i] = fill_value
    return DynValue.of_array(result)


def verb_join(args: List[DynValue], ctx: object) -> DynValue:
    """Join array elements into a string with separator."""
    if len(args) < 1:
        return DynValue.of_string("")
    arr = _extract_array(args[0])
    sep = coerce_str(args[1]) if len(args) >= 2 else ","
    parts = [coerce_str(item) for item in arr]
    return DynValue.of_string(sep.join(parts))


# ── reduce ────────────────────────────────────────────────────────────────────


def verb_reduce(args: List[DynValue], ctx: object) -> DynValue:
    """Fold array to single value using a named verb."""
    if len(args) < 3:
        return DynValue.of_null()

    arr = _extract_array(args[0])
    if not arr:
        return args[2]  # empty array → return initial value

    verb_name = coerce_str(args[1])
    if not verb_name:
        return DynValue.of_null()

    # Look up verb in registry via ctx
    from odin.transform.verb_registry import create_default_registry
    registry = create_default_registry()
    verb_fn = registry.get(verb_name)
    if verb_fn is None:
        return DynValue.of_null()

    accumulator = args[2]
    for item in arr:
        accumulator = verb_fn([accumulator, item], ctx)

    return accumulator


# ── pivot ─────────────────────────────────────────────────────────────────────


def verb_pivot(args: List[DynValue], ctx: object) -> DynValue:
    """Reshape array-of-objects → object keyed by field values."""
    if len(args) < 3:
        return DynValue.of_null()

    arr = _extract_array(args[0])
    key_field = coerce_str(args[1])
    value_field = coerce_str(args[2])
    if not key_field or not value_field:
        return DynValue.of_null()

    result: dict = {}

    for item in arr:
        if not item.is_object():
            continue

        key_val = item.get(key_field)
        if key_val is None or key_val.is_null():
            continue

        value_val = item.get(value_field)
        if value_val is None:
            continue

        key = coerce_str(key_val)
        result[key] = value_val

    return DynValue.of_object(result)


# ── unpivot ───────────────────────────────────────────────────────────────────


def verb_unpivot(args: List[DynValue], ctx: object) -> DynValue:
    """Reshape object → array of {key, value} objects."""
    if len(args) < 3:
        return DynValue.of_null()

    if not args[0].is_object():
        return DynValue.of_null()

    key_name = coerce_str(args[1])
    value_name = coerce_str(args[2])
    if not key_name or not value_name:
        return DynValue.of_null()

    obj = args[0].as_object()
    result = []

    for k, v in obj.items():
        row = {key_name: DynValue.of_string(k), value_name: v}
        result.append(DynValue.of_object(row))

    return DynValue.of_array(result)
