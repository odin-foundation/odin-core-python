"""Tests for ODIN foundation types."""
from __future__ import annotations

import pytest
import sys
from decimal import Decimal
from datetime import date, datetime
from dataclasses import FrozenInstanceError

from odin.types.values import (
    OdinNull, OdinBoolean, OdinString, OdinNumber, OdinInteger,
    OdinCurrency, OdinPercent, OdinDate, OdinTimestamp, OdinTime,
    OdinDuration, OdinReference, OdinBinary, OdinVerbExpression,
    OdinArray, OdinObject, NULL, TRUE, FALSE,
)
from odin.types.document import OdinDocument, OdinDocumentBuilder, OdinModifiers
from odin.types.errors import (
    OdinError, ParseError, PatchError,
    ParseErrorCodes, ValidationErrorCodes,
)


# ─────────────────────────────────────────────────────────────────────────────
# OdinNull
# ─────────────────────────────────────────────────────────────────────────────

class TestOdinNull:
    def test_construction(self):
        n = OdinNull()
        assert n is not None

    def test_singleton(self):
        assert NULL == OdinNull()

    def test_frozen(self):
        with pytest.raises((AttributeError, TypeError)):
            NULL.x = 1  # type: ignore

    def test_equality(self):
        assert OdinNull() == OdinNull()

    def test_hash(self):
        assert hash(OdinNull()) == hash(OdinNull())


# ─────────────────────────────────────────────────────────────────────────────
# OdinBoolean
# ─────────────────────────────────────────────────────────────────────────────

class TestOdinBoolean:
    def test_true(self):
        assert TRUE.value is True

    def test_false(self):
        assert FALSE.value is False

    def test_construction(self):
        b = OdinBoolean(True)
        assert b.value is True

    def test_frozen(self):
        with pytest.raises((AttributeError, TypeError, FrozenInstanceError)):
            TRUE.value = False  # type: ignore

    def test_equality(self):
        assert OdinBoolean(True) == OdinBoolean(True)
        assert OdinBoolean(True) != OdinBoolean(False)

    def test_singletons_equal(self):
        assert TRUE == OdinBoolean(True)
        assert FALSE == OdinBoolean(False)


# ─────────────────────────────────────────────────────────────────────────────
# OdinString
# ─────────────────────────────────────────────────────────────────────────────

class TestOdinString:
    def test_construction(self):
        s = OdinString("hello")
        assert s.value == "hello"

    def test_empty_string(self):
        s = OdinString("")
        assert s.value == ""

    def test_frozen(self):
        s = OdinString("test")
        with pytest.raises((AttributeError, TypeError, FrozenInstanceError)):
            s.value = "other"  # type: ignore

    def test_equality(self):
        assert OdinString("a") == OdinString("a")
        assert OdinString("a") != OdinString("b")

    def test_unicode(self):
        s = OdinString("日本語")
        assert s.value == "日本語"


# ─────────────────────────────────────────────────────────────────────────────
# OdinNumber
# ─────────────────────────────────────────────────────────────────────────────

class TestOdinNumber:
    def test_construction(self):
        n = OdinNumber(3.14)
        assert n.value == 3.14

    def test_with_raw(self):
        n = OdinNumber(3.14, raw="3.14")
        assert n.raw == "3.14"

    def test_zero(self):
        n = OdinNumber(0.0)
        assert n.value == 0.0

    def test_negative(self):
        n = OdinNumber(-1.5)
        assert n.value == -1.5

    def test_frozen(self):
        n = OdinNumber(1.0)
        with pytest.raises((AttributeError, TypeError, FrozenInstanceError)):
            n.value = 2.0  # type: ignore

    def test_value_is_float(self):
        n = OdinNumber(42.0)
        assert isinstance(n.value, float)


# ─────────────────────────────────────────────────────────────────────────────
# OdinInteger
# ─────────────────────────────────────────────────────────────────────────────

class TestOdinInteger:
    def test_construction(self):
        i = OdinInteger(42)
        assert i.value == 42

    def test_zero(self):
        i = OdinInteger(0)
        assert i.value == 0

    def test_negative(self):
        i = OdinInteger(-10)
        assert i.value == -10

    def test_with_raw(self):
        i = OdinInteger(42, raw="42")
        assert i.raw == "42"

    def test_frozen(self):
        i = OdinInteger(1)
        with pytest.raises((AttributeError, TypeError, FrozenInstanceError)):
            i.value = 2  # type: ignore

    def test_value_is_int(self):
        i = OdinInteger(42)
        assert isinstance(i.value, int)

    def test_large_value(self):
        i = OdinInteger(10**20)
        assert i.value == 10**20


# ─────────────────────────────────────────────────────────────────────────────
# OdinCurrency
# ─────────────────────────────────────────────────────────────────────────────

class TestOdinCurrency:
    def test_construction(self):
        c = OdinCurrency(Decimal("99.99"))
        assert c.value == Decimal("99.99")

    def test_decimal_places(self):
        c = OdinCurrency(Decimal("100.00"), decimal_places=2)
        assert c.decimal_places == 2

    def test_currency_code(self):
        c = OdinCurrency(Decimal("100.00"), currency_code="USD")
        assert c.currency_code == "USD"

    def test_with_raw(self):
        c = OdinCurrency(Decimal("99.99"), raw="99.99")
        assert c.raw == "99.99"

    def test_frozen(self):
        c = OdinCurrency(Decimal("1.00"))
        with pytest.raises((AttributeError, TypeError, FrozenInstanceError)):
            c.value = Decimal("2.00")  # type: ignore

    def test_value_is_decimal(self):
        c = OdinCurrency(Decimal("42.50"))
        assert isinstance(c.value, Decimal)


# ─────────────────────────────────────────────────────────────────────────────
# OdinPercent
# ─────────────────────────────────────────────────────────────────────────────

class TestOdinPercent:
    def test_construction(self):
        p = OdinPercent(0.5)
        assert p.value == 0.5

    def test_with_raw(self):
        p = OdinPercent(0.5, raw="50%")
        assert p.raw == "50%"

    def test_frozen(self):
        p = OdinPercent(0.1)
        with pytest.raises((AttributeError, TypeError, FrozenInstanceError)):
            p.value = 0.2  # type: ignore


# ─────────────────────────────────────────────────────────────────────────────
# OdinDate
# ─────────────────────────────────────────────────────────────────────────────

class TestOdinDate:
    def test_construction(self):
        d = OdinDate(date(2024, 1, 15), raw="2024-01-15")
        assert d.value == date(2024, 1, 15)
        assert d.raw == "2024-01-15"

    def test_frozen(self):
        d = OdinDate(date(2024, 1, 1), raw="2024-01-01")
        with pytest.raises((AttributeError, TypeError, FrozenInstanceError)):
            d.raw = "other"  # type: ignore


# ─────────────────────────────────────────────────────────────────────────────
# OdinTimestamp
# ─────────────────────────────────────────────────────────────────────────────

class TestOdinTimestamp:
    def test_construction(self):
        ts = OdinTimestamp(datetime(2024, 1, 15, 10, 30), raw="2024-01-15T10:30:00Z")
        assert ts.value == datetime(2024, 1, 15, 10, 30)
        assert ts.raw == "2024-01-15T10:30:00Z"

    def test_frozen(self):
        ts = OdinTimestamp(datetime(2024, 1, 1), raw="2024-01-01T00:00:00Z")
        with pytest.raises((AttributeError, TypeError, FrozenInstanceError)):
            ts.raw = "other"  # type: ignore


# ─────────────────────────────────────────────────────────────────────────────
# OdinTime
# ─────────────────────────────────────────────────────────────────────────────

class TestOdinTime:
    def test_construction(self):
        t = OdinTime("10:30:00")
        assert t.value == "10:30:00"

    def test_string_value(self):
        t = OdinTime("T14:30:00")
        assert isinstance(t.value, str)

    def test_frozen(self):
        t = OdinTime("10:00")
        with pytest.raises((AttributeError, TypeError, FrozenInstanceError)):
            t.value = "11:00"  # type: ignore


# ─────────────────────────────────────────────────────────────────────────────
# OdinDuration
# ─────────────────────────────────────────────────────────────────────────────

class TestOdinDuration:
    def test_construction(self):
        d = OdinDuration("P1Y2M3D")
        assert d.value == "P1Y2M3D"

    def test_string_value(self):
        d = OdinDuration("PT1H30M")
        assert isinstance(d.value, str)

    def test_frozen(self):
        d = OdinDuration("P1D")
        with pytest.raises((AttributeError, TypeError, FrozenInstanceError)):
            d.value = "P2D"  # type: ignore


# ─────────────────────────────────────────────────────────────────────────────
# OdinReference
# ─────────────────────────────────────────────────────────────────────────────

class TestOdinReference:
    def test_construction(self):
        r = OdinReference("parties[0].name")
        assert r.path == "parties[0].name"

    def test_frozen(self):
        r = OdinReference("x")
        with pytest.raises((AttributeError, TypeError, FrozenInstanceError)):
            r.path = "y"  # type: ignore


# ─────────────────────────────────────────────────────────────────────────────
# OdinBinary
# ─────────────────────────────────────────────────────────────────────────────

class TestOdinBinary:
    def test_construction(self):
        b = OdinBinary(b"hello")
        assert b.data == b"hello"

    def test_algorithm(self):
        b = OdinBinary(b"data", algorithm="sha256")
        assert b.algorithm == "sha256"

    def test_no_algorithm(self):
        b = OdinBinary(b"data")
        assert b.algorithm is None

    def test_frozen(self):
        b = OdinBinary(b"data")
        with pytest.raises((AttributeError, TypeError, FrozenInstanceError)):
            b.data = b"other"  # type: ignore


# ─────────────────────────────────────────────────────────────────────────────
# OdinVerbExpression
# ─────────────────────────────────────────────────────────────────────────────

class TestOdinVerbExpression:
    def test_construction(self):
        v = OdinVerbExpression("upper", args=(OdinString("hello"),))
        assert v.verb == "upper"
        assert len(v.args) == 1

    def test_custom_verb(self):
        v = OdinVerbExpression("myVerb", is_custom=True, args=())
        assert v.is_custom is True

    def test_not_custom_default(self):
        v = OdinVerbExpression("lower", args=())
        assert v.is_custom is False

    def test_frozen(self):
        v = OdinVerbExpression("upper", args=())
        with pytest.raises((AttributeError, TypeError, FrozenInstanceError)):
            v.verb = "lower"  # type: ignore


# ─────────────────────────────────────────────────────────────────────────────
# OdinArray / OdinObject (marker types)
# ─────────────────────────────────────────────────────────────────────────────

class TestOdinArray:
    def test_construction(self):
        a = OdinArray()
        assert a is not None

    def test_frozen(self):
        a = OdinArray()
        with pytest.raises((AttributeError, TypeError, FrozenInstanceError)):
            a.x = 1  # type: ignore


class TestOdinObject:
    def test_construction(self):
        o = OdinObject()
        assert o is not None

    def test_frozen(self):
        o = OdinObject()
        with pytest.raises((AttributeError, TypeError, FrozenInstanceError)):
            o.x = 1  # type: ignore


# ─────────────────────────────────────────────────────────────────────────────
# OdinModifiers
# ─────────────────────────────────────────────────────────────────────────────

class TestOdinModifiers:
    def test_default(self):
        m = OdinModifiers()
        assert m.required is False
        assert m.confidential is False
        assert m.deprecated is False
        assert m.attr is None

    def test_required(self):
        m = OdinModifiers(required=True)
        assert m.required is True

    def test_confidential(self):
        m = OdinModifiers(confidential=True)
        assert m.confidential is True

    def test_deprecated(self):
        m = OdinModifiers(deprecated=True)
        assert m.deprecated is True

    def test_attr(self):
        m = OdinModifiers(attr="xml:lang")
        assert m.attr == "xml:lang"

    def test_combined(self):
        m = OdinModifiers(required=True, confidential=True, deprecated=True)
        assert m.required is True
        assert m.confidential is True
        assert m.deprecated is True

    def test_frozen(self):
        m = OdinModifiers()
        with pytest.raises((AttributeError, TypeError, FrozenInstanceError)):
            m.required = True  # type: ignore

    def test_equality(self):
        assert OdinModifiers() == OdinModifiers()
        assert OdinModifiers(required=True) == OdinModifiers(required=True)
        assert OdinModifiers(required=True) != OdinModifiers(required=False)

    def test_has_any_true(self):
        assert OdinModifiers().has_any is False
        assert OdinModifiers(required=True).has_any is True
        assert OdinModifiers(confidential=True).has_any is True
        assert OdinModifiers(deprecated=True).has_any is True


# ─────────────────────────────────────────────────────────────────────────────
# OdinDocument
# ─────────────────────────────────────────────────────────────────────────────

class TestOdinDocument:
    def test_empty_document(self):
        doc = OdinDocumentBuilder().build()
        assert len(doc) == 0
        assert list(doc.paths()) == []

    def test_get_existing(self, simple_doc):
        val = simple_doc.get("name")
        assert isinstance(val, OdinString)
        assert val.value == "Alice"

    def test_get_missing(self, simple_doc):
        assert simple_doc.get("missing") is None

    def test_contains(self, simple_doc):
        assert "name" in simple_doc
        assert "missing" not in simple_doc

    def test_len(self, simple_doc):
        assert len(simple_doc) == 3

    def test_paths(self, simple_doc):
        paths = list(simple_doc.paths())
        assert "name" in paths
        assert "age" in paths
        assert "active" in paths

    def test_paths_preserve_order(self):
        builder = OdinDocumentBuilder()
        builder.set("z", OdinString("last"))
        builder.set("a", OdinString("first"))
        builder.set("m", OdinString("mid"))
        doc = builder.build()
        paths = list(doc.paths())
        assert paths == ["z", "a", "m"]

    def test_assignments_property(self, simple_doc):
        assignments = simple_doc.assignments
        assert "name" in assignments
        assert isinstance(assignments["name"], OdinString)

    def test_metadata(self):
        doc = (
            OdinDocumentBuilder()
            .set_metadata("odin", OdinString("1.0.0"))
            .set_metadata("id", OdinString("doc_123"))
            .set("name", OdinString("test"))
            .build()
        )
        assert "odin" in doc.metadata
        assert doc.metadata["odin"] == OdinString("1.0.0")
        assert doc.metadata["id"] == OdinString("doc_123")

    def test_modifiers(self):
        mods = OdinModifiers(required=True)
        doc = (
            OdinDocumentBuilder()
            .set("name", OdinString("Alice"), modifiers=mods)
            .build()
        )
        assert doc.modifiers["name"] == mods

    def test_comments(self):
        doc = (
            OdinDocumentBuilder()
            .set("name", OdinString("Alice"))
            .set_comment("name", "The person's name")
            .build()
        )
        assert doc.comments["name"] == "The person's name"

    def test_document_is_immutable(self, simple_doc):
        # assignments should return a read-only mapping
        assignments = simple_doc.assignments
        with pytest.raises(TypeError):
            assignments["new_key"] = OdinString("nope")  # type: ignore


# ─────────────────────────────────────────────────────────────────────────────
# OdinDocumentBuilder
# ─────────────────────────────────────────────────────────────────────────────

class TestOdinDocumentBuilder:
    def test_set_returns_self(self, builder):
        result = builder.set("x", OdinString("y"))
        assert result is builder

    def test_set_metadata_returns_self(self, builder):
        result = builder.set_metadata("k", OdinString("v"))
        assert result is builder

    def test_build_produces_document(self, builder):
        doc = builder.set("x", OdinString("y")).build()
        assert isinstance(doc, OdinDocument)

    def test_overwrite_path(self, builder):
        doc = (
            builder
            .set("x", OdinString("first"))
            .set("x", OdinString("second"))
            .build()
        )
        assert doc.get("x") == OdinString("second")

    def test_multiple_paths(self, builder):
        doc = (
            builder
            .set("a.b", OdinString("nested"))
            .set("c", OdinInteger(42))
            .build()
        )
        assert doc.get("a.b") == OdinString("nested")
        assert doc.get("c") == OdinInteger(42)

    def test_set_with_modifiers(self, builder):
        mods = OdinModifiers(confidential=True)
        doc = builder.set("ssn", OdinString("123-45-6789"), modifiers=mods).build()
        assert doc.get("ssn") == OdinString("123-45-6789")
        assert doc.modifiers["ssn"] == mods

    def test_set_comment(self, builder):
        doc = (
            builder
            .set("x", OdinString("y"))
            .set_comment("x", "A comment")
            .build()
        )
        assert doc.comments["x"] == "A comment"

    def test_builder_can_build_multiple_times(self, builder):
        builder.set("x", OdinString("y"))
        doc1 = builder.build()
        doc2 = builder.build()
        assert doc1.get("x") == doc2.get("x")
        # But they should be independent
        assert doc1 is not doc2


# ─────────────────────────────────────────────────────────────────────────────
# Error Types
# ─────────────────────────────────────────────────────────────────────────────

class TestErrors:
    def test_odin_error(self):
        err = OdinError("test", "E001")
        assert str(err) == "test"
        assert err.code == "E001"

    def test_parse_error(self):
        err = ParseError("Unexpected char", "P001", line=1, column=5)
        assert err.code == "P001"
        assert err.line == 1
        assert err.column == 5
        assert "line 1" in str(err)
        assert "column 5" in str(err)

    def test_patch_error(self):
        err = PatchError("Not found", "a.b.c")
        assert err.path == "a.b.c"

    def test_parse_error_is_odin_error(self):
        err = ParseError("test", "P001", 1, 1)
        assert isinstance(err, OdinError)

    def test_patch_error_is_odin_error(self):
        err = PatchError("test", "x")
        assert isinstance(err, OdinError)


# ─────────────────────────────────────────────────────────────────────────────
# Error Codes
# ─────────────────────────────────────────────────────────────────────────────

class TestErrorCodes:
    def test_parse_error_codes_exist(self):
        assert ParseErrorCodes.P001 == "P001"
        assert ParseErrorCodes.P002 == "P002"
        assert ParseErrorCodes.P003 == "P003"
        assert ParseErrorCodes.P004 == "P004"
        assert ParseErrorCodes.P005 == "P005"
        assert ParseErrorCodes.P006 == "P006"
        assert ParseErrorCodes.P007 == "P007"
        assert ParseErrorCodes.P008 == "P008"
        assert ParseErrorCodes.P009 == "P009"
        assert ParseErrorCodes.P010 == "P010"
        assert ParseErrorCodes.P011 == "P011"
        assert ParseErrorCodes.P012 == "P012"
        assert ParseErrorCodes.P013 == "P013"
        assert ParseErrorCodes.P014 == "P014"
        assert ParseErrorCodes.P015 == "P015"

    def test_validation_error_codes_exist(self):
        assert ValidationErrorCodes.V001 == "V001"
        assert ValidationErrorCodes.V002 == "V002"
        assert ValidationErrorCodes.V003 == "V003"
        assert ValidationErrorCodes.V004 == "V004"
        assert ValidationErrorCodes.V005 == "V005"
        assert ValidationErrorCodes.V006 == "V006"
        assert ValidationErrorCodes.V007 == "V007"
        assert ValidationErrorCodes.V008 == "V008"
        assert ValidationErrorCodes.V009 == "V009"
        assert ValidationErrorCodes.V010 == "V010"
        assert ValidationErrorCodes.V011 == "V011"
        assert ValidationErrorCodes.V012 == "V012"
        assert ValidationErrorCodes.V013 == "V013"


# ─────────────────────────────────────────────────────────────────────────────
# path() utility
# ─────────────────────────────────────────────────────────────────────────────

class TestPathUtility:
    def test_empty(self):
        import odin
        assert odin.path() == ""

    def test_single_segment(self):
        import odin
        assert odin.path("policy") == "policy"

    def test_dot_separated(self):
        import odin
        assert odin.path("policy", "number") == "policy.number"

    def test_array_index(self):
        import odin
        assert odin.path("vehicles", 0) == "vehicles[0]"

    def test_complex_path(self):
        import odin
        assert odin.path("policy", "vehicles", 0, "vin") == "policy.vehicles[0].vin"

    def test_extension_prefix(self):
        import odin
        assert odin.path("&com.acme", "custom_field") == "&com.acme.custom_field"


# ─────────────────────────────────────────────────────────────────────────────
# Module-level imports
# ─────────────────────────────────────────────────────────────────────────────

class TestModuleImports:
    def test_import_odin(self):
        import odin
        assert hasattr(odin, "__version__")
        assert odin.__version__ == "1.0.0"

    def test_value_types_importable(self):
        from odin import (
            OdinNull, OdinBoolean, OdinString, OdinNumber, OdinInteger,
            OdinCurrency, OdinPercent, OdinDate, OdinTimestamp, OdinTime,
            OdinDuration, OdinReference, OdinBinary, OdinVerbExpression,
            OdinArray, OdinObject,
        )

    def test_document_types_importable(self):
        from odin import OdinDocument, OdinDocumentBuilder

    def test_error_types_importable(self):
        from odin import OdinError, ParseError, PatchError

    def test_singletons_importable(self):
        from odin.types.values import NULL, TRUE, FALSE
        assert NULL == OdinNull()
        assert TRUE.value is True
        assert FALSE.value is False
