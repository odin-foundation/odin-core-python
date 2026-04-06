"""Fixed-width source parser - converts fixed-width text to DynValue."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from odin.transform.dyn_value import DynValue


def parse_fixed_width(
    source: str,
    fields: Optional[List[Dict[str, Any]]] = None,
) -> DynValue:
    """Parse fixed-width input to DynValue tree.

    Args:
        source: Fixed-width text
        fields: List of field definitions, each with:
            - name: field name
            - pos: start position (0-based)
            - len: field width
            - type: optional ('string', 'integer', 'number', 'date')
            - implied_decimals: optional int for implied decimal places

    Returns:
        DynValue object (single record) or array of objects (multiple records)
    """
    if not source.strip():
        return DynValue.of_array([])

    lines = [line.rstrip('\r') for line in source.split('\n') if line.strip()]

    if fields is None:
        # No field definitions: return array of string lines
        return DynValue.of_array([DynValue.of_string(line) for line in lines])

    records = []
    for line in lines:
        obj: Dict[str, DynValue] = {}
        for field in fields:
            name = field["name"]
            pos = field["pos"]
            length = field["len"]
            field_type = field.get("type", "string")
            implied_decimals = field.get("implied_decimals", 0)

            raw = line[pos:pos + length] if pos < len(line) else ""
            raw = raw.rstrip()

            obj[name] = _convert_field(raw, field_type, implied_decimals)
        records.append(DynValue.of_object(obj))

    if len(records) == 1:
        return records[0]
    return DynValue.of_array(records)


def _convert_field(raw: str, field_type: str, implied_decimals: int) -> DynValue:
    """Convert a raw field value based on type."""
    if not raw:
        if field_type in ("integer", "number"):
            return DynValue.of_null()
        return DynValue.of_string(raw) if field_type == "string" else DynValue.of_null()

    if field_type == "integer":
        try:
            return DynValue.of_integer(int(raw))
        except ValueError:
            return DynValue.of_null()

    if field_type == "number":
        try:
            val = float(raw)
            if implied_decimals:
                val = val / (10 ** implied_decimals)
            return DynValue.of_float(val)
        except ValueError:
            return DynValue.of_null()

    if field_type == "date":
        # YYYYMMDD -> YYYY-MM-DD
        if len(raw) == 8 and raw.isdigit():
            return DynValue.of_string(f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}")
        return DynValue.of_string(raw)

    return DynValue.of_string(raw)
