"""Shared utilities for golden tests."""

from pathlib import Path


def find_golden_dir() -> Path:
    """Locate sdk/golden/ directory."""
    candidates = [
        Path(__file__).parent.parent.parent.parent / "golden",
        Path(__file__).parent.parent.parent / ".." / "golden",
    ]
    for p in candidates:
        resolved = p.resolve()
        if resolved.is_dir():
            return resolved
    raise RuntimeError("Cannot find sdk/golden/ directory")
