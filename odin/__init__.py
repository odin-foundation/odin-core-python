"""
ODIN (Open Data Interchange Notation) - Official Python Implementation

A canonical notation format for representing structured data. Provides a precise,
unambiguous way to express hierarchical information in a flat, line-based format
optimized for machine processing, human readability, and version control.

Example:
    >>> import odin
    >>>
    >>> # Parse ODIN text
    >>> doc = odin.parse('''
    ...     {policy}
    ...     number = PAP-2024-001
    ...     premium = #$747.50
    ... ''')
    >>>
    >>> # Access values
    >>> premium = doc.get('policy.premium')
    >>>
    >>> # Serialize back to ODIN
    >>> text = odin.dumps(doc)
    >>>
    >>> # Canonical form (deterministic bytes)
    >>> canonical = odin.canonicalize(doc)
"""

from typing import IO, Optional, Union

from odin.types.document import OdinDocument, OdinDocumentBuilder, OdinModifiers
from odin.types.values import (
    OdinValue,
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
    NULL,
    TRUE,
    FALSE,
)
from odin.types.schema import OdinSchema, ValidationResult, ValidationError, ValidationWarning
from odin.types.diff import OdinDiff, PathValue, PathChange, PathMove
from odin.types.errors import OdinError, ParseError, PatchError, ParseErrorCodes, ValidationErrorCodes
from odin.types.options import ParseOptions, DumpOptions, ValidateOptions
from odin.resolver import ImportResolver, ResolverOptions, SchemaFlattener

__version__ = "1.0.5"
__all__ = [
    # Main functions
    "parse",
    "parse_documents",
    "collapse_chain",
    "loads",
    "dump",
    "dumps",
    "validate",
    "validate_with_imports",
    "canonicalize",
    "diff",
    "patch",
    "path",
    # Types - Document
    "OdinDocument",
    "OdinDocumentBuilder",
    "OdinModifiers",
    # Types - Values
    "OdinValue",
    "OdinNull",
    "OdinBoolean",
    "OdinString",
    "OdinNumber",
    "OdinInteger",
    "OdinCurrency",
    "OdinPercent",
    "OdinDate",
    "OdinTimestamp",
    "OdinTime",
    "OdinDuration",
    "OdinReference",
    "OdinBinary",
    "OdinVerbExpression",
    "OdinArray",
    "OdinObject",
    "NULL",
    "TRUE",
    "FALSE",
    # Types - Schema
    "OdinSchema",
    "ValidationResult",
    "ValidationError",
    "ValidationWarning",
    # Types - Diff
    "OdinDiff",
    "PathValue",
    "PathChange",
    "PathMove",
    # Types - Errors
    "OdinError",
    "ParseError",
    "PatchError",
    "ParseErrorCodes",
    "ValidationErrorCodes",
    # Types - Options
    "ParseOptions",
    "DumpOptions",
    "ValidateOptions",
    "ImportResolver",
    "ResolverOptions",
    "SchemaFlattener",
    # Schema
    "parse_schema",
    "serialize_schema",
    "resolve_imports",
    # Export
    "to_json",
    "to_xml",
    "to_csv",
    "to_fixed_width",
    # Transform
    "parse_transform",
    "execute_transform",
]


# ─────────────────────────────────────────────────────────────────────────────
# Parse
# ─────────────────────────────────────────────────────────────────────────────


def parse(
    text: Union[str, bytes],
    options: Optional[ParseOptions] = None,
) -> OdinDocument:
    """
    Parse ODIN text into a document.

    Args:
        text: ODIN text as string or UTF-8 bytes
        options: Parse options

    Returns:
        Parsed document

    Raises:
        ParseError: If input is invalid ODIN

    Example:
        >>> doc = odin.parse('name = John\\nage = ##42')
    """
    from odin.parsing.parser import OdinParser
    if isinstance(text, bytes):
        text = text.decode("utf-8")
    return OdinParser().parse(text, options)


def parse_documents(
    text: Union[str, bytes],
    options: Optional[ParseOptions] = None,
) -> "list[OdinDocument]":
    """
    Parse a chained ODIN document (one or more documents separated by ``---``)
    into the full list of documents.

    A single document yields a one-element list.

    Args:
        text: ODIN text as string or UTF-8 bytes
        options: Parse options

    Returns:
        List of parsed documents in chain order

    Example:
        >>> docs = odin.parse_documents('{$}\\nid = "a"\\n\\n---\\n\\n{$}\\nid = "b"')
        >>> len(docs)
        2
    """
    from odin.parsing.parser import OdinParser
    if isinstance(text, bytes):
        text = text.decode("utf-8")
    return OdinParser().parse_documents(text, options)


def collapse_chain(
    input: Union[str, bytes, "list[OdinDocument]"],
    options: Optional[ParseOptions] = None,
) -> OdinDocument:
    """Collapse a chained ODIN document into its computed current state.

    Applies chaining overlay semantics across the chain: later documents
    overlay earlier ones, a repeated path replaces the earlier value,
    ``field = ~`` removes the field and its descendants, and ``field[] = ~``
    clears the array. The result carries the final document's metadata.

    Args:
        input: Chained ODIN text (str/bytes) or a pre-parsed list of documents
        options: Parse options (used when input is text)

    Returns:
        Document representing the computed current state

    Example:
        >>> current = odin.collapse_chain('{p}\\nname = "A"\\n\\n---\\n\\n{p}\\nname = "B"\\nold = ~')
        >>> current.get('p.name').value
        'B'
    """
    from odin.parsing.chain import collapse_chain as _collapse_chain
    if isinstance(input, (str, bytes)):
        docs = parse_documents(input, options)
    else:
        docs = input
    return _collapse_chain(docs)


def loads(
    text: Union[str, bytes],
    options: Optional[ParseOptions] = None,
) -> OdinDocument:
    """Alias for parse() - matches json module convention."""
    return parse(text, options)


def load(
    fp: IO[str],
    options: Optional[ParseOptions] = None,
) -> OdinDocument:
    """
    Parse ODIN from a file-like object.

    Args:
        fp: File-like object with read() method
        options: Parse options

    Returns:
        Parsed document
    """
    return parse(fp.read(), options)


# ─────────────────────────────────────────────────────────────────────────────
# Serialize
# ─────────────────────────────────────────────────────────────────────────────


def dumps(
    doc: OdinDocument,
    options: Optional[DumpOptions] = None,
) -> str:
    """
    Convert a document to ODIN text.

    Args:
        doc: Document to serialize
        options: Dump options

    Returns:
        ODIN text

    Example:
        >>> text = odin.dumps(doc, DumpOptions(pretty=True))
    """
    from odin.serialization.stringify import stringify as _stringify
    return _stringify(doc, options)


def dump(
    doc: OdinDocument,
    fp: IO[str],
    options: Optional[DumpOptions] = None,
) -> None:
    """
    Write a document to a file-like object.

    Args:
        doc: Document to serialize
        fp: File-like object with write() method
        options: Dump options
    """
    fp.write(dumps(doc, options))


# ─────────────────────────────────────────────────────────────────────────────
# Validate
# ─────────────────────────────────────────────────────────────────────────────


def validate(
    doc: OdinDocument,
    schema: OdinSchema,
    options: Optional[ValidateOptions] = None,
    type_registry=None,
) -> ValidationResult:
    """
    Validate a document against a schema.

    Args:
        doc: Document to validate
        schema: Schema to validate against
        options: Validation options
        type_registry: Optional resolved-import type registry (alias.name keys)

    Returns:
        Validation result with errors and warnings

    Example:
        >>> result = odin.validate(doc, schema)
        >>> if not result.valid:
        ...     print('Errors:', result.errors)
    """
    from odin.validation.validator import validate as _validate
    return _validate(doc, schema, options, type_registry)


def validate_with_imports(
    doc: OdinDocument,
    schema: OdinSchema,
    base_path: str,
    options: Optional[ValidateOptions] = None,
    resolver_options: Optional[ResolverOptions] = None,
) -> ValidationResult:
    """
    Resolve a schema's @imports relative to base_path, then validate the document.

    Args:
        doc: Document to validate
        schema: Parsed schema (from parse_schema)
        base_path: Path the schema was loaded from, for resolving relative @imports
        options: Validation options
        resolver_options: Import resolver options (e.g. sandbox_root)

    Returns:
        Validation result with errors and warnings
    """
    from odin.validation.validator import validate as _validate
    resolver = ImportResolver(options=resolver_options)
    resolved = resolver.resolve_schema(schema, base_path)
    return _validate(doc, schema, options, resolved.resolution.type_registry)


# ─────────────────────────────────────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────────────────────────────────────


def parse_schema(text: Union[str, bytes]) -> OdinSchema:
    """Parse ODIN Schema text into a schema object.

    Args:
        text: Schema text as string or UTF-8 bytes

    Returns:
        Parsed schema

    Example:
        >>> schema = odin.parse_schema('{$}\\nodin = "1.0.0"\\n\\nname = !""')
    """
    from odin.validation.schema_parser import parse_schema as _parse_schema
    if isinstance(text, bytes):
        text = text.decode("utf-8")
    return _parse_schema(text)


def serialize_schema(schema: OdinSchema) -> str:
    """Serialize a schema object back to ODIN Schema text.

    Args:
        schema: Schema to serialize

    Returns:
        ODIN Schema text
    """
    from odin.validation.schema_serializer import serialize_schema as _serialize
    return _serialize(schema)


def resolve_imports(
    schema: OdinSchema,
    base_path: Optional[str] = None,
    options: Optional[ResolverOptions] = None,
) -> OdinSchema:
    """Resolve all @import directives in a schema.

    Args:
        schema: Schema with imports to resolve
        base_path: Base path for resolving relative imports
        options: Resolver options (sandbox, max depth, etc.)

    Returns:
        New schema with all imports resolved and merged

    Raises:
        ImportError_: On circular imports, max depth exceeded, etc.
    """
    from odin.resolver import ImportResolver as _Resolver
    resolver = _Resolver(options=options)
    result = resolver.resolve_schema(schema, base_path)
    return result.schema


# ─────────────────────────────────────────────────────────────────────────────
# Canonicalize
# ─────────────────────────────────────────────────────────────────────────────


def canonicalize(doc: OdinDocument) -> bytes:
    """
    Produce deterministic canonical form of a document.

    Canonical form guarantees:
    - Identical documents produce identical bytes
    - Paths sorted lexicographically
    - No comments or blank lines
    - LF line endings
    - Bare strings where possible

    Args:
        doc: Document to canonicalize

    Returns:
        Canonical UTF-8 bytes

    Example:
        >>> canonical = odin.canonicalize(doc)
        >>> import hashlib
        >>> hash = hashlib.sha256(canonical).hexdigest()
    """
    from odin.serialization.canonicalize import canonicalize as _canonicalize
    return _canonicalize(doc)


# ─────────────────────────────────────────────────────────────────────────────
# Diff
# ─────────────────────────────────────────────────────────────────────────────


def diff(a: OdinDocument, b: OdinDocument) -> OdinDiff:
    """
    Compute the difference between two documents.

    Args:
        a: Original document
        b: Modified document

    Returns:
        Diff describing changes from a to b

    Example:
        >>> d = odin.diff(original, modified)
        >>> print('Added:', d.additions)
        >>> print('Removed:', d.deletions)
    """
    from odin._diff.differ import compute_diff
    return compute_diff(a, b)


# ─────────────────────────────────────────────────────────────────────────────
# Patch
# ─────────────────────────────────────────────────────────────────────────────


def patch(doc: OdinDocument, diff: OdinDiff) -> OdinDocument:
    """
    Apply a diff to a document, producing a new document.

    Args:
        doc: Document to patch
        diff: Diff to apply

    Returns:
        New document with diff applied

    Raises:
        PatchError: If diff references non-existent paths

    Example:
        >>> patched = odin.patch(original, diff)
    """
    from odin._diff.patcher import apply_patch
    return apply_patch(doc, diff)


# ─────────────────────────────────────────────────────────────────────────────
# Export
# ─────────────────────────────────────────────────────────────────────────────


def to_json(doc: OdinDocument, indent=2, omit_nulls: bool = False) -> str:
    """Export document to JSON string."""
    from odin.export.json_export import to_json as _to_json
    return _to_json(doc, indent=indent, omit_nulls=omit_nulls)


def to_xml(
    doc: OdinDocument,
    root_element: str = "root",
    indent: str = "  ",
    declaration: bool = True,
) -> str:
    """Export document to XML string."""
    from odin.export.xml_export import to_xml as _to_xml
    return _to_xml(doc, root_element=root_element, indent=indent, declaration=declaration)


def to_csv(
    doc: OdinDocument,
    array_path=None,
    delimiter: str = ",",
) -> str:
    """Export document to CSV string."""
    from odin.export.csv_export import to_csv as _to_csv
    return _to_csv(doc, array_path=array_path, delimiter=delimiter)


def to_fixed_width(doc: OdinDocument, fields=None, line_width: int = 80, pad_char: str = " ") -> str:
    """Export document to fixed-width string."""
    from odin.export.fixed_width_export import to_fixed_width as _to_fw
    return _to_fw(doc, fields=fields or [], line_width=line_width, pad_char=pad_char)


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────


def path(*segments: Union[str, int]) -> str:
    """
    Build a path string from segments.

    Args:
        segments: Path segments (strings for fields, integers for array indices)

    Returns:
        Formatted path string

    Example:
        >>> odin.path('policy', 'vehicles', 0, 'vin')
        'policy.vehicles[0].vin'

        >>> odin.path('&com.acme', 'custom_field')
        '&com.acme.custom_field'
    """
    if not segments:
        return ""

    result = []
    for i, segment in enumerate(segments):
        if isinstance(segment, int):
            result.append(f"[{segment}]")
        elif i == 0:
            result.append(str(segment))
        else:
            result.append(f".{segment}")

    return "".join(result)


# ─────────────────────────────────────────────────────────────────────────────
# Transform
# ─────────────────────────────────────────────────────────────────────────────


def parse_transform(text: Union[str, bytes], options=None):
    """Parse an ODIN transform definition.

    Args:
        text: Transform text as string or UTF-8 bytes
        options: Parse options (reserved for future use)

    Returns:
        Parsed OdinTransform
    """
    from odin.transform.transform_parser import parse_transform as _parse_transform
    if isinstance(text, bytes):
        text = text.decode("utf-8")
    return _parse_transform(text)


def execute_transform(transform_def, source, options=None):
    """Execute a transform on source data.

    Args:
        transform_def: OdinTransform object or transform text (str/bytes)
        source: Source data (dict, list, or other Python object)
        options: Transform options (reserved for future use)

    Returns:
        TransformResult with output and formatted string
    """
    from odin.transform.engine import TransformEngine
    from odin.transform.verb_registry import create_default_registry

    if isinstance(transform_def, (str, bytes)):
        transform_def = parse_transform(transform_def)

    import_resolver = None
    if options is not None:
        if isinstance(options, dict):
            import_resolver = options.get("import_resolver")
        else:
            import_resolver = getattr(options, "import_resolver", None)

    engine = TransformEngine(create_default_registry(), import_resolver=import_resolver)
    return engine.execute(transform_def, source)
