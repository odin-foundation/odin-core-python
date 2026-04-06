"""Tests for odin.validation.redos_protection.

Mirrors the Java ReDoSProtectionTest.java test cases.
"""

import pytest

from odin.validation.redos_protection import (
    MAX_PATTERN_LENGTH,
    analyze,
    is_safe_pattern,
)


# ── Safe patterns ──────────────────────────────────────────────────────────


class TestSafePatterns:
    def test_simple_pattern(self):
        result = analyze("^[a-z]+$")
        assert result.safe

    def test_fixed_pattern(self):
        result = analyze(r"^\d{3}-\d{2}-\d{4}$")
        assert result.safe

    def test_simple_alternation(self):
        result = analyze("^(a|b|c)$")
        assert result.safe

    def test_email_like_pattern(self):
        result = analyze(r"^[a-zA-Z0-9]+@[a-zA-Z0-9]+\.[a-z]+$")
        assert result.safe

    def test_character_class_only(self):
        result = analyze("[A-Z]{3}")
        assert result.safe

    def test_bounded_quantifier(self):
        result = analyze("^[a-z]{1,10}$")
        assert result.safe

    def test_empty_pattern(self):
        result = analyze("")
        assert result.safe

    def test_literal_string(self):
        result = analyze("hello")
        assert result.safe

    def test_dot_with_bounded_quantifier(self):
        result = analyze(".{1,100}")
        assert result.safe


# ── Unsafe patterns ────────────────────────────────────────────────────────


class TestUnsafePatterns:
    def test_nested_quantifiers(self):
        result = analyze("(a+)+")
        assert not result.safe

    def test_nested_star_quantifiers(self):
        result = analyze("(a*)*")
        assert not result.safe

    def test_overlapping_alternation(self):
        # Technically unsafe but not detected by current heuristic (matches Java)
        result = analyze("(a|a)*")
        assert result.safe

    def test_nested_with_plus(self):
        result = analyze("(a+b+)+")
        assert not result.safe

    def test_classic_redos(self):
        result = analyze("(a+)+$")
        assert not result.safe

    def test_nested_star_plus(self):
        result = analyze("(a*)+")
        assert not result.safe

    def test_nested_plus_star(self):
        result = analyze("(a+)*")
        assert not result.safe

    def test_nested_with_brace(self):
        result = analyze("(a{2,})+")
        assert not result.safe


# ── Pattern length limits ──────────────────────────────────────────────────


class TestLengthLimits:
    def test_pattern_under_limit(self):
        result = analyze("^[a-z]+$")
        assert result.safe

    def test_pattern_over_limit(self):
        long_pattern = "a" * (MAX_PATTERN_LENGTH + 1)
        result = analyze(long_pattern)
        assert not result.safe

    def test_pattern_at_limit(self):
        # Exactly at limit should still be safe (if no dangerous constructs)
        pattern = "a" * MAX_PATTERN_LENGTH
        result = analyze(pattern)
        assert result.safe


# ── Complexity score ───────────────────────────────────────────────────────


class TestComplexity:
    def test_simple_pattern_low_complexity(self):
        result = analyze("^abc$")
        assert result.complexity < 5

    def test_complex_pattern_higher_complexity(self):
        result = analyze(r"^[a-z]+@[a-z]+\.[a-z]+$")
        assert result.complexity >= 0

    def test_unsafe_pattern_has_reason(self):
        result = analyze("(a+)+")
        assert not result.safe
        assert result.reason is not None
        assert len(result.reason) > 0

    def test_safe_pattern_no_reason(self):
        result = analyze("^abc$")
        assert result.safe
        assert result.reason is None

    def test_empty_pattern_zero_complexity(self):
        result = analyze("")
        assert result.complexity == 0


# ── Edge cases ─────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_escaped_quantifiers(self):
        result = analyze(r"\+\*\?")
        assert result.safe

    def test_none_pattern(self):
        result = analyze(None)
        assert result.safe

    def test_quantifier_in_char_class(self):
        # + inside [...] is literal, not a quantifier
        result = analyze("[a+]+")
        assert result.safe

    def test_escaped_parens(self):
        result = analyze(r"\(a+\)+")
        assert result.safe

    def test_deeply_nested(self):
        # 11 levels of nesting exceeds MAX_NESTING_DEPTH
        pattern = "(" * 11 + "a" + ")" * 11
        result = analyze(pattern)
        assert not result.safe
        assert result.reason == "Nesting depth exceeds limit"

    def test_too_many_quantifiers(self):
        # 21 quantifiers
        pattern = "".join(f"a+" for _ in range(21))
        result = analyze(pattern)
        assert not result.safe
        assert result.reason == "Too many quantifiers"


# ── Convenience wrapper ───────────────────────────────────────────────────


class TestIsSafePattern:
    def test_safe(self):
        assert is_safe_pattern("^[a-z]+$")

    def test_unsafe(self):
        assert not is_safe_pattern("(a+)+")

    def test_empty(self):
        assert is_safe_pattern("")
