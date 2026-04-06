"""JSON source parser - converts JSON string/dict/list to DynValue tree."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Union

from odin.transform.dyn_value import DynValue


def parse_json(source: Union[str, dict, list, Any]) -> DynValue:
    """Parse JSON input to DynValue tree.

    Args:
        source: JSON string, dict, or list

    Returns:
        DynValue tree

    Raises:
        ValueError: If input is invalid JSON
    """
    if isinstance(source, str):
        if not source.strip():
            raise ValueError("JSON parse error: empty input")
        try:
            source = json.loads(source)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON parse error: {e}") from e
    return _convert(source)


def _convert(value: Any) -> DynValue:
    """Convert a Python value to DynValue."""
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
        return DynValue.of_array([_convert(v) for v in value])
    if isinstance(value, dict):
        return DynValue.of_object({k: _convert(v) for k, v in value.items()})
    return DynValue.of_string(str(value))
