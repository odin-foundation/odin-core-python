"""Transform execution engine - execute ODIN transforms on source data."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

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
from odin.types.document import OdinModifiers
from odin.types.values import (
    OdinValue, OdinNull, OdinBoolean, OdinString, OdinNumber,
    OdinInteger, OdinCurrency, OdinPercent, OdinReference,
    OdinDate, OdinTimestamp, OdinTime, OdinDuration, OdinBinary,
)

MAX_LOOP_NESTING = 10

# Verbs that require lazy evaluation of their branch arguments
_LAZY_EVAL_VERBS = frozenset({"ifElse", "ternary", "switch"})


class VerbContext:
    """Context available to verb functions during execution."""

    __slots__ = (
        "source", "loop_vars", "accumulators", "tables",
        "constants", "global_output",
    )

    def __init__(self) -> None:
        self.source: DynValue = DynValue.of_null()
        self.loop_vars: Dict[str, DynValue] = {}
        self.accumulators: Dict[str, DynValue] = {}
        self.tables: Dict[str, Any] = {}
        self.constants: Dict[str, DynValue] = {}
        self.global_output: DynValue = DynValue.of_null()


class _ExecContext:
    """Internal execution context."""

    __slots__ = (
        "source", "constants", "accumulators", "tables",
        "loop_vars", "warnings", "errors",
        "enforce_confidential", "global_output", "field_modifiers",
        "source_format", "verb_registry", "loop_depth",
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
        self.verb_registry: Optional[VerbRegistry] = None
        self.loop_depth: int = 0


class TransformEngine:
    """ODIN transform execution engine."""

    def __init__(self, registry: VerbRegistry) -> None:
        self.registry = registry

    def execute(self, transform: OdinTransform, source: Any) -> TransformResult:
        """Execute a transform on source data."""
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

        segments = _order_segments_by_pass(transform.segments)

        current_pass = None
        is_first = True
        for seg in segments:
            seg_pass = seg.pass_num
            if seg_pass != current_pass and not is_first:
                # Reset non-persist accumulators on pass change
                for name, acc_def in transform.accumulators.items():
                    if not acc_def.persist:
                        ctx.accumulators[name] = _odin_value_to_dyn(acc_def.initial)
            current_pass = seg_pass
            is_first = False

            output = self._process_segment(seg, ctx, output, "")
            ctx.global_output = output

        # Consolidate indexed segments (e.g., vehicles[0], vehicles[1] → vehicles array)
        output = _consolidate_indexed_keys(output)

        # Confidential enforcement
        if ctx.enforce_confidential is not None:
            _apply_confidential_enforcement(
                transform.segments, ctx.enforce_confidential, output
            )

        # Format output
        formatted = self._format_output(output, transform, ctx.field_modifiers)

        return TransformResult(
            success=len(ctx.errors) == 0,
            output=output,
            formatted=formatted,
            errors=ctx.errors,
            warnings=ctx.warnings,
            output_modifiers=ctx.field_modifiers,
        )

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

            # Process segment mappings
            record_output = DynValue.of_object({})
            for mapping in seg.mappings:
                # Skip _type mapping (it's the discriminator, not an output field)
                if mapping.target == "_type":
                    continue
                record_output = self._process_mapping(
                    mapping, record_ctx, record_source, record_output, ""
                )

            # Merge modifiers from record context
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
        formatted = self._format_output(output, transform, ctx.field_modifiers)

        return TransformResult(
            success=len(ctx.errors) == 0,
            output=output,
            formatted=formatted,
            errors=ctx.errors,
            warnings=ctx.warnings,
            output_modifiers=ctx.field_modifiers,
        )

    def _process_segment(
        self,
        segment: TransformSegment,
        ctx: _ExecContext,
        output: DynValue,
        path_prefix: str,
    ) -> DynValue:
        # Condition check
        if segment.condition is not None:
            cond_val = _resolve_path(ctx.source, segment.condition, ctx)
            if not _is_truthy(cond_val):
                return output

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

        # Discard segments (name starts with _)
        if name.startswith("_") and not is_root:
            for mapping in segment.mappings:
                self._process_mapping(mapping, ctx, ctx.source, output, current_prefix)
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

            # Check if segment has ONLY "_" target mappings (identity/value-only semantics)
            is_value_only = all(m.target == "_" for m in segment.mappings)

            for idx, item in enumerate(items):
                ctx.loop_vars["_item"] = item
                ctx.loop_vars["_index"] = DynValue.of_integer(idx)
                ctx.loop_vars["_length"] = DynValue.of_integer(len(items))

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

            array_result = DynValue.of_array(result_items)
            if not is_root:
                _set_path(output, clean_name, array_result)
            else:
                output = array_result

            return output

        # Standard segment (no loop)
        if is_root:
            for mapping in segment.mappings:
                output = self._process_mapping(mapping, ctx, ctx.source, output, path_prefix)
            for child in segment.children:
                output = self._process_segment(child, ctx, output, path_prefix)
        else:
            seg_output = _get_or_create_object(output, clean_name)
            for mapping in segment.mappings:
                seg_output = self._process_mapping(
                    mapping, ctx, ctx.source, seg_output, current_prefix,
                )
            for child in segment.children:
                seg_output = self._process_segment(child, ctx, seg_output, current_prefix)
            _set_path(output, clean_name, seg_output)

        return output

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

        except Exception as e:
            ctx.errors.append(TransformError(
                message=str(e),
                path=mapping.target,
            ))

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
            return _odin_value_to_dyn(expr.value)

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
            ctx.errors.append(TransformError(
                message=f"Unknown verb: {call.verb}",
                path="",
            ))
            return DynValue.of_null()

        # Conditional verbs need lazy evaluation of branches
        if call.verb in _LAZY_EVAL_VERBS:
            return self._execute_lazy_verb(call, fn, ctx, current_source, current_output)

        # Evaluate arguments eagerly
        args: List[DynValue] = []
        for arg in call.args:
            args.append(self._evaluate_verb_arg(arg, ctx, current_source, current_output))

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

    def _format_output(self, output: DynValue, transform: OdinTransform, field_modifiers: Optional[Dict[str, 'OdinModifiers']] = None) -> Optional[str]:
        """Format the output DynValue using the target format."""
        target_format = transform.target.format
        if not target_format:
            # Default to json if direction specifies it
            direction = transform.metadata.direction or ""
            if "->" in direction:
                target_format = direction.split("->")[1]
            if not target_format:
                target_format = "json"

        opts = transform.target.options

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
            # Unknown format - try json as fallback
            from odin.transform.formatters.json_formatter import format_json
            return format_json(output)
        except Exception:
            return None


# ── Path Resolution ────────────────────────────────────────────────────────────


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
        return DynValue.of_currency(value.value, dp=getattr(value, 'decimal_places', 2))
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
        return DynValue.of_currency(value.value, dp=getattr(value, 'decimal_places', 2))
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
