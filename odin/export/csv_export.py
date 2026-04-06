"""CSV export - converts OdinDocument to CSV string."""

from __future__ import annotations

import base64
import math
import re
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Set, Tuple

from odin.types.document import OdinDocument
from odin.types.values import (
    OdinValue, OdinNull, OdinBoolean, OdinString, OdinNumber, OdinInteger,
    OdinCurrency, OdinPercent, OdinDate, OdinTimestamp, OdinTime,
    OdinDuration, OdinReference, OdinBinary, OdinArray, OdinObject,
)


def to_csv(
    doc: OdinDocument,
    array_path: Optional[str] = None,
    delimiter: str = ",",
    include_header: bool = True,
) -> str:
    """Convert an OdinDocument to CSV string.

    Args:
        doc: The document to export
        array_path: Optional path prefix for array detection
        delimiter: Field delimiter
        include_header: Whether to include header row

    Returns:
        CSV string
    """
    rows, columns = _collect_rows(doc, array_path)

    if not rows and not columns:
        # Single-row fallback
        rows, columns = _single_row_fallback(doc)

    if not columns:
        return ""

    parts: List[str] = []
    if include_header:
        parts.append(delimiter.join(_escape_csv(c, delimiter) for c in columns))

    for row in rows:
        fields = []
        for col in columns:
            val = row.get(col)
            fields.append(_escape_csv(_format_value(val) if val is not None else "", delimiter))
        parts.append(delimiter.join(fields))

    return "\n".join(parts) + "\n"


def _collect_rows(
    doc: OdinDocument, array_path: Optional[str]
) -> Tuple[List[Dict[str, str]], List[str]]:
    """Collect array rows from document assignments."""
    pattern = re.compile(r'^(.+?)\[(\d+)]\.(.+)$')
    rows_by_index: Dict[int, Dict[str, Any]] = {}
    columns: List[str] = []
    seen_columns: Set[str] = set()
    detected_prefix: Optional[str] = None

    for path, value in doc.assignments.items():
        if path.startswith("$"):
            continue
        m = pattern.match(path)
        if not m:
            continue

        prefix, idx_str, field = m.group(1), m.group(2), m.group(3)
        if array_path and prefix != array_path:
            continue
        if detected_prefix is None:
            detected_prefix = prefix
        if prefix != detected_prefix:
            continue

        idx = int(idx_str)
        if idx not in rows_by_index:
            rows_by_index[idx] = {}
        rows_by_index[idx][field] = value

        if field not in seen_columns:
            seen_columns.add(field)
            columns.append(field)

    if not rows_by_index:
        return [], []

    rows = []
    for idx in sorted(rows_by_index.keys()):
        row = {}
        for col in columns:
            val = rows_by_index[idx].get(col)
            if val is not None:
                row[col] = _format_value(val)
        rows.append(row)

    return rows, columns


def _single_row_fallback(doc: OdinDocument) -> Tuple[List[Dict[str, str]], List[str]]:
    """Fallback: treat all non-array, non-header assignments as a single row."""
    columns: List[str] = []
    row: Dict[str, str] = {}

    for path, value in doc.assignments.items():
        if path.startswith("$") or "[" in path:
            continue
        # Use last segment as column name
        parts = path.split(".")
        col = parts[-1]
        if col not in row:
            columns.append(col)
        row[col] = _format_value(value)

    if not row:
        return [], []
    return [row], columns


def _format_value(value: Any) -> str:
    """Format an OdinValue as a string for CSV."""
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


def _escape_csv(value: str, delimiter: str) -> str:
    """Escape a CSV field value."""
    if not value:
        return value
    needs_quote = delimiter in value or '"' in value or '\n' in value or '\r' in value
    if needs_quote:
        return '"' + value.replace('"', '""') + '"'
    return value
