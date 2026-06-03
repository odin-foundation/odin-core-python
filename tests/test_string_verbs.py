"""Tests for string verbs."""

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


# ── capitalize ────────────────────────────────────────────────────────────────

def test_capitalize_basic():
    assert invoke("capitalize", "hello").as_string() == "Hello"

def test_capitalize_empty():
    assert invoke("capitalize", "").as_string() == ""

def test_capitalize_null():
    assert invoke("capitalize", None).is_null()


# ── titleCase ─────────────────────────────────────────────────────────────────

def test_title_case_basic():
    assert invoke("titleCase", "hello world").as_string() == "Hello World"

def test_title_case_empty():
    assert invoke("titleCase", "").as_string() == ""

def test_title_case_multi_word():
    assert invoke("titleCase", "the quick brown fox").as_string() == "The Quick Brown Fox"

def test_title_case_null():
    assert invoke("titleCase", None).is_null()


# ── contains ──────────────────────────────────────────────────────────────────

def test_contains_basic():
    assert invoke("contains", "hello world", "world").as_bool() is True

def test_contains_not_found():
    assert invoke("contains", "hello", "xyz").as_bool() is False

def test_contains_empty():
    assert invoke("contains", "hello", "").as_bool() is True

def test_contains_null():
    assert invoke("contains", None).as_bool() is False


# ── startsWith / endsWith ─────────────────────────────────────────────────────

def test_starts_with_basic():
    assert invoke("startsWith", "hello world", "hello").as_bool() is True

def test_starts_with_false():
    assert invoke("startsWith", "hello", "world").as_bool() is False

def test_ends_with_basic():
    assert invoke("endsWith", "hello world", "world").as_bool() is True

def test_ends_with_false():
    assert invoke("endsWith", "hello", "xyz").as_bool() is False


# ── replace ───────────────────────────────────────────────────────────────────

def test_replace_basic():
    assert invoke("replace", "hello world", "world", "there").as_string() == "hello there"

def test_replace_not_found():
    assert invoke("replace", "hello", "xyz", "abc").as_string() == "hello"

def test_replace_null():
    assert invoke("replace", None, "a", "b").is_null()

def test_replace_regex_basic():
    assert invoke("replaceRegex", "hello 123 world", r"\d+", "NUM").as_string() == "hello NUM world"


# ── padLeft / padRight / pad ──────────────────────────────────────────────────

def test_pad_left_basic():
    assert invoke("padLeft", "hi", 5, "*").as_string() == "***hi"

def test_pad_left_already_wide():
    assert invoke("padLeft", "hello", 3, "*").as_string() == "hello"

def test_pad_right_basic():
    assert invoke("padRight", "hi", 5, "*").as_string() == "hi***"

def test_pad_right_already_wide():
    assert invoke("padRight", "hello", 3, "*").as_string() == "hello"

def test_pad_right_alias():
    # %pad pads on the right (alias for padRight).
    assert invoke("pad", "hi", 6, "*").as_string() == "hi****"

def test_pad_null():
    assert invoke("padLeft", None).is_null()


# ── truncate ──────────────────────────────────────────────────────────────────

def test_truncate_basic():
    assert invoke("truncate", "hello world", 5).as_string() == "hello"

def test_truncate_no_truncate():
    assert invoke("truncate", "hi", 10).as_string() == "hi"

def test_truncate_with_ellipsis():
    assert invoke("truncate", "hello world", 8, "...").as_string() == "hello..."

def test_truncate_null():
    assert invoke("truncate", None, 5).is_null()


# ── split / join ──────────────────────────────────────────────────────────────

def test_split_basic():
    r = invoke("split", "a,b,c", ",")
    assert r.is_array()
    items = r.as_array()
    assert len(items) == 3
    assert items[0].as_string() == "a"

def test_split_with_index():
    assert invoke("split", "a,b,c", ",", 1).as_string() == "b"

def test_split_null():
    assert invoke("split", None).is_null()

def test_join_basic():
    arr = _to_dyn(["a", "b", "c"])
    r = invoke("join", arr, ",")
    assert r.as_string() == "a,b,c"

def test_join_empty():
    arr = _to_dyn([])
    r = invoke("join", arr, ",")
    assert r.as_string() == ""


# ── mask ──────────────────────────────────────────────────────────────────────

def test_mask_basic():
    assert invoke("mask", "1234567890", "(###) ###-####").as_string() == "(123) 456-7890"

def test_mask_null():
    assert invoke("mask", None, "###").is_null()


# ── reverseString ─────────────────────────────────────────────────────────────

def test_reverse_basic():
    assert invoke("reverseString", "hello").as_string() == "olleh"

def test_reverse_empty():
    assert invoke("reverseString", "").as_string() == ""

def test_reverse_single():
    assert invoke("reverseString", "a").as_string() == "a"

def test_reverse_null():
    assert invoke("reverseString", None).is_null()


# ── repeat ────────────────────────────────────────────────────────────────────

def test_repeat_basic():
    assert invoke("repeat", "ab", 3).as_string() == "ababab"

def test_repeat_zero():
    assert invoke("repeat", "ab", 0).as_string() == ""

def test_repeat_negative():
    assert invoke("repeat", "ab", -1).is_null()

def test_repeat_null():
    assert invoke("repeat", None, 3).is_null()


# ── substring ─────────────────────────────────────────────────────────────────

def test_substring_basic():
    assert invoke("substring", "hello world", 6).as_string() == "world"

def test_substring_with_length():
    assert invoke("substring", "hello world", 0, 5).as_string() == "hello"

def test_substring_null():
    assert invoke("substring", None).is_null()


# ── length ────────────────────────────────────────────────────────────────────

def test_length_string():
    assert invoke("length", "hello").as_int() == 5

def test_length_array():
    assert invoke("length", _to_dyn([1, 2, 3])).as_int() == 3

def test_length_null():
    assert invoke("length", None).as_int() == 0

def test_length_object():
    assert invoke("length", _to_dyn({"a": 1, "b": 2})).as_int() == 2


# ── camelCase / snakeCase / kebabCase / pascalCase ────────────────────────────

def test_camel_case_basic():
    assert invoke("camelCase", "hello_world").as_string() == "helloWorld"

def test_camel_case_from_kebab():
    assert invoke("camelCase", "hello-world").as_string() == "helloWorld"

def test_camel_case_from_spaces():
    assert invoke("camelCase", "Hello World").as_string() == "helloWorld"

def test_camel_case_null():
    assert invoke("camelCase", None).is_null()

def test_camel_case_empty():
    assert invoke("camelCase", "").as_string() == ""

def test_snake_case_basic():
    assert invoke("snakeCase", "helloWorld").as_string() == "hello_world"

def test_snake_case_from_kebab():
    assert invoke("snakeCase", "hello-world").as_string() == "hello_world"

def test_snake_case_null():
    assert invoke("snakeCase", None).is_null()

def test_kebab_case_basic():
    assert invoke("kebabCase", "helloWorld").as_string() == "hello-world"

def test_kebab_case_from_snake():
    assert invoke("kebabCase", "hello_world").as_string() == "hello-world"

def test_kebab_case_null():
    assert invoke("kebabCase", None).is_null()

def test_pascal_case_basic():
    assert invoke("pascalCase", "hello_world").as_string() == "HelloWorld"

def test_pascal_case_from_kebab():
    assert invoke("pascalCase", "hello-world").as_string() == "HelloWorld"

def test_pascal_case_null():
    assert invoke("pascalCase", None).is_null()


# ── slugify ───────────────────────────────────────────────────────────────────

def test_slugify_basic():
    assert invoke("slugify", "Hello World!").as_string() == "hello-world"

def test_slugify_accents():
    assert invoke("slugify", "Caf\u00e9 Latt\u00e9").as_string() == "caf-latt"

def test_slugify_null():
    assert invoke("slugify", None).is_null()


# ── match / matches / extract ─────────────────────────────────────────────────

def test_match_basic():
    r = invoke("match", "hello 123 world", r"\d+")
    assert r.as_bool() is True

def test_match_no_match():
    assert invoke("match", "hello", r"\d+").as_bool() is False

def test_matches_basic():
    assert invoke("matches", "hello 123", r"\d+").as_bool() is True

def test_matches_no_match():
    assert invoke("matches", "hello", r"\d+").as_bool() is False

def test_extract_basic():
    r = invoke("extract", "hello 123 world", r"(\d+)")
    assert r.as_string() == "123"

def test_extract_group():
    r = invoke("extract", "2024-01-15", r"(\d{4})-(\d{2})-(\d{2})", 1)
    assert r.as_string() == "2024"


# ── normalizeSpace ────────────────────────────────────────────────────────────

def test_normalize_space_basic():
    assert invoke("normalizeSpace", "  hello   world  ").as_string() == "hello world"

def test_normalize_space_tabs():
    assert invoke("normalizeSpace", "\thello\t\tworld\t").as_string() == "hello world"

def test_normalize_space_null():
    assert invoke("normalizeSpace", None).is_null()


# ── leftOf / rightOf ──────────────────────────────────────────────────────────

def test_left_of_basic():
    assert invoke("leftOf", "hello@world.com", "@").as_string() == "hello"

def test_left_of_not_found():
    assert invoke("leftOf", "hello", "@").as_string() == "hello"

def test_right_of_basic():
    assert invoke("rightOf", "hello@world.com", "@").as_string() == "world.com"

def test_right_of_not_found():
    assert invoke("rightOf", "hello", "@").as_string() == ""


# ── wrap / center ─────────────────────────────────────────────────────────────

def test_wrap_basic():
    # Short text within width is returned unchanged.
    r = invoke("wrap", "hello", 10)
    assert r.as_string() == "hello"

def test_wrap_default_suffix():
    # Long text wraps onto newline-separated lines.
    r = invoke("wrap", "hello world this is a long string", 10)
    assert "\n" in r.as_string()

def test_wrap_null():
    assert invoke("wrap", None, "(").is_null()

def test_center_basic():
    r = invoke("center", "hi", 6, "*")
    assert r.as_string() == "**hi**"

def test_center_already_wide():
    assert invoke("center", "hello", 3, "*").as_string() == "hello"


# ── stripAccents ──────────────────────────────────────────────────────────────

def test_strip_accents_basic():
    assert invoke("stripAccents", "caf\u00e9").as_string() == "cafe"

def test_strip_accents_no_accents():
    assert invoke("stripAccents", "hello").as_string() == "hello"

def test_strip_accents_null():
    assert invoke("stripAccents", None).is_null()


# ── clean ─────────────────────────────────────────────────────────────────────

def test_clean_basic():
    assert invoke("clean", "hello\x00world").as_string() == "helloworld"

def test_clean_keeps_tab_newline():
    assert invoke("clean", "hello\tworld\n").as_string() == "hello world"

def test_clean_null():
    assert invoke("clean", None).is_null()


# ── wordCount / tokenize ──────────────────────────────────────────────────────

def test_word_count_basic():
    assert invoke("wordCount", "hello world foo").as_int() == 3

def test_word_count_empty():
    assert invoke("wordCount", "").as_int() == 0

def test_word_count_null():
    assert invoke("wordCount", None).as_int() == 0

def test_tokenize_basic():
    r = invoke("tokenize", "hello world foo")
    assert r.is_array()
    items = r.as_array()
    assert len(items) == 3
    assert items[0].as_string() == "hello"

def test_tokenize_empty():
    r = invoke("tokenize", "")
    assert r.is_array()
    assert len(r.as_array()) == 0

def test_tokenize_null():
    r = invoke("tokenize", None)
    assert r.is_array()
    assert len(r.as_array()) == 0


# ── levenshtein ───────────────────────────────────────────────────────────────

def test_levenshtein_exact():
    assert invoke("levenshtein", "hello", "hello").as_int() == 0

def test_levenshtein_one():
    assert invoke("levenshtein", "hello", "hallo").as_int() == 1

def test_levenshtein_multiple():
    assert invoke("levenshtein", "kitten", "sitting").as_int() == 3

def test_levenshtein_empty():
    assert invoke("levenshtein", "", "hello").as_int() == 5

def test_levenshtein_null():
    assert invoke("levenshtein", None, "hello").is_null()


# ── soundex ───────────────────────────────────────────────────────────────────

def test_soundex_basic():
    assert invoke("soundex", "Robert").as_string() == "R163"

def test_soundex_null():
    assert invoke("soundex", None).is_null()

def test_soundex_empty():
    assert invoke("soundex", "").is_null()

def test_soundex_ashcraft():
    assert invoke("soundex", "Ashcraft").as_string() == "A261"
