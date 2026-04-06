"""XML export - converts OdinDocument to XML string."""

from __future__ import annotations

import base64
import math
import re
from collections import OrderedDict
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from odin.types.document import OdinDocument
from odin.types.values import (
    OdinValue, OdinNull, OdinBoolean, OdinString, OdinNumber, OdinInteger,
    OdinCurrency, OdinPercent, OdinDate, OdinTimestamp, OdinTime,
    OdinDuration, OdinReference, OdinBinary, OdinArray, OdinObject,
)

ODIN_NS = "https://odin.foundation/ns"


def to_xml(
    doc: OdinDocument,
    root_element: str = "root",
    indent: str = "  ",
    declaration: bool = True,
) -> str:
    """Convert an OdinDocument to XML string."""
    tree = _build_tree(doc)
    modifiers = _collect_modifiers(doc)

    parts: List[str] = []
    if declaration:
        parts.append('<?xml version="1.0" encoding="UTF-8"?>')

    parts.append(f'<{_escape_name(root_element)} xmlns:odin="{ODIN_NS}">')
    _write_children(tree, modifiers, parts, indent, 1, "")
    parts.append(f"</{_escape_name(root_element)}>")

    return "\n".join(parts)


def _build_tree(doc: OdinDocument) -> Dict[str, Any]:
    """Build nested dict from flat assignments, preserving OdinValue types."""
    result: Dict[str, Any] = OrderedDict()
    for path, value in doc.assignments.items():
        if path.startswith("$"):
            continue
        _set_nested(result, path, value)
    return result


def _collect_modifiers(doc: OdinDocument) -> Dict[str, Dict[str, bool]]:
    """Collect modifier info from document."""
    mods: Dict[str, Dict[str, bool]] = {}
    if hasattr(doc, 'modifiers') and doc.modifiers:
        for path, mod in doc.modifiers.items():
            m: Dict[str, bool] = {}
            if hasattr(mod, 'required') and mod.required:
                m['required'] = True
            elif hasattr(mod, 'critical') and mod.critical:
                m['required'] = True
            if hasattr(mod, 'confidential') and mod.confidential:
                m['confidential'] = True
            if hasattr(mod, 'deprecated') and mod.deprecated:
                m['deprecated'] = True
            if m:
                mods[path] = m
    return mods


def _write_children(
    tree: dict,
    modifiers: Dict[str, Dict[str, bool]],
    parts: List[str],
    indent: str,
    depth: int,
    parent_path: str,
):
    """Write child elements."""
    prefix = indent * depth
    for key, value in tree.items():
        path = f"{parent_path}.{key}" if parent_path else key

        if isinstance(value, dict):
            safe_name = _escape_name(key)
            parts.append(f"{prefix}<{safe_name}>")
            _write_children(value, modifiers, parts, indent, depth + 1, path)
            parts.append(f"{prefix}</{safe_name}>")
        elif isinstance(value, list):
            safe_name = _escape_name(key)
            for item in value:
                if isinstance(item, dict):
                    parts.append(f"{prefix}<{safe_name}>")
                    _write_children(item, modifiers, parts, indent, depth + 1, path)
                    parts.append(f"{prefix}</{safe_name}>")
                elif item is not None:
                    attrs_str, text = _format_value_with_attrs(item, modifiers, path)
                    if text is not None:
                        parts.append(f"{prefix}<{safe_name}{attrs_str}>{_escape_content(text)}</{safe_name}>")
        else:
            attrs_str, text = _format_value_with_attrs(value, modifiers, path)
            if text is not None:
                safe_name = _escape_name(key)
                parts.append(f"{prefix}<{safe_name}{attrs_str}>{_escape_content(text)}</{safe_name}>")


def _format_value_with_attrs(
    value: Any,
    modifiers: Dict[str, Dict[str, bool]],
    path: str,
) -> tuple:
    """Format a value and return (attrs_string, text_content)."""
    attrs: List[str] = []

    # Type attribute
    type_name = _get_type_name(value)
    if type_name:
        attrs.append(f'odin:type="{type_name}"')

    # Currency-specific attributes
    if isinstance(value, OdinCurrency):
        if value.currency_code:
            attrs.append(f'odin:currencyCode="{value.currency_code}"')

    # Modifier attributes
    mod = modifiers.get(path)
    if mod:
        if mod.get('required'):
            attrs.append('odin:required="true"')
        if mod.get('confidential'):
            attrs.append('odin:confidential="true"')
        if mod.get('deprecated'):
            attrs.append('odin:deprecated="true"')

    text = _format_value(value)
    attrs_str = (" " + " ".join(attrs)) if attrs else ""
    return attrs_str, text


def _get_type_name(value: Any) -> Optional[str]:
    """Get the ODIN type name for XML attribute."""
    if isinstance(value, OdinString):
        return None  # Strings don't need type annotation
    if isinstance(value, OdinInteger):
        return "integer"
    if isinstance(value, OdinNumber):
        return "number"
    if isinstance(value, OdinCurrency):
        return "currency"
    if isinstance(value, OdinPercent):
        return "percent"
    if isinstance(value, OdinBoolean):
        return "boolean"
    if isinstance(value, OdinDate):
        return "date"
    if isinstance(value, OdinTimestamp):
        return "timestamp"
    if isinstance(value, OdinTime):
        return "time"
    if isinstance(value, OdinDuration):
        return "duration"
    if isinstance(value, OdinReference):
        return "reference"
    if isinstance(value, OdinBinary):
        return "binary"
    return None


def _format_value(value: Any) -> Optional[str]:
    """Format a value for XML text content."""
    if value is None or isinstance(value, OdinNull):
        return None
    if isinstance(value, OdinBoolean):
        return "true" if value.value else "false"
    if isinstance(value, OdinString):
        return value.value
    if isinstance(value, OdinInteger):
        return str(value.value)
    if isinstance(value, OdinNumber):
        v = value.value
        if math.isnan(v) or math.isinf(v):
            return None
        # Preserve raw representation if available
        if hasattr(value, 'raw') and value.raw:
            return value.raw
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        return str(v)
    if isinstance(value, OdinCurrency):
        # Preserve decimal precision
        v = value.value
        if value.raw:
            # Strip currency code suffix (e.g. "250.00:USD" → "250.00")
            raw = value.raw
            if ":" in raw:
                raw = raw[:raw.index(":")]
            return raw
        if hasattr(v, 'as_tuple'):  # Decimal
            # Format without scientific notation
            return format(v, 'f')
        v = float(v)
        if v == int(v):
            return f"{v:.2f}"
        return str(v)
    if isinstance(value, OdinPercent):
        if hasattr(value, 'raw') and value.raw:
            return value.raw
        v = value.value
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        return str(v)
    if isinstance(value, OdinDate):
        return value.raw
    if isinstance(value, OdinTimestamp):
        return value.raw
    if isinstance(value, OdinTime):
        s = value.value
        if s and not s.startswith("T"):
            s = "T" + s
        return s
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
        return None
    return str(value)


def _escape_content(text: str) -> str:
    """Escape XML text content."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    text = text.replace("'", "&apos;")
    return text


def _escape_name(name: str) -> str:
    """Escape XML element name."""
    result = re.sub(r'[^a-zA-Z0-9_.-]', '_', name)
    if result and result[0].isdigit():
        result = '_' + result
    return result or '_'


def _set_nested(obj: dict, path: str, value: Any):
    """Set value at a nested path."""
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
                i += 1
            segments.append(int("".join(idx)))
            if i < len(path) and path[i] == '.':
                i += 1
        else:
            current.append(ch)
            i += 1

    if current:
        segments.append("".join(current))

    return segments
