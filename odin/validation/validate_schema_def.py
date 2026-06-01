"""Schema definition validation.

Validates that the schema itself is well-formed, independent of any document:
override restrictiveness, intersection field conflicts, tabular column rules,
and default-value rules. Violations are reported as V017.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from odin.types.schema import (
    OdinSchema,
    SchemaField,
    SchemaFieldType,
    SchemaType,
    SchemaConstraint,
    BoundsConstraint,
    PatternConstraint,
    EnumConstraint,
    EnumType,
    UnionType,
    TypeRefType,
    ReferenceType,
    ValidationError,
)

_PRIMITIVE_KINDS = {
    "string", "boolean", "number", "integer", "decimal", "currency",
    "percent", "date", "timestamp", "time", "duration", "enum", "binary",
}


def validate_schema_definition(
    schema: OdinSchema,
    errors: List[ValidationError],
    type_registry: Optional[Dict[str, Any]] = None,
) -> None:
    """Run all schema-definition validations (V017)."""
    _validate_type_definitions(schema, errors, type_registry)
    _validate_path_compositions(schema, errors, type_registry)
    _validate_tabular_columns(schema, errors, type_registry)
    _validate_defaults(schema, errors)


def _add_error(
    errors: List[ValidationError],
    path: str,
    message: str,
    expected: Any = None,
    actual: Any = None,
) -> None:
    errors.append(ValidationError(
        path=path, code="V017", message=message, expected=expected, actual=actual,
    ))


def _lookup_base_type(
    schema: OdinSchema, name: str, type_registry: Optional[Dict[str, Any]]
) -> Optional[SchemaType]:
    if type_registry and name in type_registry:
        return type_registry[name]
    return schema.types.get(name)


def _member_names(name: str) -> List[str]:
    return [n.strip() for n in name.split("&") if n.strip()]


# ─────────────────────────────────────────────────────────────────────────────
# Override and Intersection (type definitions)
# ─────────────────────────────────────────────────────────────────────────────


def _validate_type_definitions(
    schema: OdinSchema, errors: List[ValidationError], type_registry: Optional[Dict[str, Any]]
) -> None:
    for type_name, type_def in schema.types.items():
        composition = type_def.fields.get("_composition")
        if composition is None or not isinstance(composition.field_type, TypeRefType):
            continue

        names = _member_names(composition.field_type.name)
        if composition.field_type.override:
            _validate_override(schema, errors, type_registry, type_name, type_def, names)
        elif len(names) > 1:
            _validate_intersection_conflicts(schema, errors, type_registry, type_name, names)


def _validate_override(
    schema: OdinSchema,
    errors: List[ValidationError],
    type_registry: Optional[Dict[str, Any]],
    type_name: str,
    type_def: SchemaType,
    base_names: List[str],
) -> None:
    base_fields: Dict[str, SchemaField] = {}
    for base_name in base_names:
        base = _lookup_base_type(schema, base_name, type_registry)
        if base is None:
            continue
        for fn, ff in base.fields.items():
            if fn != "_composition":
                base_fields[fn] = ff

    for fn, override in type_def.fields.items():
        if fn == "_composition":
            continue
        base = base_fields.get(fn)
        if base is None:
            continue
        _check_override_field(errors, f"@{type_name}.{fn}", base, override)


def _check_override_field(
    errors: List[ValidationError], label: str, base: SchemaField, override: SchemaField
) -> None:
    # Base type must match
    if not _same_base_type(base.field_type, override.field_type):
        _add_error(
            errors, label, "Override changes field type",
            _type_kind_label(base.field_type), _type_kind_label(override.field_type),
        )

    # required: optional->required allowed, required->optional forbidden
    if base.required and not override.required:
        _add_error(errors, label, "Override relaxes required field to optional",
                   "required", "optional")

    # nullable: may remove, may not add
    if not base.nullable and override.nullable:
        _add_error(errors, label, "Override adds nullability", "non-nullable", "nullable")

    # bounds: may only narrow
    base_bounds = _find_bounds(base.constraints)
    override_bounds = _find_bounds(override.constraints)
    if base_bounds is not None and override_bounds is not None:
        if _widens_bounds(base_bounds, override_bounds):
            _add_error(errors, label, "Override widens constraint bounds",
                       _bounds_label(base_bounds), _bounds_label(override_bounds))


def _validate_intersection_conflicts(
    schema: OdinSchema,
    errors: List[ValidationError],
    type_registry: Optional[Dict[str, Any]],
    type_name: str,
    member_names: List[str],
) -> None:
    seen: Dict[str, Dict[str, Any]] = {}
    for member_name in member_names:
        member = _lookup_base_type(schema, member_name, type_registry)
        if member is None:
            continue
        for fn, ff in member.fields.items():
            if fn == "_composition":
                continue
            prior = seen.get(fn)
            if prior is not None and not _same_field_definition(prior["field"], ff):
                _add_error(
                    errors,
                    f"@{type_name}.{fn}",
                    f"Intersection field conflict: '{fn}' differs between "
                    f"@{prior['member']} and @{member_name}",
                    "identical field definitions",
                    "conflicting definitions",
                )
            elif prior is None:
                seen[fn] = {"member": member_name, "field": ff}


# ─────────────────────────────────────────────────────────────────────────────
# Path-level compositions ({path} = @base :override)
# ─────────────────────────────────────────────────────────────────────────────


def _validate_path_compositions(
    schema: OdinSchema, errors: List[ValidationError], type_registry: Optional[Dict[str, Any]]
) -> None:
    suffix = "._composition"
    for path, field in schema.fields.items():
        if not path.endswith(suffix) or not isinstance(field.field_type, TypeRefType):
            continue
        parent_path = path[: -len(suffix)]
        names = _member_names(field.field_type.name)

        if field.field_type.override:
            base_fields: Dict[str, SchemaField] = {}
            for base_name in names:
                base = _lookup_base_type(schema, base_name, type_registry)
                if base is None:
                    continue
                for fn, ff in base.fields.items():
                    if fn != "_composition":
                        base_fields[fn] = ff
            for field_path, override in schema.fields.items():
                if not field_path.startswith(f"{parent_path}.") or field_path.endswith(suffix):
                    continue
                local_name = field_path[len(parent_path) + 1:]
                if "." in local_name:
                    continue
                base = base_fields.get(local_name)
                if base is None:
                    continue
                _check_override_field(errors, field_path, base, override)
        elif len(names) > 1:
            _validate_intersection_conflicts(schema, errors, type_registry, parent_path, names)


# ─────────────────────────────────────────────────────────────────────────────
# Tabular column rules
# ─────────────────────────────────────────────────────────────────────────────


def _validate_tabular_columns(
    schema: OdinSchema, errors: List[ValidationError], type_registry: Optional[Dict[str, Any]]
) -> None:
    for array_path, array in schema.arrays.items():
        if not array.columns:
            continue
        for column in array.columns:
            label = f"{array_path}[].{column}"

            if _is_multi_level_column(column):
                _add_error(errors, label, "Tabular column uses multi-level path",
                           "single-level column", column)
                continue

            item_name = re.sub(r"\[\d+\]$", "", column)
            field = array.item_fields.get(item_name) or array.item_fields.get(column)
            if field is None:
                continue

            if not _is_primitive_column_type(schema, type_registry, field.field_type):
                _add_error(errors, label, "Tabular column must be a primitive type",
                           "primitive", _type_kind_label(field.field_type))


def _is_multi_level_column(column: str) -> bool:
    dot_count = column.count(".")
    index_count = len(re.findall(r"\[\d+\]", column))
    if dot_count > 1 or index_count > 1:
        return True
    if dot_count == 1 and index_count == 1:
        return True
    return False


def _is_primitive_column_type(
    schema: OdinSchema, type_registry: Optional[Dict[str, Any]], ftype: SchemaFieldType
) -> bool:
    if isinstance(ftype, TypeRefType):
        return False
    if isinstance(ftype, UnionType):
        return all(_is_primitive_column_type(schema, type_registry, t) for t in ftype.types)
    if isinstance(ftype, ReferenceType):
        return False
    return getattr(ftype, "kind", "") in _PRIMITIVE_KINDS


# ─────────────────────────────────────────────────────────────────────────────
# Default value rules
# ─────────────────────────────────────────────────────────────────────────────


def _validate_defaults(schema: OdinSchema, errors: List[ValidationError]) -> None:
    suffix = "._composition"
    for path, field in schema.fields.items():
        if path.endswith(suffix):
            continue
        _check_default(errors, path, field)
    for type_def in schema.types.values():
        for fn, field in type_def.fields.items():
            if fn == "_composition":
                continue
            _check_default(errors, f"@{type_def.name}.{fn}", field)
    for array_path, array in schema.arrays.items():
        for fn, field in array.item_fields.items():
            if fn == "_composition":
                continue
            _check_default(errors, f"{array_path}[].{fn}", field)


def _check_default(errors: List[ValidationError], label: str, field: SchemaField) -> None:
    if field.default_value is None:
        return

    # Required fields cannot have a default.
    if field.required:
        _add_error(errors, label, "Required field cannot have a default value",
                   "no default", "default present")
        return

    # Default must satisfy field constraints.
    if not _default_satisfies_constraints(field, field.default_value):
        _add_error(errors, label, "Default value violates field constraints",
                   "value within constraints", _describe_value(field.default_value))


def _default_satisfies_constraints(field: SchemaField, default: Dict[str, Any]) -> bool:
    value = default.get("value")
    is_string = default.get("type") == "string" or isinstance(value, str)
    num = value if isinstance(value, (int, float)) and not isinstance(value, bool) else None

    for constraint in field.constraints:
        if isinstance(constraint, BoundsConstraint):
            if not _bounds_satisfied(constraint, num, value if is_string else None):
                return False
        elif isinstance(constraint, EnumConstraint):
            if not is_string or str(value) not in constraint.values:
                return False
        elif isinstance(constraint, PatternConstraint):
            if is_string:
                try:
                    if not re.search(constraint.pattern, str(value)):
                        return False
                except re.error:
                    pass

    if isinstance(field.field_type, EnumType):
        if not is_string or str(value) not in field.field_type.values:
            return False
    return True


def _bounds_satisfied(
    c: BoundsConstraint, num: Optional[float], string_val: Optional[str]
) -> bool:
    if num is not None:
        target: Optional[float] = num
    elif string_val is not None:
        target = len(string_val)
    else:
        return True

    if isinstance(c.min, (int, float)) and target < c.min:
        return False
    if isinstance(c.max, (int, float)) and target > c.max:
        return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _same_base_type(a: SchemaFieldType, b: SchemaFieldType) -> bool:
    return getattr(a, "kind", None) == getattr(b, "kind", None)


def _type_kind_label(t: SchemaFieldType) -> str:
    return getattr(t, "kind", "unknown")


def _find_bounds(constraints: List[SchemaConstraint]) -> Optional[BoundsConstraint]:
    for c in constraints:
        if isinstance(c, BoundsConstraint):
            return c
    return None


def _bounds_label(b: BoundsConstraint) -> str:
    return f"({b.min if b.min is not None else ''}..{b.max if b.max is not None else ''})"


def _widens_bounds(base: BoundsConstraint, override: BoundsConstraint) -> bool:
    if isinstance(base.min, (int, float)):
        if not isinstance(override.min, (int, float)) or override.min < base.min:
            return True
    if isinstance(base.max, (int, float)):
        if not isinstance(override.max, (int, float)) or override.max > base.max:
            return True
    return False


def _same_field_definition(a: SchemaField, b: SchemaField) -> bool:
    if getattr(a.field_type, "kind", None) != getattr(b.field_type, "kind", None):
        return False
    if a.required != b.required:
        return False
    if a.nullable != b.nullable:
        return False
    if _constraints_key(a.constraints) != _constraints_key(b.constraints):
        return False
    return True


def _constraints_key(constraints: List[SchemaConstraint]) -> str:
    return json.dumps(
        [_constraint_dict(c) for c in constraints], sort_keys=True, default=str
    )


def _constraint_dict(c: SchemaConstraint) -> Dict[str, Any]:
    return {k: v for k, v in vars(c).items()}


def _describe_value(default: Dict[str, Any]) -> Any:
    return default.get("value", default.get("type"))
