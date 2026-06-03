"""Extended tests for collection verbs — ported from Java CollectionVerbTest + CollectionVerbExtendedTest.

Goal: increase Python collection verb test coverage to match Java's ~475 tests.
"""

import pytest
from odin.transform.dyn_value import DynValue, DynType
from odin.transform.engine import TransformEngine
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


def _arr_ints(result):
    return [item._int_value for item in result.as_array()]


def _arr_floats(result):
    return [item._float_value if item.type == DynType.FLOAT else float(item._int_value) for item in result.as_array()]


def _arr_strs(result):
    return [item.as_string() for item in result.as_array()]


def _arr_len(result):
    return len(result.as_array())


# ==========================================================================
# flatten -- extended
# ==========================================================================

class TestFlattenExtended:
    def test_empty_array(self):
        r = invoke("flatten", [])
        assert _arr_len(r) == 0

    def test_all_scalars(self):
        r = invoke("flatten", [1, 2, 3])
        assert _arr_len(r) == 3
        assert _arr_ints(r) == [1, 2, 3]

    def test_single_level_only(self):
        """Only flattens one level deep."""
        r = invoke("flatten", [[[1]]])
        assert _arr_len(r) == 1
        inner = r.as_array()[0]
        assert inner.is_array()

    def test_mixed_nested_and_scalar(self):
        r = invoke("flatten", [1, [2, 3], 4])
        assert _arr_len(r) == 4

    def test_with_nulls(self):
        r = invoke("flatten", [None, [1]])
        arr = r.as_array()
        assert len(arr) == 2
        assert arr[0].is_null()
        assert arr[1]._int_value == 1

    def test_multiple_nested_arrays(self):
        r = invoke("flatten", [[1, 2], [3, 4], [5]])
        assert _arr_ints(r) == [1, 2, 3, 4, 5]

    def test_empty_inner_arrays(self):
        r = invoke("flatten", [[], [1], []])
        assert _arr_ints(r) == [1]

    def test_strings_and_arrays(self):
        r = invoke("flatten", ["a", ["b", "c"]])
        assert _arr_strs(r) == ["a", "b", "c"]

    def test_single_element_array(self):
        r = invoke("flatten", [[42]])
        assert _arr_ints(r) == [42]


# ==========================================================================
# distinct / unique -- extended
# ==========================================================================

class TestDistinctExtended:
    def test_empty(self):
        assert _arr_len(invoke("distinct", [])) == 0

    def test_single_element(self):
        assert _arr_len(invoke("distinct", [42])) == 1

    def test_all_same(self):
        r = invoke("distinct", ["a", "a", "a"])
        assert _arr_len(r) == 1
        assert _arr_strs(r) == ["a"]

    def test_preserves_order(self):
        r = invoke("distinct", [3, 1, 2, 1, 3])
        assert _arr_ints(r) == [3, 1, 2]

    def test_with_nulls(self):
        r = invoke("distinct", [None, 1, None, 2])
        assert _arr_len(r) == 3

    def test_strings_case_sensitive(self):
        r = invoke("distinct", ["abc", "ABC", "abc"])
        assert _arr_len(r) == 2

    def test_booleans(self):
        r = invoke("distinct", [True, False, True])
        assert _arr_len(r) == 2

    def test_mixed_types(self):
        # coerce_str maps 1 and True both to "1", so they dedupe
        r = invoke("distinct", [1, "1", True, None])
        assert _arr_len(r) == 3  # 1, "1"/True collide, None

    def test_unique_alias(self):
        r = invoke("unique", [1, 2, 1])
        assert _arr_len(r) == 2


# ==========================================================================
# sort -- extended
# ==========================================================================

class TestSortExtended:
    def test_empty(self):
        assert _arr_len(invoke("sort", [])) == 0

    def test_single(self):
        r = invoke("sort", [42])
        assert _arr_ints(r) == [42]

    def test_floats(self):
        r = invoke("sort", [3.1, 1.5, 2.7])
        vals = _arr_floats(r)
        assert vals == pytest.approx([1.5, 2.7, 3.1])

    def test_already_sorted(self):
        r = invoke("sort", [1, 2, 3])
        assert _arr_ints(r) == [1, 2, 3]

    def test_reverse_order(self):
        r = invoke("sort", [3, 2, 1])
        assert _arr_ints(r) == [1, 2, 3]

    def test_with_duplicates(self):
        r = invoke("sort", [2, 1, 2, 1])
        assert _arr_ints(r) == [1, 1, 2, 2]

    def test_strings_case_sensitive(self):
        r = invoke("sort", ["banana", "Apple", "cherry"])
        assert _arr_strs(r) == ["Apple", "banana", "cherry"]

    def test_mixed_int_float(self):
        r = invoke("sort", _to_dyn([]),)
        # Use DynValue directly
        arr = DynValue.of_array([DynValue.of_float(2.5), DynValue.of_integer(1), DynValue.of_integer(3)])
        r = invoke("sort", arr)
        vals = _arr_floats(r)
        assert vals[0] == pytest.approx(1.0)
        assert vals[1] == pytest.approx(2.5)
        assert vals[2] == pytest.approx(3.0)

    def test_negative_numbers(self):
        r = invoke("sort", [-3, -1, -2])
        assert _arr_ints(r) == [-3, -2, -1]

    def test_large_array(self):
        data = list(range(100, 0, -1))
        r = invoke("sort", data)
        assert _arr_ints(r) == list(range(1, 101))


# ==========================================================================
# sortDesc -- extended
# ==========================================================================

class TestSortDescExtended:
    def test_empty(self):
        assert _arr_len(invoke("sortDesc", [])) == 0

    def test_strings(self):
        r = invoke("sortDesc", ["a", "c", "b"])
        assert _arr_strs(r) == ["c", "b", "a"]

    def test_floats(self):
        r = invoke("sortDesc", [1.1, 3.3, 2.2])
        vals = _arr_floats(r)
        assert vals == pytest.approx([3.3, 2.2, 1.1])

    def test_single(self):
        r = invoke("sortDesc", [5])
        assert _arr_ints(r) == [5]

    def test_preserves_all_elements(self):
        r = invoke("sortDesc", [3, 1, 4, 1, 5])
        assert _arr_ints(r) == [5, 4, 3, 1, 1]

    def test_already_descending(self):
        r = invoke("sortDesc", [3, 2, 1])
        assert _arr_ints(r) == [3, 2, 1]

    def test_negative_numbers(self):
        r = invoke("sortDesc", [-1, -3, -2])
        assert _arr_ints(r) == [-1, -2, -3]


# ==========================================================================
# sortBy -- extended
# ==========================================================================

class TestSortByExtended:
    def test_numeric_field(self):
        items = [{"n": 3}, {"n": 1}, {"n": 2}]
        r = invoke("sortBy", items, "n")
        arr = r.as_array()
        assert arr[0].get("n")._int_value == 1
        assert arr[2].get("n")._int_value == 3

    def test_string_field(self):
        items = [{"name": "Charlie"}, {"name": "Alice"}, {"name": "Bob"}]
        r = invoke("sortBy", items, "name")
        arr = r.as_array()
        assert arr[0].get("name").as_string() == "Alice"
        assert arr[1].get("name").as_string() == "Bob"
        assert arr[2].get("name").as_string() == "Charlie"

    def test_empty_array(self):
        r = invoke("sortBy", [], "x")
        assert _arr_len(r) == 0

    def test_missing_field(self):
        items = [{"a": 2}, {"b": 1}]
        r = invoke("sortBy", items, "a")
        assert _arr_len(r) == 2

    def test_single_element(self):
        r = invoke("sortBy", [{"x": 5}], "x")
        assert _arr_len(r) == 1

    def test_all_same_field_value(self):
        items = [{"v": 1, "name": "A"}, {"v": 1, "name": "B"}]
        r = invoke("sortBy", items, "v")
        assert _arr_len(r) == 2


# ==========================================================================
# map / pluck -- extended
# ==========================================================================

class TestMapExtended:
    def test_missing_field_gives_null(self):
        items = [{"a": 1}]
        r = invoke("map", items, "b")
        assert r.as_array()[0].is_null()

    def test_empty_array(self):
        assert _arr_len(invoke("map", [], "x")) == 0

    def test_all_missing_fields(self):
        items = [{"a": 1}, {"a": 2}]
        r = invoke("map", items, "z")
        assert r.as_array()[0].is_null()
        assert r.as_array()[1].is_null()

    def test_mixed_present_missing(self):
        items = [{"x": 10}, {"y": 20}, {"x": 30}]
        r = invoke("map", items, "x")
        arr = r.as_array()
        assert arr[0]._int_value == 10
        assert arr[1].is_null()
        assert arr[2]._int_value == 30

    def test_nested_field_dot_notation(self):
        items = [{"a": {"b": 1}}, {"a": {"b": 2}}]
        r = invoke("map", items, "a.b")
        assert _arr_ints(r) == [1, 2]


class TestPluckExtended:
    def test_empty_array(self):
        assert _arr_len(invoke("pluck", [], "x")) == 0

    def test_extracts_field(self):
        items = [{"name": "A", "age": 10}, {"name": "B", "age": 20}]
        r = invoke("pluck", items, "age")
        assert _arr_ints(r) == [10, 20]

    def test_missing_field_gives_null(self):
        items = [{"x": 1}]
        r = invoke("pluck", items, "y")
        assert r.as_array()[0].is_null()

    def test_string_values(self):
        items = [{"color": "red"}, {"color": "blue"}]
        r = invoke("pluck", items, "color")
        assert _arr_strs(r) == ["red", "blue"]


# ==========================================================================
# indexOf -- extended
# ==========================================================================

class TestIndexOfExtended:
    def test_first_occurrence(self):
        r = invoke("indexOf", [1, 2, 1], 1)
        assert r._int_value == 0

    def test_empty_array(self):
        r = invoke("indexOf", [], 1)
        assert r._int_value == -1

    def test_string_value(self):
        r = invoke("indexOf", ["hello", "world"], "world")
        assert r._int_value == 1

    def test_boolean_value(self):
        r = invoke("indexOf", [True, False, True], False)
        assert r._int_value == 1

    def test_null_value(self):
        r = invoke("indexOf", [1, None, 3], None)
        assert r._int_value == 1

    def test_last_element(self):
        r = invoke("indexOf", [10, 20, 30], 30)
        assert r._int_value == 2

    def test_single_element_found(self):
        r = invoke("indexOf", [42], 42)
        assert r._int_value == 0

    def test_single_element_not_found(self):
        r = invoke("indexOf", [42], 99)
        assert r._int_value == -1


# ==========================================================================
# at -- extended
# ==========================================================================

class TestAtExtended:
    def test_first_element(self):
        r = invoke("at", ["first", "second"], 0)
        assert r.as_string() == "first"

    def test_last_element(self):
        r = invoke("at", [1, 2, 3], 2)
        assert r._int_value == 3

    def test_empty_array(self):
        r = invoke("at", [], 0)
        assert r.is_null()

    def test_negative_index_minus_one(self):
        r = invoke("at", [10, 20, 30], -1)
        assert r._int_value == 30

    def test_negative_index_minus_two(self):
        r = invoke("at", [10, 20, 30], -2)
        assert r._int_value == 20

    def test_negative_index_minus_three(self):
        r = invoke("at", [10, 20, 30], -3)
        assert r._int_value == 10

    def test_negative_out_of_bounds(self):
        r = invoke("at", [1, 2], -5)
        assert r.is_null()

    def test_string_element(self):
        r = invoke("at", ["a", "b", "c"], 1)
        assert r.as_string() == "b"

    def test_single_element(self):
        r = invoke("at", [42], 0)
        assert r._int_value == 42


# ==========================================================================
# slice -- extended
# ==========================================================================

class TestSliceExtended:
    def test_empty_range(self):
        r = invoke("slice", [1, 2], 1, 1)
        assert _arr_len(r) == 0

    def test_clamps_end(self):
        r = invoke("slice", [1, 2], 0, 100)
        assert _arr_len(r) == 2

    def test_full_array(self):
        r = invoke("slice", [1, 2, 3], 0, 3)
        assert _arr_ints(r) == [1, 2, 3]

    def test_empty_array(self):
        r = invoke("slice", [], 0, 0)
        assert _arr_len(r) == 0

    def test_start_past_length(self):
        r = invoke("slice", [1], 5, 10)
        assert _arr_len(r) == 0

    def test_negative_start(self):
        r = invoke("slice", [1, 2, 3, 4, 5], -2)
        assert _arr_len(r) == 2

    def test_negative_end(self):
        r = invoke("slice", [1, 2, 3, 4, 5], 1, -1)
        assert _arr_len(r) == 3
        assert _arr_ints(r) == [2, 3, 4]

    def test_from_start(self):
        r = invoke("slice", [10, 20, 30, 40], 0, 2)
        assert _arr_ints(r) == [10, 20]

    def test_to_end(self):
        r = invoke("slice", [10, 20, 30, 40], 2)
        assert _arr_ints(r) == [30, 40]


# ==========================================================================
# reverse -- extended
# ==========================================================================

class TestReverseExtended:
    def test_empty(self):
        assert _arr_len(invoke("reverse", [])) == 0

    def test_single(self):
        r = invoke("reverse", [1])
        assert _arr_ints(r) == [1]

    def test_strings(self):
        r = invoke("reverse", ["a", "b", "c"])
        assert _arr_strs(r) == ["c", "b", "a"]

    def test_two_elements(self):
        r = invoke("reverse", [1, 2])
        assert _arr_ints(r) == [2, 1]

    def test_with_nulls(self):
        r = invoke("reverse", [1, None, 3])
        arr = r.as_array()
        assert arr[0]._int_value == 3
        assert arr[1].is_null()
        assert arr[2]._int_value == 1

    def test_large_array(self):
        data = list(range(50))
        r = invoke("reverse", data)
        assert _arr_ints(r) == list(range(49, -1, -1))

    def test_palindrome(self):
        r = invoke("reverse", [1, 2, 1])
        assert _arr_ints(r) == [1, 2, 1]


# ==========================================================================
# filter -- extended
# ==========================================================================

class TestFilterExtended:
    # -- truthy filter (1-arg) --
    def test_truthy_elements(self):
        r = invoke("filter", [1, None, 0, "hello", "", True, False])
        assert _arr_len(r) == 3  # 1, "hello", True

    def test_empty_array(self):
        assert _arr_len(invoke("filter", [])) == 0

    def test_all_truthy(self):
        r = invoke("filter", [1, 2, 3])
        assert _arr_len(r) == 3

    def test_all_falsy(self):
        r = invoke("filter", [None, 0, ""])
        assert _arr_len(r) == 0

    # -- filter by field truthiness (2-arg) --
    def test_by_field_name(self):
        items = [
            {"active": True, "name": "A"},
            {"active": False, "name": "B"},
            {"active": True, "name": "C"},
        ]
        r = invoke("filter", items, "active")
        assert _arr_len(r) == 2

    def test_by_numeric_field(self):
        items = [{"score": 0}, {"score": 10}, {"score": 5}]
        r = invoke("filter", items, "score")
        assert _arr_len(r) == 2

    def test_by_missing_field(self):
        items = [{"a": 1}, {"b": 2}]
        r = invoke("filter", items, "a")
        assert _arr_len(r) == 1

    # -- 4-arg filter: array, field, op, value --
    def test_eq_operator(self):
        items = [{"status": "active"}, {"status": "inactive"}, {"status": "active"}]
        r = invoke("filter", items, "status", "=", "active")
        assert _arr_len(r) == 2

    def test_eq_double_equals(self):
        items = [{"v": 1}, {"v": 2}, {"v": 1}]
        r = invoke("filter", items, "v", "==", 1)
        assert _arr_len(r) == 2

    def test_ne_operator(self):
        items = [{"v": 1}, {"v": 2}, {"v": 3}]
        r = invoke("filter", items, "v", "!=", 2)
        assert _arr_len(r) == 2

    def test_ne_diamond(self):
        items = [{"v": 1}, {"v": 2}]
        r = invoke("filter", items, "v", "<>", 1)
        assert _arr_len(r) == 1

    def test_gt_operator(self):
        items = [{"age": 25}, {"age": 35}, {"age": 20}]
        r = invoke("filter", items, "age", ">", 22)
        assert _arr_len(r) == 2

    def test_gte_operator(self):
        items = [{"v": 1}, {"v": 2}, {"v": 3}]
        r = invoke("filter", items, "v", ">=", 2)
        assert _arr_len(r) == 2

    def test_lt_operator(self):
        items = [{"v": 10}, {"v": 20}, {"v": 30}]
        r = invoke("filter", items, "v", "<", 25)
        assert _arr_len(r) == 2

    def test_lte_operator(self):
        items = [{"v": 10}, {"v": 20}, {"v": 30}]
        r = invoke("filter", items, "v", "<=", 20)
        assert _arr_len(r) == 2

    def test_contains_operator(self):
        items = [{"name": "Alice"}, {"name": "Bob"}, {"name": "Alicia"}]
        r = invoke("filter", items, "name", "contains", "lic")
        assert _arr_len(r) == 2

    def test_startswith_operator(self):
        items = [{"name": "Alice"}, {"name": "Bob"}, {"name": "Alicia"}]
        r = invoke("filter", items, "name", "startsWith", "Al")
        assert _arr_len(r) == 2

    def test_endswith_operator(self):
        items = [{"name": "Alice"}, {"name": "Bob"}, {"name": "Grace"}]
        r = invoke("filter", items, "name", "endsWith", "ce")
        assert _arr_len(r) == 2

    def test_no_matches(self):
        items = [{"v": 1}, {"v": 2}]
        r = invoke("filter", items, "v", ">", 100)
        assert _arr_len(r) == 0

    def test_all_match(self):
        items = [{"v": 10}, {"v": 20}]
        r = invoke("filter", items, "v", ">", 0)
        assert _arr_len(r) == 2

    def test_string_comparison_gt(self):
        items = [{"name": "apple"}, {"name": "cherry"}, {"name": "banana"}]
        r = invoke("filter", items, "name", ">", "banana")
        assert _arr_len(r) == 1  # "cherry"

    def test_float_comparison(self):
        items = [{"v": 1.5}, {"v": 2.5}, {"v": 3.5}]
        r = invoke("filter", items, "v", ">=", 2.5)
        assert _arr_len(r) == 2


# ==========================================================================
# every -- extended
# ==========================================================================

class TestEveryExtended:
    def test_all_match(self):
        items = [{"v": 10}, {"v": 20}]
        assert invoke("every", items, "v", ">", 5)._bool_value is True

    def test_has_non_match(self):
        items = [{"v": 10}, {"v": 1}]
        assert invoke("every", items, "v", ">", 5)._bool_value is False

    def test_empty_is_true(self):
        assert invoke("every", [], "v", ">", 5)._bool_value is True

    def test_with_field_truthy(self):
        items = [{"v": 10}, {"v": 20}]
        assert invoke("every", items, "v", "=", 10)._bool_value is False

    def test_non_array_null(self):
        assert invoke("every", "x", "v", "=", 1).is_null()

    def test_all_true_booleans(self):
        items = [{"v": "active"}, {"v": "active"}]
        assert invoke("every", items, "v", "=", "active")._bool_value is True

    def test_single_truthy(self):
        assert invoke("every", [{"v": 1}], "v", "=", 1)._bool_value is True


# ==========================================================================
# some -- extended
# ==========================================================================

class TestSomeExtended:
    def test_one_matches(self):
        items = [{"v": 0}, {"v": 0}, {"v": 1}]
        assert invoke("some", items, "v", "=", 1)._bool_value is True

    def test_none_match(self):
        items = [{"v": 0}, {"v": 0}]
        assert invoke("some", items, "v", "=", 1)._bool_value is False

    def test_empty_is_false(self):
        assert invoke("some", [], "v", "=", 1)._bool_value is False

    def test_all_truthy(self):
        items = [{"v": 1}, {"v": 2}]
        assert invoke("some", items, "v", ">", 0)._bool_value is True

    def test_with_field(self):
        items = [{"v": 0}, {"v": 10}]
        assert invoke("some", items, "v", "=", 10)._bool_value is True

    def test_all_falsy_field(self):
        items = [{"v": 0}, {"v": 0}]
        assert invoke("some", items, "v", "=", 10)._bool_value is False

    def test_single_true(self):
        assert invoke("some", [{"v": 1}], "v", "=", 1)._bool_value is True

    def test_single_false(self):
        assert invoke("some", [{"v": 0}], "v", "=", 1)._bool_value is False


# ==========================================================================
# find -- extended
# ==========================================================================

class TestFindExtended:
    def test_with_field(self):
        items = [{"n": "a", "v": 0}, {"n": "b", "v": 1}]
        r = invoke("find", items, "v", "=", 1)
        assert r.get("n").as_string() == "b"

    def test_no_match_returns_null(self):
        items = [{"v": 0}, {"v": 1}]
        r = invoke("find", items, "v", "=", 99)
        assert r.is_null()

    def test_empty_array(self):
        assert invoke("find", [], "v", "=", 1).is_null()

    def test_returns_first(self):
        items = [{"s": "x"}, {"s": "y"}, {"s": "y"}]
        r = invoke("find", items, "s", "=", "y")
        assert r is items[1] or r.get("s").as_string() == "y"

    def test_single_match(self):
        items = [{"v": 42}]
        r = invoke("find", items, "v", "=", 42)
        assert r.get("v")._int_value == 42

    def test_single_no_match(self):
        assert invoke("find", [{"v": 0}], "v", "=", 1).is_null()


# ==========================================================================
# findIndex -- extended
# ==========================================================================

class TestFindIndexExtended:
    def test_found(self):
        items = [{"v": 0}, {"v": 0}, {"v": 1}]
        r = invoke("findIndex", items, "v", "=", 1)
        assert r._int_value == 2

    def test_not_found(self):
        items = [{"v": 0}, {"v": 0}]
        r = invoke("findIndex", items, "v", "=", 1)
        assert r._int_value == -1

    def test_empty_array(self):
        r = invoke("findIndex", [], "v", "=", 1)
        assert r._int_value == -1

    def test_first_match(self):
        items = [{"v": 0}, {"v": 5}, {"v": 10}]
        r = invoke("findIndex", items, "v", "=", 5)
        assert r._int_value == 1

    def test_with_field(self):
        items = [{"v": 0}, {"v": 10}]
        r = invoke("findIndex", items, "v", "=", 10)
        assert r._int_value == 1


# ==========================================================================
# includes -- extended
# ==========================================================================

class TestIncludesExtended:
    def test_string_present(self):
        assert invoke("includes", ["hello", "world"], "hello")._bool_value is True

    def test_integer_present(self):
        assert invoke("includes", [1, 2, 3], 2)._bool_value is True

    def test_float_present(self):
        r = invoke("includes",
                    DynValue.of_array([DynValue.of_float(1.5), DynValue.of_float(2.5)]),
                    DynValue.of_float(2.5))
        assert r._bool_value is True

    def test_bool_absent(self):
        assert invoke("includes", [True], False)._bool_value is False

    def test_null_in_array(self):
        assert invoke("includes", [1, None, 3], None)._bool_value is True

    def test_empty_array(self):
        assert invoke("includes", [], 1)._bool_value is False

    def test_string_absent(self):
        assert invoke("includes", ["a", "b"], "c")._bool_value is False

    def test_single_element_found(self):
        assert invoke("includes", [42], 42)._bool_value is True


# ==========================================================================
# concatArrays -- extended
# ==========================================================================

class TestConcatArraysExtended:
    def test_two_arrays(self):
        r = invoke("concatArrays", [1, 2], [3, 4])
        assert _arr_ints(r) == [1, 2, 3, 4]

    def test_with_empty(self):
        r = invoke("concatArrays", [1], [])
        assert _arr_len(r) == 1

    def test_both_empty(self):
        assert _arr_len(invoke("concatArrays", [], [])) == 0

    def test_first_empty(self):
        r = invoke("concatArrays", [], [1])
        assert _arr_len(r) == 1

    def test_mixed_types(self):
        r = invoke("concatArrays", [1, "two"], [True, None])
        assert _arr_len(r) == 4

    def test_preserves_order(self):
        r = invoke("concatArrays", [1, 2], [3, 4])
        assert _arr_ints(r) == [1, 2, 3, 4]

    def test_nested_arrays(self):
        r = invoke("concatArrays", [[1]], [[2]])
        assert _arr_len(r) == 2


# ==========================================================================
# zip -- extended
# ==========================================================================

def _group_items(result, key):
    """Look up a group's items in the array-of-{key, items} groupBy result."""
    for g in result.as_array():
        if g.get("key").as_string() == str(key):
            return g.get("items")
    return None


class TestZipExtended:
    def test_equal_length(self):
        r = invoke("zip", [1, 2], ["a", "b"])
        assert _arr_len(r) == 2
        first = r.as_array()[0].as_array()
        assert first[0]._int_value == 1
        assert first[1].as_string() == "a"

    def test_unequal_stops_at_shorter(self):
        r = invoke("zip", [1, 2, 3], ["a"])
        assert _arr_len(r) == 1
        assert r.as_array()[0].as_array()[1].as_string() == "a"

    def test_both_empty(self):
        assert _arr_len(invoke("zip", [], [])) == 0

    def test_single_elements(self):
        r = invoke("zip", [1], ["a"])
        assert _arr_len(r) == 1
        pair = r.as_array()[0].as_array()
        assert pair[0]._int_value == 1
        assert pair[1].as_string() == "a"

    def test_mixed_types(self):
        r = invoke("zip", [1, "two"], [True, None])
        assert _arr_len(r) == 2

    def test_first_longer(self):
        r = invoke("zip", [1, 2, 3], ["x"])
        assert _arr_len(r) == 1
        assert r.as_array()[0].as_array()[1].as_string() == "x"

    def test_second_longer(self):
        r = invoke("zip", [1], ["a", "b", "c"])
        assert _arr_len(r) == 1
        assert r.as_array()[0].as_array()[0]._int_value == 1


# ==========================================================================
# groupBy -- extended
# ==========================================================================

class TestGroupByExtended:
    def test_empty_array(self):
        r = invoke("groupBy", [], "key")
        assert r.is_array()
        assert _arr_len(r) == 0

    def test_single_group(self):
        items = [{"type": "A", "v": 1}, {"type": "A", "v": 2}]
        r = invoke("groupBy", items, "type")
        assert r.is_array()
        a = _group_items(r, "A")
        assert a is not None
        assert _arr_len(a) == 2

    def test_missing_field_uses_null_key(self):
        items = [{"v": 1}, {"type": "A", "v": 2}]
        r = invoke("groupBy", items, "type")
        assert r.is_array()
        assert _arr_len(r) == 2

    def test_integer_field(self):
        items = [{"score": 10}, {"score": 20}, {"score": 10}]
        r = invoke("groupBy", items, "score")
        assert r.is_array()
        assert _arr_len(_group_items(r, 10)) == 2

    def test_bool_field(self):
        items = [
            {"active": True, "name": "A"},
            {"active": False, "name": "B"},
            {"active": True, "name": "C"},
        ]
        r = invoke("groupBy", items, "active")
        assert r.is_array()
        assert _arr_len(r) == 2

    def test_all_same_key(self):
        items = [{"k": "x", "v": 1}, {"k": "x", "v": 2}]
        r = invoke("groupBy", items, "k")
        x = _group_items(r, "x")
        assert x is not None
        assert _arr_len(x) == 2

    def test_all_unique_keys(self):
        items = [{"k": "a"}, {"k": "b"}, {"k": "c"}]
        r = invoke("groupBy", items, "k")
        assert _group_items(r, "a") is not None
        assert _group_items(r, "b") is not None
        assert _group_items(r, "c") is not None

    def test_three_groups(self):
        items = [
            {"color": "red"}, {"color": "blue"}, {"color": "green"},
            {"color": "red"}, {"color": "blue"},
        ]
        r = invoke("groupBy", items, "color")
        assert _arr_len(_group_items(r, "red")) == 2
        assert _arr_len(_group_items(r, "blue")) == 2
        assert _arr_len(_group_items(r, "green")) == 1


# ==========================================================================
# partition -- extended
# ==========================================================================

class TestPartitionExtended:
    def test_all_match(self):
        items = [{"v": 1}, {"v": 1}, {"v": 1}]
        r = invoke("partition", items, "v", "=", 1)
        parts = r.as_array()
        assert _arr_len(parts[0]) == 3
        assert _arr_len(parts[1]) == 0

    def test_none_match(self):
        items = [{"v": 0}, {"v": 0}, {"v": 0}]
        r = invoke("partition", items, "v", "=", 1)
        parts = r.as_array()
        assert _arr_len(parts[0]) == 0
        assert _arr_len(parts[1]) == 3

    def test_empty(self):
        r = invoke("partition", [], "v", "=", 1)
        parts = r.as_array()
        assert _arr_len(parts[0]) == 0
        assert _arr_len(parts[1]) == 0

    def test_mixed(self):
        items = [{"v": 1}, {"v": 0}, {"v": 1}, {"v": 0}]
        r = invoke("partition", items, "v", "=", 1)
        parts = r.as_array()
        assert _arr_len(parts[0]) == 2
        assert _arr_len(parts[1]) == 2

    def test_by_field(self):
        items = [{"v": 10}, {"v": 0}]
        r = invoke("partition", items, "v", ">", 5)
        parts = r.as_array()
        assert _arr_len(parts[0]) == 1
        assert _arr_len(parts[1]) == 1

    def test_strings(self):
        items = [{"s": "a"}, {"s": "b"}, {"s": "a"}]
        r = invoke("partition", items, "s", "=", "a")
        parts = r.as_array()
        assert _arr_len(parts[0]) == 2
        assert _arr_len(parts[1]) == 1

    def test_single_match(self):
        r = invoke("partition", [{"v": 1}], "v", "=", 1)
        assert _arr_len(r.as_array()[0]) == 1
        assert _arr_len(r.as_array()[1]) == 0

    def test_single_no_match(self):
        r = invoke("partition", [{"v": 0}], "v", "=", 1)
        assert _arr_len(r.as_array()[0]) == 0
        assert _arr_len(r.as_array()[1]) == 1


# ==========================================================================
# take -- extended
# ==========================================================================

class TestTakeExtended:
    def test_first_n(self):
        r = invoke("take", [1, 2, 3, 4], 2)
        assert _arr_ints(r) == [1, 2]

    def test_more_than_length(self):
        r = invoke("take", [1], 100)
        assert _arr_len(r) == 1

    def test_zero(self):
        assert _arr_len(invoke("take", [1, 2, 3], 0)) == 0

    def test_empty_array(self):
        assert _arr_len(invoke("take", [], 5)) == 0

    def test_exact_length(self):
        r = invoke("take", [1, 2], 2)
        assert _arr_len(r) == 2

    def test_mixed_types(self):
        r = invoke("take", [1, "two", True, None], 3)
        assert _arr_len(r) == 3

    def test_one(self):
        r = invoke("take", [10, 20, 30], 1)
        assert _arr_ints(r) == [10]


# ==========================================================================
# drop -- extended
# ==========================================================================

class TestDropExtended:
    def test_first_n(self):
        r = invoke("drop", [1, 2, 3, 4], 2)
        assert _arr_ints(r) == [3, 4]

    def test_all(self):
        assert _arr_len(invoke("drop", [1, 2], 10)) == 0

    def test_zero(self):
        r = invoke("drop", [1, 2, 3], 0)
        assert _arr_len(r) == 3

    def test_empty_array(self):
        assert _arr_len(invoke("drop", [], 5)) == 0

    def test_exact_length(self):
        assert _arr_len(invoke("drop", [1, 2], 2)) == 0

    def test_mixed_types(self):
        r = invoke("drop", ["a", 1, False], 1)
        assert _arr_len(r) == 2

    def test_one(self):
        r = invoke("drop", [10, 20, 30], 1)
        assert _arr_ints(r) == [20, 30]


# ==========================================================================
# limit (alias for take) -- extended
# ==========================================================================

class TestLimitExtended:
    def test_basic(self):
        r = invoke("limit", [1, 2, 3, 4], 2)
        assert _arr_ints(r) == [1, 2]

    def test_zero(self):
        assert _arr_len(invoke("limit", [1, 2, 3], 0)) == 0

    def test_exact_length(self):
        r = invoke("limit", [1, 2], 2)
        assert _arr_len(r) == 2

    def test_more_than_length(self):
        r = invoke("limit", [1], 10)
        assert _arr_len(r) == 1

    def test_empty(self):
        assert _arr_len(invoke("limit", [], 5)) == 0


# ==========================================================================
# chunk -- extended
# ==========================================================================

class TestChunkExtended:
    def test_single_element(self):
        r = invoke("chunk", [1], 1)
        assert _arr_len(r) == 1
        assert _arr_len(r.as_array()[0]) == 1

    def test_size_larger_than_array(self):
        r = invoke("chunk", [1, 2], 10)
        assert _arr_len(r) == 1
        assert _arr_len(r.as_array()[0]) == 2

    def test_empty_array(self):
        r = invoke("chunk", [], 3)
        assert _arr_len(r) == 0

    def test_size_one(self):
        r = invoke("chunk", [1, 2, 3], 1)
        assert _arr_len(r) == 3

    def test_size_equals_length(self):
        r = invoke("chunk", [1, 2, 3], 3)
        assert _arr_len(r) == 1
        assert _arr_len(r.as_array()[0]) == 3

    def test_size_two_odd_length(self):
        r = invoke("chunk", [1, 2, 3, 4, 5], 2)
        assert _arr_len(r) == 3
        assert _arr_len(r.as_array()[0]) == 2
        assert _arr_len(r.as_array()[1]) == 2
        assert _arr_len(r.as_array()[2]) == 1

    def test_size_three(self):
        r = invoke("chunk", [1, 2, 3, 4, 5, 6, 7], 3)
        assert _arr_len(r) == 3
        assert _arr_len(r.as_array()[2]) == 1


# ==========================================================================
# range -- extended
# ==========================================================================

class TestRangeExtended:
    def test_basic(self):
        r = invoke("range", 0, 5)
        assert _arr_len(r) == 5
        assert _arr_ints(r) == [0, 1, 2, 3, 4]

    def test_single_arg(self):
        r = invoke("range", 3)
        assert _arr_len(r) == 3
        assert _arr_ints(r) == [0, 1, 2]

    def test_with_step(self):
        r = invoke("range", 0, 10, 3)
        assert _arr_ints(r) == [0, 3, 6, 9]

    def test_negative_step(self):
        r = invoke("range", 5, 0, -2)
        assert _arr_ints(r) == [5, 3, 1]

    def test_empty_when_start_ge_end(self):
        assert _arr_len(invoke("range", 5, 3)) == 0

    def test_single_element(self):
        r = invoke("range", 0, 1)
        assert _arr_ints(r) == [0]

    def test_negative_values(self):
        r = invoke("range", -3, 0)
        assert _arr_ints(r) == [-3, -2, -1]

    def test_same_start_end(self):
        assert _arr_len(invoke("range", 5, 5)) == 0

    def test_step_of_two(self):
        r = invoke("range", 0, 6, 2)
        assert _arr_ints(r) == [0, 2, 4]

    def test_large_step(self):
        r = invoke("range", 0, 10, 5)
        assert _arr_ints(r) == [0, 5]

    def test_descending(self):
        r = invoke("range", 5, 0, -1)
        assert _arr_ints(r) == [5, 4, 3, 2, 1]

    def test_step_three(self):
        r = invoke("range", 1, 10, 3)
        assert _arr_ints(r) == [1, 4, 7]


# ==========================================================================
# compact -- extended
# ==========================================================================

class TestCompactExtended:
    def test_all_null(self):
        assert _arr_len(invoke("compact", [None, None])) == 0

    def test_no_nulls(self):
        r = invoke("compact", [1, 2, 3])
        assert _arr_len(r) == 3

    def test_empty_array(self):
        assert _arr_len(invoke("compact", [])) == 0

    def test_only_empty_strings(self):
        assert _arr_len(invoke("compact", ["", "", ""])) == 0

    def test_keeps_non_empty_strings(self):
        r = invoke("compact", ["", "hello", None, "world"])
        assert _arr_strs(r) == ["hello", "world"]

    def test_keeps_zeros_and_false(self):
        """compact only removes nulls and empty strings, not 0 or false."""
        r = invoke("compact", [0, False, None, ""])
        assert _arr_len(r) == 2  # 0 and false are kept

    def test_all_valid(self):
        r = invoke("compact", [1, "a", True])
        assert _arr_len(r) == 3

    def test_mixed(self):
        r = invoke("compact", [1, None, "hello", "", 0, True])
        # Keeps: 1, "hello", 0, True
        assert _arr_len(r) == 4


# ==========================================================================
# dedupe -- extended
# ==========================================================================

class TestDedupeExtended:
    def test_empty_array(self):
        assert _arr_len(invoke("dedupe", [], "id")) == 0

    def test_no_duplicates(self):
        r = invoke("dedupe", [1, 2, 3], "id")
        assert _arr_ints(r) == [1, 2, 3]

    def test_consecutive_duplicates(self):
        r = invoke("dedupe", [1, 1, 2, 2, 3], "id")
        assert _arr_ints(r) == [1, 2, 3]

    def test_non_consecutive_removed(self):
        # Dedupe keeps the first occurrence globally, not just consecutive ones.
        r = invoke("dedupe", [1, 2, 1], "id")
        assert _arr_ints(r) == [1, 2]

    def test_all_same(self):
        r = invoke("dedupe", [5, 5, 5, 5], "id")
        assert _arr_ints(r) == [5]

    def test_strings(self):
        r = invoke("dedupe", ["a", "a", "b", "b", "a"], "id")
        assert _arr_strs(r) == ["a", "b"]

    def test_single_element(self):
        r = invoke("dedupe", [42], "id")
        assert _arr_ints(r) == [42]

    def test_by_field(self):
        items = [{"id": "x", "v": 1}, {"id": "x", "v": 2}, {"id": "y", "v": 3}]
        r = invoke("dedupe", items, "id")
        ids = [g.get("id").as_string() for g in r.as_array()]
        assert ids == ["x", "y"]


# ==========================================================================
# cumsum -- extended
# ==========================================================================

class TestCumsumExtended:
    def test_single_element(self):
        r = invoke("cumsum", [5])
        assert _arr_ints(r) == [5]

    def test_empty(self):
        assert _arr_len(invoke("cumsum", [])) == 0

    def test_floats(self):
        r = invoke("cumsum",
                    DynValue.of_array([DynValue.of_float(1.5), DynValue.of_float(2.5), DynValue.of_float(3.0)]))
        arr = r.as_array()
        # 1.5 -> 1.5, 1.5+2.5=4.0->int 4, 4.0+3.0=7.0->int 7
        assert arr[0]._float_value == pytest.approx(1.5)
        assert arr[1]._int_value == 4
        assert arr[2]._int_value == 7

    def test_negative_numbers(self):
        r = invoke("cumsum", [5, -3, 2])
        assert _arr_ints(r) == [5, 2, 4]

    def test_all_nulls(self):
        r = invoke("cumsum", [None, None])
        arr = r.as_array()
        assert arr[0].is_null()
        assert arr[1].is_null()

    def test_mixed_null_int(self):
        r = invoke("cumsum", [1, None, 3])
        arr = r.as_array()
        assert arr[0]._int_value == 1
        assert arr[1].is_null()
        assert arr[2]._int_value == 4  # 1+3=4

    def test_large_numbers(self):
        r = invoke("cumsum", [1000000, 2000000, 3000000])
        assert _arr_ints(r) == [1000000, 3000000, 6000000]

    def test_zeros(self):
        r = invoke("cumsum", [0, 0, 0])
        assert _arr_ints(r) == [0, 0, 0]


# ==========================================================================
# cumprod -- extended
# ==========================================================================

class TestCumprodExtended:
    def test_single_element(self):
        r = invoke("cumprod", [5])
        assert _arr_ints(r) == [5]

    def test_empty(self):
        assert _arr_len(invoke("cumprod", [])) == 0

    def test_floats(self):
        r = invoke("cumprod",
                    DynValue.of_array([DynValue.of_float(2.0), DynValue.of_float(3.0), DynValue.of_float(4.0)]))
        arr = r.as_array()
        assert arr[0]._int_value == 2
        assert arr[1]._int_value == 6
        assert arr[2]._int_value == 24

    def test_with_ones(self):
        r = invoke("cumprod", [1, 1, 1])
        assert _arr_ints(r) == [1, 1, 1]

    def test_with_negative(self):
        r = invoke("cumprod", [2, -3])
        assert _arr_ints(r) == [2, -6]

    def test_with_zero(self):
        r = invoke("cumprod", [5, 0, 3])
        assert _arr_ints(r) == [5, 0, 0]

    def test_ascending(self):
        r = invoke("cumprod", [1, 2, 3, 4])
        assert _arr_ints(r) == [1, 2, 6, 24]

    def test_all_twos(self):
        r = invoke("cumprod", [2, 2, 2, 2])
        assert _arr_ints(r) == [2, 4, 8, 16]


# ==========================================================================
# diff -- extended
# ==========================================================================

class TestDiffExtended:
    def test_empty_array(self):
        assert _arr_len(invoke("diff", [])) == 0

    def test_single_element(self):
        r = invoke("diff", [5])
        assert r.as_array()[0].is_null()

    def test_floats(self):
        r = invoke("diff",
                    DynValue.of_array([DynValue.of_float(1.0), DynValue.of_float(3.0), DynValue.of_float(6.0)]))
        arr = r.as_array()
        assert arr[0].is_null()
        assert arr[1]._int_value == 2
        assert arr[2]._int_value == 3

    def test_integers(self):
        r = invoke("diff", [10, 20, 50])
        arr = r.as_array()
        assert arr[0].is_null()
        assert arr[1]._int_value == 10
        assert arr[2]._int_value == 30

    def test_negative_differences(self):
        r = invoke("diff", [30, 20, 10])
        arr = r.as_array()
        assert arr[1]._int_value == -10
        assert arr[2]._int_value == -10

    def test_same_values(self):
        r = invoke("diff", [5, 5, 5])
        arr = r.as_array()
        assert arr[0].is_null()
        assert arr[1]._int_value == 0
        assert arr[2]._int_value == 0

    def test_two_elements(self):
        r = invoke("diff", [10, 25])
        arr = r.as_array()
        assert arr[0].is_null()
        assert arr[1]._int_value == 15


# ==========================================================================
# pctChange -- extended
# ==========================================================================

class TestPctChangeExtended:
    def test_empty(self):
        assert _arr_len(invoke("pctChange", [])) == 0

    def test_single(self):
        r = invoke("pctChange", [100])
        assert r.as_array()[0].is_null()

    def test_doubling(self):
        r = invoke("pctChange", [100, 200])
        arr = r.as_array()
        assert arr[0].is_null()
        assert abs(arr[1].as_float() - 1.0) < 1e-10

    def test_with_zero_previous(self):
        r = invoke("pctChange", [0, 100])
        assert r.as_array()[1].is_null()  # division by zero

    def test_decrease(self):
        r = invoke("pctChange", [100, 75])
        arr = r.as_array()
        assert abs(arr[1]._float_value - (-0.25)) < 1e-10

    def test_no_change(self):
        r = invoke("pctChange", [100, 100])
        arr = r.as_array()
        assert abs(arr[1]._float_value) < 1e-10

    def test_multiple(self):
        r = invoke("pctChange", [100, 200, 100])
        arr = r.as_array()
        assert arr[0].is_null()
        assert abs(arr[1].as_float() - 1.0) < 1e-10
        assert abs(arr[2]._float_value - (-0.5)) < 1e-10


# ==========================================================================
# shift -- extended
# ==========================================================================

class TestShiftExtended:
    def test_zero_no_change(self):
        r = invoke("shift", [1, 2, 3], 0)
        assert _arr_ints(r) == [1, 2, 3]

    def test_right_by_one(self):
        r = invoke("shift", [1, 2, 3], 1)
        arr = r.as_array()
        assert arr[0].is_null()
        assert arr[1]._int_value == 1
        assert arr[2]._int_value == 2

    def test_left_by_two(self):
        r = invoke("shift", [1, 2, 3, 4], -2)
        arr = r.as_array()
        assert arr[0]._int_value == 3
        assert arr[1]._int_value == 4
        assert arr[2].is_null()
        assert arr[3].is_null()

    def test_shift_larger_than_array(self):
        r = invoke("shift", [1, 2], 5)
        arr = r.as_array()
        assert arr[0].is_null()
        assert arr[1].is_null()

    def test_empty_array(self):
        r = invoke("shift", [], 1)
        assert _arr_len(r) == 0

    def test_right_by_two(self):
        r = invoke("shift", [10, 20, 30, 40], 2)
        arr = r.as_array()
        assert arr[0].is_null()
        assert arr[1].is_null()
        assert arr[2]._int_value == 10
        assert arr[3]._int_value == 20


# ==========================================================================
# lag -- extended
# ==========================================================================

class TestLagExtended:
    def test_default_period_one(self):
        r = invoke("lag", [10, 20, 30])
        arr = r.as_array()
        assert arr[0].is_null()
        assert arr[1]._int_value == 10
        assert arr[2]._int_value == 20

    def test_period_two(self):
        r = invoke("lag", [10, 20, 30, 40], 2)
        arr = r.as_array()
        assert arr[0].is_null()
        assert arr[1].is_null()
        assert arr[2]._int_value == 10
        assert arr[3]._int_value == 20

    def test_period_three(self):
        r = invoke("lag", [10, 20, 30, 40, 50], 3)
        arr = r.as_array()
        assert arr[0].is_null()
        assert arr[1].is_null()
        assert arr[2].is_null()
        assert arr[3]._int_value == 10
        assert arr[4]._int_value == 20

    def test_empty_array(self):
        assert _arr_len(invoke("lag", [])) == 0

    def test_single_element(self):
        r = invoke("lag", [42])
        assert r.as_array()[0].is_null()


# ==========================================================================
# lead -- extended
# ==========================================================================

class TestLeadExtended:
    def test_default_period_one(self):
        r = invoke("lead", [10, 20, 30])
        arr = r.as_array()
        assert arr[0]._int_value == 20
        assert arr[1]._int_value == 30
        assert arr[2].is_null()

    def test_period_two(self):
        r = invoke("lead", [10, 20, 30, 40], 2)
        arr = r.as_array()
        assert arr[0]._int_value == 30
        assert arr[1]._int_value == 40
        assert arr[2].is_null()
        assert arr[3].is_null()

    def test_empty_array(self):
        assert _arr_len(invoke("lead", [])) == 0

    def test_single_element(self):
        r = invoke("lead", [42])
        assert r.as_array()[0].is_null()


# ==========================================================================
# rank -- extended
# ==========================================================================

def _ranks(result):
    """Extract the _rank field from each ranked object."""
    return [x.get("_rank").as_int() for x in result.as_array()]


class TestRankExtended:
    def test_basic_descending(self):
        r = invoke("rank", [10, 30, 20])
        assert _ranks(r) == [3, 1, 2]

    def test_tied_values(self):
        r = invoke("rank", [10, 10, 30])
        assert _ranks(r)[0] == _ranks(r)[1]

    def test_single_element(self):
        r = invoke("rank", [42])
        assert _ranks(r) == [1]

    def test_all_same_value(self):
        r = invoke("rank", [5, 5, 5])
        assert _ranks(r) == [1, 1, 1]

    def test_empty(self):
        assert invoke("rank", []).is_null()

    def test_already_descending(self):
        r = invoke("rank", [30, 20, 10])
        assert _ranks(r) == [1, 2, 3]

    def test_already_ascending(self):
        r = invoke("rank", [10, 20, 30])
        assert _ranks(r) == [3, 2, 1]

    def test_four_elements(self):
        r = invoke("rank", [40, 10, 30, 20])
        assert _ranks(r) == [1, 4, 2, 3]


# ==========================================================================
# fillMissing -- extended
# ==========================================================================

class TestFillMissingExtended:
    def test_no_nulls(self):
        r = invoke("fillMissing", [1, 2, 3], 0, "value")
        assert _arr_ints(r) == [1, 2, 3]

    def test_all_nulls_value(self):
        r = invoke("fillMissing", [None, None], 99, "value")
        assert _arr_ints(r) == [99, 99]

    def test_forward_strategy(self):
        r = invoke("fillMissing", [1, None, None, 4, None], 0, "forward")
        arr = r.as_array()
        assert arr[0]._int_value == 1
        assert arr[1]._int_value == 1
        assert arr[2]._int_value == 1
        assert arr[3]._int_value == 4
        assert arr[4]._int_value == 4

    def test_backward_strategy(self):
        r = invoke("fillMissing", [None, None, 3, None, 5], 0, "backward")
        arr = r.as_array()
        assert arr[0]._int_value == 3
        assert arr[1]._int_value == 3
        assert arr[2]._int_value == 3
        assert arr[3]._int_value == 5
        assert arr[4]._int_value == 5

    def test_empty_array(self):
        assert _arr_len(invoke("fillMissing", [], 0, "value")) == 0

    def test_forward_leading_null(self):
        # No prior value; the fill value (None) seeds the carry.
        r = invoke("fillMissing", [None, 1, None], None, "forward")
        arr = r.as_array()
        assert arr[0].is_null()
        assert arr[1]._int_value == 1
        assert arr[2]._int_value == 1

    def test_backward_trailing_null(self):
        r = invoke("fillMissing", [None, 1, None], None, "backward")
        arr = r.as_array()
        assert arr[0]._int_value == 1
        assert arr[1]._int_value == 1
        assert arr[2].is_null()

    def test_value_with_string(self):
        r = invoke("fillMissing", ["a", None, "c"], "x", "value")
        assert r.as_array()[1].as_string() == "x"


# ==========================================================================
# sample -- extended
# ==========================================================================

class TestSampleExtended:
    def test_zero_count(self):
        assert _arr_len(invoke("sample", [1, 2, 3], 0)) == 0

    def test_more_than_length(self):
        r = invoke("sample", [1, 2], 10)
        assert _arr_len(r) == 2

    def test_empty_array(self):
        assert _arr_len(invoke("sample", [], 5)) == 0

    def test_one_element(self):
        r = invoke("sample", [42], 1)
        assert _arr_len(r) == 1
        assert r.as_array()[0]._int_value == 42

    def test_returns_correct_count(self):
        r = invoke("sample", [1, 2, 3, 4, 5], 3)
        assert _arr_len(r) == 3

    def test_full_array(self):
        r = invoke("sample", [1, 2, 3], 3)
        assert _arr_len(r) == 3


# ==========================================================================
# joinArray -- extended
# ==========================================================================

class TestJoinArrayExtended:
    def test_comma(self):
        r = invoke("joinArray", ["a", "b", "c"], ",")
        assert r.as_string() == "a,b,c"

    def test_space(self):
        r = invoke("joinArray", ["hello", "world"], " ")
        assert r.as_string() == "hello world"

    def test_empty_separator(self):
        r = invoke("joinArray", ["a", "b", "c"], "")
        assert r.as_string() == "abc"

    def test_single_element(self):
        r = invoke("joinArray", ["only"], ",")
        assert r.as_string() == "only"

    def test_empty_array(self):
        r = invoke("joinArray", [], ",")
        assert r.as_string() == ""

    def test_multi_char_separator(self):
        r = invoke("joinArray", ["a", "b", "c"], " | ")
        assert r.as_string() == "a | b | c"

    def test_integers(self):
        r = invoke("joinArray", [1, 2, 3], "-")
        assert r.as_string() == "1-2-3"


# ==========================================================================
# Additional parametrized tests for broader coverage
# ==========================================================================

class TestFilterParametrized:
    @pytest.mark.parametrize("op,value,expected_count", [
        ("=", 2, 1),
        ("!=", 2, 2),
        (">", 1, 2),
        (">=", 2, 2),
        ("<", 3, 2),
        ("<=", 2, 2),
    ])
    def test_numeric_operators(self, op, value, expected_count):
        items = [{"v": 1}, {"v": 2}, {"v": 3}]
        r = invoke("filter", items, "v", op, value)
        assert _arr_len(r) == expected_count

    @pytest.mark.parametrize("op,value,expected_count", [
        ("contains", "an", 2),   # banana, mango
        ("startsWith", "b", 1),  # banana
        ("endsWith", "e", 1),    # apple
    ])
    def test_string_operators(self, op, value, expected_count):
        items = [{"name": "apple"}, {"name": "banana"}, {"name": "mango"}]
        r = invoke("filter", items, "name", op, value)
        assert _arr_len(r) == expected_count


class TestSortParametrized:
    @pytest.mark.parametrize("input_arr,expected", [
        ([5, 3, 1, 4, 2], [1, 2, 3, 4, 5]),
        ([1], [1]),
        ([], []),
        ([1, 1, 1], [1, 1, 1]),
        ([-2, -1, -3], [-3, -2, -1]),
    ])
    def test_sort_cases(self, input_arr, expected):
        r = invoke("sort", input_arr)
        if expected:
            assert _arr_ints(r) == expected
        else:
            assert _arr_len(r) == 0


class TestRangeParametrized:
    @pytest.mark.parametrize("args,expected_len", [
        ((5,), 5),
        ((0, 5), 5),
        ((2, 5), 3),
        ((0, 10, 2), 5),
        ((5, 0, -1), 5),
        ((0, 0), 0),
    ])
    def test_range_lengths(self, args, expected_len):
        r = invoke("range", *args)
        assert _arr_len(r) == expected_len


class TestChunkParametrized:
    @pytest.mark.parametrize("arr_len,chunk_size,expected_chunks", [
        (6, 2, 3),
        (6, 3, 2),
        (5, 2, 3),
        (1, 5, 1),
        (0, 3, 0),
        (3, 1, 3),
    ])
    def test_chunk_counts(self, arr_len, chunk_size, expected_chunks):
        data = list(range(arr_len))
        r = invoke("chunk", data, chunk_size)
        assert _arr_len(r) == expected_chunks


class TestTakeDropParametrized:
    @pytest.mark.parametrize("n,expected_len", [
        (0, 0),
        (1, 1),
        (3, 3),
        (5, 5),
        (10, 5),
    ])
    def test_take_lengths(self, n, expected_len):
        data = [1, 2, 3, 4, 5]
        r = invoke("take", data, n)
        assert _arr_len(r) == expected_len

    @pytest.mark.parametrize("n,expected_len", [
        (0, 5),
        (1, 4),
        (3, 2),
        (5, 0),
        (10, 0),
    ])
    def test_drop_lengths(self, n, expected_len):
        data = [1, 2, 3, 4, 5]
        r = invoke("drop", data, n)
        assert _arr_len(r) == expected_len
