"""Encoding verbs: base64, hex, url, json, hash, crc32, jsonPath."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import urllib.parse
from typing import Any, Dict, List

from odin.transform.dyn_value import DynValue, DynType
from odin.transform.verbs.helpers import coerce_str


def verb_base64_encode(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    encoded = base64.b64encode(s.encode("utf-8")).decode("ascii")
    return DynValue.of_string(encoded)


def verb_base64_decode(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    # Support URL-safe base64
    s = s.replace("-", "+").replace("_", "/")
    # Add padding if needed
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    try:
        decoded = base64.b64decode(s).decode("utf-8")
        return DynValue.of_string(decoded)
    except Exception:
        return DynValue.of_null()


def verb_url_encode(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    return DynValue.of_string(urllib.parse.quote(s, safe=""))


def verb_url_decode(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    try:
        return DynValue.of_string(urllib.parse.unquote(s))
    except Exception:
        return DynValue.of_null()


def verb_hex_encode(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    return DynValue.of_string(s.encode("utf-8").hex())


def verb_hex_decode(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    if len(s) % 2 != 0:
        return DynValue.of_null()
    if not all(c in "0123456789abcdefABCDEF" for c in s):
        return DynValue.of_null()
    try:
        decoded = bytes.fromhex(s).decode("utf-8")
        return DynValue.of_string(decoded)
    except Exception:
        return DynValue.of_null()


def verb_json_encode(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    v = args[0]
    if v.is_object() or v.is_array():
        py = _dyn_to_python(v)
        return DynValue.of_string(json.dumps(py, ensure_ascii=False, separators=(",", ":")))
    # For other types, JSON-escape the string
    s = coerce_str(v)
    return DynValue.of_string(json.dumps(s, ensure_ascii=False, separators=(",", ":")))


def verb_json_decode(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    if not s:
        return DynValue.of_null()
    try:
        parsed = json.loads(s)
        return _python_to_dyn(parsed)
    except (json.JSONDecodeError, ValueError):
        return DynValue.of_null()


def verb_sha256(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    return DynValue.of_string(hashlib.sha256(s.encode("utf-8")).hexdigest())


def verb_sha1(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    return DynValue.of_string(hashlib.sha1(s.encode("utf-8")).hexdigest())


def verb_sha512(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    return DynValue.of_string(hashlib.sha512(s.encode("utf-8")).hexdigest())


def verb_md5(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    return DynValue.of_string(hashlib.md5(s.encode("utf-8")).hexdigest())


def verb_crc32(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    import zlib
    s = coerce_str(args[0])
    crc = zlib.crc32(s.encode("utf-8")) & 0xFFFFFFFF
    return DynValue.of_string(f"{crc:08x}")


def verb_json_path(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    data = args[0]
    path_str = coerce_str(args[1])
    if not path_str:
        return data

    # Strip leading $
    if path_str.startswith("$."):
        path_str = path_str[2:]
    elif path_str.startswith("$"):
        path_str = path_str[1:]

    if not path_str:
        return data

    current = data
    # Parse path segments
    segments = _parse_json_path_segments(path_str)
    for seg in segments:
        if current is None or current.is_null():
            return DynValue.of_null()
        if seg.startswith("[") and seg.endswith("]"):
            inner = seg[1:-1]
            try:
                idx = int(inner)
                if current.is_array():
                    items = current.as_array()
                    if 0 <= idx < len(items):
                        current = items[idx]
                    else:
                        return DynValue.of_null()
                else:
                    return DynValue.of_null()
            except ValueError:
                return DynValue.of_null()
        else:
            if current.is_object():
                child = current.get(seg)
                if child is None:
                    return DynValue.of_null()
                current = child
            else:
                return DynValue.of_null()
    return current


def _parse_json_path_segments(path: str) -> List[str]:
    segments = []
    i = 0
    while i < len(path):
        if path[i] == ".":
            i += 1
            continue
        if path[i] == "[":
            end = path.find("]", i)
            if end < 0:
                end = len(path)
            segments.append(path[i:end + 1])
            i = end + 1
        else:
            start = i
            while i < len(path) and path[i] != "." and path[i] != "[":
                i += 1
            segments.append(path[start:i])
    return segments


def _dyn_to_python(v: DynValue) -> Any:
    if v.is_null():
        return None
    if v.type == DynType.BOOL:
        return v._bool_value
    if v.type == DynType.INTEGER:
        return v._int_value
    if v.type == DynType.FLOAT:
        return v._float_value
    if v.type == DynType.STRING:
        return v._string_value or ""
    if v.type == DynType.ARRAY:
        return [_dyn_to_python(item) for item in (v._array_value or [])]
    if v.type == DynType.OBJECT:
        return {k: _dyn_to_python(val) for k, val in (v._object_value or {}).items()}
    return coerce_str(v)


def _python_to_dyn(value: Any) -> DynValue:
    if value is None:
        return DynValue.of_null()
    if isinstance(value, bool):
        return DynValue.of_bool(value)
    if isinstance(value, int):
        return DynValue.of_integer(value)
    if isinstance(value, float):
        return DynValue.of_float(value)
    if isinstance(value, str):
        return DynValue.of_string(value)
    if isinstance(value, list):
        return DynValue.of_array([_python_to_dyn(item) for item in value])
    if isinstance(value, dict):
        return DynValue.of_object({k: _python_to_dyn(v) for k, v in value.items()})
    return DynValue.of_string(str(value))
