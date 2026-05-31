"""Unit tests for schema-validator conformance fixes."""

import odin
from odin.types.schema import (
    UnionType,
    NullType,
    PercentType,
    TypeRefType,
    DateType,
    TimestampType,
    BoundsConstraint,
    PatternConstraint,
)


META = '{$}\nodin = "1.0.0"\nschema = "1.0.0"\n\n'


def _field(schema_text):
    sch = odin.parse_schema(META + schema_text)
    return sch


# ── Fix 1: type intersection ───────────────────────────────────────────────


class TestTypeIntersection:
    def test_intersection_stores_both_members(self):
        sch = _field("{@hasName}\nname = !\n\n{@hasAge}\nage = !##\n\n{customer}\n= @hasName & @hasAge")
        comp = sch.fields["customer._composition"]
        assert isinstance(comp.field_type, TypeRefType)
        assert comp.field_type.name == "hasName&hasAge"

    def test_intersection_all_required_present_valid(self):
        sch = _field("{@hasName}\nname = !\n\n{@hasAge}\nage = !##\n\n{customer}\n= @hasName & @hasAge")
        doc = odin.parse('{customer}\nname = "Bob"\nage = ##5')
        assert odin.validate(doc, sch).valid

    def test_intersection_missing_member_field_fails_v001(self):
        sch = _field("{@hasName}\nname = !\n\n{@hasAge}\nage = !##\n\n{customer}\n= @hasName & @hasAge")
        doc = odin.parse('{customer}\nname = "Bob"')
        result = odin.validate(doc, sch)
        assert not result.valid
        assert any(e.code == "V001" and e.path == "customer.age" for e in result.errors)

    def test_intersection_unresolved_member_fails_v013(self):
        sch = _field("{@hasName}\nname = !\n\n{customer}\n= @hasName & @doesNotExist")
        doc = odin.parse('{customer}\nname = "Bob"')
        result = odin.validate(doc, sch)
        assert not result.valid
        assert any(e.code == "V013" for e in result.errors)


# ── Fix 2: temporal range bounds ───────────────────────────────────────────


class TestTemporalBounds:
    def test_bounds_preserved_as_strings(self):
        sch = _field("{root}\nd = date:(2020-06-15..2020-06-20)")
        c = sch.fields["root.d"].constraints[0]
        assert isinstance(c, BoundsConstraint)
        assert c.min == "2020-06-15" and c.max == "2020-06-20"

    def test_in_range_valid(self):
        sch = _field("{root}\nd = date:(2020-06-15..2020-06-20)")
        assert odin.validate(odin.parse("{root}\nd = 2020-06-17"), sch).valid

    def test_below_min_fails_v003(self):
        sch = _field("{root}\nd = date:(2020-06-15..2020-06-20)")
        result = odin.validate(odin.parse("{root}\nd = 2020-06-10"), sch)
        assert any(e.code == "V003" and e.path == "root.d" for e in result.errors)

    def test_above_max_fails_v003(self):
        sch = _field("{root}\nd = date:(2020-06-15..2020-06-20)")
        result = odin.validate(odin.parse("{root}\nd = 2020-06-25"), sch)
        assert any(e.code == "V003" and e.path == "root.d" for e in result.errors)


# ── Fix 3: percent type ─────────────────────────────────────────────────────


class TestPercentType:
    def test_percent_is_first_class(self):
        sch = _field("{root}\ntax = #%")
        assert isinstance(sch.fields["root.tax"].field_type, PercentType)

    def test_percent_value_valid(self):
        sch = _field("{root}\ntax = #%")
        assert odin.validate(odin.parse("{root}\ntax = #%0.15"), sch).valid

    def test_non_percent_rejected_v002(self):
        sch = _field("{root}\ntax = #%")
        result = odin.validate(odin.parse('{root}\ntax = "fifteen"'), sch)
        assert any(e.code == "V002" and e.path == "root.tax" for e in result.errors)


# ── Fix 4: typed default values ─────────────────────────────────────────────


class TestTypedDefaults:
    def test_integer_default(self):
        assert _field("{root}\na = ##3").fields["root.a"].default_value == {"type": "integer", "value": 3}

    def test_number_default(self):
        assert _field("{root}\nb = #0.05").fields["root.b"].default_value == {"type": "number", "value": 0.05}

    def test_currency_default(self):
        d = _field("{root}\nc = #$5.00").fields["root.c"].default_value
        assert d["type"] == "currency" and d["value"] == 5

    def test_percent_default(self):
        assert _field("{root}\np = #%0.15").fields["root.p"].default_value == {"type": "percent", "value": 0.15}

    def test_default_after_bounds(self):
        f = _field("{root}\npriority = ##:(1..5) ##3").fields["root.priority"]
        assert f.default_value == {"type": "integer", "value": 3}
        assert f.constraints[0].min == 1 and f.constraints[0].max == 5


# ── Fix 5: union edge cases ─────────────────────────────────────────────────


class TestUnionEdgeCases:
    def test_date_timestamp_keeps_both(self):
        ft = _field("{root}\nu = date|timestamp").fields["root.u"].field_type
        assert isinstance(ft, UnionType)
        assert sorted(t.kind for t in ft.types) == ["date", "timestamp"]

    def test_number_null_keeps_both(self):
        ft = _field("{root}\nn = #|~").fields["root.n"].field_type
        assert isinstance(ft, UnionType)
        assert sorted(t.kind for t in ft.types) == ["null", "number"]

    def test_union_null_member_accepts_null(self):
        sch = _field("{root}\nn = #|~")
        assert odin.validate(odin.parse("{root}\nn = ~"), sch).valid

    def test_union_date_timestamp_accepts_timestamp(self):
        sch = _field("{root}\nu = date|timestamp")
        assert odin.validate(odin.parse("{root}\nu = 2020-06-17T10:00:00Z"), sch).valid


# ── Fix 6: :if after a pattern constraint ──────────────────────────────────


class TestPatternThenIf:
    SCHEMA = "{root}\nfield = !:/^[a-z]+$/:if method = paypal\nmethod = "

    def test_pattern_and_conditional_captured(self):
        f = _field(self.SCHEMA).fields["root.field"]
        assert any(isinstance(c, PatternConstraint) and c.pattern == "^[a-z]+$" for c in f.constraints)
        assert any(c.field == "method" and c.operator == "=" and c.value == "paypal" for c in f.conditionals)

    def test_required_when_condition_met_v010(self):
        sch = _field(self.SCHEMA)
        result = odin.validate(odin.parse('{root}\nmethod = "paypal"'), sch)
        assert any(e.code == "V010" and e.path == "root.field" for e in result.errors)

    def test_optional_when_condition_unmet(self):
        sch = _field(self.SCHEMA)
        assert odin.validate(odin.parse('{root}\nmethod = "stripe"'), sch).valid

    def test_pattern_enforced_v004(self):
        sch = _field(self.SCHEMA)
        result = odin.validate(odin.parse('{root}\nfield = "ABC123"\nmethod = "paypal"'), sch)
        assert any(e.code == "V004" and e.path == "root.field" for e in result.errors)


# ── Fix 7: glued :computed / :immutable on a temporal type ──────────────────


class TestGluedDirectives:
    def test_immutable_keeps_type(self):
        f = _field("{root}\ncreated_at = !timestamp:immutable").fields["root.created_at"]
        assert isinstance(f.field_type, TimestampType)
        assert f.required and f.immutable

    def test_computed_keeps_type(self):
        f = _field("{root}\nstamp = date:computed").fields["root.stamp"]
        assert isinstance(f.field_type, DateType)
        assert f.computed


# ── Fix 8: field-level typeRef recursive validation ─────────────────────────


class TestFieldTypeRef:
    SCHEMA = "{@address}\nstreet = !\ncity = !\n\n{customer}\nname = !\nbilling = @address"

    def test_missing_nested_required_fails_v001(self):
        sch = _field(self.SCHEMA)
        result = odin.validate(odin.parse('{customer}\nname = "X"\nbilling.street = "Main"'), sch)
        assert any(e.code == "V001" and e.path == "customer.billing.city" for e in result.errors)

    def test_absent_optional_subobject_valid(self):
        sch = _field(self.SCHEMA)
        assert odin.validate(odin.parse('{customer}\nname = "X"'), sch).valid

    def test_complete_nested_valid(self):
        sch = _field(self.SCHEMA)
        doc = odin.parse('{customer}\nname = "X"\nbilling.street = "Main"\nbilling.city = "NYC"')
        assert odin.validate(doc, sch).valid


# ── Fix 9: invariant null operand ───────────────────────────────────────────


class TestInvariantNullOperand:
    def test_arithmetic_null_operand_fails_v008(self):
        sch = _field("{order}\ntotal = #$\nsubtotal = #$\ntax = ~#$\n:invariant total = subtotal + tax")
        doc = odin.parse("{order}\ntotal = #$10.00\nsubtotal = #$10.00\ntax = ~")
        result = odin.validate(doc, sch)
        assert any(e.code == "V008" and e.path == "order" for e in result.errors)

    def test_all_present_consistent_valid(self):
        sch = _field("{order}\ntotal = #$\nsubtotal = #$\ntax = #$\n:invariant total = subtotal + tax")
        doc = odin.parse("{order}\ntotal = #$12.00\nsubtotal = #$10.00\ntax = #$2.00")
        assert odin.validate(doc, sch).valid

    def test_comparison_null_operand_fails_v008(self):
        sch = _field("{range}\nstart = ~#\nend = ~#\n:invariant end >= start")
        doc = odin.parse("{range}\nend = #5\nstart = ~")
        result = odin.validate(doc, sch)
        assert any(e.code == "V008" and e.path == "range" for e in result.errors)
