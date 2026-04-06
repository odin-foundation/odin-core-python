"""YAML source parser - converts YAML string to DynValue tree."""

from __future__ import annotations

from typing import List, Optional, Tuple

from odin.transform.dyn_value import DynValue


def parse_yaml(source: str) -> DynValue:
    """Parse YAML input to DynValue tree.

    Supports basic YAML:
        - Key-value mappings
        - Nested objects via indentation
        - Arrays with - prefix
        - Comments with #
        - Basic type inference

    Args:
        source: YAML string

    Returns:
        DynValue object
    """
    if not source.strip():
        return DynValue.of_object({})

    lines = _preprocess(source)
    if not lines:
        return DynValue.of_object({})

    result, _ = _parse_block(lines, 0, 0)
    return result


class _YamlLine:
    __slots__ = ("indent", "content")

    def __init__(self, indent: int, content: str):
        self.indent = indent
        self.content = content


def _preprocess(source: str) -> List[_YamlLine]:
    """Preprocess YAML: strip comments, empty lines, calc indent."""
    result: List[_YamlLine] = []
    for raw_line in source.split('\n'):
        line = raw_line.rstrip('\r').rstrip()

        # Strip inline comments (respect quotes)
        stripped = _strip_comment(line)
        content = stripped.rstrip()

        if not content.strip():
            continue

        indent = len(content) - len(content.lstrip())
        result.append(_YamlLine(indent, content.strip()))

    return result


def _strip_comment(line: str) -> str:
    """Strip inline comments, respecting quoted strings."""
    in_single = False
    in_double = False
    for i, ch in enumerate(line):
        if in_single:
            if ch == "'":
                in_single = False
            continue
        if in_double:
            if ch == '"':
                in_double = False
            continue
        if ch == "'":
            in_single = True
        elif ch == '"':
            in_double = True
        elif ch == '#':
            # Check if preceded by whitespace or at start
            if i == 0 or line[i - 1] in (' ', '\t'):
                return line[:i]
    return line


def _parse_block(
    lines: List[_YamlLine], start: int, base_indent: int
) -> Tuple[DynValue, int]:
    """Parse a block (mapping or array) at the given indent level."""
    if start >= len(lines):
        return DynValue.of_object({}), start

    first = lines[start]
    if first.content.startswith('- ') or first.content == '-':
        return _parse_array(lines, start, base_indent)
    else:
        return _parse_mapping(lines, start, base_indent)


def _parse_mapping(
    lines: List[_YamlLine], start: int, base_indent: int
) -> Tuple[DynValue, int]:
    """Parse a YAML mapping."""
    obj = {}
    pos = start

    while pos < len(lines):
        line = lines[pos]
        if line.indent < base_indent:
            break

        colon_pos = _find_colon(line.content)
        if colon_pos < 0:
            pos += 1
            continue

        key = line.content[:colon_pos].strip()
        rest = line.content[colon_pos + 1:].strip()

        if rest:
            obj[key] = _parse_scalar(rest)
            pos += 1
        else:
            # Value on next line(s) at increased indent
            pos += 1
            if pos < len(lines) and lines[pos].indent > base_indent:
                child_indent = lines[pos].indent
                value, pos = _parse_block(lines, pos, child_indent)
                obj[key] = value
            else:
                obj[key] = DynValue.of_null()

    return DynValue.of_object(obj), pos


def _parse_array(
    lines: List[_YamlLine], start: int, base_indent: int
) -> Tuple[DynValue, int]:
    """Parse a YAML array."""
    items: List[DynValue] = []
    pos = start

    while pos < len(lines):
        line = lines[pos]
        if line.indent < base_indent:
            break

        content = line.content
        if not (content.startswith('- ') or content == '-'):
            break

        after_dash = content[2:].strip() if len(content) > 2 else ""

        if not after_dash:
            # Empty dash - check for nested content
            pos += 1
            if pos < len(lines) and lines[pos].indent > base_indent:
                child_indent = lines[pos].indent
                value, pos = _parse_block(lines, pos, child_indent)
                items.append(value)
            else:
                items.append(DynValue.of_null())
            continue

        # Check if dash line has key: value
        colon_pos = _find_colon(after_dash)
        if colon_pos >= 0:
            # Object item
            key = after_dash[:colon_pos].strip()
            rest = after_dash[colon_pos + 1:].strip()

            obj = {}
            if rest:
                obj[key] = _parse_scalar(rest)
            else:
                obj[key] = DynValue.of_null()

            pos += 1
            # Continuation lines at indent >= base + 2
            while pos < len(lines) and lines[pos].indent >= base_indent + 2:
                cline = lines[pos]
                if cline.content.startswith('- '):
                    break
                cc = _find_colon(cline.content)
                if cc >= 0:
                    ck = cline.content[:cc].strip()
                    cv = cline.content[cc + 1:].strip()
                    if cv:
                        obj[ck] = _parse_scalar(cv)
                    else:
                        pos += 1
                        if pos < len(lines) and lines[pos].indent > cline.indent:
                            child_indent = lines[pos].indent
                            value, pos = _parse_block(lines, pos, child_indent)
                            obj[ck] = value
                        else:
                            obj[ck] = DynValue.of_null()
                        continue
                pos += 1

            items.append(DynValue.of_object(obj))
        else:
            # Simple value
            items.append(_parse_scalar(after_dash))
            pos += 1

    return DynValue.of_array(items), pos


def _find_colon(text: str) -> int:
    """Find the first colon separator (not in URL or quotes)."""
    in_single = False
    in_double = False
    for i, ch in enumerate(text):
        if in_single:
            if ch == "'":
                in_single = False
            continue
        if in_double:
            if ch == '"':
                in_double = False
            continue
        if ch == "'":
            in_single = True
        elif ch == '"':
            in_double = True
        elif ch == ':':
            # Valid colon: followed by space/tab or at end
            if i + 1 >= len(text) or text[i + 1] in (' ', '\t'):
                return i
    return -1


def _parse_scalar(text: str) -> DynValue:
    """Parse a YAML scalar value."""
    if not text:
        return DynValue.of_null()

    # Quoted strings
    if (text.startswith('"') and text.endswith('"')) or \
       (text.startswith("'") and text.endswith("'")):
        return DynValue.of_string(text[1:-1])

    lower = text.lower()

    # Null
    if lower in ('null', '~'):
        return DynValue.of_null()

    # Boolean
    if lower in ('true', 'yes', 'on'):
        return DynValue.of_bool(True)
    if lower in ('false', 'no', 'off'):
        return DynValue.of_bool(False)

    # Integer
    try:
        return DynValue.of_integer(int(text))
    except ValueError:
        pass

    # Float
    if '.' in text or 'e' in text.lower():
        try:
            return DynValue.of_float(float(text))
        except ValueError:
            pass

    return DynValue.of_string(text)
