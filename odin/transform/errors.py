"""ODIN Transform Error Codes.

Standardized error codes (T001-T011) for transform operations.
These codes are consistent across all ODIN implementations.
"""

from __future__ import annotations

from odin.transform.types import TransformError


# ── Error Code Constants ──────────────────────────────────────────────────────

class TransformErrorCodes:
    """Transform error codes as defined in the ODIN specification.

    T001-T010 are reserved for core transform errors.
    Higher codes (T011+) are for verb-level / implementation-specific errors.
    """

    # Unknown verb - the specified verb does not exist
    T001_UNKNOWN_VERB = "T001"

    # Invalid verb arguments - wrong number or type of arguments
    T002_INVALID_VERB_ARGS = "T002"

    # Lookup table not found - referenced table doesn't exist
    T003_LOOKUP_TABLE_NOT_FOUND = "T003"

    # Lookup key not found - key doesn't exist in table
    T004_LOOKUP_KEY_NOT_FOUND = "T004"

    # Source path not found - cannot resolve source path
    T005_SOURCE_PATH_NOT_FOUND = "T005"

    # Invalid output format - unsupported or misconfigured format
    T006_INVALID_OUTPUT_FORMAT = "T006"

    # Invalid modifier for format - modifier not applicable to target format
    T007_INVALID_MODIFIER = "T007"

    # Accumulator overflow - accumulator value exceeds limits
    T008_ACCUMULATOR_OVERFLOW = "T008"

    # Loop source not array - :loop directive target is not an array
    T009_LOOP_SOURCE_NOT_ARRAY = "T009"

    # Position/length exceeds line width - fixed-width field extends past line
    T010_POSITION_OVERFLOW = "T010"

    # Incompatible or unknown conversion target
    T011_INCOMPATIBLE_CONVERSION = "T011"

    # Extended codes (implementation-specific)
    CONFIG_ERROR = "CONFIG_ERROR"
    UNKNOWN_RECORD_TYPE = "UNKNOWN_RECORD_TYPE"
    TRANSFORM_ERROR = "TRANSFORM_ERROR"
    SOURCE_MISSING = "SOURCE_MISSING"
    VALUE_OVERFLOW = "VALUE_OVERFLOW"


# ── Error Factory Functions ───────────────────────────────────────────────────


def unknown_verb_error(verb: str, field: str | None = None) -> TransformError:
    """Create a T001 Unknown Verb error."""
    return TransformError(
        code=TransformErrorCodes.T001_UNKNOWN_VERB,
        message=f"Unknown verb: {verb}",
        path=field,
    )


def invalid_verb_args_error(
    verb: str, expected: str, actual: int, field: str | None = None
) -> TransformError:
    """Create a T002 Invalid Verb Arguments error."""
    return TransformError(
        code=TransformErrorCodes.T002_INVALID_VERB_ARGS,
        message=f"Invalid arguments for verb '{verb}': expected {expected}, got {actual}",
        path=field,
    )


def lookup_table_not_found_error(
    table_name: str, field: str | None = None
) -> TransformError:
    """Create a T003 Lookup Table Not Found error."""
    return TransformError(
        code=TransformErrorCodes.T003_LOOKUP_TABLE_NOT_FOUND,
        message=f"Lookup table not found: {table_name}",
        path=field,
    )


def lookup_key_not_found_error(
    table_name: str, key: str, field: str | None = None
) -> TransformError:
    """Create a T004 Lookup Key Not Found error."""
    return TransformError(
        code=TransformErrorCodes.T004_LOOKUP_KEY_NOT_FOUND,
        message=f"Lookup key '{key}' not found in table '{table_name}'",
        path=field,
    )


def source_path_not_found_error(
    path: str, field: str | None = None
) -> TransformError:
    """Create a T005 Source Path Not Found error."""
    return TransformError(
        code=TransformErrorCodes.T005_SOURCE_PATH_NOT_FOUND,
        message=f"Source path not found: {path}",
        path=field,
    )


def invalid_output_format_error(fmt: str) -> TransformError:
    """Create a T006 Invalid Output Format error."""
    return TransformError(
        code=TransformErrorCodes.T006_INVALID_OUTPUT_FORMAT,
        message=f"Invalid or unsupported output format: {fmt}",
    )


def invalid_modifier_error(
    modifier: str, fmt: str, field: str | None = None
) -> TransformError:
    """Create a T007 Invalid Modifier error."""
    return TransformError(
        code=TransformErrorCodes.T007_INVALID_MODIFIER,
        message=f"Modifier '{modifier}' is not valid for format '{fmt}'",
        path=field,
    )


def accumulator_overflow_error(
    accumulator: str, value: float, field: str | None = None
) -> TransformError:
    """Create a T008 Accumulator Overflow error."""
    return TransformError(
        code=TransformErrorCodes.T008_ACCUMULATOR_OVERFLOW,
        message=f"Accumulator '{accumulator}' overflow with value {value}",
        path=field,
    )


def loop_source_not_array_error(
    path: str, segment: str | None = None
) -> TransformError:
    """Create a T009 Loop Source Not Array error."""
    return TransformError(
        code=TransformErrorCodes.T009_LOOP_SOURCE_NOT_ARRAY,
        message=f"Loop source path '{path}' does not resolve to an array",
        path=segment,
    )


def position_overflow_error(
    position: int, length: int, line_width: int, field: str | None = None
) -> TransformError:
    """Create a T010 Position Overflow error."""
    return TransformError(
        code=TransformErrorCodes.T010_POSITION_OVERFLOW,
        message=f"Field at position {position} with length {length} exceeds line width {line_width}",
        path=field,
    )


def incompatible_conversion_error(
    verb: str, detail: str, field: str | None = None
) -> TransformError:
    """Create a T011 Incompatible Conversion error."""
    return TransformError(
        code=TransformErrorCodes.T011_INCOMPATIBLE_CONVERSION,
        message=f"Incompatible conversion in '{verb}': {detail}",
        path=field,
    )


def config_error(message: str) -> TransformError:
    """Create a configuration error."""
    return TransformError(
        code=TransformErrorCodes.CONFIG_ERROR,
        message=message,
    )


def unknown_record_type_error(
    discriminator_value: str, record_index: int
) -> TransformError:
    """Create an unknown record type error."""
    return TransformError(
        code=TransformErrorCodes.UNKNOWN_RECORD_TYPE,
        message=f"No segment matches discriminator value '{discriminator_value}' at record {record_index}",
    )


def source_missing_error(field: str) -> TransformError:
    """Create a source missing (required field) error."""
    return TransformError(
        code=TransformErrorCodes.SOURCE_MISSING,
        message=f"Required field '{field}' is missing or null",
        path=field,
    )


def transform_error(message: str, field: str | None = None) -> TransformError:
    """Create a general transform error."""
    return TransformError(
        code=TransformErrorCodes.TRANSFORM_ERROR,
        message=message,
        path=field,
    )
