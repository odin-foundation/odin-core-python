"""Flat formatter - converts DynValue to flat KVP or YAML."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

from odin.transform.dyn_value import DynValue, DynType


def format_flat(value: DynValue, style: str = "kvp") -> str:
    """Format a DynValue tree as flat key=value pairs or YAML.

    Args:
        value: DynValue tree (typically an object)
        style: "kvp" for key=value pairs, "yaml" for YAML

    Returns:
        Formatted string
    """
    if style == "yaml":
        return _format_yaml(value)
    return _format_kvp(value)


# ── KVP Style ──────────────────────────────────────────────────────────────────


def _format_kvp(value: DynValue) -> str:
    """Format as flat key=value pairs, sorted alphabetically."""
    pairs: List[Tuple[str, str]] = []
    _collect_kvp(value, "", pairs)
    # Sort alphabetically by key
    pairs.sort(key=lambda p: p[0])
    return "\n".join(f"{k}={v}" for k, v in pairs) + "\n"


def _collect_kvp(value: DynValue, prefix: str, pairs: List[Tuple[str, str]]):
    """Recursively collect key=value pairs."""
    if value.is_object():
        for key, val in value.as_object().items():
            path = f"{prefix}.{key}" if prefix else key
            _collect_kvp(val, path, pairs)
    elif value.is_array():
        for i, item in enumerate(value.as_array()):
            path = f"{prefix}[{i}]"
            _collect_kvp(item, path, pairs)
    else:
        text = _format_scalar_plain(value)
        pairs.append((prefix, text))


def _format_scalar_plain(value: DynValue) -> str:
    """Format a scalar DynValue as a plain string (no ODIN type prefixes)."""
    if value.is_null():
        return ""
    if value.type == DynType.BOOL:
        return "true" if value.as_bool() else "false"
    if value.type == DynType.INTEGER:
        return str(value.as_int())
    if value.type in (DynType.FLOAT, DynType.FLOAT_RAW):
        if value.type == DynType.FLOAT_RAW:
            raw = value.as_string()
            if raw:
                return raw
        v = value.as_float()
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        return str(v)
    if value.type in (DynType.CURRENCY, DynType.CURRENCY_RAW):
        if value.type == DynType.CURRENCY_RAW:
            raw = value.as_string()
            if raw:
                return raw
        v = value.as_float()
        if v is not None:
            if v == int(v) and abs(v) < 1e15:
                return str(int(v))
            return str(v)
        return "0"
    if value.type == DynType.PERCENT:
        v = value.as_float()
        if v is not None:
            if v == int(v) and abs(v) < 1e15:
                return str(int(v))
            return str(v)
        return "0"
    return value.as_string()


# ── YAML Style ─────────────────────────────────────────────────────────────────


def _format_yaml(value: DynValue) -> str:
    """Format as YAML hierarchical output."""
    # Build tree from flat DynValue paths
    tree = _dyn_to_tree(value)
    lines: List[str] = []
    _write_yaml_node(tree, lines, 0)
    return "\n".join(lines) + "\n"


def _dyn_to_tree(value: DynValue) -> Any:
    """Convert DynValue to a nested Python dict/list structure for YAML output."""
    if value.is_object():
        result = {}
        for key, val in value.as_object().items():
            result[key] = _dyn_to_tree(val)
        return result
    if value.is_array():
        return [_dyn_to_tree(item) for item in value.as_array()]
    return value


def _write_yaml_node(node: Any, lines: List[str], depth: int):
    """Write a YAML node recursively."""
    indent = "  " * depth

    if isinstance(node, dict):
        # Sort keys alphabetically
        for key in sorted(node.keys()):
            val = node[key]
            if isinstance(val, dict):
                lines.append(f"{indent}{key}:")
                _write_yaml_node(val, lines, depth + 1)
            elif isinstance(val, list):
                lines.append(f"{indent}{key}:")
                _write_yaml_array(val, lines, depth + 1)
            else:
                # Scalar
                text = _yaml_value(val)
                lines.append(f"{indent}{key}: {text}")
    elif isinstance(node, list):
        _write_yaml_array(node, lines, depth)
    else:
        text = _yaml_value(node)
        lines.append(f"{indent}{text}")


def _write_yaml_array(arr: list, lines: List[str], depth: int):
    """Write YAML array items."""
    indent = "  " * depth
    for item in arr:
        if isinstance(item, dict):
            # First key gets "- " prefix, rest are indented
            sorted_keys = sorted(item.keys())
            for i, key in enumerate(sorted_keys):
                val = item[key]
                text = _yaml_value(val) if not isinstance(val, (dict, list)) else None
                if i == 0:
                    if text is not None:
                        lines.append(f"{indent}- {key}: {text}")
                    else:
                        lines.append(f"{indent}- {key}:")
                        if isinstance(val, dict):
                            _write_yaml_node(val, lines, depth + 2)
                        elif isinstance(val, list):
                            _write_yaml_array(val, lines, depth + 2)
                else:
                    if text is not None:
                        lines.append(f"{indent}  {key}: {text}")
                    else:
                        lines.append(f"{indent}  {key}:")
                        if isinstance(val, dict):
                            _write_yaml_node(val, lines, depth + 2)
                        elif isinstance(val, list):
                            _write_yaml_array(val, lines, depth + 2)
        else:
            text = _yaml_value(item)
            lines.append(f"{indent}- {text}")


def _yaml_value(value: Any) -> str:
    """Convert a value to YAML-safe string representation."""
    if isinstance(value, DynValue):
        return _yaml_scalar(value)
    if value is None:
        return "null"
    return str(value)


def _yaml_scalar(value: DynValue) -> str:
    """Format a DynValue scalar for YAML output."""
    if value.is_null():
        return "null"
    if value.type == DynType.BOOL:
        s = "true" if value.as_bool() else "false"
        return f'"{s}"'
    if value.type == DynType.INTEGER:
        return str(value.as_int())
    if value.type in (DynType.FLOAT, DynType.FLOAT_RAW):
        if value.type == DynType.FLOAT_RAW:
            raw = value.as_string()
            if raw:
                return raw
        v = value.as_float()
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        return str(v)
    if value.type in (DynType.CURRENCY, DynType.CURRENCY_RAW):
        if value.type == DynType.CURRENCY_RAW:
            raw = value.as_string()
            if raw:
                return raw
        v = value.as_float()
        if v is not None:
            if v == int(v) and abs(v) < 1e15:
                return str(int(v))
            return str(v)
        return "0"
    # String - check if needs quoting
    s = value.as_string()
    if _needs_yaml_quoting(s):
        return f'"{s}"'
    return s


def _needs_yaml_quoting(s: str) -> bool:
    """Check if a string needs YAML quoting."""
    if not s:
        return True
    # Quote strings that look like YAML keywords
    lower = s.lower()
    if lower in ("true", "false", "null", "yes", "no", "on", "off"):
        return True
    # Quote if contains colon (ambiguous YAML mapping) or newline
    if ':' in s or '\n' in s or '\r' in s:
        return True
    return False
