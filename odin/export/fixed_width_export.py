"""Fixed-width export - converts OdinDocument to fixed-width string."""

from __future__ import annotations

import base64
import math
from typing import Any, Dict, List, Optional

from odin.types.document import OdinDocument
from odin.types.values import (
    OdinValue, OdinNull, OdinBoolean, OdinString, OdinNumber, OdinInteger,
    OdinCurrency, OdinPercent, OdinDate, OdinTimestamp, OdinTime,
    OdinDuration, OdinReference, OdinBinary,
)


def to_fixed_width(
    doc: OdinDocument,
    fields: List[Dict[str, Any]],
    line_width: int,
    pad_char: str = " ",
) -> str:
    """Convert an OdinDocument to fixed-width string.

    Args:
        doc: The document to export
        fields: List of field specs with: path, pos, len, align (optional)
        line_width: Total line width
        pad_char: Padding character (default: space)

    Returns:
        Fixed-width string
    """
    if line_width <= 0 or not fields:
        return ""

    line = list(pad_char * line_width)

    for field in fields:
        path = field["path"]
        pos = field["pos"]
        length = field["len"]
        align = field.get("align", "left")

        value = doc.get(path)
        text = _format_value(value) if value else ""

        # Truncate if needed
        if len(text) > length:
            text = text[:length]

        if align == "right":
            # Right-align: pad on left
            padded = text.rjust(length, pad_char)
        else:
            # Left-align: pad on right
            padded = text.ljust(length, pad_char)

        # Write into line
        for j, ch in enumerate(padded):
            target = pos + j
            if target < line_width:
                line[target] = ch

    return "".join(line)


def _format_value(value: Optional[OdinValue]) -> str:
    """Format an OdinValue as a string."""
    if value is None or isinstance(value, OdinNull):
        return ""
    if isinstance(value, OdinBoolean):
        return "true" if value.value else "false"
    if isinstance(value, OdinString):
        return value.value
    if isinstance(value, OdinInteger):
        return str(value.value)
    if isinstance(value, OdinNumber):
        v = value.value
        if math.isnan(v) or math.isinf(v):
            return ""
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        return str(v)
    if isinstance(value, OdinCurrency):
        v = float(value.value)
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        return str(v)
    if isinstance(value, OdinPercent):
        v = value.value
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        return str(v)
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
    return str(value)
