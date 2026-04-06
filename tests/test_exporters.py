"""Tests for format exporters - JSON, XML, CSV, Fixed-Width."""

import json
import pytest
import odin
from odin.types.document import OdinDocument, OdinDocumentBuilder, OdinModifiers
from odin.types.values import (
    OdinNull, OdinBoolean, OdinString, OdinNumber, OdinInteger,
    OdinCurrency, OdinPercent, OdinDate, OdinTimestamp, OdinTime,
    OdinDuration, OdinReference, OdinBinary, NULL, TRUE, FALSE,
)
from odin.export.json_export import to_json
from odin.export.xml_export import to_xml
from odin.export.csv_export import to_csv
from odin.export.fixed_width_export import to_fixed_width
from odin.transform.dyn_value import DynValue
from odin.transform.formatters.json_formatter import format_json
from odin.transform.formatters.csv_formatter import format_csv
from odin.transform.formatters.xml_formatter import format_xml
from odin.transform.formatters.odin_formatter import format_odin
from odin.transform.formatters.fixed_width_formatter import format_fixed_width
from odin.transform.formatters.flat_formatter import format_flat
from datetime import date, datetime
from decimal import Decimal


def _build_doc(**kwargs):
    b = OdinDocumentBuilder()
    for path, value in kwargs.items():
        b.set(path.replace("__", ".").replace("_IX_", "[").replace("_XE_", "]"), value)
    return b.build()


# ─────────────────────────────────────────────────────────────────────────────
# JSON Export Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestJsonExport:
    def test_string_value(self):
        doc = _build_doc(name=OdinString("John"))
        result = json.loads(to_json(doc))
        assert result["name"] == "John"

    def test_integer_value(self):
        doc = _build_doc(age=OdinInteger(42))
        result = json.loads(to_json(doc))
        assert result["age"] == 42

    def test_number_value(self):
        doc = _build_doc(rate=OdinNumber(3.14))
        result = json.loads(to_json(doc))
        assert result["rate"] == pytest.approx(3.14)

    def test_boolean_value(self):
        doc = _build_doc(flag=TRUE)
        result = json.loads(to_json(doc))
        assert result["flag"] is True

    def test_null_value(self):
        doc = _build_doc(val=NULL)
        result = json.loads(to_json(doc))
        assert result["val"] is None

    def test_currency_value(self):
        doc = _build_doc(price=OdinCurrency(Decimal("99.99")))
        result = json.loads(to_json(doc))
        assert result["price"] == pytest.approx(99.99)

    def test_percent_value(self):
        doc = _build_doc(rate=OdinPercent(75.5))
        result = json.loads(to_json(doc))
        assert result["rate"] == pytest.approx(75.5)

    def test_date_value(self):
        doc = _build_doc(dt=OdinDate(date(2024, 1, 15), "2024-01-15"))
        result = json.loads(to_json(doc))
        assert result["dt"] == "2024-01-15"

    def test_timestamp_value(self):
        doc = _build_doc(ts=OdinTimestamp(datetime(2024, 1, 15, 10, 30), "2024-01-15T10:30:00"))
        result = json.loads(to_json(doc))
        assert result["ts"] == "2024-01-15T10:30:00"

    def test_reference_value(self):
        doc = _build_doc(ref=OdinReference("policy.holder"))
        result = json.loads(to_json(doc))
        assert result["ref"] == "@policy.holder"

    def test_nested_section(self):
        b = OdinDocumentBuilder()
        b.set("customer.name", OdinString("John"))
        b.set("customer.age", OdinInteger(30))
        doc = b.build()
        result = json.loads(to_json(doc))
        assert result["customer"]["name"] == "John"
        assert result["customer"]["age"] == 30

    def test_array_values(self):
        b = OdinDocumentBuilder()
        b.set("items[0].name", OdinString("A"))
        b.set("items[1].name", OdinString("B"))
        doc = b.build()
        result = json.loads(to_json(doc))
        assert result["items"][0]["name"] == "A"
        assert result["items"][1]["name"] == "B"

    def test_indent(self):
        doc = _build_doc(name=OdinString("John"))
        result = to_json(doc, indent=2)
        assert "\n" in result

    def test_empty_document(self):
        doc = OdinDocumentBuilder().build()
        result = json.loads(to_json(doc))
        assert result == {}

    def test_binary_value(self):
        doc = _build_doc(data=OdinBinary(b"hello"))
        result = json.loads(to_json(doc))
        assert isinstance(result["data"], str)

    def test_time_value(self):
        doc = _build_doc(t=OdinTime("10:30:00"))
        result = json.loads(to_json(doc))
        assert result["t"] == "10:30:00"

    def test_duration_value(self):
        doc = _build_doc(d=OdinDuration("P1Y2M"))
        result = json.loads(to_json(doc))
        assert result["d"] == "P1Y2M"


# ─────────────────────────────────────────────────────────────────────────────
# XML Export Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestXmlExport:
    def test_simple_element(self):
        doc = _build_doc(name=OdinString("John"))
        result = to_xml(doc)
        assert "<name>John</name>" in result

    def test_root_element(self):
        doc = _build_doc(name=OdinString("John"))
        result = to_xml(doc, root_element="data")
        assert "<data" in result
        assert "</data>" in result

    def test_xml_declaration(self):
        doc = _build_doc(name=OdinString("John"))
        result = to_xml(doc, declaration=True)
        assert '<?xml version="1.0" encoding="UTF-8"?>' in result

    def test_no_declaration(self):
        doc = _build_doc(name=OdinString("John"))
        result = to_xml(doc, declaration=False)
        assert "<?xml" not in result

    def test_integer_value(self):
        doc = _build_doc(age=OdinInteger(42))
        result = to_xml(doc)
        assert "42</age>" in result

    def test_boolean_value(self):
        doc = _build_doc(flag=TRUE)
        result = to_xml(doc)
        assert "true</flag>" in result

    def test_null_skipped(self):
        doc = _build_doc(val=NULL)
        result = to_xml(doc)
        assert "<val" not in result

    def test_nested_section(self):
        b = OdinDocumentBuilder()
        b.set("person.name", OdinString("John"))
        doc = b.build()
        result = to_xml(doc)
        assert "<person>" in result
        assert "<name>John</name>" in result
        assert "</person>" in result

    def test_entity_escaping(self):
        doc = _build_doc(val=OdinString("a & b < c"))
        result = to_xml(doc)
        assert "&amp;" in result
        assert "&lt;" in result

    def test_array_items(self):
        b = OdinDocumentBuilder()
        b.set("items[0].name", OdinString("A"))
        b.set("items[1].name", OdinString("B"))
        doc = b.build()
        result = to_xml(doc)
        assert "<name>A</name>" in result
        assert "<name>B</name>" in result

    def test_empty_document(self):
        doc = OdinDocumentBuilder().build()
        result = to_xml(doc, declaration=False)
        assert "<root" in result
        assert "</root>" in result


# ─────────────────────────────────────────────────────────────────────────────
# CSV Export Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCsvExport:
    def test_array_to_csv(self):
        b = OdinDocumentBuilder()
        b.set("rows[0].name", OdinString("John"))
        b.set("rows[0].age", OdinInteger(30))
        b.set("rows[1].name", OdinString("Jane"))
        b.set("rows[1].age", OdinInteger(25))
        doc = b.build()
        result = to_csv(doc)
        lines = result.strip().split("\n")
        assert len(lines) == 3  # header + 2 rows
        assert "name" in lines[0]
        assert "age" in lines[0]

    def test_csv_quoting(self):
        b = OdinDocumentBuilder()
        b.set("rows[0].name", OdinString("Smith, John"))
        doc = b.build()
        result = to_csv(doc)
        assert '"Smith, John"' in result

    def test_csv_delimiter(self):
        b = OdinDocumentBuilder()
        b.set("rows[0].a", OdinString("x"))
        b.set("rows[0].b", OdinString("y"))
        doc = b.build()
        result = to_csv(doc, delimiter="|")
        assert "|" in result

    def test_single_row_fallback(self):
        doc = _build_doc(name=OdinString("John"), age=OdinInteger(30))
        result = to_csv(doc)
        lines = result.strip().split("\n")
        assert len(lines) == 2  # header + 1 row

    def test_null_as_empty(self):
        b = OdinDocumentBuilder()
        b.set("rows[0].name", OdinString("John"))
        b.set("rows[0].val", NULL)
        doc = b.build()
        result = to_csv(doc)
        assert result.count(",") >= 1

    def test_boolean_value(self):
        b = OdinDocumentBuilder()
        b.set("rows[0].flag", TRUE)
        doc = b.build()
        result = to_csv(doc)
        assert "true" in result


# ─────────────────────────────────────────────────────────────────────────────
# Fixed-Width Export Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestFixedWidthExport:
    def test_basic_output(self):
        doc = _build_doc(name=OdinString("John"), age=OdinInteger(42))
        fields = [
            {"path": "name", "pos": 0, "len": 10},
            {"path": "age", "pos": 10, "len": 5},
        ]
        result = to_fixed_width(doc, fields=fields, line_width=15)
        assert len(result) == 15
        assert result[:4] == "John"
        assert "42" in result[10:]

    def test_right_align(self):
        doc = _build_doc(amount=OdinInteger(42))
        fields = [{"path": "amount", "pos": 0, "len": 10, "align": "right"}]
        result = to_fixed_width(doc, fields=fields, line_width=10)
        assert result == "        42"

    def test_padding(self):
        doc = _build_doc(name=OdinString("AB"))
        fields = [{"path": "name", "pos": 0, "len": 5}]
        result = to_fixed_width(doc, fields=fields, line_width=5, pad_char=".")
        assert result == "AB..."

    def test_truncation(self):
        doc = _build_doc(name=OdinString("VeryLongName"))
        fields = [{"path": "name", "pos": 0, "len": 5}]
        result = to_fixed_width(doc, fields=fields, line_width=5)
        assert len(result) == 5
        assert result == "VeryL"

    def test_empty_fields(self):
        result = to_fixed_width(OdinDocumentBuilder().build(), fields=[], line_width=10)
        assert result == ""

    def test_zero_line_width(self):
        doc = _build_doc(name=OdinString("John"))
        fields = [{"path": "name", "pos": 0, "len": 5}]
        result = to_fixed_width(doc, fields=fields, line_width=0)
        assert result == ""


# ─────────────────────────────────────────────────────────────────────────────
# DynValue Formatter Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestJsonFormatter:
    def test_simple_object(self):
        dv = DynValue.of_object({"name": DynValue.of_string("John"), "age": DynValue.of_integer(30)})
        result = json.loads(format_json(dv))
        assert result["name"] == "John"
        assert result["age"] == 30

    def test_nested(self):
        dv = DynValue.of_object({"a": DynValue.of_object({"b": DynValue.of_integer(1)})})
        result = json.loads(format_json(dv))
        assert result["a"]["b"] == 1

    def test_array(self):
        dv = DynValue.of_array([DynValue.of_integer(1), DynValue.of_integer(2)])
        result = json.loads(format_json(dv))
        assert result == [1, 2]

    def test_null(self):
        dv = DynValue.of_null()
        assert format_json(dv) == "null"

    def test_bool(self):
        assert format_json(DynValue.of_bool(True)) == "true"

    def test_string_escaping(self):
        dv = DynValue.of_string('hello "world"')
        result = json.loads(format_json(dv))
        assert result == 'hello "world"'

    def test_indent(self):
        dv = DynValue.of_object({"a": DynValue.of_integer(1)})
        result = format_json(dv, indent=2)
        assert "\n" in result


class TestCsvFormatter:
    def test_array_of_objects(self):
        dv = DynValue.of_array([
            DynValue.of_object({"name": DynValue.of_string("John"), "age": DynValue.of_integer(30)}),
            DynValue.of_object({"name": DynValue.of_string("Jane"), "age": DynValue.of_integer(25)}),
        ])
        result = format_csv(dv)
        lines = result.strip().split("\n")
        assert len(lines) == 3

    def test_quoting(self):
        dv = DynValue.of_array([
            DynValue.of_object({"val": DynValue.of_string("a,b")}),
        ])
        result = format_csv(dv)
        assert '"a,b"' in result

    def test_custom_delimiter(self):
        dv = DynValue.of_array([
            DynValue.of_object({"a": DynValue.of_string("x"), "b": DynValue.of_string("y")}),
        ])
        result = format_csv(dv, delimiter="|")
        assert "|" in result


class TestXmlFormatter:
    def test_simple(self):
        dv = DynValue.of_object({"name": DynValue.of_string("John")})
        result = format_xml(dv)
        assert "<name>John</name>" in result

    def test_nested(self):
        dv = DynValue.of_object({"person": DynValue.of_object({"name": DynValue.of_string("John")})})
        result = format_xml(dv)
        assert "<person>" in result
        assert "<name>John</name>" in result

    def test_array_items(self):
        dv = DynValue.of_object({"items": DynValue.of_array([DynValue.of_string("a"), DynValue.of_string("b")])})
        result = format_xml(dv)
        assert "<items>" in result
        assert "a</items>" in result


class TestOdinFormatter:
    def test_simple(self):
        dv = DynValue.of_object({"name": DynValue.of_string("John"), "age": DynValue.of_integer(42)})
        result = format_odin(dv)
        assert 'name = "John"' in result
        assert "age = ##42" in result

    def test_nested(self):
        dv = DynValue.of_object({"person": DynValue.of_object({"name": DynValue.of_string("John")})})
        result = format_odin(dv)
        assert "{person}" in result
        assert 'name = "John"' in result


class TestFixedWidthFormatter:
    def test_basic(self):
        # format_fixed_width requires a transform with segment metadata;
        # without one it returns empty string
        dv = DynValue.of_object({"name": DynValue.of_string("John"), "age": DynValue.of_integer(42)})
        result = format_fixed_width(dv)
        assert result == ""


class TestFlatFormatter:
    def test_simple(self):
        dv = DynValue.of_object({"name": DynValue.of_string("John"), "age": DynValue.of_integer(30)})
        result = format_flat(dv)
        assert "name=John" in result
        assert "age=30" in result

    def test_nested(self):
        dv = DynValue.of_object({"person": DynValue.of_object({"name": DynValue.of_string("John")})})
        result = format_flat(dv)
        assert "person.name=John" in result

    def test_array(self):
        dv = DynValue.of_object({"items": DynValue.of_array([DynValue.of_string("a"), DynValue.of_string("b")])})
        result = format_flat(dv)
        assert "items[0]=a" in result
        assert "items[1]=b" in result
