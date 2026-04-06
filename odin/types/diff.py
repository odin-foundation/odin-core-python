"""Diff types for ODIN document comparison."""

from dataclasses import dataclass, field
from typing import List

from odin.types.values import OdinValue


@dataclass(frozen=True)
class PathValue:
    """A path and its value."""

    path: str
    """Full path."""

    value: OdinValue
    """Value at path."""


@dataclass(frozen=True)
class PathChange:
    """A path with old and new values."""

    path: str
    """Full path."""

    old_value: OdinValue
    """Original value."""

    new_value: OdinValue
    """New value."""


@dataclass(frozen=True)
class PathMove:
    """A path that moved from one location to another."""

    from_path: str
    """Original path."""

    to_path: str
    """New path."""


@dataclass(frozen=True)
class OdinDiff:
    """Difference between two ODIN documents."""

    additions: List[PathValue] = field(default_factory=list)
    """Paths added in the new document."""

    deletions: List[PathValue] = field(default_factory=list)
    """Paths removed from the original document."""

    modifications: List[PathChange] = field(default_factory=list)
    """Paths with changed values."""

    moves: List[PathMove] = field(default_factory=list)
    """Paths that moved (e.g., array reordering)."""

    @property
    def is_empty(self) -> bool:
        """Whether there are any changes."""
        return (
            len(self.additions) == 0
            and len(self.deletions) == 0
            and len(self.modifications) == 0
            and len(self.moves) == 0
        )
