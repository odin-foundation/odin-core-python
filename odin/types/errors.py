"""Error types for ODIN."""

from typing import Any, Dict, Optional


class OdinError(Exception):
    """Base exception for all ODIN operations."""

    def __init__(
        self,
        message: str,
        code: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.context = context or {}


class ParseError(OdinError):
    """Exception during parsing."""

    def __init__(
        self,
        message: str,
        code: str,
        line: int,
        column: int,
    ) -> None:
        super().__init__(
            f"{message} at line {line}, column {column}",
            code,
            {"line": line, "column": column},
        )
        self.line = line
        self.column = column


class PatchError(OdinError):
    """Exception during patching."""

    def __init__(self, message: str, path: str) -> None:
        super().__init__(message, "PATCH_ERROR", {"path": path})
        self.path = path


# ─────────────────────────────────────────────────────────────────────────────
# Error Codes
# ─────────────────────────────────────────────────────────────────────────────


class ParseErrorCodes:
    """Parse error codes (P001-P099)."""

    P001 = "P001"  # Unexpected character
    P002 = "P002"  # Invalid path segment
    P003 = "P003"  # Invalid array index
    P004 = "P004"  # Unterminated string
    P005 = "P005"  # Invalid escape sequence
    P006 = "P006"  # Invalid type prefix
    P007 = "P007"  # Duplicate path assignment
    P008 = "P008"  # Invalid header syntax
    P009 = "P009"  # Invalid directive
    P010 = "P010"  # Maximum depth exceeded
    P011 = "P011"  # Maximum document size exceeded
    P012 = "P012"  # Invalid UTF-8 sequence
    P013 = "P013"  # Non-contiguous array indices
    P014 = "P014"  # Empty document
    P015 = "P015"  # Array index out of range


class ValidationErrorCodes:
    """Validation error codes (V001-V099)."""

    V001 = "V001"  # Required field missing
    V002 = "V002"  # Type mismatch
    V003 = "V003"  # Value out of bounds
    V004 = "V004"  # Pattern mismatch
    V005 = "V005"  # Invalid enum value
    V006 = "V006"  # Array length violation
    V007 = "V007"  # Unique constraint violation
    V008 = "V008"  # Invariant violation
    V009 = "V009"  # Cardinality constraint violation
    V010 = "V010"  # Conditional requirement not met
    V011 = "V011"  # Unknown field
    V012 = "V012"  # Circular reference
    V013 = "V013"  # Unresolved reference
