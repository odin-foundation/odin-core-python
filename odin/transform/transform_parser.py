"""Transform parser - parse ODIN transform documents into OdinTransform objects."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from odin.parsing.parser import OdinParser
from odin.types.document import OdinDocument, OdinModifiers
from odin.types.values import (
    OdinValue, OdinNull, OdinBoolean, OdinString, OdinNumber,
    OdinInteger, OdinCurrency, OdinReference, OdinBinary,
    OdinPercent, OdinDate, OdinTimestamp, OdinTime, OdinDuration,
    OdinVerbExpression, OdinArray, OdinObject,
)
from odin.transform.types import (
    OdinTransform,
    TransformMetadata,
    TransformSourceConfig,
    TransformTargetConfig,
    TransformSegment,
    LoopSpec,
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
    Discriminator,
    SegmentDirective,
    ConfidentialMode,
    DiscriminatorType,
    SourceDiscriminator,
    AccumulatorDef,
    LookupTable,
    ImportRef,
)
from odin.transform.dyn_value import DynValue, DynType


def parse_transform(text: str) -> OdinTransform:
    """Parse an ODIN transform definition.

    Args:
        text: ODIN transform text

    Returns:
        Parsed OdinTransform
    """
    doc = OdinParser().parse(text)
    transform = parse_transform_doc(doc)
    # Post-process: extract directives from raw text for fields that lost them
    _patch_missing_directives(transform, text)
    return transform


def parse_transform_doc(doc: OdinDocument) -> OdinTransform:
    """Parse an already-parsed OdinDocument as a transform."""
    metadata = _parse_metadata(doc)
    source = _parse_source_config(doc)
    target = _parse_target_config(doc)
    constants = _parse_constants(doc)
    accumulators = _parse_accumulators(doc)
    tables = _parse_lookup_tables(doc)
    imports = _parse_imports(doc)
    enforce_confidential = _parse_enforce_confidential(doc)
    strict_types = _parse_strict_types(doc)
    segments = _parse_segments(doc)
    passes = _collect_passes(segments)

    return OdinTransform(
        metadata=metadata,
        source=source,
        target=target,
        constants=constants,
        accumulators=accumulators,
        tables=tables,
        segments=segments,
        imports=imports,
        passes=passes,
        enforce_confidential=enforce_confidential,
        strict_types=strict_types,
    )


# ── Metadata ───────────────────────────────────────────────────────────────────


def _parse_metadata(doc: OdinDocument) -> TransformMetadata:
    return TransformMetadata(
        odin_version=_get_meta_string(doc, "odin"),
        transform_version=_get_meta_string(doc, "transform"),
        direction=_get_meta_string(doc, "direction"),
        name=_get_meta_string(doc, "name"),
        description=_get_meta_string(doc, "description"),
    )


# ── Source Config ──────────────────────────────────────────────────────────────


def _parse_source_config(doc: OdinDocument) -> Optional[TransformSourceConfig]:
    # Try both $.source.format (metadata) and $source.format (section header)
    fmt = _get_meta_string(doc, "source.format")
    if fmt is None:
        fmt = _get_source_string(doc, "format")
    if fmt is None:
        return None

    options: Dict[str, str] = {}
    namespaces: Dict[str, str] = {}

    # Check metadata keys (from {$} header: source.namespace.*, source.*)
    for key in _all_meta_keys(doc):
        if key.startswith("source.namespace."):
            ns_name = key[len("source.namespace."):]
            namespaces[ns_name] = _odin_value_to_string(_get_meta_value(doc, key))
        elif key.startswith("source."):
            rest = key[len("source."):]
            if rest != "format" and rest != "discriminator" and not rest.startswith("discriminator."):
                options[rest] = _odin_value_to_string(_get_meta_value(doc, key))

    # Also check $source.* paths (from {$source} section header)
    for path in doc.paths():
        if path.startswith("$source."):
            rest = path[len("$source."):]
            if rest.startswith("namespace."):
                ns_name = rest[len("namespace."):]
                val = doc.get(path)
                if val is not None:
                    namespaces[ns_name] = _odin_value_to_string(val)
            elif rest != "format" and rest != "discriminator" and not rest.startswith("discriminator."):
                val = doc.get(path)
                if val is not None:
                    options[rest] = _odin_value_to_string(val)

    discriminator = _parse_source_discriminator(doc)

    return TransformSourceConfig(
        format=fmt,
        options=options,
        namespaces=namespaces,
        discriminator=discriminator,
    )


def _parse_source_discriminator(doc: OdinDocument) -> Optional[SourceDiscriminator]:
    import re as _re

    # Try structured format first: source.discriminator.type, source.discriminator.pos, etc.
    disc_type_str = _get_meta_string(doc, "source.discriminator.type")
    if disc_type_str is not None:
        type_map = {
            "position": DiscriminatorType.POSITION,
            "field": DiscriminatorType.FIELD,
            "path": DiscriminatorType.PATH,
        }
        disc_type = type_map.get(disc_type_str)
        if disc_type is None:
            return None

        return SourceDiscriminator(
            type=disc_type,
            pos=_get_meta_int(doc, "source.discriminator.pos"),
            len=_get_meta_int(doc, "source.discriminator.len"),
            field_index=_get_meta_int(doc, "source.discriminator.field"),
            path=_get_meta_string(doc, "source.discriminator.path"),
        )

    # Try single-string format: source.discriminator = ":field 0" or ":pos 0 :len 2"
    disc_str = _get_meta_string(doc, "source.discriminator")
    if disc_str is None:
        disc_str = _get_source_string(doc, "discriminator")
    if disc_str is None:
        return None

    pos_match = _re.search(r':pos\s+(\d+)', disc_str)
    len_match = _re.search(r':len\s+(\d+)', disc_str)
    field_match = _re.search(r':field\s+(\d+)', disc_str)

    if pos_match:
        return SourceDiscriminator(
            type=DiscriminatorType.POSITION,
            pos=int(pos_match.group(1)),
            len=int(len_match.group(1)) if len_match else 1,
        )

    if field_match:
        return SourceDiscriminator(
            type=DiscriminatorType.FIELD,
            field_index=int(field_match.group(1)),
        )

    # Path-based discriminator
    path = disc_str.lstrip("@")
    return SourceDiscriminator(
        type=DiscriminatorType.PATH,
        path=path,
    )


# ── Target Config ─────────────────────────────────────────────────────────────


def _parse_target_config(doc: OdinDocument) -> TransformTargetConfig:
    fmt = _get_meta_string(doc, "target.format") or ""
    options: Dict[str, str] = {}
    namespaces: Dict[str, str] = {}

    # Check metadata keys (from {$} header: target.namespace.*, target.*)
    for key in _all_meta_keys(doc):
        if key.startswith("target.namespace."):
            ns_name = key[len("target.namespace."):]
            namespaces[ns_name] = _odin_value_to_string(_get_meta_value(doc, key))
        elif key.startswith("target."):
            rest = key[len("target."):]
            if rest != "format":
                options[rest] = _odin_value_to_string(_get_meta_value(doc, key))

    # Also check $target.* paths (from {$target.namespace} section header)
    for path in doc.paths():
        if path.startswith("$target."):
            rest = path[len("$target."):]
            if rest.startswith("namespace."):
                ns_name = rest[len("namespace."):]
                val = doc.get(path)
                if val is not None:
                    namespaces[ns_name] = _odin_value_to_string(val)
            elif rest != "format":
                val = doc.get(path)
                if val is not None:
                    options[rest] = _odin_value_to_string(val)

    return TransformTargetConfig(format=fmt, options=options, namespaces=namespaces)


# ── Enforce Confidential ──────────────────────────────────────────────────────


def _parse_enforce_confidential(doc: OdinDocument) -> Optional[ConfidentialMode]:
    val = _get_meta_string(doc, "enforceConfidential")
    if val == "redact":
        return ConfidentialMode.REDACT
    if val == "mask":
        return ConfidentialMode.MASK
    return None


def _parse_strict_types(doc: OdinDocument) -> bool:
    val = _get_meta_value(doc, "strictTypes")
    if isinstance(val, OdinBoolean):
        return val.value
    return False


# ── Constants ──────────────────────────────────────────────────────────────────


def _parse_constants(doc: OdinDocument) -> Dict[str, Any]:
    constants: Dict[str, Any] = {}
    array_entries: Dict[str, List[Tuple[int, Any]]] = {}

    for key, value in _all_entries(doc):
        # Match both "const." and "$const." prefixes
        if key.startswith("$const."):
            name = key[len("$const."):]
        elif key.startswith("const."):
            name = key[len("const."):]
        else:
            continue

        # Check for array index
        bracket_pos = name.find("[")
        if bracket_pos >= 0 and name.endswith("]"):
            base_name = name[:bracket_pos]
            try:
                idx = int(name[bracket_pos + 1:-1])
                array_entries.setdefault(base_name, []).append((idx, value))
                continue
            except ValueError:
                pass

        constants[name] = value

    # Build arrays
    for base_name, entries in array_entries.items():
        max_idx = max(idx for idx, _ in entries)
        arr = [None] * (max_idx + 1)
        for idx, val in entries:
            arr[idx] = val
        constants[base_name] = arr

    return constants


# ── Accumulators ───────────────────────────────────────────────────────────────


def _parse_accumulators(doc: OdinDocument) -> Dict[str, AccumulatorDef]:
    accumulators: Dict[str, AccumulatorDef] = {}

    for key, value in _all_entries(doc):
        # Match both "accumulator." and "$accumulator." prefixes
        if key.startswith("$accumulator."):
            name = key[len("$accumulator."):]
        elif key.startswith("accumulator."):
            name = key[len("accumulator."):]
        else:
            continue
        if name.endswith("._persist"):
            continue
        accumulators[name] = AccumulatorDef(name=name, initial=value, persist=False)

    for key, value in _all_entries(doc):
        if key.startswith("$accumulator."):
            name = key[len("$accumulator."):]
        elif key.startswith("accumulator."):
            name = key[len("accumulator."):]
        else:
            continue
        if not name.endswith("._persist"):
            continue
        acc_name = name[:-len("._persist")]
        if acc_name in accumulators and isinstance(value, OdinBoolean):
            accumulators[acc_name].persist = value.value

    return accumulators


# ── Lookup Tables ──────────────────────────────────────────────────────────────


def _parse_lookup_tables(doc: OdinDocument) -> Dict[str, LookupTable]:
    table_rows: Dict[str, List[Tuple[int, str, Any]]] = {}
    table_defaults: Dict[str, Any] = {}

    for key, value in _all_entries(doc):
        if key.startswith("$.table."):
            rest = key[len("$.table."):]
        elif key.startswith("$table."):
            rest = key[len("$table."):]
        elif key.startswith("table."):
            rest = key[len("table."):]
        else:
            continue

        if rest.endswith("._default"):
            name = rest[:-len("._default")]
            if name and "[" not in name:
                table_defaults[name] = value
                continue

        bracket_pos = rest.find("[")
        if bracket_pos < 0:
            continue
        close_pos = rest.find("]", bracket_pos)
        if close_pos < 0:
            continue

        table_name = rest[:bracket_pos]
        try:
            row_idx = int(rest[bracket_pos + 1:close_pos])
        except ValueError:
            continue

        after = rest[close_pos + 1:]
        col_name = after[1:] if after.startswith(".") else after
        if not col_name:
            continue

        table_rows.setdefault(table_name, []).append((row_idx, col_name, value))

    tables: Dict[str, LookupTable] = {}
    for table_name, rows in table_rows.items():
        columns: List[str] = []
        for _, col, _ in rows:
            if col not in columns:
                columns.append(col)

        max_row = max(idx for idx, _, _ in rows)
        row_data: Dict[int, Dict[str, Any]] = {}
        for idx, col, val in rows:
            row_data.setdefault(idx, {})[col] = val

        built_rows = []
        for i in range(max_row + 1):
            rd = row_data.get(i)
            if rd is not None:
                built_rows.append([rd.get(col) for col in columns])

        tables[table_name] = LookupTable(
            name=table_name,
            columns=columns,
            rows=built_rows,
            default=table_defaults.get(table_name),
        )

    return tables


# ── Imports ────────────────────────────────────────────────────────────────────


def _parse_imports(doc: OdinDocument) -> List[ImportRef]:
    imports: List[ImportRef] = []
    for key, value in _all_entries(doc):
        if key.startswith("import."):
            name = key[len("import."):]
            path = _odin_value_to_string(value)
            imports.append(ImportRef(path=path, alias=name))
    return imports


# ── Segments ───────────────────────────────────────────────────────────────────


def _parse_segments(doc: OdinDocument) -> List[TransformSegment]:
    """Parse non-metadata assignments into transform segments."""
    segments: List[TransformSegment] = []
    current_segment: Optional[TransformSegment] = None
    current_header: Optional[str] = None

    # Group assignments by their header context
    # In ODIN, assignments under {Header} belong to that segment
    # Assignments under {$} are metadata (already parsed)

    # We need to look at the raw document structure
    # The parser groups assignments by header path
    # Header paths like "" (root), "Customer", "Items[]" etc.

    # Get all non-metadata assignments grouped by header
    header_groups = _group_by_header(doc)

    for header, assignments in header_groups.items():
        if header == "$" or header.startswith("$"):
            continue  # Skip metadata, constants, accumulators, tables, imports

        seg = _build_segment(header, assignments, doc)
        if seg is not None:
            segments.append(seg)

    return segments


def _group_by_header(doc: OdinDocument) -> Dict[str, List[Tuple[str, Any]]]:
    """Group document assignments by their header context."""
    groups: Dict[str, List[Tuple[str, Any]]] = {}

    for path in doc.paths():
        # Skip metadata entries
        value = doc.get(path)
        if value is None:
            continue

        # Determine header from path
        # Paths like "Customer.Name" → header="Customer", field="Name"
        # Paths like "Name" → header="" (root), field="Name"
        # Paths like "Items[0].Name" → might be from {Items[]}
        header, field = _split_header_field(path)

        groups.setdefault(header, []).append((field, value, path, doc.modifiers.get(path)))

    return groups


def _split_header_field(path: str) -> Tuple[str, str]:
    """Split a path into header and field parts."""
    # Check for indexed array pattern: Items[0].field → header=Items[0], field=field
    # Preserves the index so {vehicles[0]} and {vehicles[1]} stay separate
    idx_match = re.match(r'^([^.\[]+\[\d+\])\.(.+)$', path)
    if idx_match:
        return idx_match.group(1), idx_match.group(2)

    # Check for array-shorthand pattern (no explicit index): Items[].field
    arr_match = re.match(r'^([^.\[]+)\[\]\.(.+)$', path)
    if arr_match:
        return arr_match.group(1) + "[]", arr_match.group(2)

    # Check for simple nested: Header.Field → header=Header, field=Field
    dot_pos = path.find(".")
    if dot_pos >= 0:
        return path[:dot_pos], path[dot_pos + 1:]

    # Root-level field
    return "", path


def _build_segment(
    header: str,
    assignments: List,
    doc: OdinDocument,
) -> Optional[TransformSegment]:
    """Build a TransformSegment from grouped assignments."""
    is_array = header.endswith("[]")
    clean_name = header[:-2] if is_array else header

    # Handle indexed segments like "vehicles[0]" — preserve index in name
    # so the engine can create indexed keys (later consolidated into arrays)
    array_index = None
    if not is_array:
        idx_match = re.match(r'^(.+)\[(\d+)\]$', header)
        if idx_match:
            array_index = int(idx_match.group(2))
            # Keep the indexed name (e.g., "vehicles[0]") so the engine
            # outputs separate indexed keys that get consolidated into arrays
            # clean_name stays as the full "vehicles[0]" for the segment

    seg = TransformSegment(
        name=clean_name,
        path=clean_name,
        is_array=is_array,
    )

    # Separate top-level assignments from sub-segment assignments
    # Sub-segments are detected by paths containing [] (e.g., "contacts[]._loop")
    top_assignments = []
    sub_segment_groups: Dict[str, List] = {}

    for entry in assignments:
        if len(entry) == 4:
            field = entry[0]
        else:
            field = entry[0]

        # Detect sub-segment: field contains [] (nested array segment)
        arr_idx = field.find("[]")
        if arr_idx >= 0:
            # Split: everything before [] is the sub-segment name
            sub_name = field[:arr_idx]
            sub_field = field[arr_idx + 3:]  # skip [].
            if not sub_field and field.endswith("[]"):
                sub_field = ""
            # Create modified entry with the sub-field
            if len(entry) == 4:
                sub_entry = (sub_field, entry[1], entry[2], entry[3])
            else:
                sub_entry = (sub_field, entry[1]) + entry[2:]
            sub_segment_groups.setdefault(sub_name, []).append(sub_entry)
            continue

        top_assignments.append(entry)

    # Build sub-segments
    for sub_name, sub_entries in sub_segment_groups.items():
        child_seg = _build_segment(sub_name + "[]", sub_entries, doc)
        if child_seg is not None:
            seg.children.append(child_seg)

    source_path = None
    from_path = None
    mappings = []
    loops: List[LoopSpec] = []

    for entry in top_assignments:
        if len(entry) == 4:
            field, value, full_path, modifiers = entry
        else:
            field, value = entry[:2]
            full_path = None
            modifiers = None

        # Handle _pass directive
        if field == "_pass":
            try:
                if isinstance(value, OdinInteger):
                    seg.pass_num = value.value
                elif isinstance(value, OdinNumber):
                    seg.pass_num = int(value.value)
                elif isinstance(value, OdinString):
                    seg.pass_num = int(value.value)
            except (ValueError, TypeError):
                pass
            continue

        # Handle _if / _elif directive (verb-expression or legacy infix condition)
        if field in ("_if", "_elif"):
            seg.branch = field[1:]
            _set_segment_condition(seg, value)
            continue

        # Handle _else directive (bare flag, value ignored)
        if field == "_else":
            seg.branch = "else"
            continue

        # Handle _type (discriminator)
        if field == "_type":
            disc_value = _odin_value_to_string(value)
            seg.segment_discriminator = Discriminator(path="", value=disc_value)
            continue

        # Handle _loop directive (string assignment). Repeated loops are stored as
        # _loop, _loop2, _loop3, …; each adds a nested iteration level.
        if field == "_loop" or _LOOP_KEY_RE.match(field):
            if isinstance(value, OdinString):
                raw = value.value
            elif isinstance(value, OdinReference):
                raw = value.path
            else:
                raw = ""
            loop_path, loop_alias = _split_loop_alias(raw)
            loop_path = loop_path.lstrip("@").strip() if not loop_path.startswith(".") else loop_path
            if field == "_loop":
                source_path = loop_path
            loops.append(LoopSpec(path=loop_path, alias=loop_alias))
            continue

        # Handle _literal / _literalBody directives (literal text block segment)
        if field == "_literal":
            seg.is_literal = True
            continue
        if field == "_literalBody":
            if isinstance(value, OdinString):
                seg.literal_body = value.value
            continue

        # Handle _from directive (alternative loop source; takes priority over _loop)
        if field == "_from":
            if isinstance(value, OdinString):
                from_path = value.value.lstrip("@").strip()
            elif isinstance(value, OdinReference):
                from_path = value.path
            continue

        # Handle _counter directive (loop counter name)
        if field == "_counter":
            if isinstance(value, OdinString):
                seg.counter_name = value.value.lstrip("@").strip()
            elif isinstance(value, OdinReference):
                seg.counter_name = value.path
            continue

        # Check for loop directive: _ = @items :loop
        if field == "_" and isinstance(value, OdinReference):
            ref_path = value.path
            # Parse directives from the reference path
            directives = _parse_inline_directives(ref_path)
            clean_ref = _strip_directives(ref_path)
            if any(d.name == "loop" for d in directives):
                source_path = clean_ref
                continue
            # Even without :loop, _ = @path is still a loop source for array segments
            if is_array:
                if clean_ref:
                    # Non-empty path → set source_path
                    source_path = clean_ref
                    continue
                elif source_path is None:
                    # Empty path and no _loop set yet → set empty source
                    source_path = clean_ref
                    continue
                # else: Empty path but _loop already set → identity mapping, fall through

        mapping = _build_mapping(field, value, modifiers)
        if mapping is not None:
            mappings.append(mapping)

    # _from takes priority over _loop / path as the loop source.
    if from_path is not None:
        source_path = from_path
        if loops:
            loops[0] = LoopSpec(path=source_path, alias=loops[0].alias)
    seg.source_path = source_path
    seg.mappings = mappings
    seg.loops = loops

    if (
        not mappings
        and source_path is None
        and not seg.children
        and not seg.is_literal
    ):
        return None

    return seg


# Repeated loop keys: _loop2, _loop3, …
_LOOP_KEY_RE = re.compile(r"^_loop\d+$")


def _split_loop_alias(raw: str) -> tuple[str, Optional[str]]:
    """Split a loop directive value `path :as alias` into (path, alias)."""
    if ":as" in raw:
        head, _, tail = raw.partition(":as")
        return head.strip(), tail.strip() or None
    return raw.strip(), None


def _set_segment_condition(seg: TransformSegment, value: Any) -> None:
    """Store a segment condition as a parsed verb expression or legacy infix string.

    Verb conditions (`%verb …` or an OdinVerbExpression) are parsed into a
    TransformExpression evaluated by the expression evaluator. A bare reference or
    a non-`%` string is kept as a legacy infix condition string.
    """
    if isinstance(value, OdinVerbExpression):
        seg.condition_expr = TransformExpression(call=_parse_verb_call(value))
        return
    if isinstance(value, OdinString):
        raw = value.value.strip()
        if raw.startswith("%"):
            call = _parse_verb_from_string(raw)
            if call is not None:
                seg.condition_expr = TransformExpression(call=call)
                return
        seg.condition = value.value
        return
    if isinstance(value, OdinReference):
        seg.condition = value.path


def _build_mapping(
    field: str,
    value: Any,
    modifiers: Optional[OdinModifiers] = None,
) -> Optional[FieldMapping]:
    """Build a FieldMapping from a field name and its value."""
    expression, directives, extra_modifiers = _parse_value_expression(value)
    if expression is None:
        return None

    # Merge modifiers from the document with those parsed from directives
    final_modifiers = _merge_modifiers(modifiers, extra_modifiers)

    return FieldMapping(
        target=field,
        expression=expression,
        modifiers=final_modifiers,
        directives=directives,
    )


def _split_object_pairs(body: str) -> List[str]:
    """Split an inline object body on commas not nested inside braces."""
    pairs: List[str] = []
    depth = 0
    current = ""
    for ch in body:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if ch == "," and depth == 0:
            pairs.append(current)
            current = ""
        else:
            current += ch
    if current.strip():
        pairs.append(current)
    return pairs


def _build_object_expression(spec: str) -> ObjectExpression:
    """Build an ObjectExpression from an inline `{key = @path, ...}` spec."""
    inner = spec.strip()
    if inner.startswith("{"):
        inner = inner[1:]
    if inner.endswith("}"):
        inner = inner[:-1]
    fields: List[FieldMapping] = []
    if inner.strip():
        for pair in _split_object_pairs(inner):
            eq = pair.find("=")
            if eq == -1:
                continue
            key = pair[:eq].strip()
            rhs = pair[eq + 1:].strip()
            if not key:
                continue
            expr, directives, _ = _parse_value_expression(OdinString(value=rhs))
            fields.append(FieldMapping(target=key, expression=expr, directives=directives))
    return ObjectExpression(fields=fields)


def _parse_value_expression(value: Any) -> Tuple[Optional[FieldExpression], List[Directive], Optional[OdinModifiers]]:
    """Parse an OdinValue into a FieldExpression with directives."""
    directives: List[Directive] = []
    extra_modifiers: Optional[OdinModifiers] = None

    if isinstance(value, OdinNull):
        return LiteralExpression(value=value), directives, extra_modifiers

    if isinstance(value, OdinBoolean):
        return LiteralExpression(value=value), directives, extra_modifiers

    if isinstance(value, (OdinInteger, OdinNumber, OdinCurrency, OdinPercent)):
        return LiteralExpression(value=value), directives, extra_modifiers

    if isinstance(value, (OdinDate, OdinTimestamp, OdinTime, OdinDuration)):
        return LiteralExpression(value=value), directives, extra_modifiers

    if isinstance(value, OdinBinary):
        return LiteralExpression(value=value), directives, extra_modifiers

    if isinstance(value, OdinReference):
        path = value.path
        path, special = _extract_special_directives(path)
        # Parse directives from reference path
        directives = special + _parse_inline_directives(path)
        clean_path = _strip_directives(path)
        extra_modifiers = _extract_modifier_directives(directives)
        return CopyExpression(path=clean_path), directives, extra_modifiers

    if isinstance(value, OdinVerbExpression):
        # Extract directives from verb expression string (e.g., "%formatDate @x :pos 3 :len 8")
        raw_verb = value.verb if hasattr(value, 'verb') else ""
        directives = _parse_inline_directives(raw_verb)
        if directives:
            # Strip directives from the raw verb string before parsing verb call
            stripped = _strip_directives(raw_verb)
            value = OdinVerbExpression(verb=stripped, args=value.args, is_custom=value.is_custom)
            extra_modifiers = _extract_modifier_directives(directives)
        call = _parse_verb_call(value)
        return TransformExpression(call=call), directives, extra_modifiers

    if isinstance(value, OdinString):
        raw = value.value

        # Inline object spec: `:object {k = @p, ...}` builds a nested object.
        obj_match = _OBJECT_RE.search(raw)
        if raw.lstrip().startswith(":object") and obj_match:
            return _build_object_expression(obj_match.group(1)), [], None

        # Pull rest-of-line (:if/:unless) and :object out before generic parsing.
        raw, special = _extract_special_directives(raw)

        # Check if it's a reference pattern (@path)
        if raw.startswith("@"):
            path = raw[1:]
            directives = special + _parse_inline_directives(path)
            clean_path = _strip_directives(path)
            extra_modifiers = _extract_modifier_directives(directives)
            return CopyExpression(path=clean_path), directives, extra_modifiers

        # Check if it's a verb pattern (%verb ...)
        if raw.startswith("%"):
            # Extract directives first
            directives = special + _parse_inline_directives(raw)
            if directives:
                clean_raw = _strip_directives(raw)
                extra_modifiers = _extract_modifier_directives(directives)
            else:
                clean_raw = raw
            call = _parse_verb_from_string(clean_raw)
            if call:
                return TransformExpression(call=call), directives, extra_modifiers

        # Check for directives in the string
        directives = special + _parse_inline_directives(raw)
        if directives:
            clean = _strip_directives(raw)
            extra_modifiers = _extract_modifier_directives(directives)
            # Re-check if clean part is a reference
            if clean.startswith("@"):
                return CopyExpression(path=clean[1:]), directives, extra_modifiers
            return LiteralExpression(value=OdinString(value=clean)), directives, extra_modifiers

        if special:
            return LiteralExpression(value=OdinString(value=raw)), special, None
        return LiteralExpression(value=value), directives, extra_modifiers

    # Fallback
    return LiteralExpression(value=value), directives, extra_modifiers


def _parse_verb_call(verb_expr: OdinVerbExpression) -> VerbCall:
    """Convert an OdinVerbExpression to a VerbCall.

    The OdinVerbExpression.verb field contains the full raw expression
    like '%upper @name'. The args tuple is usually empty (raw parsing).
    We parse the raw string into verb name + args.
    """
    if verb_expr.args:
        # Args were already parsed
        args: List[VerbArg] = []
        for arg in verb_expr.args:
            if isinstance(arg, OdinReference):
                args.append(ReferenceArg(path=arg.path))
            elif isinstance(arg, OdinVerbExpression):
                nested_call = _parse_verb_call(arg)
                args.append(VerbCallArg(call=nested_call))
            elif isinstance(arg, OdinString):
                raw = arg.value
                if raw.startswith("@"):
                    args.append(ReferenceArg(path=raw[1:]))
                else:
                    args.append(LiteralArg(value=arg))
            else:
                args.append(LiteralArg(value=arg))
        # Extract verb name from raw expression
        raw = verb_expr.verb
        verb_name = raw.lstrip("%").split()[0] if raw.startswith("%") else raw
        return VerbCall(verb=verb_name, is_custom=verb_expr.is_custom, args=args)

    # Parse from the raw expression string
    raw = verb_expr.verb
    call = _parse_verb_from_string(raw)
    if call:
        call.is_custom = verb_expr.is_custom
        return call
    return VerbCall(verb=raw, is_custom=verb_expr.is_custom)


def _parse_verb_from_string(raw: str) -> Optional[VerbCall]:
    """Parse a verb expression from a raw string like '%upper @name'.

    Uses recursive descent to correctly handle nested verb calls:
    %ifElse %eq @a @b %accumulate passed ##1 %accumulate failed ##1
    parses as: ifElse(eq(a, b), accumulate(passed, 1), accumulate(failed, 1))
    """
    if not raw.startswith("%"):
        return None

    rest = raw[1:]
    is_custom = rest.startswith("&")
    if is_custom:
        rest = rest[1:]

    parts = _tokenize_verb_string(rest)
    if not parts:
        return None

    call = _parse_top_verb(parts)
    if call:
        call.is_custom = is_custom
    return call


def _parse_nested_verb(parts: List[str], start: int) -> Tuple[Optional[VerbCall], int]:
    """Parse a nested verb call starting at parts[start] (which starts with %).

    A nested verb consumes non-% tokens as its args, limited by known verb arity.
    Stops when it hits the next % token (sibling verb) or reaches its arity limit.

    Returns (VerbCall, next_index).
    """
    if start >= len(parts):
        return None, start

    raw_name = parts[start]
    is_custom = raw_name.startswith("%&")
    verb_name = raw_name.lstrip("%").lstrip("&")

    args: List[VerbArg] = []
    i = start + 1
    max_args = _VERB_ARITY.get(verb_name)  # None means consume all non-% tokens

    while i < len(parts):
        if max_args is not None and len(args) >= max_args:
            break  # Reached arity limit
        part = parts[i]
        if part.startswith("%"):
            if max_args is not None and len(args) < max_args:
                # This verb still needs args — parse nested verb as an arg
                nested_call, i = _parse_nested_verb(parts, i)
                if nested_call is not None:
                    args.append(VerbCallArg(call=nested_call))
                continue
            break  # No arity or arity satisfied — sibling verb
        i = _parse_plain_arg(parts, i, args)

    return VerbCall(verb=verb_name, is_custom=is_custom, args=args), i


# Known verb arities for correct nested verb parsing.
# Verbs not listed here consume all non-% tokens when nested.
_VERB_ARITY: Dict[str, int] = {
    # Comparison (2 args)
    "eq": 2, "ne": 2, "lt": 2, "gt": 2, "lte": 2, "gte": 2,
    # Boolean (1-2 args)
    "not": 1, "and": 2, "or": 2, "xor": 2, "implies": 2, "nand": 2, "nor": 2,
    # Arithmetic (2 args)
    "add": 2, "subtract": 2, "multiply": 2, "divide": 2, "mod": 2,
    # Unary (1 arg)
    "negate": 1, "abs": 1, "floor": 1, "ceil": 1,
    "upper": 1, "lower": 1, "trim": 1, "trimLeft": 1, "trimRight": 1,
    "capitalize": 1, "titleCase": 1, "length": 1,
    "camelCase": 1, "snakeCase": 1, "kebabCase": 1, "pascalCase": 1, "slugify": 1,
    "base64Encode": 1, "base64Decode": 1, "urlEncode": 1, "urlDecode": 1,
    "sha256": 1, "md5": 1,
    "isNull": 1, "isNumber": 1, "isInteger": 1, "isString": 1, "isBoolean": 1,
    "isArray": 1, "isObject": 1, "isDate": 1,
    "coerceString": 1, "coerceNumber": 1, "coerceInteger": 1, "coerceBoolean": 1, "coerceDate": 1,
    # Binary (2 args)
    "accumulate": 2, "set": 2,
    # Aggregation (1 arg = array)
    "sum": 1, "count": 1, "min": 1, "max": 1, "avg": 1,
    "first": 1, "last": 1,
    "std": 1, "stdSample": 1, "variance": 1, "varianceSample": 1,
    "median": 1, "mode": 1,
    "percentile": 2, "quantile": 2,
    "covariance": 2, "correlation": 2,
    "weightedAvg": 2,
    # Array (various)
    "filter": 4, "flatten": 1, "distinct": 1,
    "sort": 1, "sortDesc": 1, "sortBy": 2,
    "map": 2, "indexOf": 2, "at": 2, "slice": 3, "reverse": 1,
    # Financial
    "compound": 3, "discount": 3, "pmt": 3, "fv": 3, "pv": 3,
    "npv": 2, "irr": 1,
    # Math
    "log": 2, "ln": 1, "log10": 1, "exp": 1, "pow": 2, "sqrt": 1,
    "clamp": 3,
    # Generation
    "uuid": 1, "sequence": 1, "resetSequence": 1,
    "round": 2, "formatNumber": 2, "formatInteger": 2,
    "formatCurrency": 2, "formatPercent": 2,
    "padLeft": 2, "padRight": 2, "truncate": 2, "mask": 2,
    "contains": 2, "startsWith": 2, "endsWith": 2,
    "ifNull": 2, "ifEmpty": 2,
    "lookup": 2, "lookupDefault": 2,
    "addDays": 2, "addMonths": 2, "addYears": 2,
    "replace": 2,  # Actually 3 but rare as nested
    "substring": 2,  # Actually 2-3
    # Ternary (3 args)
    "ifElse": 3, "ternary": 3, "between": 3,
    "replace": 3,
    "substring": 3,
    "formatDate": 2, "formatTimestamp": 2,
    "parseDate": 2,
    "dateDiff": 2, "dayOfWeek": 1,
    # New verbs
    "nextBusinessDay": 1, "formatDuration": 1,
    "formatPhone": 2, "movingAvg": 2, "businessDays": 2,
    "reduce": 3, "pivot": 3, "unpivot": 3, "convertUnit": 3,
}


def _parse_top_verb(parts: List[str]) -> Optional[VerbCall]:
    """Parse the top-level verb call from parts (first element is verb name).

    The top-level verb can have both plain args and nested %verb sub-calls.
    Nested verbs each consume their own trailing non-% args.

    Example: ifElse %eq @a @b %accumulate passed ##1 %accumulate failed ##1
    → ifElse( eq(a, b), accumulate(passed, 1), accumulate(failed, 1) )
    """
    if not parts:
        return None

    verb_name = parts[0]
    is_custom = verb_name.startswith("&")
    if is_custom:
        verb_name = verb_name[1:]

    args: List[VerbArg] = []
    i = 1

    while i < len(parts):
        part = parts[i]
        if part.startswith("%"):
            nested, i = _parse_nested_verb(parts, i)
            if nested:
                args.append(VerbCallArg(call=nested))
        else:
            i = _parse_plain_arg(parts, i, args)

    return VerbCall(verb=verb_name, is_custom=is_custom, args=args)


def _parse_plain_arg(parts: List[str], i: int, args: List[VerbArg]) -> int:
    """Parse a single non-verb argument at parts[i], append to args, return next index."""
    part = parts[i]
    if part == "@" and i + 1 < len(parts) and not parts[i + 1].startswith(("@", "%", '"', "#", "~", "?")):
        args.append(ReferenceArg(path=parts[i + 1]))
        return i + 2
    elif part.startswith("@"):
        args.append(ReferenceArg(path=part[1:]))
    elif part.startswith('"') and part.endswith('"'):
        args.append(LiteralArg(value=OdinString(value=part[1:-1])))
    elif part.startswith("#$"):
        try:
            from decimal import Decimal
            args.append(LiteralArg(value=OdinCurrency(value=Decimal(part[2:]))))
        except Exception:
            args.append(LiteralArg(value=OdinString(value=part)))
    elif part.startswith("##"):
        try:
            args.append(LiteralArg(value=OdinInteger(value=int(part[2:]))))
        except ValueError:
            args.append(LiteralArg(value=OdinString(value=part)))
    elif part.startswith("#%"):
        try:
            args.append(LiteralArg(value=OdinPercent(value=float(part[2:]))))
        except ValueError:
            args.append(LiteralArg(value=OdinString(value=part)))
    elif part.startswith("#"):
        try:
            args.append(LiteralArg(value=OdinNumber(value=float(part[1:]))))
        except ValueError:
            args.append(LiteralArg(value=OdinString(value=part)))
    elif part == "~":
        args.append(LiteralArg(value=OdinNull()))
    elif part.startswith("?"):
        args.append(LiteralArg(value=OdinBoolean(value=part[1:].lower() == "true")))
    elif part in ("true", "false"):
        args.append(LiteralArg(value=OdinBoolean(value=part == "true")))
    else:
        args.append(LiteralArg(value=OdinString(value=part)))
    return i + 1


def _tokenize_verb_string(s: str) -> List[str]:
    """Tokenize a verb argument string, respecting quoted strings."""
    tokens: List[str] = []
    i = 0
    while i < len(s):
        if s[i] in (" ", "\t"):
            i += 1
            continue
        if s[i] == '"':
            # Quoted string
            end = s.find('"', i + 1)
            if end < 0:
                end = len(s)
            tokens.append(s[i:end + 1])
            i = end + 1
        else:
            # Unquoted token
            start = i
            while i < len(s) and s[i] not in (" ", "\t"):
                if s[i] == '"':
                    break
                i += 1
            tokens.append(s[start:i])
    return tokens


# ── Directive Parsing ──────────────────────────────────────────────────────────


_DIRECTIVE_RE = re.compile(r'(?<=\s):(\w+)(?:\s+"([^"]*)"|\s+([^\s:]+))?')

# Boolean directives that never consume a following value
_BOOLEAN_DIRECTIVES = frozenset({
    "trim", "required", "confidential", "deprecated", "attr", "loop",
    "raw", "array", "cdata",
})

# Directives whose value is the entire remainder of the line (e.g. `:if a = b`).
_REST_OF_LINE_RE = re.compile(r'\s+:(if|unless)\s+(.+)$')

# Inline object spec: `:object {k = @p, ...}` (consumes a brace-balanced body).
_OBJECT_RE = re.compile(r'(?:^|\s):object\s*(\{.*\})\s*$')


def _extract_special_directives(text: str) -> Tuple[str, List[Directive]]:
    """Pull rest-of-line (:if/:unless) and :object specs out of a directive string.

    Returns (remaining_text, directives). The remaining text still carries any
    other inline directives for the generic parser.
    """
    extracted: List[Directive] = []

    obj = _OBJECT_RE.search(text)
    if obj:
        extracted.append(Directive(name="object", value=obj.group(1).strip()))
        text = text[:obj.start()].rstrip()

    rest = _REST_OF_LINE_RE.search(text)
    if rest:
        extracted.append(Directive(name=rest.group(1), value=rest.group(2).strip()))
        text = text[:rest.start()].rstrip()

    return text, extracted


def _parse_inline_directives(text: str) -> List[Directive]:
    """Parse :directive patterns from text."""
    directives: List[Directive] = []
    for m in _DIRECTIVE_RE.finditer(text):
        name = m.group(1)
        if name in _BOOLEAN_DIRECTIVES:
            directives.append(Directive(name=name, value=None))
        else:
            value = m.group(2) if m.group(2) is not None else m.group(3)
            directives.append(Directive(name=name, value=value))
    return directives


def _strip_directives(text: str) -> str:
    """Remove :directive patterns from text."""
    def _replace(m: re.Match) -> str:
        name = m.group(1)
        if name in _BOOLEAN_DIRECTIVES:
            # Only strip the directive name, not the following value
            full = m.group(0)
            name_end = m.start(1) - m.start(0) + len(name)
            return full[name_end:]  # keep everything after the directive name
        return ""
    result = _DIRECTIVE_RE.sub(_replace, text).strip()
    return result


def _extract_modifier_directives(directives: List[Directive]) -> Optional[OdinModifiers]:
    """Extract OdinModifiers from a list of directives."""
    required = False
    confidential = False
    deprecated = False

    for d in directives:
        if d.name == "required":
            required = True
        elif d.name == "confidential":
            confidential = True
        elif d.name == "deprecated":
            deprecated = True

    if required or confidential or deprecated:
        return OdinModifiers(
            required=required,
            confidential=confidential,
            deprecated=deprecated,
        )
    return None


def _patch_missing_directives(transform: OdinTransform, raw_text: str):
    """Post-process: extract directives from raw text for fields that lost them.

    The ODIN parser drops directives after quoted strings (e.g., "EMP" :pos 0 :len 3).
    This function rescans the raw text to find and attach those directives.
    """
    # Build a map of field → raw line text
    field_lines: Dict[str, str] = {}
    current_header = ""
    for line in raw_text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        # Header
        if stripped.startswith("{") and stripped.endswith("}"):
            h = stripped[1:-1].strip()
            if h.startswith("$") or h.startswith("."):
                continue
            current_header = h
            continue
        # Assignment
        eq_pos = stripped.find("=")
        if eq_pos > 0:
            field = stripped[:eq_pos].strip()
            raw_value = stripped[eq_pos + 1:].strip()
            key = f"{current_header}.{field}" if current_header else field
            field_lines[key] = raw_value

    # Now check each mapping and patch missing directives
    for segment in transform.segments:
        _patch_segment_directives(segment, field_lines, "")


def _patch_segment_directives(segment, field_lines: Dict[str, str], parent_prefix: str):
    """Patch directives for a single segment's mappings."""
    seg_name = segment.name
    if segment.is_array:
        seg_name = segment.name + "[]"

    # Build full qualified name including parent prefix
    full_seg_name = f"{parent_prefix}.{seg_name}" if parent_prefix else seg_name

    for mapping in segment.mappings:
        key = f"{full_seg_name}.{mapping.target}" if full_seg_name else mapping.target
        raw_line = field_lines.get(key, "")
        if not raw_line:
            # Try with [] suffix
            key2 = f"{full_seg_name}[].{mapping.target}" if full_seg_name else mapping.target
            raw_line = field_lines.get(key2, "")
        if not raw_line:
            # Try without parent prefix (backward compatibility)
            local_key = f"{seg_name}.{mapping.target}" if seg_name else mapping.target
            raw_line = field_lines.get(local_key, "")
        if raw_line:
            raw_directives = _parse_inline_directives(raw_line)
            if raw_directives:
                # Merge: use raw directives, they're the most complete
                existing_names = {d.name for d in mapping.directives}
                for rd in raw_directives:
                    if rd.name not in existing_names:
                        mapping.directives.append(rd)
                        existing_names.add(rd.name)
                # If raw has more directives, replace entirely
                if len(raw_directives) > len(mapping.directives):
                    mapping.directives = raw_directives

            # Fix truncated @.@attr reference paths
            # ODIN parser truncates @.@id to just @. — recover full path from raw text
            if isinstance(mapping.expression, CopyExpression):
                _fix_truncated_ref_path(mapping, raw_line)

    # Pass the parent segment name (without []) as prefix for children
    parent_for_children = f"{parent_prefix}.{segment.name}" if parent_prefix else segment.name
    for child in segment.children:
        _patch_segment_directives(child, field_lines, parent_for_children)


def _fix_truncated_ref_path(mapping, raw_line: str):
    """Fix reference paths truncated by the ODIN parser.

    The ODIN parser truncates @.@id to just @. because the second @
    looks like a new reference. We recover the full path from the raw text.
    """
    import re as _re
    expr = mapping.expression
    if not isinstance(expr, CopyExpression):
        return

    # Extract the reference path from raw text: @path (before any space-delimited directives)
    m = _re.match(r'@(\S+)', raw_line)
    if not m:
        return

    raw_path = m.group(1)
    # Strip any directives that start after whitespace
    # The path is everything up to the first space-colon pattern
    clean = _DIRECTIVE_RE.sub("", raw_path).strip()

    # Only fix if the raw path is longer/different
    if len(clean) > len(expr.path) and clean != expr.path:
        mapping.expression = CopyExpression(path=clean)


def _merge_modifiers(
    doc_modifiers: Optional[OdinModifiers],
    extra_modifiers: Optional[OdinModifiers],
) -> Optional[OdinModifiers]:
    """Merge document-level modifiers with directive-extracted modifiers."""
    if doc_modifiers is None and extra_modifiers is None:
        return None
    if doc_modifiers is None:
        return extra_modifiers
    if extra_modifiers is None:
        return doc_modifiers
    return OdinModifiers(
        required=doc_modifiers.required or extra_modifiers.required,
        confidential=doc_modifiers.confidential or extra_modifiers.confidential,
        deprecated=doc_modifiers.deprecated or extra_modifiers.deprecated,
    )


# ── Pass Collection ────────────────────────────────────────────────────────────


def _collect_passes(segments: List[TransformSegment]) -> List[int]:
    """Collect all pass numbers from segments."""
    passes: set = set()
    for seg in segments:
        if seg.pass_num is not None:
            passes.add(seg.pass_num)
    return sorted(passes)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _get_meta_value(doc: OdinDocument, key: str) -> Optional[Any]:
    """Get a metadata value by key."""
    # Check metadata first
    meta = doc.metadata
    if key in meta:
        return meta[key]
    # Check assignments (for non-header metadata)
    return doc.get(key)


def _get_meta_string(doc: OdinDocument, key: str) -> Optional[str]:
    """Get a metadata value as string."""
    val = _get_meta_value(doc, key)
    if val is None:
        return None
    return _odin_value_to_string(val)


def _get_source_string(doc: OdinDocument, key: str) -> Optional[str]:
    """Get a value from the {$source} section."""
    val = doc.get("$source." + key)
    if val is None:
        return None
    return _odin_value_to_string(val)


def _get_meta_int(doc: OdinDocument, key: str) -> Optional[int]:
    """Get a metadata value as int."""
    val = _get_meta_value(doc, key)
    if val is None:
        return None
    if isinstance(val, OdinInteger):
        return val.value
    if isinstance(val, OdinNumber):
        return int(val.value)
    if isinstance(val, OdinString):
        try:
            return int(val.value)
        except ValueError:
            return None
    return None


def _odin_value_to_string(val: Any) -> str:
    """Convert an OdinValue to string."""
    if val is None:
        return ""
    if isinstance(val, OdinString):
        return val.value
    if isinstance(val, OdinInteger):
        return str(val.value)
    if isinstance(val, OdinNumber):
        return str(val.value)
    if isinstance(val, OdinBoolean):
        return "true" if val.value else "false"
    if isinstance(val, OdinNull):
        return ""
    if isinstance(val, OdinReference):
        return val.path
    if isinstance(val, OdinCurrency):
        return str(val.value)
    return str(getattr(val, "value", ""))


def _all_meta_keys(doc: OdinDocument) -> List[str]:
    """Get all metadata keys."""
    keys = list(doc.metadata.keys())
    return keys


def _all_entries(doc: OdinDocument):
    """Yield all entries from metadata and assignments."""
    for key, value in doc.metadata.items():
        yield key, value
    for path in doc.paths():
        yield path, doc.get(path)
