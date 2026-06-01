"""Transform-specific types for the ODIN transform engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from odin.types.document import OdinDocument, OdinModifiers


# ── Enums ──────────────────────────────────────────────────────────────────────


class ConfidentialMode(Enum):
    REDACT = auto()
    MASK = auto()


class DiscriminatorType(Enum):
    POSITION = auto()
    FIELD = auto()
    PATH = auto()


# ── Expression Types ───────────────────────────────────────────────────────────


@dataclass
class VerbArg:
    """Base class for verb arguments."""
    pass


@dataclass
class ReferenceArg(VerbArg):
    path: str
    directives: List[Directive] = field(default_factory=list)


@dataclass
class LiteralArg(VerbArg):
    value: Any  # OdinValue


@dataclass
class VerbCallArg(VerbArg):
    call: VerbCall


@dataclass
class VerbCall:
    verb: str = ""
    is_custom: bool = False
    args: List[VerbArg] = field(default_factory=list)


# ── Field Expression Types ─────────────────────────────────────────────────────


@dataclass
class FieldExpression:
    """Base class for field mapping expressions."""
    pass


@dataclass
class CopyExpression(FieldExpression):
    path: str = ""


@dataclass
class TransformExpression(FieldExpression):
    call: VerbCall = field(default_factory=VerbCall)


@dataclass
class LiteralExpression(FieldExpression):
    value: Any = None  # OdinValue


@dataclass
class ObjectExpression(FieldExpression):
    fields: List[FieldMapping] = field(default_factory=list)


# ── Directive ──────────────────────────────────────────────────────────────────


@dataclass
class Directive:
    name: str = ""
    value: Optional[str] = None


# ── Segment Directive ──────────────────────────────────────────────────────────


@dataclass
class SegmentDirective:
    directive_type: str = ""
    value: Optional[str] = None


# ── Field Mapping ──────────────────────────────────────────────────────────────


@dataclass
class FieldMapping:
    target: str = ""
    expression: Optional[FieldExpression] = None
    modifiers: Optional[OdinModifiers] = None
    directives: List[Directive] = field(default_factory=list)


# ── Discriminator ──────────────────────────────────────────────────────────────


@dataclass
class Discriminator:
    path: str = ""
    value: str = ""


@dataclass
class SourceDiscriminator:
    type: Optional[DiscriminatorType] = None
    pos: Optional[int] = None
    len: Optional[int] = None
    field_index: Optional[int] = None
    path: Optional[str] = None


# ── Accumulator & Table ────────────────────────────────────────────────────────


@dataclass
class AccumulatorDef:
    name: str = ""
    initial: Any = None  # OdinValue
    persist: bool = False


@dataclass
class LookupTable:
    name: str = ""
    columns: List[str] = field(default_factory=list)
    rows: List[List[Any]] = field(default_factory=list)
    default: Any = None


# ── Segment ────────────────────────────────────────────────────────────────────


@dataclass
class LoopSpec:
    """One `:loop path :as alias` declaration on a segment."""

    path: str = ""
    alias: Optional[str] = None


@dataclass
class TransformSegment:
    name: str = ""
    path: str = ""
    source_path: Optional[str] = None
    segment_discriminator: Optional[Discriminator] = None
    is_array: bool = False
    directives: List[SegmentDirective] = field(default_factory=list)
    mappings: List[FieldMapping] = field(default_factory=list)
    children: List[TransformSegment] = field(default_factory=list)
    pass_num: Optional[int] = None
    condition: Optional[str] = None
    condition_expr: Optional[FieldExpression] = None
    branch: Optional[str] = None  # 'if' | 'elif' | 'else' for conditional chains
    counter_name: Optional[str] = None  # loop counter declared via :counter
    loops: List[LoopSpec] = field(default_factory=list)  # nested :loop directives
    literal_body: Optional[str] = None  # body of a :literal segment
    is_literal: bool = False  # segment renders a literal text block


# ── Source / Target Config ─────────────────────────────────────────────────────


@dataclass
class TransformSourceConfig:
    format: str = ""
    options: Dict[str, str] = field(default_factory=dict)
    namespaces: Dict[str, str] = field(default_factory=dict)
    discriminator: Optional[SourceDiscriminator] = None


@dataclass
class TransformTargetConfig:
    format: str = ""
    options: Dict[str, str] = field(default_factory=dict)
    namespaces: Dict[str, str] = field(default_factory=dict)


# ── Metadata ───────────────────────────────────────────────────────────────────


@dataclass
class TransformMetadata:
    odin_version: Optional[str] = None
    transform_version: Optional[str] = None
    direction: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None


# ── Import Ref ─────────────────────────────────────────────────────────────────


@dataclass
class ImportRef:
    path: str = ""
    alias: Optional[str] = None


# ── Transform Result ───────────────────────────────────────────────────────────


@dataclass
class TransformError:
    message: str = ""
    path: Optional[str] = None
    code: Optional[str] = None


@dataclass
class TransformWarning:
    message: str = ""
    path: Optional[str] = None


@dataclass
class TransformResult:
    success: bool = True
    output: Any = None  # DynValue
    formatted: Optional[str] = None
    errors: List[TransformError] = field(default_factory=list)
    warnings: List[TransformWarning] = field(default_factory=list)
    output_modifiers: Dict[str, OdinModifiers] = field(default_factory=dict)


# ── OdinTransform ──────────────────────────────────────────────────────────────


@dataclass
class OdinTransform:
    metadata: TransformMetadata = field(default_factory=TransformMetadata)
    source: Optional[TransformSourceConfig] = None
    target: TransformTargetConfig = field(default_factory=TransformTargetConfig)
    constants: Dict[str, Any] = field(default_factory=dict)
    accumulators: Dict[str, AccumulatorDef] = field(default_factory=dict)
    tables: Dict[str, LookupTable] = field(default_factory=dict)
    segments: List[TransformSegment] = field(default_factory=list)
    imports: List[ImportRef] = field(default_factory=list)
    passes: List[int] = field(default_factory=list)
    enforce_confidential: Optional[ConfidentialMode] = None
    strict_types: bool = False
