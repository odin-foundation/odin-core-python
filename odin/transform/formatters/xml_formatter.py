"""XML formatter - converts DynValue tree to XML string."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from odin.transform.dyn_value import DynValue, DynType


# Map DynType to odin:type XML attribute names
_TYPE_MAP = {
    DynType.BOOL: "boolean",
    DynType.INTEGER: "integer",
    DynType.FLOAT: "number",
    DynType.FLOAT_RAW: "number",
    DynType.CURRENCY: "currency",
    DynType.CURRENCY_RAW: "currency",
    DynType.PERCENT: "percent",
    DynType.DATE: "date",
    DynType.TIMESTAMP: "timestamp",
    DynType.TIME: "time",
    DynType.DURATION: "duration",
    DynType.REFERENCE: "reference",
    DynType.BINARY: "binary",
}


def format_xml(
    value: DynValue,
    root_element: str = "root",
    indent: str = "  ",
    declaration: bool = False,
    transform: Any = None,
) -> str:
    """Format a DynValue tree as an XML string.

    Args:
        value: DynValue tree (typically an object)
        root_element: Root element name
        indent: Indentation string
        declaration: Whether to include XML declaration
        transform: OdinTransform with segment/mapping metadata

    Returns:
        XML string
    """
    # Collect :attr, :ns and :cdata fields from transform
    attr_fields: Set[str] = set()
    ns_fields: Dict[str, str] = {}
    cdata_fields: Set[str] = set()
    namespaces: Dict[str, str] = {}
    emit_type_hints = True
    if transform is not None:
        for seg in transform.segments:
            for m in seg.mappings:
                for d in m.directives:
                    if d.name == "attr":
                        attr_fields.add(f"{seg.name}.{m.target}")
                    elif d.name == "ns" and d.value:
                        ns_fields[f"{seg.name}.{m.target}"] = str(d.value)
                    elif d.name == "cdata":
                        cdata_fields.add(f"{seg.name}.{m.target}")
        namespaces = transform.target.namespaces
        emit_type_hints = transform.target.options.get("emitTypeHints") != "false"

    # Emit the odin namespace only when type hints are on and the document
    # carries any odin: attribute (typed or null values).
    include_odin_ns = emit_type_hints and _needs_odin_ns(value, attr_fields)

    parts: List[str] = []
    if declaration:
        parts.append('<?xml version="1.0" encoding="UTF-8"?>')

    if transform is not None and value.is_object():
        # Segment-based: each segment is a top-level element
        _write_segments(
            value, transform.segments, attr_fields, ns_fields, cdata_fields, namespaces,
            include_odin_ns, emit_type_hints, parts, indent,
        )
    else:
        # Fallback: simple tree walk
        parts.append(f"<{_escape_name(root_element)}>")
        _write_value(value, parts, indent, 1, set(), {}, set(), emit_type_hints)
        parts.append(f"</{_escape_name(root_element)}>")

    return "\n".join(parts) + "\n"


def _write_segments(
    output: DynValue,
    segments: list,
    attr_fields: Set[str],
    ns_fields: Dict[str, str],
    cdata_fields: Set[str],
    namespaces: Dict[str, str],
    include_odin_ns: bool,
    emit_type_hints: bool,
    parts: List[str],
    indent: str,
):
    """Write segments as top-level XML elements."""
    for segment in segments:
        name = segment.name
        is_array = name.endswith("[]") or segment.source_path is not None
        clean_name = name[:-2] if name.endswith("[]") else name

        if not clean_name:
            continue

        seg_data = output.get(clean_name) if output.is_object() else None
        if seg_data is None:
            continue

        # Collect attr field names for this segment
        seg_attr_fields = _segment_field_set(attr_fields, name, clean_name)
        seg_cdata_fields = _segment_field_set(cdata_fields, name, clean_name)

        # Collect :ns prefixes keyed by bare field name for this segment
        seg_ns_fields: Dict[str, str] = {}
        for nf, ns_prefix in ns_fields.items():
            prefix = f"{name}." if name.endswith("[]") else f"{clean_name}."
            if nf.startswith(prefix):
                seg_ns_fields[nf[len(prefix):]] = ns_prefix
            prefix2 = f"{clean_name}[]."
            if nf.startswith(prefix2):
                seg_ns_fields[nf[len(prefix2):]] = ns_prefix

        if is_array and seg_data.is_array():
            for item in seg_data.as_array():
                if not item.is_object():
                    continue
                # Array items don't carry root declarations
                _write_element(
                    clean_name, item, seg_attr_fields, seg_ns_fields, seg_cdata_fields,
                    None, False, emit_type_hints, parts, indent, 0,
                )
        elif seg_data.is_object():
            # Non-array segments carry the root namespace declarations
            _write_element(
                clean_name, seg_data, seg_attr_fields, seg_ns_fields, seg_cdata_fields,
                namespaces, include_odin_ns, emit_type_hints, parts, indent, 0,
            )

        if segment.children:
            _write_segments(
                output, segment.children, attr_fields, ns_fields, cdata_fields,
                namespaces, include_odin_ns, emit_type_hints, parts, indent,
            )


def _segment_field_set(fields: Set[str], name: str, clean_name: str) -> Set[str]:
    """Reduce qualified field names to the bare names belonging to a segment."""
    result: Set[str] = set()
    prefix = f"{name}." if name.endswith("[]") else f"{clean_name}."
    prefix2 = f"{clean_name}[]."
    for f in fields:
        if f.startswith(prefix):
            result.add(f[len(prefix):])
        if f.startswith(prefix2):
            result.add(f[len(prefix2):])
    return result


def _write_element(
    tag: str,
    value: DynValue,
    attr_fields: Set[str],
    ns_fields: Dict[str, str],
    cdata_fields: Set[str],
    root_namespaces: Optional[Dict[str, str]],
    include_odin_ns: bool,
    emit_type_hints: bool,
    parts: List[str],
    indent: str,
    depth: int,
):
    """Write an XML element with attributes and child elements."""
    pad = indent * depth
    safe_tag = _escape_name(tag)

    # Build attribute string
    attrs_str = ""
    if root_namespaces is not None:
        if include_odin_ns:
            attrs_str += ' xmlns:odin="https://odin.foundation/ns"'
        for ns_prefix, uri in root_namespaces.items():
            attrs_str += f' xmlns:{_escape_name(ns_prefix)}="{_escape_attr(uri)}"'

    # Collect :attr fields as XML attributes
    skip_keys: Set[str] = set()
    if value.is_object():
        for key, val in value.as_object().items():
            if key in attr_fields:
                text = _format_text(val)
                if text is not None:
                    attrs_str += f' {_escape_name(key)}="{_escape_attr(text)}"'
                skip_keys.add(key)

    parts.append(f"{pad}<{safe_tag}{attrs_str}>")
    _write_value(value, parts, indent, depth + 1, skip_keys, ns_fields, cdata_fields, emit_type_hints)
    parts.append(f"{pad}</{safe_tag}>")


def _needs_odin_ns(value: DynValue, attr_fields: Set[str]) -> bool:
    """Check if a value tree will emit any odin: attribute (typed or null values)."""
    if value.is_object():
        for key, val in value.as_object().items():
            if key in attr_fields:
                continue
            if val.is_null() or val.type in _TYPE_MAP:
                return True
            if (val.is_object() or val.is_array()) and _needs_odin_ns(val, set()):
                return True
    elif value.is_array():
        for item in value.as_array():
            if item.is_null() or item.type in _TYPE_MAP:
                return True
            if (item.is_object() or item.is_array()) and _needs_odin_ns(item, set()):
                return True
    return False


def _has_typed_values(value: DynValue, attr_fields: Set[str]) -> bool:
    """Check if a value tree contains non-string typed values."""
    if value.is_object():
        for key, val in value.as_object().items():
            if key in attr_fields:
                continue
            if val.type in _TYPE_MAP:
                return True
            if val.is_object() and _has_typed_values(val, set()):
                return True
    elif value.is_array():
        for item in value.as_array():
            if _has_typed_values(item, attr_fields):
                return True
    return False


def _write_value(
    value: DynValue,
    parts: List[str],
    indent: str,
    depth: int,
    skip_keys: Set[str],
    ns_fields: Dict[str, str],
    cdata_fields: Set[str],
    emit_type_hints: bool,
):
    """Write a DynValue as XML child elements."""
    prefix = indent * depth

    if value.is_object():
        for key, val in value.as_object().items():
            if key in skip_keys:
                continue
            safe_name = _ns_qualify(_escape_name(key), key, ns_fields)
            is_cdata = key in cdata_fields
            if val.is_null():
                null_attr = ' odin:type="null"' if emit_type_hints else ""
                parts.append(
                    f'{prefix}<{safe_name}{null_attr}></{safe_name}>'
                )
                continue
            if val.is_object():
                parts.append(f"{prefix}<{safe_name}>")
                _write_value(val, parts, indent, depth + 1, set(), {}, set(), emit_type_hints)
                parts.append(f"{prefix}</{safe_name}>")
            elif val.is_array():
                for item in val.as_array():
                    if item.is_null():
                        null_attr = ' odin:type="null"' if emit_type_hints else ""
                        parts.append(
                            f'{prefix}<{safe_name}{null_attr}></{safe_name}>'
                        )
                        continue
                    if item.is_object():
                        parts.append(f"{prefix}<{safe_name}>")
                        _write_value(item, parts, indent, depth + 1, set(), {}, set(), emit_type_hints)
                        parts.append(f"{prefix}</{safe_name}>")
                    else:
                        text = _format_text(item)
                        type_attr = _type_attr(item) if emit_type_hints else ""
                        if text is not None:
                            body = _cdata_wrap(text) if is_cdata else _escape_content(text)
                            parts.append(
                                f"{prefix}<{safe_name}{type_attr}>{body}</{safe_name}>"
                            )
            else:
                text = _format_text(val)
                type_attr = _type_attr(val) if emit_type_hints else ""
                if text is not None:
                    body = _cdata_wrap(text) if is_cdata else _escape_content(text)
                    parts.append(
                        f"{prefix}<{safe_name}{type_attr}>{body}</{safe_name}>"
                    )


def _ns_qualify(safe_name: str, key: str, ns_fields: Dict[str, str]) -> str:
    """Prefix an element name with its target namespace when the field carries :ns."""
    ns_prefix = ns_fields.get(key)
    return f"{_escape_name(ns_prefix)}:{safe_name}" if ns_prefix else safe_name


def _type_attr(value: DynValue) -> str:
    """Return odin:type attribute string for non-string types."""
    # Currency always renders as currency; emit currencyCode when coded.
    if value.type in (DynType.CURRENCY, DynType.CURRENCY_RAW):
        code = value.get_currency_code()
        if code:
            return f' odin:type="currency" odin:currencyCode="{code}"'
        return ' odin:type="currency"'
    type_name = _TYPE_MAP.get(value.type)
    if not type_name:
        return ""
    return f' odin:type="{type_name}"'


def _format_text(value: DynValue) -> Optional[str]:
    """Convert a DynValue to XML text."""
    if value.is_null():
        return None
    if value.type == DynType.BOOL:
        return "true" if value.as_bool() else "false"
    if value.type == DynType.INTEGER:
        return str(value.as_int())
    if value.type in (DynType.FLOAT, DynType.FLOAT_RAW):
        v = value.as_float()
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        return str(v)
    if value.type in (DynType.CURRENCY, DynType.CURRENCY_RAW):
        # Preserve the raw decimal string when available; otherwise render at scale.
        if value.type == DynType.CURRENCY_RAW:
            raw = value.as_string()
            if raw:
                return raw
        v = value.as_float()
        if v is None:
            return "0"
        dp = value.get_decimal_places()
        return f"{v:.{dp}f}" if dp >= 0 else str(v)
    return value.as_string()


def _cdata_wrap(text: str) -> str:
    """Wrap element text in a CDATA section, splitting any embedded `]]>`."""
    safe = text.replace("]]>", "]]]]><![CDATA[>")
    return f"<![CDATA[{safe}]]>"


def _escape_content(text: str) -> str:
    """Escape XML text content."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def _escape_attr(text: str) -> str:
    """Escape XML attribute value."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    return text


def _escape_name(name: str) -> str:
    """Escape XML element name."""
    result = re.sub(r'[^a-zA-Z0-9_.-]', '_', name)
    if result and result[0].isdigit():
        result = '_' + result
    return result or '_'
