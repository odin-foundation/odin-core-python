"""Transform execution engine - execute ODIN transforms on source data."""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from odin.transform.dyn_value import DynValue, DynType
from odin.transform.types import (
    OdinTransform,
    TransformSegment,
    FieldMapping,
    FieldExpression,
    CopyExpression,
    TransformExpression,
    LiteralExpression,
    ObjectExpression,
    VerbCall,
    VerbArg,
    ReferenceArg,
    LiteralArg,
    VerbCallArg,
    Directive,
    ConfidentialMode,
    DiscriminatorType,
    SourceDiscriminator,
    TransformResult,
    TransformError,
    TransformWarning,
)
from odin.transform.verb_registry import VerbRegistry
import re as _re

from odin.transform.errors import (
    dangling_branch_error,
    validation_error,
    unknown_verb_error,
    source_path_not_found_error,
    source_path_not_found_warning,
    source_missing_error,
    loop_source_not_array_error,
    invalid_output_format_error,
    invalid_verb_args_error,
    invalid_modifier_warning,
    position_overflow_warning,
    CodedTransformError,
)
from odin.transform.verbs.collection_verbs import _check_filter_condition
from odin.types.document import OdinModifiers
from odin.types.values import (
    OdinValue, OdinNull, OdinBoolean, OdinString, OdinNumber,
    OdinInteger, OdinCurrency, OdinPercent, OdinReference,
    OdinDate, OdinTimestamp, OdinTime, OdinDuration, OdinBinary,
)

MAX_LOOP_NESTING = 10

# Cap on interpolations per template to bound resource use
MAX_INTERPOLATIONS = 320

# Matches ${...} with an optional leading backslash for escaped markers
_INTERP_RE = _re.compile(r"\\?\$\{([^}]+)\}")

# Verbs that require lazy evaluation of their branch arguments
_LAZY_EVAL_VERBS = frozenset({"ifElse", "ternary", "switch"})

# Positional argument types for strict-type validation (subset; "number" accepts
# number/integer/currency). Verbs absent here skip strict validation.
_VERB_ARG_TYPES: Dict[str, List[str]] = {
    "abs": ["number"], "round": ["number", "integer"], "floor": ["number"],
    "ceil": ["number"], "trunc": ["number"], "sign": ["number"],
    "negate": ["number"], "sqrt": ["number"], "exp": ["number"],
    "add": ["number", "number"], "subtract": ["number", "number"],
    "multiply": ["number", "number"], "divide": ["number", "number"],
    "mod": ["number", "number"], "pow": ["number", "number"],
    "log": ["number", "number"], "clamp": ["number", "number", "number"],
}


def _dyn_type_name(v: DynValue) -> str:
    """Map a DynValue to a transform type name for strict validation."""
    if v.is_null():
        return "null"
    if v.is_integer():
        return "integer"
    if v.type in (DynType.CURRENCY, DynType.CURRENCY_RAW):
        return "currency"
    if v.is_number():
        return "number"
    if v.is_bool():
        return "boolean"
    if v.is_array():
        return "array"
    if v.is_object():
        return "object"
    if v.is_string():
        return "string"
    return "any"


def _type_matches(actual: str, expected: str) -> bool:
    if expected == "any" or actual == "null":
        return True
    if expected == "number":
        return actual in ("number", "integer", "currency")
    return actual == expected


# Modifiers valid only for specific target formats.
_FORMAT_SPECIFIC_MODIFIERS: Dict[str, frozenset] = {
    "pos": frozenset({"fixed-width", "fwf"}),
    "len": frozenset({"fixed-width", "fwf"}),
    "leftPad": frozenset({"fixed-width", "fwf"}),
    "rightPad": frozenset({"fixed-width", "fwf"}),
    "truncate": frozenset({"fixed-width", "fwf"}),
    "element": frozenset({"xml"}),
    "attr": frozenset({"xml"}),
    "ns": frozenset({"xml"}),
    "cdata": frozenset({"xml"}),
    "omitEmpty": frozenset({"xml", "json"}),
    "raw": frozenset({"json"}),
}


def _directive_int(directives, name: str):
    """Return the integer value of a named directive, or None."""
    for d in directives:
        if d.name == name and d.value is not None:
            try:
                return int(str(d.value).strip())
            except (ValueError, TypeError):
                return None
    return None


def _is_modifier_compatible(modifier: str, fmt: str) -> bool:
    allowed = _FORMAT_SPECIFIC_MODIFIERS.get(modifier)
    if allowed is None:
        return True
    return fmt in allowed


def _validate_verb_arg_types(verb: str, args: List[DynValue]):
    """Return a T002 error when a built-in verb receives an arg of the wrong type."""
    sig = _VERB_ARG_TYPES.get(verb)
    if sig is None:
        return None
    for i, arg in enumerate(args):
        expected = sig[i] if i < len(sig) else "any"
        if not _type_matches(_dyn_type_name(arg), expected):
            return invalid_verb_args_error(verb, expected, len(args))
    return None


class VerbContext:
    """Context available to verb functions during execution."""

    __slots__ = (
        "source", "loop_vars", "accumulators", "tables",
        "constants", "global_output", "on_missing", "errors", "warnings",
    )

    def __init__(self) -> None:
        self.source: DynValue = DynValue.of_null()
        self.loop_vars: Dict[str, DynValue] = {}
        self.accumulators: Dict[str, DynValue] = {}
        self.tables: Dict[str, Any] = {}
        self.constants: Dict[str, DynValue] = {}
        self.global_output: DynValue = DynValue.of_null()
        self.on_missing: Optional[str] = None
        self.errors: List[TransformError] = []
        self.warnings: List[TransformWarning] = []


class _ExecContext:
    """Internal execution context."""

    __slots__ = (
        "source", "constants", "accumulators", "tables",
        "loop_vars", "warnings", "errors",
        "enforce_confidential", "global_output", "field_modifiers",
        "source_format", "target_format", "verb_registry", "loop_depth",
        "on_validation", "on_error", "on_missing", "strict_types", "line_width",
    )

    def __init__(self) -> None:
        self.source: DynValue = DynValue.of_null()
        self.constants: Dict[str, DynValue] = {}
        self.accumulators: Dict[str, DynValue] = {}
        self.tables: Dict[str, Any] = {}
        self.loop_vars: Dict[str, DynValue] = {}
        self.warnings: List[TransformWarning] = []
        self.errors: List[TransformError] = []
        self.enforce_confidential: Optional[ConfidentialMode] = None
        self.global_output: DynValue = DynValue.of_object({})
        self.field_modifiers: Dict[str, OdinModifiers] = {}
        self.source_format: str = ""
        self.target_format: str = ""
        self.verb_registry: Optional[VerbRegistry] = None
        self.loop_depth: int = 0
        self.on_validation: str = "fail"
        self.on_error: str = "fail"
        self.on_missing: Optional[str] = None
        self.strict_types: bool = False
        self.line_width: Optional[int] = None


class TransformEngine:
    """ODIN transform execution engine."""

    def __init__(
        self,
        registry: VerbRegistry,
        import_resolver: Optional[Callable[[str], Optional[str]]] = None,
    ) -> None:
        self.registry = registry
        self.import_resolver = import_resolver

    def execute(self, transform: OdinTransform, source: Any) -> TransformResult:
        """Execute a transform on source data."""
        if self.import_resolver is not None and transform.imports:
            self._resolve_imports(transform, self.import_resolver)
        # Check for multi-record discriminator mode
        discriminator = transform.source.discriminator if transform.source else None
        source_format = transform.source.format if transform.source else ""

        if discriminator and isinstance(source, (str, DynValue)):
            # For string/DynValue sources with discriminator, use multi-record mode
            raw_str = None
            if isinstance(source, str):
                raw_str = source
            elif isinstance(source, DynValue):
                # Try raw source stashed by CSV parser
                if hasattr(source, '_raw_source') and source._raw_source:
                    raw_str = source._raw_source
                elif source.is_string():
                    raw_str = source.as_string()
            if raw_str and source_format in ("csv", "delimited", "fixed-width", "fwf", "fixed_width", "flat"):
                return self._execute_multi_record(transform, raw_str, discriminator, source_format)

        ctx = self._build_context(transform, source)
        output = DynValue.of_object({})

        # Group segments by pass: ordered passes (1, 2, ...) then pass 0.
        # The conditional chain controller runs within each pass group so chains
        # break at pass boundaries.
        pass_groups = _group_segments_by_pass(transform.segments)

        is_first = True
        for _pass_num, group in pass_groups:
            if not is_first:
                # Reset non-persist accumulators on pass change
                for name, acc_def in transform.accumulators.items():
                    if not acc_def.persist:
                        ctx.accumulators[name] = _odin_value_to_dyn(acc_def.initial)
            is_first = False

            output = self._process_segment_list(group, ctx, output, "")
            ctx.global_output = output

        # Consolidate indexed segments (e.g., vehicles[0], vehicles[1] → vehicles array)
        output = _consolidate_indexed_keys(output)

        # Confidential enforcement
        if ctx.enforce_confidential is not None:
            _apply_confidential_enforcement(
                transform.segments, ctx.enforce_confidential, output
            )

        # Format output
        formatted = self._format_output(output, transform, ctx.field_modifiers, ctx.errors)

        return TransformResult(
            success=len(ctx.errors) == 0,
            output=output,
            formatted=formatted,
            errors=ctx.errors,
            warnings=ctx.warnings,
            output_modifiers=ctx.field_modifiers,
        )

    def _resolve_imports(
        self,
        transform: OdinTransform,
        resolver: Callable[[str], Optional[str]],
    ) -> None:
        """Merge imported tables, constants, accumulators, and named segments.

        Local declarations win over imported ones; imported segments are appended
        so their mappings remain referenceable. An import the resolver cannot
        satisfy (returns None) is skipped.
        """
        from odin.transform.transform_parser import parse_transform as _parse

        seen: set = set()
        existing_paths = {s.name for s in transform.segments}
        for imp in transform.imports:
            if imp.path in seen:
                continue
            seen.add(imp.path)

            text = resolver(imp.path)
            if text is None:
                continue

            imported = _parse(text)

            for name, table in imported.tables.items():
                if name not in transform.tables:
                    transform.tables[name] = table
            for name, value in imported.constants.items():
                if name not in transform.constants:
                    transform.constants[name] = value
            for name, acc in imported.accumulators.items():
                if name not in transform.accumulators:
                    transform.accumulators[name] = acc
            for segment in imported.segments:
                if segment.name == "" or segment.name in existing_paths:
                    continue
                transform.segments.append(segment)
                existing_paths.add(segment.name)

    def invoke_verb(self, name: str, args: List[DynValue], ctx: Optional[VerbContext] = None) -> DynValue:
        """Invoke a verb directly (for unit testing)."""
        if ctx is None:
            ctx = VerbContext()
        fn = self.registry.get(name)
        if fn is None:
            return DynValue.of_null()
        return fn(args, ctx)

    def _build_context(self, transform: OdinTransform, source: Any) -> _ExecContext:
        ctx = _ExecContext()
        ctx.source = _python_to_dyn(source)
        ctx.verb_registry = self.registry
        ctx.enforce_confidential = transform.enforce_confidential
        ctx.source_format = (transform.source.format if transform.source else "")
        ctx.target_format = transform.target.format if transform.target else ""
        ctx.on_validation = transform.target.options.get("onValidation", "fail")
        ctx.on_error = transform.target.options.get("onError", "fail")
        ctx.on_missing = transform.target.options.get("onMissing")
        ctx.strict_types = transform.strict_types
        lw = transform.target.options.get("lineWidth") if transform.target else None
        if lw:
            try:
                ctx.line_width = int(lw)
            except (ValueError, TypeError):
                ctx.line_width = None

        # Init constants
        for name, value in transform.constants.items():
            ctx.constants[name] = _odin_value_to_dyn(value)

        # Init accumulators
        for name, acc_def in transform.accumulators.items():
            ctx.accumulators[name] = _odin_value_to_dyn(acc_def.initial)

        # Init tables
        ctx.tables = {name: tbl for name, tbl in transform.tables.items()}

        return ctx

    def _execute_multi_record(
        self,
        transform: OdinTransform,
        raw_input: str,
        discriminator: SourceDiscriminator,
        source_format: str,
    ) -> TransformResult:
        """Execute a multi-record transform with discriminator-based routing."""
        import re as _re

        ctx = self._build_context(transform, raw_input)
        ctx.source_format = source_format

        # Build segment routing map: discriminator value -> segment
        segment_map: Dict[str, TransformSegment] = {}
        for seg in transform.segments:
            if seg.segment_discriminator is not None:
                val = seg.segment_discriminator.value
                if val:
                    segment_map[val] = seg

        # Initialize array accumulators for array segments
        array_accumulators: Dict[str, List[DynValue]] = {}
        for seg in transform.segments:
            if seg.segment_discriminator is not None and seg.is_array:
                clean_name = seg.name[:-2] if seg.name.endswith("[]") else seg.name
                array_accumulators[clean_name] = []

        # Split input into records
        records = [line for line in _re.split(r'\r?\n', raw_input) if line.strip()]

        output = DynValue.of_object({})

        for record_index, record in enumerate(records):
            # Extract discriminator value
            disc_value = _extract_discriminator_value(record, discriminator, source_format)

            # Find matching segment
            seg = segment_map.get(disc_value)
            if seg is None:
                if ctx.on_error == "fail":
                    ctx.errors.append(TransformError(
                        message=f"Unknown record type '{disc_value}' at record {record_index + 1}",
                        path="",
                    ))
                elif ctx.on_error == "warn":
                    ctx.warnings.append(TransformWarning(
                        message=f"Unknown record type '{disc_value}' at record {record_index + 1}",
                        path="",
                    ))
                continue

            # Parse record into source object
            record_source = _parse_record(record, source_format)

            # Create context for this record
            record_ctx = _ExecContext()
            record_ctx.source = record_source
            record_ctx.verb_registry = self.registry
            record_ctx.enforce_confidential = transform.enforce_confidential
            record_ctx.source_format = source_format
            record_ctx.constants = ctx.constants
            record_ctx.accumulators = ctx.accumulators
            record_ctx.tables = ctx.tables
            record_ctx.global_output = output
            record_ctx.field_modifiers = ctx.field_modifiers
            record_ctx.on_validation = ctx.on_validation
            record_ctx.on_error = ctx.on_error
            record_ctx.on_missing = ctx.on_missing

            # Process segment mappings
            record_output = DynValue.of_object({})
            for mapping in seg.mappings:
                # Skip _type mapping (it's the discriminator, not an output field)
                if mapping.target == "_type":
                    continue
                record_output = self._process_mapping(
                    mapping, record_ctx, record_source, record_output, ""
                )

            # Merge errors/warnings and modifiers from record context
            ctx.errors.extend(record_ctx.errors)
            ctx.warnings.extend(record_ctx.warnings)
            ctx.field_modifiers.update(record_ctx.field_modifiers)

            # Merge into output
            clean_name = seg.name[:-2] if seg.name.endswith("[]") else seg.name
            if seg.is_array:
                arr = array_accumulators.get(clean_name)
                if arr is not None:
                    arr.append(record_output)
            else:
                _set_path(output, clean_name, record_output)

        # Apply array accumulators to output
        for path, arr in array_accumulators.items():
            _set_path(output, path, DynValue.of_array(arr))

        # Format output
        formatted = self._format_output(output, transform, ctx.field_modifiers, ctx.errors)

        return TransformResult(
            success=len(ctx.errors) == 0,
            output=output,
            formatted=formatted,
            errors=ctx.errors,
            warnings=ctx.warnings,
            output_modifiers=ctx.field_modifiers,
        )

    def _evaluate_segment_condition(
        self, segment: TransformSegment, ctx: _ExecContext
    ) -> bool:
        """Evaluate a segment condition: a verb expression, or a legacy infix string."""
        if segment.condition_expr is not None:
            return _is_truthy(
                self._evaluate_expression(
                    segment.condition_expr, ctx, ctx.source, ctx.global_output
                )
            )
        if segment.condition is not None:
            return _evaluate_condition(segment.condition, ctx.source, ctx)
        return True

    def _process_segment_list(
        self,
        segments: List[TransformSegment],
        ctx: _ExecContext,
        output: DynValue,
        path_prefix: str,
    ) -> DynValue:
        """Process a list of segments, honoring if/elif/else conditional chains.

        A chain is a run of consecutive segments: one `if`, then any `elif`, then an
        optional `else`. Only the first branch whose condition holds is processed.
        """
        # 'none' = no active chain; 'pending' = chain open, none taken; 'taken' = a branch taken
        branch = "none"

        for segment in segments:
            kind = segment.branch
            if kind == "if":
                taken = self._evaluate_segment_condition(segment, ctx)
                branch = "taken" if taken else "pending"
                if taken:
                    output = self._process_segment(segment, ctx, output, path_prefix)
            elif kind == "elif":
                if branch == "none":
                    ctx.errors.append(dangling_branch_error("elif", segment.name))
                    continue
                if branch == "taken":
                    continue
                taken = self._evaluate_segment_condition(segment, ctx)
                branch = "taken" if taken else "pending"
                if taken:
                    output = self._process_segment(segment, ctx, output, path_prefix)
            elif kind == "else":
                if branch == "none":
                    ctx.errors.append(dangling_branch_error("else", segment.name))
                    continue
                if branch == "pending":
                    output = self._process_segment(segment, ctx, output, path_prefix)
                branch = "none"
            else:
                branch = "none"
                output = self._process_segment(segment, ctx, output, path_prefix)
            ctx.global_output = output

        return output

    def _process_segment(
        self,
        segment: TransformSegment,
        ctx: _ExecContext,
        output: DynValue,
        path_prefix: str,
    ) -> DynValue:
        # Discriminator check (only for import; export _type has empty path)
        if segment.segment_discriminator is not None:
            disc = segment.segment_discriminator
            if disc.path:
                disc_val = _resolve_path(ctx.source, disc.path, ctx)
                disc_str = disc_val.as_string() if not disc_val.is_null() else ""
                if disc_str != disc.value:
                    return output

        name = segment.name
        is_root = name == "" or name == "$" or name == "_root"

        clean_name = name[:-2] if name.endswith("[]") else name

        current_prefix = (
            path_prefix if is_root
            else (clean_name if not path_prefix else f"{path_prefix}.{clean_name}")
        )

        # Computation-only sink: a `_`-prefixed section runs for side effects
        # only (accumulators, verbs) and never appears in the output.
        is_sink = clean_name.startswith("_") and not is_root

        # Literal block: emit interpolated text lines instead of field mappings.
        if segment.is_literal:
            return self._process_literal_segment(
                segment, ctx, output, clean_name, is_root,
            )

        # Nested cross-product loops (one or more :loop directives).
        if segment.loops and segment.is_array:
            if ctx.loop_depth >= MAX_LOOP_NESTING:
                ctx.errors.append(TransformError(
                    message="Maximum loop nesting exceeded",
                    path=clean_name,
                ))
                return output

            old_loop_vars = dict(ctx.loop_vars)
            old_depth = ctx.loop_depth
            results: List[DynValue] = []
            # A non-array loop source raises a coded error honoring onError.
            try:
                self._iterate_loops(
                    segment, 0, ctx, ctx.source, results, current_prefix, None,
                )
            except CodedTransformError as e:
                ctx.loop_vars = old_loop_vars
                ctx.loop_depth = old_depth
                if ctx.on_error == "warn":
                    err = e.transform_error
                    ctx.warnings.append(TransformWarning(
                        message=err.message, path=err.path, code=err.code,
                    ))
                elif ctx.on_error != "skip":
                    ctx.errors.append(e.transform_error)
                return output
            ctx.loop_vars = old_loop_vars
            ctx.loop_depth = old_depth

            if is_sink:
                return output

            array_result = DynValue.of_array(results)
            if not is_root:
                _set_path(output, clean_name, array_result)
            else:
                output = array_result
            return output

        # Array loop
        if segment.source_path is not None:
            array_val = _resolve_path(ctx.source, segment.source_path, ctx)
            if array_val is None:
                array_val = DynValue.of_null()

            if array_val.is_array():
                items = array_val.as_array()
            elif not array_val.is_null():
                items = [array_val]
            else:
                items = []

            if ctx.loop_depth >= MAX_LOOP_NESTING:
                ctx.errors.append(TransformError(
                    message="Maximum loop nesting exceeded",
                    path=clean_name,
                ))
                return output

            ctx.loop_depth += 1
            result_items: List[DynValue] = []

            old_loop_vars = dict(ctx.loop_vars)
            counter_name = segment.counter_name

            # Check if segment has ONLY "_" target mappings (identity/value-only semantics)
            is_value_only = all(m.target == "_" for m in segment.mappings)

            for idx, item in enumerate(items):
                ctx.loop_vars["_item"] = item
                ctx.loop_vars["_index"] = DynValue.of_integer(idx)
                ctx.loop_vars["_length"] = DynValue.of_integer(len(items))
                # A named counter is readable by name and via @$accumulator.<name>.
                if counter_name:
                    counter_val = DynValue.of_integer(idx)
                    ctx.loop_vars[counter_name] = counter_val
                    ctx.accumulators[counter_name] = counter_val

                if is_value_only:
                    # Identity: the value IS the row
                    val = DynValue.of_null()
                    for mapping in segment.mappings:
                        val = self._process_mapping(
                            mapping, ctx, item, val, current_prefix,
                            is_loop=True,
                        )
                    result_items.append(val)
                else:
                    row_output = DynValue.of_object({})
                    for mapping in segment.mappings:
                        if mapping.target == "_":
                            # Side-effect only: evaluate but don't replace row
                            self._evaluate_expression(mapping.expression, ctx, item, row_output)
                        else:
                            row_output = self._process_mapping(
                                mapping, ctx, item, row_output, current_prefix,
                                is_loop=False,
                            )
                    result_items.append(row_output)

            ctx.loop_vars = old_loop_vars
            ctx.loop_depth -= 1

            if is_sink:
                return output

            array_result = DynValue.of_array(result_items)
            if not is_root:
                _set_path(output, clean_name, array_result)
            else:
                output = array_result

            return output

        # Non-loop discard segment: run mappings for side effects only.
        if is_sink:
            for mapping in segment.mappings:
                self._process_mapping(mapping, ctx, ctx.source, output, current_prefix)
            return output

        # Standard segment (no loop)
        if is_root:
            for mapping in segment.mappings:
                output = self._process_mapping(mapping, ctx, ctx.source, output, path_prefix)
            output = self._process_segment_list(segment.children, ctx, output, path_prefix)
        else:
            seg_output = _get_or_create_object(output, clean_name)
            for mapping in segment.mappings:
                seg_output = self._process_mapping(
                    mapping, ctx, ctx.source, seg_output, current_prefix,
                )
            seg_output = self._process_segment_list(
                segment.children, ctx, seg_output, current_prefix
            )
            _set_path(output, clean_name, seg_output)

        return output

    def _iterate_loops(
        self,
        segment: TransformSegment,
        depth: int,
        ctx: _ExecContext,
        base: DynValue,
        results: List[DynValue],
        current_prefix: str,
        on_item: Optional[Callable[[], None]],
    ) -> None:
        """Drive nested :loop directives as a cross-product.

        Each level binds its alias and current item, then recurses; the innermost
        level emits one element per item. A relative inner path (`.field`) resolves
        against the enclosing item. A non-array source at any level yields no rows.
        """
        if ctx.loop_depth >= MAX_LOOP_NESTING:
            ctx.errors.append(TransformError(
                message="Maximum loop nesting exceeded",
                path=segment.name,
            ))
            return

        loops = segment.loops
        loop = loops[depth]
        is_outermost = depth == 0
        is_innermost = depth == len(loops) - 1

        loop_path = loop.path or ""
        if loop_path.startswith("@"):
            loop_path = loop_path[1:]

        if loop_path.startswith("."):
            items_val = _resolve_sub_path(ctx.loop_vars.get("_item"), loop_path[1:])
        elif is_outermost:
            items_val = _resolve_path(ctx.source, loop_path, ctx)
        else:
            first_part = loop_path.split(".")[0]
            if first_part in ctx.loop_vars:
                aliased = ctx.loop_vars[first_part]
                rest = loop_path[len(first_part) + 1:] if "." in loop_path else ""
                items_val = _resolve_sub_path(aliased, rest) if rest else aliased
            else:
                items_val = _resolve_sub_path(base, loop_path)

        if items_val is None or not items_val.is_array():
            # A present non-array scalar is a T009 error; an absent (None/null)
            # source yields zero rows silently.
            if items_val is not None and not items_val.is_null():
                raise CodedTransformError(
                    loop_source_not_array_error(loop_path, segment.name))
            return

        items = items_val.as_array()
        counter_name = segment.counter_name

        ctx.loop_depth += 1
        saved_vars = dict(ctx.loop_vars)
        for idx, item in enumerate(items):
            ctx.loop_vars["_item"] = item
            ctx.loop_vars["_index"] = DynValue.of_integer(idx)
            ctx.loop_vars["_length"] = DynValue.of_integer(len(items))
            if loop.alias:
                ctx.loop_vars[loop.alias] = item
            if counter_name and is_innermost:
                counter_val = DynValue.of_integer(idx)
                ctx.loop_vars[counter_name] = counter_val
                ctx.accumulators[counter_name] = counter_val

            if not is_innermost:
                self._iterate_loops(
                    segment, depth + 1, ctx, item, results, current_prefix, on_item,
                )
                continue

            if on_item is not None:
                on_item()
                continue

            is_value_only = bool(segment.mappings) and all(
                m.target == "_" for m in segment.mappings
            )
            if is_value_only:
                val = DynValue.of_null()
                for mapping in segment.mappings:
                    val = self._process_mapping(
                        mapping, ctx, item, val, current_prefix, is_loop=True,
                    )
                results.append(val)
            else:
                row_output = DynValue.of_object({})
                for mapping in segment.mappings:
                    if mapping.target == "_":
                        self._evaluate_expression(mapping.expression, ctx, item, row_output)
                    else:
                        row_output = self._process_mapping(
                            mapping, ctx, item, row_output, current_prefix, is_loop=False,
                        )
                results.append(row_output)

        ctx.loop_vars = saved_vars
        ctx.loop_depth -= 1

    def _process_literal_segment(
        self,
        segment: TransformSegment,
        ctx: _ExecContext,
        output: DynValue,
        clean_name: str,
        is_root: bool,
    ) -> DynValue:
        """Render a :literal segment to interpolated text lines.

        One leading and one trailing delimiter newline are stripped; each remaining
        source line becomes an output line. Under a :loop the block renders per item.
        """
        template = _normalize_literal_body(segment.literal_body or "")
        lines: List[str] = []

        def render() -> None:
            current = ctx.loop_vars.get("_item", ctx.source)
            rendered = self._render_literal(template, ctx, current, segment.name)
            lines.extend(rendered.split("\n"))

        if segment.loops and segment.is_array:
            if ctx.loop_depth >= MAX_LOOP_NESTING:
                ctx.errors.append(TransformError(
                    message="Maximum loop nesting exceeded",
                    path=clean_name,
                ))
                return output
            old_loop_vars = dict(ctx.loop_vars)
            old_depth = ctx.loop_depth
            try:
                self._iterate_loops(segment, 0, ctx, ctx.source, [], clean_name, render)
            except CodedTransformError as e:
                ctx.loop_vars = old_loop_vars
                ctx.loop_depth = old_depth
                if ctx.on_error == "warn":
                    err = e.transform_error
                    ctx.warnings.append(TransformWarning(
                        message=err.message, path=err.path, code=err.code,
                    ))
                elif ctx.on_error != "skip":
                    ctx.errors.append(e.transform_error)
                return output
            ctx.loop_vars = old_loop_vars
            ctx.loop_depth = old_depth
        else:
            render()

        literal_val = DynValue.of_object({"__literalLines": DynValue.of_array(
            [DynValue.of_string(line) for line in lines]
        )})
        if not is_root:
            _set_path(output, clean_name, literal_val)
        else:
            output = literal_val
        return output

    def _render_literal(
        self,
        template: str,
        ctx: _ExecContext,
        current: DynValue,
        segment_path: str,
    ) -> str:
        """Interpolate ${…} markers in a literal block body.

        Escapes: `\\${`→`${`, `\\$`→`$`, `\\\\`→`\\`. A `${…}` whose body contains
        another `${` is rejected as a nested interpolation (T014).
        """
        out: List[str] = []
        i = 0
        n = len(template)
        empty = DynValue.of_object({})

        while i < n:
            ch = template[i]
            if ch == "\\":
                nxt = template[i + 1] if i + 1 < n else ""
                if nxt == "$" and i + 2 < n and template[i + 2] == "{":
                    out.append("${")
                    i += 3
                    continue
                if nxt == "\\":
                    out.append("\\")
                    i += 2
                    continue
                if nxt == "$":
                    out.append("$")
                    i += 2
                    continue
                out.append("\\")
                i += 1
                continue

            if ch == "$" and i + 1 < n and template[i + 1] == "{":
                close = template.find("}", i + 2)
                if close == -1:
                    out.append(template[i:])
                    break
                expr = template[i + 2:close]
                if "${" in expr:
                    ctx.errors.append(TransformError(
                        message=f"Nested interpolation is not allowed: {expr}",
                        path=segment_path,
                        code="T014",
                    ))
                    return ""
                out.append(self._eval_literal_expr(expr.strip(), ctx, current, empty))
                i = close + 1
                continue

            out.append(ch)
            i += 1

        return "".join(out)

    def _eval_literal_expr(
        self, expr: str, ctx: _ExecContext, current: DynValue, empty: DynValue
    ) -> str:
        """Evaluate one literal-block ${…} expression (path or verb) to a string."""
        if expr.startswith("%"):
            call = _parse_inline_verb(expr)
            if call is not None:
                value = self._execute_verb_call(call, ctx, current, empty)
                return _dyn_to_interp_string(value)
            return "${" + expr + "}"
        if expr.startswith("@"):
            value = self._evaluate_copy(CopyExpression(path=expr[1:]), ctx, current, empty)
            return _dyn_to_interp_string(value)
        return "${" + expr + "}"

    def _process_mapping(
        self,
        mapping: FieldMapping,
        ctx: _ExecContext,
        current_source: DynValue,
        output: DynValue,
        path_prefix: str,
        is_loop: bool = False,
    ) -> DynValue:
        try:
            # Field :if / :unless conditions gate whether the field is emitted.
            cond_source = current_source if (is_loop and not current_source.is_null()) else ctx.source
            for d in mapping.directives:
                if d.name == "if" and d.value is not None:
                    if not _evaluate_condition(d.value, cond_source, ctx):
                        return output
                elif d.name == "unless" and d.value is not None:
                    if _evaluate_condition(d.value, cond_source, ctx):
                        return output

            # T007: warn on modifiers that are not valid for the target format.
            for d in mapping.directives:
                if not _is_modifier_compatible(d.name, ctx.target_format):
                    ctx.warnings.append(
                        invalid_modifier_warning(d.name, ctx.target_format, mapping.target))

            # T010: fixed-width field whose pos + len exceeds the configured lineWidth.
            if ctx.target_format in ("fixed-width", "fixed_width", "fwf") and ctx.line_width:
                pos = _directive_int(mapping.directives, "pos")
                length = _directive_int(mapping.directives, "len")
                if pos is not None and length is not None and pos + length > ctx.line_width:
                    ctx.warnings.append(
                        position_overflow_warning(pos, length, ctx.line_width, mapping.target))

            # For verb expressions with extraction directives (pos/len/field),
            # pre-extract from the verb's reference argument before calling the verb
            expr = mapping.expression
            extraction_directives = _get_extraction_directives(mapping.directives)

            if (extraction_directives
                    and isinstance(expr, TransformExpression)
                    and expr.call.args):
                # Apply extraction directives to the first reference argument
                value = self._evaluate_verb_with_extracted_arg(
                    expr.call, extraction_directives, ctx, current_source, output
                )
                # Apply remaining non-extraction directives
                remaining = [d for d in mapping.directives
                             if d.name not in ("pos", "len", "field")]
                value = _apply_mapping_directives(value, remaining, ctx.source_format)
            else:
                value = self._evaluate_expression(expr, ctx, current_source, output)
                # Apply directives (type coercion etc.)
                value = _apply_mapping_directives(value, mapping.directives, ctx.source_format)

            # Validation modifiers: :validate / :enum / :range (honors onValidation).
            if not _validate_field_value(value, mapping, ctx):
                return output

            # Missing source path: a :required field always fails (T005 when the
            # path is absent, SOURCE_MISSING when present-but-null); an ordinary
            # field honors the onMissing policy (fail -> T005, warn -> warning,
            # skip/default -> keep null). A path that is merely null is not absent.
            is_required = mapping.modifiers is not None and mapping.modifiers.required
            if value.is_null():
                raw_path = (mapping.expression.path
                            if isinstance(mapping.expression, CopyExpression)
                            else mapping.target)
                rep_path = raw_path[1:] if raw_path.startswith(".") else raw_path
                if self._is_copy_source_absent(mapping, ctx, current_source, is_loop):
                    if is_required:
                        ctx.errors.append(
                            source_path_not_found_error(rep_path, mapping.target))
                        return output
                    policy = ctx.on_missing
                    if policy == "fail":
                        ctx.errors.append(
                            source_path_not_found_error(rep_path, mapping.target))
                        return output
                    if policy == "warn":
                        ctx.warnings.append(
                            source_path_not_found_warning(rep_path, mapping.target))
                elif is_required:
                    # Present but explicitly null.
                    ctx.errors.append(source_missing_error(mapping.target))
                    return output

            # :raw emits inline JSON structurally instead of an escaped string.
            if any(d.name == "raw" for d in mapping.directives):
                value = _parse_raw_json_value(value)

            # :array wraps the value in a single-element array.
            if any(d.name == "array" for d in mapping.directives):
                value = DynValue.of_array([value])

            # Confidential enforcement at mapping level
            if (mapping.modifiers is not None
                    and mapping.modifiers.confidential
                    and ctx.enforce_confidential is not None):
                value = _apply_confidential_to_value(value, ctx.enforce_confidential)

            if mapping.target == "_":
                if is_loop:
                    # Identity mapping in loop: the value IS the row itself
                    return value
                # Non-loop: discard target, don't add to output
            else:
                # Normal mapping: set the value on the output object
                _set_path(output, mapping.target, value)

                # Record modifiers
                if mapping.modifiers is not None and mapping.modifiers.has_any:
                    full_key = (
                        mapping.target if not path_prefix
                        else f"{path_prefix}.{mapping.target}"
                    )
                    ctx.field_modifiers[full_key] = mapping.modifiers

        except CodedTransformError as e:
            # Coded errors carry a stable T-code; preserve it under fail/warn.
            err = e.transform_error
            if ctx.on_error == "warn":
                ctx.warnings.append(TransformWarning(
                    message=err.message, path=mapping.target, code=err.code,
                ))
            elif ctx.on_error == "skip":
                pass
            else:
                ctx.errors.append(TransformError(
                    message=err.message, path=mapping.target, code=err.code,
                ))
        except Exception as e:
            message = str(e)
            if ctx.on_error == "warn":
                ctx.warnings.append(TransformWarning(message=message, path=mapping.target))
            elif ctx.on_error == "skip":
                pass
            else:
                ctx.errors.append(TransformError(message=message, path=mapping.target))

        return output

    def _evaluate_expression(
        self,
        expr: Optional[FieldExpression],
        ctx: _ExecContext,
        current_source: DynValue,
        current_output: DynValue,
    ) -> DynValue:
        if expr is None:
            return DynValue.of_null()

        if isinstance(expr, CopyExpression):
            return self._evaluate_copy(expr, ctx, current_source, current_output)

        if isinstance(expr, LiteralExpression):
            value = expr.value
            if isinstance(value, OdinString) and "${" in value.value:
                return self._interpolate_string(
                    value.value, ctx, current_source, current_output,
                )
            return _odin_value_to_dyn(value)

        if isinstance(expr, TransformExpression):
            return self._execute_verb_call(expr.call, ctx, current_source, current_output)

        if isinstance(expr, ObjectExpression):
            obj: Dict[str, DynValue] = {}
            for field_mapping in expr.fields:
                val = self._evaluate_expression(
                    field_mapping.expression, ctx, current_source, current_output,
                )
                obj[field_mapping.target] = val if val is not None else DynValue.of_null()
            return DynValue.of_object(obj)

        return DynValue.of_null()

    def _interpolate_string(
        self,
        template: str,
        ctx: _ExecContext,
        current_source: DynValue,
        current_output: DynValue,
    ) -> DynValue:
        """Interpolate ${...} expressions within a string template.

        Supports ${@path}, ${@.path}, ${%verb args} and \\${...} escapes.
        """
        count = 0
        max_interp = MAX_INTERPOLATIONS

        def replace(match: "_re.Match[str]") -> str:
            nonlocal count
            count += 1
            if count > max_interp:
                return match.group(0)
            # Escaped \${...} → literal ${...}
            if match.group(0).startswith("\\"):
                return "${" + match.group(1) + "}"
            expr = match.group(1).strip()
            if expr.startswith("%"):
                call = _parse_inline_verb(expr)
                if call is not None:
                    value = self._execute_verb_call(
                        call, ctx, current_source, current_output,
                    )
                    return _dyn_to_interp_string(value)
                return match.group(0)
            if expr.startswith("@"):
                copy = CopyExpression(path=expr[1:])
                value = self._evaluate_copy(
                    copy, ctx, current_source, current_output,
                )
                return _dyn_to_interp_string(value)
            return match.group(0)

        return DynValue.of_string(_INTERP_RE.sub(replace, template))

    def _is_copy_source_absent(
        self,
        mapping: FieldMapping,
        ctx: _ExecContext,
        current_source: DynValue,
        is_loop: bool,
    ) -> bool:
        """Whether a mapping copies a source path that is absent (not present-null).

        Only plain copy expressions over ordinary source paths qualify; verbs,
        literals, objects, special paths, and counters are never missing-source.
        """
        expr = mapping.expression
        if not isinstance(expr, CopyExpression):
            return False
        # A :default directive supplies its own fallback; not a missing source.
        if any(d.name == "default" for d in mapping.directives):
            return False
        path = expr.path
        if path in ("", "_item", "_index", "_length"):
            return False
        clean = path.lstrip("@")
        if clean in ("", "_item", "_index", "_length"):
            return False
        if clean.startswith("$"):
            return False
        if clean in ctx.loop_vars:
            return False

        # Relative path resolves against the current loop item (or source).
        if path.startswith("."):
            base = current_source if (is_loop and not current_source.is_null()) else ctx.source
            return _sub_path_absent(base, path[1:])

        first_part = clean.split(".")[0]
        if first_part in ctx.loop_vars:
            aliased = ctx.loop_vars[first_part]
            rest = clean[len(first_part) + 1:] if "." in clean else ""
            return _sub_path_absent(aliased, rest)

        return _sub_path_absent(ctx.source, clean)

    def _evaluate_copy(
        self,
        expr: CopyExpression,
        ctx: _ExecContext,
        current_source: DynValue,
        current_output: DynValue,
    ) -> DynValue:
        path = expr.path

        # Check loop vars
        if path in ctx.loop_vars:
            return ctx.loop_vars[path]

        clean_path = path.lstrip("@")

        # Loop variable references
        if clean_path == "_item":
            return ctx.loop_vars.get("_item", DynValue.of_null())
        if clean_path.startswith("_item."):
            sub = clean_path[len("_item."):]
            item = ctx.loop_vars.get("_item")
            return _resolve_sub_path(item, sub) if item else DynValue.of_null()
        if clean_path == "_index":
            return ctx.loop_vars.get("_index", DynValue.of_null())
        if clean_path == "_length":
            return ctx.loop_vars.get("_length", DynValue.of_null())

        # Loop alias reference (e.g. `@veh.vin` where `veh` is a :loop :as alias).
        if clean_path:
            first_part = clean_path.split(".")[0]
            if first_part in ctx.loop_vars:
                aliased = ctx.loop_vars[first_part]
                rest = clean_path[len(first_part) + 1:] if "." in clean_path else ""
                return _resolve_sub_path(aliased, rest) if rest else aliased

        # Empty path (@) — return current source (loop item in loops)
        if not clean_path:
            return current_source

        # Relative path (.field) - resolve against current source
        if path.startswith("."):
            return _resolve_sub_path(current_source, path[1:])

        # Constant references
        if clean_path.startswith("$const."):
            const_name = clean_path[len("$const."):]
            return ctx.constants.get(const_name, DynValue.of_null())

        # Accumulator references
        if clean_path.startswith("$accumulator."):
            acc_name = clean_path[len("$accumulator."):]
            return ctx.accumulators.get(acc_name, DynValue.of_null())

        # Absolute reference - resolve from root source first, then global output
        result = _resolve_path(ctx.source, clean_path, ctx)
        if result.is_null() and ctx.global_output is not None and ctx.global_output.is_object():
            # Also check global output (for references to earlier segment outputs)
            output_result = _resolve_sub_path(ctx.global_output, clean_path)
            if not output_result.is_null():
                return output_result
        # Also check current output (for references to earlier mappings in same segment)
        if result.is_null() and current_output is not None and current_output.is_object():
            output_result = _resolve_sub_path(current_output, clean_path)
            if not output_result.is_null():
                return output_result
        return result

    def _execute_verb_call(
        self,
        call: VerbCall,
        ctx: _ExecContext,
        current_source: DynValue,
        current_output: DynValue,
    ) -> DynValue:
        if ctx.verb_registry is None:
            return DynValue.of_null()

        fn = ctx.verb_registry.get(call.verb)
        if fn is None and call.is_custom:
            # Default custom verb handler: echo first argument
            args = [self._evaluate_verb_arg(a, ctx, current_source, current_output) for a in call.args]
            return args[0] if args else DynValue.of_null()
        if fn is None:
            # T001: unknown built-in verb. Raised so the mapping handler preserves
            # the stable code under the onError policy.
            raise CodedTransformError(unknown_verb_error(call.verb))

        # Conditional verbs need lazy evaluation of branches
        if call.verb in _LAZY_EVAL_VERBS:
            return self._execute_lazy_verb(call, fn, ctx, current_source, current_output)

        # Evaluate arguments eagerly
        args: List[DynValue] = []
        for arg in call.args:
            args.append(self._evaluate_verb_arg(arg, ctx, current_source, current_output))

        # Strict type validation (T002) when enabled.
        if ctx.strict_types and not call.is_custom:
            type_error = _validate_verb_arg_types(call.verb, args)
            if type_error is not None:
                raise CodedTransformError(type_error)

        # Build verb context
        verb_ctx = self._make_verb_context(ctx)

        try:
            return fn(args, verb_ctx)
        except Exception as e:
            ctx.errors.append(TransformError(
                message=f"Verb '{call.verb}' error: {e}",
                path="",
            ))
            return DynValue.of_null()

    def _evaluate_verb_arg(
        self,
        arg: VerbArg,
        ctx: _ExecContext,
        current_source: DynValue,
        current_output: DynValue,
    ) -> DynValue:
        """Evaluate a single verb argument."""
        if isinstance(arg, ReferenceArg):
            copy_expr = CopyExpression(path=arg.path)
            return self._evaluate_copy(copy_expr, ctx, current_source, current_output)
        elif isinstance(arg, LiteralArg):
            return _odin_value_to_dyn(arg.value)
        elif isinstance(arg, VerbCallArg):
            return self._execute_verb_call(arg.call, ctx, current_source, current_output)
        return DynValue.of_null()

    def _evaluate_verb_with_extracted_arg(
        self,
        call: VerbCall,
        extraction_directives: List[Directive],
        ctx: _ExecContext,
        current_source: DynValue,
        current_output: DynValue,
    ) -> DynValue:
        """Evaluate a verb call, applying extraction directives to the first reference arg."""
        args: List[DynValue] = []
        applied_extraction = False
        for arg in call.args:
            if not applied_extraction and isinstance(arg, VerbCallArg):
                # Recursively apply extraction to nested verb call
                val = self._evaluate_verb_with_extracted_arg(
                    arg.call, extraction_directives, ctx, current_source, current_output
                )
                applied_extraction = True
            else:
                val = self._evaluate_verb_arg(arg, ctx, current_source, current_output)
                # Apply extraction directives to the first reference argument
                if not applied_extraction and isinstance(arg, ReferenceArg):
                    val = _apply_mapping_directives(val, extraction_directives, ctx.source_format)
                    applied_extraction = True
            args.append(val)

        if ctx.verb_registry is None:
            return DynValue.of_null()

        fn = ctx.verb_registry.get(call.verb)
        if fn is None:
            return DynValue.of_null()

        verb_ctx = self._make_verb_context(ctx)
        try:
            return fn(args, verb_ctx)
        except Exception as e:
            ctx.errors.append(TransformError(
                message=f"Verb '{call.verb}' error: {e}",
                path="",
            ))
            return DynValue.of_null()

    def _make_verb_context(self, ctx: _ExecContext) -> VerbContext:
        """Build verb context from execution context."""
        verb_ctx = VerbContext()
        verb_ctx.source = ctx.source
        verb_ctx.loop_vars = ctx.loop_vars
        verb_ctx.accumulators = ctx.accumulators
        verb_ctx.tables = ctx.tables
        verb_ctx.constants = ctx.constants
        verb_ctx.global_output = ctx.global_output
        verb_ctx.on_missing = ctx.on_missing
        # Share the execution context's error/warning lists so verb-reported
        # misses surface in the result.
        verb_ctx.errors = ctx.errors
        verb_ctx.warnings = ctx.warnings
        return verb_ctx

    def _execute_lazy_verb(
        self,
        call: VerbCall,
        fn,
        ctx: _ExecContext,
        current_source: DynValue,
        current_output: DynValue,
    ) -> DynValue:
        """Execute a conditional verb with lazy evaluation of branches.

        For ifElse/ternary: evaluate condition, then only evaluate the selected branch.
        For switch: evaluate the switch value, then only evaluate the matching case.
        """
        verb_ctx = self._make_verb_context(ctx)
        verb_name = call.verb

        try:
            if verb_name in ("ifElse", "ternary") and len(call.args) >= 3:
                # Args: condition, trueValue, falseValue
                cond = self._evaluate_verb_arg(call.args[0], ctx, current_source, current_output)
                if _is_truthy(cond):
                    true_val = self._evaluate_verb_arg(call.args[1], ctx, current_source, current_output)
                    return true_val
                else:
                    false_val = self._evaluate_verb_arg(call.args[2], ctx, current_source, current_output)
                    return false_val

            elif verb_name == "switch" and len(call.args) >= 3:
                # Args: value, case1, result1, case2, result2, ..., [default]
                switch_val = self._evaluate_verb_arg(call.args[0], ctx, current_source, current_output)
                switch_str = switch_val.as_string()
                i = 1
                while i + 1 < len(call.args):
                    case_val = self._evaluate_verb_arg(call.args[i], ctx, current_source, current_output)
                    if case_val.as_string() == switch_str:
                        return self._evaluate_verb_arg(call.args[i + 1], ctx, current_source, current_output)
                    i += 2
                # Default value (odd number of remaining args)
                if i < len(call.args):
                    return self._evaluate_verb_arg(call.args[i], ctx, current_source, current_output)
                return DynValue.of_null()

            else:
                # Fallback to eager evaluation
                args = [self._evaluate_verb_arg(a, ctx, current_source, current_output) for a in call.args]
                return fn(args, verb_ctx)

        except Exception as e:
            ctx.errors.append(TransformError(
                message=f"Verb '{verb_name}' error: {e}",
                path="",
            ))
            return DynValue.of_null()

    def _format_output(self, output: DynValue, transform: OdinTransform, field_modifiers: Optional[Dict[str, 'OdinModifiers']] = None, errors: Optional[List[TransformError]] = None) -> Optional[str]:
        """Format the output DynValue using the target format.

        The effective format is the declared target format, or the right-hand
        side of the direction header when no target format is declared. An
        unrecognized format raises T006 rather than silently falling back.
        """
        target_format = transform.target.format
        if not target_format:
            # Derive from the direction header (e.g. "json->odin" -> "odin").
            direction = transform.metadata.direction or ""
            if "->" in direction:
                target_format = direction.split("->")[1].strip()

        opts = transform.target.options

        known_formats = {
            "json", "odin", "csv", "xml",
            "fixed-width", "fixed_width", "fwf",
            "flat", "properties", "yaml",
        }
        if target_format and target_format not in known_formats:
            if errors is not None:
                errors.append(invalid_output_format_error(target_format))
            return None
        if not target_format:
            target_format = "json"

        try:
            if target_format == "json":
                from odin.transform.formatters.json_formatter import format_json
                indent_str = opts.get("indent", "")
                indent_val = int(indent_str) if indent_str != "" else 2
                omit_nulls = opts.get("nulls", "") == "omit"
                omit_empty_arrays = opts.get("emptyArrays", "") == "omit"
                return format_json(output, indent=indent_val, omit_nulls=omit_nulls, omit_empty_arrays=omit_empty_arrays)
            if target_format == "odin":
                from odin.transform.formatters.odin_formatter import format_odin
                header = opts.get("header", "") in ("true", "?true")
                return format_odin(output, header=header, modifiers=field_modifiers)
            if target_format == "csv":
                from odin.transform.formatters.csv_formatter import format_csv
                delimiter = opts.get("delimiter", ",")
                header_opt = opts.get("header", "true")
                include_header = header_opt not in ("false", "?false")
                return format_csv(output, delimiter=delimiter, include_header=include_header)
            if target_format == "xml":
                from odin.transform.formatters.xml_formatter import format_xml
                decl_opt = opts.get("declaration", "true")
                declaration = decl_opt not in ("false", "?false")
                indent_str = opts.get("indent", "")
                indent_spaces = " " * int(indent_str) if indent_str != "" else "  "
                return format_xml(output, declaration=declaration, indent=indent_spaces, transform=transform)
            if target_format in ("fixed-width", "fixed_width", "fwf"):
                from odin.transform.formatters.fixed_width_formatter import format_fixed_width
                return format_fixed_width(output, transform=transform)
            if target_format in ("flat", "properties", "yaml"):
                from odin.transform.formatters.flat_formatter import format_flat
                style = transform.target.options.get("style", "kvp")
                if target_format == "yaml":
                    style = "yaml"
                return format_flat(output, style=style)
            return None
        except Exception:
            return None


# ── Interpolation Helpers ───────────────────────────────────────────────────────


def _parse_inline_verb(expr: str) -> Optional[VerbCall]:
    """Parse a `%verb args` expression into a VerbCall."""
    from odin.transform.transform_parser import _parse_verb_from_string
    return _parse_verb_from_string(expr)


def _dyn_to_interp_string(value: DynValue) -> str:
    """Render a DynValue as its interpolated string form."""
    if value.is_null():
        return ""
    if value.is_string():
        return value.as_string()
    if value.is_array() or value.is_object():
        return json.dumps(_dyn_to_plain(value))
    from odin.transform.verbs.helpers import coerce_str
    return coerce_str(value)


def _dyn_to_plain(value: DynValue) -> Any:
    """Convert a DynValue to plain Python values for JSON rendering."""
    if value.is_null():
        return None
    if value.is_object():
        return {k: _dyn_to_plain(v) for k, v in value.as_object().items()}
    if value.is_array():
        return [_dyn_to_plain(v) for v in value.as_array()]
    if value.is_string():
        return value.as_string()
    if value.is_bool():
        return value.as_bool()
    if value.is_integer():
        return value.as_int()
    if value.is_number():
        return value.as_float()
    from odin.transform.verbs.helpers import coerce_str
    return coerce_str(value)


# ── Path Resolution ────────────────────────────────────────────────────────────


def _normalize_literal_body(body: str) -> str:
    """Strip one leading and one trailing delimiter newline from a literal body."""
    s = body
    if s.startswith("\r\n"):
        s = s[2:]
    elif s.startswith("\n"):
        s = s[1:]
    if s.endswith("\r\n"):
        s = s[:-2]
    elif s.endswith("\n"):
        s = s[:-1]
    return s


def _is_present(value: Optional[DynValue]) -> bool:
    """Whether a resolved value exists (object key present / array index in range).

    A present value may still be a null; absence is the missing-source condition.
    """
    return value is not None


def _sub_path_absent(source: Optional[DynValue], path: str) -> bool:
    """Whether a dotted/bracketed path is absent (vs present with a null value)."""
    if source is None:
        return True
    if not path:
        return False
    current = source
    for seg in _parse_path_segments(path):
        if current is None:
            return True
        if seg.startswith("[") and seg.endswith("]"):
            try:
                idx = int(seg[1:-1])
            except ValueError:
                return True
            if not current.is_array():
                return True
            items = current.as_array()
            if not (0 <= idx < len(items)):
                return True
            current = items[idx]
        else:
            if not current.is_object():
                return True
            child = current.get(seg)
            if child is None:
                return True
            current = child
    return False


def _resolve_path(source: DynValue, path: str, ctx: _ExecContext) -> DynValue:
    """Resolve a path against the source data."""
    if not path:
        return source

    # Handle special paths
    if path.startswith("$const."):
        name = path[len("$const."):]
        return ctx.constants.get(name, DynValue.of_null())

    if path.startswith("$accumulator."):
        name = path[len("$accumulator."):]
        return ctx.accumulators.get(name, DynValue.of_null())

    return _resolve_sub_path(source, path)


def _resolve_sub_path(source: Optional[DynValue], path: str) -> DynValue:
    """Resolve a dotted/bracketed path against a DynValue."""
    if source is None:
        return DynValue.of_null()
    if not path:
        return source

    current = source
    segments = _parse_path_segments(path)

    for seg in segments:
        if current is None or current.is_null():
            return DynValue.of_null()

        if seg.startswith("[") and seg.endswith("]"):
            # Array index
            try:
                idx = int(seg[1:-1])
            except ValueError:
                return DynValue.of_null()
            if current.is_array():
                items = current.as_array()
                if 0 <= idx < len(items):
                    current = items[idx]
                else:
                    return DynValue.of_null()
            else:
                return DynValue.of_null()
        else:
            # Object field
            if current.is_object():
                child = current.get(seg)
                if child is None:
                    return DynValue.of_null()
                current = child
            else:
                return DynValue.of_null()

    return current


def _parse_path_segments(path: str) -> List[str]:
    """Parse a path string into segments.

    Examples:
        "name" → ["name"]
        "address.city" → ["address", "city"]
        "items[0].name" → ["items", "[0]", "name"]
        "[0]" → ["[0]"]
    """
    segments: List[str] = []
    i = 0
    while i < len(path):
        if path[i] == ".":
            i += 1
            continue
        if path[i] == "[":
            end = path.find("]", i)
            if end < 0:
                end = len(path)
            segments.append(path[i:end + 1])
            i = end + 1
        else:
            # Find end of segment (. or [)
            start = i
            while i < len(path) and path[i] != "." and path[i] != "[":
                i += 1
            segments.append(path[start:i])
    return segments


# ── DynValue Helpers ───────────────────────────────────────────────────────────


def _set_path(target: DynValue, key: str, value: DynValue) -> None:
    """Set a value at a key in a DynValue object."""
    if not target.is_object():
        return
    obj = target.as_object()
    obj[key] = value


def _get_or_create_object(parent: DynValue, key: str) -> DynValue:
    """Get or create a nested object."""
    if parent.is_object():
        existing = parent.get(key)
        if existing is not None and existing.is_object():
            return existing
    return DynValue.of_object({})


def _python_to_dyn(value: Any) -> DynValue:
    """Convert a Python object to DynValue."""
    if value is None:
        return DynValue.of_null()
    if isinstance(value, DynValue):
        return value
    if isinstance(value, bool):
        return DynValue.of_bool(value)
    if isinstance(value, int):
        return DynValue.of_integer(value)
    if isinstance(value, float):
        return DynValue.of_float(value)
    if isinstance(value, str):
        return DynValue.of_string(value)
    if isinstance(value, list):
        return DynValue.of_array([_python_to_dyn(item) for item in value])
    if isinstance(value, dict):
        return DynValue.of_object({k: _python_to_dyn(v) for k, v in value.items()})
    # Handle OdinDocument
    from odin.types.document import OdinDocument
    if isinstance(value, OdinDocument):
        return _odin_doc_to_dyn(value)
    # Handle OdinValue types
    result = _try_odin_value_to_dyn(value)
    if result is not None:
        return result
    return DynValue.of_string(str(value))


def _odin_doc_to_dyn(doc) -> DynValue:
    """Convert an OdinDocument to a DynValue tree."""
    result = {}
    for path, value in doc.assignments.items():
        if path.startswith("$"):
            continue
        dyn_val = _odin_value_to_dyn(value)
        _set_nested_dyn(result, path, dyn_val)
    return _dict_to_dyn(result)


def _dict_to_dyn(obj) -> DynValue:
    """Recursively convert a nested dict (with DynValue leaves) to DynValue."""
    if isinstance(obj, DynValue):
        return obj
    if isinstance(obj, dict):
        return DynValue.of_object({k: _dict_to_dyn(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return DynValue.of_array([_dict_to_dyn(v) for v in obj])
    return DynValue.of_string(str(obj))


def _set_nested_dyn(obj, path: str, value):
    """Set a value at a dotted/bracketed path in a nested dict/list structure."""
    segments = []
    i = 0
    while i < len(path):
        if path[i] == ".":
            i += 1
            continue
        if path[i] == "[":
            end = path.find("]", i)
            if end < 0:
                end = len(path)
            segments.append(path[i:end + 1])
            i = end + 1
        else:
            start = i
            while i < len(path) and path[i] != "." and path[i] != "[":
                i += 1
            segments.append(path[start:i])

    current = obj
    for idx, seg in enumerate(segments):
        is_last = idx == len(segments) - 1
        if seg.startswith("[") and seg.endswith("]"):
            try:
                arr_idx = int(seg[1:-1])
            except ValueError:
                return
            if not isinstance(current, list):
                return
            while len(current) <= arr_idx:
                current.append({})
            if is_last:
                current[arr_idx] = value
            else:
                if not isinstance(current[arr_idx], (dict, list)):
                    current[arr_idx] = {}
                current = current[arr_idx]
        elif is_last:
            if isinstance(current, dict):
                current[seg] = value
        else:
            if isinstance(current, dict):
                next_seg = segments[idx + 1] if idx + 1 < len(segments) else None
                if next_seg and next_seg.startswith("[") and next_seg.endswith("]"):
                    if seg not in current or not isinstance(current[seg], list):
                        current[seg] = []
                    current = current[seg]
                else:
                    if seg not in current or not isinstance(current[seg], dict):
                        current[seg] = {}
                    current = current[seg]


def _try_odin_value_to_dyn(value: Any) -> Optional[DynValue]:
    """Try converting an OdinValue to DynValue. Returns None if not an OdinValue."""
    if isinstance(value, OdinNull):
        return DynValue.of_null()
    if isinstance(value, OdinBoolean):
        return DynValue.of_bool(value.value)
    if isinstance(value, OdinInteger):
        return DynValue.of_integer(value.value)
    if isinstance(value, OdinNumber):
        return DynValue.of_float(value.value)
    if isinstance(value, OdinCurrency):
        return DynValue.of_currency(value.value, code=getattr(value, 'currency_code', None), dp=getattr(value, 'decimal_places', 2))
    if isinstance(value, OdinPercent):
        return DynValue.of_float(value.value)
    if isinstance(value, OdinString):
        return DynValue.of_string(value.value)
    if isinstance(value, OdinReference):
        return DynValue.of_string(value.path)
    if isinstance(value, OdinBinary):
        return DynValue.of_binary(value.data)
    return None


def _odin_value_to_dyn(value: Any) -> DynValue:
    """Convert an OdinValue to DynValue."""
    if value is None:
        return DynValue.of_null()
    if isinstance(value, DynValue):
        return value
    if isinstance(value, OdinNull):
        return DynValue.of_null()
    if isinstance(value, OdinBoolean):
        return DynValue.of_bool(value.value)
    if isinstance(value, OdinInteger):
        return DynValue.of_integer(value.value)
    if isinstance(value, OdinNumber):
        return DynValue.of_float(value.value)
    if isinstance(value, OdinCurrency):
        return DynValue.of_currency(value.value, code=getattr(value, 'currency_code', None), dp=getattr(value, 'decimal_places', 2))
    if isinstance(value, OdinPercent):
        return DynValue.of_float(value.value)
    if isinstance(value, OdinString):
        return DynValue.of_string(value.value)
    if isinstance(value, OdinReference):
        return DynValue.of_string(value.path)
    if isinstance(value, OdinDate):
        return DynValue.of_string(value.value.isoformat() if hasattr(value.value, 'isoformat') else str(value.value))
    if isinstance(value, OdinTimestamp):
        return DynValue.of_string(value.value.isoformat() if hasattr(value.value, 'isoformat') else str(value.value))
    if isinstance(value, OdinTime):
        return DynValue.of_string(value.value)
    if isinstance(value, OdinDuration):
        return DynValue.of_string(value.value)
    if isinstance(value, OdinBinary):
        return DynValue.of_binary(value.data)
    # Fallback for lists (from constant arrays)
    if isinstance(value, list):
        return DynValue.of_array([_odin_value_to_dyn(v) for v in value])
    return DynValue.of_string(str(value))


def _is_truthy(val: DynValue) -> bool:
    """Check if a DynValue is truthy."""
    if val.is_null():
        return False
    if val.is_bool():
        return val.as_bool()
    if val.is_integer():
        return val.as_int() != 0
    if val.is_string():
        s = val.as_string()
        return s != "" and s.lower() != "false"
    if val.is_array():
        return len(val.as_array()) > 0
    if val.is_object():
        return len(val.as_object()) > 0
    return True


# ── Condition Evaluation ──────────────────────────────────────────────────────

# Comparison operators ordered so multi-char forms match before their prefixes
_CONDITION_OPS = ("==", "!=", "<>", "<=", ">=", "=", "<", ">")


def _parse_condition_value(part: str) -> DynValue:
    """Parse the right-hand literal of a condition into a DynValue."""
    if len(part) >= 2 and part[0] == part[-1] and part[0] in ("'", '"'):
        return DynValue.of_string(part[1:-1])
    lower = part.lower()
    if lower == "true":
        return DynValue.of_bool(True)
    if lower == "false":
        return DynValue.of_bool(False)
    if lower in ("null", "nil"):
        return DynValue.of_null()
    try:
        return DynValue.of_integer(int(part))
    except ValueError:
        pass
    try:
        return DynValue.of_float(float(part))
    except ValueError:
        pass
    return DynValue.of_string(part)


def _split_condition(expr: str) -> Optional[tuple]:
    """Split `path <op> value` into (path, op, value); None if no operator."""
    for op in _CONDITION_OPS:
        idx = expr.find(op)
        if idx > 0:
            return expr[:idx].strip(), op, expr[idx + len(op):].strip()
    return None


def _evaluate_condition(condition: str, source: DynValue, ctx: "_ExecContext") -> bool:
    """Evaluate an _if condition: truthy path check or `path <op> value` comparison."""
    expr = condition.strip()
    parsed = _split_condition(expr)
    if parsed is not None:
        path_part, op, value_part = parsed
        left = _resolve_path(source, _strip_path_prefix(path_part), ctx)
        right = _parse_condition_value(value_part)
        return _check_filter_condition(left, op, right)
    return _is_truthy(_resolve_path(source, _strip_path_prefix(expr), ctx))


def _strip_path_prefix(path: str) -> str:
    """Strip a leading @ and/or . from a condition path."""
    if path.startswith("@"):
        path = path[1:]
    if path.startswith("."):
        path = path[1:]
    return path


# ── Confidential Enforcement ──────────────────────────────────────────────────


def _apply_confidential_to_value(value: DynValue, mode: ConfidentialMode) -> DynValue:
    """Apply confidential enforcement to a single value."""
    if mode == ConfidentialMode.REDACT:
        return DynValue.of_null()
    if mode == ConfidentialMode.MASK:
        if value.is_string():
            length = len(value.as_string())
            return DynValue.of_string("*" * length)
        # Non-string → null
        return DynValue.of_null()
    return value


def _apply_confidential_enforcement(
    segments: List[TransformSegment],
    mode: ConfidentialMode,
    output: DynValue,
) -> None:
    """Apply confidential enforcement to all confidential fields in output.

    Second pass that walks the segment tree to find fields marked as confidential
    and applies redaction/masking. This catches fields that may not have been
    handled during inline mapping processing.
    """
    paths: List[str] = []
    _collect_confidential_paths(segments, "", paths)
    for path in paths:
        val = _resolve_dotted_path(output, path)
        if val is not None:
            replaced = _apply_confidential_to_value(val, mode)
            _set_by_dotted_path(output, path, replaced)


def _collect_confidential_paths(
    segments: List[TransformSegment], prefix: str, paths: List[str]
) -> None:
    """Recursively collect target paths for confidential fields."""
    for seg in segments:
        if not seg.name or seg.name in ("$", "_root"):
            seg_prefix = prefix
        elif not prefix:
            seg_prefix = seg.name
        else:
            seg_prefix = prefix + "." + seg.name

        for mapping in seg.mappings:
            if mapping.modifiers and mapping.modifiers.confidential:
                full_path = mapping.target if not seg_prefix else seg_prefix + "." + mapping.target
                paths.append(full_path)

        _collect_confidential_paths(seg.children, seg_prefix, paths)


def _resolve_dotted_path(output: DynValue, path: str) -> Optional[DynValue]:
    """Navigate a dotted path in a DynValue object tree."""
    parts = path.split(".")
    current = output
    for part in parts:
        if not current.is_object():
            return None
        child = current.get(part)
        if child is None:
            return None
        current = child
    return current


def _set_by_dotted_path(output: DynValue, path: str, value: DynValue) -> None:
    """Set a value at a dotted path in a DynValue object tree."""
    parts = path.split(".")
    current = output
    for part in parts[:-1]:
        if not current.is_object():
            return
        child = current.get(part)
        if child is None:
            return
        current = child
    if current.is_object():
        obj = current.as_object()
        obj[parts[-1]] = value


# ── Directive Application ─────────────────────────────────────────────────────


def _get_extraction_directives(directives: List[Directive]) -> List[Directive]:
    """Get extraction directives (pos, len, field) from a list of directives."""
    result = []
    for d in directives:
        if d.name in ("pos", "len", "field"):
            result.append(d)
    return result


def _dyn_numeric_of(value: DynValue) -> Optional[float]:
    """Return a numeric value for range checks, or None if not numeric."""
    if value.is_number():
        return value.as_float()
    if value.is_string():
        try:
            return float(value.as_string())
        except ValueError:
            return None
    return None


def _parse_raw_json_value(value: DynValue) -> DynValue:
    """Parse a string value as JSON for :raw, producing a structural DynValue."""
    if not value.is_string():
        return value
    import json as _json
    try:
        return _python_to_dyn(_json.loads(value.as_string()))
    except (ValueError, TypeError):
        return value


def _validate_field_value(
    value: DynValue, mapping: FieldMapping, ctx: _ExecContext
) -> bool:
    """Validate a value against :validate / :enum / :range directives.

    Returns False when the field should be dropped (onValidation = skip).
    """
    if value.is_null():
        return True

    failures: List[str] = []

    for d in mapping.directives:
        if d.name == "validate" and d.value is not None:
            pattern = d.value
            text = value.as_string()
            try:
                if _re.search(pattern, text) is None:
                    failures.append(f"value '{text}' does not match pattern '{pattern}'")
            except _re.error:
                failures.append(f"invalid validation pattern '{pattern}'")
        elif d.name == "enum" and d.value is not None:
            allowed = [v.strip().strip("\"'") for v in d.value.split(",")]
            text = value.as_string()
            if text not in allowed:
                failures.append(f"value '{text}' is not one of [{', '.join(allowed)}]")
        elif d.name == "range" and d.value is not None:
            parts = d.value.split("..")
            num = _dyn_numeric_of(value)
            if num is None:
                failures.append(
                    f"value '{value.as_string()}' is not numeric for range {d.value}"
                )
            else:
                lo = _try_float(parts[0]) if len(parts) > 0 else None
                hi = _try_float(parts[1]) if len(parts) > 1 else None
                if (lo is not None and num < lo) or (hi is not None and num > hi):
                    failures.append(f"value {num} is outside range {d.value}")

    if not failures:
        return True

    message = f"Validation failed for '{mapping.target}': {'; '.join(failures)}"
    policy = ctx.on_validation
    if policy == "warn":
        ctx.warnings.append(TransformWarning(message=message, path=mapping.target))
        return True
    if policy == "skip":
        return False
    ctx.errors.append(validation_error(message, mapping.target))
    return False


def _try_float(text: str) -> Optional[float]:
    try:
        return float(text.strip())
    except (ValueError, AttributeError):
        return None


def _apply_mapping_directives(
    value: DynValue, directives: List[Directive], source_format: str = "",
) -> DynValue:
    """Apply mapping-level directives to a value."""
    # Collect extraction directives
    pos_val = None
    len_val = None
    field_idx = None

    for d in directives:
        if d.name == "pos" and d.value is not None:
            try:
                pos_val = int(d.value)
            except ValueError:
                pass
        elif d.name == "len" and d.value is not None:
            try:
                len_val = int(d.value)
            except ValueError:
                pass
        elif d.name == "field" and d.value is not None:
            try:
                field_idx = int(d.value)
            except ValueError:
                pass

    # Apply extraction only for import (source is FWF/CSV/flat), not export
    is_import = source_format in ("fixed-width", "fwf", "fixed_width", "csv", "flat")
    if value.is_string() and (field_idx is not None or (is_import and pos_val is not None)):
        s = value.as_string()
        if field_idx is not None:
            fields = s.split(",")
            s = fields[field_idx].strip() if field_idx < len(fields) else ""
        if is_import and pos_val is not None:
            if len_val is not None:
                s = s[pos_val:pos_val + len_val]
            else:
                s = s[pos_val:]
        value = DynValue.of_string(s.strip())

    # Collect all directive info first
    type_name = None
    currency_code = None
    decimals = None
    default_val = None

    for d in directives:
        if d.name == "type" and d.value:
            type_name = d.value
        elif d.name == "currencyCode" and d.value:
            currency_code = d.value
        elif d.name == "decimals" and d.value:
            try:
                decimals = int(d.value)
            except ValueError:
                pass

    # Apply non-type directives first
    for d in directives:
        if d.name == "default" and d.value:
            if value.is_null():
                value = DynValue.of_string(d.value)
        elif d.name == "upper":
            if value.is_string():
                value = DynValue.of_string(value.as_string().upper())
        elif d.name == "lower":
            if value.is_string():
                value = DynValue.of_string(value.as_string().lower())
        elif d.name == "trim":
            if value.is_string():
                value = DynValue.of_string(value.as_string().strip())
        elif d.name == "maxLen" and d.value:
            try:
                max_len = int(d.value)
                if value.is_string():
                    s = value.as_string()
                    if len(s) > max_len:
                        value = DynValue.of_string(s[:max_len])
            except ValueError:
                pass

    # Apply type coercion (with context from currencyCode/decimals)
    effective_type = type_name
    # Also handle shorthand directives
    for d in directives:
        if d.name in ("date", "time", "timestamp", "duration", "integer",
                       "number", "currency", "percent", "boolean", "reference", "binary"):
            if effective_type is None:
                effective_type = d.name

    if effective_type:
        value = _coerce_type_with_context(
            value, effective_type,
            currency_code=currency_code,
            decimals=decimals,
        )

    return value


def _coerce_type_with_context(
    value: DynValue,
    type_name: str,
    currency_code: Optional[str] = None,
    decimals: Optional[int] = None,
) -> DynValue:
    """Coerce a DynValue to a specific type with additional context."""
    # Null values pass through unchanged (matches TypeScript reference)
    if value.is_null():
        return value
    if type_name == "currency":
        try:
            from decimal import Decimal
            raw_str = value.as_string()
            code = currency_code.upper() if currency_code else None
            # When source is a string (e.g. from CSV), preserve raw decimal representation
            if value.is_string() and raw_str:
                try:
                    float(raw_str)  # validate numeric
                    dv = DynValue(DynType.CURRENCY_RAW)
                    dv._string_value = raw_str
                    dv._currency_code = code
                    dp = decimals
                    if dp is None:
                        # Infer dp from raw string
                        if '.' in raw_str:
                            dp = len(raw_str.split('.')[-1])
                        else:
                            dp = 0
                    dv._decimal_places = dp
                    return dv
                except (ValueError, TypeError):
                    pass
            # Numeric source — use regular Currency
            try:
                num_val = Decimal(raw_str) if raw_str else Decimal(str(value.as_float()))
            except Exception:
                num_val = Decimal(str(value.as_float()))
            dp = decimals if decimals is not None else 2
            if decimals is not None and decimals > 6:
                # High precision → use CurrencyRaw to preserve exact decimal string
                fmt = f"{{:.{dp}f}}"
                raw = fmt.format(num_val)
                dv = DynValue(DynType.CURRENCY_RAW)
                dv._string_value = raw
                dv._currency_code = code
                dv._decimal_places = dp
                return dv
            dv = DynValue.of_currency(num_val, code=code, dp=dp)
            return dv
        except (ValueError, TypeError):
            return value
    if type_name == "number":
        # If value is a string, preserve the raw form as FloatRaw
        if value.is_string():
            raw_str = value.as_string()
            if raw_str:
                try:
                    float(raw_str)  # validate it's numeric
                    return DynValue.of_float_raw(raw_str)
                except (ValueError, TypeError):
                    pass
        return DynValue.of_float(value.as_float())
    if type_name == "reference":
        s = value.as_string()
        if s:
            return DynValue.of_reference(s)
        return value
    if type_name == "binary":
        s = value.as_string()
        if s:
            import base64
            try:
                data = base64.b64decode(s)
                return DynValue.of_binary(data)
            except Exception:
                # Not valid base64, store raw string
                dv = DynValue(DynType.BINARY)
                dv._string_value = s
                return dv
        return value
    # Fall back to the basic coercion for all other types
    return _coerce_type(value, type_name)


def _coerce_type(value: DynValue, type_name: str) -> DynValue:
    """Coerce a DynValue to a specific type.

    Null values are preserved (returned as-is) to match TypeScript behavior.
    Type coercion only applies to non-null values.
    """
    # Null values pass through unchanged (matches TypeScript reference)
    if value.is_null():
        return value
    if type_name == "string":
        return DynValue.of_string(value.as_string())
    if type_name == "number":
        return DynValue.of_float(value.as_float())
    if type_name == "integer":
        if value.is_string():
            try:
                return DynValue.of_integer(int(value.as_string()))
            except (ValueError, TypeError):
                return value
        if value.is_integer() or value.is_float():
            return DynValue.of_integer(value.as_int())
        return value
    if type_name == "boolean":
        if value.is_string():
            return DynValue.of_bool(value.as_string().lower() in ("true", "1"))
        return DynValue.of_bool(value.as_bool())
    if type_name == "date":
        s = value.as_string()
        if s:
            dv = DynValue(DynType.DATE)
            dv._string_value = s
            return dv
        return value
    if type_name == "time":
        s = value.as_string()
        return DynValue.of_time(s) if s else value
    if type_name == "timestamp":
        s = value.as_string()
        if s:
            normalized = _normalize_timestamp(s)
            dv = DynValue(DynType.TIMESTAMP)
            dv._string_value = normalized
            return dv
        return value
    if type_name == "duration":
        s = value.as_string()
        if s:
            return DynValue.of_duration(s)
        return value
    if type_name == "currency":
        try:
            from decimal import Decimal
            return DynValue.of_currency(Decimal(str(value.as_float())))
        except (ValueError, TypeError):
            return value
    if type_name == "percent":
        try:
            return DynValue.of_percent(value.as_float())
        except (ValueError, TypeError):
            return value
    return value


# ── Timestamp Normalization ────────────────────────────────────────────────────


def _normalize_timestamp(s: str) -> str:
    """Normalize an ISO 8601 timestamp to UTC."""
    import re as _re
    from datetime import datetime, timedelta

    # Already normalized
    if s.endswith("Z"):
        return s

    # Try parsing with timezone offset
    # Pattern: 2024-06-15T14:30:00+05:30 or 2024-06-15T14:30:00-04:00
    tz_match = _re.search(r'([+-])(\d{2}):?(\d{2})$', s)
    if tz_match:
        sign = 1 if tz_match.group(1) == '+' else -1
        hours = int(tz_match.group(2))
        minutes = int(tz_match.group(3))
        offset = timedelta(hours=hours, minutes=minutes) * sign
        base = s[:tz_match.start()]
        try:
            dt = datetime.fromisoformat(base)
            utc = dt - offset
            return utc.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
        except ValueError:
            pass

    return s  # Return as-is if can't normalize


# ── Segment Ordering ──────────────────────────────────────────────────────────


def _group_segments_by_pass(segments: List[TransformSegment]):
    """Group segments into ordered pass groups: passes 1..N first, then pass 0.

    Returns a list of (pass_num, segments) preserving original order within each pass.
    """
    pass_nums = sorted({seg.pass_num for seg in segments if seg.pass_num})
    groups = []
    for p in pass_nums:
        groups.append((p, [s for s in segments if s.pass_num == p]))
    groups.append((0, [s for s in segments if not s.pass_num]))
    return groups


def _order_segments_by_pass(segments: List[TransformSegment]) -> List[TransformSegment]:
    """Order segments by pass number. Pass 0 (or None) comes last."""
    with_pass = [(seg.pass_num or 0, i, seg) for i, seg in enumerate(segments)]
    # Sort: non-zero passes first (sorted), then pass 0
    result: List[TransformSegment] = []
    non_zero = [(p, i, s) for p, i, s in with_pass if p != 0]
    zero = [(p, i, s) for p, i, s in with_pass if p == 0]
    non_zero.sort(key=lambda x: (x[0], x[1]))
    zero.sort(key=lambda x: x[1])
    result.extend(s for _, _, s in non_zero)
    result.extend(s for _, _, s in zero)
    return result


def _consolidate_indexed_keys(output: DynValue) -> DynValue:
    """Consolidate indexed keys like vehicles[0], vehicles[1] into arrays.

    When a transform uses {vehicles[0]}, {vehicles[1]}, etc., the engine
    creates separate object keys. This function merges them into arrays.
    """
    import re as _re

    if not output.is_object():
        return output

    obj = output.as_object()

    # First recursively consolidate children
    for key in list(obj.keys()):
        val = obj[key]
        if val.is_object():
            obj[key] = _consolidate_indexed_keys(val)
        elif val.is_array():
            obj[key] = DynValue.of_array(
                [_consolidate_indexed_keys(item) for item in val.as_array()]
            )

    # Find indexed keys: name[N]
    indexed_groups: Dict[str, List[tuple]] = {}

    for key in list(obj.keys()):
        match = _re.match(r'^(.+)\[(\d+)\]$', key)
        if match:
            base_name = match.group(1)
            index = int(match.group(2))
            if base_name not in indexed_groups:
                indexed_groups[base_name] = []
            indexed_groups[base_name].append((index, key))

    if not indexed_groups:
        return output

    # Build new output preserving key order, replacing indexed keys with arrays
    new_obj: Dict[str, DynValue] = {}
    processed_indexed: set = set()

    for key in list(obj.keys()):
        match = _re.match(r'^(.+)\[(\d+)\]$', key)
        if match:
            base_name = match.group(1)
            if base_name not in processed_indexed:
                processed_indexed.add(base_name)
                entries = indexed_groups[base_name]
                entries.sort(key=lambda x: x[0])
                items = [obj[k] for _, k in entries]
                new_obj[base_name] = DynValue.of_array(items)
        else:
            new_obj[key] = obj[key]

    return DynValue.of_object(new_obj)


# ── Multi-Record Helpers ──────────────────────────────────────────────────────


def _extract_discriminator_value(
    record: str,
    discriminator: SourceDiscriminator,
    source_format: str,
) -> str:
    """Extract the discriminator value from a record string."""
    if discriminator.type == DiscriminatorType.POSITION:
        pos = discriminator.pos or 0
        length = discriminator.len or 1
        return record[pos:pos + length]

    if discriminator.type == DiscriminatorType.FIELD:
        fields = record.split(",")
        idx = discriminator.field_index or 0
        return fields[idx].strip() if idx < len(fields) else ""

    if discriminator.type == DiscriminatorType.PATH:
        # Path-based: parse as JSON and resolve path
        try:
            parsed = json.loads(record)
            path = discriminator.path or ""
            val = _resolve_sub_path(_python_to_dyn(parsed), path)
            return val.as_string() if not val.is_null() else ""
        except (json.JSONDecodeError, Exception):
            return ""

    return ""


def _parse_record(record: str, source_format: str) -> DynValue:
    """Parse a record string into a DynValue source object for field mappings."""
    if source_format in ("csv", "delimited"):
        # Parse delimited record into indexed fields + _line
        fields = record.split(",")
        rec_obj: Dict[str, DynValue] = {
            "_raw": DynValue.of_string(record),
            "_line": DynValue.of_string(record),
        }
        for i, f in enumerate(fields):
            rec_obj[str(i)] = DynValue.of_string(f)
        return DynValue.of_object(rec_obj)

    if source_format == "json":
        try:
            parsed = json.loads(record)
            result = _python_to_dyn(parsed)
            if result.is_object():
                result.as_object()["_raw"] = DynValue.of_string(record)
            return result
        except json.JSONDecodeError:
            return DynValue.of_object({"_raw": DynValue.of_string(record)})

    # Default: fixed-width - raw line is the source
    return DynValue.of_object({
        "_raw": DynValue.of_string(record),
        "_line": DynValue.of_string(record),
    })
