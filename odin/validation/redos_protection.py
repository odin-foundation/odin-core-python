"""ReDoS (Regular Expression Denial of Service) protection.

Provides static analysis of regex patterns to detect constructs that could
cause catastrophic backtracking, such as nested quantifiers ``(a+)+``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

MAX_PATTERN_LENGTH: int = 1024
MAX_NESTING_DEPTH: int = 10
MAX_QUANTIFIERS: int = 20


@dataclass(frozen=True)
class RedosAnalysis:
    """Result of analysing a regex pattern for ReDoS risk."""

    safe: bool
    reason: Optional[str]
    complexity: int


def _compute_complexity(quantifiers: int, depth: int, length: int) -> int:
    return (quantifiers * 2) + (depth * 3) + (length // 10)


def _has_nested_quantifiers(pattern: str) -> bool:
    """Return True if *pattern* contains a group with an inner quantifier
    that is itself followed by an outer quantifier (e.g. ``(a+)+``).
    """
    stack: list[bool] = []  # True if the current group contains a quantifier
    escaped = False
    in_char_class = False

    i = 0
    while i < len(pattern):
        ch = pattern[i]

        if escaped:
            escaped = False
            i += 1
            continue

        if ch == "\\":
            escaped = True
            i += 1
            continue

        if ch == "[" and not in_char_class:
            in_char_class = True
            i += 1
            continue
        if ch == "]" and in_char_class:
            in_char_class = False
            i += 1
            continue
        if in_char_class:
            i += 1
            continue

        if ch == "(":
            stack.append(False)
        elif ch == ")":
            group_had_quantifier = stack.pop() if stack else False
            if group_had_quantifier and i + 1 < len(pattern):
                nxt = pattern[i + 1]
                if nxt in ("+", "*", "?", "{"):
                    return True
        elif ch in ("+", "*", "?"):
            if stack:
                stack[-1] = True
        elif ch == "{":
            if stack:
                stack[-1] = True

        i += 1

    return False


def analyze(pattern: Optional[str]) -> RedosAnalysis:
    """Analyse *pattern* for ReDoS risk.

    Returns a :class:`RedosAnalysis` indicating whether the pattern is
    considered safe, a human-readable reason if not, and a complexity score.
    """
    if pattern is None or len(pattern) == 0:
        return RedosAnalysis(safe=True, reason=None, complexity=0)

    if len(pattern) > MAX_PATTERN_LENGTH:
        return RedosAnalysis(
            safe=False,
            reason="Pattern exceeds maximum length",
            complexity=len(pattern),
        )

    max_depth = 0
    current_depth = 0
    quantifier_count = 0
    in_char_class = False
    escaped = False

    for ch in pattern:
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == "[" and not in_char_class:
            in_char_class = True
            continue
        if ch == "]" and in_char_class:
            in_char_class = False
            continue
        if in_char_class:
            continue

        if ch == "(":
            current_depth += 1
            if current_depth > max_depth:
                max_depth = current_depth
        elif ch == ")":
            if current_depth > 0:
                current_depth -= 1
        elif ch in ("+", "*", "?"):
            quantifier_count += 1
        elif ch == "{":
            quantifier_count += 1

    complexity = _compute_complexity(quantifier_count, max_depth, len(pattern))

    if max_depth > MAX_NESTING_DEPTH:
        return RedosAnalysis(
            safe=False,
            reason="Nesting depth exceeds limit",
            complexity=complexity,
        )

    if quantifier_count > MAX_QUANTIFIERS:
        return RedosAnalysis(
            safe=False,
            reason="Too many quantifiers",
            complexity=complexity,
        )

    if _has_nested_quantifiers(pattern):
        return RedosAnalysis(
            safe=False,
            reason="Nested quantifiers detected",
            complexity=complexity,
        )

    return RedosAnalysis(safe=True, reason=None, complexity=complexity)


# ReDoS safety verdicts keyed by pattern source; the static analysis runs once
# per distinct pattern and is reused for every value.
_SAFETY_CACHE: dict = {}


def is_safe_pattern(regex: str) -> bool:
    """Convenience wrapper: return True if *regex* is considered safe."""
    if regex in _SAFETY_CACHE:
        return _SAFETY_CACHE[regex]
    safe = analyze(regex).safe
    _SAFETY_CACHE[regex] = safe
    return safe
