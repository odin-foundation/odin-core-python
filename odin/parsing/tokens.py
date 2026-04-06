"""Token types for ODIN tokenizer."""

from enum import IntEnum, auto
from typing import Optional


class TokenType(IntEnum):
    """All token types produced by the ODIN tokenizer.

    Uses IntEnum for faster comparisons than Enum.
    """

    # Structure
    HEADER_OPEN = auto()
    HEADER_CLOSE = auto()
    EQUALS = auto()
    NEWLINE = auto()
    EOF = auto()

    # Comments & Directives
    COMMENT = auto()
    DIRECTIVE_IMPORT = auto()
    DIRECTIVE_SCHEMA = auto()
    DIRECTIVE_COND = auto()

    # Document
    DOC_SEPARATOR = auto()

    # Identifiers & Paths
    IDENTIFIER = auto()
    ARRAY_INDEX = auto()
    DOT = auto()

    # Type Prefixes
    PREFIX_NUMBER = auto()
    PREFIX_INTEGER = auto()
    PREFIX_CURRENCY = auto()
    PREFIX_BOOLEAN = auto()
    PREFIX_REFERENCE = auto()
    PREFIX_BINARY = auto()
    PREFIX_NULL = auto()
    PREFIX_EXTENSION = auto()
    PREFIX_META = auto()
    PREFIX_VERB = auto()
    PREFIX_PERCENT = auto()

    # Modifiers
    MODIFIER_CRITICAL = auto()
    MODIFIER_REDACTED = auto()
    MODIFIER_DEPRECATED = auto()

    # Values
    STRING_BARE = auto()
    STRING_QUOTED = auto()
    NUMBER = auto()
    BOOLEAN = auto()
    DATE = auto()
    TIMESTAMP = auto()
    TIME = auto()
    DURATION = auto()
    BASE64 = auto()

    # Whitespace
    WHITESPACE = auto()

    # Error
    ERROR = auto()


class Token:
    """A single token from the ODIN tokenizer.

    Uses __slots__ instead of dataclass for lower overhead on hot paths.
    """
    __slots__ = ('type', 'value', 'line', 'column', 'raw')

    def __init__(self, type: TokenType, value: str, line: int, column: int,
                 raw: Optional[str] = None) -> None:
        self.type = type
        self.value = value
        self.line = line
        self.column = column
        self.raw = raw

    def __repr__(self) -> str:
        if self.raw is not None:
            return f"Token({self.type.name}, {self.value!r}, raw={self.raw!r}, {self.line}:{self.column})"
        return f"Token({self.type.name}, {self.value!r}, {self.line}:{self.column})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Token):
            return NotImplemented
        return (self.type == other.type and self.value == other.value
                and self.line == other.line and self.column == other.column)

    def __hash__(self) -> int:
        return hash((self.type, self.value, self.line, self.column))
