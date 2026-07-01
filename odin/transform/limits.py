"""Transform execution limits, overridable via ODIN_ environment variables.

Values are read once at import; tests set the module attributes directly.
The engine reads these at execute time so a host or test can adjust them.
"""

from __future__ import annotations

import os


def _env_int(name: str, default: int) -> int:
    """Read an ODIN_-prefixed integer env var, falling back to the default."""
    raw = os.environ.get(f"ODIN_{name}")
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except (ValueError, AttributeError):
        return default


# Cap on recursive expression-evaluation depth; standing default enforced.
MAX_EXPRESSION_DEPTH = _env_int("MAX_EXPRESSION_DEPTH", 32)

# Fuel budget for a single execute; 0 = unbounded.
MAX_TRANSFORM_FUEL = _env_int("MAX_TRANSFORM_FUEL", 0)

# Wall-clock timeout in milliseconds for a single execute; 0 = unbounded.
TRANSFORM_TIMEOUT_MS = _env_int("TRANSFORM_TIMEOUT_MS", 0)
