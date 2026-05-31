"""Tests for Wave-3 transform conformance fixes."""
import json

import odin
from odin.types.values import OdinString


def _execute(transform_text: str, source):
    t = odin.parse_transform(transform_text)
    return odin.execute_transform(t, source)


def _json(result):
    return json.loads(result.formatted)


# ── Parser: bare segment-directive lines ────────────────────────────────────


class TestBareDirectiveLines:
    def test_bare_loop_counter_from_synthesize_assignments(self):
        doc = odin.parse(
            '{$}\nodin = "1.0.0"\n{rows[]}\n:loop items\n:counter idx\n'
            ':from @other.path\nsku = "@.sku"\n'
        )
        assert doc.get("rows[]._loop") == OdinString(value="items")
        assert doc.get("rows[]._counter") == OdinString(value="idx")
        assert doc.get("rows[]._from") == OdinString(value="@other.path")
        assert doc.get("rows[].sku") == OdinString(value="@.sku")

    def test_bare_loop_with_alias(self):
        doc = odin.parse('{$}\nodin = "1.0.0"\n{rows[]}\n:loop items :as it\n')
        assert doc.get("rows[]._loop") == OdinString(value="items :as it")

    def test_header_inline_loop_captures_to_brace(self):
        doc = odin.parse('{$}\nodin = "1.0.0"\n{rows[] :loop items}\nsku = "@.sku"\n')
        assert doc.get("rows[]._loop") == OdinString(value="items")

    def test_header_inline_counter_and_from(self):
        doc = odin.parse('{$}\nodin = "1.0.0"\n{rows[] :counter idx}\nsku = "@.sku"\n')
        assert doc.get("rows[]._counter") == OdinString(value="idx")
        doc2 = odin.parse('{$}\nodin = "1.0.0"\n{rows[] :from @src}\nsku = "@.sku"\n')
        assert doc2.get("rows[]._from") == OdinString(value="@src")

    def test_bare_directive_not_triggered_in_tabular(self):
        # A tabular header keeps colon-separated columns, not a bare directive.
        doc = odin.parse('{$}\nodin = "1.0.0"\n{rows[] : a, b}\n"x", "y"\n')
        assert doc.get("rows[0].a") == OdinString(value="x")


# ── Engine: validation modifiers (:validate / :enum / :range) ───────────────


_VALIDATE_TRANSFORM = (
    '{$}\nodin = "1.0.0"\ntransform = "1.0.0"\n'
    'direction = "odin->json"\ntarget.format = "json"\n'
    'target.onValidation = "{policy}"\n'
    '{Record}\n'
    'status = "@status :enum A,P,C"\n'
    'year = "@year :range 1900..2100"\n'
    'email = "@email :validate \\"^[^@]+@[^@]+$\\""\n'
)


class TestValidationModifiers:
    def _src(self):
        return {"status": "Z", "year": 1850, "email": "bad"}

    def test_warn_policy_emits_value_with_warnings(self):
        r = _execute(_VALIDATE_TRANSFORM.replace("{policy}", "warn"), self._src())
        assert not r.errors
        assert len(r.warnings) == 3
        out = _json(r)
        assert out["Record"] == {"status": "Z", "year": 1850, "email": "bad"}

    def test_fail_policy_raises_t013(self):
        r = _execute(_VALIDATE_TRANSFORM.replace("{policy}", "fail"), self._src())
        codes = [e.code for e in r.errors]
        assert codes.count("T013") == 3

    def test_skip_policy_drops_failing_fields(self):
        r = _execute(_VALIDATE_TRANSFORM.replace("{policy}", "skip"), self._src())
        assert not r.errors
        assert _json(r)["Record"] == {}

    def test_valid_values_pass(self):
        r = _execute(
            _VALIDATE_TRANSFORM.replace("{policy}", "fail"),
            {"status": "A", "year": 2000, "email": "a@b"},
        )
        assert not r.errors
        assert _json(r)["Record"] == {"status": "A", "year": 2000, "email": "a@b"}


# ── Engine: :object / :raw / :array ─────────────────────────────────────────


class TestStructuralModifiers:
    def test_inline_object(self):
        tf = (
            '{$}\nodin = "1.0.0"\ntransform = "1.0.0"\n'
            'direction = "odin->json"\ntarget.format = "json"\n'
            '{Quote}\ncontact = ":object {name = @n, phone = @p}"\n'
        )
        r = _execute(tf, {"n": "John", "p": "555"})
        assert _json(r)["Quote"]["contact"] == {"name": "John", "phone": "555"}

    def test_raw_json(self):
        tf = (
            '{$}\nodin = "1.0.0"\ntransform = "1.0.0"\n'
            'direction = "odin->json"\ntarget.format = "json"\n'
            '{Doc}\nmeta = "@m :raw"\n'
        )
        r = _execute(tf, {"m": '{"v":2,"tags":["a","b"]}'})
        assert _json(r)["Doc"]["meta"] == {"v": 2, "tags": ["a", "b"]}

    def test_array_wrap(self):
        tf = (
            '{$}\nodin = "1.0.0"\ntransform = "1.0.0"\n'
            'direction = "odin->json"\ntarget.format = "json"\n'
            '{P}\ncodes = "@code :array"\n'
        )
        r = _execute(tf, {"code": "COLL"})
        assert _json(r)["P"]["codes"] == ["COLL"]


# ── Engine: field :if comparison ────────────────────────────────────────────


class TestFieldIfComparison:
    def _tf(self):
        return (
            '{$}\nodin = "1.0.0"\ntransform = "1.0.0"\n'
            'direction = "odin->json"\ntarget.format = "json"\n'
            '{Quote}\n'
            'discount = "@discount :if @tier = gold"\n'
            'surcharge = "@surcharge :if @tier = bronze"\n'
        )

    def test_emits_only_when_comparison_holds(self):
        r = _execute(self._tf(), {"tier": "gold", "discount": 15, "surcharge": 40})
        assert _json(r)["Quote"] == {"discount": 15}

    def test_unless_negates(self):
        tf = (
            '{$}\nodin = "1.0.0"\ntransform = "1.0.0"\n'
            'direction = "odin->json"\ntarget.format = "json"\n'
            '{Q}\nx = "@v :unless @tier = gold"\n'
        )
        assert _json(_execute(tf, {"tier": "gold", "v": 1}))["Q"] == {}
        assert _json(_execute(tf, {"tier": "silver", "v": 1}))["Q"] == {"x": 1}


# ── Engine: :counter readable by name and accumulator ───────────────────────


class TestLoopCounter:
    def test_counter_by_name_and_accumulator(self):
        tf = (
            '{$}\nodin = "1.0.0"\ntransform = "1.0.0"\n'
            'direction = "odin->json"\ntarget.format = "json"\n'
            '{rows[]}\n:loop items\n:counter rownum\n'
            'sku = "@.sku"\nn = "@rownum"\nm = "@$accumulator.rownum"\n'
        )
        r = _execute(tf, {"items": [{"sku": "A"}, {"sku": "B"}]})
        rows = _json(r)["rows"]
        assert rows == [
            {"sku": "A", "n": 0, "m": 0},
            {"sku": "B", "n": 1, "m": 1},
        ]


# ── Engine: computation-only sink sections omitted ──────────────────────────


class TestSinkSegments:
    def test_loop_sink_runs_for_side_effects_only(self):
        tf = (
            '{$}\nodin = "1.0.0"\ntransform = "1.0.0"\n'
            'direction = "odin->json"\ntarget.format = "json"\n'
            '{$accumulator}\ntotal = ##0\n'
            '{_sum[]}\n:loop items\n_ = "%accumulate total @.amount"\n'
            '{Summary}\ntotal = "@$accumulator.total"\n'
        )
        r = _execute(tf, {"items": [{"amount": 10}, {"amount": 20}, {"amount": 30}]})
        out = _json(r)
        assert "_sum" not in out
        assert out["Summary"]["total"] == 60


# ── XML :cdata ──────────────────────────────────────────────────────────────


class TestXmlCdata:
    def test_cdata_wraps_element_text(self):
        tf = (
            '{$}\nodin = "1.0.0"\ntransform = "1.0.0"\n'
            'direction = "odin->xml"\ntarget.format = "xml"\n'
            'emitTypeHints = ?false\n'
            '{Policy}\n'
            'Number = "@number"\n'
            'Description = "@description :cdata"\n'
        )
        r = _execute(tf, {"number": "POL-100", "description": "a < b & c > d"})
        assert "<![CDATA[a < b & c > d]]>" in r.formatted
        assert "<Number>POL-100</Number>" in r.formatted

    def test_cdata_splits_embedded_terminator(self):
        tf = (
            '{$}\nodin = "1.0.0"\ntransform = "1.0.0"\n'
            'direction = "odin->xml"\ntarget.format = "xml"\n'
            'emitTypeHints = ?false\n'
            '{Doc}\nbody = "@b :cdata"\n'
        )
        r = _execute(tf, {"b": "x]]>y"})
        assert "]]]]><![CDATA[>" in r.formatted


# ── Fixed-width lineWidth padding ───────────────────────────────────────────


class TestFixedWidthLineWidth:
    def test_records_padded_to_line_width(self):
        tf = (
            '{$}\nodin = "1.0.0"\ntransform = "1.0.0"\n'
            'direction = "odin->fixed-width"\ntarget.format = "fixed-width"\n'
            '{$target}\nlineWidth = ##20\npadChar = "."\n'
            '{record}\n'
            'code = @code :pos 0 :len 5 :rightPad " "\n'
            'name = @name :pos 5 :len 8 :rightPad " "\n'
        )
        r = _execute(tf, {"code": "AB", "name": "WIDGET"})
        line = r.formatted.rstrip("\n")
        assert line == "AB   WIDGET  ......."
        assert len(line) == 20

    def test_no_line_width_trims_trailing(self):
        tf = (
            '{$}\nodin = "1.0.0"\ntransform = "1.0.0"\n'
            'direction = "odin->fixed-width"\ntarget.format = "fixed-width"\n'
            '{record}\n'
            'code = @code :pos 0 :len 5 :rightPad " "\n'
        )
        r = _execute(tf, {"code": "AB"})
        assert r.formatted.rstrip("\n") == "AB"
