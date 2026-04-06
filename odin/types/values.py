"""Value types for ODIN."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Tuple, Union


@dataclass(frozen=True, slots=True)
class OdinNull:
    """Null value (~)."""
    pass


@dataclass(frozen=True, slots=True)
class OdinBoolean:
    """Boolean value."""
    value: bool


@dataclass(frozen=True, slots=True)
class OdinString:
    """String value."""
    value: str


@dataclass(frozen=True, slots=True)
class OdinNumber:
    """Floating-point number (#prefix)."""
    value: float
    raw: Optional[str] = None


@dataclass(frozen=True, slots=True)
class OdinInteger:
    """Integer number (##prefix)."""
    value: int
    raw: Optional[str] = None


@dataclass(frozen=True, slots=True)
class OdinCurrency:
    """Currency value (#$prefix). Uses Decimal for precision."""
    value: Decimal
    currency_code: Optional[str] = None
    decimal_places: int = 2
    raw: Optional[str] = None


@dataclass(frozen=True, slots=True)
class OdinPercent:
    """Percent value (#%prefix)."""
    value: float
    raw: Optional[str] = None


@dataclass(frozen=True, slots=True)
class OdinDate:
    """Date value."""
    value: date
    raw: str = ""


@dataclass(frozen=True, slots=True)
class OdinTimestamp:
    """Timestamp value."""
    value: datetime
    raw: str = ""


@dataclass(frozen=True, slots=True)
class OdinTime:
    """Time value (stored as string like TS)."""
    value: str


@dataclass(frozen=True, slots=True)
class OdinDuration:
    """Duration value (stored as string like TS)."""
    value: str


@dataclass(frozen=True, slots=True)
class OdinReference:
    """Reference to another path (@prefix)."""
    path: str


@dataclass(frozen=True, slots=True)
class OdinBinary:
    """Binary value (^prefix, base64 encoded)."""
    data: bytes
    algorithm: Optional[str] = None


@dataclass(frozen=True, slots=True)
class OdinVerbExpression:
    """Verb expression for transforms."""
    verb: str
    is_custom: bool = False
    args: Tuple[OdinValue, ...] = ()  # type: ignore[assignment]


@dataclass(frozen=True, slots=True)
class OdinArray:
    """Array marker type (expanded to indexed paths in document)."""
    pass


@dataclass(frozen=True, slots=True)
class OdinObject:
    """Object marker type (expanded to dot paths in document)."""
    pass


# Singleton constants
NULL = OdinNull()
TRUE = OdinBoolean(True)
FALSE = OdinBoolean(False)

# Union type for all ODIN values
OdinValue = Union[
    OdinNull,
    OdinBoolean,
    OdinString,
    OdinNumber,
    OdinInteger,
    OdinCurrency,
    OdinPercent,
    OdinDate,
    OdinTimestamp,
    OdinTime,
    OdinDuration,
    OdinReference,
    OdinBinary,
    OdinVerbExpression,
    OdinArray,
    OdinObject,
]
