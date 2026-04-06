"""ODIN parser - converts token streams into OdinDocument instances."""
from __future__ import annotations

import re
from collections import OrderedDict

# Pre-compiled regex for tabular header column parsing
_BRACKET_COLUMNS_RE = re.compile(
    r'\[([a-zA-Z_][a-zA-Z0-9_]*(?:\s*,\s*[a-zA-Z_][a-zA-Z0-9_]*)*)\]$'
)
from typing import Dict, List, Optional, Set, Tuple

from odin.parsing.tokenizer import Tokenizer
from odin.parsing.tokens import Token, TokenType
from odin.parsing.value_parser import parse_modifiers, parse_value
from odin.types.document import OdinDocument, OdinDocumentBuilder, OdinModifiers
from odin.types.errors import ParseError, ParseErrorCodes
from odin.types.options import ParseOptions
from odin.types.values import NULL, OdinNull, OdinString, OdinValue


# Security limits
MAX_ARRAY_INDEX = 10_000
DEFAULT_MAX_DEPTH = 64

# Token type sets for fast membership checks
_ASSIGNMENT_START_TYPES = frozenset({
    TokenType.IDENTIFIER, TokenType.PREFIX_EXTENSION,
    TokenType.PREFIX_META, TokenType.BOOLEAN, TokenType.ARRAY_INDEX,
})
_PATH_TYPES = frozenset({
    TokenType.IDENTIFIER, TokenType.DOT, TokenType.ARRAY_INDEX,
    TokenType.PREFIX_EXTENSION, TokenType.PREFIX_META, TokenType.BOOLEAN,
})


class OdinParser:
    """Parser that builds OdinDocument from ODIN text."""

    def parse(self, text: str, options: Optional[ParseOptions] = None) -> OdinDocument:
        """Parse ODIN text into a document."""
        if options is None:
            options = ParseOptions()

        # BOM check
        if text and text[0] == "\ufeff":
            text = text[1:]

        # Size check
        if len(text) > options.max_document_size:
            raise ParseError(
                "Maximum document size exceeded",
                ParseErrorCodes.P011,
                1,
                1,
            )

        tokens = Tokenizer(text).tokenize()
        return self._build_documents(tokens, options)

    def _build_documents(self, tokens: List[Token], options: ParseOptions) -> OdinDocument:
        """Build document(s) from token stream. Returns the first/primary document."""
        documents: List[OdinDocument] = []
        start = 0

        # Find document separators
        doc_starts: List[int] = [0]
        for i, t in enumerate(tokens):
            if t.type == TokenType.DOC_SEPARATOR:
                doc_starts.append(i + 1)

        for seg_idx, seg_start in enumerate(doc_starts):
            seg_end = doc_starts[seg_idx + 1] - 1 if seg_idx + 1 < len(doc_starts) else len(tokens)
            doc = self._build_single_document(tokens, seg_start, seg_end, options)
            documents.append(doc)

        if len(documents) == 0:
            return OdinDocumentBuilder().build()

        return documents[0]

    def _build_single_document(
        self,
        tokens: List[Token],
        start: int,
        end: int,
        options: ParseOptions,
    ) -> OdinDocument:
        """Build a single document from a segment of the token stream."""
        builder = OdinDocumentBuilder()
        pos = start
        current_header: Optional[str] = None
        last_absolute_header: Optional[str] = None
        in_metadata = False
        assigned_paths: Set[str] = set()
        array_indices: Dict[str, List[int]] = {}
        max_depth = options.max_nesting_depth

        # Tabular mode state
        tabular_columns: Optional[List[str]] = None
        tabular_base: Optional[str] = None
        tabular_row_index = 0

        last_was_newline = False

        while pos < end:
            token = tokens[pos]
            tt = token.type

            # Skip newlines and comments, with metadata blank-line detection
            if tt == TokenType.NEWLINE:
                if last_was_newline and in_metadata and current_header is None:
                    in_metadata = False
                last_was_newline = True
                pos += 1
                continue
            if tt == TokenType.COMMENT:
                last_was_newline = False
                pos += 1
                continue
            if tt == TokenType.EOF:
                break

            last_was_newline = False

            # Document separator (should be handled by caller, but skip)
            if tt == TokenType.DOC_SEPARATOR:
                pos += 1
                continue

            # Header
            if tt == TokenType.HEADER_OPEN:
                result = self._parse_header(tokens, pos, end, current_header, last_absolute_header)
                pos = result[0]
                current_header = result[1]
                new_last_abs = result[2]
                in_metadata = result[3]
                is_tabular = result[4]
                tab_cols = result[5]
                tab_base = result[6]

                if new_last_abs is not None:
                    last_absolute_header = new_last_abs

                if is_tabular:
                    tabular_columns = tab_cols
                    tabular_base = tab_base
                    tabular_row_index = 0
                else:
                    tabular_columns = None
                    tabular_base = None

                continue

            # Directives (@import, @schema, @if)
            if tt in (TokenType.DIRECTIVE_IMPORT, TokenType.DIRECTIVE_SCHEMA, TokenType.DIRECTIVE_COND):
                self._validate_directive(token)
                pos += 1
                continue

            # Directives that tokenizer didn't fully capture (@import without path)
            if tt == TokenType.PREFIX_REFERENCE and token.column == 1:
                # Check if next token is 'import', 'schema', 'if'
                if pos + 1 < end and tokens[pos + 1].type == TokenType.IDENTIFIER:
                    directive_name = tokens[pos + 1].value
                    if directive_name in ("import", "schema", "if"):
                        # Collect the rest of the line
                        pos += 2
                        rest_parts = []
                        while pos < end and tokens[pos].type not in (TokenType.NEWLINE, TokenType.EOF):
                            rest_parts.append(tokens[pos].value)
                            pos += 1
                        rest = " ".join(rest_parts).strip()
                        if directive_name == "import" and not rest:
                            raise ParseError(
                                "Invalid directive: @import requires a path",
                                ParseErrorCodes.P009,
                                token.line,
                                token.column,
                            )
                        if directive_name == "schema" and not rest:
                            raise ParseError(
                                "Invalid directive: @schema requires a URL",
                                ParseErrorCodes.P009,
                                token.line,
                                token.column,
                            )
                        if directive_name == "if" and not rest:
                            raise ParseError(
                                "Invalid directive: @if requires a condition",
                                ParseErrorCodes.P009,
                                token.line,
                                token.column,
                            )
                        # Validate import alias syntax
                        if directive_name == "import" and "as" in rest:
                            parts_list = rest.split()
                            if parts_list[-1] == "as":
                                raise ParseError(
                                    "Invalid directive: @import alias requires a name",
                                    ParseErrorCodes.P009,
                                    token.line,
                                    token.column,
                                )
                        continue

            # Tabular data rows
            if tabular_columns is not None and tt != TokenType.HEADER_OPEN:
                if self._is_assignment_start(tokens, pos, end):
                    # Assignment line in tabular context — exit tabular mode
                    # (e.g., _loop = "@items" after {items[] : col1, col2})
                    tabular_columns = None
                    tabular_base = None
                else:
                    pos = self._parse_tabular_row(
                        tokens, pos, end, tabular_base or "", tabular_columns,
                        tabular_row_index, builder, assigned_paths, array_indices,
                        in_metadata, max_depth,
                    )
                    tabular_row_index += 1
                    continue

            # Assignment: path = value
            if self._is_assignment_start(tokens, pos, end):
                pos = self._parse_assignment(
                    tokens, pos, end, current_header, in_metadata,
                    builder, assigned_paths, array_indices, max_depth,
                )
                continue

            # Identifier or path that's not an assignment - could be an error
            if tt == TokenType.IDENTIFIER:
                # Check if it's just a lone identifier on a line (no = follows)
                # This is an error condition
                raise ParseError(
                    "Invalid syntax",
                    ParseErrorCodes.P001,
                    token.line,
                    token.column,
                )

            # Prefix token at start of line without path
            if tt == TokenType.PREFIX_REFERENCE:
                # @something at start of line, not at col 1 (directives handled above)
                raise ParseError(
                    "Unexpected character",
                    ParseErrorCodes.P001,
                    token.line,
                    token.column,
                )

            # Error token
            if tt == TokenType.ERROR:
                msg = token.value if token.value else "Unexpected character"
                if "Unterminated" in msg:
                    raise ParseError(msg, ParseErrorCodes.P004, token.line, token.column)
                if "Invalid escape" in msg:
                    raise ParseError(msg, ParseErrorCodes.P005, token.line, token.column)
                raise ParseError(msg, ParseErrorCodes.P001, token.line, token.column)

            # Skip other unexpected tokens
            pos += 1

        return builder.build()

    def _is_assignment_start(self, tokens: List[Token], pos: int, end: int) -> bool:
        """Check if tokens at pos form an assignment (path = value)."""
        i = pos
        # Must start with identifier, dot, array index, prefix_extension, or prefix_meta
        if i >= end:
            return False
        tt = tokens[i].type
        if tt not in _ASSIGNMENT_START_TYPES:
            return False

        # Scan forward through path tokens looking for EQUALS
        while i < end:
            t = tokens[i]
            if t.type == TokenType.EQUALS:
                return True
            if t.type in _PATH_TYPES:
                i += 1
                continue
            break
        return False

    def _parse_header(
        self,
        tokens: List[Token],
        pos: int,
        end: int,
        current_header: Optional[str],
        last_absolute_header: Optional[str],
    ) -> Tuple[int, Optional[str], Optional[str], bool, bool, Optional[List[str]], Optional[str]]:
        """Parse a header like {Section}, {.relative}, {$}, {}, {items[]}, {items[] : col1, col2}.

        Returns (new_pos, current_header, last_absolute_header_update, in_metadata,
                 is_tabular, tabular_columns, tabular_base).
        """
        pos += 1  # consume {
        header_line = tokens[pos - 1].line
        header_col = tokens[pos - 1].column

        # Collect header content
        parts: List[str] = []
        is_meta = False
        is_relative = False
        is_tabular = False
        tabular_columns: Optional[List[str]] = None

        in_column_defs = False  # After `:` in tabular header
        _last_col_parent: Optional[str] = None  # For relative column resolution

        while pos < end:
            t = tokens[pos]

            if t.type == TokenType.HEADER_CLOSE:
                pos += 1
                break

            if t.type == TokenType.NEWLINE or t.type == TokenType.EOF:
                raise ParseError(
                    "Invalid header syntax - missing closing brace",
                    ParseErrorCodes.P008,
                    header_line,
                    header_col,
                )

            # Detect tabular column separator `:` (comes as ERROR token)
            if t.type == TokenType.ERROR and t.value == ":":
                in_column_defs = True
                is_tabular = True
                tabular_columns = []
                pos += 1
                continue

            # Collecting column names after `:`
            if in_column_defs:
                if t.type == TokenType.IDENTIFIER or t.type == TokenType.BOOLEAN:
                    # Collect full dotted name with array indices (e.g., product.name, permissions[0])
                    col_parts = [t.value]
                    pos += 1
                    while pos < end:
                        if tokens[pos].type == TokenType.DOT:
                            pos += 1  # skip dot
                            if pos < end and tokens[pos].type in (TokenType.IDENTIFIER, TokenType.BOOLEAN):
                                col_parts.append(".")
                                col_parts.append(tokens[pos].value)
                                pos += 1
                        elif tokens[pos].type == TokenType.ARRAY_INDEX:
                            col_parts.append(f"[{tokens[pos].value}]")
                            pos += 1
                        else:
                            break
                    col_name = "".join(col_parts)
                    tabular_columns.append(col_name)
                    # Track last parent for relative column resolution
                    if "." in col_name:
                        _last_col_parent = col_name.rsplit(".", 1)[0]
                    else:
                        _last_col_parent = None
                elif t.type == TokenType.PREFIX_NULL:
                    # ~column marker = primitive array mode
                    tabular_columns.append("~")
                    pos += 1
                elif t.type == TokenType.ERROR and t.value == ",":
                    pos += 1  # skip comma separator
                elif t.type == TokenType.DOT:
                    # Relative column like .city (relative to previous column's parent)
                    pos += 1
                    if pos < end and tokens[pos].type in (TokenType.IDENTIFIER, TokenType.BOOLEAN):
                        rel_name = tokens[pos].value
                        pos += 1
                        # Resolve against last column's parent
                        if _last_col_parent:
                            tabular_columns.append(f"{_last_col_parent}.{rel_name}")
                        else:
                            tabular_columns.append(rel_name)
                else:
                    pos += 1
                continue

            if t.type == TokenType.PREFIX_META:
                is_meta = True
                parts.append("$")
                pos += 1
            elif t.type == TokenType.DOT:
                if not parts:
                    is_relative = True
                parts.append(".")
                pos += 1
            elif t.type == TokenType.IDENTIFIER or t.type == TokenType.BOOLEAN:
                parts.append(t.value)
                pos += 1
            elif t.type == TokenType.ARRAY_INDEX:
                content = t.value.strip()
                if content == "":
                    parts.append("[]")
                else:
                    try:
                        idx = int(content)
                        if idx < 0:
                            raise ParseError(
                                f"Invalid array index: {content}",
                                ParseErrorCodes.P003,
                                t.line,
                                t.column,
                            )
                        parts.append(f"[{content}]")
                    except ValueError:
                        # Check for obviously broken array index (e.g., [} from {invalid[})
                        if "}" in content or not content:
                            raise ParseError(
                                "Invalid array index",
                                ParseErrorCodes.P003,
                                t.line,
                                t.column,
                            )
                        # In headers: column definitions like [code, name] for lookup tables
                        parts.append(f"[{content}]")
                pos += 1
            elif t.type == TokenType.PREFIX_EXTENSION:
                parts.append("&")
                pos += 1
            elif t.type == TokenType.PREFIX_REFERENCE:
                parts.append("@")
                pos += 1
            elif t.type == TokenType.COMMENT:
                pos += 1
            elif t.type == TokenType.ERROR:
                if "}" not in t.value:
                    raise ParseError(
                        f"Invalid array index",
                        ParseErrorCodes.P003,
                        t.line,
                        t.column,
                    )
                pos += 1
            else:
                pos += 1

        header_value = "".join(parts)

        # Skip trailing whitespace/newline after header, check for tabular `: col1, col2`
        # Actually tabular detection: {items[] : col1, col2} is done differently
        # The `:` and column names would be INSIDE the braces
        # Let me re-check... Actually in ODIN spec, tabular is:
        # {items[] : name, qty, price}
        # So the colon and columns are INSIDE the header braces.

        # Re-scan: if we see `[] :` or `[] : ` in header_value, that's tabular
        # Actually we need to re-examine - the parts we collected may include the colon

        # Hmm, the tokenizer wouldn't emit the `:` inside a header as a special token.
        # Let me check if the content contains `:` for tabular detection.
        # Actually, looking at the golden tests more carefully:
        # {items[] : name, qty, price} - the colon is part of the header content.

        # The issue is that the tokenizer emits individual tokens inside {}.
        # A colon `:` inside the header wouldn't be emitted as a token by our tokenizer.
        # Let me handle tabular by looking at the raw text approach.

        # For now, handle tabular by checking if header_value ends with []
        # and then looking for colon in the header.

        # Actually, I think we need to handle tabular differently.
        # Looking at the golden test input: {items[] : name, qty, price}
        # The tokenizer will see { then `items` IDENTIFIER, then `[]` ARRAY_INDEX,
        # then whitespace, then `:` which isn't a standard token...
        # Let me handle tabular by re-parsing the raw header text.

        # For simplicity and to match golden tests, let's detect tabular from the token stream.
        # If we see header with empty array_index, we need to check if remaining header content
        # has column definitions.

        # Let's use a simpler approach: extract the full header text between { and }
        # from the original tokens, handling the tabular case with string manipulation.

        # Metadata header
        if header_value == "$":
            return pos, None, None, True, False, None, None

        # Empty header - reset
        if header_value == "" or header_value.strip() == "":
            return pos, None, None, False, False, None, None

        # Reference header
        if header_value.startswith("@"):
            return pos, header_value[1:], header_value[1:], False, False, None, None

        # Relative header
        if is_relative:
            rel_path = header_value[1:]  # remove leading dot
            if last_absolute_header:
                new_header = last_absolute_header + "." + rel_path
            else:
                new_header = rel_path
            return pos, new_header, None, False, False, None, None

        # Tabular header: path ends with []
        if header_value.endswith("[]") and is_tabular and tabular_columns:
            base = header_value[:-2]
            return pos, header_value, header_value, False, True, tabular_columns, base

        # Lookup table column definition: {$table.NAME[col1, col2]}
        # Detect bracket with non-integer content as column definitions
        import re
        bracket_match = _BRACKET_COLUMNS_RE.search(header_value)
        if bracket_match:
            col_str = bracket_match.group(1)
            cols = [c.strip() for c in col_str.split(",")]
            base = header_value[:bracket_match.start()]
            tab_header = base + "[]"
            return pos, tab_header, tab_header, is_meta, True, cols, base

        # Absolute header
        new_header = header_value
        new_last_abs = header_value
        return pos, new_header, new_last_abs, False, False, None, None

    def _parse_assignment(
        self,
        tokens: List[Token],
        pos: int,
        end: int,
        current_header: Optional[str],
        in_metadata: bool,
        builder: OdinDocumentBuilder,
        assigned_paths: Set[str],
        array_indices: Dict[str, List[int]],
        max_depth: int,
    ) -> int:
        """Parse a path = value assignment line. Returns new pos."""
        # Collect path tokens
        path_parts: List[str] = []
        path_line = tokens[pos].line
        path_col = tokens[pos].column
        has_empty_array = False

        while pos < end:
            t = tokens[pos]
            if t.type == TokenType.EQUALS:
                pos += 1  # consume =
                break
            if t.type == TokenType.IDENTIFIER or t.type == TokenType.BOOLEAN:
                path_parts.append(t.value)
                pos += 1
            elif t.type == TokenType.DOT:
                path_parts.append(".")
                pos += 1
            elif t.type == TokenType.ARRAY_INDEX:
                content = t.value.strip()
                if content == "":
                    has_empty_array = True
                    path_parts.append("[]")
                elif content.isdigit():
                    path_parts.append(f"[{int(content)}]")
                else:
                    path_parts.append(f"[{content}]")
                pos += 1
            elif t.type == TokenType.PREFIX_EXTENSION:
                path_parts.append("&")
                pos += 1
            elif t.type == TokenType.PREFIX_META:
                path_parts.append("$")
                pos += 1
            else:
                break

        path_value = "".join(path_parts)

        # Resolve full path with header context
        full_path = self._resolve_path(path_value, current_header)

        # Depth validation (P010)
        depth = self._count_depth(full_path)
        if depth > max_depth:
            raise ParseError(
                "Maximum depth exceeded",
                ParseErrorCodes.P010,
                path_line,
                path_col,
            )

        # Array index validation (P015 & P003)
        self._validate_array_indices(full_path, path_line, path_col, array_indices)

        # Duplicate path check (P007)
        check_path = "$." + full_path if in_metadata else full_path
        if check_path in assigned_paths:
            raise ParseError(
                "Duplicate path assignment",
                ParseErrorCodes.P007,
                path_line,
                path_col,
            )

        # Parse modifiers
        mods, mod_consumed = parse_modifiers(tokens, pos)
        pos += mod_consumed

        # Parse value
        if pos < end and tokens[pos].type not in (TokenType.NEWLINE, TokenType.EOF, TokenType.COMMENT):
            value, val_consumed = parse_value(tokens, pos)
            pos += val_consumed
        else:
            value = OdinString("")

        # Skip remaining tokens on the line (trailing comments, directives, etc.)
        while pos < end and tokens[pos].type not in (TokenType.NEWLINE, TokenType.EOF):
            pos += 1

        # Store
        assigned_paths.add(check_path)

        if in_metadata:
            builder.set_metadata(full_path, value)
            # Also store in assignments with $. prefix
            builder.set(f"$.{full_path}", value, mods if mods.has_any else None)
        else:
            builder.set(full_path, value, mods if mods.has_any else None)

        return pos

    def _resolve_path(self, path: str, header: Optional[str]) -> str:
        """Resolve assignment path with header context."""
        if header is None:
            return path
        if not path:
            return header
        if path.startswith("["):
            # Array index directly: {items}[0] -> items[0]
            h = header
            if h.endswith("[]"):
                h = h[:-2]
            return h + path
        return header + "." + path

    def _count_depth(self, path: str) -> int:
        """Count nesting depth of a path."""
        return 1 + path.count('.') + path.count('[')

    def _validate_array_indices(
        self,
        full_path: str,
        line: int,
        col: int,
        array_indices: Dict[str, List[int]],
    ) -> None:
        """Validate array indices in a path for range (P015) and contiguity (P013)."""
        cumulative = 0
        i = 0
        while i < len(full_path):
            if full_path[i] == "[":
                bracket_start = i
                i += 1
                close = full_path.find("]", i)
                if close == -1:
                    idx_str = full_path[i:]
                    i = len(full_path)
                else:
                    idx_str = full_path[i:close]
                    i = close + 1

                idx_str = idx_str.strip()
                if idx_str == "":
                    continue  # empty array marker []

                # Check for negative index
                if idx_str.startswith("-"):
                    raise ParseError(
                        f"Invalid array index: {idx_str}",
                        ParseErrorCodes.P003,
                        line,
                        col,
                    )

                try:
                    idx = int(idx_str)
                except ValueError:
                    raise ParseError(
                        f"Invalid array index: {idx_str}",
                        ParseErrorCodes.P003,
                        line,
                        col,
                    )

                if idx < 0:
                    raise ParseError(
                        f"Invalid array index: {idx_str}",
                        ParseErrorCodes.P003,
                        line,
                        col,
                    )

                # Range check (P015)
                cumulative += idx
                if idx > MAX_ARRAY_INDEX or cumulative > MAX_ARRAY_INDEX:
                    raise ParseError(
                        "Array index out of range",
                        ParseErrorCodes.P015,
                        line,
                        col,
                    )

                # Contiguity tracking - use the array base path
                array_base = full_path[:bracket_start]
                if array_base not in array_indices:
                    array_indices[array_base] = []
                indices = array_indices[array_base]

                if idx not in indices:
                    expected = 0 if not indices else max(indices) + 1
                    if idx != expected:
                        raise ParseError(
                            f"Non-contiguous array indices: expected {expected}, got {idx}",
                            ParseErrorCodes.P013,
                            line,
                            col,
                        )
                    indices.append(idx)
            else:
                i += 1

    def _validate_directive(self, token: Token) -> None:
        """Validate a directive token for completeness."""
        val = token.value
        if val.startswith("@import"):
            rest = val[7:].strip()
            if not rest:
                raise ParseError(
                    "Invalid directive: @import requires a path",
                    ParseErrorCodes.P009,
                    token.line,
                    token.column,
                )
            parts = rest.split()
            if parts[-1] == "as":
                raise ParseError(
                    "Invalid directive: @import alias requires a name",
                    ParseErrorCodes.P009,
                    token.line,
                    token.column,
                )
        elif val.startswith("@schema"):
            rest = val[7:].strip()
            if not rest:
                raise ParseError(
                    "Invalid directive: @schema requires a URL",
                    ParseErrorCodes.P009,
                    token.line,
                    token.column,
                )
        elif val.startswith("@if"):
            rest = val[3:].strip()
            if not rest:
                raise ParseError(
                    "Invalid directive: @if requires a condition",
                    ParseErrorCodes.P009,
                    token.line,
                    token.column,
                )

    def _parse_tabular_row(
        self,
        tokens: List[Token],
        pos: int,
        end: int,
        base: str,
        columns: List[str],
        row_index: int,
        builder: OdinDocumentBuilder,
        assigned_paths: Set[str],
        array_indices: Dict[str, List[int]],
        in_metadata: bool,
        max_depth: int,
    ) -> int:
        """Parse a tabular data row. Returns new pos."""
        col_idx = 0
        expect_value = True

        while pos < end and tokens[pos].type not in (TokenType.NEWLINE, TokenType.EOF):
            t = tokens[pos]

            # Comma separator (comes as ERROR token from tokenizer)
            if t.type == TokenType.ERROR and t.value == ",":
                if expect_value:
                    # Empty cell - absent value, skip this column
                    pass
                col_idx += 1
                expect_value = True
                pos += 1
                continue

            if not expect_value:
                pos += 1
                continue

            if col_idx >= len(columns):
                pos += 1
                continue

            # Parse modifiers
            mods, mod_consumed = parse_modifiers(tokens, pos)
            pos += mod_consumed

            # Parse value
            if pos < end and tokens[pos].type not in (
                TokenType.NEWLINE, TokenType.EOF
            ) and not (tokens[pos].type == TokenType.ERROR and tokens[pos].value == ","):
                value, val_consumed = parse_value(tokens, pos)
                pos += val_consumed

                # Build path
                col_name = columns[col_idx]
                if col_name == "~":
                    # Primitive array mode - no sub-path
                    full_path = f"{base}[{row_index}]"
                else:
                    full_path = f"{base}[{row_index}].{col_name}"

                builder.set(full_path, value, mods if mods.has_any else None)
                assigned_paths.add(full_path)

            expect_value = False

        # Skip newline
        if pos < end and tokens[pos].type == TokenType.NEWLINE:
            pos += 1

        return pos
