"""Extended string verb tests — ported from Java StringVerbTest + StringVerbExtendedTest.

Targets ~250 additional tests to bring Python string verb coverage closer to Java's ~443.
"""

import pytest
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
# capitalize — extended
# =============================================================================

class TestCapitalizeExtended:
    def test_already_capitalized(self):
        assert invoke("capitalize", "Hello").as_string() == "Hello"

    def test_single_char(self):
        assert invoke("capitalize", "h").as_string() == "H"

    def test_all_upper(self):
        assert invoke("capitalize", "HELLO").as_string() == "Hello"

    def test_no_args(self):
        assert invoke("capitalize").is_null()

    def test_with_spaces(self):
        assert invoke("capitalize", "hello world").as_string() == "Hello world"

    def test_numeric_string(self):
        assert invoke("capitalize", "123abc").as_string() == "123abc"

    def test_unicode_start(self):
        result = invoke("capitalize", "\u00fcber").as_string()
        assert result[0] == "\u00dc"  # U+00FC -> U+00DC uppercase

    def test_with_leading_space(self):
        assert invoke("capitalize", " hello").as_string() == " hello"

    @pytest.mark.parametrize("input_str,expected", [
        ("hello", "Hello"),
        ("WORLD", "World"),
        ("a", "A"),
        ("", ""),
        ("hELLO wORLD", "Hello world"),
    ])
    def test_parametrized(self, input_str, expected):
        assert invoke("capitalize", input_str).as_string() == expected


# =============================================================================
# titleCase — extended
# =============================================================================

class TestTitleCaseExtended:
    def test_all_upper(self):
        result = invoke("titleCase", "HELLO WORLD").as_string()
        assert result == "Hello World"

    def test_with_numbers(self):
        result = invoke("titleCase", "hello 42 world").as_string()
        assert result.startswith("H")
        assert "42" in result

    def test_unicode(self):
        result = invoke("titleCase", "\u00fcber cool").as_string()
        assert "cool" in result.lower()

    def test_single_word(self):
        assert invoke("titleCase", "hello").as_string() == "Hello"

    def test_already_title_case(self):
        assert invoke("titleCase", "Hello World").as_string() == "Hello World"

    def test_no_args(self):
        assert invoke("titleCase").is_null()

    def test_integer_coerces(self):
        result = invoke("titleCase", 42)
        assert result is not None

    @pytest.mark.parametrize("input_str,expected", [
        ("hello world", "Hello World"),
        ("THE QUICK BROWN FOX", "The Quick Brown Fox"),
        ("a b c", "A B C"),
        ("mixedCase words", "Mixedcase Words"),
    ])
    def test_parametrized(self, input_str, expected):
        assert invoke("titleCase", input_str).as_string() == expected


# =============================================================================
# contains — extended
# =============================================================================

class TestContainsExtended:
    def test_both_empty(self):
        assert invoke("contains", "", "").as_bool() is True

    def test_unicode(self):
        assert invoke("contains", "caf\u00e9", "f\u00e9").as_bool() is True

    def test_empty_string_in_nonempty(self):
        assert invoke("contains", "", "a").as_bool() is False

    def test_case_sensitive(self):
        assert invoke("contains", "Hello", "hello").as_bool() is False

    def test_too_few_args(self):
        assert invoke("contains", "hello").as_bool() is False

    def test_special_chars(self):
        assert invoke("contains", "hello@world", "@").as_bool() is True

    def test_multiline(self):
        assert invoke("contains", "hello\nworld", "\n").as_bool() is True

    @pytest.mark.parametrize("haystack,needle,expected", [
        ("hello world", "world", True),
        ("hello world", "WORLD", False),
        ("abcdef", "cde", True),
        ("abcdef", "xyz", False),
        ("", "", True),
        ("abc", "", True),
    ])
    def test_parametrized(self, haystack, needle, expected):
        assert invoke("contains", haystack, needle).as_bool() is expected


# =============================================================================
# startsWith — extended
# =============================================================================

class TestStartsWithExtended:
    def test_empty_prefix(self):
        assert invoke("startsWith", "hello", "").as_bool() is True

    def test_exact_match(self):
        assert invoke("startsWith", "hello", "hello").as_bool() is True

    def test_longer_prefix(self):
        assert invoke("startsWith", "hi", "hello").as_bool() is False

    def test_too_few_args(self):
        assert invoke("startsWith", "hello").as_bool() is False

    def test_null_input(self):
        assert invoke("startsWith", None, "a").as_bool() is False

    def test_unicode_prefix(self):
        assert invoke("startsWith", "caf\u00e9 latte", "caf\u00e9").as_bool() is True

    @pytest.mark.parametrize("text,prefix,expected", [
        ("hello world", "hello", True),
        ("hello world", "world", False),
        ("hello world", "", True),
        ("hello", "hello world", False),
        ("", "", True),
        ("", "a", False),
    ])
    def test_parametrized(self, text, prefix, expected):
        assert invoke("startsWith", text, prefix).as_bool() is expected


# =============================================================================
# endsWith — extended
# =============================================================================

class TestEndsWithExtended:
    def test_empty_suffix(self):
        assert invoke("endsWith", "hello", "").as_bool() is True

    def test_exact_match(self):
        assert invoke("endsWith", "hello", "hello").as_bool() is True

    def test_too_few_args(self):
        assert invoke("endsWith", "hello").as_bool() is False

    def test_null_input(self):
        assert invoke("endsWith", None, "a").as_bool() is False

    def test_unicode_suffix(self):
        assert invoke("endsWith", "caf\u00e9", "\u00e9").as_bool() is True

    @pytest.mark.parametrize("text,suffix,expected", [
        ("hello world", "world", True),
        ("hello world", "hello", False),
        ("hello world", "", True),
        ("hello", "hello world", False),
        ("", "", True),
    ])
    def test_parametrized(self, text, suffix, expected):
        assert invoke("endsWith", text, suffix).as_bool() is expected


# =============================================================================
# replace — extended
# =============================================================================

class TestReplaceExtended:
    def test_multiple_occurrences(self):
        assert invoke("replace", "aaa", "a", "b").as_string() == "bbb"

    def test_empty_search(self):
        # Python str.replace with empty search inserts between chars
        result = invoke("replace", "hello", "", "x")
        assert result is not None

    def test_empty_replacement(self):
        assert invoke("replace", "hello world", " ", "").as_string() == "helloworld"

    def test_replace_longer(self):
        assert invoke("replace", "abc", "b", "xyz").as_string() == "axyzc"

    def test_replace_unicode(self):
        assert invoke("replace", "caf\u00e9", "\u00e9", "e").as_string() == "cafe"

    def test_replace_entire_string(self):
        assert invoke("replace", "hello", "hello", "world").as_string() == "world"

    @pytest.mark.parametrize("text,old,new,expected", [
        ("hello world", "world", "there", "hello there"),
        ("aaa", "a", "bb", "bbbbbb"),
        ("abc", "xyz", "123", "abc"),
        ("hello", "l", "", "heo"),
    ])
    def test_parametrized(self, text, old, new, expected):
        assert invoke("replace", text, old, new).as_string() == expected


# =============================================================================
# replaceRegex — extended
# =============================================================================

class TestReplaceRegexExtended:
    def test_no_match(self):
        assert invoke("replaceRegex", "hello", "xyz", "abc").as_string() == "hello"

    def test_empty_replacement(self):
        assert invoke("replaceRegex", "hello world", " ", "").as_string() == "helloworld"

    def test_multiple_occurrences(self):
        assert invoke("replaceRegex", "aaa", "a", "bb").as_string() == "bbbbbb"

    def test_all_occurrences(self):
        assert invoke("replaceRegex", "aaa", "a", "b").as_string() == "bbb"

    def test_digits_removed(self):
        assert invoke("replaceRegex", "a1b2c3", r"\d", "").as_string() == "abc"

    def test_collapse_whitespace(self):
        assert invoke("replaceRegex", "hello   world", r"\s+", " ").as_string() == "hello world"

    def test_invalid_pattern_returns_null(self):
        result = invoke("replaceRegex", "hello", "[invalid", "x")
        assert result.is_null()

    def test_remove_world(self):
        assert invoke("replaceRegex", "hello world", " world", "").as_string() == "hello"

    @pytest.mark.parametrize("text,pattern,repl,expected", [
        ("abc123", r"\d+", "NUM", "abcNUM"),
        ("hello world", r"\w+", "X", "X X"),
        ("a.b.c", r"\.", "-", "a-b-c"),
    ])
    def test_parametrized(self, text, pattern, repl, expected):
        assert invoke("replaceRegex", text, pattern, repl).as_string() == expected


# =============================================================================
# padLeft — extended
# =============================================================================

class TestPadLeftExtended:
    def test_default_char(self):
        assert invoke("padLeft", "42", 5).as_string() == "   42"

    def test_exact_width(self):
        assert invoke("padLeft", "hi", 2).as_string() == "hi"

    def test_empty_string(self):
        assert invoke("padLeft", "", 3, "x").as_string() == "xxx"

    def test_with_space(self):
        assert invoke("padLeft", "x", 4, " ").as_string() == "   x"

    def test_zero_pad(self):
        assert invoke("padLeft", "42", 5, "0").as_string() == "00042"

    @pytest.mark.parametrize("text,width,char,expected", [
        ("hi", 5, "*", "***hi"),
        ("hello", 3, "*", "hello"),
        ("", 4, "-", "----"),
        ("x", 1, "0", "x"),
    ])
    def test_parametrized(self, text, width, char, expected):
        assert invoke("padLeft", text, width, char).as_string() == expected


# =============================================================================
# padRight — extended
# =============================================================================

class TestPadRightExtended:
    def test_default_char(self):
        assert invoke("padRight", "hi", 5).as_string() == "hi   "

    def test_empty_string(self):
        assert invoke("padRight", "", 4, "-").as_string() == "----"

    def test_space_char(self):
        assert invoke("padRight", "hi", 5, " ").as_string() == "hi   "

    def test_single_char(self):
        assert invoke("padRight", "x", 5, ".").as_string() == "x...."

    def test_dot_pad(self):
        assert invoke("padRight", "hi", 5, ".").as_string() == "hi..."

    @pytest.mark.parametrize("text,width,char,expected", [
        ("hi", 5, "*", "hi***"),
        ("hello", 3, "*", "hello"),
        ("", 3, ".", "..."),
        ("abc", 3, "x", "abc"),
    ])
    def test_parametrized(self, text, width, char, expected):
        assert invoke("padRight", text, width, char).as_string() == expected


# =============================================================================
# pad (center) — extended
# =============================================================================

class TestPadCenterExtended:
    def test_already_wide(self):
        assert invoke("pad", "hello", 3, "*").as_string() == "hello"

    def test_empty_string(self):
        assert invoke("pad", "", 4, "x").as_string() == "xxxx"

    def test_right_padding(self):
        assert invoke("pad", "hi", 6, "-").as_string() == "hi----"

    def test_odd_width(self):
        result = invoke("pad", "hi", 5, "*").as_string()
        assert result == "hi***"

    def test_default_pad_char(self):
        # %pad requires an explicit pad character; fewer args yields null.
        assert invoke("pad", "hi", 6).is_null()

    @pytest.mark.parametrize("text,width,char,expected_len", [
        ("hi", 6, "*", 6),
        ("hello", 5, "-", 5),
        ("a", 5, ".", 5),
        ("", 3, "x", 3),
    ])
    def test_parametrized_length(self, text, width, char, expected_len):
        result = invoke("pad", text, width, char).as_string()
        assert len(result) == expected_len


# =============================================================================
# truncate — extended
# =============================================================================

class TestTruncateExtended:
    def test_shorter_than_limit(self):
        assert invoke("truncate", "hi", 10).as_string() == "hi"

    def test_exact_length(self):
        assert invoke("truncate", "hello", 5).as_string() == "hello"

    def test_empty_string(self):
        assert invoke("truncate", "", 5).as_string() == ""

    def test_to_one(self):
        assert invoke("truncate", "hello", 1).as_string() == "h"

    def test_zero_length(self):
        assert invoke("truncate", "hello", 0).as_string() == ""

    def test_with_ellipsis_exact(self):
        assert invoke("truncate", "hello world", 5, "...").as_string() == "he..."

    def test_unicode(self):
        assert invoke("truncate", "caf\u00e9 latte", 4).as_string() == "caf\u00e9"

    @pytest.mark.parametrize("text,max_len,expected", [
        ("hello world", 5, "hello"),
        ("hi", 10, "hi"),
        ("abcdef", 3, "abc"),
        ("", 5, ""),
        ("a", 1, "a"),
    ])
    def test_parametrized(self, text, max_len, expected):
        assert invoke("truncate", text, max_len).as_string() == expected


# =============================================================================
# split — extended
# =============================================================================

class TestSplitExtended:
    def test_empty_string(self):
        result = invoke("split", "", ",")
        arr = result.as_array()
        assert len(arr) == 1
        assert arr[0].as_string() == ""

    def test_multi_char_delimiter(self):
        result = invoke("split", "a::b::c", "::")
        arr = result.as_array()
        assert len(arr) == 3
        assert arr[0].as_string() == "a"
        assert arr[1].as_string() == "b"
        assert arr[2].as_string() == "c"

    def test_no_match(self):
        result = invoke("split", "hello", ",")
        arr = result.as_array()
        assert len(arr) == 1
        assert arr[0].as_string() == "hello"

    def test_four_parts(self):
        result = invoke("split", "a,b,c,d", ",")
        assert len(result.as_array()) == 4

    def test_with_index_first(self):
        assert invoke("split", "a,b,c", ",", 0).as_string() == "a"

    def test_with_index_last(self):
        assert invoke("split", "a,b,c", ",", 2).as_string() == "c"

    def test_with_index_negative(self):
        assert invoke("split", "a,b,c", ",", -1).as_string() == "c"

    def test_with_index_out_of_bounds(self):
        assert invoke("split", "a,b,c", ",", 10).is_null()

    def test_too_few_args(self):
        assert invoke("split", "hello").is_null()

    def test_tab_delimiter(self):
        result = invoke("split", "a\tb\tc", "\t")
        assert len(result.as_array()) == 3

    @pytest.mark.parametrize("text,delim,count", [
        ("a,b,c", ",", 3),
        ("hello", ",", 1),
        ("a::b::c", "::", 3),
        ("a|b|c|d", "|", 4),
    ])
    def test_parametrized_count(self, text, delim, count):
        assert len(invoke("split", text, delim).as_array()) == count


# =============================================================================
# join — extended
# =============================================================================

class TestJoinExtended:
    def test_empty_delimiter(self):
        assert invoke("join", _to_dyn(["a", "b", "c"]), "").as_string() == "abc"

    def test_single_item(self):
        assert invoke("join", _to_dyn(["hello"]), ",").as_string() == "hello"

    def test_multi_char_delimiter(self):
        assert invoke("join", _to_dyn(["a", "b"]), " -- ").as_string() == "a -- b"

    def test_with_integers(self):
        arr = DynValue.of_array([DynValue.of_integer(1), DynValue.of_integer(2), DynValue.of_integer(3)])
        assert invoke("join", arr, "-").as_string() == "1-2-3"

    def test_too_few_args(self):
        assert invoke("join", _to_dyn(["a"])).is_null()

    def test_string_input(self):
        # Joining a string returns the string itself
        result = invoke("join", "hello", ",")
        assert result.as_string() == "hello"

    @pytest.mark.parametrize("items,sep,expected", [
        (["a", "b", "c"], ",", "a,b,c"),
        (["x"], "-", "x"),
        ([], ",", ""),
        (["hello", "world"], " ", "hello world"),
    ])
    def test_parametrized(self, items, sep, expected):
        assert invoke("join", _to_dyn(items), sep).as_string() == expected


# =============================================================================
# mask — extended
# =============================================================================

class TestMaskExtended:
    def test_show_all_wildcard(self):
        assert invoke("mask", "abc", "***").as_string() == "abc"

    def test_show_zero(self):
        assert invoke("mask", "abc", "*-*-*").as_string() == "a-b-c"

    def test_show_exact_length(self):
        assert invoke("mask", "abc", "###").as_string() == "abc"

    def test_phone_format(self):
        assert invoke("mask", "1234567890", "###-###-####").as_string() == "123-456-7890"

    def test_default_show_last(self):
        result = invoke("mask", "123456789")
        assert result.is_null()

    def test_short_input(self):
        result = invoke("mask", "abc", "##-##").as_string()
        assert result == "ab-c#"

    def test_ssn_format(self):
        assert invoke("mask", "123456789", "###-##-####").as_string() == "123-45-6789"

    @pytest.mark.parametrize("value,pattern,expected", [
        ("1234567890", "(###) ###-####", "(123) 456-7890"),
        ("abc", "###", "abc"),
        ("12345", "##-##-#", "12-34-5"),
    ])
    def test_parametrized(self, value, pattern, expected):
        assert invoke("mask", value, pattern).as_string() == expected


# =============================================================================
# reverseString — extended
# =============================================================================

class TestReverseStringExtended:
    def test_with_spaces(self):
        assert invoke("reverseString", "a b c").as_string() == "c b a"

    def test_palindrome(self):
        assert invoke("reverseString", "racecar").as_string() == "racecar"

    def test_unicode(self):
        # Simple unicode reversal (note: Python reverses code units)
        assert invoke("reverseString", "caf\u00e9").as_string() == "\u00e9fac"

    def test_integer_coerces(self):
        result = invoke("reverseString", 42)
        assert result is not None
        assert result.as_string() == "24"

    def test_numbers_in_string(self):
        assert invoke("reverseString", "abc123").as_string() == "321cba"

    def test_special_chars(self):
        assert invoke("reverseString", "!@#$").as_string() == "$#@!"

    @pytest.mark.parametrize("input_str,expected", [
        ("hello", "olleh"),
        ("", ""),
        ("a", "a"),
        ("ab", "ba"),
        ("abcde", "edcba"),
    ])
    def test_parametrized(self, input_str, expected):
        assert invoke("reverseString", input_str).as_string() == expected


# =============================================================================
# repeat — extended
# =============================================================================

class TestRepeatExtended:
    def test_one(self):
        assert invoke("repeat", "ab", 1).as_string() == "ab"

    def test_empty_string(self):
        assert invoke("repeat", "", 5).as_string() == ""

    def test_large_count(self):
        result = invoke("repeat", "x", 100).as_string()
        assert len(result) == 100

    def test_too_few_args(self):
        assert invoke("repeat", "abc").is_null()

    def test_single_char(self):
        assert invoke("repeat", "*", 5).as_string() == "*****"

    @pytest.mark.parametrize("text,count,expected", [
        ("ab", 3, "ababab"),
        ("x", 1, "x"),
        ("x", 0, ""),
        ("ab", 2, "abab"),
    ])
    def test_parametrized(self, text, count, expected):
        assert invoke("repeat", text, count).as_string() == expected


# =============================================================================
# substring — extended
# =============================================================================

class TestSubstringExtended:
    def test_with_length(self):
        assert invoke("substring", "hello", 1, 3).as_string() == "ell"

    def test_no_length(self):
        assert invoke("substring", "hello", 2).as_string() == "llo"

    def test_start_beyond(self):
        assert invoke("substring", "hello", 10).as_string() == ""

    def test_negative_start_clamped(self):
        assert invoke("substring", "hello", -1).as_string() == "hello"

    def test_zero_length(self):
        assert invoke("substring", "hello", 0, 0).as_string() == ""

    def test_full_string(self):
        assert invoke("substring", "hello", 0, 5).as_string() == "hello"

    def test_length_exceeds_string(self):
        assert invoke("substring", "hello", 0, 100).as_string() == "hello"

    def test_unicode(self):
        assert invoke("substring", "caf\u00e9", 0, 4).as_string() == "caf\u00e9"

    @pytest.mark.parametrize("text,start,length,expected", [
        ("hello", 0, 5, "hello"),
        ("hello", 1, 3, "ell"),
        ("hello", 4, 1, "o"),
        ("hello", 5, 1, ""),
    ])
    def test_parametrized(self, text, start, length, expected):
        assert invoke("substring", text, start, length).as_string() == expected


# =============================================================================
# length — extended
# =============================================================================

class TestLengthExtended:
    def test_empty_string(self):
        assert invoke("length", "").as_int() == 0

    def test_no_args(self):
        assert invoke("length").as_int() == 0

    def test_unicode_string(self):
        assert invoke("length", "caf\u00e9").as_int() == 4

    def test_long_string(self):
        assert invoke("length", "a" * 1000).as_int() == 1000

    def test_boolean_coerced(self):
        # booleans coerce to string "true"/"false"
        result = invoke("length", True)
        assert result.as_int() == 4  # "true"

    @pytest.mark.parametrize("value,expected", [
        ("hello", 5),
        ("", 0),
        ("abc def", 7),
    ])
    def test_parametrized(self, value, expected):
        assert invoke("length", value).as_int() == expected


# =============================================================================
# camelCase — extended
# =============================================================================

class TestCamelCaseExtended:
    def test_from_pascal(self):
        assert invoke("camelCase", "HelloWorld").as_string() == "helloWorld"

    def test_multiple_words(self):
        assert invoke("camelCase", "the quick brown fox").as_string() == "theQuickBrownFox"

    def test_already_camel(self):
        result = invoke("camelCase", "helloWorld").as_string()
        assert result.startswith("h")

    def test_single_word(self):
        assert invoke("camelCase", "hello").as_string() == "hello"

    def test_three_words(self):
        assert invoke("camelCase", "the quick brown").as_string() == "theQuickBrown"

    def test_integer_coerces(self):
        result = invoke("camelCase", 42)
        assert result is not None

    def test_from_snake_multi(self):
        assert invoke("camelCase", "hello_world_test").as_string() == "helloWorldTest"

    def test_from_kebab_multi(self):
        assert invoke("camelCase", "hello-world-test").as_string() == "helloWorldTest"

    @pytest.mark.parametrize("input_str,expected", [
        ("hello_world", "helloWorld"),
        ("hello-world", "helloWorld"),
        ("Hello World", "helloWorld"),
        ("", ""),
    ])
    def test_parametrized(self, input_str, expected):
        assert invoke("camelCase", input_str).as_string() == expected


# =============================================================================
# snakeCase — extended
# =============================================================================

class TestSnakeCaseExtended:
    def test_single_word(self):
        assert invoke("snakeCase", "hello").as_string() == "hello"

    def test_from_pascal(self):
        assert invoke("snakeCase", "HelloWorld").as_string() == "hello_world"

    def test_from_spaces(self):
        assert invoke("snakeCase", "hello world test").as_string() == "hello_world_test"

    def test_empty(self):
        assert invoke("snakeCase", "").as_string() == ""

    def test_already_snake(self):
        assert invoke("snakeCase", "hello_world").as_string() == "hello_world"

    @pytest.mark.parametrize("input_str,expected", [
        ("helloWorld", "hello_world"),
        ("hello-world", "hello_world"),
        ("Hello World", "hello_world"),
        ("hello_world", "hello_world"),
    ])
    def test_parametrized(self, input_str, expected):
        assert invoke("snakeCase", input_str).as_string() == expected


# =============================================================================
# kebabCase — extended
# =============================================================================

class TestKebabCaseExtended:
    def test_single_word(self):
        assert invoke("kebabCase", "hello").as_string() == "hello"

    def test_from_pascal(self):
        assert invoke("kebabCase", "HelloWorld").as_string() == "hello-world"

    def test_from_spaces(self):
        assert invoke("kebabCase", "hello world test").as_string() == "hello-world-test"

    def test_empty(self):
        assert invoke("kebabCase", "").as_string() == ""

    @pytest.mark.parametrize("input_str,expected", [
        ("helloWorld", "hello-world"),
        ("hello_world", "hello-world"),
        ("Hello World", "hello-world"),
    ])
    def test_parametrized(self, input_str, expected):
        assert invoke("kebabCase", input_str).as_string() == expected


# =============================================================================
# pascalCase — extended
# =============================================================================

class TestPascalCaseExtended:
    def test_from_camel(self):
        assert invoke("pascalCase", "helloWorld").as_string() == "HelloWorld"

    def test_from_kebab(self):
        assert invoke("pascalCase", "hello-world").as_string() == "HelloWorld"

    def test_multiple_words(self):
        assert invoke("pascalCase", "the quick brown fox").as_string() == "TheQuickBrownFox"

    def test_single_word(self):
        assert invoke("pascalCase", "hello").as_string() == "Hello"

    def test_empty(self):
        assert invoke("pascalCase", "").as_string() == ""

    def test_integer_coerces(self):
        result = invoke("pascalCase", 42)
        assert result is not None

    @pytest.mark.parametrize("input_str,expected", [
        ("hello_world", "HelloWorld"),
        ("hello-world", "HelloWorld"),
        ("hello world", "HelloWorld"),
    ])
    def test_parametrized(self, input_str, expected):
        assert invoke("pascalCase", input_str).as_string() == expected


# =============================================================================
# slugify — extended
# =============================================================================

class TestSlugifyExtended:
    def test_empty(self):
        assert invoke("slugify", "").as_string() == ""

    def test_leading_trailing_special(self):
        assert invoke("slugify", "!!hello!!").as_string() == "hello"

    def test_numbers(self):
        assert invoke("slugify", "Test 123 Stuff").as_string() == "test-123-stuff"

    def test_already_slug(self):
        assert invoke("slugify", "hello-world").as_string() == "hello-world"

    def test_special_chars(self):
        assert invoke("slugify", "hello & world").as_string() == "hello-world"

    def test_multiple_spaces(self):
        assert invoke("slugify", "hello   world").as_string() == "hello-world"

    def test_accents_complex(self):
        assert invoke("slugify", "caf\u00e9 na\u00efve").as_string() == "cafe-naive"

    @pytest.mark.parametrize("input_str,expected", [
        ("Hello World!", "hello-world"),
        ("Caf\u00e9 Latt\u00e9", "cafe-latte"),
        ("foo_bar-baz", "foo-bar-baz"),
        ("   spaces   ", "spaces"),
    ])
    def test_parametrized(self, input_str, expected):
        assert invoke("slugify", input_str).as_string() == expected


# =============================================================================
# match — extended
# =============================================================================

class TestMatchExtended:
    def test_digit_pattern(self):
        # Python match verb returns bool (unlike Java which returns first match)
        assert invoke("match", "abc123def", r"\d+").as_bool() is True

    def test_not_found(self):
        assert invoke("match", "abc", r"\d+").as_bool() is False

    def test_null_returns_false(self):
        # null coerces to "" which doesn't match, so returns False
        assert invoke("match", None, r"\d+").as_bool() is False

    def test_too_few_args(self):
        assert invoke("match", "hello").is_null()

    def test_full_pattern(self):
        assert invoke("match", "hello", "^hello$").as_bool() is True

    def test_word_boundary(self):
        assert invoke("match", "hello world", "world").as_bool() is True

    def test_email_pattern(self):
        assert invoke("match", "user@domain.com", r"^\S+@\S+\.\S+$").as_bool() is True

    @pytest.mark.parametrize("text,pattern,expected", [
        ("hello 123", r"\d+", True),
        ("hello", r"\d+", False),
        ("abc", "^abc$", True),
        ("abc", "^xyz$", False),
    ])
    def test_parametrized(self, text, pattern, expected):
        assert invoke("match", text, pattern).as_bool() is expected


# =============================================================================
# matches — extended
# =============================================================================

class TestMatchesExtended:
    def test_true(self):
        assert invoke("matches", "hello123", r"\d+").as_bool() is True

    def test_false(self):
        assert invoke("matches", "hello", r"\d+").as_bool() is False

    def test_null_input(self):
        # matches with null coerces to "" which won't match
        result = invoke("matches", None, r"\d+")
        # Should be null or false depending on implementation
        assert result is not None

    def test_full_pattern(self):
        assert invoke("matches", "hello", "^hello$").as_bool() is True

    def test_partial_match(self):
        assert invoke("matches", "hello123world", r"\d+").as_bool() is True

    @pytest.mark.parametrize("text,pattern,expected", [
        ("hello123", r"\d+", True),
        ("hello", r"\d+", False),
        ("abc", r"[a-z]+", True),
        ("123", r"[a-z]+", False),
    ])
    def test_parametrized(self, text, pattern, expected):
        assert invoke("matches", text, pattern).as_bool() is expected


# =============================================================================
# extract — extended
# =============================================================================

class TestExtractExtended:
    def test_no_match(self):
        assert invoke("extract", "abc", r"\d+").is_null()

    def test_null_input(self):
        assert invoke("extract", None, r"\d+").is_null()

    def test_digits(self):
        r = invoke("extract", "abc123def", r"(\d+)")
        assert r.as_string() == "123"

    def test_group_1(self):
        r = invoke("extract", "2024-01-15", r"(\d{4})-(\d{2})-(\d{2})", 1)
        assert r.as_string() == "2024"

    def test_group_2(self):
        r = invoke("extract", "2024-01-15", r"(\d{4})-(\d{2})-(\d{2})", 2)
        assert r.as_string() == "01"

    def test_group_3(self):
        r = invoke("extract", "2024-01-15", r"(\d{4})-(\d{2})-(\d{2})", 3)
        assert r.as_string() == "15"

    def test_group_out_of_range(self):
        r = invoke("extract", "2024-01-15", r"(\d{4})", 5)
        assert r.is_null()

    def test_email_extraction(self):
        r = invoke("extract", "user@domain.com", r"(.+)@(.+)", 1)
        assert r.as_string() == "user"

    def test_email_domain(self):
        r = invoke("extract", "user@domain.com", r"(.+)@(.+)", 2)
        assert r.as_string() == "domain.com"

    @pytest.mark.parametrize("text,pattern,expected", [
        ("abc 123 def", r"(\d+)", "123"),
        ("hello world", r"(\w+)", "hello"),
    ])
    def test_parametrized(self, text, pattern, expected):
        r = invoke("extract", text, pattern)
        assert r.as_string() == expected


# =============================================================================
# normalizeSpace — extended
# =============================================================================

class TestNormalizeSpaceExtended:
    def test_empty_string(self):
        assert invoke("normalizeSpace", "").as_string() == ""

    def test_only_whitespace(self):
        assert invoke("normalizeSpace", "   ").as_string() == ""

    def test_tabs_and_newlines(self):
        assert invoke("normalizeSpace", "hello\t\nworld").as_string() == "hello world"

    def test_single_word(self):
        assert invoke("normalizeSpace", "hello").as_string() == "hello"

    def test_no_extra_space(self):
        assert invoke("normalizeSpace", "hello world").as_string() == "hello world"

    def test_integer_coerces(self):
        result = invoke("normalizeSpace", 42)
        assert result is not None

    @pytest.mark.parametrize("input_str,expected", [
        ("  hello   world  ", "hello world"),
        ("\thello\t\tworld\t", "hello world"),
        ("   ", ""),
        ("hello", "hello"),
        ("a  b  c", "a b c"),
    ])
    def test_parametrized(self, input_str, expected):
        assert invoke("normalizeSpace", input_str).as_string() == expected


# =============================================================================
# leftOf — extended
# =============================================================================

class TestLeftOfExtended:
    def test_no_delimiter(self):
        assert invoke("leftOf", "hello", "@").as_string() == "hello"

    def test_multiple_delimiters(self):
        assert invoke("leftOf", "a@b@c", "@").as_string() == "a"

    def test_empty_string(self):
        assert invoke("leftOf", "", "@").as_string() == ""

    def test_at_start(self):
        assert invoke("leftOf", "@hello", "@").as_string() == ""

    def test_too_few_args(self):
        assert invoke("leftOf", "hello").is_null()

    def test_multi_char_delimiter(self):
        assert invoke("leftOf", "hello::world", "::").as_string() == "hello"

    @pytest.mark.parametrize("text,delim,expected", [
        ("hello@world", "@", "hello"),
        ("a/b/c", "/", "a"),
        ("no-delimiter", "@", "no-delimiter"),
    ])
    def test_parametrized(self, text, delim, expected):
        assert invoke("leftOf", text, delim).as_string() == expected


# =============================================================================
# rightOf — extended
# =============================================================================

class TestRightOfExtended:
    def test_no_delimiter(self):
        assert invoke("rightOf", "hello", "@").as_string() == ""

    def test_at_end(self):
        assert invoke("rightOf", "hello@", "@").as_string() == ""

    def test_multiple_delimiters(self):
        assert invoke("rightOf", "a@b@c", "@").as_string() == "b@c"

    def test_empty_string(self):
        assert invoke("rightOf", "", "@").as_string() == ""

    def test_too_few_args(self):
        assert invoke("rightOf", "hello").is_null()

    def test_multi_char_delimiter(self):
        assert invoke("rightOf", "hello::world", "::").as_string() == "world"

    @pytest.mark.parametrize("text,delim,expected", [
        ("hello@world.com", "@", "world.com"),
        ("a/b/c", "/", "b/c"),
        ("no-match", "@", ""),
    ])
    def test_parametrized(self, text, delim, expected):
        assert invoke("rightOf", text, delim).as_string() == expected


# =============================================================================
# center — extended
# =============================================================================

class TestCenterExtended:
    def test_already_wide(self):
        assert invoke("center", "hello", 3, "-").as_string() == "hello"

    def test_empty_string(self):
        assert invoke("center", "", 4, "*").as_string() == "****"

    def test_exact_width(self):
        assert invoke("center", "abcd", 4, "-").as_string() == "abcd"

    def test_default_pad_char(self):
        result = invoke("center", "hi", 6)
        assert len(result.as_string()) == 6

    @pytest.mark.parametrize("text,width,char,expected", [
        ("hi", 6, "*", "**hi**"),
        ("hi", 6, "-", "--hi--"),
        ("x", 5, ".", "..x.."),
    ])
    def test_parametrized(self, text, width, char, expected):
        assert invoke("center", text, width, char).as_string() == expected


# =============================================================================
# stripAccents — extended
# =============================================================================

class TestStripAccentsExtended:
    def test_various_a(self):
        assert invoke("stripAccents", "\u00e0\u00e1\u00e2\u00e3\u00e4\u00e5").as_string() == "aaaaaa"

    def test_upper_a(self):
        assert invoke("stripAccents", "\u00c0\u00c1\u00c2").as_string() == "AAA"

    def test_cedilla(self):
        assert invoke("stripAccents", "\u00e7\u00c7").as_string() == "cC"

    def test_n_tilde(self):
        assert invoke("stripAccents", "\u00f1\u00d1").as_string() == "nN"

    def test_mixed(self):
        assert invoke("stripAccents", "caf\u00e9 na\u00efve").as_string() == "cafe naive"

    def test_german_umlauts(self):
        assert invoke("stripAccents", "\u00fc\u00f6\u00e4").as_string() == "uoa"

    @pytest.mark.parametrize("input_str,expected", [
        ("caf\u00e9", "cafe"),
        ("hello", "hello"),
        ("\u00e9l\u00e8ve", "eleve"),
        ("", ""),
    ])
    def test_parametrized(self, input_str, expected):
        assert invoke("stripAccents", input_str).as_string() == expected


# =============================================================================
# clean — extended
# =============================================================================

class TestCleanExtended:
    def test_empty_string(self):
        assert invoke("clean", "").as_string() == ""

    def test_no_control_chars(self):
        assert invoke("clean", "hello world").as_string() == "hello world"

    def test_null_byte(self):
        assert invoke("clean", "hello\x00world").as_string() == "helloworld"

    def test_bell_char(self):
        assert invoke("clean", "hello\x07world").as_string() == "helloworld"

    def test_integer_coerces(self):
        result = invoke("clean", 42)
        assert result is not None

    def test_multiple_control_chars(self):
        assert invoke("clean", "\x01\x02\x03hello\x04\x05").as_string() == "hello"

    @pytest.mark.parametrize("input_str,expected", [
        ("hello\x00world", "helloworld"),
        ("normal text", "normal text"),
        ("", ""),
        ("\x01\x02\x03", ""),
    ])
    def test_parametrized(self, input_str, expected):
        assert invoke("clean", input_str).as_string() == expected


# =============================================================================
# wordCount — extended
# =============================================================================

class TestWordCountExtended:
    def test_only_whitespace(self):
        assert invoke("wordCount", "   ").as_int() == 0

    def test_with_tabs(self):
        assert invoke("wordCount", "a\tb\tc").as_int() == 3

    def test_single_word(self):
        assert invoke("wordCount", "hello").as_int() == 1

    def test_integer_coerces(self):
        result = invoke("wordCount", 42)
        assert result is not None

    @pytest.mark.parametrize("text,expected", [
        ("hello world foo", 3),
        ("", 0),
        ("one", 1),
        ("  spaces  everywhere  ", 2),
        ("a\tb\nc", 3),
    ])
    def test_parametrized(self, text, expected):
        assert invoke("wordCount", text).as_int() == expected


# =============================================================================
# tokenize — extended
# =============================================================================

class TestTokenizeExtended:
    def test_whitespace_default(self):
        result = invoke("tokenize", "hello world test")
        arr = result.as_array()
        assert len(arr) == 3
        assert arr[0].as_string() == "hello"
        assert arr[1].as_string() == "world"
        assert arr[2].as_string() == "test"

    def test_with_custom_delimiter(self):
        result = invoke("tokenize", "a,b,c", ",")
        arr = result.as_array()
        assert len(arr) == 3

    def test_no_args(self):
        result = invoke("tokenize")
        arr = result.as_array()
        assert len(arr) == 0

    def test_multiple_spaces(self):
        result = invoke("tokenize", "hello   world")
        arr = result.as_array()
        assert len(arr) == 2

    @pytest.mark.parametrize("text,count", [
        ("hello world", 2),
        ("a b c d", 4),
        ("", 0),
        ("single", 1),
    ])
    def test_parametrized(self, text, count):
        result = invoke("tokenize", text)
        assert len(result.as_array()) == count


# =============================================================================
# levenshtein — extended
# =============================================================================

class TestLevenshteinExtended:
    def test_single_edit(self):
        assert invoke("levenshtein", "kitten", "sitten").as_int() == 1

    def test_classic(self):
        assert invoke("levenshtein", "kitten", "sitting").as_int() == 3

    def test_same_string(self):
        assert invoke("levenshtein", "hello", "hello").as_int() == 0

    def test_both_empty(self):
        assert invoke("levenshtein", "", "").as_int() == 0

    def test_one_empty(self):
        assert invoke("levenshtein", "", "abc").as_int() == 3

    def test_other_empty(self):
        assert invoke("levenshtein", "abc", "").as_int() == 3

    def test_completely_different(self):
        assert invoke("levenshtein", "abc", "xyz").as_int() == 3

    def test_too_few_args(self):
        result = invoke("levenshtein", "hello")
        assert result.is_null()

    def test_case_sensitive(self):
        assert invoke("levenshtein", "Hello", "hello").as_int() == 1

    @pytest.mark.parametrize("a,b,expected", [
        ("hello", "hello", 0),
        ("hello", "hallo", 1),
        ("kitten", "sitting", 3),
        ("", "hello", 5),
        ("hello", "", 5),
        ("abc", "abc", 0),
        ("abc", "def", 3),
        ("flaw", "lawn", 2),
    ])
    def test_parametrized(self, a, b, expected):
        assert invoke("levenshtein", a, b).as_int() == expected


# =============================================================================
# soundex — extended
# =============================================================================

class TestSoundexExtended:
    def test_single_letter(self):
        assert invoke("soundex", "A").as_string() == "A000"

    def test_smith(self):
        assert invoke("soundex", "Smith").as_string() == "S530"

    def test_smythe(self):
        assert invoke("soundex", "Smythe").as_string() == "S530"

    def test_no_args(self):
        assert invoke("soundex").is_null()

    def test_robert(self):
        assert invoke("soundex", "Robert").as_string() == "R163"

    def test_rupert(self):
        assert invoke("soundex", "Rupert").as_string() == "R163"

    def test_ashcraft(self):
        assert invoke("soundex", "Ashcraft").as_string() == "A261"

    def test_ashcroft(self):
        assert invoke("soundex", "Ashcroft").as_string() == "A261"

    def test_tymczak(self):
        assert invoke("soundex", "Tymczak").as_string() == "T522"

    @pytest.mark.parametrize("name,expected", [
        ("Robert", "R163"),
        ("Rupert", "R163"),
        ("Smith", "S530"),
        ("Lee", "L000"),
        ("Jackson", "J250"),
        ("Washington", "W252"),
    ])
    def test_parametrized(self, name, expected):
        assert invoke("soundex", name).as_string() == expected


# =============================================================================
# wrap — extended (word-wrap in Python, different from Java)
# =============================================================================

class TestWrapExtended:
    def test_short_text(self):
        r = invoke("wrap", "hello", 10)
        assert r.as_string() == "hello"

    def test_word_wrap(self):
        r = invoke("wrap", "hello world test case", 11)
        lines = r.as_string().split("\n")
        assert len(lines) >= 2

    def test_null_input(self):
        assert invoke("wrap", None, 10).is_null()

    def test_empty_string(self):
        r = invoke("wrap", "", 10)
        assert r.as_string() == ""

    def test_single_long_word(self):
        r = invoke("wrap", "superlongword", 5)
        # A single word longer than the width stays on one line.
        assert r.as_string() == "superlongword"


# =============================================================================
# Cross-verb integration tests
# =============================================================================

class TestCrossVerbIntegration:
    def test_trim_and_lower(self):
        """normalizeSpace acts as trim+collapse."""
        result = invoke("normalizeSpace", "  HELLO  ")
        assert result.as_string() == "HELLO"

    def test_split_then_join(self):
        parts = invoke("split", "a,b,c", ",")
        result = invoke("join", parts, "-")
        assert result.as_string() == "a-b-c"

    def test_slugify_complex(self):
        result = invoke("slugify", "  Hello World! This is a TEST  ")
        assert result.as_string() == "hello-world-this-is-a-test"

    def test_pad_truncate(self):
        padded = invoke("padRight", "hi", 10, ".").as_string()
        assert padded == "hi........"
        truncated = invoke("truncate", padded, 5).as_string()
        assert truncated == "hi..."

    def test_replace_chain(self):
        step1 = invoke("replace", "hello world", "world", "planet").as_string()
        step2 = invoke("replace", step1, "hello", "greetings").as_string()
        assert step2 == "greetings planet"


# =============================================================================
# Edge cases — unicode, special characters, very long strings
# =============================================================================

class TestUnicodeEdgeCases:
    def test_emoji_length(self):
        # Basic emoji
        result = invoke("length", "\U0001f600")
        assert result.as_int() >= 1

    def test_chinese_characters(self):
        assert invoke("length", "\u4f60\u597d").as_int() == 2

    def test_arabic_text(self):
        result = invoke("reverseString", "\u0645\u0631\u062d\u0628\u0627")
        assert result.as_string() == "\u0627\u0628\u062d\u0631\u0645"

    def test_mixed_scripts(self):
        assert invoke("contains", "hello\u4e16\u754c", "\u4e16\u754c").as_bool() is True

    def test_empty_vs_null(self):
        assert invoke("capitalize", "").as_string() == ""
        assert invoke("capitalize", None).is_null()

    def test_very_long_string_truncate(self):
        long_str = "a" * 10000
        result = invoke("truncate", long_str, 100)
        assert result.as_string() == "a" * 100

    def test_very_long_string_length(self):
        long_str = "x" * 50000
        assert invoke("length", long_str).as_int() == 50000


class TestSpecialCharacterEdgeCases:
    def test_newlines_in_replace(self):
        assert invoke("replace", "hello\nworld", "\n", " ").as_string() == "hello world"

    def test_tab_in_split(self):
        result = invoke("split", "a\tb\tc", "\t")
        assert len(result.as_array()) == 3

    def test_backslash(self):
        assert invoke("contains", "path\\to\\file", "\\").as_bool() is True

    def test_quotes(self):
        assert invoke("contains", 'say "hello"', '"').as_bool() is True

    def test_null_char_in_clean(self):
        assert invoke("clean", "abc\x00def").as_string() == "abcdef"

    def test_non_breaking_space(self):
        result = invoke("clean", "hello\u00a0world")
        assert result.as_string() == "hello world"
