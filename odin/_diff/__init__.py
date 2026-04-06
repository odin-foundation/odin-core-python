"""ODIN diff and patch operations."""

from odin._diff.differ import compute_diff
from odin._diff.patcher import apply_patch

__all__ = ["compute_diff", "apply_patch"]
