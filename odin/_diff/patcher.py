"""Apply diffs to ODIN documents."""

from collections import OrderedDict

from odin.types.document import OdinDocument
from odin.types.diff import OdinDiff
from odin.types.errors import PatchError


def apply_patch(doc: OdinDocument, diff: OdinDiff) -> OdinDocument:
    """Apply a diff to a document, producing a new document.

    Args:
        doc: Document to patch
        diff: Diff to apply

    Returns:
        New document with diff applied

    Raises:
        PatchError: If diff references non-existent paths
    """
    # If diff is empty, return a clone
    if diff.is_empty:
        return OdinDocument(
            assignments=OrderedDict(doc.assignments),
            metadata=OrderedDict(doc.metadata),
            modifiers=dict(doc.modifiers),
            comments=dict(doc.comments),
        )

    # Clone assignments for mutation
    assignments = OrderedDict(doc.assignments)

    # 1. Apply removals
    for entry in diff.deletions:
        if entry.path not in assignments:
            raise PatchError(
                f"Cannot remove non-existent path: {entry.path}", entry.path
            )
        del assignments[entry.path]

    # 2. Apply changes
    for change in diff.modifications:
        if change.path not in assignments:
            raise PatchError(
                f"Cannot change non-existent path: {change.path}", change.path
            )
        assignments[change.path] = change.new_value

    # 3. Apply additions
    for entry in diff.additions:
        assignments[entry.path] = entry.value

    # 4. Apply moves
    for move in diff.moves:
        if move.from_path not in assignments:
            raise PatchError(
                f"Cannot move from non-existent path: {move.from_path}",
                move.from_path,
            )
        val = assignments[move.from_path]
        del assignments[move.from_path]
        assignments[move.to_path] = val

    return OdinDocument(
        assignments=assignments,
        metadata=OrderedDict(doc.metadata),
        modifiers=dict(doc.modifiers),
        comments=dict(doc.comments),
    )
