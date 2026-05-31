"""Validate ODIN documents against schemas."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from odin.types.document import OdinDocument
from odin.types.schema import (
    OdinSchema,
    SchemaField,
    SchemaFieldType,
    SchemaType,
    SchemaArray,
    SchemaConditional,
    SchemaInvariant,
    SchemaCardinality,
    ValidationResult,
    ValidationError,
    ValidationWarning,
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
    FormatConstraint,
    UniqueConstraint,
)
from odin.types.values import (
    OdinValue, OdinNull, OdinBoolean, OdinString, OdinNumber,
    OdinInteger, OdinCurrency, OdinPercent, OdinDate, OdinTimestamp,
    OdinTime, OdinDuration, OdinReference, OdinBinary,
)
from odin.types.options import ValidateOptions
from odin.validation.constraints import check_bounds, check_pattern, check_enum
from odin.validation.format_validators import validate as validate_format
from odin.validation.redos_protection import is_safe_pattern


def validate(
    doc: OdinDocument,
    schema: OdinSchema,
    options: Optional[ValidateOptions] = None,
    type_registry: Optional[Dict[str, Any]] = None,
) -> ValidationResult:
    """Validate a document against a schema.

    Checks V001-V013 validation codes.

    Args:
        doc: Document to validate
        schema: Schema to validate against
        options: Validation options
        type_registry: Optional resolved-import type registry (alias.name keys)

    Returns:
        ValidationResult
    """
    if options is None:
        options = ValidateOptions()

    errors: List[ValidationError] = []
    warnings: List[ValidationWarning] = []

    def _add_error(error: ValidationError) -> bool:
        """Add error and return True if we should stop (fail_fast)."""
        errors.append(error)
        return options.fail_fast

    # ------------------------------------------------------------------
    # V012: Circular reference detection
    # V013: Unresolved reference detection
    # ------------------------------------------------------------------
    _check_references(doc, errors, options, schema, type_registry)
    if options.fail_fast and errors:
        return ValidationResult(valid=False, errors=errors, warnings=warnings)

    # Expand type compositions and field-level type references into concrete
    # fields (e.g. customer._composition: @a & @b -> customer.<fields>).
    expanded_fields = _expand_type_compositions(doc, schema, type_registry)

    # ------------------------------------------------------------------
    # Per-field validation: V001, V002, V003, V004, V005, V010
    # ------------------------------------------------------------------
    for field_path, schema_field in expanded_fields.items():
        value = doc.get(field_path)

        # V010 / V001: Conditional requirements
        if schema_field.conditionals:
            cond_required = _evaluate_conditionals(
                schema_field.conditionals, doc, schema_field.required, field_path
            )
        else:
            cond_required = schema_field.required

        # V001: Required field missing
        if cond_required:
            if value is None or isinstance(value, OdinNull):
                # If the requirement came from a conditional, use V010
                code = "V010" if schema_field.conditionals else "V001"
                msg = (
                    f"Conditional requirement not met at {field_path}"
                    if code == "V010"
                    else f"Required field missing: {field_path}"
                )
                if _add_error(ValidationError(
                    path=field_path,
                    code=code,
                    message=msg,
                    expected="non-null value",
                    actual="null" if isinstance(value, OdinNull) else "missing",
                )):
                    return ValidationResult(valid=False, errors=errors, warnings=warnings)
                continue

        # Skip further checks if value is not present
        if value is None:
            continue

        # Allow null if nullable
        if isinstance(value, OdinNull):
            if schema_field.nullable:
                continue
            continue

        # V002: Type mismatch
        if not _type_matches(value, schema_field.field_type, schema, type_registry):
            actual_type = _value_type_name(value)
            expected_type = _field_type_name(schema_field.field_type)
            if _add_error(ValidationError(
                path=field_path,
                code="V002",
                message=f"Type mismatch at {field_path}: expected {expected_type}, got {actual_type}",
                expected=expected_type,
                actual=actual_type,
            )):
                return ValidationResult(valid=False, errors=errors, warnings=warnings)
            continue

        # V003: Value out of bounds
        for constraint in schema_field.constraints:
            if isinstance(constraint, BoundsConstraint):
                raw = _extract_raw_value(value)
                if not check_bounds(raw, constraint):
                    if _add_error(ValidationError(
                        path=field_path,
                        code="V003",
                        message=f"Value out of bounds at {field_path}",
                        expected=f"min={constraint.min}, max={constraint.max}",
                        actual=raw,
                    )):
                        return ValidationResult(valid=False, errors=errors, warnings=warnings)

            # V004: Pattern mismatch (with ReDoS protection)
            elif isinstance(constraint, PatternConstraint):
                if constraint.pattern and is_safe_pattern(constraint.pattern):
                    raw = _extract_raw_value(value)
                    if not check_pattern(raw, constraint):
                        if _add_error(ValidationError(
                            path=field_path,
                            code="V004",
                            message=f"Pattern mismatch at {field_path}",
                            expected=constraint.pattern,
                            actual=raw,
                        )):
                            return ValidationResult(valid=False, errors=errors, warnings=warnings)

            # V005: Invalid enum value (via EnumConstraint)
            elif isinstance(constraint, EnumConstraint):
                raw = str(_extract_raw_value(value))
                if not check_enum(raw, constraint.values):
                    if _add_error(ValidationError(
                        path=field_path,
                        code="V005",
                        message=f"Invalid enum value at {field_path}",
                        expected=constraint.values,
                        actual=raw,
                    )):
                        return ValidationResult(valid=False, errors=errors, warnings=warnings)

            # Format validation (uses format_validators)
            elif isinstance(constraint, FormatConstraint):
                raw = _extract_raw_value(value)
                if raw is not None and not validate_format(str(raw), constraint.format):
                    if _add_error(ValidationError(
                        path=field_path,
                        code="V004",
                        message=f"Format validation failed at {field_path}: expected {constraint.format}",
                        expected=constraint.format,
                        actual=raw,
                    )):
                        return ValidationResult(valid=False, errors=errors, warnings=warnings)

            # V007: Unique constraint on field
            elif isinstance(constraint, UniqueConstraint):
                _check_field_uniqueness(field_path, doc, errors, options)
                if options.fail_fast and errors:
                    return ValidationResult(valid=False, errors=errors, warnings=warnings)

        # V005: Invalid enum value (via EnumType)
        if isinstance(schema_field.field_type, EnumType):
            raw = str(_extract_raw_value(value))
            if not check_enum(raw, schema_field.field_type.values):
                if _add_error(ValidationError(
                    path=field_path,
                    code="V005",
                    message=f"Invalid enum value at {field_path}",
                    expected=schema_field.field_type.values,
                    actual=raw,
                )):
                    return ValidationResult(valid=False, errors=errors, warnings=warnings)

        # Deprecated warning
        if schema_field.deprecated and options.include_warnings:
            warnings.append(ValidationWarning(
                path=field_path,
                code="W001",
                message=f"Deprecated field used: {field_path}",
            ))

    # ------------------------------------------------------------------
    # V006: Array length violation
    # V007: Array unique constraint
    # ------------------------------------------------------------------
    _check_arrays(doc, schema, errors, options)
    if options.fail_fast and errors:
        return ValidationResult(valid=False, errors=errors, warnings=warnings)

    # ------------------------------------------------------------------
    # V008: Invariant violation
    # V009: Cardinality constraint violation
    # ------------------------------------------------------------------
    _check_object_constraints(doc, schema, errors, options)
    if options.fail_fast and errors:
        return ValidationResult(valid=False, errors=errors, warnings=warnings)

    # ------------------------------------------------------------------
    # V011: Unknown field (strict mode)
    # ------------------------------------------------------------------
    if options.strict:
        _check_unknown_fields(doc, schema, errors, options)
        if options.fail_fast and errors:
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


# ─────────────────────────────────────────────────────────────────────────────
# V010: Conditional evaluation
# ─────────────────────────────────────────────────────────────────────────────


def _evaluate_conditionals(
    conditionals: List[SchemaConditional],
    doc: OdinDocument,
    base_required: bool,
    field_path: str = "",
) -> bool:
    """Evaluate conditional requirements on a field.

    If all conditions are met, the field is required.
    If any condition is not met, the field requirement falls back to base_required.
    """
    parent = field_path[: field_path.rfind(".")] if "." in field_path else ""
    for cond in conditionals:
        cond_field = cond.field
        if "." not in cond_field and parent:
            cond_field = f"{parent}.{cond_field}"
        cond_field_value = doc.get(cond_field)
        raw = _extract_raw_value(cond_field_value) if cond_field_value is not None else None

        met = _compare_values(raw, cond.operator, cond.value)

        if cond.unless:
            # :unless — field is required when condition is NOT met
            if met:
                return False
        else:
            # :if — field is required when condition IS met
            if not met:
                return False

    return True


def _compare_values(actual: Any, operator: str, expected: Any) -> bool:
    """Compare two values with the given operator."""
    if actual is None:
        # Null doesn't satisfy any condition except != with non-null
        if operator == "!=":
            return expected is not None
        return False

    # Try numeric comparison
    try:
        a_num = float(actual) if not isinstance(actual, (int, float)) else actual
        e_num = float(expected) if not isinstance(expected, (int, float)) else expected
        if operator == "=":
            return a_num == e_num
        if operator == "!=":
            return a_num != e_num
        if operator == ">":
            return a_num > e_num
        if operator == "<":
            return a_num < e_num
        if operator == ">=":
            return a_num >= e_num
        if operator == "<=":
            return a_num <= e_num
    except (ValueError, TypeError):
        pass

    # Fall back to string comparison
    a_str = str(actual)
    e_str = str(expected)

    if operator == "=":
        return a_str == e_str
    if operator == "!=":
        return a_str != e_str
    if operator == ">":
        return a_str > e_str
    if operator == "<":
        return a_str < e_str
    if operator == ">=":
        return a_str >= e_str
    if operator == "<=":
        return a_str <= e_str

    return False


# ─────────────────────────────────────────────────────────────────────────────
# V006 / V007: Array checks
# ─────────────────────────────────────────────────────────────────────────────


def _count_array_elements(doc: OdinDocument, array_path: str) -> int:
    """Count the number of elements in an array by scanning document paths."""
    prefix = array_path + "["
    indices: Set[int] = set()
    for path in doc.paths():
        if path.startswith(prefix):
            rest = path[len(prefix):]
            bracket_end = rest.find("]")
            if bracket_end > 0:
                idx_str = rest[:bracket_end]
                if idx_str.isdigit():
                    indices.add(int(idx_str))
    return len(indices)


def _check_arrays(
    doc: OdinDocument,
    schema: OdinSchema,
    errors: List[ValidationError],
    options: ValidateOptions,
) -> None:
    """Check V006 (array length) and V007 (array uniqueness)."""
    for array_path, schema_array in schema.arrays.items():
        count = _count_array_elements(doc, array_path)

        # V006: Array length violation
        if schema_array.min_items is not None and count < schema_array.min_items:
            errors.append(ValidationError(
                path=array_path,
                code="V006",
                message=f"Array length violation at {array_path}: minimum {schema_array.min_items}, got {count}",
                expected=f"min_items={schema_array.min_items}",
                actual=count,
            ))
            if options.fail_fast:
                return

        if schema_array.max_items is not None and count > schema_array.max_items:
            errors.append(ValidationError(
                path=array_path,
                code="V006",
                message=f"Array length violation at {array_path}: maximum {schema_array.max_items}, got {count}",
                expected=f"max_items={schema_array.max_items}",
                actual=count,
            ))
            if options.fail_fast:
                return

        # V007: Unique constraint on array
        if schema_array.unique:
            _check_array_uniqueness(array_path, count, doc, errors, options)
            if options.fail_fast and errors:
                return


def _check_array_uniqueness(
    array_path: str,
    count: int,
    doc: OdinDocument,
    errors: List[ValidationError],
    options: ValidateOptions,
) -> None:
    """Check that array elements are unique."""
    seen: Dict[Any, int] = {}
    for i in range(count):
        # Get the direct value at array_path[i] if it exists,
        # otherwise try to build a composite key from sub-fields
        elem_path = f"{array_path}[{i}]"
        value = doc.get(elem_path)
        if value is not None:
            raw = _extract_raw_value(value)
            key = repr(raw)
        else:
            # Composite: collect all sub-paths for this index
            prefix = elem_path + "."
            parts: List[str] = []
            for path in doc.paths():
                if path.startswith(prefix):
                    sub_val = doc.get(path)
                    if sub_val is not None:
                        relative = path[len(prefix):]
                        parts.append(f"{relative}={repr(_extract_raw_value(sub_val))}")
            key = "|".join(sorted(parts)) if parts else None

        if key is not None:
            if key in seen:
                errors.append(ValidationError(
                    path=array_path,
                    code="V007",
                    message=f"Unique constraint violation at {array_path}: duplicate value at index {i} (same as index {seen[key]})",
                    expected="unique values",
                    actual=key,
                ))
                if options.fail_fast:
                    return
            else:
                seen[key] = i


def _check_field_uniqueness(
    field_path: str,
    doc: OdinDocument,
    errors: List[ValidationError],
    options: ValidateOptions,
) -> None:
    """Check uniqueness for a field across array siblings.

    For a field like items[*].name, ensure all name values are unique
    across array elements.
    """
    # Find the array base and field suffix
    bracket_idx = field_path.rfind("[")
    if bracket_idx < 0:
        return  # Not an array field, uniqueness doesn't apply

    array_base = field_path[:bracket_idx]
    # Extract suffix after the bracket group
    rest = field_path[bracket_idx:]
    close_bracket = rest.find("]")
    if close_bracket < 0:
        return
    suffix = rest[close_bracket + 1:]

    # Collect values across all array indices
    seen: Dict[Any, int] = {}
    prefix = array_base + "["
    for path in doc.paths():
        if path.startswith(prefix) and path.endswith(suffix):
            mid = path[len(prefix):]
            close = mid.find("]")
            if close > 0:
                idx_str = mid[:close]
                if idx_str.isdigit():
                    idx = int(idx_str)
                    value = doc.get(path)
                    if value is not None:
                        raw = repr(_extract_raw_value(value))
                        if raw in seen:
                            errors.append(ValidationError(
                                path=path,
                                code="V007",
                                message=f"Unique constraint violation: duplicate value at {path}",
                                expected="unique values",
                                actual=raw,
                            ))
                            if options.fail_fast:
                                return
                        else:
                            seen[raw] = idx


# ─────────────────────────────────────────────────────────────────────────────
# V008 / V009: Object-level constraints
# ─────────────────────────────────────────────────────────────────────────────


def _check_object_constraints(
    doc: OdinDocument,
    schema: OdinSchema,
    errors: List[ValidationError],
    options: ValidateOptions,
) -> None:
    """Check V008 (invariant) and V009 (cardinality) constraints."""
    for section_path, constraints in schema.constraints.items():
        for constraint in constraints:
            if isinstance(constraint, SchemaInvariant):
                _check_invariant(section_path, constraint, doc, errors, options)
                if options.fail_fast and errors:
                    return

            elif isinstance(constraint, SchemaCardinality):
                _check_cardinality(section_path, constraint, doc, errors, options)
                if options.fail_fast and errors:
                    return


def _check_invariant(
    section_path: str,
    invariant: SchemaInvariant,
    doc: OdinDocument,
    errors: List[ValidationError],
    options: ValidateOptions,
) -> None:
    """Evaluate a simple invariant expression.

    Supports expressions like:
      field1 > field2
      field1 != field2
      field1 = "literal"
      field1 >= 0
    """
    expr = invariant.expression.strip()
    if not expr:
        return

    # Spec: any present-but-null operand makes the invariant evaluate to false.
    if _has_null_operand(expr, section_path, doc):
        errors.append(ValidationError(
            path=section_path,
            code="V008",
            message=f"Invariant violation: {expr}",
            expected=f"{expr} to be true",
            actual="null operand",
        ))
        return

    # Parse binary expression: left op right
    operators = ["!=", ">=", "<=", "=", ">", "<"]
    op = None
    left_str = None
    right_str = None

    for candidate_op in operators:
        idx = expr.find(candidate_op)
        if idx > 0:
            op = candidate_op
            left_str = expr[:idx].strip()
            right_str = expr[idx + len(candidate_op):].strip()
            break

    if op is None or left_str is None or right_str is None:
        return  # Unparseable expression — skip

    # Resolve left and right values
    left_val = _resolve_invariant_value(left_str, section_path, doc)
    right_val = _resolve_invariant_value(right_str, section_path, doc)

    # If either side can't be resolved, skip (don't fail on missing fields)
    if left_val is None or right_val is None:
        return

    if not _compare_values(left_val, op, right_val):
        errors.append(ValidationError(
            path=section_path,
            code="V008",
            message=f"Invariant violation: {expr}",
            expected=f"{left_str} {op} {right_str}",
            actual=f"{left_val} vs {right_val}",
        ))


_INVARIANT_KEYWORDS = {"true", "false"}


def _has_null_operand(expr: str, section_path: str, doc: OdinDocument) -> bool:
    """Return True if any field operand is present in the document with a null value.

    Absent fields are not treated as null operands; their absence is handled by
    field-level required validation.
    """
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_.]*", expr)
    for token in tokens:
        if token in _INVARIANT_KEYWORDS:
            continue
        full_path = f"{section_path}.{token}" if section_path else token
        value = doc.get(full_path)
        if value is None and section_path:
            value = doc.get(token)
        if isinstance(value, OdinNull):
            return True
    return False


def _resolve_invariant_value(
    token: str, section_path: str, doc: OdinDocument
) -> Any:
    """Resolve an invariant token to a Python value.

    Handles:
    - Quoted strings: "foo"
    - Numeric literals: 42, 3.14
    - Boolean literals: true, false
    - Arithmetic expressions: field1 + field2, field1 - field2
    - Field references: field_name (resolved relative to section_path)
    """
    # Quoted string literal
    if (token.startswith('"') and token.endswith('"')) or \
       (token.startswith("'") and token.endswith("'")):
        return token[1:-1]

    # Boolean literals
    if token.lower() == "true":
        return True
    if token.lower() == "false":
        return False

    # Numeric literal
    try:
        if "." in token:
            return float(token)
        return int(token)
    except ValueError:
        pass

    # Arithmetic expression: check for + or - between tokens
    for arith_op in [" + ", " - ", " * ", " / "]:
        if arith_op in token:
            parts = token.split(arith_op, 1)
            left = _resolve_invariant_value(parts[0].strip(), section_path, doc)
            right = _resolve_invariant_value(parts[1].strip(), section_path, doc)
            if left is not None and right is not None:
                try:
                    l_num = float(left) if not isinstance(left, (int, float)) else left
                    r_num = float(right) if not isinstance(right, (int, float)) else right
                    if arith_op == " + ":
                        return l_num + r_num
                    elif arith_op == " - ":
                        return l_num - r_num
                    elif arith_op == " * ":
                        return l_num * r_num
                    elif arith_op == " / " and r_num != 0:
                        return l_num / r_num
                except (ValueError, TypeError):
                    pass
            return None

    # Field reference — resolve relative to section path
    if section_path:
        full_path = f"{section_path}.{token}"
    else:
        full_path = token

    value = doc.get(full_path)
    if value is None:
        # Try without section prefix
        value = doc.get(token)
    if value is not None:
        return _extract_raw_value(value)

    return None


def _check_cardinality(
    section_path: str,
    cardinality: SchemaCardinality,
    doc: OdinDocument,
    errors: List[ValidationError],
    options: ValidateOptions,
) -> None:
    """Check cardinality constraints (V009).

    Types:
    - one_of: At least one of the fields must be present
    - exactly_one: Exactly one of the fields must be present
    - at_most_one: At most one of the fields may be present
    - of: Between min and max fields must be present
    """
    present_count = 0
    present_fields: List[str] = []

    for field_name in cardinality.fields:
        # Resolve field path relative to section
        if section_path:
            full_path = f"{section_path}.{field_name}"
        else:
            full_path = field_name

        value = doc.get(full_path)
        if value is not None and not isinstance(value, OdinNull):
            present_count += 1
            present_fields.append(field_name)

    card_type = cardinality.cardinality_type
    violation = False
    message = ""

    if card_type == "one_of":
        if present_count < 1:
            violation = True
            message = f"At least one of {cardinality.fields} must be present"

    elif card_type == "exactly_one":
        if present_count != 1:
            violation = True
            message = f"Exactly one of {cardinality.fields} must be present, found {present_count}"

    elif card_type == "at_most_one":
        if present_count > 1:
            violation = True
            message = f"At most one of {cardinality.fields} may be present, found {present_count}: {present_fields}"

    elif card_type == "of":
        if cardinality.min is not None and present_count < cardinality.min:
            violation = True
            message = f"At least {cardinality.min} of {cardinality.fields} must be present, found {present_count}"
        elif cardinality.max is not None and present_count > cardinality.max:
            violation = True
            message = f"At most {cardinality.max} of {cardinality.fields} may be present, found {present_count}"

    if violation:
        errors.append(ValidationError(
            path=section_path,
            code="V009",
            message=f"Cardinality constraint violation: {message}",
            expected=card_type,
            actual=present_count,
        ))


# ─────────────────────────────────────────────────────────────────────────────
# V011: Unknown field detection (strict mode)
# ─────────────────────────────────────────────────────────────────────────────


def _check_unknown_fields(
    doc: OdinDocument,
    schema: OdinSchema,
    errors: List[ValidationError],
    options: ValidateOptions,
) -> None:
    """Report fields in the document that are not defined in the schema."""
    known_paths: Set[str] = set(schema.fields.keys())

    # Also add array item field paths as known
    for array_path, schema_array in schema.arrays.items():
        for item_field_path in schema_array.item_fields.keys():
            known_paths.add(item_field_path)
        # Array base path patterns: arrayPath[N] and arrayPath[N].field
        known_paths.add(array_path)

    # Also add type-defined fields
    for type_name, schema_type in schema.types.items():
        for field_name in schema_type.fields.keys():
            known_paths.add(field_name)

    for path in doc.paths():
        if _is_known_path(path, known_paths, schema):
            continue
        errors.append(ValidationError(
            path=path,
            code="V011",
            message=f"Unknown field: {path}",
        ))
        if options.fail_fast:
            return


def _is_known_path(
    path: str, known_paths: Set[str], schema: OdinSchema
) -> bool:
    """Check if a document path matches any known schema path."""
    if path in known_paths:
        return True

    # Check if the path matches an array element pattern
    # e.g., items[0].name matches items[*].name or items
    for known in known_paths:
        if _path_matches_pattern(path, known):
            return True

    # Check array paths: path could be items[0], items[1], etc.
    for array_path in schema.arrays:
        if path.startswith(array_path + "["):
            return True

    return False


def _path_matches_pattern(path: str, pattern: str) -> bool:
    """Check if a concrete path matches a schema path pattern.

    Handles array index wildcards: items[0].name matches items[*].name.
    """
    if path == pattern:
        return True

    # Replace concrete indices [N] with [*] for comparison
    normalized = re.sub(r'\[\d+\]', '[*]', path)
    if normalized == pattern:
        return True

    # Also check if pattern without wildcards matches
    pattern_normalized = re.sub(r'\[\*\]', '[0]', pattern)
    path_base = re.sub(r'\[\d+\]', '[0]', path)
    if path_base == pattern_normalized:
        return True

    return False


# ─────────────────────────────────────────────────────────────────────────────
# V012 / V013: Reference checks
# ─────────────────────────────────────────────────────────────────────────────


def _check_references(
    doc: OdinDocument,
    errors: List[ValidationError],
    options: ValidateOptions,
    schema: Optional[OdinSchema] = None,
    type_registry: Optional[Dict[str, Any]] = None,
) -> None:
    """Check V012 (circular references) and V013 (unresolved references)."""
    # Collect all reference paths from the document
    ref_map: Dict[str, str] = {}  # path -> target_path
    for path in doc.paths():
        value = doc.get(path)
        if isinstance(value, OdinReference):
            ref_map[path] = value.path

    # V013: Unresolved document references
    all_paths = set(doc.paths())
    for ref_path, target_path in ref_map.items():
        if target_path not in all_paths:
            errors.append(ValidationError(
                path=ref_path,
                code="V013",
                message=f"Unresolved reference: {target_path}",
                expected="existing path",
                actual=target_path,
            ))
            if options.fail_fast:
                return

    # V012: Circular document references
    for start_path in ref_map:
        visited: Set[str] = set()
        current = start_path
        while current in ref_map:
            if current in visited:
                errors.append(ValidationError(
                    path=start_path,
                    code="V012",
                    message=f"Circular reference detected starting at {start_path}",
                    expected="non-circular reference chain",
                    actual=f"cycle involving {current}",
                ))
                if options.fail_fast:
                    return
                break
            visited.add(current)
            current = ref_map[current]

    # Schema-level reference checks
    if schema is not None:
        _check_schema_references(schema, errors, options, type_registry)


def lookup_type(
    schema: OdinSchema,
    name: str,
    type_registry: Optional[Dict[str, Any]] = None,
) -> Optional[SchemaType]:
    """Resolve a type reference: registry (alias.name) first, then local types."""
    if type_registry and name in type_registry:
        return type_registry[name]
    return schema.types.get(name)


def _split_typeref_members(name: str) -> List[str]:
    """Split an intersection typeRef name (a&b) into its member type names."""
    return [n.strip() for n in name.split("&") if n.strip()]


def _object_present(doc: OdinDocument, path: str) -> bool:
    """True if the path itself or any descendant path holds a value."""
    if doc.get(path) is not None:
        return True
    prefix = path + "."
    return any(p.startswith(prefix) for p in doc.paths())


def _expand_type_compositions(
    doc: OdinDocument,
    schema: OdinSchema,
    type_registry: Optional[Dict[str, Any]] = None,
) -> Dict[str, SchemaField]:
    """Expand object compositions and field-level type references into fields.

    - A `<path>._composition` typeRef merges every referenced (and intersected)
      type's fields under the parent path.
    - A field typed `@SomeType` enforces that type's fields under the field path
      when the sub-object is present or the field is required.
    """
    result: Dict[str, SchemaField] = {}

    # First pass: expand explicit compositions.
    for path, fld in schema.fields.items():
        if path.endswith("._composition") and isinstance(fld.field_type, TypeRefType):
            parent = path[: -len("._composition")]
            for member in _split_typeref_members(fld.field_type.name):
                type_def = lookup_type(schema, member, type_registry)
                if type_def:
                    for field_name, type_field in type_def.fields.items():
                        if field_name == "_composition":
                            continue
                        full = f"{parent}.{field_name}"
                        result[full] = _rebind(type_field, full)

    # Second pass: explicit fields (override inherited, skip composition markers).
    for path, fld in schema.fields.items():
        if path.endswith("._composition"):
            continue
        result[path] = fld

    # Third pass: a field typed @SomeType enforces the referenced type's fields.
    for path, fld in list(result.items()):
        if path.endswith("._composition"):
            continue
        ref_name = None
        if isinstance(fld.field_type, TypeRefType):
            ref_name = fld.field_type.name
        elif isinstance(fld.field_type, ReferenceType):
            ref_name = fld.field_type.target_path
        if not ref_name:
            continue

        members = _split_typeref_members(ref_name)
        type_defs = [t for t in (lookup_type(schema, m, type_registry) for m in members) if t]
        if not type_defs:
            continue  # runtime reference, not a defined type

        if not _object_present(doc, path) and not fld.required:
            continue

        for type_def in type_defs:
            for field_name, type_field in type_def.fields.items():
                if field_name == "_composition":
                    continue
                full = f"{path}.{field_name}"
                if full not in result:
                    result[full] = _rebind(type_field, full)

    return result


def _rebind(field_def: SchemaField, new_path: str) -> SchemaField:
    """Copy a SchemaField under a new path (shallow, preserves type/constraints)."""
    return SchemaField(
        path=new_path,
        field_type=field_def.field_type,
        required=field_def.required,
        nullable=field_def.nullable,
        redacted=field_def.redacted,
        deprecated=field_def.deprecated,
        computed=field_def.computed,
        immutable=field_def.immutable,
        constraints=list(field_def.constraints),
        conditionals=list(field_def.conditionals),
        default_value=field_def.default_value,
        description=field_def.description,
    )


def _check_schema_references(
    schema: OdinSchema,
    errors: List[ValidationError],
    options: ValidateOptions,
    type_registry: Optional[Dict[str, Any]] = None,
) -> None:
    """Check V012/V013 for schema-level type references."""
    all_type_names = set(schema.types.keys())

    # V013: Unresolved top-level field type references (intersections carry
    # multiple &-joined member names).
    for field_path, field_def in schema.fields.items():
        if isinstance(field_def.field_type, TypeRefType):
            for name in _split_typeref_members(field_def.field_type.name):
                if lookup_type(schema, name, type_registry) is None:
                    errors.append(ValidationError(
                        path=field_path,
                        code="V013",
                        message=f"Unresolved type reference: @{name}",
                        expected="defined type",
                        actual=name,
                    ))
                    if options.fail_fast:
                        return

    # V012: Circular schema type references among locally defined types
    type_refs: Dict[str, List[str]] = {}
    for type_name, schema_type in schema.types.items():
        refs = []
        for field_def in schema_type.fields.values():
            if isinstance(field_def.field_type, TypeRefType):
                refs.append(field_def.field_type.name)
        type_refs[type_name] = refs

    for start_type in type_refs:
        visited: Set[str] = set()
        stack = [start_type]
        while stack:
            current = stack.pop()
            if current in visited:
                errors.append(ValidationError(
                    path=f"@{start_type}",
                    code="V012",
                    message=f"Circular type reference detected: @{start_type}",
                    expected="non-circular type chain",
                    actual=f"cycle involving @{current}",
                ))
                if options.fail_fast:
                    return
                break
            visited.add(current)
            for ref in type_refs.get(current, []):
                if ref in all_type_names:
                    stack.append(ref)


# ─────────────────────────────────────────────────────────────────────────────
# Type matching helpers
# ─────────────────────────────────────────────────────────────────────────────


def _type_matches(
    value: OdinValue,
    field_type: SchemaFieldType,
    schema: OdinSchema,
    type_registry: Optional[Dict[str, Any]] = None,
) -> bool:
    """Check if a value matches the expected field type."""
    if isinstance(field_type, StringType):
        return isinstance(value, (OdinString, OdinDate, OdinTimestamp, OdinTime))
    if isinstance(field_type, BooleanType):
        return isinstance(value, OdinBoolean)
    if isinstance(field_type, NumberType):
        return isinstance(value, (OdinNumber, OdinInteger))
    if isinstance(field_type, IntegerType):
        return isinstance(value, OdinInteger)
    if isinstance(field_type, (DecimalType, CurrencyType)):
        return isinstance(value, (OdinCurrency, OdinNumber))
    if isinstance(field_type, PercentType):
        return isinstance(value, (OdinPercent, OdinNumber))
    if isinstance(field_type, DateType):
        return isinstance(value, OdinDate)
    if isinstance(field_type, TimestampType):
        return isinstance(value, OdinTimestamp)
    if isinstance(field_type, TimeType):
        return isinstance(value, OdinTime)
    if isinstance(field_type, DurationType):
        return isinstance(value, OdinDuration)
    if isinstance(field_type, ReferenceType):
        return isinstance(value, OdinReference)
    if isinstance(field_type, BinaryType):
        return isinstance(value, OdinBinary)
    if isinstance(field_type, NullType):
        return isinstance(value, OdinNull)
    if isinstance(field_type, EnumType):
        return isinstance(value, OdinString)
    if isinstance(field_type, UnionType):
        return any(_type_matches(value, t, schema, type_registry) for t in field_type.types)
    if isinstance(field_type, TypeRefType):
        # Resolve type reference
        ref_type = lookup_type(schema, field_type.name, type_registry)
        if ref_type is None:
            return True  # Unknown type reference — don't fail
        # For type refs, check that value fields match the type's field definitions
        # This is a structural check — the value itself passes if it's a valid ODIN value
        return True
    return True


def _value_type_name(value: OdinValue) -> str:
    """Get a human-readable type name for a value."""
    if isinstance(value, OdinNull):
        return "null"
    if isinstance(value, OdinBoolean):
        return "boolean"
    if isinstance(value, OdinString):
        return "string"
    if isinstance(value, OdinInteger):
        return "integer"
    if isinstance(value, OdinNumber):
        return "number"
    if isinstance(value, OdinCurrency):
        return "currency"
    if isinstance(value, OdinPercent):
        return "percent"
    if isinstance(value, OdinDate):
        return "date"
    if isinstance(value, OdinTimestamp):
        return "timestamp"
    if isinstance(value, OdinTime):
        return "time"
    if isinstance(value, OdinDuration):
        return "duration"
    if isinstance(value, OdinReference):
        return "reference"
    if isinstance(value, OdinBinary):
        return "binary"
    return "unknown"


def _field_type_name(field_type: SchemaFieldType) -> str:
    """Get a human-readable name for a schema field type."""
    return getattr(field_type, "kind", "unknown")


def _extract_raw_value(value: OdinValue) -> Any:
    """Extract the raw Python value from an OdinValue."""
    if isinstance(value, OdinNull):
        return None
    if isinstance(value, OdinBoolean):
        return value.value
    if isinstance(value, OdinString):
        return value.value
    if isinstance(value, OdinInteger):
        return value.value
    if isinstance(value, OdinNumber):
        return value.value
    if isinstance(value, OdinCurrency):
        return value.value
    if isinstance(value, OdinPercent):
        return value.value
    return str(getattr(value, "value", ""))
