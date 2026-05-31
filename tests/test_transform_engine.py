"""Tests for the ODIN transform engine."""

import json
import pytest

from odin.transform.transform_parser import parse_transform
from odin.transform.engine import TransformEngine, _evaluate_condition, _ExecContext
from odin.transform.verb_registry import VerbRegistry, create_default_registry
from odin.transform.dyn_value import DynValue, DynType
from odin.transform.types import (
    ConfidentialMode,
    TransformResult,
)


def _execute(transform_text: str, source: dict) -> TransformResult:
    """Helper: parse transform text and execute on source dict."""
    t = parse_transform(transform_text)
    engine = TransformEngine(create_default_registry())
    return engine.execute(t, source)


def _output_dict(result: TransformResult) -> dict:
    """Convert result output DynValue to Python dict."""
    return _dyn_to_python(result.output)


def _dyn_to_python(dv):
    """Convert DynValue to Python native types."""
    if dv is None or dv.is_null():
        return None
    if dv.is_bool():
        return dv.as_bool()
    if dv.is_integer():
        return dv.as_int()
    if dv.is_float() or dv.is_number():
        return dv.as_float()
    if dv.is_string():
        return dv.as_string()
    if dv.is_array():
        return [_dyn_to_python(item) for item in dv.as_array()]
    if dv.is_object():
        return {k: _dyn_to_python(v) for k, v in dv.as_object().items()}
    return dv.as_string()


# ── Simple Field Mapping ───────────────────────────────────────────────────────


class TestSimpleFieldMapping:
    def test_single_field(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nName = @name',
            {"name": "Alice"},
        )
        assert result.success
        out = _output_dict(result)
        assert out["Name"] == "Alice"

    def test_multiple_fields(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nName = @name\nAge = @age',
            {"name": "Bob", "age": 30},
        )
        out = _output_dict(result)
        assert out["Name"] == "Bob"
        assert out["Age"] == 30

    def test_missing_field_yields_null(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nName = @missing',
            {"name": "Alice"},
        )
        out = _output_dict(result)
        assert out["Name"] is None

    def test_string_value(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nGreeting = @msg',
            {"msg": "hello world"},
        )
        out = _output_dict(result)
        assert out["Greeting"] == "hello world"

    def test_boolean_value(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nActive = @active',
            {"active": True},
        )
        out = _output_dict(result)
        assert out["Active"] is True

    def test_null_value(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nVal = @val',
            {"val": None},
        )
        out = _output_dict(result)
        assert out["Val"] is None


# ── Reference Resolution ──────────────────────────────────────────────────────


class TestReferenceResolution:
    def test_nested_reference(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nCity = @address.city',
            {"address": {"city": "NYC"}},
        )
        out = _output_dict(result)
        assert out["City"] == "NYC"

    def test_deeply_nested(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nZip = @address.location.zip',
            {"address": {"location": {"zip": "10001"}}},
        )
        out = _output_dict(result)
        assert out["Zip"] == "10001"

    def test_array_index_reference(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nFirst = @items[0]',
            {"items": ["a", "b", "c"]},
        )
        out = _output_dict(result)
        assert out["First"] == "a"

    def test_array_index_nested(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nName = @people[0].name',
            {"people": [{"name": "Alice"}, {"name": "Bob"}]},
        )
        out = _output_dict(result)
        assert out["Name"] == "Alice"

    def test_missing_nested_yields_null(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nVal = @a.b.c',
            {"a": {"x": 1}},
        )
        out = _output_dict(result)
        assert out["Val"] is None

    def test_reference_to_object(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nAddr = @address',
            {"address": {"city": "NYC", "state": "NY"}},
        )
        out = _output_dict(result)
        assert isinstance(out["Addr"], dict)
        assert out["Addr"]["city"] == "NYC"

    def test_reference_to_array(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nItems = @items',
            {"items": [1, 2, 3]},
        )
        out = _output_dict(result)
        assert isinstance(out["Items"], list)
        assert out["Items"] == [1, 2, 3]


# ── Literal Values ─────────────────────────────────────────────────────────────


class TestLiteralValues:
    def test_string_literal(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nType = "fixed"',
            {},
        )
        out = _output_dict(result)
        assert out["Type"] == "fixed"

    def test_integer_literal(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nCount = ##42',
            {},
        )
        out = _output_dict(result)
        assert out["Count"] == 42

    def test_number_literal(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nRate = #3.14',
            {},
        )
        out = _output_dict(result)
        assert abs(out["Rate"] - 3.14) < 0.001

    def test_boolean_literal_true(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nActive = ?true',
            {},
        )
        out = _output_dict(result)
        assert out["Active"] is True

    def test_boolean_literal_false(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nActive = ?false',
            {},
        )
        out = _output_dict(result)
        assert out["Active"] is False

    def test_null_literal(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nOld = ~',
            {},
        )
        out = _output_dict(result)
        assert out["Old"] is None

    def test_currency_literal(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nPrice = #$99.99',
            {},
        )
        out = _output_dict(result)
        assert abs(out["Price"] - 99.99) < 0.01


# ── Named Segments ─────────────────────────────────────────────────────────────


class TestNamedSegments:
    def test_named_segment_creates_nested_object(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{Customer}\nName = @name',
            {"name": "Alice"},
        )
        out = _output_dict(result)
        assert "Customer" in out
        assert out["Customer"]["Name"] == "Alice"

    def test_multiple_named_segments(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n'
            '{Customer}\nName = @customer_name\n'
            '{Order}\nId = @order_id',
            {"customer_name": "Alice", "order_id": "ORD-1"},
        )
        out = _output_dict(result)
        assert out["Customer"]["Name"] == "Alice"
        assert out["Order"]["Id"] == "ORD-1"

    def test_root_segment_merges_to_top(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nName = @name\nAge = @age',
            {"name": "Alice", "age": 30},
        )
        out = _output_dict(result)
        assert out["Name"] == "Alice"
        assert out["Age"] == 30


# ── Verb Invocation ────────────────────────────────────────────────────────────


class TestVerbInvocation:
    def test_stub_verb_upper(self):
        """Register a stub 'upper' verb and test it."""
        t = parse_transform(
            '{$}\ndirection = "json->json"\n{}\nName = %upper @name'
        )
        registry = create_default_registry()
        registry.register("upper", lambda args, ctx: DynValue.of_string(args[0].as_string().upper()))
        engine = TransformEngine(registry)
        result = engine.execute(t, {"name": "alice"})
        out = _output_dict(result)
        assert out["Name"] == "ALICE"

    def test_stub_verb_concat(self):
        t = parse_transform(
            '{$}\ndirection = "json->json"\n{}\nFull = %concat @first " " @last'
        )
        registry = create_default_registry()
        registry.register("concat", lambda args, ctx: DynValue.of_string(
            "".join(a.as_string() for a in args)
        ))
        engine = TransformEngine(registry)
        result = engine.execute(t, {"first": "John", "last": "Doe"})
        out = _output_dict(result)
        assert out["Full"] == "John Doe"

    def test_stub_verb_default(self):
        t = parse_transform(
            '{$}\ndirection = "json->json"\n{}\nVal = %default @missing "N/A"'
        )
        registry = create_default_registry()
        registry.register("default", lambda args, ctx: args[0] if not args[0].is_null() else args[1])
        engine = TransformEngine(registry)
        result = engine.execute(t, {})
        out = _output_dict(result)
        assert out["Val"] == "N/A"

    def test_unknown_verb_error(self):
        t = parse_transform(
            '{$}\ndirection = "json->json"\n{}\nVal = %nonexistent @name'
        )
        engine = TransformEngine(create_default_registry())
        result = engine.execute(t, {"name": "Alice"})
        # Should not crash; should produce error or null
        assert result is not None


# ── Array Iteration ────────────────────────────────────────────────────────────


class TestArrayIteration:
    def test_simple_array_loop(self):
        text = (
            '{$}\ndirection = "json->json"\n'
            '{Items[]}\n'
            '_ = @items :loop\n'
            'Name = @.name'
        )
        result = _execute(text, {"items": [{"name": "A"}, {"name": "B"}]})
        out = _output_dict(result)
        assert "Items" in out
        assert isinstance(out["Items"], list)
        assert len(out["Items"]) == 2
        assert out["Items"][0]["Name"] == "A"
        assert out["Items"][1]["Name"] == "B"

    def test_array_loop_multiple_fields(self):
        text = (
            '{$}\ndirection = "json->json"\n'
            '{Lines[]}\n'
            '_ = @lines :loop\n'
            'Sku = @.sku\n'
            'Qty = @.qty'
        )
        result = _execute(text, {"lines": [
            {"sku": "ABC", "qty": 2},
            {"sku": "DEF", "qty": 5},
        ]})
        out = _output_dict(result)
        assert len(out["Lines"]) == 2
        assert out["Lines"][0]["Sku"] == "ABC"
        assert out["Lines"][1]["Qty"] == 5

    def test_empty_array(self):
        text = (
            '{$}\ndirection = "json->json"\n'
            '{Items[]}\n'
            '_ = @items :loop\n'
            'Name = @.name'
        )
        result = _execute(text, {"items": []})
        out = _output_dict(result)
        assert "Items" in out
        assert out["Items"] == []


# ── Confidential Enforcement ──────────────────────────────────────────────────


class TestConfidentialEnforcement:
    def test_redact_confidential_string(self):
        text = (
            '{$}\ndirection = "json->json"\n'
            'enforceConfidential = "redact"\n'
            '{}\nSSN = @ssn :confidential'
        )
        result = _execute(text, {"ssn": "123-45-6789"})
        out = _output_dict(result)
        assert out["SSN"] is None

    def test_mask_confidential_string(self):
        text = (
            '{$}\ndirection = "json->json"\n'
            'enforceConfidential = "mask"\n'
            '{}\nSSN = @ssn :confidential'
        )
        result = _execute(text, {"ssn": "123-45-6789"})
        out = _output_dict(result)
        # Masked string should be all asterisks
        assert out["SSN"] is not None
        assert "*" in str(out["SSN"])

    def test_no_enforcement_passes_through(self):
        text = (
            '{$}\ndirection = "json->json"\n'
            '{}\nSSN = @ssn :confidential'
        )
        result = _execute(text, {"ssn": "123-45-6789"})
        out = _output_dict(result)
        assert out["SSN"] == "123-45-6789"

    def test_redact_non_confidential_passes_through(self):
        text = (
            '{$}\ndirection = "json->json"\n'
            'enforceConfidential = "redact"\n'
            '{}\nName = @name'
        )
        result = _execute(text, {"name": "Alice"})
        out = _output_dict(result)
        assert out["Name"] == "Alice"

    def test_mask_number_becomes_null(self):
        text = (
            '{$}\ndirection = "json->json"\n'
            'enforceConfidential = "mask"\n'
            '{}\nVal = @val :confidential'
        )
        result = _execute(text, {"val": 42})
        out = _output_dict(result)
        assert out["Val"] is None

    def test_mask_boolean_becomes_null(self):
        text = (
            '{$}\ndirection = "json->json"\n'
            'enforceConfidential = "mask"\n'
            '{}\nVal = @val :confidential'
        )
        result = _execute(text, {"val": True})
        out = _output_dict(result)
        assert out["Val"] is None


# ── Output Formatting ──────────────────────────────────────────────────────────


class TestOutputFormatting:
    def test_json_format(self):
        text = (
            '{$}\ndirection = "json->json"\n'
            'target.format = "json"\n'
            '{}\nName = @name'
        )
        result = _execute(text, {"name": "Alice"})
        assert result.formatted is not None
        parsed = json.loads(result.formatted)
        assert parsed["Name"] == "Alice"

    def test_json_format_nested(self):
        text = (
            '{$}\ndirection = "json->json"\n'
            'target.format = "json"\n'
            '{Customer}\nName = @name\nAge = @age'
        )
        result = _execute(text, {"name": "Alice", "age": 30})
        parsed = json.loads(result.formatted)
        assert parsed["Customer"]["Name"] == "Alice"

    def test_default_format_is_json(self):
        """If no target.format specified, default to json."""
        text = (
            '{$}\ndirection = "json->json"\n'
            '{}\nName = @name'
        )
        result = _execute(text, {"name": "Alice"})
        # Should still produce formatted output
        if result.formatted:
            parsed = json.loads(result.formatted)
            assert parsed["Name"] == "Alice"


# ── Constants in Expressions ───────────────────────────────────────────────────


class TestConstants:
    def test_constant_reference(self):
        text = (
            '{$}\ndirection = "json->json"\n'
            'const.VERSION = "1.0"\n'
            '{}\nVer = @$const.VERSION'
        )
        result = _execute(text, {})
        out = _output_dict(result)
        assert out["Ver"] == "1.0"

    def test_constant_with_mappings(self):
        text = (
            '{$}\ndirection = "json->json"\n'
            'const.DEFAULT_COUNTRY = "US"\n'
            '{}\nName = @name\nCountry = @$const.DEFAULT_COUNTRY'
        )
        result = _execute(text, {"name": "Alice"})
        out = _output_dict(result)
        assert out["Name"] == "Alice"
        assert out["Country"] == "US"


# ── Discard Target ─────────────────────────────────────────────────────────────


class TestDiscardTarget:
    def test_underscore_target_not_in_output(self):
        text = (
            '{$}\ndirection = "json->json"\n'
            '{}\nName = @name\n_ = @side_effect'
        )
        result = _execute(text, {"name": "Alice", "side_effect": "x"})
        out = _output_dict(result)
        assert "Name" in out
        assert "_" not in out


# ── VerbRegistry ───────────────────────────────────────────────────────────────


class TestVerbRegistry:
    def test_register_and_invoke(self):
        registry = VerbRegistry()
        registry.register("double", lambda args, ctx: DynValue.of_integer(args[0].as_int() * 2))
        assert registry.has("double")
        result = registry.get("double")([DynValue.of_integer(5)], None)
        assert result.as_int() == 10

    def test_missing_verb(self):
        registry = VerbRegistry()
        assert not registry.has("missing")

    def test_overwrite_verb(self):
        registry = VerbRegistry()
        registry.register("test", lambda args, ctx: DynValue.of_string("first"))
        registry.register("test", lambda args, ctx: DynValue.of_string("second"))
        result = registry.get("test")([], None)
        assert result.as_string() == "second"

    def test_create_default_registry(self):
        registry = create_default_registry()
        assert isinstance(registry, VerbRegistry)


# ── Edge Cases ─────────────────────────────────────────────────────────────────


class TestEngineEdgeCases:
    def test_empty_source(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nName = @name',
            {},
        )
        out = _output_dict(result)
        assert out["Name"] is None

    def test_empty_transform(self):
        result = _execute('{$}\ndirection = "json->json"', {"name": "Alice"})
        out = _output_dict(result)
        assert isinstance(out, dict)

    def test_source_is_array(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nFirst = @[0]',
            [1, 2, 3],
        )
        # Should handle array source
        assert result is not None

    def test_deeply_nested_output(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n'
            '{A}\nB = @b',
            {"b": "val"},
        )
        out = _output_dict(result)
        assert out["A"]["B"] == "val"

    def test_numeric_source_values(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nX = @x\nY = @y',
            {"x": 1.5, "y": -3},
        )
        out = _output_dict(result)
        assert out["X"] == 1.5
        assert out["Y"] == -3

    def test_nested_array_in_object(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nTags = @tags',
            {"tags": ["a", "b"]},
        )
        out = _output_dict(result)
        assert out["Tags"] == ["a", "b"]

    def test_result_success_flag(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nName = @name',
            {"name": "Alice"},
        )
        assert result.success is True

    def test_result_has_formatted(self):
        result = _execute(
            '{$}\ndirection = "json->json"\ntarget.format = "json"\n{}\nName = @name',
            {"name": "Alice"},
        )
        assert result.formatted is not None
        assert isinstance(result.formatted, str)

    def test_multiple_root_fields(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nA = @a\nB = @b\nC = @c',
            {"a": 1, "b": 2, "c": 3},
        )
        out = _output_dict(result)
        assert out["A"] == 1
        assert out["B"] == 2
        assert out["C"] == 3

    def test_null_in_nested_object(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nVal = @obj.missing',
            {"obj": {"present": 1}},
        )
        out = _output_dict(result)
        assert out["Val"] is None

    def test_integer_zero_is_not_null(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nVal = @val',
            {"val": 0},
        )
        out = _output_dict(result)
        assert out["Val"] == 0

    def test_empty_string_is_not_null(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nVal = @val',
            {"val": ""},
        )
        out = _output_dict(result)
        assert out["Val"] == ""

    def test_false_is_not_null(self):
        result = _execute(
            '{$}\ndirection = "json->json"\n{}\nVal = @val',
            {"val": False},
        )
        out = _output_dict(result)
        assert out["Val"] is False


# ── Type Directives ────────────────────────────────────────────────────────────


class TestTypeDirectives:
    def test_coerce_to_string(self):
        text = (
            '{$}\ndirection = "json->json"\n'
            '{}\nVal = "@val :type string"'
        )
        result = _execute(text, {"val": 42})
        out = _output_dict(result)
        assert out["Val"] == "42"

    def test_coerce_to_integer(self):
        text = (
            '{$}\ndirection = "json->json"\n'
            '{}\nVal = "@val :type integer"'
        )
        result = _execute(text, {"val": "42"})
        out = _output_dict(result)
        assert out["Val"] == 42

    def test_default_directive(self):
        text = (
            '{$}\ndirection = "json->json"\n'
            '{}\nVal = "@missing :default N/A"'
        )
        result = _execute(text, {})
        out = _output_dict(result)
        assert out["Val"] == "N/A"

    def test_default_not_applied_when_present(self):
        text = (
            '{$}\ndirection = "json->json"\n'
            '{}\nVal = "@val :default N/A"'
        )
        result = _execute(text, {"val": "hello"})
        out = _output_dict(result)
        assert out["Val"] == "hello"


# ── Condition Evaluation ────────────────────────────────────────────────────────


class TestEvaluateCondition:
    def _source(self):
        return DynValue.of_object({
            "hasDui": DynValue.of_bool(True),
            "active": DynValue.of_bool(False),
            "age": DynValue.of_integer(30),
            "status": DynValue.of_string("active"),
        })

    def test_truthy_path_true(self):
        assert _evaluate_condition("hasDui", self._source(), _ExecContext()) is True

    def test_truthy_path_false(self):
        assert _evaluate_condition("active", self._source(), _ExecContext()) is False

    def test_equals_comparison_true(self):
        assert _evaluate_condition('status = "active"', self._source(), _ExecContext()) is True

    def test_equals_comparison_false(self):
        assert _evaluate_condition('status = "void"', self._source(), _ExecContext()) is False

    def test_numeric_greater_than(self):
        assert _evaluate_condition("age > 18", self._source(), _ExecContext()) is True

    def test_at_prefixed_path(self):
        assert _evaluate_condition("@hasDui = true", self._source(), _ExecContext()) is True


# ── Verb-Expression Conditions ─────────────────────────────────────────────────


_VERB_COND_HEADER = (
    '{$}\n'
    'odin = "1.0.0"\n'
    'transform = "1.0.0"\n'
    'direction = "odin->json"\n'
    'target.format = "json"\n\n'
)


class TestVerbConditions:
    def test_truthy_reference_condition_included(self):
        t = _VERB_COND_HEADER + '{Sec :if @flag}\nv = "yes"\n'
        out = _output_dict(_execute(t, {"flag": True}))
        assert out == {"Sec": {"v": "yes"}}

    def test_truthy_reference_condition_omitted(self):
        t = _VERB_COND_HEADER + '{Sec :if @flag}\nv = "yes"\n'
        out = _output_dict(_execute(t, {"flag": False}))
        assert out == {}

    def test_eq_verb_condition_true(self):
        t = _VERB_COND_HEADER + '{Sec :if %eq @tier "gold"}\nv = "yes"\n'
        out = _output_dict(_execute(t, {"tier": "gold"}))
        assert out == {"Sec": {"v": "yes"}}

    def test_eq_verb_condition_false(self):
        t = _VERB_COND_HEADER + '{Sec :if %eq @tier "gold"}\nv = "yes"\n'
        out = _output_dict(_execute(t, {"tier": "silver"}))
        assert out == {}

    def test_lt_verb_condition_true(self):
        t = _VERB_COND_HEADER + '{Sec :if %lt @age ##25}\nv = "young"\n'
        out = _output_dict(_execute(t, {"age": 20}))
        assert out == {"Sec": {"v": "young"}}

    def test_and_verb_condition(self):
        t = _VERB_COND_HEADER + '{Sec :if %and @a @b}\nv = "ok"\n'
        assert _output_dict(_execute(t, {"a": True, "b": True})) == {"Sec": {"v": "ok"}}
        assert _output_dict(_execute(t, {"a": True, "b": False})) == {}

    def test_or_verb_condition(self):
        t = _VERB_COND_HEADER + '{Sec :if %or @a @b}\nv = "ok"\n'
        assert _output_dict(_execute(t, {"a": False, "b": True})) == {"Sec": {"v": "ok"}}
        assert _output_dict(_execute(t, {"a": False, "b": False})) == {}

    def test_not_verb_condition(self):
        t = _VERB_COND_HEADER + '{Sec :if %not @flag}\nv = "ok"\n'
        assert _output_dict(_execute(t, {"flag": False})) == {"Sec": {"v": "ok"}}
        assert _output_dict(_execute(t, {"flag": True})) == {}

    def test_legacy_quoted_infix_back_compat(self):
        t = _VERB_COND_HEADER + '{Sec}\n_if = "@status = \'active\'"\nv = "yes"\n'
        assert _output_dict(_execute(t, {"status": "active"})) == {"Sec": {"v": "yes"}}
        assert _output_dict(_execute(t, {"status": "void"})) == {}


# ── Conditional Chains (if/elif/else) ──────────────────────────────────────────


_CHAIN = (
    _VERB_COND_HEADER
    + '{High :if %eq @tier "dui"}\nband = "high"\n'
    + '{Young :elif %lt @age ##25}\nband = "young"\n'
    + '{Standard :else}\nband = "standard"\n'
)


class TestConditionalChain:
    def test_if_branch_taken(self):
        out = _output_dict(_execute(_CHAIN, {"tier": "dui", "age": 30}))
        assert out == {"High": {"band": "high"}}

    def test_elif_fall_through(self):
        out = _output_dict(_execute(_CHAIN, {"tier": "standard", "age": 20}))
        assert out == {"Young": {"band": "young"}}

    def test_else_fallback(self):
        out = _output_dict(_execute(_CHAIN, {"tier": "standard", "age": 40}))
        assert out == {"Standard": {"band": "standard"}}

    def test_only_first_matching_branch_emitted(self):
        # if true → elif/else skipped even though elif would also match
        out = _output_dict(_execute(_CHAIN, {"tier": "dui", "age": 20}))
        assert out == {"High": {"band": "high"}}

    def test_chain_breaks_on_non_chain_segment(self):
        t = (
            _VERB_COND_HEADER
            + '{A :if %eq @x "1"}\nv = "a"\n'
            + '{Mid}\nv = "m"\n'
            + '{B :else}\nv = "b"\n'
        )
        result = _execute(t, {"x": "9"})
        # {B :else} has no preceding if (chain broke at {Mid}) → T012
        assert not result.success
        assert any(e.code == "T012" for e in result.errors)

    def test_orphan_elif_raises_t012(self):
        t = _VERB_COND_HEADER + '{Sec :elif %eq @x "1"}\nv = "a"\n'
        result = _execute(t, {"x": "1"})
        assert not result.success
        codes = [e.code for e in result.errors]
        assert "T012" in codes
        msg = next(e.message for e in result.errors if e.code == "T012")
        assert "'elif' segment has no preceding 'if'" == msg

    def test_orphan_else_raises_t012(self):
        t = _VERB_COND_HEADER + '{Sec :else}\nv = "a"\n'
        result = _execute(t, {})
        assert not result.success
        assert any(e.code == "T012" for e in result.errors)


_INTERP_HEADER = (
    '{$}\nodin = "1.0.0"\ntransform = "1.0.0"\ndirection = "json->json"\n'
)


class TestStringInterpolation:
    def test_simple_path_interpolation(self):
        t = _INTERP_HEADER + '{R}\ngreeting = "Hello, ${@.name}!"\n'
        out = _output_dict(_execute(t, {"name": "Alice"}))
        assert out["R"]["greeting"] == "Hello, Alice!"

    def test_multiple_interpolations(self):
        t = _INTERP_HEADER + '{R}\nfull = "${@.first} ${@.last}"\n'
        out = _output_dict(_execute(t, {"first": "John", "last": "Doe"}))
        assert out["R"]["full"] == "John Doe"

    def test_verb_interpolation(self):
        t = _INTERP_HEADER + '{R}\nv = "${%upper @.name}"\n'
        out = _output_dict(_execute(t, {"name": "alice"}))
        assert out["R"]["v"] == "ALICE"

    def test_escaped_dollar_is_literal(self):
        t = _INTERP_HEADER + '{R}\nv = "Total: \\$${@.amount}"\n'
        out = _output_dict(_execute(t, {"amount": "42.00"}))
        assert out["R"]["v"] == "Total: $42.00"

    def test_escaped_marker_preserved(self):
        t = _INTERP_HEADER + '{R}\nv = "Use \\${@.field} for the value"\n'
        out = _output_dict(_execute(t, {"field": "X"}))
        assert out["R"]["v"] == "Use ${@.field} for the value"
