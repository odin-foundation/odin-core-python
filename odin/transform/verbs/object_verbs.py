"""Object verbs for the ODIN transform engine."""

from __future__ import annotations

from typing import Dict, List

from odin.transform.dyn_value import DynValue, DynType
from odin.transform.verbs.helpers import coerce_str


_UNSAFE_KEYS = frozenset({"__proto__", "constructor", "prototype"})


def _extract_obj(v: DynValue) -> Dict[str, DynValue]:
    """Extract object from DynValue."""
    if v.is_object():
        return v.as_object()
    return {}


def _safe_keys(obj: Dict[str, DynValue]) -> List[str]:
    """Get keys excluding prototype pollution vectors."""
    return [k for k in obj if k not in _UNSAFE_KEYS]


def _get_nested(obj: DynValue, path: str) -> DynValue:
    """Get nested value using dot notation."""
    parts = path.split(".")
    current = obj
    for part in parts:
        if part in _UNSAFE_KEYS:
            return DynValue.of_null()
        if current.is_object():
            val = current.get(part)
            if val is None:
                return DynValue.of_null()
            current = val
        elif current.is_array():
            try:
                idx = int(part)
                val = current.get_index(idx)
                if val is None:
                    return DynValue.of_null()
                current = val
            except (ValueError, IndexError):
                return DynValue.of_null()
        else:
            return DynValue.of_null()
    return current


# ── Verb implementations ────────────────────────────────────────────

def verb_keys(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1 or not args[0].is_object():
        return DynValue.of_null()
    obj = args[0].as_object()
    return DynValue.of_array([DynValue.of_string(k) for k in _safe_keys(obj)])


def verb_values(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1 or not args[0].is_object():
        return DynValue.of_null()
    obj = args[0].as_object()
    return DynValue.of_array([obj[k] for k in _safe_keys(obj)])


def verb_entries(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1 or not args[0].is_object():
        return DynValue.of_null()
    obj = args[0].as_object()
    result = []
    for k in _safe_keys(obj):
        result.append(DynValue.of_array([DynValue.of_string(k), obj[k]]))
    return DynValue.of_array(result)


def verb_has(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_bool(False)
    if not args[0].is_object():
        return DynValue.of_bool(False)
    path = coerce_str(args[1])
    if not path or path in _UNSAFE_KEYS:
        return DynValue.of_bool(False)
    result = _get_nested(args[0], path)
    return DynValue.of_bool(not result.is_null())


def verb_get(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    if not args[0].is_object():
        default = args[2] if len(args) >= 3 else DynValue.of_null()
        return default
    path = coerce_str(args[1])
    if not path or path in _UNSAFE_KEYS:
        return args[2] if len(args) >= 3 else DynValue.of_null()
    result = _get_nested(args[0], path)
    if result.is_null() and len(args) >= 3:
        return args[2]
    return result


def verb_merge(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    merged: Dict[str, DynValue] = {}
    for arg in args:
        if arg.is_object():
            obj = arg.as_object()
            for k in _safe_keys(obj):
                merged[k] = obj[k]
    if not merged:
        return DynValue.of_null()
    return DynValue.of_object(merged)


def verb_pick(args: List[DynValue], ctx: object) -> DynValue:
    if not args or not args[0].is_object():
        return DynValue.of_null()
    src = args[0].as_object()
    result: Dict[str, DynValue] = {}
    for arg in args[1:]:
        key = coerce_str(arg)
        if key not in _UNSAFE_KEYS and key in src:
            result[key] = src[key]
    return DynValue.of_object(result)


def verb_omit(args: List[DynValue], ctx: object) -> DynValue:
    if not args or not args[0].is_object():
        return DynValue.of_null()
    src = args[0].as_object()
    drop = {coerce_str(a) for a in args[1:]}
    result: Dict[str, DynValue] = {}
    for k in _safe_keys(src):
        if k not in drop:
            result[k] = src[k]
    return DynValue.of_object(result)


def verb_from_entries(args: List[DynValue], ctx: object) -> DynValue:
    if not args or not args[0].is_array():
        return DynValue.of_null()
    result: Dict[str, DynValue] = {}
    for entry in args[0].as_array():
        if entry.is_array():
            pair = entry.as_array()
        else:
            continue
        if len(pair) < 2:
            continue
        key = coerce_str(pair[0])
        if key not in _UNSAFE_KEYS:
            result[key] = pair[1]
    return DynValue.of_object(result)


def verb_invert(args: List[DynValue], ctx: object) -> DynValue:
    if not args or not args[0].is_object():
        return DynValue.of_null()
    src = args[0].as_object()
    result: Dict[str, DynValue] = {}
    for k in _safe_keys(src):
        new_key = coerce_str(src[k])
        if new_key not in _UNSAFE_KEYS:
            result[new_key] = DynValue.of_string(k)
    return DynValue.of_object(result)


def verb_defaults(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    a = args[0]
    d = args[1]
    if not a.is_object():
        return d if d.is_object() else DynValue.of_null()
    if not d.is_object():
        return a
    src = a.as_object()
    defs = d.as_object()
    result: Dict[str, DynValue] = {}
    for k in _safe_keys(src):
        result[k] = src[k]
    for k in _safe_keys(defs):
        if k not in result:
            result[k] = defs[k]
    return DynValue.of_object(result)


def verb_rename_keys(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    val = args[0]
    mapping = args[1]
    if not val.is_object():
        return DynValue.of_null()
    if not mapping.is_object():
        return val
    src = val.as_object()
    rename = mapping.as_object()
    result: Dict[str, DynValue] = {}
    for k in _safe_keys(src):
        new_key = coerce_str(rename[k]) if k in rename else k
        if new_key not in _UNSAFE_KEYS:
            result[new_key] = src[k]
    return DynValue.of_object(result)


def verb_compact_object(args: List[DynValue], ctx: object) -> DynValue:
    if not args or not args[0].is_object():
        return DynValue.of_null()
    src = args[0].as_object()
    result: Dict[str, DynValue] = {}
    for k in _safe_keys(src):
        v = src[k]
        if v.is_null():
            continue
        if v.is_string() and v.as_string() == "":
            continue
        if v.is_array() and len(v.as_array()) == 0:
            continue
        if v.is_object() and len(v.as_object()) == 0:
            continue
        result[k] = v
    return DynValue.of_object(result)
