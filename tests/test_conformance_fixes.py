"""Unit tests for core-format conformance fixes."""
import pytest

import odin
from odin.types.values import OdinInteger, OdinReference, OdinString
from odin.types.errors import ParseError


# ── Top-level metadata assignment ($.path) ────────────────────────────────


class TestTopLevelMetadata:
    def test_top_level_meta_routes_to_metadata(self):
        doc = odin.parse('$.foo = "bar"')
        assert doc.metadata.get("foo") == OdinString("bar")
        assert doc.get("$.foo") == OdinString("bar")

    def test_top_level_meta_dotted_key(self):
        doc = odin.parse('$.custom.field = "v"')
        assert doc.metadata.get("custom.field") == OdinString("v")

    def test_canonical_round_trip_is_idempotent(self):
        src = '{$}\nodin = "1.0.0"\nid = "x"\n\n{p}\nname = "John"'
        doc = odin.parse(src)
        canon = odin.canonicalize(doc).decode("utf-8")
        reparsed = odin.parse(canon)
        assert reparsed.metadata.get("id") == OdinString("x")
        assert reparsed.metadata.get("odin") == OdinString("1.0.0")
        assert canon == odin.canonicalize(reparsed).decode("utf-8")


# ── Integer decimal rejection ──────────────────────────────────────────────


class TestIntegerRejection:
    @pytest.mark.parametrize("text", ["##4.2", "##-3.7"])
    def test_fractional_integer_rejected(self, text):
        with pytest.raises(ParseError):
            odin.parse(f"x = {text}")

    def test_scientific_integer_valid(self):
        doc = odin.parse("x = ##1e3")
        v = doc.get("x")
        assert isinstance(v, OdinInteger)
        assert v.value == 1000

    def test_plain_integer_valid(self):
        assert odin.parse("x = ##42").get("x") == OdinInteger(42, raw="42")

    def test_large_integer_preserved(self):
        v = odin.parse("x = ##99999999999999999999").get("x")
        assert isinstance(v, OdinInteger)
        assert v.value == 99999999999999999999


# ── @$.path meta references ────────────────────────────────────────────────


class TestMetaReference:
    def test_meta_ref_with_leading_dot(self):
        assert odin.parse("x = @$.id").get("x") == OdinReference(path="$.id")

    def test_meta_ref_nested(self):
        assert odin.parse("x = @$.i18n.en.name").get("x") == OdinReference(path="$.i18n.en.name")

    def test_const_ref_still_works(self):
        assert odin.parse("x = @$const.NAME").get("x") == OdinReference(path="$const.NAME")


# ── Document chain API ─────────────────────────────────────────────────────


class TestParseDocuments:
    def test_single_document_returns_one(self):
        docs = odin.parse_documents('{$}\nid = "a"')
        assert len(docs) == 1
        assert docs[0].metadata.get("id") == OdinString("a")

    def test_chain_returns_all(self):
        docs = odin.parse_documents('{$}\nid = "a"\n\n---\n\n{$}\nid = "b"')
        assert len(docs) == 2
        assert docs[0].metadata.get("id") == OdinString("a")
        assert docs[1].metadata.get("id") == OdinString("b")

    def test_chain_independent_assignments(self):
        src = '{p}\nname = "John"\n\n---\n\n{p}\nname = "Jane"'
        docs = odin.parse_documents(src)
        assert docs[0].get("p.name") == OdinString("John")
        assert docs[1].get("p.name") == OdinString("Jane")


# ── Canonical numeric precision (raw preserved) ────────────────────────────


class TestCanonicalPrecision:
    def _canon(self, src):
        return odin.canonicalize(odin.parse(src)).decode("utf-8")

    def test_integer_beyond_float_range(self):
        assert self._canon("big = ##9007199254740993") == "big = ##9007199254740993\n"

    def test_large_20_digit_integer(self):
        assert self._canon("huge = ##12345678901234567890") == "huge = ##12345678901234567890\n"

    def test_high_precision_decimal(self):
        assert self._canon("pi = #3.14159265358979323846") == "pi = #3.14159265358979323846\n"

    def test_currency_large_integer_part(self):
        assert self._canon("amt = #$12345678901234567890.50") == "amt = #$12345678901234567890.50\n"

    def test_currency_high_precision_fraction(self):
        assert self._canon("amt = #$123.450000000000000000") == "amt = #$123.450000000000000000\n"

    def test_currency_code_does_not_leak_into_raw(self):
        assert self._canon("p = #$50.00:gbp") == "p = #$50.00:GBP\n"


# ── Canonical modifier order !-* ───────────────────────────────────────────


class TestCanonicalModifierOrder:
    def _canon(self, src):
        return odin.canonicalize(odin.parse(src)).decode("utf-8")

    def test_all_three(self):
        assert self._canon('x = !-*"secret"') == 'x = !-*"secret"\n'

    def test_required_confidential(self):
        assert self._canon('x = !*"secret"') == 'x = !*"secret"\n'

    def test_required_deprecated(self):
        assert self._canon('x = !-"secret"') == 'x = !-"secret"\n'

    def test_deprecated_confidential(self):
        assert self._canon('x = -*"secret"') == 'x = -*"secret"\n'


# ── Schema validation: :if / :unless / :computed / binary / decimal ────────


_BASE = '{$}\nodin = "1.0.0"\nschema = "1.0.0"\n\n'


def _validate(schema_text, input_text):
    doc = odin.parse(input_text)
    schema = odin.parse_schema(schema_text)
    return odin.validate(doc, schema)


class TestConditionalRequirement:
    SCHEMA_UNLESS = _BASE + '{Person}\nstatus =\nphone = ! :unless status = "inactive"'
    SCHEMA_IF = _BASE + '{Person}\nstatus =\nphone = ! :if status = "active"'

    def test_unless_condition_true_not_required(self):
        r = _validate(self.SCHEMA_UNLESS, '{Person}\nstatus = "inactive"')
        assert r.valid

    def test_unless_condition_false_required(self):
        r = _validate(self.SCHEMA_UNLESS, '{Person}\nstatus = "active"')
        assert not r.valid
        assert any(e.code == "V010" and e.path == "Person.phone" for e in r.errors)

    def test_unless_condition_absent_required(self):
        r = _validate(self.SCHEMA_UNLESS, '{Person}\nname = "x"')
        assert not r.valid
        assert any(e.code == "V010" for e in r.errors)

    def test_if_condition_true_required(self):
        r = _validate(self.SCHEMA_IF, '{Person}\nstatus = "active"')
        assert not r.valid
        assert any(e.code == "V010" for e in r.errors)

    def test_if_condition_false_not_required(self):
        r = _validate(self.SCHEMA_IF, '{Person}\nstatus = "inactive"')
        assert r.valid


class TestComputedExclusion:
    SCHEMA = _BASE + '{Order}\ntotal = !# :computed'

    def test_computed_absent_not_required(self):
        r = _validate(self.SCHEMA, '{Order}\nname = "x"')
        assert r.valid


class TestBinarySize:
    SCHEMA = _BASE + '{R}\nhash = ^:(4)'
    SHA = _BASE + '{R}\nhash = ^sha256:(32)'

    def test_exact_byte_length_valid(self):
        assert _validate(self.SCHEMA, '{R}\nhash = ^AAAAAA==').valid

    def test_too_small_fails(self):
        r = _validate(self.SCHEMA, '{R}\nhash = ^AAAA')
        assert not r.valid
        assert any(e.code == "V003" for e in r.errors)

    def test_too_large_fails(self):
        r = _validate(self.SCHEMA, '{R}\nhash = ^AAAAAAA=')
        assert not r.valid
        assert any(e.code == "V003" for e in r.errors)

    def test_sha256_wrong_length_fails(self):
        r = _validate(self.SHA, '{R}\nhash = ^sha256:AAAAAAAAAAAAAAAAAAAAAA==')
        assert not r.valid
        assert any(e.code == "V003" for e in r.errors)


class TestDecimalPlaces:
    SCHEMA = _BASE + '{R}\nrate = #.4'

    def test_exact_valid(self):
        assert _validate(self.SCHEMA, '{R}\nrate = #1.2345').valid

    def test_too_few_fails(self):
        r = _validate(self.SCHEMA, '{R}\nrate = #1.23')
        assert not r.valid
        assert any(e.code == "V003" for e in r.errors)

    def test_too_many_fails(self):
        r = _validate(self.SCHEMA, '{R}\nrate = #1.23456')
        assert not r.valid
        assert any(e.code == "V003" for e in r.errors)


# ── Transform onError default + custom verb echo ───────────────────────────


def _transform(text, source):
    return odin.execute_transform(odin.parse_transform(text), source)


_T_HEAD = ('{$}\nodin = "1.0.0"\ntransform = "1.0.0"\n'
           'direction = "json->json"\ntarget.format = "json"\n')


class TestOnErrorDefault:
    def test_unknown_builtin_verb_surfaces_error(self):
        t = _T_HEAD + '\n{out}\nx = "%nosuchverb @.a"\n'
        r = _transform(t, {"a": 1})
        assert not r.success
        assert any("nosuchverb" in (e.message or "") for e in r.errors)

    def test_custom_verb_echoes_first_arg_no_error(self):
        t = _T_HEAD + '\n{out}\nx = "%&mycustom @.a"\n'
        r = _transform(t, {"a": 7})
        assert r.success
        assert len(r.errors) == 0
        assert r.output.get("out").get("x").as_int() == 7


# ── Transform %lookup miss via onMissing ───────────────────────────────────


def _lookup_transform(on_missing, verb='%lookup "RATE.val" @.code'):
    om = f'target.onMissing = "{on_missing}"\n' if on_missing else ""
    return (
        '{$}\nodin = "1.0.0"\ntransform = "1.0.0"\n'
        'direction = "json->json"\ntarget.format = "json"\n' + om +
        '\n{$table.RATE[code, val]}\n"A", ##10\n\n{out}\nv = ' + verb + '\n'
    )


class TestLookupOnMissing:
    def test_default_silent_null(self):
        r = _transform(_lookup_transform(None), {"code": "ZZZ"})
        assert r.success
        assert len(r.errors) == 0 and len(r.warnings) == 0

    def test_fail_reports_error(self):
        r = _transform(_lookup_transform("fail"), {"code": "ZZZ"})
        assert not r.success
        assert any(e.code == "T004" for e in r.errors)

    def test_warn_reports_warning(self):
        r = _transform(_lookup_transform("warn"), {"code": "ZZZ"})
        assert r.success
        assert len(r.warnings) == 1

    def test_hit_no_report(self):
        r = _transform(_lookup_transform("fail"), {"code": "A"})
        assert r.success
        assert len(r.errors) == 0

    def test_lookup_default_suppresses(self):
        r = _transform(
            _lookup_transform("fail", '%lookupDefault "RATE.val" @.code "NA"'),
            {"code": "ZZZ"},
        )
        assert r.success
        assert len(r.errors) == 0
