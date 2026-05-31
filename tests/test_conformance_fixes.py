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
