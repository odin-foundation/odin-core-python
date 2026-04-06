"""JSON export - converts OdinDocument to JSON string."""

from __future__ import annotations

import base64
import json
import math
import re
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Union

from odin.types.document import OdinDocument
from odin.types.values import (
    OdinValue, OdinNull, OdinBoolean, OdinString, OdinNumber, OdinInteger,
    OdinCurrency, OdinPercent, OdinDate, OdinTimestamp, OdinTime,
    OdinDuration, OdinReference, OdinBinary, OdinArray, OdinObject,
)


def to_json(
    doc: OdinDocument,
    indent: Optional[int] = None,
    omit_nulls: bool = False,
) -> str:
    """Convert an OdinDocument to JSON string.

    Args:
        doc: The document to export
        indent: JSON indentation (None for compact)
        omit_nulls: Whether to omit null values

    Returns:
        JSON string
    """
    obj = _build_json_object(doc, omit_nulls)
    return json.dumps(obj, indent=indent, ensure_ascii=False)


def _build_json_object(doc: OdinDocument, omit_nulls: bool) -> dict:
    """Build a nested dict from flat OdinDocument assignments."""
    result: Dict[str, Any] = OrderedDict()

    # Collect header metadata under "$" key
    header_entries: Dict[str, Any] = OrderedDict()
    for path, value in doc.assignments.items():
        if path.startswith("$."):
            key = path[2:]  # Remove "$."
            header_entries[key] = _convert_value(value)

    for path, value in doc.assignments.items():
        if path.startswith("$"):
            continue

        json_value = _convert_value(value)
        if omit_nulls and json_value is None:
            continue

        _set_nested(result, path, json_value)

    # Append header metadata at the end
    if header_entries:
        result["$"] = header_entries

    return result


def _convert_value(value: OdinValue) -> Any:
    """Convert an OdinValue to a JSON-compatible Python value."""
    if isinstance(value, OdinNull):
        return None
    if isinstance(value, OdinBoolean):
        return value.value
    if isinstance(value, OdinString):
        return value.value
    if isinstance(value, OdinInteger):
        return value.value
    if isinstance(value, OdinNumber):
        v = value.value
        if math.isnan(v) or math.isinf(v):
            return None
        if v == int(v) and abs(v) < 1e15:
            return int(v)
        return v
    if isinstance(value, OdinCurrency):
        v = float(value.value)
        if v == int(v) and abs(v) < 1e15:
            return int(v)
        return v
    if isinstance(value, OdinPercent):
        v = value.value
        if v == int(v) and abs(v) < 1e15:
            return int(v)
        return v
    if isinstance(value, OdinDate):
        return value.raw
    if isinstance(value, OdinTimestamp):
        return value.raw
    if isinstance(value, OdinTime):
        return value.value
    if isinstance(value, OdinDuration):
        return value.value
    if isinstance(value, OdinReference):
        return f"@{value.path}"
    if isinstance(value, OdinBinary):
        b64 = base64.b64encode(value.data).decode("ascii")
        if value.algorithm:
            return f"^{value.algorithm}:{b64}"
        return f"^{b64}"
    if isinstance(value, (OdinArray, OdinObject)):
        return None  # markers, actual values are in child paths
    return str(value)


def _set_nested(obj: dict, path: str, value: Any):
    """Set a value in a nested dict structure from an ODIN path."""
    segments = _parse_path(path)
    current: Any = obj

    for i, seg in enumerate(segments[:-1]):
        next_seg = segments[i + 1]
        if isinstance(seg, str):
            if seg not in current:
                if isinstance(next_seg, int):
                    current[seg] = []
                else:
                    current[seg] = OrderedDict()
            current = current[seg]
        elif isinstance(seg, int):
            while len(current) <= seg:
                current.append(None)
            if current[seg] is None:
                if isinstance(next_seg, int):
                    current[seg] = []
                else:
                    current[seg] = OrderedDict()
            current = current[seg]

    last = segments[-1]
    if isinstance(last, str):
        current[last] = value
    elif isinstance(last, int):
        while len(current) <= last:
            current.append(None)
        current[last] = value


def _parse_path(path: str) -> List[Union[str, int]]:
    """Parse an ODIN path into segments."""
    segments: List[Union[str, int]] = []
    current: List[str] = []

    i = 0
    while i < len(path):
        ch = path[i]
        if ch == '.':
            if current:
                segments.append("".join(current))
                current = []
            i += 1
        elif ch == '[':
            if current:
                segments.append("".join(current))
                current = []
            i += 1
            idx: List[str] = []
            while i < len(path) and path[i] != ']':
                idx.append(path[i])
                i += 1
            if i < len(path):
                i += 1  # ]
            segments.append(int("".join(idx)))
            if i < len(path) and path[i] == '.':
                i += 1
        else:
            current.append(ch)
            i += 1

    if current:
        segments.append("".join(current))

    return segments
