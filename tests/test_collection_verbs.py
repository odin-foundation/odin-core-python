"""Tests for collection verbs."""

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
    """Extract integer values from array result."""
    return [item._int_value for item in result.as_array()]


def _arr_strs(result):
    """Extract string values from array result."""
    return [item.as_string() for item in result.as_array()]


# ── flatten ──────────────────────────────────────────────────────────

class TestFlatten:
    def test_nested(self):
        r = invoke("flatten", [[1, 2], [3]])
        assert len(r.as_array()) == 3

    def test_single_level(self):
        r = invoke("flatten", [[1, [2, 3]], [4]])
        arr = r.as_array()
        # First level flattened, but [2,3] stays nested
        assert len(arr) == 3

    def test_with_nulls(self):
        r = invoke("flatten", [[1, None], [3]])
        arr = r.as_array()
        assert len(arr) == 3
        assert arr[1].is_null()


# ── distinct ─────────────────────────────────────────────────────────

class TestDistinct:
    def test_removes_duplicates(self):
        r = invoke("distinct", [1, 2, 1, 3, 2])
        assert len(r.as_array()) == 3

    def test_preserves_order(self):
        r = invoke("distinct", [3, 1, 2, 1, 3])
        assert _arr_ints(r) == [3, 1, 2]

    def test_unique_alias(self):
        r = invoke("unique", [1, 2, 1])
        assert len(r.as_array()) == 2


# ── sort ─────────────────────────────────────────────────────────────

class TestSort:
    def test_integers(self):
        r = invoke("sort", [3, 1, 2])
        assert _arr_ints(r) == [1, 2, 3]

    def test_strings(self):
        r = invoke("sort", ["banana", "apple", "cherry"])
        assert _arr_strs(r) == ["apple", "banana", "cherry"]

    def test_sort_desc(self):
        r = invoke("sortDesc", [1, 3, 2])
        assert _arr_ints(r) == [3, 2, 1]


# ── sortBy ───────────────────────────────────────────────────────────

class TestSortBy:
    def test_by_field(self):
        items = [{"name": "Charlie", "age": 30}, {"name": "Alice", "age": 25}]
        r = invoke("sortBy", items, "name")
        arr = r.as_array()
        assert arr[0].get("name").as_string() == "Alice"
        assert arr[1].get("name").as_string() == "Charlie"


# ── map / pluck ──────────────────────────────────────────────────────

class TestMap:
    def test_extract_field(self):
        items = [{"name": "Alice"}, {"name": "Bob"}]
        r = invoke("map", items, "name")
        assert _arr_strs(r) == ["Alice", "Bob"]

    def test_pluck_alias(self):
        items = [{"x": 1}, {"x": 2}]
        r = invoke("pluck", items, "x")
        assert len(r.as_array()) == 2


# ── indexOf ──────────────────────────────────────────────────────────

class TestIndexOf:
    def test_found(self):
        r = invoke("indexOf", ["a", "b", "c"], "b")
        assert r._int_value == 1

    def test_not_found(self):
        r = invoke("indexOf", ["a", "b", "c"], "d")
        assert r._int_value == -1


# ── at ───────────────────────────────────────────────────────────────

class TestAt:
    def test_valid_index(self):
        r = invoke("at", [10, 20, 30], 1)
        assert r._int_value == 20

    def test_negative_index(self):
        r = invoke("at", [10, 20, 30], -1)
        assert r._int_value == 30

    def test_out_of_bounds(self):
        r = invoke("at", [10, 20], 5)
        assert r.is_null()


# ── slice ────────────────────────────────────────────────────────────

class TestSlice:
    def test_middle(self):
        r = invoke("slice", [10, 20, 30, 40, 50], 1, 4)
        assert len(r.as_array()) == 3

    def test_single_element(self):
        r = invoke("slice", [10, 20, 30], 1, 2)
        arr = r.as_array()
        assert len(arr) == 1
        assert arr[0]._int_value == 20


# ── reverse ──────────────────────────────────────────────────────────

class TestReverse:
    def test_array(self):
        r = invoke("reverse", [1, 2, 3])
        assert _arr_ints(r) == [3, 2, 1]


# ── filter ───────────────────────────────────────────────────────────

class TestFilter:
    def test_with_condition(self):
        items = [{"age": 25}, {"age": 35}, {"age": 20}]
        r = invoke("filter", items, "age", ">", 22)
        assert len(r.as_array()) == 2

    def test_equality(self):
        items = [{"status": "active"}, {"status": "inactive"}]
        r = invoke("filter", items, "status", "=", "active")
        assert len(r.as_array()) == 1

    def test_truthy_filter(self):
        r = invoke("filter", [1, 0, "hello", "", None, True, False])
        arr = r.as_array()
        assert len(arr) == 3  # 1, "hello", True


# ── every / some ─────────────────────────────────────────────────────

class TestEverySome:
    def test_every_true(self):
        r = invoke("every", [1, 2, 3])
        assert r._bool_value is True

    def test_every_false(self):
        r = invoke("every", [1, 0, 3])
        assert r._bool_value is False

    def test_every_empty(self):
        r = invoke("every", [])
        assert r._bool_value is True

    def test_some_true(self):
        r = invoke("some", [0, 0, 1])
        assert r._bool_value is True

    def test_some_false(self):
        r = invoke("some", [0, 0, 0])
        assert r._bool_value is False


# ── includes ─────────────────────────────────────────────────────────

class TestIncludes:
    def test_found(self):
        r = invoke("includes", [1, 2, 3], 2)
        assert r._bool_value is True

    def test_not_found(self):
        r = invoke("includes", [1, 2, 3], 5)
        assert r._bool_value is False


# ── take / drop ──────────────────────────────────────────────────────

class TestTakeDrop:
    def test_take(self):
        r = invoke("take", [1, 2, 3, 4, 5], 3)
        assert _arr_ints(r) == [1, 2, 3]

    def test_drop(self):
        r = invoke("drop", [1, 2, 3, 4, 5], 2)
        assert _arr_ints(r) == [3, 4, 5]

    def test_limit_alias(self):
        r = invoke("limit", [1, 2, 3], 2)
        assert len(r.as_array()) == 2


# ── chunk ────────────────────────────────────────────────────────────

class TestChunk:
    def test_even(self):
        r = invoke("chunk", [1, 2, 3, 4], 2)
        arr = r.as_array()
        assert len(arr) == 2
        assert len(arr[0].as_array()) == 2

    def test_odd(self):
        r = invoke("chunk", [1, 2, 3, 4, 5], 2)
        arr = r.as_array()
        assert len(arr) == 3
        assert len(arr[2].as_array()) == 1


# ── range ────────────────────────────────────────────────────────────

class TestRange:
    def test_simple(self):
        r = invoke("range", 5)
        assert len(r.as_array()) == 5

    def test_start_end(self):
        r = invoke("range", 2, 5)
        assert len(r.as_array()) == 3

    def test_with_step(self):
        r = invoke("range", 0, 10, 2)
        assert len(r.as_array()) == 5


# ── compact ──────────────────────────────────────────────────────────

class TestCompact:
    def test_removes_nulls(self):
        r = invoke("compact", [1, None, 2, None, 3])
        assert len(r.as_array()) == 3

    def test_removes_empty_strings(self):
        r = invoke("compact", ["a", "", "b"])
        assert len(r.as_array()) == 2


# ── zip ──────────────────────────────────────────────────────────────

class TestZip:
    def test_basic(self):
        r = invoke("zip", [1, 2, 3], ["a", "b", "c"])
        arr = r.as_array()
        assert len(arr) == 3
        assert arr[0].as_array()[0]._int_value == 1
        assert arr[0].as_array()[1].as_string() == "a"


# ── groupBy ──────────────────────────────────────────────────────────

class TestGroupBy:
    def test_basic(self):
        items = [
            {"dept": "eng", "name": "Alice"},
            {"dept": "sales", "name": "Bob"},
            {"dept": "eng", "name": "Charlie"},
        ]
        r = invoke("groupBy", items, "dept")
        # Array of {key, items} objects, insertion order
        arr = r.as_array()
        assert len(arr) == 2
        assert arr[0].get("key").as_string() == "eng"
        assert len(arr[0].get("items").as_array()) == 2
        assert arr[1].get("key").as_string() == "sales"


# ── partition ────────────────────────────────────────────────────────

class TestPartition:
    def test_basic(self):
        items = [
            {"status": "active"},
            {"status": "inactive"},
            {"status": "active"},
        ]
        r = invoke("partition", items, "status", "=", "active")
        arr = r.as_array()
        assert len(arr) == 2
        passing = arr[0].as_array()
        failing = arr[1].as_array()
        assert len(passing) == 2
        assert len(failing) == 1


# ── dedupe ───────────────────────────────────────────────────────────

class TestDedupe:
    def test_basic(self):
        items = [
            {"id": "a"}, {"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "a"},
        ]
        r = invoke("dedupe", items, "id")
        ids = [x.get("id").as_string() for x in r.as_array()]
        assert ids == ["a", "b", "c"]


# ── cumsum ───────────────────────────────────────────────────────────

class TestCumsum:
    def test_basic(self):
        r = invoke("cumsum", [1, 2, 3, 4])
        assert _arr_ints(r) == [1, 3, 6, 10]


# ── cumprod ──────────────────────────────────────────────────────────

class TestCumprod:
    def test_basic(self):
        r = invoke("cumprod", [1, 2, 3, 4])
        assert _arr_ints(r) == [1, 2, 6, 24]


# ── diff ─────────────────────────────────────────────────────────────

class TestDiff:
    def test_basic(self):
        r = invoke("diff", [10, 20, 15, 25])
        arr = r.as_array()
        assert arr[0].is_null()
        assert arr[1]._int_value == 10
        assert arr[2]._int_value == -5
        assert arr[3]._int_value == 10


# ── rank ─────────────────────────────────────────────────────────────

class TestRank:
    def test_basic(self):
        r = invoke("rank", [30, 10, 20])
        ranks = [x.get("_rank").as_int() for x in r.as_array()]
        assert ranks == [1, 3, 2]


# ── fillMissing ──────────────────────────────────────────────────────

class TestFillMissing:
    def test_forward(self):
        r = invoke("fillMissing", [1, None, None, 4], 0, "forward")
        arr = r.as_array()
        assert arr[1]._int_value == 1
        assert arr[2]._int_value == 1

    def test_value(self):
        r = invoke("fillMissing", [1, None, 3], 0)
        arr = r.as_array()
        assert arr[1]._int_value == 0


# ── joinArray ────────────────────────────────────────────────────────

class TestJoinArray:
    def test_basic(self):
        r = invoke("joinArray", ["a", "b", "c"], ",")
        assert r.as_string() == "a,b,c"

    def test_with_space(self):
        r = invoke("joinArray", ["hello", "world"], " ")
        assert r.as_string() == "hello world"
