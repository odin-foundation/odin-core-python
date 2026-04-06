"""Tests for source parsers - JSON, CSV, XML, Fixed-Width, Flat KVP, YAML."""

import pytest
from odin.transform.dyn_value import DynValue, DynType
from odin.transform.source_parsers.json_parser import parse_json
from odin.transform.source_parsers.csv_parser import parse_csv
from odin.transform.source_parsers.xml_parser import parse_xml
from odin.transform.source_parsers.fixed_width_parser import parse_fixed_width
from odin.transform.source_parsers.flat_parser import parse_flat
from odin.transform.source_parsers.yaml_parser import parse_yaml


# ─────────────────────────────────────────────────────────────────────────────
# DynValue Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDynValue:
    def test_of_null(self):
        v = DynValue.of_null()
        assert v.is_null()
        assert v.type == DynType.NULL

    def test_of_bool_true(self):
        v = DynValue.of_bool(True)
        assert v.as_bool() is True
        assert v.is_bool()

    def test_of_bool_false(self):
        v = DynValue.of_bool(False)
        assert v.as_bool() is False

    def test_of_integer(self):
        v = DynValue.of_integer(42)
        assert v.as_int() == 42
        assert v.is_integer()

    def test_of_integer_as_float(self):
        v = DynValue.of_integer(42)
        assert v.as_float() == 42.0

    def test_of_float(self):
        v = DynValue.of_float(3.14)
        assert v.as_float() == pytest.approx(3.14)
        assert v.is_float()

    def test_of_string(self):
        v = DynValue.of_string("hello")
        assert v.as_string() == "hello"
        assert v.is_string()

    def test_of_array(self):
        v = DynValue.of_array([DynValue.of_integer(1), DynValue.of_integer(2)])
        assert v.is_array()
        assert len(v.as_array()) == 2
        assert v.as_array()[0].as_int() == 1

    def test_of_object(self):
        v = DynValue.of_object({"name": DynValue.of_string("John")})
        assert v.is_object()
        assert v.as_object()["name"].as_string() == "John"

    def test_of_date(self):
        from datetime import date
        v = DynValue.of_date(date(2024, 1, 15))
        assert v.type == DynType.DATE
        assert v.as_string() == "2024-01-15"

    def test_of_timestamp(self):
        from datetime import datetime
        v = DynValue.of_timestamp(datetime(2024, 1, 15, 10, 30, 0))
        assert v.type == DynType.TIMESTAMP

    def test_of_time(self):
        v = DynValue.of_time("10:30:00")
        assert v.type == DynType.TIME
        assert v.as_string() == "10:30:00"

    def test_of_duration(self):
        v = DynValue.of_duration("P1Y2M")
        assert v.type == DynType.DURATION
        assert v.as_string() == "P1Y2M"

    def test_of_currency(self):
        from decimal import Decimal
        v = DynValue.of_currency(Decimal("99.99"), "USD", 2)
        assert v.type == DynType.CURRENCY
        assert v.as_float() == pytest.approx(99.99)

    def test_of_percent(self):
        v = DynValue.of_percent(75.5)
        assert v.type == DynType.PERCENT
        assert v.as_float() == pytest.approx(75.5)

    def test_of_reference(self):
        v = DynValue.of_reference("policy.holder")
        assert v.type == DynType.REFERENCE
        assert v.as_string() == "policy.holder"

    def test_of_binary(self):
        v = DynValue.of_binary(b"hello")
        assert v.type == DynType.BINARY

    def test_get_field(self):
        v = DynValue.of_object({"a": DynValue.of_integer(1)})
        assert v.get("a").as_int() == 1
        assert v.get("missing") is None

    def test_get_index(self):
        v = DynValue.of_array([DynValue.of_string("x"), DynValue.of_string("y")])
        assert v.get_index(0).as_string() == "x"
        assert v.get_index(5) is None

    def test_as_string_coercion(self):
        assert DynValue.of_integer(42).as_string() == "42"
        assert DynValue.of_float(3.14).as_string() == "3.14"
        assert DynValue.of_bool(True).as_string() == "true"
        assert DynValue.of_null().as_string() == ""


# ─────────────────────────────────────────────────────────────────────────────
# JSON Source Parser Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestJsonParser:
    def test_parse_string(self):
        result = parse_json('{"name": "John"}')
        assert result.is_object()
        assert result.get("name").as_string() == "John"

    def test_parse_dict(self):
        result = parse_json({"name": "John", "age": 30})
        assert result.get("name").as_string() == "John"
        assert result.get("age").as_int() == 30

    def test_parse_list(self):
        result = parse_json([1, 2, 3])
        assert result.is_array()
        assert len(result.as_array()) == 3

    def test_parse_nested(self):
        result = parse_json({"a": {"b": {"c": 42}}})
        assert result.get("a").get("b").get("c").as_int() == 42

    def test_parse_null(self):
        result = parse_json({"x": None})
        assert result.get("x").is_null()

    def test_parse_boolean(self):
        result = parse_json({"t": True, "f": False})
        assert result.get("t").as_bool() is True
        assert result.get("f").as_bool() is False

    def test_parse_integer(self):
        result = parse_json({"n": 42})
        assert result.get("n").is_integer()
        assert result.get("n").as_int() == 42

    def test_parse_float(self):
        result = parse_json({"n": 3.14})
        assert result.get("n").is_float()
        assert result.get("n").as_float() == pytest.approx(3.14)

    def test_parse_array_of_objects(self):
        result = parse_json([{"id": 1}, {"id": 2}])
        assert result.as_array()[0].get("id").as_int() == 1

    def test_parse_empty_object(self):
        result = parse_json({})
        assert result.is_object()
        assert len(result.as_object()) == 0

    def test_parse_empty_array(self):
        result = parse_json([])
        assert result.is_array()
        assert len(result.as_array()) == 0

    def test_parse_mixed_array(self):
        result = parse_json([1, "two", True, None])
        arr = result.as_array()
        assert arr[0].as_int() == 1
        assert arr[1].as_string() == "two"
        assert arr[2].as_bool() is True
        assert arr[3].is_null()

    def test_parse_string_json(self):
        result = parse_json('"hello"')
        assert result.is_string()
        assert result.as_string() == "hello"

    def test_parse_invalid_json(self):
        with pytest.raises(ValueError):
            parse_json("{invalid")

    def test_parse_empty_raises(self):
        with pytest.raises(ValueError):
            parse_json("")

    def test_parse_large_integer(self):
        result = parse_json({"n": 9999999999999})
        assert result.get("n").as_int() == 9999999999999


# ─────────────────────────────────────────────────────────────────────────────
# CSV Source Parser Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCsvParser:
    def test_basic_csv(self):
        result = parse_csv("name,age\nJohn,30\nJane,25")
        arr = result.as_array()
        assert len(arr) == 2
        assert arr[0].get("name").as_string() == "John"
        assert arr[0].get("age").as_int() == 30

    def test_quoted_fields(self):
        result = parse_csv('name,desc\n"Smith, John","Has a ""quote"""')
        arr = result.as_array()
        assert arr[0].get("name").as_string() == "Smith, John"
        assert arr[0].get("desc").as_string() == 'Has a "quote"'

    def test_no_header(self):
        result = parse_csv("John,30", has_header=False)
        arr = result.as_array()
        assert arr[0].is_array()
        assert arr[0].as_array()[0].as_string() == "John"

    def test_custom_delimiter(self):
        result = parse_csv("name|age\nJohn|30", delimiter="|")
        assert result.as_array()[0].get("name").as_string() == "John"

    def test_empty_csv(self):
        result = parse_csv("")
        assert result.is_array()
        assert len(result.as_array()) == 0

    def test_type_inference_bool(self):
        result = parse_csv("val\ntrue\nfalse")
        arr = result.as_array()
        assert arr[0].get("val").as_bool() is True
        assert arr[1].get("val").as_bool() is False

    def test_type_inference_null(self):
        result = parse_csv("val\nnull")
        assert result.as_array()[0].get("val").is_null()

    def test_type_inference_integer(self):
        result = parse_csv("val\n42")
        assert result.as_array()[0].get("val").as_int() == 42

    def test_type_inference_float(self):
        result = parse_csv("val\n3.14")
        assert result.as_array()[0].get("val").as_float() == pytest.approx(3.14)

    def test_empty_values(self):
        result = parse_csv("a,b\n1,\n,2")
        arr = result.as_array()
        assert arr[0].get("b").is_null()
        assert arr[1].get("a").is_null()

    def test_crlf_line_endings(self):
        result = parse_csv("name,age\r\nJohn,30\r\n")
        assert result.as_array()[0].get("name").as_string() == "John"

    def test_multiline_quoted(self):
        result = parse_csv('val\n"line1\nline2"')
        assert result.as_array()[0].get("val").as_string() == "line1\nline2"

    def test_header_only(self):
        result = parse_csv("name,age\n")
        assert len(result.as_array()) == 0


# ─────────────────────────────────────────────────────────────────────────────
# XML Source Parser Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestXmlParser:
    def test_simple_element(self):
        result = parse_xml("<root><name>John</name></root>")
        assert result.get("root").get("name").as_string() == "John"

    def test_attributes(self):
        result = parse_xml('<root><entry id="1">hello</entry></root>')
        entry = result.get("root").get("entry")
        assert entry.get("@id").as_string() == "1"
        assert entry.get("_text").as_string() == "hello"

    def test_nested_elements(self):
        result = parse_xml("<root><a><b><c>deep</c></b></a></root>")
        assert result.get("root").get("a").get("b").get("c").as_string() == "deep"

    def test_repeated_elements_become_array(self):
        result = parse_xml("<root><item>a</item><item>b</item></root>")
        items = result.get("root").get("item")
        assert items.is_array()
        assert len(items.as_array()) == 2

    def test_self_closing(self):
        result = parse_xml("<root><empty/></root>")
        assert result.get("root").get("empty").is_null()

    def test_nil_attribute(self):
        result = parse_xml('<root><val xsi:nil="true"/></root>')
        assert result.get("root").get("val").is_null()

    def test_empty_element(self):
        result = parse_xml("<root><val></val></root>")
        assert result.get("root").get("val").as_string() == ""

    def test_xml_declaration_stripped(self):
        result = parse_xml('<?xml version="1.0"?><root><x>1</x></root>')
        assert result.get("root").get("x").as_string() == "1"

    def test_cdata(self):
        result = parse_xml("<root><data><![CDATA[<html>]]></data></root>")
        assert result.get("root").get("data").as_string() == "<html>"

    def test_entity_decoding(self):
        result = parse_xml("<root><val>a &amp; b</val></root>")
        assert result.get("root").get("val").as_string() == "a & b"

    def test_multiple_attributes(self):
        result = parse_xml('<root><entry id="1" type="test"/></root>')
        entry = result.get("root").get("entry")
        assert entry.get("@id").as_string() == "1"
        assert entry.get("@type").as_string() == "test"

    def test_mixed_content(self):
        result = parse_xml("<root><p>text<b>bold</b></p></root>")
        p = result.get("root").get("p")
        assert p.get("_text").as_string() == "text"
        assert p.get("b").as_string() == "bold"

    def test_invalid_xml(self):
        with pytest.raises(ValueError):
            parse_xml("<root><unclosed>")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            parse_xml("")

    def test_namespace_stripped(self):
        result = parse_xml('<ns:root xmlns:ns="http://example.com"><ns:name>val</ns:name></ns:root>')
        assert result.get("ns:root").get("ns:name").as_string() == "val"


# ─────────────────────────────────────────────────────────────────────────────
# Fixed-Width Source Parser Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestFixedWidthParser:
    def test_single_record(self):
        fields = [
            {"name": "first", "pos": 0, "len": 10},
            {"name": "last", "pos": 10, "len": 10},
        ]
        result = parse_fixed_width("John      Smith     ", fields=fields)
        assert result.get("first").as_string() == "John"
        assert result.get("last").as_string() == "Smith"

    def test_multiple_records(self):
        fields = [
            {"name": "name", "pos": 0, "len": 5},
            {"name": "age", "pos": 5, "len": 3},
        ]
        result = parse_fixed_width("John 30 \nJane 25 ", fields=fields)
        assert result.is_array()
        assert len(result.as_array()) == 2
        assert result.as_array()[0].get("name").as_string() == "John"

    def test_trimming(self):
        fields = [{"name": "val", "pos": 0, "len": 10}]
        result = parse_fixed_width("hello     ", fields=fields)
        assert result.get("val").as_string() == "hello"

    def test_out_of_bounds(self):
        fields = [{"name": "val", "pos": 0, "len": 20}]
        result = parse_fixed_width("short", fields=fields)
        assert result.get("val").as_string() == "short"

    def test_empty_input(self):
        fields = [{"name": "val", "pos": 0, "len": 5}]
        result = parse_fixed_width("", fields=fields)
        assert result.is_array()
        assert len(result.as_array()) == 0

    def test_integer_type(self):
        fields = [{"name": "age", "pos": 0, "len": 3, "type": "integer"}]
        result = parse_fixed_width("042", fields=fields)
        assert result.get("age").as_int() == 42

    def test_number_type(self):
        fields = [{"name": "rate", "pos": 0, "len": 5, "type": "number"}]
        result = parse_fixed_width("3.14 ", fields=fields)
        assert result.get("rate").as_float() == pytest.approx(3.14)

    def test_implied_decimals(self):
        fields = [{"name": "amount", "pos": 0, "len": 5, "type": "number", "implied_decimals": 2}]
        result = parse_fixed_width("12345", fields=fields)
        assert result.get("amount").as_float() == pytest.approx(123.45)

    def test_date_type(self):
        fields = [{"name": "dt", "pos": 0, "len": 8, "type": "date"}]
        result = parse_fixed_width("20240115", fields=fields)
        assert result.get("dt").as_string() == "2024-01-15"

    def test_no_fields_returns_lines(self):
        result = parse_fixed_width("line1\nline2")
        assert result.is_array()
        assert len(result.as_array()) == 2


# ─────────────────────────────────────────────────────────────────────────────
# Flat KVP Source Parser Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestFlatParser:
    def test_simple_kvp(self):
        result = parse_flat("name = John\nage = 30")
        assert result.get("name").as_string() == "John"
        assert result.get("age").as_int() == 30

    def test_nested_paths(self):
        result = parse_flat("person.name = John\nperson.age = 30")
        assert result.get("person").get("name").as_string() == "John"

    def test_array_paths(self):
        result = parse_flat("items[0] = a\nitems[1] = b")
        arr = result.get("items").as_array()
        assert arr[0].as_string() == "a"
        assert arr[1].as_string() == "b"

    def test_mixed_paths(self):
        result = parse_flat("employees[0].name = John\nemployees[0].age = 30")
        emp = result.get("employees").as_array()[0]
        assert emp.get("name").as_string() == "John"
        assert emp.get("age").as_int() == 30

    def test_comments_skipped(self):
        result = parse_flat("# comment\nname = John\n; another comment")
        assert result.get("name").as_string() == "John"

    def test_empty_lines_skipped(self):
        result = parse_flat("\nname = John\n\nage = 30\n")
        assert result.get("name").as_string() == "John"

    def test_quoted_string(self):
        result = parse_flat('name = "John Smith"')
        assert result.get("name").as_string() == "John Smith"

    def test_bool_inference(self):
        result = parse_flat("flag = true")
        assert result.get("flag").as_bool() is True

    def test_null_tilde(self):
        result = parse_flat("val = ~")
        assert result.get("val").is_null()

    def test_null_word(self):
        result = parse_flat("val = null")
        assert result.get("val").is_null()

    def test_empty_value(self):
        result = parse_flat("val = ")
        assert result.get("val").is_null()

    def test_empty_input(self):
        result = parse_flat("")
        assert result.is_object()
        assert len(result.as_object()) == 0


# ─────────────────────────────────────────────────────────────────────────────
# YAML Source Parser Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestYamlParser:
    def test_simple_mapping(self):
        result = parse_yaml("name: John\nage: 30")
        assert result.get("name").as_string() == "John"
        assert result.get("age").as_int() == 30

    def test_nested_mapping(self):
        result = parse_yaml("person:\n  name: John\n  age: 30")
        assert result.get("person").get("name").as_string() == "John"

    def test_array(self):
        result = parse_yaml("items:\n  - one\n  - two\n  - three")
        arr = result.get("items").as_array()
        assert len(arr) == 3
        assert arr[0].as_string() == "one"

    def test_array_of_objects(self):
        result = parse_yaml("people:\n  - name: John\n    age: 30\n  - name: Jane\n    age: 25")
        arr = result.get("people").as_array()
        assert arr[0].get("name").as_string() == "John"
        assert arr[1].get("age").as_int() == 25

    def test_boolean_values(self):
        result = parse_yaml("a: true\nb: false\nc: yes\nd: no")
        assert result.get("a").as_bool() is True
        assert result.get("b").as_bool() is False
        assert result.get("c").as_bool() is True
        assert result.get("d").as_bool() is False

    def test_null_values(self):
        result = parse_yaml("a: null\nb: ~")
        assert result.get("a").is_null()
        assert result.get("b").is_null()

    def test_quoted_strings(self):
        result = parse_yaml('name: "John Smith"\nother: \'hello\'')
        assert result.get("name").as_string() == "John Smith"
        assert result.get("other").as_string() == "hello"

    def test_comments(self):
        result = parse_yaml("# comment\nname: John  # inline")
        assert result.get("name").as_string() == "John"

    def test_empty_input(self):
        result = parse_yaml("")
        assert result.is_object()

    def test_integer_type(self):
        result = parse_yaml("val: 42")
        assert result.get("val").as_int() == 42

    def test_float_type(self):
        result = parse_yaml("val: 3.14")
        assert result.get("val").as_float() == pytest.approx(3.14)

    def test_deeply_nested(self):
        result = parse_yaml("a:\n  b:\n    c:\n      d: deep")
        assert result.get("a").get("b").get("c").get("d").as_string() == "deep"
