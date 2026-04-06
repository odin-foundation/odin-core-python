"""Extended tests for core verbs: concat, upper, lower, trim, coalesce, ifNull, ifEmpty, ifElse, lookup, lookupDefault.

Ported from Java CoreVerbTest + CoreVerbExtendedTest for cross-language parity.
"""

import math
import pytest
from decimal import Decimal
from datetime import date, datetime

from odin.transform.dyn_value import DynValue, DynType
from odin.transform.engine import TransformEngine, VerbContext
from odin.transform.verb_registry import create_default_registry


def _engine():
    return TransformEngine(create_default_registry())


def invoke(verb_name, *raw_args):
    engine = _engine()
    args = [_to_dyn(a) for a in raw_args]
    return engine.invoke_verb(verb_name, args)


def _to_dyn(v):
    if isinstance(v, DynValue):
        return v
    if v is None:
        return DynValue.of_null()
    if isinstance(v, bool):
        return DynValue.of_bool(v)
    if isinstance(v, int):
        return DynValue.of_integer(v)
    if isinstance(v, float):
        return DynValue.of_float(v)
    if isinstance(v, str):
        return DynValue.of_string(v)
    if isinstance(v, list):
        return DynValue.of_array([_to_dyn(x) for x in v])
    if isinstance(v, dict):
        return DynValue.of_object({k: _to_dyn(val) for k, val in v.items()})
    return DynValue.of_string(str(v))


# =============================================================================
# concat -- extended
# =============================================================================

class TestConcatExtended:
    """Extended concat tests covering type coercion, unicode, and edge cases."""

    def test_two_strings_no_space(self):
        assert invoke("concat", "hello", "world").as_string() == "helloworld"

    def test_three_strings(self):
        assert invoke("concat", "a", "b", "c").as_string() == "abc"

    def test_four_strings(self):
        assert invoke("concat", "1", "2", "3", "4").as_string() == "1234"

    def test_five_strings(self):
        assert invoke("concat", "a", "b", "c", "d", "e").as_string() == "abcde"

    def test_single_string(self):
        assert invoke("concat", "hello").as_string() == "hello"

    def test_single_null(self):
        assert invoke("concat", None).as_string() == ""

    def test_null_between_strings(self):
        assert invoke("concat", "a", None, "b").as_string() == "ab"

    def test_all_nulls_three(self):
        assert invoke("concat", None, None, None).as_string() == ""

    def test_integer_single(self):
        assert invoke("concat", 42).as_string() == "42"

    def test_float_single(self):
        assert invoke("concat", 3.14).as_string() == "3.14"

    def test_bool_true(self):
        assert invoke("concat", True).as_string() == "true"

    def test_bool_false(self):
        assert invoke("concat", False).as_string() == "false"

    def test_string_and_integer(self):
        assert invoke("concat", "val=", 42).as_string() == "val=42"

    def test_integer_and_string(self):
        assert invoke("concat", 42, " items").as_string() == "42 items"

    def test_string_and_float(self):
        assert invoke("concat", "pi=", 3.14).as_string() == "pi=3.14"

    def test_string_and_bool(self):
        assert invoke("concat", "is_valid=", True).as_string() == "is_valid=true"

    def test_mixed_types(self):
        assert invoke("concat", "count:", 5, " active:", True).as_string() == "count:5 active:true"

    def test_empty_string_args(self):
        assert invoke("concat", "", "").as_string() == ""

    def test_empty_string_with_value(self):
        assert invoke("concat", "", "hello").as_string() == "hello"

    def test_value_with_empty_string(self):
        assert invoke("concat", "hello", "").as_string() == "hello"

    def test_unicode_strings(self):
        assert invoke("concat", "hello", " ", "world").as_string() == "hello world"

    def test_unicode_emoji(self):
        r = invoke("concat", "hi", " ", "there")
        assert r.as_string() == "hi there"

    def test_newline_in_concat(self):
        assert invoke("concat", "line1", "\n", "line2").as_string() == "line1\nline2"

    def test_tab_in_concat(self):
        assert invoke("concat", "col1", "\t", "col2").as_string() == "col1\tcol2"

    def test_negative_integer(self):
        assert invoke("concat", "val:", -42).as_string() == "val:-42"

    def test_zero_integer(self):
        assert invoke("concat", "val:", 0).as_string() == "val:0"

    def test_large_integer(self):
        assert invoke("concat", "n=", 999999999).as_string() == "n=999999999"

    def test_many_args(self):
        result = invoke("concat", "a", "b", "c", "d", "e", "f", "g", "h")
        assert result.as_string() == "abcdefgh"

    def test_array_arg_coerced(self):
        # Arrays get coerced to a string representation
        r = invoke("concat", "arr=", [1, 2, 3])
        assert "arr=" in r.as_string()

    def test_object_arg_coerced(self):
        r = invoke("concat", "obj=", {"a": 1})
        assert "obj=" in r.as_string()

    def test_return_type_is_string(self):
        r = invoke("concat", 1, 2, 3)
        assert r.type == DynType.STRING


# =============================================================================
# upper -- extended
# =============================================================================

class TestUpperExtended:
    """Extended upper tests covering unicode, already-uppercased, and edge cases."""

    def test_lowercase(self):
        assert invoke("upper", "hello").as_string() == "HELLO"

    def test_mixed_case(self):
        assert invoke("upper", "Hello World").as_string() == "HELLO WORLD"

    def test_already_upper(self):
        assert invoke("upper", "HELLO").as_string() == "HELLO"

    def test_empty_string(self):
        assert invoke("upper", "").as_string() == ""

    def test_null_returns_null(self):
        assert invoke("upper", None).is_null()

    def test_no_args_returns_null(self):
        assert invoke("upper").is_null()

    def test_single_char(self):
        assert invoke("upper", "a").as_string() == "A"

    def test_numbers_unchanged(self):
        assert invoke("upper", "abc123").as_string() == "ABC123"

    def test_special_chars_unchanged(self):
        assert invoke("upper", "hello!@#").as_string() == "HELLO!@#"

    def test_whitespace_preserved(self):
        assert invoke("upper", "  hello  ").as_string() == "  HELLO  "

    def test_integer_coerced(self):
        assert invoke("upper", 42).as_string() == "42"

    def test_float_coerced(self):
        r = invoke("upper", 3.14)
        assert "3.14" in r.as_string()

    def test_bool_coerced(self):
        assert invoke("upper", True).as_string() == "TRUE"

    @pytest.mark.parametrize("input_str,expected", [
        ("abc", "ABC"),
        ("ABC", "ABC"),
        ("aBcDeF", "ABCDEF"),
        ("hello world", "HELLO WORLD"),
        ("123", "123"),
        ("", ""),
    ])
    def test_parametrized(self, input_str, expected):
        assert invoke("upper", input_str).as_string() == expected


# =============================================================================
# lower -- extended
# =============================================================================

class TestLowerExtended:
    """Extended lower tests."""

    def test_uppercase(self):
        assert invoke("lower", "HELLO").as_string() == "hello"

    def test_mixed_case(self):
        assert invoke("lower", "Hello World").as_string() == "hello world"

    def test_already_lower(self):
        assert invoke("lower", "hello").as_string() == "hello"

    def test_empty_string(self):
        assert invoke("lower", "").as_string() == ""

    def test_null_returns_null(self):
        assert invoke("lower", None).is_null()

    def test_no_args_returns_null(self):
        assert invoke("lower").is_null()

    def test_single_char(self):
        assert invoke("lower", "A").as_string() == "a"

    def test_numbers_unchanged(self):
        assert invoke("lower", "ABC123").as_string() == "abc123"

    def test_special_chars_unchanged(self):
        assert invoke("lower", "HELLO!@#").as_string() == "hello!@#"

    def test_whitespace_preserved(self):
        assert invoke("lower", "  HELLO  ").as_string() == "  hello  "

    def test_integer_coerced(self):
        assert invoke("lower", 42).as_string() == "42"

    def test_bool_coerced(self):
        assert invoke("lower", True).as_string() == "true"

    @pytest.mark.parametrize("input_str,expected", [
        ("ABC", "abc"),
        ("abc", "abc"),
        ("AbCdEf", "abcdef"),
        ("HELLO WORLD", "hello world"),
        ("123", "123"),
        ("", ""),
    ])
    def test_parametrized(self, input_str, expected):
        assert invoke("lower", input_str).as_string() == expected


# =============================================================================
# trim -- extended
# =============================================================================

class TestTrimExtended:
    """Extended trim tests covering tabs, newlines, and mixed whitespace."""

    def test_leading_spaces(self):
        assert invoke("trim", "   hello").as_string() == "hello"

    def test_trailing_spaces(self):
        assert invoke("trim", "hello   ").as_string() == "hello"

    def test_both_spaces(self):
        assert invoke("trim", "  hello  ").as_string() == "hello"

    def test_tabs(self):
        assert invoke("trim", "\thello\t").as_string() == "hello"

    def test_newlines(self):
        assert invoke("trim", "\nhello\n").as_string() == "hello"

    def test_mixed_whitespace(self):
        assert invoke("trim", " \t\nhello\n\t ").as_string() == "hello"

    def test_no_whitespace(self):
        assert invoke("trim", "hello").as_string() == "hello"

    def test_only_spaces(self):
        assert invoke("trim", "   ").as_string() == ""

    def test_empty_string(self):
        assert invoke("trim", "").as_string() == ""

    def test_null_returns_null(self):
        assert invoke("trim", None).is_null()

    def test_no_args_returns_null(self):
        assert invoke("trim").is_null()

    def test_inner_whitespace_preserved(self):
        assert invoke("trim", "  hello world  ").as_string() == "hello world"

    def test_multiple_inner_spaces(self):
        assert invoke("trim", "  a  b  c  ").as_string() == "a  b  c"


class TestTrimLeftExtended:
    """Extended trimLeft tests."""

    def test_leading_spaces(self):
        assert invoke("trimLeft", "   hello").as_string() == "hello"

    def test_both_spaces(self):
        assert invoke("trimLeft", "  hello  ").as_string() == "hello  "

    def test_tabs(self):
        assert invoke("trimLeft", "\thello\t").as_string() == "hello\t"

    def test_newlines(self):
        assert invoke("trimLeft", "\nhello\n").as_string() == "hello\n"

    def test_no_leading_whitespace(self):
        assert invoke("trimLeft", "hello  ").as_string() == "hello  "

    def test_only_spaces(self):
        assert invoke("trimLeft", "   ").as_string() == ""

    def test_empty_string(self):
        assert invoke("trimLeft", "").as_string() == ""

    def test_null_returns_null(self):
        assert invoke("trimLeft", None).is_null()

    def test_no_args_returns_null(self):
        assert invoke("trimLeft").is_null()

    def test_mixed_whitespace(self):
        assert invoke("trimLeft", " \t\nhello").as_string() == "hello"


class TestTrimRightExtended:
    """Extended trimRight tests."""

    def test_trailing_spaces(self):
        assert invoke("trimRight", "hello   ").as_string() == "hello"

    def test_both_spaces(self):
        assert invoke("trimRight", "  hello  ").as_string() == "  hello"

    def test_tabs(self):
        assert invoke("trimRight", "\thello\t").as_string() == "\thello"

    def test_newlines(self):
        assert invoke("trimRight", "\nhello\n").as_string() == "\nhello"

    def test_no_trailing_whitespace(self):
        assert invoke("trimRight", "  hello").as_string() == "  hello"

    def test_only_spaces(self):
        assert invoke("trimRight", "   ").as_string() == ""

    def test_empty_string(self):
        assert invoke("trimRight", "").as_string() == ""

    def test_null_returns_null(self):
        assert invoke("trimRight", None).is_null()

    def test_no_args_returns_null(self):
        assert invoke("trimRight").is_null()

    def test_mixed_whitespace(self):
        assert invoke("trimRight", "hello \t\n").as_string() == "hello"


# =============================================================================
# coalesce -- extended
# =============================================================================

class TestCoalesceExtended:
    """Extended coalesce tests covering multiple null/empty positions."""

    def test_first_non_null(self):
        assert invoke("coalesce", None, "hello").as_string() == "hello"

    def test_first_is_value(self):
        assert invoke("coalesce", "first", "second").as_string() == "first"

    def test_skips_empty_string(self):
        assert invoke("coalesce", "", "fallback").as_string() == "fallback"

    def test_skips_null_and_empty(self):
        assert invoke("coalesce", None, "", "value").as_string() == "value"

    def test_all_null(self):
        assert invoke("coalesce", None, None).is_null()

    def test_all_null_three(self):
        assert invoke("coalesce", None, None, None).is_null()

    def test_all_empty(self):
        assert invoke("coalesce", "", "").is_null()

    def test_all_empty_three(self):
        assert invoke("coalesce", "", "", "").is_null()

    def test_all_null_and_empty(self):
        assert invoke("coalesce", None, "", None, "").is_null()

    def test_returns_integer(self):
        r = invoke("coalesce", None, 42)
        assert r.as_int() == 42

    def test_returns_zero_integer(self):
        r = invoke("coalesce", 0, "fallback")
        assert r.as_int() == 0

    def test_returns_false_boolean(self):
        r = invoke("coalesce", False, "fallback")
        assert r.as_bool() is False

    def test_returns_float(self):
        r = invoke("coalesce", None, 3.14)
        assert r.as_float() == pytest.approx(3.14)

    def test_single_value(self):
        assert invoke("coalesce", "only").as_string() == "only"

    def test_single_null(self):
        assert invoke("coalesce", None).is_null()

    def test_single_empty(self):
        assert invoke("coalesce", "").is_null()

    def test_empty_args(self):
        assert invoke("coalesce").is_null()

    def test_value_after_many_nulls(self):
        assert invoke("coalesce", None, None, None, None, "found").as_string() == "found"

    def test_value_after_many_empties(self):
        assert invoke("coalesce", "", "", "", "", "found").as_string() == "found"

    def test_first_non_null_is_integer_zero(self):
        r = invoke("coalesce", None, 0)
        assert r.type == DynType.INTEGER
        assert r.as_int() == 0

    def test_preserves_type_of_first_non_null(self):
        r = invoke("coalesce", None, True)
        assert r.type == DynType.BOOL


# =============================================================================
# ifNull -- extended
# =============================================================================

class TestIfNullExtended:
    """Extended ifNull tests."""

    def test_null_returns_default(self):
        assert invoke("ifNull", None, "default").as_string() == "default"

    def test_non_null_returns_first(self):
        assert invoke("ifNull", "value", "default").as_string() == "value"

    def test_empty_string_not_null(self):
        assert invoke("ifNull", "", "default").as_string() == ""

    def test_zero_not_null(self):
        assert invoke("ifNull", 0, "default").as_int() == 0

    def test_false_not_null(self):
        assert invoke("ifNull", False, "default").as_bool() is False

    def test_too_few_args(self):
        assert invoke("ifNull", "only_one").is_null()

    def test_no_args(self):
        assert invoke("ifNull").is_null()

    def test_null_with_integer_default(self):
        r = invoke("ifNull", None, 42)
        assert r.as_int() == 42

    def test_null_with_bool_default(self):
        r = invoke("ifNull", None, True)
        assert r.as_bool() is True

    def test_null_with_float_default(self):
        r = invoke("ifNull", None, 3.14)
        assert r.as_float() == pytest.approx(3.14)

    def test_null_with_null_default(self):
        assert invoke("ifNull", None, None).is_null()

    def test_float_not_null(self):
        r = invoke("ifNull", 3.14, "default")
        assert r.as_float() == pytest.approx(3.14)

    def test_array_not_null(self):
        r = invoke("ifNull", [1, 2, 3], "default")
        assert r.type == DynType.ARRAY

    def test_object_not_null(self):
        r = invoke("ifNull", {"a": 1}, "default")
        assert r.type == DynType.OBJECT


# =============================================================================
# ifEmpty -- extended
# =============================================================================

class TestIfEmptyExtended:
    """Extended ifEmpty tests."""

    def test_null_returns_default(self):
        assert invoke("ifEmpty", None, "default").as_string() == "default"

    def test_empty_string_returns_default(self):
        assert invoke("ifEmpty", "", "default").as_string() == "default"

    def test_non_empty_returns_first(self):
        assert invoke("ifEmpty", "value", "default").as_string() == "value"

    def test_whitespace_not_empty(self):
        assert invoke("ifEmpty", " ", "default").as_string() == " "

    def test_int_zero_not_empty(self):
        r = invoke("ifEmpty", 0, "default")
        assert r.as_int() == 0

    def test_float_zero_not_empty(self):
        r = invoke("ifEmpty", 0.0, "default")
        assert r.as_float() == 0.0

    def test_bool_false_not_empty(self):
        r = invoke("ifEmpty", False, "default")
        assert r.as_bool() is False

    def test_bool_true_not_empty(self):
        r = invoke("ifEmpty", True, "default")
        assert r.as_bool() is True

    def test_too_few_args(self):
        assert invoke("ifEmpty").is_null()

    def test_too_few_args_one(self):
        assert invoke("ifEmpty", "").is_null()

    def test_null_with_integer_default(self):
        r = invoke("ifEmpty", None, 42)
        assert r.as_int() == 42

    def test_empty_with_integer_default(self):
        r = invoke("ifEmpty", "", 42)
        assert r.as_int() == 42

    def test_array_not_empty(self):
        r = invoke("ifEmpty", [1, 2], "default")
        assert r.type == DynType.ARRAY

    def test_object_not_empty(self):
        r = invoke("ifEmpty", {"a": 1}, "default")
        assert r.type == DynType.OBJECT


# =============================================================================
# ifElse -- extended
# =============================================================================

class TestIfElseExtended:
    """Extended ifElse tests covering various truthiness edge cases."""

    def test_true_returns_then(self):
        assert invoke("ifElse", True, "yes", "no").as_string() == "yes"

    def test_false_returns_else(self):
        assert invoke("ifElse", False, "yes", "no").as_string() == "no"

    def test_null_is_falsy(self):
        assert invoke("ifElse", None, "yes", "no").as_string() == "no"

    def test_non_zero_int_is_truthy(self):
        assert invoke("ifElse", 1, "yes", "no").as_string() == "yes"

    def test_negative_int_is_truthy(self):
        assert invoke("ifElse", -1, "yes", "no").as_string() == "yes"

    def test_zero_is_falsy(self):
        assert invoke("ifElse", 0, "yes", "no").as_string() == "no"

    def test_non_zero_float_is_truthy(self):
        assert invoke("ifElse", 0.1, "yes", "no").as_string() == "yes"

    def test_zero_float_is_falsy(self):
        assert invoke("ifElse", 0.0, "yes", "no").as_string() == "no"

    def test_non_empty_string_is_truthy(self):
        assert invoke("ifElse", "hello", "yes", "no").as_string() == "yes"

    def test_empty_string_is_falsy(self):
        assert invoke("ifElse", "", "yes", "no").as_string() == "no"

    def test_whitespace_string_is_truthy(self):
        assert invoke("ifElse", " ", "yes", "no").as_string() == "yes"

    def test_array_is_truthy(self):
        assert invoke("ifElse", [1, 2], "yes", "no").as_string() == "yes"

    def test_empty_array_is_truthy(self):
        # Arrays are always truthy in Java/TS
        assert invoke("ifElse", _to_dyn([]), "yes", "no").as_string() == "yes"

    def test_object_is_truthy(self):
        assert invoke("ifElse", {"a": 1}, "yes", "no").as_string() == "yes"

    def test_too_few_args(self):
        assert invoke("ifElse", True, "yes").is_null()

    def test_too_few_args_one(self):
        assert invoke("ifElse", True).is_null()

    def test_no_args(self):
        assert invoke("ifElse").is_null()

    def test_then_value_preserved_type_int(self):
        r = invoke("ifElse", True, 42, "no")
        assert r.as_int() == 42

    def test_else_value_preserved_type_int(self):
        r = invoke("ifElse", False, "yes", 42)
        assert r.as_int() == 42

    def test_string_true_is_truthy(self):
        assert invoke("ifElse", "true", "yes", "no").as_string() == "yes"

    def test_string_false_is_truthy(self):
        # "false" as a non-empty string is truthy
        assert invoke("ifElse", "false", "yes", "no").as_string() == "yes"

    def test_string_zero_is_truthy(self):
        # "0" as a non-empty string is truthy
        assert invoke("ifElse", "0", "yes", "no").as_string() == "yes"


# =============================================================================
# coercion verbs -- extended (these are in the core verb family)
# =============================================================================

class TestCoerceStringExtended:
    """Tests for coerceString verb."""

    def test_from_string(self):
        assert invoke("coerceString", "hello").as_string() == "hello"

    def test_from_integer(self):
        assert invoke("coerceString", 42).as_string() == "42"

    def test_from_negative_integer(self):
        assert invoke("coerceString", -42).as_string() == "-42"

    def test_from_zero(self):
        assert invoke("coerceString", 0).as_string() == "0"

    def test_from_float(self):
        assert invoke("coerceString", 3.14).as_string() == "3.14"

    def test_from_bool_true(self):
        assert invoke("coerceString", True).as_string() == "true"

    def test_from_bool_false(self):
        assert invoke("coerceString", False).as_string() == "false"

    def test_from_null(self):
        assert invoke("coerceString", None).is_null()

    def test_from_empty_string(self):
        assert invoke("coerceString", "").as_string() == ""


class TestCoerceNumberExtended:
    """Tests for coerceNumber verb."""

    def test_from_string_integer(self):
        r = invoke("coerceNumber", "42")
        assert r.as_float() == 42.0

    def test_from_string_float(self):
        r = invoke("coerceNumber", "3.14")
        assert r.as_float() == pytest.approx(3.14)

    def test_from_string_negative(self):
        r = invoke("coerceNumber", "-5.5")
        assert r.as_float() == pytest.approx(-5.5)

    def test_from_integer(self):
        r = invoke("coerceNumber", 42)
        assert r.as_float() == 42.0

    def test_from_float_passthrough(self):
        r = invoke("coerceNumber", 3.14)
        assert r.as_float() == pytest.approx(3.14)

    def test_from_bool_true(self):
        r = invoke("coerceNumber", True)
        assert r.as_float() == 1.0

    def test_from_bool_false(self):
        r = invoke("coerceNumber", False)
        assert r.as_float() == 0.0

    def test_from_null(self):
        assert invoke("coerceNumber", None).is_null()


class TestCoerceIntegerExtended:
    """Tests for coerceInteger verb."""

    def test_from_integer(self):
        assert invoke("coerceInteger", 42).as_int() == 42

    def test_from_float_truncates(self):
        assert invoke("coerceInteger", 3.7).as_int() == 3

    def test_from_string(self):
        assert invoke("coerceInteger", "42").as_int() == 42

    def test_from_bool_true(self):
        assert invoke("coerceInteger", True).as_int() == 1

    def test_from_bool_false(self):
        assert invoke("coerceInteger", False).as_int() == 0

    def test_from_null(self):
        assert invoke("coerceInteger", None).is_null()

    def test_from_negative(self):
        assert invoke("coerceInteger", -5).as_int() == -5


class TestCoerceBooleanExtended:
    """Tests for coerceBoolean verb."""

    def test_from_bool_true(self):
        assert invoke("coerceBoolean", True).as_bool() is True

    def test_from_bool_false(self):
        assert invoke("coerceBoolean", False).as_bool() is False

    def test_from_string_true(self):
        assert invoke("coerceBoolean", "true").as_bool() is True

    def test_from_string_false(self):
        assert invoke("coerceBoolean", "false").as_bool() is False

    def test_from_string_yes(self):
        assert invoke("coerceBoolean", "yes").as_bool() is True

    def test_from_string_no(self):
        assert invoke("coerceBoolean", "no").as_bool() is False

    def test_from_string_one(self):
        assert invoke("coerceBoolean", "1").as_bool() is True

    def test_from_string_zero(self):
        assert invoke("coerceBoolean", "0").as_bool() is False

    def test_from_string_empty(self):
        assert invoke("coerceBoolean", "").as_bool() is False

    def test_from_int_nonzero(self):
        assert invoke("coerceBoolean", 5).as_bool() is True

    def test_from_int_zero(self):
        assert invoke("coerceBoolean", 0).as_bool() is False

    def test_from_null(self):
        assert invoke("coerceBoolean", None).as_bool() is False


# =============================================================================
# lookup -- extended (basic table-less tests)
# =============================================================================

class TestLookupExtended:
    """Tests for lookup verb without table context (should return null)."""

    def test_no_table_ref(self):
        assert invoke("lookup", "noRef", "val").is_null()

    def test_no_dot_in_ref(self):
        assert invoke("lookup", "tableName", "val").is_null()

    def test_dot_ref_no_table(self):
        # No table in context, should return null
        assert invoke("lookup", "table.col", "val").is_null()

    def test_too_few_args(self):
        assert invoke("lookup", "table.col").is_null()

    def test_no_args(self):
        assert invoke("lookup").is_null()


class TestLookupDefaultExtended:
    """Tests for lookupDefault verb without table context."""

    def test_no_table_returns_default(self):
        r = invoke("lookupDefault", "table.col", "val", "myDefault")
        assert r.as_string() == "myDefault"

    def test_no_dot_returns_default(self):
        r = invoke("lookupDefault", "tableName", "val", "myDefault")
        assert r.as_string() == "myDefault"

    def test_too_few_args(self):
        assert invoke("lookupDefault", "table.col", "val").is_null()

    def test_no_args(self):
        assert invoke("lookupDefault").is_null()


# =============================================================================
# Parametrized edge case tests across multiple verbs
# =============================================================================

class TestNullHandlingAcrossVerbs:
    """Verify null handling is consistent across all core verbs."""

    @pytest.mark.parametrize("verb", [
        "upper", "lower", "trim", "trimLeft", "trimRight",
    ])
    def test_null_input_returns_null(self, verb):
        assert invoke(verb, None).is_null()

    @pytest.mark.parametrize("verb", [
        "upper", "lower", "trim", "trimLeft", "trimRight",
    ])
    def test_no_args_returns_null(self, verb):
        assert invoke(verb).is_null()

    @pytest.mark.parametrize("verb", [
        "upper", "lower", "trim", "trimLeft", "trimRight",
    ])
    def test_empty_string_returns_empty(self, verb):
        assert invoke(verb, "").as_string() == ""


class TestTypeMixingInConcat:
    """Test various type combinations in concat."""

    @pytest.mark.parametrize("args,expected", [
        (("a", "b"), "ab"),
        (("a", 1), "a1"),
        ((1, "a"), "1a"),
        ((1, 2), "12"),
        ((True, False), "truefalse"),
        (("val=", True), "val=true"),
        (("pi=", 3.14), "pi=3.14"),
        ((None, "a"), "a"),
        (("a", None), "a"),
        ((None,), ""),
        ((), ""),
    ])
    def test_mixed_types(self, args, expected):
        assert invoke("concat", *args).as_string() == expected


# =============================================================================
# Return type preservation tests
# =============================================================================

class TestReturnTypePreservation:
    """Verify that ifNull, ifEmpty, coalesce preserve the type of the returned value."""

    def test_ifNull_preserves_integer(self):
        r = invoke("ifNull", None, 42)
        assert r.type == DynType.INTEGER

    def test_ifNull_preserves_float(self):
        r = invoke("ifNull", None, 3.14)
        assert r.type == DynType.FLOAT

    def test_ifNull_preserves_bool(self):
        r = invoke("ifNull", None, True)
        assert r.type == DynType.BOOL

    def test_ifNull_preserves_string(self):
        r = invoke("ifNull", None, "hello")
        assert r.type == DynType.STRING

    def test_ifEmpty_preserves_integer(self):
        r = invoke("ifEmpty", "", 42)
        assert r.type == DynType.INTEGER

    def test_coalesce_preserves_integer(self):
        r = invoke("coalesce", None, 42)
        assert r.type == DynType.INTEGER

    def test_coalesce_preserves_bool(self):
        r = invoke("coalesce", None, True)
        assert r.type == DynType.BOOL

    def test_coalesce_preserves_float(self):
        r = invoke("coalesce", None, 3.14)
        assert r.type == DynType.FLOAT
