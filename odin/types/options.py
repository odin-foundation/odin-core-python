"""Options types for ODIN operations."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class LineEnding(Enum):
    """Line ending style."""

    LF = "LF"
    CRLF = "CRLF"


@dataclass
class ParseOptions:
    """Options for parsing ODIN text."""

    continue_on_error: bool = False
    """Continue parsing after errors (collect all errors)."""

    preserve_comments: bool = False
    """Preserve comments for round-trip."""

    preserve_whitespace: bool = False
    """Preserve original whitespace/formatting."""

    max_document_size: int = 100 * 1024 * 1024  # 100MB
    """Maximum document size in bytes."""

    max_nesting_depth: int = 64
    """Maximum nesting depth."""


@dataclass
class DumpOptions:
    """Options for serializing to ODIN text."""

    pretty: bool = False
    """Human-readable formatting with headers."""

    line_ending: LineEnding = LineEnding.LF
    """Line ending style."""

    include_comments: bool = False
    """Include preserved comments."""

    sort_paths: bool = False
    """Sort paths alphabetically."""

    use_headers: bool = True
    """Group paths under section headers."""

    use_tabular: bool = True
    """Use tabular format for eligible arrays."""

    indent: str = "  "
    """Indentation for pretty mode."""


@dataclass
class ValidateOptions:
    """Options for validation."""

    fail_fast: bool = False
    """Stop on first error."""

    strict: bool = False
    """Treat unknown fields as errors."""

    include_warnings: bool = True
    """Include warnings in result."""
