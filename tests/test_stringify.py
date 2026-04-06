"""Tests for ODIN stringify serialization."""
import pytest
import odin
from odin.types.document import OdinDocumentBuilder, OdinModifiers
from odin.types.values import (
    OdinNull, OdinBoolean, OdinString, OdinNumber, OdinInteger,
    OdinCurrency, OdinPercent, OdinDate, OdinTimestamp, OdinTime,
    OdinDuration, OdinReference, OdinBinary, OdinVerbExpression,
    OdinArray, OdinObject, NULL, TRUE, FALSE,
)
from odin.types.options import DumpOptions, LineEnding
from decimal import Decimal
from datetime import date, datetime


# ─── Value Formatting ───

class TestValueFormatting:
    """Test individual value type formatting."""

    def test_null_value(self):
        doc = OdinDocumentBuilder().set("x", NULL).build()
        assert odin.dumps(doc) == "x = ~\n"

    def test_boolean_true(self):
        doc = OdinDocumentBuilder().set("x", TRUE).build()
        assert odin.dumps(doc) == "x = ?true\n"

    def test_boolean_false(self):
        doc = OdinDocumentBuilder().set("x", FALSE).build()
        assert odin.dumps(doc) == "x = ?false\n"

    def test_string_simple(self):
        doc = OdinDocumentBuilder().set("x", OdinString("hello")).build()
        assert odin.dumps(doc) == 'x = "hello"\n'

    def test_string_with_quotes(self):
        doc = OdinDocumentBuilder().set("x", OdinString('say "hi"')).build()
        assert odin.dumps(doc) == 'x = "say \\"hi\\""\n'

    def test_string_with_newline(self):
        doc = OdinDocumentBuilder().set("x", OdinString("a\nb")).build()
        assert odin.dumps(doc) == 'x = "a\\nb"\n'

    def test_string_with_tab(self):
        doc = OdinDocumentBuilder().set("x", OdinString("a\tb")).build()
        assert odin.dumps(doc) == 'x = "a\\tb"\n'

    def test_string_with_backslash(self):
        doc = OdinDocumentBuilder().set("x", OdinString("a\\b")).build()
        assert odin.dumps(doc) == 'x = "a\\\\b"\n'

    def test_string_with_carriage_return(self):
        doc = OdinDocumentBuilder().set("x", OdinString("a\rb")).build()
        assert odin.dumps(doc) == 'x = "a\\rb"\n'

    def test_number_simple(self):
        doc = OdinDocumentBuilder().set("x", OdinNumber(3.14)).build()
        assert odin.dumps(doc) == "x = #3.14\n"

    def test_number_with_raw(self):
        doc = OdinDocumentBuilder().set("x", OdinNumber(1e10, raw="1e10")).build()
        assert odin.dumps(doc) == "x = #1e10\n"

    def test_integer(self):
        doc = OdinDocumentBuilder().set("x", OdinInteger(42)).build()
        assert odin.dumps(doc) == "x = ##42\n"

    def test_integer_negative(self):
        doc = OdinDocumentBuilder().set("x", OdinInteger(-100)).build()
        assert odin.dumps(doc) == "x = ##-100\n"

    def test_integer_with_raw(self):
        doc = OdinDocumentBuilder().set("x", OdinInteger(999, raw="999")).build()
        assert odin.dumps(doc) == "x = ##999\n"

    def test_currency_simple(self):
        doc = OdinDocumentBuilder().set("x", OdinCurrency(Decimal("99.99"))).build()
        assert odin.dumps(doc) == "x = #$99.99\n"

    def test_currency_with_code(self):
        doc = OdinDocumentBuilder().set("x", OdinCurrency(Decimal("100.00"), currency_code="USD")).build()
        assert odin.dumps(doc) == "x = #$100.00:USD\n"

    def test_currency_with_raw(self):
        doc = OdinDocumentBuilder().set("x", OdinCurrency(Decimal("50.00"), raw="50.00")).build()
        assert odin.dumps(doc) == "x = #$50.00\n"

    def test_percent(self):
        doc = OdinDocumentBuilder().set("x", OdinPercent(0.15, raw="0.15")).build()
        assert odin.dumps(doc) == "x = #%0.15\n"

    def test_percent_no_raw(self):
        doc = OdinDocumentBuilder().set("x", OdinPercent(0.5)).build()
        assert odin.dumps(doc) == "x = #%0.5\n"

    def test_date(self):
        doc = OdinDocumentBuilder().set("x", OdinDate(date(2024, 6, 15), raw="2024-06-15")).build()
        assert odin.dumps(doc) == "x = 2024-06-15\n"

    def test_timestamp(self):
        doc = OdinDocumentBuilder().set("x", OdinTimestamp(datetime(2024, 6, 15, 10, 30), raw="2024-06-15T10:30:00Z")).build()
        assert odin.dumps(doc) == "x = 2024-06-15T10:30:00Z\n"

    def test_time(self):
        doc = OdinDocumentBuilder().set("x", OdinTime("T09:30:00")).build()
        assert odin.dumps(doc) == "x = T09:30:00\n"

    def test_duration(self):
        doc = OdinDocumentBuilder().set("x", OdinDuration("P6M")).build()
        assert odin.dumps(doc) == "x = P6M\n"

    def test_reference(self):
        doc = OdinDocumentBuilder().set("x", OdinReference("drivers[0]")).build()
        assert odin.dumps(doc) == "x = @drivers[0]\n"

    def test_binary(self):
        doc = OdinDocumentBuilder().set("x", OdinBinary(b"Hello")).build()
        assert odin.dumps(doc) == "x = ^SGVsbG8=\n"

    def test_binary_with_algorithm(self):
        doc = OdinDocumentBuilder().set("x", OdinBinary(b"Hello", algorithm="sha256")).build()
        assert odin.dumps(doc) == "x = ^sha256:SGVsbG8=\n"

    def test_array_marker(self):
        doc = OdinDocumentBuilder().set("x", OdinArray()).build()
        assert odin.dumps(doc) == "x = []\n"

    def test_object_marker(self):
        doc = OdinDocumentBuilder().set("x", OdinObject()).build()
        assert odin.dumps(doc) == "x = {}\n"

    def test_verb_expression(self):
        doc = OdinDocumentBuilder().set("x", OdinVerbExpression("upper", args=(OdinReference("name"),))).build()
        assert odin.dumps(doc) == "x = %upper @name\n"

    def test_verb_expression_custom(self):
        doc = OdinDocumentBuilder().set("x", OdinVerbExpression("myverb", is_custom=True)).build()
        assert odin.dumps(doc) == "x = %&myverb\n"


# ─── Modifier Formatting ───

class TestModifierFormatting:
    """Test modifier prefix formatting."""

    def test_required(self):
        b = OdinDocumentBuilder()
        b.set("x", OdinString("val"), OdinModifiers(required=True))
        assert odin.dumps(b.build()) == 'x = !"val"\n'

    def test_confidential(self):
        b = OdinDocumentBuilder()
        b.set("x", OdinString("val"), OdinModifiers(confidential=True))
        assert odin.dumps(b.build()) == 'x = *"val"\n'

    def test_deprecated(self):
        b = OdinDocumentBuilder()
        b.set("x", OdinString("val"), OdinModifiers(deprecated=True))
        assert odin.dumps(b.build()) == 'x = -"val"\n'

    def test_combined_required_confidential(self):
        b = OdinDocumentBuilder()
        b.set("x", OdinString("val"), OdinModifiers(required=True, confidential=True))
        assert odin.dumps(b.build()) == 'x = !*"val"\n'

    def test_combined_all(self):
        b = OdinDocumentBuilder()
        b.set("x", OdinString("val"), OdinModifiers(required=True, confidential=True, deprecated=True))
        assert odin.dumps(b.build()) == 'x = !*-"val"\n'

    def test_no_modifiers(self):
        b = OdinDocumentBuilder()
        b.set("x", OdinString("val"))
        assert odin.dumps(b.build()) == 'x = "val"\n'


# ─── Header Grouping ───

class TestHeaderGrouping:
    """Test section header grouping."""

    def test_simple_section(self):
        text = "{Person}\nname = \"John\"\nage = ##30\n"
        doc = odin.parse(text)
        result = odin.dumps(doc)
        assert "{Person}" in result
        assert 'name = "John"' in result
        assert "age = ##30" in result

    def test_multiple_sections(self):
        text = "{person}\nname = \"Alice\"\n{address}\ncity = \"Austin\"\n"
        doc = odin.parse(text)
        result = odin.dumps(doc)
        assert "{person}" in result
        assert "{address}" in result

    def test_metadata_section(self):
        text = "{$}\nodin = \"1.0.0\"\n{}\nname = \"test\"\n"
        doc = odin.parse(text)
        result = odin.dumps(doc)
        assert "{$}" in result
        assert 'odin = "1.0.0"' in result
        assert "{}" in result

    def test_metadata_before_data(self):
        text = "{$}\nodin = \"1.0.0\"\n{}\n{person}\nname = \"John\"\n"
        doc = odin.parse(text)
        result = odin.dumps(doc)
        # {$} should come first
        dollar_pos = result.index("{$}")
        person_pos = result.index("{person}")
        assert dollar_pos < person_pos

    def test_flat_scalars_no_header(self):
        doc = OdinDocumentBuilder().set("x", OdinInteger(1)).set("y", OdinInteger(2)).build()
        result = odin.dumps(doc)
        assert "x = ##1\n" in result
        assert "y = ##2\n" in result
        assert "{" not in result.replace("##", "")

    def test_empty_document(self):
        doc = OdinDocumentBuilder().build()
        assert odin.dumps(doc) == ""


# ─── Options ───

class TestOptions:
    """Test stringify options."""

    def test_sort_paths(self):
        b = OdinDocumentBuilder()
        b.set("z", OdinInteger(1))
        b.set("a", OdinInteger(2))
        result = odin.dumps(b.build(), DumpOptions(sort_paths=True))
        a_pos = result.index("a =")
        z_pos = result.index("z =")
        assert a_pos < z_pos

    def test_no_headers(self):
        text = "{Person}\nname = \"John\"\nage = ##30\n"
        doc = odin.parse(text)
        result = odin.dumps(doc, DumpOptions(use_headers=False))
        assert "{Person}" not in result
        assert 'Person.name = "John"' in result

    def test_crlf_line_ending(self):
        doc = OdinDocumentBuilder().set("x", OdinInteger(1)).build()
        result = odin.dumps(doc, DumpOptions(line_ending=LineEnding.CRLF))
        assert result == "x = ##1\r\n"

    def test_lf_line_ending(self):
        doc = OdinDocumentBuilder().set("x", OdinInteger(1)).build()
        result = odin.dumps(doc, DumpOptions(line_ending=LineEnding.LF))
        assert result == "x = ##1\n"


# ─── Roundtrip ───

class TestRoundtrip:
    """Test parse -> stringify roundtrips."""

    def test_simple_values(self):
        text = "name = \"John\"\nage = ##30\n"
        doc = odin.parse(text)
        result = odin.dumps(doc)
        doc2 = odin.parse(result)
        assert doc2.get("name").value == "John"
        assert doc2.get("age").value == 30

    def test_all_types(self):
        text = (
            "n = ~\n"
            "b = ?true\n"
            "s = \"hello\"\n"
            "num = #3.14\n"
            "i = ##42\n"
            "c = #$99.99\n"
            "d = 2024-06-15\n"
            "r = @some.path\n"
        )
        doc = odin.parse(text)
        result = odin.dumps(doc)
        doc2 = odin.parse(result)
        assert isinstance(doc2.get("n"), OdinNull)
        assert doc2.get("b").value is True
        assert doc2.get("s").value == "hello"
        assert doc2.get("i").value == 42

    def test_section_roundtrip(self):
        text = "{person}\nname = \"Alice\"\nage = ##30\n"
        doc = odin.parse(text)
        result = odin.dumps(doc)
        doc2 = odin.parse(result)
        assert doc2.get("person.name").value == "Alice"
        assert doc2.get("person.age").value == 30

    def test_metadata_roundtrip(self):
        text = "{$}\nodin = \"1.0.0\"\n{}\nname = \"test\"\n"
        doc = odin.parse(text)
        result = odin.dumps(doc)
        doc2 = odin.parse(result)
        assert doc2.get("name") is not None or doc2.metadata.get("odin") is not None

    def test_modifiers_roundtrip(self):
        text = 'name = !"required"\n'
        doc = odin.parse(text)
        result = odin.dumps(doc)
        doc2 = odin.parse(result)
        assert doc2.get("name").value == "required"
        mods = doc2.modifiers.get("name")
        assert mods is not None
        assert mods.required is True

    def test_nested_section_roundtrip(self):
        text = (
            "{policy}\n"
            "number = \"PAP-001\"\n"
            "{policy}\n"
            "premium = #$747.50\n"
        )
        doc = odin.parse(text)
        result = odin.dumps(doc)
        doc2 = odin.parse(result)
        assert doc2.get("policy.number").value == "PAP-001"

    def test_string_escape_roundtrip(self):
        text = 'text = "line1\\nline2\\ttab\\\\backslash"\n'
        doc = odin.parse(text)
        result = odin.dumps(doc)
        doc2 = odin.parse(result)
        assert doc2.get("text").value == "line1\nline2\ttab\\backslash"

    def test_multiple_modifiers_roundtrip(self):
        text = 'x = !*-"secret"\n'
        doc = odin.parse(text)
        result = odin.dumps(doc)
        doc2 = odin.parse(result)
        mods = doc2.modifiers.get("x")
        assert mods.required
        assert mods.confidential
        assert mods.deprecated


# ─── Tabular Arrays ───

class TestTabularArrays:
    """Test tabular array output."""

    def test_primitive_array(self):
        text = '{tags[] : ~}\n"urgent"\n"important"\n'
        doc = odin.parse(text)
        result = odin.dumps(doc)
        assert "tags[]" in result
        assert '"urgent"' in result
        assert '"important"' in result

    def test_tabular_array(self):
        text = '{items[] : name, qty}\n"Widget", ##10\n"Gadget", ##5\n'
        doc = odin.parse(text)
        result = odin.dumps(doc)
        assert "items[]" in result
        assert '"Widget"' in result

    def test_tabular_with_dot_columns(self):
        text = '{items[] : product.name, product.sku}\n"Widget", "WGT-001"\n'
        doc = odin.parse(text)
        result = odin.dumps(doc)
        assert "items[]" in result

    def test_tabular_roundtrip(self):
        text = '{items[] : name, qty}\n"Widget", ##10\n"Gadget", ##5\n'
        doc = odin.parse(text)
        result = odin.dumps(doc)
        doc2 = odin.parse(result)
        assert doc2.get("items[0].name").value == "Widget"
        assert doc2.get("items[0].qty").value == 10
        assert doc2.get("items[1].name").value == "Gadget"
        assert doc2.get("items[1].qty").value == 5

    def test_no_tabular_option(self):
        text = '{items[] : name, qty}\n"Widget", ##10\n'
        doc = odin.parse(text)
        result = odin.dumps(doc, DumpOptions(use_tabular=False))
        # Should not produce tabular format
        assert "{items[]" not in result or "items[0]" in result


# ─── Deep/Complex Documents ───

class TestComplexDocuments:
    """Test complex document structures."""

    def test_deep_nesting(self):
        b = OdinDocumentBuilder()
        b.set("a.b.c.d", OdinString("deep"))
        doc = b.build()
        result = odin.dumps(doc)
        doc2 = odin.parse(result)
        assert doc2.get("a.b.c.d").value == "deep"

    def test_mixed_sections_and_scalars(self):
        b = OdinDocumentBuilder()
        b.set("top", OdinString("root"))
        b.set("section.a", OdinInteger(1))
        b.set("section.b", OdinInteger(2))
        doc = b.build()
        result = odin.dumps(doc)
        assert 'top = "root"' in result

    def test_array_with_objects(self):
        b = OdinDocumentBuilder()
        b.set("items[0].name", OdinString("Widget"))
        b.set("items[0].qty", OdinInteger(10))
        b.set("items[1].name", OdinString("Gadget"))
        b.set("items[1].qty", OdinInteger(5))
        doc = b.build()
        result = odin.dumps(doc)
        doc2 = odin.parse(result)
        assert doc2.get("items[0].name").value == "Widget"
        assert doc2.get("items[1].qty").value == 5

    def test_multiple_arrays(self):
        b = OdinDocumentBuilder()
        b.set("a[0]", OdinString("x"))
        b.set("a[1]", OdinString("y"))
        b.set("b[0]", OdinString("m"))
        b.set("b[1]", OdinString("n"))
        doc = b.build()
        result = odin.dumps(doc)
        doc2 = odin.parse(result)
        assert doc2.get("a[0]").value == "x"
        assert doc2.get("b[1]").value == "n"

    def test_metadata_and_arrays(self):
        b = OdinDocumentBuilder()
        b.set_metadata("odin", OdinString("1.0.0"))
        b.set("items[0]", OdinString("first"))
        b.set("items[1]", OdinString("second"))
        doc = b.build()
        result = odin.dumps(doc)
        assert "{$}" in result
        assert 'odin = "1.0.0"' in result

    def test_relative_header_roundtrip(self):
        text = (
            "{vehicles[0]}\n"
            "vin = \"ABC123\"\n"
            "\n"
            "{.garaging}\n"
            "city = \"Dallas\"\n"
        )
        doc = odin.parse(text)
        result = odin.dumps(doc)
        doc2 = odin.parse(result)
        assert doc2.get("vehicles[0].vin").value == "ABC123"
        assert doc2.get("vehicles[0].garaging.city").value == "Dallas"
