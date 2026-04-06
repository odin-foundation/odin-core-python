"""Dynamic value type for the transform engine.

DynValue is the intermediate representation used by source parsers and formatters.
It is mutable and untyped, unlike OdinValue which is immutable and typed.
"""

from __future__ import annotations

import base64
from datetime import date, datetime
from decimal import Decimal
from enum import Enum, auto
from typing import Dict, List, Optional, Union


class DynType(Enum):
    NULL = auto()
    BOOL = auto()
    INTEGER = auto()
    FLOAT = auto()
    FLOAT_RAW = auto()
    STRING = auto()
    ARRAY = auto()
    OBJECT = auto()
    DATE = auto()
    TIMESTAMP = auto()
    TIME = auto()
    DURATION = auto()
    CURRENCY = auto()
    CURRENCY_RAW = auto()
    PERCENT = auto()
    REFERENCE = auto()
    BINARY = auto()


class DynValue:
    """Dynamic value for the transform engine."""

    __slots__ = (
        "type", "_bool_value", "_int_value", "_float_value",
        "_string_value", "_array_value", "_object_value",
        "_currency_code", "_decimal_places", "_bytes_value",
        "_algorithm", "_raw_source",
    )

    def __init__(self, type: DynType):
        self.type = type
        self._bool_value: bool = False
        self._int_value: int = 0
        self._float_value: float = 0.0
        self._string_value: Optional[str] = None
        self._array_value: Optional[List[DynValue]] = None
        self._object_value: Optional[Dict[str, DynValue]] = None
        self._currency_code: Optional[str] = None
        self._decimal_places: int = 2
        self._bytes_value: Optional[bytes] = None
        self._algorithm: Optional[str] = None
        self._raw_source: Optional[str] = None

    # ── Factory Methods ───────────────────────────────────────────────────

    @staticmethod
    def of_null() -> DynValue:
        return DynValue(DynType.NULL)

    @staticmethod
    def of_bool(v: bool) -> DynValue:
        dv = DynValue(DynType.BOOL)
        dv._bool_value = v
        return dv

    @staticmethod
    def of_integer(v: int) -> DynValue:
        dv = DynValue(DynType.INTEGER)
        dv._int_value = v
        return dv

    @staticmethod
    def of_float(v: float) -> DynValue:
        dv = DynValue(DynType.FLOAT)
        dv._float_value = v
        return dv

    @staticmethod
    def of_float_raw(v: str) -> DynValue:
        dv = DynValue(DynType.FLOAT_RAW)
        dv._string_value = v
        return dv

    @staticmethod
    def of_string(v: str) -> DynValue:
        dv = DynValue(DynType.STRING)
        dv._string_value = v
        return dv

    @staticmethod
    def of_array(items: List[DynValue]) -> DynValue:
        dv = DynValue(DynType.ARRAY)
        dv._array_value = list(items)
        return dv

    @staticmethod
    def of_object(fields: Dict[str, DynValue]) -> DynValue:
        dv = DynValue(DynType.OBJECT)
        dv._object_value = dict(fields)
        return dv

    @staticmethod
    def of_date(v: date) -> DynValue:
        dv = DynValue(DynType.DATE)
        dv._string_value = v.isoformat()
        return dv

    @staticmethod
    def of_timestamp(v: datetime) -> DynValue:
        dv = DynValue(DynType.TIMESTAMP)
        dv._string_value = v.isoformat()
        return dv

    @staticmethod
    def of_time(v: str) -> DynValue:
        dv = DynValue(DynType.TIME)
        dv._string_value = v
        return dv

    @staticmethod
    def of_duration(v: str) -> DynValue:
        dv = DynValue(DynType.DURATION)
        dv._string_value = v
        return dv

    @staticmethod
    def of_currency(v: Decimal, code: Optional[str] = None, dp: int = 2) -> DynValue:
        dv = DynValue(DynType.CURRENCY)
        dv._float_value = float(v)
        dv._currency_code = code
        dv._decimal_places = dp
        return dv

    @staticmethod
    def of_percent(v: float) -> DynValue:
        dv = DynValue(DynType.PERCENT)
        dv._float_value = v
        return dv

    @staticmethod
    def of_reference(path: str) -> DynValue:
        dv = DynValue(DynType.REFERENCE)
        dv._string_value = path
        return dv

    @staticmethod
    def of_binary(data: bytes, algorithm: Optional[str] = None) -> DynValue:
        dv = DynValue(DynType.BINARY)
        dv._bytes_value = data
        dv._algorithm = algorithm
        dv._string_value = base64.b64encode(data).decode("ascii")
        return dv

    # ── Accessors ─────────────────────────────────────────────────────────

    def as_string(self) -> str:
        if self.type == DynType.STRING:
            return self._string_value or ""
        if self.type == DynType.INTEGER:
            return str(self._int_value)
        if self.type == DynType.FLOAT:
            return _format_float(self._float_value)
        if self.type == DynType.BOOL:
            return "true" if self._bool_value else "false"
        if self.type == DynType.NULL:
            return ""
        if self.type in (
            DynType.DATE, DynType.TIMESTAMP, DynType.TIME,
            DynType.DURATION, DynType.REFERENCE, DynType.FLOAT_RAW,
            DynType.CURRENCY_RAW,
        ):
            return self._string_value or ""
        if self.type == DynType.CURRENCY:
            return _format_float(self._float_value)
        if self.type == DynType.PERCENT:
            return _format_float(self._float_value)
        if self.type == DynType.BINARY:
            return self._string_value or ""
        return ""

    def as_int(self) -> int:
        if self.type == DynType.INTEGER:
            return self._int_value
        if self.type == DynType.FLOAT:
            return int(self._float_value)
        if self.type == DynType.FLOAT_RAW:
            return int(float(self._string_value or "0"))
        if self.type == DynType.STRING:
            try:
                return int(self._string_value or "0")
            except ValueError:
                return 0
        return 0

    def as_float(self) -> float:
        if self.type == DynType.FLOAT:
            return self._float_value
        if self.type == DynType.INTEGER:
            return float(self._int_value)
        if self.type == DynType.CURRENCY:
            return self._float_value
        if self.type == DynType.PERCENT:
            return self._float_value
        if self.type == DynType.FLOAT_RAW:
            try:
                return float(self._string_value or "0")
            except ValueError:
                return 0.0
        if self.type == DynType.STRING:
            try:
                return float(self._string_value or "0")
            except ValueError:
                return 0.0
        return 0.0

    def as_bool(self) -> bool:
        if self.type == DynType.BOOL:
            return self._bool_value
        if self.type == DynType.INTEGER:
            return self._int_value != 0
        if self.type == DynType.STRING:
            return (self._string_value or "").lower() in ("true", "yes", "1")
        return False

    def as_array(self) -> List[DynValue]:
        if self.type == DynType.ARRAY:
            if self._array_value is None:
                self._array_value = []
            return self._array_value
        return []

    def as_object(self) -> Dict[str, DynValue]:
        if self.type == DynType.OBJECT:
            if self._object_value is None:
                self._object_value = {}
            return self._object_value
        return {}

    def get(self, key: str) -> Optional[DynValue]:
        if self.type == DynType.OBJECT and self._object_value:
            return self._object_value.get(key)
        return None

    def get_index(self, index: int) -> Optional[DynValue]:
        if self.type == DynType.ARRAY and self._array_value:
            if 0 <= index < len(self._array_value):
                return self._array_value[index]
        return None

    def get_currency_code(self) -> Optional[str]:
        return self._currency_code

    def get_decimal_places(self) -> int:
        return self._decimal_places

    def get_algorithm(self) -> Optional[str]:
        return self._algorithm

    # ── Type Checks ───────────────────────────────────────────────────────

    def is_null(self) -> bool:
        return self.type == DynType.NULL

    def is_bool(self) -> bool:
        return self.type == DynType.BOOL

    def is_integer(self) -> bool:
        return self.type == DynType.INTEGER

    def is_float(self) -> bool:
        return self.type in (DynType.FLOAT, DynType.FLOAT_RAW)

    def is_number(self) -> bool:
        return self.type in (DynType.INTEGER, DynType.FLOAT, DynType.FLOAT_RAW, DynType.CURRENCY, DynType.PERCENT)

    def is_string(self) -> bool:
        return self.type == DynType.STRING

    def is_array(self) -> bool:
        return self.type == DynType.ARRAY

    def is_object(self) -> bool:
        return self.type == DynType.OBJECT

    def is_temporal(self) -> bool:
        return self.type in (DynType.DATE, DynType.TIMESTAMP, DynType.TIME, DynType.DURATION)

    def __repr__(self) -> str:
        if self.type == DynType.NULL:
            return "DynValue(null)"
        if self.type == DynType.BOOL:
            return f"DynValue({self._bool_value})"
        if self.type == DynType.INTEGER:
            return f"DynValue(int={self._int_value})"
        if self.type == DynType.FLOAT:
            return f"DynValue(float={self._float_value})"
        if self.type == DynType.STRING:
            return f"DynValue(str={self._string_value!r})"
        if self.type == DynType.ARRAY:
            return f"DynValue(array[{len(self._array_value or [])}])"
        if self.type == DynType.OBJECT:
            return f"DynValue(object{{{len(self._object_value or {})}}})"
        return f"DynValue({self.type.name}={self._string_value!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DynValue):
            return NotImplemented
        if self.type != other.type:
            return False
        if self.type == DynType.NULL:
            return True
        if self.type == DynType.BOOL:
            return self._bool_value == other._bool_value
        if self.type == DynType.INTEGER:
            return self._int_value == other._int_value
        if self.type in (DynType.FLOAT, DynType.CURRENCY, DynType.PERCENT):
            return self._float_value == other._float_value
        if self.type in (DynType.STRING, DynType.DATE, DynType.TIMESTAMP,
                         DynType.TIME, DynType.DURATION, DynType.REFERENCE,
                         DynType.FLOAT_RAW, DynType.CURRENCY_RAW):
            return self._string_value == other._string_value
        if self.type == DynType.ARRAY:
            return self._array_value == other._array_value
        if self.type == DynType.OBJECT:
            return self._object_value == other._object_value
        return False

    def __hash__(self) -> int:
        if self.type == DynType.NULL:
            return hash(DynType.NULL)
        if self.type == DynType.BOOL:
            return hash((DynType.BOOL, self._bool_value))
        if self.type == DynType.INTEGER:
            return hash((DynType.INTEGER, self._int_value))
        if self.type in (DynType.FLOAT, DynType.CURRENCY, DynType.PERCENT):
            return hash((self.type, self._float_value))
        if self.type == DynType.ARRAY:
            return hash((DynType.ARRAY, id(self._array_value)))
        if self.type == DynType.OBJECT:
            return hash((DynType.OBJECT, id(self._object_value)))
        return hash((self.type, self._string_value))


def _format_float(v: float) -> str:
    """Format a float, removing trailing .0 for whole numbers."""
    if v == v and abs(v) < 1e15 and v == int(v):
        return str(int(v))
    return str(v)
