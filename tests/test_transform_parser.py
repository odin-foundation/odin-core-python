"""Tests for the ODIN transform parser."""

import pytest

from odin.transform.transform_parser import parse_transform
from odin.transform.types import (
    OdinTransform,
    ConfidentialMode,
    CopyExpression,
    TransformExpression,
    LiteralExpression,
    ObjectExpression,
)


# ── Direction Header ───────────────────────────────────────────────────────────


class TestDirectionHeader:
    def test_parse_json_to_odin_direction(self):
        t = parse_transform('{$}\nodin = "1.0.0"\ntransform = "1.0.0"\ndirection = "json->odin"')
        assert t.metadata.direction == "json->odin"

    def test_parse_odin_to_json_direction(self):
        t = parse_transform('{$}\ndirection = "odin->json"')
        assert t.metadata.direction == "odin->json"

    def test_parse_json_to_json_direction(self):
        t = parse_transform('{$}\ndirection = "json->json"')
        assert t.metadata.direction == "json->json"

    def test_parse_csv_to_odin_direction(self):
        t = parse_transform('{$}\ndirection = "csv->odin"')
        assert t.metadata.direction == "csv->odin"

    def test_parse_odin_version(self):
        t = parse_transform('{$}\nodin = "1.0.0"\ntransform = "2.0.0"')
        assert t.metadata.odin_version == "1.0.0"
        assert t.metadata.transform_version == "2.0.0"

    def test_parse_name_and_description(self):
        t = parse_transform('{$}\nname = "my-transform"\ndescription = "desc"')
        assert t.metadata.name == "my-transform"
        assert t.metadata.description == "desc"


# ── Target Config ──────────────────────────────────────────────────────────────


class TestTargetConfig:
    def test_parse_target_format(self):
        t = parse_transform('{$}\ntarget.format = "json"')
        assert t.target.format == "json"

    def test_parse_target_format_odin(self):
        t = parse_transform('{$}\ntarget.format = "odin"')
        assert t.target.format == "odin"

    def test_parse_target_options(self):
        t = parse_transform('{$}\ntarget.format = "json"\ntarget.indent = "2"')
        assert t.target.options.get("indent") == "2"

    def test_parse_target_csv_options(self):
        t = parse_transform('{$}\ntarget.format = "csv"\ntarget.delimiter = ","')
        assert t.target.format == "csv"
        assert t.target.options.get("delimiter") == ","


# ── Source Config ──────────────────────────────────────────────────────────────


class TestSourceConfig:
    def test_parse_source_format(self):
        t = parse_transform('{$}\nsource.format = "csv"')
        assert t.source is not None
        assert t.source.format == "csv"

    def test_no_source_config(self):
        t = parse_transform('{$}\nodin = "1.0.0"')
        assert t.source is None

    def test_source_namespace(self):
        t = parse_transform('{$}\nsource.format = "xml"\nsource.namespace.ns = "http://example.com"')
        assert t.source.namespaces.get("ns") == "http://example.com"


# ── Enforce Confidential ──────────────────────────────────────────────────────


class TestEnforceConfidential:
    def test_redact_mode(self):
        t = parse_transform('{$}\nenforceConfidential = "redact"')
        assert t.enforce_confidential == ConfidentialMode.REDACT

    def test_mask_mode(self):
        t = parse_transform('{$}\nenforceConfidential = "mask"')
        assert t.enforce_confidential == ConfidentialMode.MASK

    def test_no_confidential(self):
        t = parse_transform('{$}\nodin = "1.0.0"')
        assert t.enforce_confidential is None


# ── Simple Mappings ────────────────────────────────────────────────────────────


class TestSimpleMappings:
    def test_single_copy_mapping(self):
        t = parse_transform('{$}\ndirection = "json->json"\n{}\nName = @name')
        assert len(t.segments) >= 1
        seg = t.segments[0]
        assert len(seg.mappings) >= 1
        m = seg.mappings[0]
        assert m.target == "Name"
        assert isinstance(m.expression, CopyExpression)
        assert m.expression.path == "name"

    def test_multiple_mappings(self):
        t = parse_transform(
            '{$}\ndirection = "json->json"\n{}\nName = @name\nAge = @age'
        )
        seg = t.segments[0]
        assert len(seg.mappings) >= 2
        assert seg.mappings[0].target == "Name"
        assert seg.mappings[1].target == "Age"

    def test_nested_reference(self):
        t = parse_transform('{$}\ndirection = "json->json"\n{}\nCity = @address.city')
        m = t.segments[0].mappings[0]
        assert isinstance(m.expression, CopyExpression)
        assert m.expression.path == "address.city"

    def test_array_reference(self):
        t = parse_transform('{$}\ndirection = "json->json"\n{}\nFirst = @items[0].name')
        m = t.segments[0].mappings[0]
        assert isinstance(m.expression, CopyExpression)
        assert m.expression.path == "items[0].name"

    def test_dot_reference(self):
        """@.field means current context relative."""
        t = parse_transform('{$}\ndirection = "json->json"\n{}\nName = @.name')
        m = t.segments[0].mappings[0]
        assert isinstance(m.expression, CopyExpression)
        assert m.expression.path == ".name"


# ── Literal Values ─────────────────────────────────────────────────────────────


class TestLiteralValues:
    def test_string_literal(self):
        t = parse_transform('{$}\ndirection = "json->json"\n{}\nType = "fixed"')
        m = t.segments[0].mappings[0]
        assert isinstance(m.expression, LiteralExpression)

    def test_number_literal(self):
        t = parse_transform('{$}\ndirection = "json->json"\n{}\nCount = ##42')
        m = t.segments[0].mappings[0]
        assert isinstance(m.expression, LiteralExpression)

    def test_boolean_literal(self):
        t = parse_transform('{$}\ndirection = "json->json"\n{}\nActive = ?true')
        m = t.segments[0].mappings[0]
        assert isinstance(m.expression, LiteralExpression)

    def test_null_literal(self):
        t = parse_transform('{$}\ndirection = "json->json"\n{}\nOld = ~')
        m = t.segments[0].mappings[0]
        assert isinstance(m.expression, LiteralExpression)

    def test_currency_literal(self):
        t = parse_transform('{$}\ndirection = "json->json"\n{}\nPrice = #$99.99')
        m = t.segments[0].mappings[0]
        assert isinstance(m.expression, LiteralExpression)

    def test_float_literal(self):
        t = parse_transform('{$}\ndirection = "json->json"\n{}\nRate = #3.14')
        m = t.segments[0].mappings[0]
        assert isinstance(m.expression, LiteralExpression)


# ── Verb Expressions ───────────────────────────────────────────────────────────


class TestVerbExpressions:
    def test_verb_with_reference_arg(self):
        t = parse_transform('{$}\ndirection = "json->json"\n{}\nUpper = %upper @name')
        m = t.segments[0].mappings[0]
        assert isinstance(m.expression, TransformExpression)
        assert m.expression.call.verb == "upper"
        assert len(m.expression.call.args) == 1

    def test_verb_with_multiple_args(self):
        t = parse_transform('{$}\ndirection = "json->json"\n{}\nResult = %concat @first " " @last')
        m = t.segments[0].mappings[0]
        assert isinstance(m.expression, TransformExpression)
        assert m.expression.call.verb == "concat"
        assert len(m.expression.call.args) >= 3

    def test_verb_with_literal_arg(self):
        t = parse_transform('{$}\ndirection = "json->json"\n{}\nFixed = %default @val "N/A"')
        m = t.segments[0].mappings[0]
        assert isinstance(m.expression, TransformExpression)
        assert m.expression.call.verb == "default"

    def test_nested_verb(self):
        t = parse_transform('{$}\ndirection = "json->json"\n{}\nOut = %upper %concat @first @last')
        m = t.segments[0].mappings[0]
        assert isinstance(m.expression, TransformExpression)
        assert m.expression.call.verb == "upper"

    def test_custom_verb(self):
        t = parse_transform('{$}\ndirection = "json->json"\n{}\nOut = %&custom.myVerb @val')
        m = t.segments[0].mappings[0]
        assert isinstance(m.expression, TransformExpression)
        assert m.expression.call.is_custom is True


# ── Modifier Mappings ──────────────────────────────────────────────────────────


class TestModifierMappings:
    def test_confidential_modifier(self):
        t = parse_transform('{$}\ndirection = "json->json"\n{}\nSSN = @ssn :confidential')
        m = t.segments[0].mappings[0]
        # Should have modifiers or directives indicating confidential
        has_confidential = (
            (m.modifiers is not None and m.modifiers.confidential)
            or any(d.name == "confidential" for d in m.directives)
        )
        assert has_confidential

    def test_required_modifier(self):
        t = parse_transform('{$}\ndirection = "json->json"\n{}\nName = @name :required')
        m = t.segments[0].mappings[0]
        has_required = (
            (m.modifiers is not None and m.modifiers.required)
            or any(d.name == "required" for d in m.directives)
        )
        assert has_required

    def test_deprecated_modifier(self):
        t = parse_transform('{$}\ndirection = "json->json"\n{}\nOld = @old :deprecated')
        m = t.segments[0].mappings[0]
        has_deprecated = (
            (m.modifiers is not None and m.modifiers.deprecated)
            or any(d.name == "deprecated" for d in m.directives)
        )
        assert has_deprecated

    def test_type_directive(self):
        t = parse_transform('{$}\ndirection = "json->json"\n{}\nAge = @age :type "integer"')
        m = t.segments[0].mappings[0]
        assert any(d.name == "type" for d in m.directives)

    def test_default_directive(self):
        t = parse_transform('{$}\ndirection = "json->json"\n{}\nState = @state :default "CA"')
        m = t.segments[0].mappings[0]
        assert any(d.name == "default" for d in m.directives)

    def test_multiple_directives(self):
        t = parse_transform('{$}\ndirection = "json->json"\n{}\nSSN = @ssn :required :confidential')
        m = t.segments[0].mappings[0]
        has_required = (
            (m.modifiers is not None and m.modifiers.required)
            or any(d.name == "required" for d in m.directives)
        )
        has_confidential = (
            (m.modifiers is not None and m.modifiers.confidential)
            or any(d.name == "confidential" for d in m.directives)
        )
        assert has_required
        assert has_confidential


# ── Named Sections ─────────────────────────────────────────────────────────────


class TestNamedSections:
    def test_named_segment(self):
        t = parse_transform(
            '{$}\ndirection = "json->json"\n{Customer}\nName = @name'
        )
        seg = [s for s in t.segments if s.name == "Customer"]
        assert len(seg) == 1
        assert len(seg[0].mappings) >= 1

    def test_multiple_segments(self):
        t = parse_transform(
            '{$}\ndirection = "json->json"\n{Customer}\nName = @name\n{Order}\nId = @id'
        )
        names = [s.name for s in t.segments]
        assert "Customer" in names
        assert "Order" in names

    def test_root_segment(self):
        t = parse_transform('{$}\ndirection = "json->json"\n{}\nName = @name')
        # Root segment has empty name
        root_segs = [s for s in t.segments if s.name == "" or s.name == "$"]
        assert len(root_segs) >= 1


# ── Array Iteration ────────────────────────────────────────────────────────────


class TestArrayIteration:
    def test_array_segment(self):
        text = (
            '{$}\ndirection = "json->json"\n'
            '{Items[]}\n'
            '_ = @items :loop\n'
            'Name = @.name'
        )
        t = parse_transform(text)
        arr_segs = [s for s in t.segments if "Items" in s.name or s.source_path]
        assert len(arr_segs) >= 1

    def test_array_segment_with_source_path(self):
        text = (
            '{$}\ndirection = "json->json"\n'
            '{Items[]}\n'
            '_ = @items :loop\n'
            'Sku = @.sku\n'
            'Qty = @.quantity'
        )
        t = parse_transform(text)
        # Should have an array segment with mappings
        found = False
        for seg in t.segments:
            if seg.source_path or seg.is_array:
                found = True
                break
        assert found


# ── Constants ──────────────────────────────────────────────────────────────────


class TestConstants:
    def test_parse_constant(self):
        t = parse_transform('{$}\nconst.VERSION = "1.0"')
        assert "VERSION" in t.constants

    def test_parse_multiple_constants(self):
        t = parse_transform('{$}\nconst.A = "alpha"\nconst.B = "beta"')
        assert "A" in t.constants
        assert "B" in t.constants


# ── Accumulators ───────────────────────────────────────────────────────────────


class TestAccumulators:
    def test_parse_accumulator(self):
        t = parse_transform('{$}\naccumulator.total = ##0')
        assert "total" in t.accumulators
        assert t.accumulators["total"].name == "total"

    def test_accumulator_persist(self):
        t = parse_transform('{$}\naccumulator.total = ##0\naccumulator.total._persist = ?true')
        assert t.accumulators["total"].persist is True


# ── Lookup Tables ──────────────────────────────────────────────────────────────


class TestLookupTables:
    def test_parse_table(self):
        t = parse_transform(
            '{$}\ntable.states[0].code = "CA"\n'
            'table.states[0].name = "California"\n'
            'table.states[1].code = "NY"\n'
            'table.states[1].name = "New York"'
        )
        assert "states" in t.tables
        tbl = t.tables["states"]
        assert "code" in tbl.columns
        assert "name" in tbl.columns
        assert len(tbl.rows) == 2


# ── Edge Cases ─────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_transform(self):
        t = parse_transform('{$}\nodin = "1.0.0"')
        assert isinstance(t, OdinTransform)
        assert len(t.segments) == 0

    def test_comment_lines_ignored(self):
        t = parse_transform('{$}\ndirection = "json->json"\n; comment\n{}\nName = @name')
        seg = t.segments[0]
        assert len(seg.mappings) >= 1

    def test_transform_with_all_sections(self):
        text = (
            '{$}\n'
            'odin = "1.0.0"\n'
            'transform = "1.0.0"\n'
            'direction = "json->json"\n'
            'target.format = "json"\n'
            'enforceConfidential = "redact"\n'
            'const.DEFAULT = "N/A"\n'
            '{Customer}\n'
            'Name = @name\n'
            'SSN = @ssn :confidential\n'
        )
        t = parse_transform(text)
        assert t.metadata.direction == "json->json"
        assert t.target.format == "json"
        assert t.enforce_confidential == ConfidentialMode.REDACT
        assert "DEFAULT" in t.constants
        assert len(t.segments) >= 1
