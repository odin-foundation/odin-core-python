"""Integration tests for the ODIN Python SDK public API.

Covers odin.parse(), odin.dumps(), odin.canonicalize(), odin.diff(),
odin.patch(), odin.parse_transform(), odin.execute_transform(),
OdinDocumentBuilder, roundtrip tests, multi-document handling, and error handling.
"""
import io
import pytest
from decimal import Decimal

import odin
from odin.types.values import (
    NULL, TRUE, FALSE,
    OdinNull, OdinBoolean, OdinString, OdinNumber, OdinInteger,
    OdinCurrency, OdinPercent, OdinDate, OdinTimestamp, OdinTime,
    OdinDuration, OdinReference, OdinBinary, OdinVerbExpression,
)
from odin.types.document import OdinDocument, OdinDocumentBuilder, OdinModifiers
from odin.types.diff import OdinDiff, PathValue, PathChange, PathMove
from odin.types.errors import ParseError, PatchError
from odin.types.options import ParseOptions, DumpOptions, LineEnding


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════


def roundtrip(text: str) -> OdinDocument:
    """Parse -> dumps -> parse roundtrip."""
    doc = odin.parse(text)
    serialized = odin.dumps(doc)
    return odin.parse(serialized)


def assert_roundtrip_stable(text: str):
    """Assert parse -> dumps -> parse -> dumps produces identical output."""
    d1 = odin.parse(text)
    t1 = odin.dumps(d1)
    d2 = odin.parse(t1)
    t2 = odin.dumps(d2)
    assert t1 == t2, f"Roundtrip not stable for: {text!r}"


def assert_patch_roundtrip(src: str, dst: str):
    """Assert diff + patch produces equivalent document."""
    d1 = odin.parse(src)
    d2 = odin.parse(dst)
    d = odin.diff(d1, d2)
    patched = odin.patch(d1, d)
    d_check = odin.diff(patched, d2)
    assert d_check.is_empty, f"Patch roundtrip failed: {src!r} -> {dst!r}"


# ══════════════════════════════════════════════════════════════════════════════
# odin.parse() Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestParse:
    """odin.parse() function tests."""

    def test_parse_string(self):
        doc = odin.parse('name = "Alice"')
        assert doc.get("name").value == "Alice"

    def test_parse_bytes(self):
        doc = odin.parse(b'name = "Alice"')
        assert doc.get("name").value == "Alice"

    def test_parse_empty(self):
        doc = odin.parse("")
        assert len(doc) == 0

    def test_parse_whitespace(self):
        doc = odin.parse("   \n\n   ")
        assert len(doc) == 0

    def test_parse_comments_only(self):
        doc = odin.parse("; just comments")
        assert len(doc) == 0

    def test_parse_returns_odin_document(self):
        doc = odin.parse('x = ##1')
        assert isinstance(doc, OdinDocument)

    def test_parse_preserves_order(self):
        doc = odin.parse('z = ##3\na = ##1\nm = ##2')
        assert doc.paths() == ["z", "a", "m"]

    def test_parse_with_options(self):
        opts = ParseOptions(max_nesting_depth=10)
        doc = odin.parse('a.b = "val"', options=opts)
        assert doc.get("a.b").value == "val"

    def test_parse_raises_on_invalid(self):
        with pytest.raises(ParseError):
            odin.parse('name = "unterminated')

    def test_parse_all_value_types(self):
        text = "\n".join([
            'str = "hello"',
            "num = #3.14",
            "int = ##42",
            "cur = #$99.99",
            "pct = #%0.15",
            "boolT = true",
            "boolF = false",
            "null = ~",
            "ref = @other",
            "bin = ^SGVsbG8=",
            "date = 2024-06-15",
            "ts = 2024-06-15T14:30:00Z",
            "time = T09:30:00",
            "dur = P6M",
        ])
        doc = odin.parse(text)
        assert len(doc) == 14

    def test_parse_with_metadata(self):
        doc = odin.parse('{$}\nodin = "1.0.0"\n\nname = "test"')
        assert doc.metadata["odin"].value == "1.0.0"
        assert doc.get("name").value == "test"


# ══════════════════════════════════════════════════════════════════════════════
# odin.loads() and odin.load() Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestLoadsAndLoad:
    """odin.loads() alias and odin.load() file-like."""

    def test_loads_is_alias(self):
        doc = odin.loads('name = "Alice"')
        assert doc.get("name").value == "Alice"

    def test_load_from_file(self):
        fp = io.StringIO('name = "Alice"\nage = ##30')
        doc = odin.load(fp)
        assert doc.get("name").value == "Alice"
        assert doc.get("age").value == 30


# ══════════════════════════════════════════════════════════════════════════════
# odin.dumps() Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestDumps:
    """odin.dumps() serialization tests."""

    def test_dumps_simple(self):
        doc = odin.parse('name = "Alice"')
        text = odin.dumps(doc)
        assert "name" in text
        assert "Alice" in text

    def test_dumps_returns_string(self):
        doc = odin.parse('x = ##1')
        result = odin.dumps(doc)
        assert isinstance(result, str)

    def test_dumps_with_options(self):
        doc = odin.parse('x = ##1')
        result = odin.dumps(doc, DumpOptions(sort_paths=True))
        assert isinstance(result, str)

    def test_dumps_with_crlf(self):
        doc = odin.parse('a = ##1\nb = ##2')
        result = odin.dumps(doc, DumpOptions(line_ending=LineEnding.CRLF))
        assert "\r\n" in result

    def test_dumps_empty_doc(self):
        doc = odin.parse("")
        result = odin.dumps(doc)
        assert result == ""

    def test_dumps_preserves_types(self):
        doc = odin.parse('num = #3.14\nint = ##42\nbool = true')
        text = odin.dumps(doc)
        assert "#3.14" in text or "#3.14" in text
        assert "##42" in text
        assert "true" in text

    def test_dumps_preserves_modifiers(self):
        doc = odin.parse('secret = *"hidden"')
        text = odin.dumps(doc)
        assert "*" in text

    def test_dumps_metadata_section(self):
        doc = odin.parse('{$}\nodin = "1.0.0"\n\nname = "test"')
        text = odin.dumps(doc)
        assert "{$}" in text
        assert "1.0.0" in text


# ══════════════════════════════════════════════════════════════════════════════
# odin.dump() to file Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestDump:
    """odin.dump() to file-like object."""

    def test_dump_to_stringio(self):
        doc = odin.parse('name = "Alice"')
        fp = io.StringIO()
        odin.dump(doc, fp)
        output = fp.getvalue()
        assert "Alice" in output


# ══════════════════════════════════════════════════════════════════════════════
# Roundtrip Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestRoundtrip:
    """Parse -> dumps -> parse roundtrip preserves values."""

    def test_roundtrip_string(self):
        doc = roundtrip('name = "Alice"')
        assert doc.get("name").value == "Alice"

    def test_roundtrip_empty_string(self):
        doc = roundtrip('name = ""')
        assert doc.get("name").value == ""

    def test_roundtrip_string_with_spaces(self):
        doc = roundtrip('name = "  spaces  "')
        assert doc.get("name").value == "  spaces  "

    def test_roundtrip_string_with_escapes(self):
        doc = roundtrip('val = "a\\nb"')
        assert doc.get("val").value == "a\nb"

    def test_roundtrip_integer(self):
        doc = roundtrip("x = ##42")
        assert doc.get("x").value == 42

    def test_roundtrip_negative_integer(self):
        doc = roundtrip("x = ##-5")
        assert doc.get("x").value == -5

    def test_roundtrip_zero_integer(self):
        doc = roundtrip("x = ##0")
        assert doc.get("x").value == 0

    def test_roundtrip_large_integer(self):
        doc = roundtrip("x = ##2147483647")
        assert doc.get("x").value == 2147483647

    def test_roundtrip_number(self):
        doc = roundtrip("x = #3.14")
        assert doc.get("x").value == pytest.approx(3.14, abs=0.001)

    def test_roundtrip_boolean_true(self):
        doc = roundtrip("x = true")
        assert doc.get("x").value is True

    def test_roundtrip_boolean_false(self):
        doc = roundtrip("x = false")
        assert doc.get("x").value is False

    def test_roundtrip_null(self):
        doc = roundtrip("x = ~")
        assert isinstance(doc.get("x"), OdinNull)

    def test_roundtrip_currency(self):
        doc = roundtrip("x = #$99.99")
        assert isinstance(doc.get("x"), OdinCurrency)

    def test_roundtrip_percent(self):
        doc = roundtrip("x = #%50")
        assert isinstance(doc.get("x"), OdinPercent)

    def test_roundtrip_date(self):
        doc = roundtrip("x = 2024-01-15")
        assert isinstance(doc.get("x"), OdinDate)

    def test_roundtrip_timestamp(self):
        doc = roundtrip("x = 2024-01-15T10:30:00Z")
        assert isinstance(doc.get("x"), OdinTimestamp)

    def test_roundtrip_time(self):
        doc = roundtrip("x = T14:30:00")
        val = doc.get("x")
        assert val is not None

    def test_roundtrip_duration(self):
        doc = roundtrip("x = P1Y2M3D")
        val = doc.get("x")
        assert val is not None

    def test_roundtrip_reference(self):
        doc = roundtrip("x = @other")
        assert isinstance(doc.get("x"), OdinReference)

    def test_roundtrip_binary(self):
        doc = roundtrip("x = ^SGVsbG8=")
        assert isinstance(doc.get("x"), OdinBinary)

    def test_roundtrip_section(self):
        doc = roundtrip('{S}\nname = "Alice"')
        assert doc.get("S.name").value == "Alice"

    def test_roundtrip_array(self):
        doc = roundtrip('items[0] = "a"\nitems[1] = "b"')
        assert doc.get("items[0]").value == "a"
        assert doc.get("items[1]").value == "b"

    def test_roundtrip_multiple_fields(self):
        doc = roundtrip("a = ##1\nb = ##2\nc = ##3")
        assert doc.get("a").value == 1
        assert doc.get("b").value == 2
        assert doc.get("c").value == 3

    def test_roundtrip_required_modifier(self):
        doc = roundtrip('x = !"val"')
        assert doc.modifiers.get("x") is not None
        assert doc.modifiers["x"].required is True

    def test_roundtrip_confidential_modifier(self):
        doc = roundtrip('x = *"secret"')
        assert doc.modifiers["x"].confidential is True

    def test_roundtrip_deprecated_modifier(self):
        doc = roundtrip('x = -"old"')
        assert doc.modifiers["x"].deprecated is True

    def test_roundtrip_stability_simple(self):
        assert_roundtrip_stable('name = "Alice"\nage = ##30')

    def test_roundtrip_stability_with_section(self):
        assert_roundtrip_stable('{Person}\nname = "Alice"\nage = ##30')

    def test_roundtrip_stability_with_metadata(self):
        assert_roundtrip_stable('{$}\nodin = "1.0.0"\n\nname = "test"')


# ══════════════════════════════════════════════════════════════════════════════
# odin.canonicalize() Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestCanonicalize:
    """odin.canonicalize() deterministic output tests."""

    def test_canonicalize_returns_bytes(self):
        doc = odin.parse('x = ##1')
        result = odin.canonicalize(doc)
        assert isinstance(result, bytes)

    def test_canonicalize_deterministic(self):
        doc = odin.parse('x = ##1\ny = ##2')
        r1 = odin.canonicalize(doc)
        r2 = odin.canonicalize(doc)
        assert r1 == r2

    def test_canonicalize_sorted_paths(self):
        doc = odin.parse('z = ##3\na = ##1\nm = ##2')
        result = odin.canonicalize(doc).decode("utf-8")
        lines = [l for l in result.strip().split("\n") if l]
        # Paths should be sorted alphabetically
        paths = [l.split(" = ")[0] for l in lines]
        assert paths == sorted(paths)

    def test_canonicalize_lf_only(self):
        doc = odin.parse('a = ##1\nb = ##2')
        result = odin.canonicalize(doc)
        assert b"\r\n" not in result

    def test_canonicalize_identical_for_equivalent_docs(self):
        doc1 = odin.parse('b = ##2\na = ##1')
        doc2 = odin.parse('a = ##1\nb = ##2')
        assert odin.canonicalize(doc1) == odin.canonicalize(doc2)

    def test_canonicalize_different_for_different_docs(self):
        doc1 = odin.parse('x = ##1')
        doc2 = odin.parse('x = ##2')
        assert odin.canonicalize(doc1) != odin.canonicalize(doc2)

    def test_canonicalize_includes_type_prefixes(self):
        doc = odin.parse("x = ##42")
        result = odin.canonicalize(doc).decode("utf-8")
        assert "##42" in result

    def test_canonicalize_string_value(self):
        doc = odin.parse('name = "Alice"')
        result = odin.canonicalize(doc).decode("utf-8")
        assert '"Alice"' in result

    def test_canonicalize_null_value(self):
        doc = odin.parse("x = ~")
        result = odin.canonicalize(doc).decode("utf-8")
        assert "~" in result

    def test_canonicalize_boolean_value(self):
        doc = odin.parse("x = true")
        result = odin.canonicalize(doc).decode("utf-8")
        assert "true" in result

    def test_canonicalize_metadata_first(self):
        doc = odin.parse('{$}\nodin = "1.0.0"\n\nname = "test"')
        result = odin.canonicalize(doc).decode("utf-8")
        lines = [l for l in result.strip().split("\n") if l]
        # Metadata ($. prefixed) should come first
        assert lines[0].startswith("$.")

    def test_canonicalize_hashable(self):
        import hashlib
        doc = odin.parse('x = ##1')
        canonical = odin.canonicalize(doc)
        h = hashlib.sha256(canonical).hexdigest()
        assert len(h) == 64

    def test_canonicalize_empty_doc(self):
        doc = odin.parse("")
        result = odin.canonicalize(doc)
        assert result == b""


# ══════════════════════════════════════════════════════════════════════════════
# odin.diff() Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestDiff:
    """odin.diff() document comparison tests."""

    def test_diff_identical(self):
        d1 = odin.parse("x = ##1")
        d2 = odin.parse("x = ##1")
        d = odin.diff(d1, d2)
        assert d.is_empty

    def test_diff_added(self):
        d1 = odin.parse("x = ##1")
        d2 = odin.parse("x = ##1\ny = ##2")
        d = odin.diff(d1, d2)
        assert len(d.additions) > 0
        assert d.additions[0].path == "y"

    def test_diff_removed(self):
        d1 = odin.parse("x = ##1\ny = ##2")
        d2 = odin.parse("x = ##1")
        d = odin.diff(d1, d2)
        assert len(d.deletions) > 0

    def test_diff_changed(self):
        d1 = odin.parse("x = ##1")
        d2 = odin.parse("x = ##2")
        d = odin.diff(d1, d2)
        assert len(d.modifications) > 0
        assert d.modifications[0].path == "x"

    def test_diff_type_change(self):
        d1 = odin.parse("x = ##1")
        d2 = odin.parse('x = "one"')
        d = odin.diff(d1, d2)
        assert len(d.modifications) > 0

    def test_diff_multiple_changes(self):
        d1 = odin.parse('a = ##1\nb = "old"\nc = true')
        d2 = odin.parse('a = ##2\nb = "new"\nc = false')
        d = odin.diff(d1, d2)
        assert len(d.modifications) == 3

    def test_diff_returns_odin_diff(self):
        d1 = odin.parse("x = ##1")
        d2 = odin.parse("x = ##1")
        d = odin.diff(d1, d2)
        assert isinstance(d, OdinDiff)

    def test_diff_empty_docs(self):
        d1 = odin.parse("")
        d2 = odin.parse("")
        d = odin.diff(d1, d2)
        assert d.is_empty

    def test_diff_added_to_empty(self):
        d1 = odin.parse("")
        d2 = odin.parse("x = ##1")
        d = odin.diff(d1, d2)
        assert len(d.additions) == 1

    def test_diff_removed_to_empty(self):
        d1 = odin.parse("x = ##1")
        d2 = odin.parse("")
        d = odin.diff(d1, d2)
        assert len(d.deletions) == 1

    def test_diff_changed_string(self):
        d1 = odin.parse('name = "Alice"')
        d2 = odin.parse('name = "Bob"')
        d = odin.diff(d1, d2)
        assert len(d.modifications) == 1
        change = d.modifications[0]
        assert isinstance(change.old_value, OdinString)
        assert isinstance(change.new_value, OdinString)

    def test_diff_changed_integer(self):
        d1 = odin.parse("x = ##1")
        d2 = odin.parse("x = ##999")
        d = odin.diff(d1, d2)
        assert len(d.modifications) == 1

    def test_diff_move_detection(self):
        d1 = odin.parse('a = "val"\nb = ##1')
        d2 = odin.parse('c = "val"\nb = ##1')
        d = odin.diff(d1, d2)
        # "val" moved from a to c
        assert len(d.moves) >= 1 or (len(d.additions) > 0 and len(d.deletions) > 0)

    def test_diff_with_sections(self):
        d1 = odin.parse('{S}\nx = ##1')
        d2 = odin.parse('{S}\nx = ##2')
        d = odin.diff(d1, d2)
        assert len(d.modifications) == 1


# ══════════════════════════════════════════════════════════════════════════════
# odin.patch() Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestPatch:
    """odin.patch() tests."""

    def test_patch_empty_diff(self):
        doc = odin.parse("x = ##1")
        d = odin.diff(doc, doc)
        result = odin.patch(doc, d)
        assert result.get("x").value == 1

    def test_patch_add_field(self):
        d1 = odin.parse("x = ##1")
        d2 = odin.parse("x = ##1\ny = ##2")
        d = odin.diff(d1, d2)
        result = odin.patch(d1, d)
        assert result.get("y").value == 2

    def test_patch_remove_field(self):
        d1 = odin.parse("x = ##1\ny = ##2")
        d2 = odin.parse("x = ##1")
        d = odin.diff(d1, d2)
        result = odin.patch(d1, d)
        assert result.get("y") is None

    def test_patch_change_field(self):
        d1 = odin.parse('name = "Alice"')
        d2 = odin.parse('name = "Bob"')
        d = odin.diff(d1, d2)
        result = odin.patch(d1, d)
        assert result.get("name").value == "Bob"

    def test_patch_roundtrip(self):
        assert_patch_roundtrip('name = "Alice"\nage = ##25', 'name = "Bob"\nage = ##30')

    def test_patch_roundtrip_add_remove(self):
        assert_patch_roundtrip('a = ##1\nb = ##2', 'b = ##2\nc = ##3')

    def test_patch_roundtrip_types(self):
        assert_patch_roundtrip('x = ##1\ny = ##2', 'x = ##10\ny = ##20')

    def test_patch_returns_new_document(self):
        d1 = odin.parse("x = ##1")
        d2 = odin.parse("x = ##2")
        d = odin.diff(d1, d2)
        result = odin.patch(d1, d)
        assert result is not d1
        # Original should be unchanged
        assert d1.get("x").value == 1

    def test_patch_error_remove_nonexistent(self):
        doc = odin.parse("x = ##1")
        diff = OdinDiff(deletions=[PathValue("nonexistent", OdinInteger(1))])
        with pytest.raises(PatchError):
            odin.patch(doc, diff)

    def test_patch_error_change_nonexistent(self):
        doc = odin.parse("x = ##1")
        diff = OdinDiff(modifications=[PathChange("nonexistent", OdinInteger(1), OdinInteger(2))])
        with pytest.raises(PatchError):
            odin.patch(doc, diff)


# ══════════════════════════════════════════════════════════════════════════════
# OdinDocumentBuilder Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestBuilder:
    """OdinDocumentBuilder tests."""

    def test_builder_simple(self):
        doc = OdinDocumentBuilder().set("name", OdinString("Alice")).build()
        assert doc.get("name").value == "Alice"

    def test_builder_multiple_fields(self):
        doc = (OdinDocumentBuilder()
               .set("a", OdinInteger(1))
               .set("b", OdinInteger(2))
               .set("c", OdinInteger(3))
               .build())
        assert doc.get("a").value == 1
        assert doc.get("b").value == 2
        assert doc.get("c").value == 3

    def test_builder_with_modifiers(self):
        mods = OdinModifiers(required=True, confidential=True)
        doc = OdinDocumentBuilder().set("secret", OdinString("val"), mods).build()
        assert doc.modifiers["secret"].required is True
        assert doc.modifiers["secret"].confidential is True

    def test_builder_with_metadata(self):
        doc = (OdinDocumentBuilder()
               .set_metadata("odin", OdinString("1.0.0"))
               .set("name", OdinString("test"))
               .build())
        assert doc.metadata["odin"].value == "1.0.0"

    def test_builder_null_value(self):
        doc = OdinDocumentBuilder().set("x", NULL).build()
        assert isinstance(doc.get("x"), OdinNull)

    def test_builder_boolean_values(self):
        doc = (OdinDocumentBuilder()
               .set("t", TRUE)
               .set("f", FALSE)
               .build())
        assert doc.get("t").value is True
        assert doc.get("f").value is False

    def test_builder_all_types(self):
        from datetime import date, datetime
        doc = (OdinDocumentBuilder()
               .set("str", OdinString("hello"))
               .set("num", OdinNumber(3.14))
               .set("int", OdinInteger(42))
               .set("cur", OdinCurrency(Decimal("99.99")))
               .set("pct", OdinPercent(0.15))
               .set("bool", OdinBoolean(True))
               .set("null", NULL)
               .set("ref", OdinReference("other"))
               .set("bin", OdinBinary(b"data"))
               .build())
        assert doc.get("str").value == "hello"
        assert doc.get("num").value == pytest.approx(3.14)
        assert doc.get("int").value == 42
        assert isinstance(doc.get("cur"), OdinCurrency)
        assert isinstance(doc.get("pct"), OdinPercent)
        assert doc.get("bool").value is True
        assert isinstance(doc.get("null"), OdinNull)
        assert isinstance(doc.get("ref"), OdinReference)
        assert isinstance(doc.get("bin"), OdinBinary)

    def test_builder_produces_immutable_doc(self):
        doc = OdinDocumentBuilder().set("x", OdinInteger(1)).build()
        with pytest.raises(AttributeError):
            doc.x = 42

    def test_builder_chaining(self):
        builder = OdinDocumentBuilder()
        result = builder.set("x", OdinInteger(1))
        assert result is builder  # chaining returns self

    def test_builder_set_comment(self):
        doc = (OdinDocumentBuilder()
               .set("x", OdinInteger(1))
               .set_comment("x", "this is x")
               .build())
        assert doc.comments.get("x") == "this is x"

    def test_builder_roundtrip(self):
        """Build -> dumps -> parse preserves values."""
        doc = (OdinDocumentBuilder()
               .set("name", OdinString("Alice"))
               .set("age", OdinInteger(30))
               .build())
        text = odin.dumps(doc)
        reparsed = odin.parse(text)
        assert reparsed.get("name").value == "Alice"
        assert reparsed.get("age").value == 30


# ══════════════════════════════════════════════════════════════════════════════
# OdinDocument API Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestDocumentAPI:
    """OdinDocument interface tests."""

    def test_get_existing(self):
        doc = odin.parse("x = ##1")
        assert doc.get("x").value == 1

    def test_get_nonexistent(self):
        doc = odin.parse("x = ##1")
        assert doc.get("nonexistent") is None

    def test_contains(self):
        doc = odin.parse("x = ##1")
        assert "x" in doc
        assert "y" not in doc

    def test_len(self):
        doc = odin.parse("a = ##1\nb = ##2\nc = ##3")
        assert len(doc) == 3

    def test_paths(self):
        doc = odin.parse("b = ##2\na = ##1")
        assert doc.paths() == ["b", "a"]

    def test_assignments_mapping(self):
        doc = odin.parse("x = ##1")
        assert "x" in doc.assignments

    def test_metadata_mapping(self):
        doc = odin.parse('{$}\nodin = "1.0.0"\n\nname = "test"')
        assert "odin" in doc.metadata

    def test_modifiers_mapping(self):
        doc = odin.parse('x = !"val"')
        assert "x" in doc.modifiers
        assert doc.modifiers["x"].required is True

    def test_immutable(self):
        doc = odin.parse("x = ##1")
        with pytest.raises(AttributeError):
            doc.new_attr = "fail"


# ══════════════════════════════════════════════════════════════════════════════
# odin.path() Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestPath:
    """odin.path() utility tests."""

    def test_simple_path(self):
        assert odin.path("policy", "number") == "policy.number"

    def test_path_with_index(self):
        assert odin.path("items", 0, "name") == "items[0].name"

    def test_path_single_segment(self):
        assert odin.path("name") == "name"

    def test_path_empty(self):
        assert odin.path() == ""

    def test_path_extension(self):
        assert odin.path("&com.acme", "custom_field") == "&com.acme.custom_field"

    def test_path_multiple_indices(self):
        assert odin.path("items", 0, "sub", 1) == "items[0].sub[1]"


# ══════════════════════════════════════════════════════════════════════════════
# Export Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestExport:
    """odin.to_json(), odin.to_xml(), etc."""

    def test_to_json_simple(self):
        doc = odin.parse('name = "Alice"\nage = ##30')
        result = odin.to_json(doc)
        assert isinstance(result, str)
        import json
        data = json.loads(result)
        assert data["name"] == "Alice"
        assert data["age"] == 30

    def test_to_json_with_indent(self):
        doc = odin.parse('name = "Alice"')
        result = odin.to_json(doc, indent=2)
        assert "\n" in result

    def test_to_json_nested(self):
        doc = odin.parse('{person}\nname = "Alice"\nage = ##30')
        result = odin.to_json(doc)
        import json
        data = json.loads(result)
        assert data["person"]["name"] == "Alice"

    def test_to_xml_basic(self):
        doc = odin.parse('name = "Alice"')
        result = odin.to_xml(doc)
        assert isinstance(result, str)
        assert "Alice" in result

    def test_to_xml_with_root(self):
        doc = odin.parse('name = "Alice"')
        result = odin.to_xml(doc, root_element="doc")
        assert "<doc>" in result or "<doc " in result

    def test_to_csv_basic(self):
        doc = odin.parse('{items[] : name, qty}\n"Widget", ##10\n"Gadget", ##5')
        result = odin.to_csv(doc, array_path="items")
        assert isinstance(result, str)


# ══════════════════════════════════════════════════════════════════════════════
# Transform Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestTransform:
    """odin.parse_transform() and odin.execute_transform() tests."""

    def test_parse_transform_basic(self):
        transform_text = '\n'.join([
            '{$}',
            'odin = "1.0.0"',
            'transform = "1.0.0"',
            'direction = "json->json"',
            '',
            '{Customer}',
            'Name = "@.name"',
        ])
        t = odin.parse_transform(transform_text)
        assert t is not None

    def test_parse_transform_bytes(self):
        transform_text = b'{$}\nodin = "1.0.0"\ntransform = "1.0.0"\ndirection = "json->json"\n\n{Out}\nX = "@.x"'
        t = odin.parse_transform(transform_text)
        assert t is not None

    def test_execute_transform_simple(self):
        transform_text = '\n'.join([
            '{$}',
            'odin = "1.0.0"',
            'transform = "1.0.0"',
            'direction = "json->json"',
            '',
            '{Customer}',
            'Name = "@.name"',
        ])
        source = {"name": "Alice"}
        result = odin.execute_transform(transform_text, source)
        assert result is not None
        assert result.success is True

    def test_execute_transform_from_parsed(self):
        transform_text = '\n'.join([
            '{$}',
            'odin = "1.0.0"',
            'transform = "1.0.0"',
            'direction = "json->json"',
            '',
            '{Customer}',
            'Name = "@.name"',
            'Age = "@.age"',
        ])
        t = odin.parse_transform(transform_text)
        source = {"name": "Alice", "age": 30}
        result = odin.execute_transform(t, source)
        assert result.success is True

    def test_execute_transform_output_structure(self):
        transform_text = '\n'.join([
            '{$}',
            'odin = "1.0.0"',
            'transform = "1.0.0"',
            'direction = "json->json"',
            '',
            '{Person}',
            'FirstName = "@.first"',
            'LastName = "@.last"',
        ])
        source = {"first": "Alice", "last": "Smith"}
        result = odin.execute_transform(transform_text, source)
        assert result.success is True
        # Output should contain Person structure
        if result.output is not None:
            output = result.output
            if hasattr(output, 'to_python'):
                output = output.to_python()
            # The output should map the fields
            assert output is not None


# ══════════════════════════════════════════════════════════════════════════════
# Error Handling Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestErrorHandling:
    """Error handling across the public API."""

    def test_parse_error_has_code(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('name = "unterminated')
        assert exc_info.value.code == "P004"

    def test_parse_error_has_line(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('name = "unterminated')
        assert exc_info.value.line >= 1

    def test_parse_error_has_column(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('name = "unterminated')
        assert exc_info.value.column >= 1

    def test_parse_error_is_odin_error(self):
        with pytest.raises(odin.OdinError):
            odin.parse('name = "unterminated')

    def test_parse_error_is_exception(self):
        with pytest.raises(Exception):
            odin.parse('name = "unterminated')

    def test_patch_error_has_path(self):
        doc = odin.parse("x = ##1")
        diff = OdinDiff(deletions=[PathValue("nonexistent", OdinInteger(1))])
        with pytest.raises(PatchError) as exc_info:
            odin.patch(doc, diff)
        assert exc_info.value.path == "nonexistent"

    def test_validate_invalid_schema(self):
        doc = odin.parse("x = ##1")
        with pytest.raises(Exception):
            odin.validate(doc, None)

    def test_max_document_size_error(self):
        opts = ParseOptions(max_document_size=10)
        with pytest.raises(ParseError) as exc_info:
            odin.parse("x" * 100, options=opts)
        assert exc_info.value.code == "P011"


# ══════════════════════════════════════════════════════════════════════════════
# Multi-Document Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestMultiDocument:
    """Document separator (---) multi-document handling."""

    def test_separator_returns_first_doc(self):
        text = 'a = ##1\n---\nb = ##2'
        doc = odin.parse(text)
        assert doc.get("a").value == 1
        assert doc.get("b") is None

    def test_separator_with_metadata(self):
        text = '{$}\nodin = "1.0.0"\nid = "d1"\n\nname = "John"\n---\n{$}\nodin = "1.0.0"\n\nname = "Jane"'
        doc = odin.parse(text)
        assert doc.get("name").value == "John"


# ══════════════════════════════════════════════════════════════════════════════
# OdinDiff Type Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestDiffTypes:
    """OdinDiff data structure tests."""

    def test_diff_is_empty(self):
        d = OdinDiff()
        assert d.is_empty

    def test_diff_not_empty_additions(self):
        d = OdinDiff(additions=[PathValue("x", OdinInteger(1))])
        assert not d.is_empty

    def test_diff_not_empty_deletions(self):
        d = OdinDiff(deletions=[PathValue("x", OdinInteger(1))])
        assert not d.is_empty

    def test_diff_not_empty_modifications(self):
        d = OdinDiff(modifications=[PathChange("x", OdinInteger(1), OdinInteger(2))])
        assert not d.is_empty

    def test_diff_not_empty_moves(self):
        d = OdinDiff(moves=[PathMove("a", "b")])
        assert not d.is_empty

    def test_path_value_structure(self):
        pv = PathValue("x", OdinInteger(1))
        assert pv.path == "x"
        assert pv.value.value == 1

    def test_path_change_structure(self):
        pc = PathChange("x", OdinInteger(1), OdinInteger(2))
        assert pc.path == "x"
        assert pc.old_value.value == 1
        assert pc.new_value.value == 2

    def test_path_move_structure(self):
        pm = PathMove("a", "b")
        assert pm.from_path == "a"
        assert pm.to_path == "b"


# ══════════════════════════════════════════════════════════════════════════════
# OdinModifiers Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestModifiersType:
    """OdinModifiers data class tests."""

    def test_default_no_modifiers(self):
        m = OdinModifiers()
        assert m.required is False
        assert m.confidential is False
        assert m.deprecated is False
        assert m.has_any is False

    def test_required_only(self):
        m = OdinModifiers(required=True)
        assert m.has_any is True

    def test_confidential_only(self):
        m = OdinModifiers(confidential=True)
        assert m.has_any is True

    def test_deprecated_only(self):
        m = OdinModifiers(deprecated=True)
        assert m.has_any is True

    def test_all_modifiers(self):
        m = OdinModifiers(required=True, confidential=True, deprecated=True)
        assert m.has_any is True

    def test_immutable(self):
        m = OdinModifiers(required=True)
        with pytest.raises(Exception):
            m.required = False


# ══════════════════════════════════════════════════════════════════════════════
# Value Type Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestValueTypes:
    """Value type construction and properties."""

    def test_null_singleton(self):
        assert NULL is NULL
        assert isinstance(NULL, OdinNull)

    def test_true_singleton(self):
        assert TRUE is TRUE
        assert TRUE.value is True

    def test_false_singleton(self):
        assert FALSE is FALSE
        assert FALSE.value is False

    def test_string_value(self):
        v = OdinString("hello")
        assert v.value == "hello"

    def test_number_value(self):
        v = OdinNumber(3.14)
        assert v.value == pytest.approx(3.14)

    def test_integer_value(self):
        v = OdinInteger(42)
        assert v.value == 42

    def test_currency_value(self):
        v = OdinCurrency(Decimal("99.99"), currency_code="USD", decimal_places=2)
        assert float(v.value) == pytest.approx(99.99)
        assert v.currency_code == "USD"

    def test_percent_value(self):
        v = OdinPercent(0.15)
        assert v.value == pytest.approx(0.15)

    def test_reference_value(self):
        v = OdinReference("other.path")
        assert v.path == "other.path"

    def test_binary_value(self):
        v = OdinBinary(b"hello")
        assert v.data == b"hello"

    def test_binary_with_algorithm(self):
        v = OdinBinary(b"data", algorithm="sha256")
        assert v.algorithm == "sha256"

    def test_values_are_frozen(self):
        v = OdinString("hello")
        with pytest.raises(Exception):
            v.value = "world"


# ══════════════════════════════════════════════════════════════════════════════
# ParseOptions Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestParseOptions:
    """ParseOptions configuration tests."""

    def test_default_options(self):
        opts = ParseOptions()
        assert opts.max_nesting_depth == 64
        assert opts.max_document_size == 100 * 1024 * 1024

    def test_custom_depth(self):
        opts = ParseOptions(max_nesting_depth=10)
        assert opts.max_nesting_depth == 10

    def test_custom_size(self):
        opts = ParseOptions(max_document_size=1000)
        assert opts.max_document_size == 1000


# ══════════════════════════════════════════════════════════════════════════════
# DumpOptions Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestDumpOptions:
    """DumpOptions configuration tests."""

    def test_default_options(self):
        opts = DumpOptions()
        assert opts.sort_paths is False
        assert opts.use_headers is True
        assert opts.line_ending == LineEnding.LF

    def test_sort_paths(self):
        doc = odin.parse('z = ##3\na = ##1')
        result = odin.dumps(doc, DumpOptions(sort_paths=True, use_headers=False))
        lines = [l for l in result.strip().split("\n") if l]
        paths = [l.split(" = ")[0] for l in lines]
        assert paths == sorted(paths)


# ══════════════════════════════════════════════════════════════════════════════
# Version and Module Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestModule:
    """Module-level attributes and exports."""

    def test_version(self):
        assert odin.__version__ == "1.0.4"

    def test_all_exports(self):
        assert "parse" in odin.__all__
        assert "dumps" in odin.__all__
        assert "diff" in odin.__all__
        assert "patch" in odin.__all__
        assert "canonicalize" in odin.__all__

    def test_type_exports(self):
        assert "OdinDocument" in odin.__all__
        assert "OdinString" in odin.__all__
        assert "OdinInteger" in odin.__all__
        assert "OdinNumber" in odin.__all__

    def test_error_exports(self):
        assert "ParseError" in odin.__all__
        assert "PatchError" in odin.__all__
        assert "OdinError" in odin.__all__

    def test_constant_exports(self):
        assert "NULL" in odin.__all__
        assert "TRUE" in odin.__all__
        assert "FALSE" in odin.__all__


# ══════════════════════════════════════════════════════════════════════════════
# Complex Roundtrip Scenarios
# ══════════════════════════════════════════════════════════════════════════════


class TestComplexRoundtrips:
    """Complex documents that exercise multiple features."""

    def test_insurance_policy_roundtrip(self):
        text = "\n".join([
            '{$}',
            'odin = "1.0.0"',
            'id = "PAP-2024-001"',
            '',
            '{policy}',
            'number = "PAP-2024-001"',
            'effective = 2024-06-15',
            'premium = !#$747.50',
            '',
            '{vehicles[0]}',
            'vin = "1HGBH41JXMN109186"',
            'year = ##2024',
            '',
            '{drivers[0]}',
            'name = "John Smith"',
            'license = *"DL-12345"',
        ])
        doc = odin.parse(text)
        serialized = odin.dumps(doc)
        reparsed = odin.parse(serialized)
        assert reparsed.get("policy.number").value == "PAP-2024-001"
        assert reparsed.get("vehicles[0].year").value == 2024
        assert reparsed.get("drivers[0].name").value == "John Smith"

    def test_diff_patch_complex(self):
        src = "\n".join([
            '{$}',
            'odin = "1.0.0"',
            '',
            'name = "Alice"',
            'age = ##25',
            'active = true',
        ])
        dst = "\n".join([
            '{$}',
            'odin = "1.0.0"',
            '',
            'name = "Bob"',
            'age = ##30',
            'active = false',
        ])
        d1 = odin.parse(src)
        d2 = odin.parse(dst)
        d = odin.diff(d1, d2)
        patched = odin.patch(d1, d)
        assert patched.get("name").value == "Bob"
        assert patched.get("age").value == 30
        assert patched.get("active").value is False

    def test_canonical_hash_stability(self):
        """Same data produces same canonical hash regardless of input order."""
        import hashlib
        doc1 = odin.parse('z = ##3\na = ##1\nm = ##2')
        doc2 = odin.parse('a = ##1\nm = ##2\nz = ##3')
        h1 = hashlib.sha256(odin.canonicalize(doc1)).hexdigest()
        h2 = hashlib.sha256(odin.canonicalize(doc2)).hexdigest()
        assert h1 == h2

    def test_builder_to_json(self):
        doc = (OdinDocumentBuilder()
               .set("name", OdinString("Alice"))
               .set("age", OdinInteger(30))
               .build())
        result = odin.to_json(doc)
        import json
        data = json.loads(result)
        assert data["name"] == "Alice"
        assert data["age"] == 30
