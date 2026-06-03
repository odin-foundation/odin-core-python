"""ODIN formatter - converts DynValue tree to ODIN text with section headers."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from odin.transform.dyn_value import DynValue, DynType


def format_odin(
    value: DynValue,
    header: bool = False,
    modifiers: Optional[Dict[str, object]] = None,
) -> str:
    """Format a DynValue tree as ODIN text with section headers.

    Args:
        value: DynValue tree (typically an object)
        header: Whether to include {$} odin header
        modifiers: Field modifier map (path -> OdinModifiers)

    Returns:
        ODIN text string
    """
    if not value.is_object():
        if value.is_array():
            lines: List[str] = []
            _write_tabular_array(value, lines, "root")
            return "\n".join(lines) + "\n" if lines else ""
        return _format_value(value, modifiers, "") + "\n"

    lines: List[str] = []
    obj = value.as_object()

    # Step 1: Add ODIN header if requested
    if header:
        lines.append("{$}")
        lines.append('odin = "1.0.0"')

    # Step 2: Classify top-level entries, preserving order
    root_scalars: List[Tuple[str, DynValue]] = []
    ordered_entries: List[Tuple[str, DynValue, str]] = []  # (key, val, type)

    top_groups = sum(
        1 for k, v in obj.items() if k != "$" and (v.is_object() or v.is_array())
    )

    for key, val in obj.items():
        if key == "$":
            continue
        if val.is_object():
            # A single-scalar section alongside other top-level groups collapses to
            # a dotted root path emitted ahead of the section blocks.
            if top_groups > 1 and _single_scalar_section_entry(val) is not None:
                sub_key, sub_val = _single_scalar_section_entry(val)
                root_scalars.append((f"{key}.{sub_key}", sub_val))
            elif _should_be_section(val):
                ordered_entries.append((key, val, "section"))
            else:
                # Flatten to root-level dotted paths
                _flatten_object(key, val, root_scalars)
        elif val.is_array():
            ordered_entries.append((key, val, "array"))
        else:
            root_scalars.append((key, val))

    # Step 3: Write root section {} if there are root-level entries
    if root_scalars:
        if header:
            lines.append("{}")
        for key, val in root_scalars:
            mod_prefix = _get_modifier_prefix(modifiers, key)
            lines.append(f"{key} = {mod_prefix}{_format_value(val, modifiers, key)}")

    # Step 4: Write sections and arrays in original order
    for key, val, entry_type in ordered_entries:
        if entry_type == "section":
            single = _single_scalar_array_entry(val)
            if single is not None:
                sub_key, arr_val = single
                _write_tabular_array(arr_val, lines, f"{key}.{sub_key}", modifiers)
                continue
            lines.append(f"{{{key}}}")
            _write_section_body(key, val, lines, depth=0, modifiers=modifiers)
        elif entry_type == "array":
            _write_tabular_array(val, lines, key, modifiers, full_path=key)

    return "\n".join(lines) + "\n" if lines else ""


def _single_scalar_section_entry(obj: DynValue):
    """Return (key, value) when a section holds exactly one non-dotted scalar."""
    if not obj.is_object():
        return None
    entries = obj.as_object()
    if len(entries) != 1:
        return None
    key, val = next(iter(entries.items()))
    if "." in key or val.is_object() or val.is_array():
        return None
    return key, val


def _single_scalar_array_entry(obj: DynValue):
    """Return (key, array) when a section holds exactly one single-element scalar array."""
    if not obj.is_object():
        return None
    entries = obj.as_object()
    if len(entries) != 1:
        return None
    key, val = next(iter(entries.items()))
    if not val.is_array():
        return None
    items = val.as_array()
    if len(items) != 1:
        return None
    only = items[0]
    if only.is_object() or only.is_array():
        return None
    return key, val


def _should_be_section(obj: DynValue) -> bool:
    """Check if an object should be a named section vs flattened to dotted paths."""
    if not obj.is_object():
        return False
    entries = obj.as_object()
    if not entries:
        return False
    # If any key does NOT contain a dot, or if there are objects/arrays, it's a section
    has_non_dotted = False
    all_dotted_scalar = True
    for key, val in entries.items():
        if "." not in key:
            has_non_dotted = True
        if val.is_object() or val.is_array():
            return True
        if "." not in key:
            all_dotted_scalar = False
    if has_non_dotted:
        return True
    # All keys are dotted and all values are scalars
    # Flatten only if there's just one dotted key (thin section)
    if all_dotted_scalar and len(entries) <= 1:
        return False
    # Multiple dotted keys → keep as section (group is meaningful)
    return True


def _should_flatten_child(obj: DynValue) -> bool:
    """Check if a child object should be flattened to dotted paths instead of a sub-section.

    Returns True if the object has a single entry that is either:
    - a scalar value, or
    - another single-entry object that is itself flattenable (recursive chain).
    This handles chains like level1 -> level2 -> value.
    """
    if not obj.is_object():
        return False
    entries = obj.as_object()
    if not entries:
        return False
    # Only flatten if there's just one entry
    if len(entries) > 1:
        return False
    for v in entries.values():
        if v.is_array():
            return False
        if v.is_object():
            # Recursively check if the nested object is also flattenable
            return _should_flatten_child(v)
    return True


def _is_group_flattenable(entries: List[Tuple[str, "DynValue"]]) -> bool:
    """Check if a group of dotted-key entries can be flattened to a single scalar path.

    Returns True if there is exactly one entry and its value is a scalar
    (not an object or array). The entry key may itself contain dots.
    """
    if len(entries) != 1:
        return False
    _, val = entries[0]
    return not val.is_object() and not val.is_array()


def _flatten_object(prefix: str, obj: DynValue, result: List[Tuple[str, DynValue]]):
    """Flatten an object to dotted-path scalars."""
    if not obj.is_object():
        return
    for key, val in obj.as_object().items():
        full_key = f"{prefix}.{key}"
        if val.is_object():
            _flatten_object(full_key, val, result)
        else:
            result.append((full_key, val))


def _write_section_body(
    full_path: str,
    value: DynValue,
    lines: List[str],
    depth: int,
    modifiers: Optional[Dict[str, object]] = None,
):
    """Write section body content recursively."""
    if not value.is_object():
        return

    obj = value.as_object()

    # Check if this object has dotted keys that need hierarchy reconstruction
    has_dotted_keys = any("." in k for k in obj.keys())

    if has_dotted_keys:
        # Reconstruct hierarchy: group dotted keys by first segment
        _write_section_with_dotted_keys(full_path, obj, lines, depth, modifiers)
        return

    # Emit scalars, arrays and flattened thin objects in declaration order;
    # full child sections are emitted last.
    sections: List[Tuple[str, DynValue]] = []

    for k, v in obj.items():
        if v.is_object():
            if _should_flatten_child(v):
                _flatten_object(k, v, scalars_out := [])
                for dk, dv in scalars_out:
                    fp = f"{full_path}.{dk}"
                    mod_prefix = _get_modifier_prefix(modifiers, fp)
                    lines.append(f"{dk} = {mod_prefix}{_format_value(dv, modifiers, fp)}")
            else:
                sections.append((k, v))
        elif v.is_array():
            _write_tabular_array(v, lines, f".{k}", modifiers, full_path=f"{full_path}.{k}")
        else:
            field_path = f"{full_path}.{k}"
            mod_prefix = _get_modifier_prefix(modifiers, field_path)
            lines.append(f"{k} = {mod_prefix}{_format_value(v, modifiers, field_path)}")

    # Write full child sections last
    for k, v in sections:
        if len(v.as_object()) == 0:
            continue
        child_path = f"{full_path}.{k}"
        if depth == 0:
            lines.append(f"{{.{k}}}")
        else:
            lines.append(f"{{{child_path}}}")
        _write_section_body(child_path, v, lines, depth + 1, modifiers)


def _write_section_with_dotted_keys(
    full_path: str,
    obj: dict,
    lines: List[str],
    depth: int,
    modifiers: Optional[Dict[str, object]] = None,
):
    """Write section body where keys are dotted paths, reconstructing hierarchy."""
    # Group by first segment, preserving order
    groups: Dict[str, List[Tuple[str, DynValue]]] = {}
    # Track order of appearance: (type, key) where type is "direct" or "group"
    ordered_items: List[Tuple[str, str, Any]] = []
    seen_groups: set = set()

    for key, val in obj.items():
        dot_pos = key.find(".")
        if dot_pos >= 0:
            prefix = key[:dot_pos]
            rest = key[dot_pos + 1:]
            if prefix not in groups:
                groups[prefix] = []
                seen_groups.add(prefix)
                ordered_items.append(("group", prefix, None))
            groups[prefix].append((rest, val))
        else:
            ordered_items.append(("direct", key, val))

    # Classify items: scalars/flat-groups first, then arrays, then sections
    scalar_items: List[Tuple[str, str, Any]] = []
    array_items: List[Tuple[str, str, Any]] = []
    section_items: List[Tuple[str, str, Any]] = []

    for item_type, key, val in ordered_items:
        if item_type == "direct":
            if val.is_object():
                if _should_flatten_child(val):
                    scalar_items.append(("flat_obj", key, val))
                else:
                    section_items.append((item_type, key, val))
            elif val.is_array():
                array_items.append((item_type, key, val))
            else:
                scalar_items.append((item_type, key, val))
        else:  # group
            entries = groups[key]
            if len(entries) == 1 and _is_group_flattenable(entries):
                scalar_items.append(("flat_group", key, entries))
            else:
                section_items.append((item_type, key, None))

    # Write scalars and flat groups
    for item_type, key, val in scalar_items:
        if item_type == "direct":
            field_path = f"{full_path}.{key}"
            mod_prefix = _get_modifier_prefix(modifiers, field_path)
            lines.append(f"{key} = {mod_prefix}{_format_value(val, modifiers, field_path)}")
        elif item_type == "flat_obj":
            _flatten_object(key, val, scalars_out := [])
            for dk, dv in scalars_out:
                fp = f"{full_path}.{dk}"
                mod_prefix = _get_modifier_prefix(modifiers, fp)
                lines.append(f"{dk} = {mod_prefix}{_format_value(dv, modifiers, fp)}")
        elif item_type == "flat_group":
            entries = val
            child_path = f"{full_path}.{key}"
            k, v = entries[0]
            field_path = f"{child_path}.{k}"
            dotted_key = f"{key}.{k}"
            mod_prefix = _get_modifier_prefix(modifiers, field_path)
            lines.append(f"{dotted_key} = {mod_prefix}{_format_value(v, modifiers, field_path)}")

    # Write arrays
    for item_type, key, val in array_items:
        _write_tabular_array(val, lines, f".{key}", modifiers, full_path=f"{full_path}.{key}")

    # Write object sections and groups
    for item_type, key, val in section_items:
        if item_type == "direct":
            child_path = f"{full_path}.{key}"
            if depth == 0:
                lines.append(f"{{.{key}}}")
            else:
                lines.append(f"{{{child_path}}}")
            _write_section_body(child_path, val, lines, depth + 1, modifiers)
        else:  # group → sub-section
            entries = groups[key]
            child_path = f"{full_path}.{key}"
            has_nested = any("." in k for k, _ in entries)

            if depth == 0:
                lines.append(f"{{.{key}}}")
            else:
                lines.append(f"{{{child_path}}}")

            if has_nested:
                virtual_obj = {}
                for k, v in entries:
                    virtual_obj[k] = v
                _write_section_with_dotted_keys(child_path, virtual_obj, lines, depth + 1, modifiers)
            else:
                for k, v in entries:
                    field_path = f"{child_path}.{k}"
                    mod_prefix = _get_modifier_prefix(modifiers, field_path)
                    lines.append(f"{k} = {mod_prefix}{_format_value(v, modifiers, field_path)}")


def _shorthand_column_names(columns: List[str]) -> List[str]:
    """Convert column names to shorthand notation.

    When consecutive columns share a common dotted prefix, subsequent
    columns use .suffix notation instead of the full path.

    Examples:
        ["name.first", "name.last"] → ["name.first", ".last"]
        ["license.number", "license.state"] → ["license.number", ".state"]
        ["vin", "year"] → ["vin", "year"]  (no dots, no shorthand)
    """
    if not columns:
        return columns

    result: List[str] = []
    prev_prefix = ""

    for col in columns:
        dot_pos = col.rfind(".")
        if dot_pos >= 0:
            prefix = col[:dot_pos]
            suffix = col[dot_pos:]  # includes the dot
            if prefix == prev_prefix:
                result.append(suffix)
            else:
                result.append(col)
                prev_prefix = prefix
        else:
            result.append(col)
            prev_prefix = ""

    return result


def _write_tabular_array(
    value: DynValue,
    lines: List[str],
    prefix: str,
    modifiers: Optional[Dict[str, object]] = None,
    full_path: Optional[str] = None,
):
    """Write an array using ODIN tabular notation."""
    items = value.as_array()
    if not items:
        # Empty array → just the header with null sentinel
        lines.append(f"{{{prefix}[] : ~}}")
        lines.append("~")
        return

    # Detect item shapes
    all_objects = all(item.is_object() for item in items)
    all_arrays = all(item.is_array() for item in items)

    if all_arrays:
        _write_array_of_arrays(items, lines, prefix, modifiers)
        return

    if all_objects:
        # Records containing nested objects/arrays cannot be tabular → indexed sections.
        if full_path and any(
            any(fv.is_object() or fv.is_array() for fv in item.as_object().values())
            for item in items
        ):
            for i, item in enumerate(items):
                lines.append(f"{{{full_path}[{i}]}}")
                _write_section_body(f"{full_path}[{i}]", item, lines, depth=1, modifiers=modifiers)
            return

        # Collect column names from all rows (preserve order from first row)
        columns: List[str] = []
        seen: set = set()
        for item in items:
            for k in item.as_object().keys():
                if k not in seen:
                    columns.append(k)
                    seen.add(k)

        # Header - use shorthand notation for consecutive dotted columns
        display_columns = _shorthand_column_names(columns)
        col_list = ", ".join(display_columns)
        lines.append(f"{{{prefix}[] : {col_list}}}")

        # Rows
        for item in items:
            obj = item.as_object()
            row_vals = []
            for col in columns:
                cell = obj.get(col)
                if cell is None:
                    # Key missing from object → empty cell
                    row_vals.append("")
                elif cell.is_null():
                    # Explicit null value → tilde
                    row_vals.append("~")
                else:
                    row_vals.append(_format_value(cell, modifiers, ""))
            lines.append(", ".join(row_vals))
    else:
        # Scalar array
        lines.append(f"{{{prefix}[] : ~}}")
        for item in items:
            lines.append(_format_value(item, modifiers, ""))


def _write_array_of_arrays(
    items: List[DynValue],
    lines: List[str],
    prefix: str,
    modifiers: Optional[Dict[str, object]] = None,
):
    """Write an array whose elements are themselves arrays as a positional table.

    Scalar sub-arrays produce indexed columns ([0], [1], …); sub-arrays of records
    produce per-position field columns ([0].field). Ragged rows leave empty cells.
    """
    width = max((len(item.as_array()) for item in items), default=0)

    # Determine which positions hold records (objects) across all rows.
    record_fields: List[List[str]] = []
    for pos in range(width):
        fields: List[str] = []
        seen: set = set()
        is_record = False
        for item in items:
            sub = item.as_array()
            if pos < len(sub) and sub[pos].is_object():
                is_record = True
                for k in sub[pos].as_object().keys():
                    if k not in seen:
                        fields.append(k)
                        seen.add(k)
        record_fields.append(fields if is_record else [])

    columns: List[str] = []
    for pos in range(width):
        if record_fields[pos]:
            for f in record_fields[pos]:
                columns.append(f"[{pos}].{f}")
        else:
            columns.append(f"[{pos}]")

    display_columns = _shorthand_column_names(columns)
    lines.append(f"{{{prefix}[] : {', '.join(display_columns)}}}")

    for item in items:
        sub = item.as_array()
        row_vals: List[str] = []
        for pos in range(width):
            cell = sub[pos] if pos < len(sub) else None
            if record_fields[pos]:
                rec = cell.as_object() if (cell is not None and cell.is_object()) else {}
                for f in record_fields[pos]:
                    fv = rec.get(f)
                    if fv is None:
                        row_vals.append("")
                    elif fv.is_null():
                        row_vals.append("~")
                    else:
                        row_vals.append(_format_value(fv, modifiers, ""))
            else:
                if cell is None:
                    row_vals.append("")
                elif cell.is_null():
                    row_vals.append("~")
                else:
                    row_vals.append(_format_value(cell, modifiers, ""))
        lines.append(", ".join(row_vals))


def _format_value(
    value: DynValue,
    modifiers: Optional[Dict[str, object]] = None,
    path: str = "",
) -> str:
    """Format a scalar DynValue as an ODIN value string."""
    if value.is_null():
        return "~"
    if value.type == DynType.BOOL:
        return "?true" if value.as_bool() else "?false"
    if value.type == DynType.INTEGER:
        return f"##{value.as_int()}"
    if value.type in (DynType.FLOAT, DynType.FLOAT_RAW):
        if value.type == DynType.FLOAT_RAW:
            raw = value.as_string()
            if raw:
                return f"#{raw}"
        v = value.as_float()
        if v is not None:
            if v == int(v) and abs(v) < 1e15 and not _is_inf_or_nan(v):
                return f"#{int(v)}"
            return f"#{v}"
        return "#0"
    if value.type == DynType.STRING:
        s = value.as_string()
        return f'"{_escape_string(s)}"'
    if value.type in (DynType.CURRENCY, DynType.CURRENCY_RAW):
        return _format_currency(value)
    if value.type == DynType.PERCENT:
        v = value.as_float()
        if v is not None:
            if v == int(v) and abs(v) < 1e15 and not _is_inf_or_nan(v):
                return f"#%{int(v)}.0"
            return f"#%{v}"
        return "#%0"
    if value.type == DynType.DATE:
        return value.as_string()
    if value.type == DynType.TIMESTAMP:
        s = value.as_string()
        # Ensure .000 milliseconds are present when missing
        if s and s.endswith("Z") and "." not in s.split("T")[-1]:
            s = s[:-1] + ".000Z"
        return s
    if value.type == DynType.TIME:
        s = value.as_string()
        # ODIN times need T prefix
        if s and not s.startswith("T"):
            s = "T" + s
        return s
    if value.type == DynType.DURATION:
        return value.as_string()
    if value.type == DynType.REFERENCE:
        return f"@{value.as_string()}"
    if value.type == DynType.BINARY:
        return f"^{value.as_string()}"
    # Fallback
    return f'"{_escape_string(value.as_string())}"'


def _format_currency(value: DynValue) -> str:
    """Format a currency DynValue."""
    code = ""
    if hasattr(value, 'get_currency_code'):
        c = value.get_currency_code()
        if c:
            code = c

    if value.type == DynType.CURRENCY_RAW:
        raw = value.as_string()
        if raw:
            suffix = f":{code}" if code else ""
            return f"#${raw}{suffix}"

    v = value.as_float()
    dp = None
    if hasattr(value, 'get_decimal_places'):
        dp = value.get_decimal_places()

    if dp is not None and dp > 0:
        formatted = f"{v:.{dp}f}"
    elif v is not None and v == int(v) and abs(v) < 1e15 and not _is_inf_or_nan(v):
        formatted = f"{int(v)}.0"
    elif v is not None:
        formatted = str(v)
    else:
        formatted = "0"

    suffix = f":{code}" if code else ""
    return f"#${formatted}{suffix}"


def _get_modifier_prefix(
    modifiers: Optional[Dict[str, object]],
    path: str,
) -> str:
    """Get the modifier prefix (!*- etc.) for a field path."""
    if not modifiers or not path:
        return ""
    mod = modifiers.get(path)
    if mod is None:
        return ""
    prefix = ""
    if (hasattr(mod, 'required') and mod.required) or (hasattr(mod, 'critical') and mod.critical):
        prefix += "!"
    if hasattr(mod, 'deprecated') and mod.deprecated:
        prefix += "-"
    if hasattr(mod, 'confidential') and mod.confidential:
        prefix += "*"
    return prefix


def _escape_string(s: str) -> str:
    """Escape special characters in an ODIN string."""
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    s = s.replace("\t", "\\t")
    return s


def _is_inf_or_nan(v: float) -> bool:
    import math
    return math.isinf(v) or math.isnan(v)
