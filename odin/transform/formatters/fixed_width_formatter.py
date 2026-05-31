"""Fixed-width formatter - converts DynValue to fixed-width string."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from odin.transform.dyn_value import DynValue, DynType


def format_fixed_width(
    value: DynValue,
    transform=None,
) -> str:
    """Format a DynValue as fixed-width text using transform segment metadata.

    Args:
        value: DynValue object (output from transform engine)
        transform: OdinTransform with segment/mapping metadata

    Returns:
        Fixed-width string
    """
    if transform is None:
        return ""

    # A configured lineWidth pads every record to that width with padChar.
    target_line_width: Optional[int] = None
    pad_char = " "
    opts = transform.target.options
    if opts.get("lineWidth"):
        try:
            target_line_width = int(opts["lineWidth"])
        except (ValueError, TypeError):
            target_line_width = None
    if opts.get("padChar"):
        pc = opts["padChar"]
        if pc:
            pad_char = pc[0]

    lines: List[str] = []
    _process_segments(value, transform.segments, lines, target_line_width, pad_char)
    if lines:
        return "\n".join(lines) + "\n"
    return ""


def _process_segments(
    output: DynValue,
    segments: list,
    lines: List[str],
    target_line_width: Optional[int] = None,
    pad_char: str = " ",
):
    """Process segments to produce fixed-width lines."""
    for segment in segments:
        name = segment.name
        is_array = name.endswith("[]") or segment.source_path is not None
        clean_name = name[:-2] if name.endswith("[]") else name

        # Extract field layout from segment mappings
        field_layout = _extract_field_layout(segment)
        if not field_layout:
            continue

        # Calculate line width from max(pos + len)
        line_width = 0
        for fl in field_layout:
            end = fl["pos"] + fl["len"]
            if end > line_width:
                line_width = end

        if is_array and clean_name:
            # Array segment: one line per item
            arr = _get_nested(output, clean_name)
            if arr is not None and arr.is_array():
                for item in arr.as_array():
                    line = _format_record(item, field_layout, line_width)
                    lines.append(_finalize_line(line, target_line_width, pad_char))
        else:
            # Single segment: one line
            seg_data = _get_nested(output, clean_name) if clean_name else output
            if seg_data is not None and seg_data.is_object():
                line = _format_record(seg_data, field_layout, line_width)
                lines.append(_finalize_line(line, target_line_width, pad_char))

        # Process child segments
        if segment.children:
            _process_segments(output, segment.children, lines, target_line_width, pad_char)


def _finalize_line(line: str, target_line_width: Optional[int], pad_char: str) -> str:
    """Pad a record to the configured line width, else trim trailing spaces."""
    if target_line_width is not None:
        if len(line) < target_line_width:
            return line + pad_char * (target_line_width - len(line))
        return line[:target_line_width]
    return line.rstrip()


def _extract_field_layout(segment) -> List[Dict[str, Any]]:
    """Extract field position/length metadata from segment mappings."""
    fields = []
    for mapping in segment.mappings:
        if mapping.target.startswith("_"):
            continue  # Skip directives like _type, _loop

        pos = None
        length = None
        left_pad = None
        right_pad = None

        for d in mapping.directives:
            if d.name == "pos" and d.value:
                try:
                    pos = int(d.value)
                except ValueError:
                    pass
            elif d.name == "len" and d.value:
                try:
                    length = int(d.value)
                except ValueError:
                    pass
            elif d.name == "leftPad" and d.value:
                left_pad = d.value
            elif d.name == "rightPad" and d.value:
                right_pad = d.value

        if pos is not None and length is not None:
            fields.append({
                "name": mapping.target,
                "pos": pos,
                "len": length,
                "leftPad": left_pad,
                "rightPad": right_pad,
            })

    return fields


def _format_record(
    value: DynValue,
    fields: List[Dict[str, Any]],
    line_width: int,
) -> str:
    """Format a single record as a fixed-width line."""
    line = [" "] * line_width

    obj = value.as_object() if value.is_object() else {}
    for field in sorted(fields, key=lambda f: f["pos"]):
        name = field["name"]
        pos = field["pos"]
        length = field["len"]
        left_pad = field.get("leftPad")
        right_pad = field.get("rightPad")

        val = obj.get(name)
        text = _format_value(val) if val else ""

        # Truncate if too long
        if len(text) > length:
            text = text[:length]

        # Pad
        if left_pad:
            pad_char = left_pad if len(left_pad) == 1 else left_pad[0]
            text = text.rjust(length, pad_char)
        elif right_pad:
            pad_char = right_pad if len(right_pad) == 1 else right_pad[0]
            text = text.ljust(length, pad_char)
        else:
            # Default: right-pad with spaces for strings, left-pad with spaces for numbers
            text = text.ljust(length)

        # Place into line
        for j, ch in enumerate(text):
            target = pos + j
            if target < line_width:
                line[target] = ch

    return "".join(line)


def _get_nested(value: DynValue, path: str) -> Optional[DynValue]:
    """Get a nested value by dotted path."""
    if not path:
        return value
    parts = path.split(".")
    current = value
    for part in parts:
        if current is None or not current.is_object():
            return None
        obj = current.as_object()
        current = obj.get(part)
    return current


def _format_value(value: Optional[DynValue]) -> str:
    """Convert a DynValue to its string representation."""
    if value is None or value.is_null():
        return ""
    if value.type == DynType.BOOL:
        return "true" if value.as_bool() else "false"
    if value.type == DynType.INTEGER:
        return str(value.as_int())
    if value.type in (DynType.FLOAT, DynType.FLOAT_RAW):
        v = value.as_float()
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        return str(v)
    return value.as_string()
