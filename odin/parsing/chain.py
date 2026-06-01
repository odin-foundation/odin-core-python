"""Chain overlay - collapse chained ODIN documents into current state."""
from __future__ import annotations

from collections import OrderedDict
from typing import Dict, List

from odin.types.document import OdinDocument, OdinModifiers
from odin.types.values import OdinNull, OdinValue


def collapse_chain(docs: List[OdinDocument]) -> OdinDocument:
    """Compute the current-state document from a chain via overlay semantics.

    Later documents overlay earlier ones; a repeated path replaces the earlier
    value; ``field = ~`` removes the field and its descendants; ``field[] = ~``
    clears the array. The result carries the final document's metadata.
    """
    assignments: OrderedDict[str, OdinValue] = OrderedDict()
    modifiers: Dict[str, OdinModifiers] = {}
    metadata: OrderedDict[str, OdinValue] = OrderedDict()

    for doc in docs:
        metadata = OrderedDict(doc.metadata)

        for path in doc.paths():
            if path.startswith("$."):
                continue

            value = doc.get(path)
            if value is None:
                continue

            if isinstance(value, OdinNull):
                if path.endswith("[]"):
                    _clear_array(assignments, modifiers, path[:-2])
                else:
                    _remove_path(assignments, modifiers, path)
                continue

            assignments[path] = value
            mods = doc.modifiers.get(path)
            if mods is not None:
                modifiers[path] = mods
            else:
                modifiers.pop(path, None)

    return OdinDocument(
        assignments=assignments,
        metadata=metadata,
        modifiers=modifiers,
        comments={},
    )


def _remove_path(
    assignments: OrderedDict[str, OdinValue],
    modifiers: Dict[str, OdinModifiers],
    path: str,
) -> None:
    """Remove a path and any nested descendants from the working maps."""
    for key in list(assignments.keys()):
        if key == path or key.startswith(f"{path}.") or key.startswith(f"{path}["):
            del assignments[key]
            modifiers.pop(key, None)


def _clear_array(
    assignments: OrderedDict[str, OdinValue],
    modifiers: Dict[str, OdinModifiers],
    array_path: str,
) -> None:
    """Clear all indexed elements of an array path from the working maps."""
    prefix = f"{array_path}["
    for key in list(assignments.keys()):
        if key.startswith(prefix):
            del assignments[key]
            modifiers.pop(key, None)
