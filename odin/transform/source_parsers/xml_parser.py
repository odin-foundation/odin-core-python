"""XML source parser - converts XML string to DynValue tree."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from odin.transform.dyn_value import DynValue

MAX_DEPTH = 100


def parse_xml(source: str) -> DynValue:
    """Parse XML input to DynValue tree.

    Args:
        source: XML string

    Returns:
        DynValue object with root element as key

    Raises:
        ValueError: If input is invalid XML
    """
    if not source or not source.strip():
        raise ValueError("XML parse error: empty input")

    # Strip XML declaration
    text = re.sub(r'<\?xml[^?]*\?>\s*', '', source.strip())
    if not text:
        raise ValueError("XML parse error: no content after declaration")

    parser = _XmlParser(text)
    node = parser.parse_element()
    if node is None:
        raise ValueError("XML parse error: no root element found")

    value = _node_to_value(node, 0)
    return DynValue.of_object({node.name: value})


class _XmlNode:
    __slots__ = ("name", "attributes", "children", "text", "self_closing")

    def __init__(self, name: str):
        self.name = name
        self.attributes: List[Tuple[str, str]] = []
        self.children: List[_XmlNode] = []
        self.text: str = ""
        self.self_closing: bool = False


class _XmlParser:
    def __init__(self, text: str):
        self._text = text
        self._pos = 0

    def _remaining(self) -> str:
        return self._text[self._pos:]

    def _peek(self) -> str:
        if self._pos < len(self._text):
            return self._text[self._pos]
        return ""

    def _advance(self, n: int = 1) -> str:
        result = self._text[self._pos:self._pos + n]
        self._pos += n
        return result

    def _skip_whitespace(self):
        while self._pos < len(self._text) and self._text[self._pos] in " \t\r\n":
            self._pos += 1

    def _starts_with(self, s: str) -> bool:
        return self._text[self._pos:self._pos + len(s)] == s

    def parse_element(self) -> Optional[_XmlNode]:
        self._skip_whitespace()
        # Skip comments
        while self._starts_with("<!--"):
            end = self._text.find("-->", self._pos)
            if end == -1:
                self._pos = len(self._text)
                return None
            self._pos = end + 3
            self._skip_whitespace()

        if self._pos >= len(self._text) or self._peek() != '<':
            return None

        self._advance()  # skip <

        if self._peek() == '/':
            return None  # closing tag

        # Read tag name
        name = self._read_name()
        if not name:
            raise ValueError("XML parse error: expected element name")

        # Preserve namespace prefix in element name for namespace-aware transforms
        node = _XmlNode(name)

        # Read attributes
        while True:
            self._skip_whitespace()
            if self._pos >= len(self._text):
                raise ValueError("XML parse error: unterminated element")
            if self._peek() == '/' and self._pos + 1 < len(self._text) and self._text[self._pos + 1] == '>':
                self._advance(2)  # />
                node.self_closing = True
                return node
            if self._peek() == '>':
                self._advance()
                break
            # Read attribute
            attr_name = self._read_name()
            if not attr_name:
                self._advance()  # skip unknown char
                continue
            self._skip_whitespace()
            if self._peek() == '=':
                self._advance()
                self._skip_whitespace()
                attr_value = self._read_attr_value()
            else:
                attr_value = ""
            # Skip xmlns declarations
            if attr_name.startswith("xmlns"):
                continue
            # Strip namespace prefix from attribute name
            if ':' in attr_name:
                attr_prefix, attr_local = attr_name.split(':', 1)
                if attr_prefix == "xmlns":
                    continue
                attr_name = f"{attr_prefix}:{attr_local}"
            node.attributes.append((attr_name, attr_value))

        # Read children and text content
        text_parts: List[str] = []
        found_closing = False
        while self._pos < len(self._text):
            if self._starts_with("</"):
                # Closing tag
                self._pos += 2
                closing_name = self._read_name()
                # Skip to >
                while self._pos < len(self._text) and self._peek() != '>':
                    self._advance()
                if self._pos < len(self._text):
                    self._advance()  # >
                found_closing = True
                break

            if self._starts_with("<!--"):
                # Comment
                end = self._text.find("-->", self._pos)
                if end == -1:
                    self._pos = len(self._text)
                else:
                    self._pos = end + 3
                continue

            if self._starts_with("<![CDATA["):
                # CDATA
                self._pos += 9
                end = self._text.find("]]>", self._pos)
                if end == -1:
                    text_parts.append(self._text[self._pos:])
                    self._pos = len(self._text)
                else:
                    text_parts.append(self._text[self._pos:end])
                    self._pos = end + 3
                continue

            if self._peek() == '<' and not self._starts_with("</"):
                child = self.parse_element()
                if child:
                    node.children.append(child)
                continue

            # Text content
            start = self._pos
            while self._pos < len(self._text) and self._peek() != '<':
                self._advance()
            if self._pos > start:
                text_parts.append(self._text[start:self._pos])

        if not found_closing:
            raise ValueError(f"XML parse error: unclosed element <{name}>")

        if text_parts:
            node.text = _decode_entities("".join(text_parts))

        return node

    def _read_name(self) -> str:
        start = self._pos
        while self._pos < len(self._text):
            ch = self._text[self._pos]
            if ch.isalnum() or ch in '-_.:':
                self._pos += 1
            else:
                break
        return self._text[start:self._pos]

    def _read_attr_value(self) -> str:
        if self._peek() in ('"', "'"):
            quote = self._advance()
            start = self._pos
            while self._pos < len(self._text) and self._peek() != quote:
                self._advance()
            value = self._text[start:self._pos]
            if self._pos < len(self._text):
                self._advance()  # closing quote
            return _decode_entities(value)
        # Unquoted
        start = self._pos
        while self._pos < len(self._text) and self._peek() not in ' \t\r\n/>':
            self._advance()
        return self._text[start:self._pos]


def _decode_entities(text: str) -> str:
    """Decode XML entities."""
    result = text
    result = result.replace("&amp;", "&")
    result = result.replace("&lt;", "<")
    result = result.replace("&gt;", ">")
    result = result.replace("&quot;", '"')
    result = result.replace("&apos;", "'")
    # Numeric entities
    result = re.sub(r'&#x([0-9a-fA-F]+);', lambda m: chr(int(m.group(1), 16)), result)
    result = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), result)
    return result


def _node_to_value(node: _XmlNode, depth: int) -> DynValue:
    """Convert an XML node to a DynValue."""
    if depth > MAX_DEPTH:
        raise ValueError(f"XML parse error: nesting depth exceeds {MAX_DEPTH}")

    # Check xsi:nil
    for attr_name, attr_value in node.attributes:
        if attr_name == "xsi:nil" and attr_value.lower() == "true":
            return DynValue.of_null()

    # Filter out nil/nillable attributes
    attrs = [(n, v) for n, v in node.attributes
             if n not in ("xsi:nil", "xsi:nillable")]

    # Self-closing with no attributes: null
    if node.self_closing and not attrs:
        return DynValue.of_null()

    # Leaf node: no children, no attributes
    if not node.children and not attrs:
        return DynValue.of_string(node.text)

    # Has children or attributes: build object
    obj: Dict[str, DynValue] = {}

    # Add attributes with @ prefix
    for attr_name, attr_value in attrs:
        obj[f"@{attr_name}"] = DynValue.of_string(attr_value)

    # Add text if mixed with children
    if node.text and node.text.strip() and node.children:
        obj["_text"] = DynValue.of_string(node.text.strip())
    elif node.text and node.text.strip() and attrs and not node.children:
        obj["_text"] = DynValue.of_string(node.text.strip())

    # Group children by name
    child_groups: Dict[str, List[_XmlNode]] = {}
    for child in node.children:
        child_groups.setdefault(child.name, []).append(child)

    for child_name, children in child_groups.items():
        if len(children) == 1 and child_name != "item":
            obj[child_name] = _node_to_value(children[0], depth + 1)
        else:
            obj[child_name] = DynValue.of_array(
                [_node_to_value(c, depth + 1) for c in children]
            )

    return DynValue.of_object(obj)
