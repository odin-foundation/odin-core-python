"""Serialize ODIN documents to text format."""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

# Pre-compiled regex for tabular column sort
_TABULAR_COL_RE = re.compile(r'^([^\[]+)\[(\d+)\]$')

from odin.types.document import OdinDocument, OdinModifiers
from odin.types.options import DumpOptions
from odin.types.values import OdinValue, OdinArray, OdinObject
from odin.utils.format_utils import (
    format_modifier_prefix, format_value, has_any_modifier, is_primitive_value,
)

# Maximum array index for safety
MAX_ARRAY_INDEX = 10_000


def stringify(doc: OdinDocument, options: Optional[DumpOptions] = None) -> str:
    """Convert an ODIN document to text format."""
    opts = _resolve_options(options)

    # Fast path for shallow documents
    if opts.use_headers and not opts.sort_paths and _is_shallow(doc):
        return _stringify_flat(doc, opts)

    lines: List[str] = []

    # Separate metadata and data paths — use internal dicts directly
    _assignments = doc._assignments
    _metadata = doc._metadata

    meta_paths: List[str] = []
    data_paths: List[str] = []
    for key in _assignments:
        if len(key) > 1 and key[0] == '$' and key[1] == '.':
            meta_paths.append(key)
        else:
            data_paths.append(key)
    # Also add from metadata map
    for key in _metadata:
        p = '$.' + key
        if p not in meta_paths:
            meta_paths.append(p)

    if opts.sort_paths:
        meta_paths = sorted(meta_paths)

    if meta_paths:
        if opts.use_headers:
            lines.append('{$}')
        for path in meta_paths:
            val = doc.get(path)
            if val is None:
                # Try metadata map
                key = path[2:]
                val = doc.metadata.get(key)
            if val is not None:
                display = path[2:] if opts.use_headers else path
                lines.append(_format_assignment(display, val, doc.modifiers.get(path)))
        if opts.use_headers and data_paths:
            lines.append('{}')

    if opts.use_headers or opts.use_tabular:
        _output_hierarchical(doc, data_paths, opts, lines)
    else:
        sorted_data = sorted(data_paths) if opts.sort_paths else data_paths
        for path in sorted_data:
            val = doc.get(path)
            if val is not None:
                lines.append(_format_assignment(path, val, doc.modifiers.get(path)))

    le = opts.line_ending
    return le.join(lines) + (le if lines else '')


class _ResolvedOptions:
    """Resolved stringify options with defaults."""
    __slots__ = ('sort_paths', 'use_headers', 'use_tabular', 'include_comments', 'line_ending')

    def __init__(self, opts: Optional[DumpOptions]):
        if opts is None:
            self.sort_paths = False
            self.use_headers = True
            self.use_tabular = True
            self.include_comments = True
            self.line_ending = '\n'
        else:
            self.sort_paths = opts.sort_paths
            self.use_headers = getattr(opts, 'use_headers', True)
            self.use_tabular = getattr(opts, 'use_tabular', True)
            self.include_comments = opts.include_comments
            from odin.types.options import LineEnding
            self.line_ending = '\r\n' if opts.line_ending == LineEnding.CRLF else '\n'


def _resolve_options(options: Optional[DumpOptions]) -> _ResolvedOptions:
    return _ResolvedOptions(options)


def _is_shallow(doc: OdinDocument) -> bool:
    """Check if document is shallow (no arrays, max 1 dot)."""
    for key in doc.assignments:
        if '[' in key:
            return False
        first_dot = key.find('.')
        if first_dot >= 0 and key.find('.', first_dot + 1) >= 0:
            return False
    return True


def _stringify_flat(doc: OdinDocument, opts: _ResolvedOptions) -> str:
    """Fast flat stringify for shallow documents."""
    lines: List[str] = []
    le = opts.line_ending

    has_metadata = len(doc.metadata) > 0
    if has_metadata:
        lines.append('{$}')
        for key, value in doc.metadata.items():
            lines.append(_format_assignment(key, value, None))

    # Check for data assignments
    has_data = False
    for key in doc.assignments:
        if not (len(key) > 1 and key[0] == '$' and key[1] == '.'):
            has_data = True
            break

    if has_metadata and has_data:
        lines.append('{}')

    current_section: Optional[str] = None
    first_section = True

    for path, value in doc.assignments.items():
        if len(path) > 1 and path[0] == '$' and path[1] == '.':
            continue

        dot_pos = path.find('.')
        if dot_pos > 0:
            section = path[:dot_pos]
            field = path[dot_pos + 1:]
        else:
            section = None
            field = path

        if section != current_section:
            if section is not None:
                lines.append(f'{{{section}}}')
            current_section = section

        mods = doc.modifiers.get(path)
        lines.append(_format_assignment(field, value, mods))

    return le.join(lines) + (le if lines else '')


# ─── Path Tree ───

class _PathNode:
    """Node in the path hierarchy tree."""
    __slots__ = ('name', 'full_path', 'value', 'modifiers', 'children', 'is_array', 'array_indices')

    def __init__(self, name: str, full_path: str) -> None:
        self.name = name
        self.full_path = full_path
        self.value: Optional[OdinValue] = None
        self.modifiers: Optional[OdinModifiers] = None
        self.children: Dict[str, _PathNode] = {}
        self.is_array = name.startswith('[')
        self.array_indices: List[int] = []


def _parse_path_segments(path: str) -> List[str]:
    """Parse a path into segments, array indices as separate segments."""
    segments: List[str] = []
    path_len = len(path)
    i = 0
    start = 0
    while i < path_len:
        ch = path[i]
        if ch == '.':
            if i > start:
                segments.append(path[start:i])
            start = i + 1
            i += 1
        elif ch == '[':
            if i > start:
                segments.append(path[start:i])
            close = path.find(']', i)
            if close < 0:
                close = path_len
            segments.append(path[i:close + 1])
            start = close + 1
            i = start
        else:
            i += 1
    if start < path_len:
        segments.append(path[start:])
    return segments


def _build_path_tree(doc: OdinDocument, paths: List[str]) -> _PathNode:
    """Build a hierarchical tree from flat paths.

    Inlines segment parsing to avoid intermediate list allocation.
    """
    root = _PathNode('', '')
    # Direct dict access (skip MappingProxy)
    assignments = doc._assignments
    modifiers_dict = doc._modifiers

    for path in paths:
        current = root
        path_len = len(path)
        i = 0
        start = 0
        full_path = ''

        while True:
            # Find next segment boundary
            seg = None
            if i >= path_len:
                break

            if path[i] == '[':
                if i > start:
                    # Emit identifier segment before bracket
                    seg = path[start:i]
                    is_bracket = False
                    # Don't advance i — process bracket next iteration
                    start = i
                else:
                    close = path.find(']', i)
                    if close < 0:
                        close = path_len - 1
                    seg = path[i:close + 1]
                    is_bracket = True
                    i = close + 1
                    start = i
            else:
                # Scan to next . or [
                while i < path_len and path[i] != '.' and path[i] != '[':
                    i += 1
                seg = path[start:i]
                is_bracket = False
                if i < path_len and path[i] == '.':
                    i += 1
                start = i

            if not seg:
                continue

            # Build full_path incrementally
            if is_bracket:
                full_path = full_path + seg
            elif full_path:
                full_path = full_path + '.' + seg
            else:
                full_path = seg

            children = current.children
            node = children.get(seg)
            if node is None:
                node = _PathNode(seg, full_path)
                children[seg] = node

            # Track array indices
            if is_bracket:
                idx_str = seg[1:-1]
                if idx_str.isdigit():
                    idx = int(idx_str)
                    arr = current.array_indices
                    if not arr or arr[-1] != idx:
                        arr.append(idx)

            current = node

        # Set value/modifiers on the final node
        val = assignments.get(path)
        if val is not None:
            current.value = val
        mods = modifiers_dict.get(path)
        if mods is not None:
            current.modifiers = mods

    return root


def _node_has_array_children(node: _PathNode) -> bool:
    """Check if any child key starts with '['."""
    for key in node.children:
        if key[0] == '[':
            return True
    return False


def _has_multiple_leaf_descendants(node: _PathNode) -> bool:
    """Check if a node has multiple leaf descendants. Iterative to avoid closure overhead."""
    count = 0
    stack = [node]
    while stack:
        n = stack.pop()
        if n.value is not None:
            count += 1
            if count > 1:
                return True
        else:
            for child in n.children.values():
                stack.append(child)
    return False


def _output_hierarchical(
    doc: OdinDocument,
    data_paths: List[str],
    opts: _ResolvedOptions,
    lines: List[str],
) -> None:
    """Output paths hierarchically with headers and tabular arrays."""
    tree = _build_path_tree(doc, data_paths)

    child_names = list(tree.children.keys())
    if opts.sort_paths:
        child_names.sort()

    scalars: List[str] = []
    groups: List[str] = []

    for name in child_names:
        child = tree.children[name]
        if child.value is not None:
            scalars.append(name)
        else:
            groups.append(name)

    # Output root-level scalars
    for name in scalars:
        child = tree.children[name]
        lines.append(_format_assignment(child.full_path, child.value, child.modifiers))

    # Classify groups
    single_leaf: List[str] = []
    header_groups: List[str] = []

    for name in groups:
        child = tree.children[name]
        has_arr = _node_has_array_children(child)
        if has_arr or (opts.use_headers and _has_multiple_leaf_descendants(child)):
            header_groups.append(name)
        else:
            single_leaf.append(name)

    for name in single_leaf:
        child = tree.children[name]
        _output_node(doc, child, '', opts, lines)

    for name in header_groups:
        child = tree.children[name]
        has_array_children = _node_has_array_children(child)

        if has_array_children and opts.use_tabular and child.array_indices:
            if _try_output_tabular(doc, child, '', opts, lines):
                continue

        if has_array_children:
            _output_node(doc, child, '', opts, lines)
        elif opts.use_headers and _has_multiple_leaf_descendants(child):
            lines.append(f'{{{child.full_path}}}')
            _output_node(doc, child, child.full_path, opts, lines)
        else:
            _output_node(doc, child, '', opts, lines)


def _output_node(
    doc: OdinDocument,
    node: _PathNode,
    header_path: str,
    opts: _ResolvedOptions,
    lines: List[str],
    inside_relative_header: bool = False,
) -> None:
    """Recursively output a node and its descendants."""
    if node.value is not None:
        rel_path = node.full_path[len(header_path) + 1:] if header_path else node.full_path
        lines.append(_format_assignment(rel_path, node.value, node.modifiers))
        return

    if not node.children:
        return

    child_names: List[str]
    if opts.sort_paths:
        child_names = sorted(node.children.keys(), key=lambda k: _child_sort_key(k))
    else:
        child_names = list(node.children.keys())

    array_children: List[str] = []
    regular_children: List[str] = []
    subheader_children: List[str] = []

    for name in child_names:
        child = node.children[name]
        if name[0] == '[':
            array_children.append(name)
            continue

        child_has_arr = _node_has_array_children(child)
        should_subheader = (
            opts.use_headers
            and child.value is None
            and not child_has_arr
            and _has_multiple_leaf_descendants(child)
        )
        if should_subheader:
            subheader_children.append(name)
        else:
            regular_children.append(name)

    for name in regular_children:
        _output_node(doc, node.children[name], header_path, opts, lines)

    if array_children:
        if opts.use_tabular and node.array_indices:
            if _try_output_tabular(doc, node, header_path, opts, lines):
                pass  # tabular succeeded
            else:
                for name in array_children:
                    child = node.children[name]
                    if opts.use_headers and _has_multiple_leaf_descendants(child):
                        lines.append(f'{{{child.full_path}}}')
                        _output_node(doc, child, child.full_path, opts, lines)
                    else:
                        _output_node(doc, child, header_path, opts, lines)
        else:
            for name in array_children:
                child = node.children[name]
                if opts.use_headers and _has_multiple_leaf_descendants(child):
                    lines.append(f'{{{child.full_path}}}')
                    _output_node(doc, child, child.full_path, opts, lines)
                else:
                    _output_node(doc, child, header_path, opts, lines)

    for name in subheader_children:
        child = node.children[name]
        is_direct = (
            header_path
            and child.full_path.startswith(header_path + '.')
            and '.' not in child.full_path[len(header_path) + 1:]
        )
        can_use_relative = is_direct and not inside_relative_header

        if can_use_relative:
            rel_name = child.full_path[len(header_path) + 1:]
            lines.append(f'{{.{rel_name}}}')
            _output_node(doc, child, child.full_path, opts, lines, True)
        else:
            lines.append(f'{{{child.full_path}}}')
            _output_node(doc, child, child.full_path, opts, lines, False)


def _child_sort_key(key: str):
    """Sort key: array indices numerically, others lexicographically."""
    if key.startswith('[') and key.endswith(']'):
        try:
            return (1, int(key[1:-1]), '')
        except ValueError:
            return (1, MAX_ARRAY_INDEX, key)
    return (0, 0, key)


# ─── Tabular Output ───

def _try_output_tabular(
    doc: OdinDocument,
    node: _PathNode,
    current_header: str,
    opts: _ResolvedOptions,
    lines: List[str],
) -> bool:
    """Try to output array as tabular. Returns True if successful."""
    if _is_primitive_array_node(node):
        return _try_output_primitive_tabular(node, current_header, lines)

    items: Dict[int, Dict[str, Tuple[OdinValue, Optional[OdinModifiers]]]] = {}
    all_columns: List[str] = []  # Use list to preserve order
    all_columns_set: Set[str] = set()

    for child_name, child in node.children.items():
        if not child_name.startswith('[') or not child_name.endswith(']'):
            continue
        idx_str = child_name[1:-1]
        if not idx_str.isdigit():
            continue
        index = int(idx_str)
        if index > MAX_ARRAY_INDEX:
            index = MAX_ARRAY_INDEX

        fields: Dict[str, Tuple[OdinValue, Optional[OdinModifiers]]] = {}
        if not _collect_tabular_fields(child, '', fields):
            return False
        if not fields:
            return False

        for col in fields:
            if col not in all_columns_set:
                all_columns.append(col)
                all_columns_set.add(col)
        items[index] = fields

    if not items:
        return False

    indices = sorted(items.keys())
    for i, idx in enumerate(indices):
        if idx != i:
            return False

    columns = list(all_columns)
    if opts.sort_paths:
        columns.sort(key=_tabular_column_sort_key)

    if current_header:
        header_path = '.' + node.full_path[len(current_header) + 1:] + '[]'
    else:
        header_path = node.full_path + '[]'

    formatted_cols = _format_columns_with_relative(columns)
    lines.append(f'{{{header_path} : {formatted_cols}}}')

    for i in range(len(indices)):
        fields = items[i]
        values: List[str] = []
        for col in columns:
            if col in fields:
                values.append(format_value(fields[col][0]))
            else:
                values.append('')
        lines.append(', '.join(values))

    return True


def _collect_tabular_fields(
    node: _PathNode,
    prefix: str,
    fields: Dict[str, Tuple[OdinValue, Optional[OdinModifiers]]],
) -> bool:
    """Collect fields from node for tabular. Returns False if not eligible."""
    for field_name, field_node in node.children.items():
        col_name = f'{prefix}.{field_name}' if prefix else field_name

        if field_node.value is not None:
            if not is_primitive_value(field_node.value):
                return False
            if has_any_modifier(field_node.modifiers):
                return False
            fields[col_name] = (field_node.value, field_node.modifiers)
            continue

        if prefix:
            return False

        child_keys = list(field_node.children.keys())
        has_arr = any(k.startswith('[') for k in child_keys)

        if has_arr:
            for ck, cn in field_node.children.items():
                if not ck.startswith('['):
                    return False
                if cn.value is None or cn.children:
                    return False
                if not is_primitive_value(cn.value):
                    return False
                if has_any_modifier(cn.modifiers):
                    return False
                arr_col = f'{field_name}{ck}'
                fields[arr_col] = (cn.value, cn.modifiers)
        else:
            for ck, cn in field_node.children.items():
                if cn.value is None or cn.children:
                    return False
                if not is_primitive_value(cn.value):
                    return False
                if has_any_modifier(cn.modifiers):
                    return False
                dot_col = f'{field_name}.{ck}'
                fields[dot_col] = (cn.value, cn.modifiers)

    return True


def _is_primitive_array_node(node: _PathNode) -> bool:
    """Check if all array items are direct primitive values."""
    has_items = False
    for name, child in node.children.items():
        if not name.startswith('['):
            continue
        has_items = True
        if child.value is None or child.children:
            return False
        if not is_primitive_value(child.value):
            return False
        if has_any_modifier(child.modifiers):
            return False
    return has_items


def _try_output_primitive_tabular(
    node: _PathNode,
    current_header: str,
    lines: List[str],
) -> bool:
    """Output a primitive array as {path[] : ~} format."""
    items: Dict[int, Tuple[OdinValue, Optional[OdinModifiers]]] = {}

    for name, child in node.children.items():
        if not name.startswith('[') or not name.endswith(']'):
            continue
        idx_str = name[1:-1]
        if not idx_str.isdigit():
            continue
        index = int(idx_str)
        if child.value is None:
            return False
        items[index] = (child.value, child.modifiers)

    if not items:
        return False

    indices = sorted(items.keys())
    for i, idx in enumerate(indices):
        if idx != i:
            return False

    if current_header:
        header_path = '.' + node.full_path[len(current_header) + 1:] + '[]'
    else:
        header_path = node.full_path + '[]'

    lines.append(f'{{{header_path} : ~}}')

    for i in range(len(indices)):
        lines.append(format_value(items[i][0]))

    return True


def _format_columns_with_relative(columns: List[str]) -> str:
    """Format column names, using relative syntax for consecutive same-parent columns."""
    if not columns:
        return ''

    result: List[str] = []
    current_parent = ''

    for col in columns:
        dot_idx = col.find('.')
        if dot_idx > 0:
            parent = col[:dot_idx]
            field = col[dot_idx + 1:]
            if parent == current_parent:
                result.append('.' + field)
            else:
                result.append(col)
                current_parent = parent
        else:
            result.append(col)
            current_parent = ''

    return ', '.join(result)


def _tabular_column_sort_key(col: str):
    """Sort key for tabular columns."""
    has_dot = '.' in col
    has_arr = '[' in col

    if not has_dot and not has_arr:
        return (0, '', 0, col)
    if has_dot and not has_arr:
        return (1, col, 0, col)
    if has_arr:
        m = _TABULAR_COL_RE.match(col)
        if m:
            return (2, m.group(1), int(m.group(2)), col)
        return (2, col, 0, col)
    return (3, col, 0, col)


# ─── Formatting ───

def _format_assignment(
    path: str,
    value: OdinValue,
    modifiers: Optional[OdinModifiers] = None,
) -> str:
    """Format a single assignment line."""
    return f'{path} = {format_modifier_prefix(modifiers)}{format_value(value)}'
