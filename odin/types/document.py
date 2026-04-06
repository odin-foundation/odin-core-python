"""Document types for ODIN."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from types import MappingProxyType
from typing import Dict, List, Mapping, Optional

from odin.types.values import OdinValue


@dataclass(frozen=True, slots=True)
class OdinModifiers:
    """Modifiers that can be applied to a value."""
    required: bool = False
    confidential: bool = False
    deprecated: bool = False
    attr: Optional[str] = None

    @property
    def has_any(self) -> bool:
        """Whether any modifier is set."""
        return self.required or self.confidential or self.deprecated


class OdinDocument:
    """Immutable ODIN document."""

    __slots__ = (
        "_assignments", "_metadata", "_modifiers", "_comments",
        "_assignments_proxy", "_metadata_proxy", "_modifiers_proxy", "_comments_proxy",
    )

    def __init__(
        self,
        assignments: OrderedDict[str, OdinValue],
        metadata: OrderedDict[str, OdinValue],
        modifiers: Dict[str, OdinModifiers],
        comments: Dict[str, str],
    ) -> None:
        object.__setattr__(self, "_assignments", assignments)
        object.__setattr__(self, "_metadata", metadata)
        object.__setattr__(self, "_modifiers", modifiers)
        object.__setattr__(self, "_comments", comments)
        # Cache proxies to avoid re-creation on every property access
        object.__setattr__(self, "_assignments_proxy", MappingProxyType(assignments))
        object.__setattr__(self, "_metadata_proxy", MappingProxyType(metadata))
        object.__setattr__(self, "_modifiers_proxy", MappingProxyType(modifiers))
        object.__setattr__(self, "_comments_proxy", MappingProxyType(comments))

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("OdinDocument is immutable")

    def get(self, path: str) -> Optional[OdinValue]:
        """Get value at path, or None if not found."""
        return self._assignments.get(path)

    def paths(self) -> List[str]:
        """List all assignment paths in insertion order."""
        return list(self._assignments.keys())

    def __contains__(self, path: object) -> bool:
        return path in self._assignments

    def __len__(self) -> int:
        return len(self._assignments)

    @property
    def assignments(self) -> Mapping[str, OdinValue]:
        """Read-only view of path -> value assignments."""
        return self._assignments_proxy

    @property
    def metadata(self) -> Mapping[str, OdinValue]:
        """Read-only view of metadata key -> value."""
        return self._metadata_proxy

    @property
    def modifiers(self) -> Mapping[str, OdinModifiers]:
        """Read-only view of path -> modifiers."""
        return self._modifiers_proxy

    @property
    def comments(self) -> Mapping[str, str]:
        """Read-only view of path -> comment."""
        return self._comments_proxy


class OdinDocumentBuilder:
    """Mutable builder for OdinDocument."""

    def __init__(self) -> None:
        self._assignments: OrderedDict[str, OdinValue] = OrderedDict()
        self._metadata: OrderedDict[str, OdinValue] = OrderedDict()
        self._modifiers: Dict[str, OdinModifiers] = {}
        self._comments: Dict[str, str] = {}

    def set(
        self,
        path: str,
        value: OdinValue,
        modifiers: Optional[OdinModifiers] = None,
    ) -> OdinDocumentBuilder:
        """Set value at path, optionally with modifiers."""
        self._assignments[path] = value
        if modifiers is not None:
            self._modifiers[path] = modifiers
        return self

    def set_metadata(self, key: str, value: OdinValue) -> OdinDocumentBuilder:
        """Set metadata key-value pair."""
        self._metadata[key] = value
        return self

    def set_comment(self, path: str, comment: str) -> OdinDocumentBuilder:
        """Set comment for a path."""
        self._comments[path] = comment
        return self

    def build(self) -> OdinDocument:
        """Build an immutable OdinDocument from current state."""
        return OdinDocument(
            assignments=OrderedDict(self._assignments),
            metadata=OrderedDict(self._metadata),
            modifiers=dict(self._modifiers),
            comments=dict(self._comments),
        )
