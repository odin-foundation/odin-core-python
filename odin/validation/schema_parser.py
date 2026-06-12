"""Parse ODIN Schema documents into OdinSchema objects."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple, Union

from odin.types.schema import (
    OdinSchema,
    SchemaField,
    SchemaType,
    SchemaArray,
    SchemaFieldType,
    SchemaConstraint,
    SchemaConditional,
    SchemaObjectConstraint,
    SchemaInvariant,
    SchemaCardinality,
    SchemaImport,
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


def parse_schema(text: str) -> OdinSchema:
    """Parse an ODIN Schema document into an OdinSchema object."""
    parser = SchemaParser(text)
    return parser.parse()


class SchemaParser:
    """Line-based schema parser."""

    def __init__(self, text: str) -> None:
        self.lines = text.split("\n")
        self.pos = 0
        self.metadata: Dict[str, str] = {}
        self.types: Dict[str, SchemaType] = {}
        self.fields: Dict[str, SchemaField] = {}
        self.arrays: Dict[str, SchemaArray] = {}
        self.imports: List[SchemaImport] = []
        self.constraints: Dict[str, List[SchemaObjectConstraint]] = {}

        # Current parsing context
        self._current_header: Optional[str] = None
        self._current_header_kind: str = "root"  # root, metadata, type, array, object
        self._current_type_name: Optional[str] = None
        self._current_array_path: Optional[str] = None

        # Relative-header context: last absolute header, and the sub-path of the
        # current relative header within its parent (e.g. 'term' for {.term}).
        self._previous_header_path: str = ""
        self._previous_header_type: Optional[str] = None
        self._current_type_sub_path: str = ""

    def parse(self) -> OdinSchema:
        """Parse all lines and return schema."""
        while self.pos < len(self.lines):
            line = self.lines[self.pos].strip()
            self.pos += 1

            if not line or line.startswith(";"):
                continue

            if line.startswith("@import "):
                self._parse_import(line, self.pos)
            elif line.startswith("{") and "}" in line:
                self._parse_header(line)
            elif line.startswith(":"):
                self._parse_object_constraint(line)
            elif "=" in line:
                self._parse_field_definition(line)

        for type_def in self.types.values():
            self._extract_type_arrays(type_def)

        return OdinSchema(
            metadata=self.metadata,
            types=self.types,
            fields=self.fields,
            arrays=self.arrays,
            imports=self.imports,
            constraints=self.constraints,
        )

    _TYPE_ARRAY_RE = re.compile(r"^([^\[\]]+)\[\](?:\.(.+))?$")

    def _extract_type_arrays(self, type_def: SchemaType) -> None:
        """Pull array-of-object entries (arr[] / arr[].field) out of a type's
        flat field map into a type-level arrays map for per-element validation.
        """
        builders: Dict[str, SchemaArray] = {}
        for key in list(type_def.fields.keys()):
            m = self._TYPE_ARRAY_RE.match(key)
            if not m:
                continue
            arr_name = m.group(1)
            item_path = m.group(2)
            fld = type_def.fields.pop(key)

            arr = builders.get(arr_name)
            if arr is None:
                arr = SchemaArray(path=arr_name)
                builders[arr_name] = arr

            if item_path is None:
                # arr[] = @type: entry fields come from the referenced type.
                ref: Optional[str] = None
                if isinstance(fld.field_type, TypeRefType):
                    ref = fld.field_type.name
                elif isinstance(fld.field_type, ReferenceType):
                    ref = fld.field_type.target_path
                if ref:
                    arr.item_type_ref = ref
            else:
                # arr[].field: entry field declared inline.
                fld.path = item_path
                arr.item_fields[item_path] = fld

        for name, arr in builders.items():
            type_def.arrays[name] = arr

    def _parse_import(self, line: str, line_no: int) -> None:
        """Parse @import directive: @import "<path>" [as <alias>]."""
        rest = line[8:].strip()
        path, after = _read_import_path(rest)
        alias: Optional[str] = None
        after = after.strip()
        if after.startswith("as "):
            alias = after[3:].strip() or None
        if path:
            self.imports.append(SchemaImport(path=path, alias=alias, line=line_no))

    def _parse_header(self, line: str) -> None:
        """Parse a header line like {$}, {@TypeName}, {path[]}, {path}."""
        # Extract header content between { and }
        brace_end = line.index("}")
        content = line[1:brace_end].strip()

        # Check for array constraint after the header
        after_header = line[brace_end + 1:].strip()

        # Relative header ({.sub}): nest under the last absolute context, not the root.
        if content.startswith("."):
            sub_path = content[1:]
            if self._previous_header_type is not None:
                # Re-open the parent type; fields route under the sub-path (e.g. policy.term.*).
                self._current_header = "@" + self._previous_header_type
                self._current_header_kind = "type"
                self._current_type_name = self._previous_header_type
                self._current_array_path = None
                self._current_type_sub_path = sub_path
            else:
                # Object context: relative headers nest under the last absolute path.
                full = f"{self._previous_header_path}.{sub_path}" if self._previous_header_path else sub_path
                self._current_header = full
                self._current_header_kind = "object"
                self._current_type_name = None
                self._current_array_path = None
                self._current_type_sub_path = ""
            return

        # Absolute header resets the relative sub-path context.
        self._current_type_sub_path = ""

        if content == "$":
            self._current_header = "$"
            self._current_header_kind = "metadata"
            self._current_type_name = None
            self._current_array_path = None
        elif content == "$derivation":
            self._current_header = "$derivation"
            self._current_header_kind = "metadata"
            self._current_type_name = None
            self._current_array_path = None
        elif content.startswith("@"):
            # Type definition
            type_name = content[1:]
            self._current_header = content
            self._current_header_kind = "type"
            self._current_type_name = type_name
            self._current_array_path = None
            self._previous_header_type = type_name
            self._previous_header_path = ""
            if type_name not in self.types:
                self.types[type_name] = SchemaType(name=type_name)
        elif content.endswith("[]") or "[]" in content:
            # Array definition, optionally tabular: {path[] : col1, col2}.
            marker = content.index("[]")
            array_path = content[:marker].strip()
            tail = content[marker + 2:].strip()

            columns: Optional[List[str]] = None
            if tail.startswith(":"):
                columns = self._parse_field_list(tail[1:])

            self._current_header = array_path
            self._current_header_kind = "array"
            self._current_type_name = None
            self._current_array_path = array_path
            self._previous_header_path = array_path
            self._previous_header_type = None

            array_def = SchemaArray(path=array_path, columns=columns)

            # Parse array constraints from after header or following lines
            if after_header:
                self._parse_array_constraints(array_def, after_header)

            self.arrays[array_path] = array_def
        else:
            # Regular object header
            self._current_header = content
            self._current_header_kind = "object"
            self._current_type_name = None
            self._current_array_path = None
            self._previous_header_path = content
            self._previous_header_type = None

    def _parse_array_constraints(self, array_def: SchemaArray, text: str) -> None:
        """Parse constraints on an array definition line."""
        text = text.strip()
        if not text:
            return

        # Check for :unique
        if ":unique" in text:
            array_def.unique = True
            text = text.replace(":unique", "").strip()

        # Check for bounds :(min..max)
        bounds_match = re.search(r":\((\d*)\.\.(\.?\d*)\)", text)
        if bounds_match:
            min_str = bounds_match.group(1)
            max_str = bounds_match.group(2)
            if min_str:
                array_def.min_items = int(min_str)
            if max_str:
                array_def.max_items = int(max_str)

    def _parse_object_constraint(self, line: str) -> None:
        """Parse an object-level constraint like :invariant, :one_of, :of, etc."""
        scope = self._current_header or "root"

        if scope not in self.constraints:
            self.constraints[scope] = []

        line = line.strip()

        if line.startswith(":invariant "):
            expr = line[11:].strip()
            self.constraints[scope].append(SchemaInvariant(expression=expr))
        elif line.startswith(":one_of "):
            fields = self._parse_field_list(line[8:])
            self.constraints[scope].append(
                SchemaCardinality(cardinality_type="one_of", fields=fields, min=1)
            )
        elif line.startswith(":exactly_one "):
            fields = self._parse_field_list(line[13:])
            self.constraints[scope].append(
                SchemaCardinality(cardinality_type="exactly_one", fields=fields, min=1, max=1)
            )
        elif line.startswith(":at_most_one "):
            fields = self._parse_field_list(line[13:])
            self.constraints[scope].append(
                SchemaCardinality(cardinality_type="at_most_one", fields=fields, max=1)
            )
        elif line.startswith(":of "):
            self._parse_of_constraint(line[4:], scope)
        elif line.startswith(":unique"):
            # Array uniqueness on following lines
            if self._current_array_path and self._current_array_path in self.arrays:
                self.arrays[self._current_array_path].unique = True
        elif line.startswith(":("):
            # Array bounds constraint on following line
            if self._current_array_path and self._current_array_path in self.arrays:
                self._parse_array_constraints(self.arrays[self._current_array_path], line)

    def _parse_of_constraint(self, text: str, scope: str) -> None:
        """Parse :of (min..max) field1, field2, ..."""
        bounds_match = re.match(r"\((\d*)\.\.(\.?\d*)\)\s*(.*)", text.strip())
        if bounds_match:
            min_str = bounds_match.group(1)
            max_str = bounds_match.group(2)
            fields = self._parse_field_list(bounds_match.group(3))
            min_val = int(min_str) if min_str else None
            max_val = int(max_str) if max_str else None
            self.constraints[scope].append(
                SchemaCardinality(cardinality_type="of", fields=fields, min=min_val, max=max_val)
            )

    def _parse_field_list(self, text: str) -> List[str]:
        """Parse a comma-separated list of field names."""
        return [f.strip() for f in text.split(",") if f.strip()]

    def _parse_field_definition(self, line: str) -> None:
        """Parse a field definition line: path = [modifiers] [type] [constraints] [conditionals]."""
        # Handle comment at end of line
        comment_idx = _find_comment(line)
        if comment_idx >= 0:
            line = line[:comment_idx].rstrip()

        # Split on first =
        eq_idx = line.index("=")
        left = line[:eq_idx].strip()
        right = line[eq_idx + 1:].strip()

        # Handle array constraint lines like :(1..5)
        if not left and right.startswith(":"):
            if self._current_array_path and self._current_array_path in self.arrays:
                self._parse_array_constraints(self.arrays[self._current_array_path], right)
            return

        # Type composition: = @type1 & @type2 (empty left side)
        if not left and right.startswith("@"):
            self._parse_type_composition(right)
            return

        field_name = left

        # Build full path
        if self._current_header_kind == "metadata":
            self.metadata[field_name] = _unquote(right)
            return
        elif self._current_header_kind == "type":
            # Prefix with sub-path when inside a relative sub-section like {.term}.
            field_name = f"{self._current_type_sub_path}.{field_name}" if self._current_type_sub_path else field_name
            full_path = field_name
        elif self._current_header_kind == "array":
            full_path = field_name
        elif self._current_header_kind == "object" and self._current_header:
            full_path = f"{self._current_header}.{field_name}"
        else:
            full_path = field_name

        # Parse the field spec from the right side
        schema_field = self._parse_field_spec(full_path, right)
        schema_field.path = full_path

        # Store the field
        if self._current_header_kind == "type" and self._current_type_name:
            self.types[self._current_type_name].fields[field_name] = schema_field
        elif self._current_header_kind == "array" and self._current_array_path:
            if self._current_array_path in self.arrays:
                self.arrays[self._current_array_path].item_fields[field_name] = schema_field
        else:
            self.fields[full_path] = schema_field

    def _parse_type_composition(self, text: str) -> None:
        """Parse type composition: = @type1 & @type2 [:override]."""
        text = text.strip()
        has_override = ":override" in text
        body = text.split(":override", 1)[0]
        refs: List[str] = []
        for part in body.split("&"):
            part = part.strip()
            if part.startswith("@"):
                refs.append(part[1:].strip())
            elif part:
                refs.append(part)
        refs = [r for r in refs if r]
        if not refs:
            return

        comp = SchemaField(
            path="",
            field_type=TypeRefType(name="&".join(refs), override=has_override),
        )

        if self._current_header_kind == "type" and self._current_type_name:
            self.types[self._current_type_name].fields["_composition"] = comp
        elif self._current_header_kind == "array" and self._current_array_path:
            if self._current_array_path in self.arrays:
                self.arrays[self._current_array_path].item_fields["_composition"] = comp
        elif self._current_header_kind == "object" and self._current_header:
            self.fields[f"{self._current_header}._composition"] = comp
        else:
            self.fields["_composition"] = comp

    def _parse_field_spec(self, path: str, spec: str) -> SchemaField:
        """Parse the right side of a field definition."""
        sf = SchemaField(path=path)
        if not spec:
            sf.field_type = StringType()
            return sf

        pos = 0
        spec_len = len(spec)

        # Parse modifiers: ! ~ * -
        while pos < spec_len and spec[pos] in "!~*-":
            ch = spec[pos]
            if ch == "!":
                sf.required = True
            elif ch == "~":
                sf.nullable = True
            elif ch == "*":
                sf.redacted = True
            elif ch == "-":
                sf.deprecated = True
            pos += 1

        remaining = spec[pos:].strip()

        # Parse type (with union members and glued :directives) and constraints.
        sf.field_type, remaining = self._parse_type_with_union(sf, remaining)
        sf.constraints, remaining = self._parse_constraints(remaining, sf.field_type)
        sf.conditionals, remaining = self._parse_conditionals(remaining)
        self._parse_directives(sf, remaining)
        self._parse_default_value(sf, remaining)

        return sf

    def _parse_type_with_union(
        self, sf: SchemaField, text: str
    ) -> Tuple[SchemaFieldType, str]:
        """Parse a type and any trailing union members (type1|type2|...)."""
        first, remaining = self._parse_type_spec(text)
        types: List[SchemaFieldType] = [first]
        while remaining.startswith("|"):
            remaining = remaining[1:].strip()
            member, remaining = self._parse_type_spec(remaining)
            types.append(member)
        if len(types) == 1:
            return types[0], remaining
        return UnionType(types=types), remaining

    def _parse_type_spec(self, text: str) -> Tuple[SchemaFieldType, str]:
        """Parse type specifier from text, return (type, remaining_text)."""
        text = text.strip()
        if not text:
            return StringType(), ""

        # Check for enum: (val1, val2, ...)
        if text.startswith("("):
            return self._parse_enum_type(text)

        # Check for type prefixes
        if text.startswith("##"):
            return IntegerType(), text[2:].strip()
        elif text.startswith("#$"):
            rest = text[2:].strip()
            # Check for decimal places #$.N
            if rest.startswith(".") and len(rest) > 1 and rest[1].isdigit():
                places = int(rest[1])
                return CurrencyType(places=places), rest[2:].strip()
            return CurrencyType(), rest
        elif text.startswith("#%"):
            return PercentType(), text[2:].strip()
        elif text.startswith("#"):
            rest = text[1:].strip()
            # Check for decimal places #.N
            if rest.startswith(".") and len(rest) > 1 and rest[1].isdigit():
                places = int(rest[1])
                return DecimalType(places=places), rest[2:].strip()
            return NumberType(), rest
        elif text.startswith("?"):
            return BooleanType(), text[1:].strip()
        elif text.startswith("@"):
            # Type reference or reference type
            rest = text[1:]
            # Extract the name up to space, :, |, or end
            name = ""
            i = 0
            while i < len(rest) and rest[i] not in " \t:,)|":
                name += rest[i]
                i += 1
            remaining = rest[i:].strip()
            if name:
                return TypeRefType(name=name), remaining
            return ReferenceType(), remaining
        elif text.startswith("^"):
            rest = text[1:].strip()
            algo = None
            if rest and rest[0].isalpha():
                end = 0
                while end < len(rest) and rest[end] not in " \t:|":
                    end += 1
                algo = rest[:end]
                rest = rest[end:].strip()
            return BinaryType(algorithm=algo), rest
        elif text.startswith("~"):
            return NullType(), text[1:].strip()
        elif text.startswith('"'):
            # Quoted string — treat as string type with possible default
            return StringType(), text

        # Keyword types
        for keyword, type_cls in _KEYWORD_TYPES:
            if text.startswith(keyword):
                after = text[len(keyword):]
                if not after or after[0] in " \t:,)|":
                    return type_cls(), after.strip()

        # Default: string
        return StringType(), text

    def _parse_enum_type(self, text: str) -> Tuple[SchemaFieldType, str]:
        """Parse (val1, val2, ...) enum type."""
        # Find matching close paren
        depth = 0
        i = 0
        for i, ch in enumerate(text):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break

        enum_content = text[1:i]
        values = [v.strip().strip('"').strip("'") for v in enum_content.split(",")]
        remaining = text[i + 1:].strip()
        return EnumType(values=values), remaining

    def _parse_constraints(
        self, text: str, field_type: SchemaFieldType
    ) -> Tuple[List[SchemaConstraint], str]:
        """Parse constraint expressions from text."""
        constraints: List[SchemaConstraint] = []
        text = text.strip()

        while text.startswith(":"):
            # Check what kind of constraint
            if text.startswith(":("):
                # Bounds constraint
                constraint, text = self._parse_bounds_constraint(text[1:], field_type)
                if constraint:
                    constraints.append(constraint)
            elif text.startswith(":/"):
                # Pattern constraint
                constraint, text = self._parse_pattern_constraint(text[1:])
                if constraint:
                    constraints.append(constraint)
            elif text.startswith(":format ") or text.startswith(":format="):
                # Format constraint
                sep_len = 8 if text.startswith(":format ") else 8
                rest = text[sep_len:].strip()
                fmt_name = ""
                i = 0
                while i < len(rest) and rest[i] not in " \t:":
                    fmt_name += rest[i]
                    i += 1
                if fmt_name:
                    constraints.append(FormatConstraint(format=fmt_name))
                text = rest[i:].strip()
            elif text.startswith(":unique"):
                constraints.append(UniqueConstraint())
                text = text[7:].strip()
            elif text.startswith(":pattern ") or text.startswith(":pattern="):
                # Pattern as :pattern "..."
                sep_len = 9 if text.startswith(":pattern ") else 9
                rest = text[sep_len:].strip()
                if rest.startswith('"'):
                    end = rest.index('"', 1) if '"' in rest[1:] else len(rest)
                    pat = rest[1:end]
                    constraints.append(PatternConstraint(pattern=pat))
                    text = rest[end + 1:].strip() if end + 1 < len(rest) else ""
                else:
                    text = rest
            elif text.startswith(":if ") or text.startswith(":unless "):
                break  # Conditionals handled separately
            elif text.startswith(":computed") or text.startswith(":immutable"):
                break  # Directives handled separately
            else:
                break

        return constraints, text

    def _parse_bounds_constraint(
        self, text: str, field_type: SchemaFieldType
    ) -> Tuple[Optional[BoundsConstraint], str]:
        """Parse (min..max) or (exact) bounds."""
        if not text.startswith("("):
            return None, text

        # Find close paren
        depth = 0
        i = 0
        for i, ch in enumerate(text):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break

        content = text[1:i]
        remaining = text[i + 1:].strip()

        if ".." in content:
            parts = content.split("..", 1)
            min_val = _parse_bound_value(parts[0].strip()) if parts[0].strip() else None
            max_val = _parse_bound_value(parts[1].strip()) if parts[1].strip() else None
        else:
            # Exact value: :(3) means both min and max
            val = _parse_bound_value(content.strip())
            min_val = val
            max_val = val

        return BoundsConstraint(min=min_val, max=max_val), remaining

    def _parse_pattern_constraint(self, text: str) -> Tuple[Optional[PatternConstraint], str]:
        """Parse /regex/ pattern."""
        if not text.startswith("/"):
            return None, text

        # Find closing /
        end = text.index("/", 1) if "/" in text[1:] else len(text)
        pattern = text[1:end]
        remaining = text[end + 1:].strip() if end + 1 < len(text) else ""
        return PatternConstraint(pattern=pattern), remaining

    def _parse_conditionals(self, text: str) -> Tuple[List[SchemaConditional], str]:
        """Parse :if and :unless conditionals."""
        conditionals: List[SchemaConditional] = []
        text = text.strip()

        while text:
            if text.startswith(":if "):
                cond, text = self._parse_single_conditional(text[4:], unless=False)
                if cond:
                    conditionals.append(cond)
            elif text.startswith(":unless "):
                cond, text = self._parse_single_conditional(text[8:], unless=True)
                if cond:
                    conditionals.append(cond)
            else:
                break

        return conditionals, text

    def _parse_single_conditional(
        self, text: str, unless: bool
    ) -> Tuple[Optional[SchemaConditional], str]:
        """Parse: field op value"""
        text = text.strip()
        # Match: field_name operator value
        match = re.match(
            r"(\w[\w.]*)\s*(>=|<=|!=|>|<|=)\s*(\S+)(.*)", text
        )
        if not match:
            return None, text

        field_name = match.group(1)
        operator = match.group(2)
        raw_value = match.group(3).strip().strip('"').strip("'")
        remaining = match.group(4).strip()

        # Store the bare condition field; resolution against the parent path
        # happens during validation.
        cond_field = field_name

        # Parse the value
        value: Union[str, int, float, bool] = raw_value
        if raw_value == "true":
            value = True
        elif raw_value == "false":
            value = False
        else:
            try:
                value = int(raw_value)
            except ValueError:
                try:
                    value = float(raw_value)
                except ValueError:
                    pass

        return SchemaConditional(
            field=cond_field, operator=operator, value=value, unless=unless
        ), remaining

    def _parse_directives(self, sf: SchemaField, text: str) -> None:
        """Parse :computed, :immutable, and other directives."""
        text = text.strip()
        while text:
            if text.startswith(":computed"):
                sf.computed = True
                text = text[9:].strip()
            elif text.startswith(":immutable"):
                sf.immutable = True
                text = text[10:].strip()
            else:
                break

    def _parse_default_value(self, sf: SchemaField, text: str) -> None:
        """Capture a trailing typed/bare default value (e.g. ##3, #$5.00, 3)."""
        text = text.strip()
        if not text or text.startswith(":"):
            return
        parsed = _parse_default_from_string(sf.field_type, text)
        if parsed is not None:
            sf.default_value = parsed


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_KEYWORD_TYPES: List[Tuple[str, type]] = [
    ("timestamp", TimestampType),
    ("date", DateType),
    ("time", TimeType),
    ("duration", DurationType),
    ("string", StringType),
    ("integer", IntegerType),
    ("number", NumberType),
    ("boolean", BooleanType),
    ("currency", CurrencyType),
    ("percent", PercentType),
    ("binary", BinaryType),
    ("null", NullType),
]


def _read_import_path(s: str) -> Tuple[str, str]:
    """Read an import path (quoted or bare), return (path, remaining)."""
    s = s.strip()
    if not s:
        return "", ""
    if s[0] in ('"', "'"):
        quote = s[0]
        end = s.index(quote, 1) if quote in s[1:] else len(s)
        return s[1:end], s[end + 1:]
    parts = s.split(None, 1)
    return parts[0], parts[1] if len(parts) > 1 else ""


def _unquote(s: str) -> str:
    """Remove surrounding quotes from a string."""
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return s[1:-1]
    return s


def _parse_default_from_string(
    field_type: SchemaFieldType, raw: str
) -> Optional[Dict[str, Any]]:
    """Parse a default value fragment into a typed {type, value} dict."""
    s = raw.strip()
    if not s:
        return None

    if s.startswith("##"):
        return {"type": "integer", "value": int(s[2:])}
    if s.startswith("#$"):
        return {"type": "currency", "value": float(s[2:])}
    if s.startswith("#%"):
        return {"type": "percent", "value": float(s[2:])}
    if s.startswith("#"):
        return {"type": "number", "value": float(s[1:])}
    if s.startswith("?"):
        return {"type": "boolean", "value": s[1:] == "true"}
    if s in ("true", "false"):
        return {"type": "boolean", "value": s == "true"}

    if re.match(r"^-?\d", s):
        kind = getattr(field_type, "kind", "")
        try:
            if kind == "integer":
                return {"type": "integer", "value": int(s)}
            if kind == "currency":
                return {"type": "currency", "value": float(s)}
            if kind == "percent":
                return {"type": "percent", "value": float(s)}
            return {"type": "number", "value": float(s)}
        except ValueError:
            pass

    return {"type": "string", "value": s.strip('"').strip("'")}


def _parse_bound_value(s: str) -> Union[int, float, str]:
    """Parse a bound value — could be numeric or date string."""
    if not s:
        return 0
    # Try integer
    try:
        return int(s)
    except ValueError:
        pass
    # Try float
    try:
        return float(s)
    except ValueError:
        pass
    # Return as string (e.g. date)
    return s


def _find_comment(line: str) -> int:
    """Find the position of a ; comment outside of strings."""
    in_string = False
    for i, ch in enumerate(line):
        if ch == '"' and (i == 0 or line[i - 1] != "\\"):
            in_string = not in_string
        elif ch == ";" and not in_string:
            return i
    return -1
