"""Serialize OdinSchema objects back to ODIN Schema text."""
from __future__ import annotations

from typing import Union

from odin.types.schema import (
    OdinSchema,
    SchemaField,
    SchemaType,
    SchemaArray,
    SchemaFieldType,
    SchemaConstraint,
    SchemaObjectConstraint,
    SchemaInvariant,
    SchemaCardinality,
    StringType,
    BooleanType,
    NumberType,
    IntegerType,
    DecimalType,
    CurrencyType,
    PercentType,
    DateType,
    TimestampType,
    TimeType,
    DurationType,
    ReferenceType,
    BinaryType,
    NullType,
    EnumType,
    UnionType,
    TypeRefType,
    BoundsConstraint,
    PatternConstraint,
    EnumConstraint,
    SizeConstraint,
    FormatConstraint,
    UniqueConstraint,
)


def serialize_schema(schema: OdinSchema) -> str:
    """Serialize an OdinSchema object to ODIN Schema text.

    The output should roundtrip: parse_schema(serialize_schema(schema))
    should produce an equivalent schema.
    """
    parts: list[str] = []

    # Metadata header
    if schema.metadata:
        parts.append("{$}")
        for key, value in schema.metadata.items():
            parts.append(f'{key} = "{value}"')
        parts.append("")

    # Import directives
    for imp in schema.imports:
        parts.append(f"@import {imp}")
    if schema.imports:
        parts.append("")

    # Type definitions
    for type_name, schema_type in schema.types.items():
        parts.append(f"{{@{type_name}}}")
        for field_name, field_def in schema_type.fields.items():
            parts.append(_serialize_field(field_name, field_def))
        parts.append("")

    # Group fields by section
    sections: dict[str, list[tuple[str, SchemaField]]] = {}
    for path, field_def in schema.fields.items():
        dot_pos = path.find(".")
        section = ""
        if dot_pos > 0:
            candidate = path[:dot_pos]
            if candidate[0].isupper():
                section = candidate
        if section not in sections:
            sections[section] = []
        sections[section].append((path, field_def))

    for section, fields in sections.items():
        if section:
            parts.append(f"{{{section}}}")
        for path, field_def in fields:
            field_name = path
            if section:
                field_name = path[len(section) + 1:]
            parts.append(_serialize_field(field_name, field_def))

        # Object-level constraints for this section
        scope = section if section else "root"
        if scope in schema.constraints:
            for constraint in schema.constraints[scope]:
                parts.append(_serialize_object_constraint(constraint))

        parts.append("")

    # Array definitions
    for array_path, array_def in schema.arrays.items():
        header = f"{{{array_path}[]}}"
        suffix = _serialize_array_constraints(array_def)
        if suffix:
            header += f" {suffix}"
        parts.append(header)
        for field_name, field_def in array_def.item_fields.items():
            parts.append(_serialize_field(field_name, field_def))
        parts.append("")

    # Root-level constraints (if not already emitted under a section)
    if "root" in schema.constraints and "" not in sections:
        for constraint in schema.constraints["root"]:
            parts.append(_serialize_object_constraint(constraint))
        parts.append("")

    # Other scoped constraints not yet emitted
    emitted_scopes = set()
    for section in sections:
        emitted_scopes.add(section if section else "root")
    for scope, constraints in schema.constraints.items():
        if scope in emitted_scopes:
            continue
        for constraint in constraints:
            parts.append(_serialize_object_constraint(constraint))

    result = "\n".join(parts)
    # Clean up trailing whitespace
    while result.endswith("\n\n"):
        result = result[:-1]
    return result


def _serialize_field(name: str, field_def: SchemaField) -> str:
    """Serialize a single field definition line."""
    parts = [f"{name} = "]

    # Modifiers come first: ! ~ * -
    modifiers = ""
    if field_def.required:
        modifiers += "!"
    if field_def.nullable:
        modifiers += "~"
    if field_def.redacted:
        modifiers += "*"
    if field_def.deprecated:
        modifiers += "-"
    parts.append(modifiers)

    # Type
    parts.append(_format_field_type(field_def.field_type))

    # Constraints
    for constraint in field_def.constraints:
        parts.append(" ")
        parts.append(_serialize_constraint(constraint))

    # Conditionals
    for cond in field_def.conditionals:
        keyword = ":unless" if cond.unless else ":if"
        value = cond.value
        if isinstance(value, bool):
            value = "true" if value else "false"
        parts.append(f" {keyword} {cond.field} {cond.operator} {value}")

    # Directives
    if field_def.computed:
        parts.append(" :computed")
    if field_def.immutable:
        parts.append(" :immutable")

    return "".join(parts)


def _format_field_type(field_type: SchemaFieldType) -> str:
    """Format a field type to its ODIN text representation."""
    if isinstance(field_type, StringType):
        return '""'
    if isinstance(field_type, BooleanType):
        return "?"
    if isinstance(field_type, IntegerType):
        return "##"
    if isinstance(field_type, DecimalType):
        return f"#.{field_type.places}"
    if isinstance(field_type, CurrencyType):
        if field_type.places != 2:
            return f"#$.{field_type.places}"
        return "#$"
    if isinstance(field_type, PercentType):
        return "#%"
    if isinstance(field_type, NumberType):
        return "#"
    if isinstance(field_type, DateType):
        return "date"
    if isinstance(field_type, TimestampType):
        return "timestamp"
    if isinstance(field_type, TimeType):
        return "time"
    if isinstance(field_type, DurationType):
        return "duration"
    if isinstance(field_type, BinaryType):
        if field_type.algorithm:
            return f"^{field_type.algorithm}"
        return "^"
    if isinstance(field_type, NullType):
        return "~"
    if isinstance(field_type, ReferenceType):
        if field_type.target_path:
            return f"@{field_type.target_path}"
        return "@"
    if isinstance(field_type, TypeRefType):
        return f"@{field_type.name}"
    if isinstance(field_type, EnumType):
        values = ", ".join(field_type.values)
        return f"({values})"
    if isinstance(field_type, UnionType):
        return "|".join(_format_field_type(t) for t in field_type.types)
    return '""'


def _serialize_constraint(constraint: SchemaConstraint) -> str:
    """Serialize a single constraint."""
    if isinstance(constraint, BoundsConstraint):
        if constraint.min is not None and constraint.max is not None:
            return f":({constraint.min}..{constraint.max})"
        elif constraint.min is not None:
            return f":({constraint.min}..)"
        elif constraint.max is not None:
            return f":(..{constraint.max})"
        return ""
    if isinstance(constraint, PatternConstraint):
        return f":/{constraint.pattern}/"
    if isinstance(constraint, EnumConstraint):
        return ":(" + ", ".join(constraint.values) + ")"
    if isinstance(constraint, SizeConstraint):
        if constraint.min is not None and constraint.max is not None:
            return f":({constraint.min}..{constraint.max})"
        elif constraint.min is not None:
            return f":({constraint.min}..)"
        elif constraint.max is not None:
            return f":(..{constraint.max})"
        return ""
    if isinstance(constraint, FormatConstraint):
        return f":format {constraint.format}"
    if isinstance(constraint, UniqueConstraint):
        return ":unique"
    return ""


def _serialize_array_constraints(array_def: SchemaArray) -> str:
    """Serialize array-level constraints."""
    parts: list[str] = []
    if array_def.min_items is not None or array_def.max_items is not None:
        min_str = str(array_def.min_items) if array_def.min_items is not None else ""
        max_str = str(array_def.max_items) if array_def.max_items is not None else ""
        parts.append(f":({min_str}..{max_str})")
    if array_def.unique:
        parts.append(":unique")
    return " ".join(parts)


def _serialize_object_constraint(constraint: SchemaObjectConstraint) -> str:
    """Serialize an object-level constraint."""
    if isinstance(constraint, SchemaInvariant):
        return f":invariant {constraint.expression}"
    if isinstance(constraint, SchemaCardinality):
        fields_str = ", ".join(constraint.fields)
        if constraint.cardinality_type == "one_of":
            return f":one_of {fields_str}"
        elif constraint.cardinality_type == "exactly_one":
            return f":exactly_one {fields_str}"
        elif constraint.cardinality_type == "at_most_one":
            return f":at_most_one {fields_str}"
        elif constraint.cardinality_type == "of":
            min_str = str(constraint.min) if constraint.min is not None else ""
            max_str = str(constraint.max) if constraint.max is not None else ""
            return f":of ({min_str}..{max_str}) {fields_str}"
    return ""
