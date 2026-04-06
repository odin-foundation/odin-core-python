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
    if len(args) < 1:
        return DynValue.of_array([])
    obj = _extract_obj(args[0])
    keys = _safe_keys(obj)
    return DynValue.of_array([DynValue.of_string(k) for k in keys])


def verb_values(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_array([])
    obj = _extract_obj(args[0])
    keys = _safe_keys(obj)
    return DynValue.of_array([obj[k] for k in keys])


def verb_entries(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_array([])
    obj = _extract_obj(args[0])
    keys = _safe_keys(obj)
    result = []
    for k in keys:
        entry = DynValue.of_array([DynValue.of_string(k), obj[k]])
        result.append(entry)
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
