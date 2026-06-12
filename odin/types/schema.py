"""Schema types for ODIN validation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


# ─────────────────────────────────────────────────────────────────────────────
# Field Type Kinds
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class StringType:
    kind: str = "string"


@dataclass(frozen=True)
class BooleanType:
    kind: str = "boolean"


@dataclass(frozen=True)
class NumberType:
    kind: str = "number"


@dataclass(frozen=True)
class IntegerType:
    kind: str = "integer"


@dataclass(frozen=True)
class DecimalType:
    places: int = 2
    kind: str = "decimal"


@dataclass(frozen=True)
class CurrencyType:
    places: int = 2
    kind: str = "currency"


@dataclass(frozen=True)
class PercentType:
    kind: str = "percent"


@dataclass(frozen=True)
class DateType:
    kind: str = "date"


@dataclass(frozen=True)
class TimestampType:
    kind: str = "timestamp"


@dataclass(frozen=True)
class TimeType:
    kind: str = "time"


@dataclass(frozen=True)
class DurationType:
    kind: str = "duration"


@dataclass(frozen=True)
class ReferenceType:
    target_path: Optional[str] = None
    kind: str = "reference"


@dataclass(frozen=True)
class BinaryType:
    algorithm: Optional[str] = None
    kind: str = "binary"


@dataclass(frozen=True)
class NullType:
    kind: str = "null"


@dataclass(frozen=True)
class EnumType:
    values: List[str] = field(default_factory=list)
    kind: str = "enum"


@dataclass(frozen=True)
class UnionType:
    types: List[SchemaFieldType] = field(default_factory=list)
    kind: str = "union"


@dataclass(frozen=True)
class TypeRefType:
    name: str = ""
    override: bool = False
    kind: str = "typeRef"


SchemaFieldType = Union[
    StringType, BooleanType, NumberType, IntegerType, DecimalType,
    CurrencyType, PercentType, DateType, TimestampType, TimeType,
    DurationType, ReferenceType, BinaryType, NullType, EnumType,
    UnionType, TypeRefType,
]


# ─────────────────────────────────────────────────────────────────────────────
# Constraints
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BoundsConstraint:
    min: Optional[Union[int, float, str]] = None
    max: Optional[Union[int, float, str]] = None
    kind: str = "bounds"


@dataclass(frozen=True)
class PatternConstraint:
    pattern: str = ""
    kind: str = "pattern"


@dataclass(frozen=True)
class EnumConstraint:
    values: List[str] = field(default_factory=list)
    kind: str = "enum"


@dataclass(frozen=True)
class SizeConstraint:
    min: Optional[int] = None
    max: Optional[int] = None
    kind: str = "size"


@dataclass(frozen=True)
class FormatConstraint:
    format: str = ""
    kind: str = "format"


@dataclass(frozen=True)
class UniqueConstraint:
    kind: str = "unique"


SchemaConstraint = Union[
    BoundsConstraint, PatternConstraint, EnumConstraint,
    SizeConstraint, FormatConstraint, UniqueConstraint,
]


# ─────────────────────────────────────────────────────────────────────────────
# Conditionals
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SchemaConditional:
    field: str = ""
    operator: str = "="
    value: Union[str, int, float, bool] = ""
    unless: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Fields, Types, Arrays
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SchemaField:
    path: str = ""
    field_type: SchemaFieldType = field(default_factory=StringType)
    required: bool = False
    nullable: bool = False
    redacted: bool = False
    deprecated: bool = False
    computed: bool = False
    immutable: bool = False
    constraints: List[SchemaConstraint] = field(default_factory=list)
    conditionals: List[SchemaConditional] = field(default_factory=list)
    default_value: Optional[Any] = None
    description: Optional[str] = None


@dataclass
class SchemaType:
    name: str = ""
    fields: Dict[str, SchemaField] = field(default_factory=dict)
    base_type: Optional[str] = None
    # Array-of-object entries declared inside the type, keyed by array name
    # (e.g. `producers` for `producers[] = @t` or `producers[].field`).
    arrays: Dict[str, "SchemaArray"] = field(default_factory=dict)


@dataclass
class SchemaArray:
    path: str = ""
    min_items: Optional[int] = None
    max_items: Optional[int] = None
    unique: bool = False
    item_fields: Dict[str, SchemaField] = field(default_factory=dict)
    columns: Optional[List[str]] = None
    # For an `arr[] = @type` declaration, entry fields come from this type,
    # resolved at validation time. Empty item_fields plus this ref.
    item_type_ref: Optional[str] = None


@dataclass
class SchemaImport:
    """An @import directive with its declared alias."""
    path: str = ""
    alias: Optional[str] = None
    line: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# Object-Level Constraints
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SchemaInvariant:
    expression: str = ""
    kind: str = "invariant"


@dataclass(frozen=True)
class SchemaCardinality:
    cardinality_type: str = "one_of"  # one_of, exactly_one, at_most_one, of
    fields: List[str] = field(default_factory=list)
    min: Optional[int] = None
    max: Optional[int] = None
    kind: str = "cardinality"


SchemaObjectConstraint = Union[SchemaInvariant, SchemaCardinality]


# ─────────────────────────────────────────────────────────────────────────────
# Schema Definition
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class OdinSchema:
    """Parsed ODIN Schema."""

    metadata: Dict[str, str] = field(default_factory=dict)
    types: Dict[str, SchemaType] = field(default_factory=dict)
    fields: Dict[str, SchemaField] = field(default_factory=dict)
    arrays: Dict[str, SchemaArray] = field(default_factory=dict)
    imports: List[SchemaImport] = field(default_factory=list)
    constraints: Dict[str, List[SchemaObjectConstraint]] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Validation Results
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ValidationError:
    """Validation error."""

    path: str
    """Path where error occurred."""

    code: str
    """Error code (V001-V099)."""

    message: str
    """Human-readable message."""

    expected: Optional[Any] = None
    """What was expected."""

    actual: Optional[Any] = None
    """What was found."""

    schema_path: Optional[str] = None
    """Path in schema where constraint is defined."""


@dataclass(frozen=True)
class ValidationWarning:
    """Validation warning."""

    path: str
    """Path where warning applies."""

    code: str
    """Warning code."""

    message: str
    """Human-readable message."""


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating a document against a schema."""

    valid: bool
    """Whether the document is valid."""

    errors: List[ValidationError] = field(default_factory=list)
    """Validation errors (if any)."""

    warnings: List[ValidationWarning] = field(default_factory=list)
    """Validation warnings (if any)."""
