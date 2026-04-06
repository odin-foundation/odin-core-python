"""Compute differences between two ODIN documents."""

from typing import List, Optional

from odin.types.document import OdinDocument, OdinModifiers
from odin.types.diff import OdinDiff, PathValue, PathChange, PathMove
from odin.types.values import (
    OdinValue, OdinNull, OdinBoolean, OdinString, OdinNumber, OdinInteger,
    OdinCurrency, OdinPercent, OdinDate, OdinTimestamp, OdinTime,
    OdinDuration, OdinReference, OdinBinary,
)


def compute_diff(a: OdinDocument, b: OdinDocument) -> OdinDiff:
    """Compare two documents and produce a diff.

    Detects additions, deletions, modifications, and moves.

    Args:
        a: Original document
        b: Modified document

    Returns:
        OdinDiff describing all changes from a to b
    """
    added: List[PathValue] = []
    removed: List[PathValue] = []
    changed: List[PathChange] = []
    moved: List[PathMove] = []

    a_assignments = a.assignments
    b_assignments = b.assignments
    a_paths = set(a.paths())
    b_paths = set(b.paths())

    # Find removed and changed
    for path in a.paths():
        a_val = a_assignments[path]
        if path not in b_paths:
            removed.append(PathValue(path, a_val))
        else:
            b_val = b_assignments[path]
            if not _values_equal(a_val, b_val) or not _modifiers_equal(
                a.modifiers.get(path), b.modifiers.get(path)
            ):
                changed.append(PathChange(path, a_val, b_val))

    # Find added
    for path in b.paths():
        if path not in a_paths:
            added.append(PathValue(path, b_assignments[path]))

    # Detect moves: removed value that appears as added value
    removed_to_remove: List[int] = []
    added_used: set = set()

    for ri, rem in enumerate(removed):
        for ai, add in enumerate(added):
            if ai in added_used:
                continue
            if _values_equal(rem.value, add.value):
                moved.append(PathMove(rem.path, add.path))
                removed_to_remove.append(ri)
                added_used.add(ai)
                break

    # Remove matched items (descending order to preserve indices)
    removed_to_remove.sort(reverse=True)
    for idx in removed_to_remove:
        _swap_remove(removed, idx)

    added_indices = sorted(added_used, reverse=True)
    for idx in added_indices:
        _swap_remove(added, idx)

    return OdinDiff(
        additions=added,
        deletions=removed,
        modifications=changed,
        moves=moved,
    )


def _values_equal(a: OdinValue, b: OdinValue) -> bool:
    """Check if two ODIN values are semantically equal."""
    if a is b:
        return True
    if type(a) is not type(b):
        return False

    # Since frozen dataclasses with __slots__ generate __eq__, just use it
    return a == b


def _modifiers_equal(
    a: Optional[OdinModifiers], b: Optional[OdinModifiers]
) -> bool:
    """Check if two modifier sets are equal."""
    a_req = a.required if a else False
    b_req = b.required if b else False
    a_conf = a.confidential if a else False
    b_conf = b.confidential if b else False
    a_dep = a.deprecated if a else False
    b_dep = b.deprecated if b else False
    return a_req == b_req and a_conf == b_conf and a_dep == b_dep


def _swap_remove(lst: list, index: int) -> None:
    """Remove element at index by swapping with last element (O(1))."""
    last = len(lst) - 1
    if index != last:
        lst[index] = lst[last]
    lst.pop()
