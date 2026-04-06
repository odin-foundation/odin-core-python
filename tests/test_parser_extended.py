"""Extended parser tests for the ODIN Python SDK.

Covers all value types, headers, tabular arrays, nested paths, modifiers,
comments, multi-line strings, escape sequences, document separators,
error cases, edge cases, and type prefix variations.
"""
import pytest
from decimal import Decimal

import odin
from odin.types.values import (
    NULL, TRUE, FALSE,
    OdinNull, OdinBoolean, OdinString, OdinNumber, OdinInteger,
    OdinCurrency, OdinPercent, OdinDate, OdinTimestamp, OdinTime,
    OdinDuration, OdinReference, OdinBinary, OdinVerbExpression,
)
from odin.types.document import OdinDocument, OdinModifiers
from odin.types.errors import ParseError, ParseErrorCodes
from odin.types.options import ParseOptions


# ══════════════════════════════════════════════════════════════════════════════
# String Values
# ══════════════════════════════════════════════════════════════════════════════


class TestStringValues:
    """Quoted and bare string parsing."""

    def test_simple_quoted_string(self):
        doc = odin.parse('name = "Alice"')
        assert doc.get("name").value == "Alice"

    def test_empty_quoted_string(self):
        doc = odin.parse('name = ""')
        assert doc.get("name").value == ""

    def test_string_with_spaces(self):
        doc = odin.parse('name = "  hello world  "')
        assert doc.get("name").value == "  hello world  "

    def test_string_with_special_chars(self):
        doc = odin.parse('msg = "Hello, World! @#$%^&*()"')
        assert doc.get("msg").value == "Hello, World! @#$%^&*()"

    def test_string_with_numbers(self):
        doc = odin.parse('code = "ABC-123"')
        assert doc.get("code").value == "ABC-123"

    def test_string_unicode_literal(self):
        doc = odin.parse('greeting = "Hej"')
        assert doc.get("greeting").value == "Hej"

    def test_string_very_long(self):
        long_str = "a" * 10000
        doc = odin.parse(f'long = "{long_str}"')
        assert doc.get("long").value == long_str

    def test_string_with_semicolon(self):
        doc = odin.parse('val = "has ; semicolon"')
        assert doc.get("val").value == "has ; semicolon"


# ══════════════════════════════════════════════════════════════════════════════
# Number Values (#)
# ══════════════════════════════════════════════════════════════════════════════


class TestNumberValues:
    """Number prefix (#) parsing."""

    @pytest.mark.parametrize("input_val,expected", [
        ("#0", 0.0),
        ("#1", 1.0),
        ("#42", 42.0),
        ("#3.14", 3.14),
        ("#-1", -1.0),
        ("#-3.14", -3.14),
        ("#0.0", 0.0),
        ("#100.0", 100.0),
    ])
    def test_number_values(self, input_val, expected):
        doc = odin.parse(f"n = {input_val}")
        val = doc.get("n")
        assert isinstance(val, OdinNumber)
        assert val.value == pytest.approx(expected)

    def test_number_scientific_lowercase(self):
        doc = odin.parse("n = #1.5e10")
        assert doc.get("n").value == pytest.approx(1.5e10)

    def test_number_scientific_uppercase(self):
        doc = odin.parse("n = #1.5E10")
        assert doc.get("n").value == pytest.approx(1.5e10)

    def test_number_scientific_negative_exponent(self):
        doc = odin.parse("n = #1.5e-3")
        assert doc.get("n").value == pytest.approx(1.5e-3)

    def test_number_scientific_positive_exponent(self):
        doc = odin.parse("n = #1.5e+3")
        assert doc.get("n").value == pytest.approx(1.5e+3)

    def test_number_very_large(self):
        doc = odin.parse("n = #6.022e23")
        assert doc.get("n").value == pytest.approx(6.022e23, rel=1e-10)

    def test_number_very_small(self):
        doc = odin.parse("n = #1e-15")
        assert doc.get("n").value == pytest.approx(1e-15)

    def test_number_preserves_raw(self):
        doc = odin.parse("n = #3.141592653589793238")
        val = doc.get("n")
        assert val.raw == "3.141592653589793238"

    def test_number_zero(self):
        doc = odin.parse("n = #0")
        val = doc.get("n")
        assert isinstance(val, OdinNumber)
        assert val.value == 0.0


# ══════════════════════════════════════════════════════════════════════════════
# Integer Values (##)
# ══════════════════════════════════════════════════════════════════════════════


class TestIntegerValues:
    """Integer prefix (##) parsing."""

    @pytest.mark.parametrize("input_val,expected", [
        ("##0", 0),
        ("##1", 1),
        ("##42", 42),
        ("##-1", -1),
        ("##-100", -100),
        ("##9007199254740991", 9007199254740991),
        ("##-9007199254740991", -9007199254740991),
    ])
    def test_integer_values(self, input_val, expected):
        doc = odin.parse(f"n = {input_val}")
        val = doc.get("n")
        assert isinstance(val, OdinInteger)
        assert val.value == expected

    def test_integer_large_preserves_raw(self):
        doc = odin.parse("n = ##9007199254740992")
        val = doc.get("n")
        assert val.raw == "9007199254740992"

    def test_integer_zero(self):
        doc = odin.parse("n = ##0")
        val = doc.get("n")
        assert isinstance(val, OdinInteger)
        assert val.value == 0


# ══════════════════════════════════════════════════════════════════════════════
# Currency Values (#$)
# ══════════════════════════════════════════════════════════════════════════════


class TestCurrencyValues:
    """Currency prefix (#$) parsing."""

    @pytest.mark.parametrize("input_val,expected_amount", [
        ("#$0.00", 0.00),
        ("#$99.99", 99.99),
        ("#$-50.00", -50.00),
        ("#$0.01", 0.01),
        ("#$1000.00", 1000.00),
        ("#$-0.01", -0.01),
    ])
    def test_currency_amounts(self, input_val, expected_amount):
        doc = odin.parse(f"price = {input_val}")
        val = doc.get("price")
        assert isinstance(val, OdinCurrency)
        assert float(val.value) == pytest.approx(expected_amount)

    def test_currency_with_usd(self):
        doc = odin.parse("price = #$99.99:USD")
        val = doc.get("price")
        assert val.currency_code == "USD"

    def test_currency_with_eur(self):
        doc = odin.parse("price = #$50.00:EUR")
        val = doc.get("price")
        assert val.currency_code == "EUR"

    def test_currency_with_gbp_lowercase(self):
        doc = odin.parse("price = #$50.00:gbp")
        val = doc.get("price")
        assert val.currency_code == "GBP"

    def test_currency_decimal_places(self):
        doc = odin.parse("price = #$99.99")
        val = doc.get("price")
        assert val.decimal_places == 2

    def test_currency_three_decimal_places(self):
        doc = odin.parse("price = #$99.999")
        val = doc.get("price")
        assert val.decimal_places == 3

    def test_currency_zero(self):
        doc = odin.parse("n = #$0.00")
        assert float(doc.get("n").value) == pytest.approx(0.0)


# ══════════════════════════════════════════════════════════════════════════════
# Percent Values (#%)
# ══════════════════════════════════════════════════════════════════════════════


class TestPercentValues:
    """Percent prefix (#%) parsing."""

    @pytest.mark.parametrize("input_val,expected", [
        ("#%0.15", 0.15),
        ("#%-0.05", -0.05),
        ("#%0.0", 0.0),
        ("#%100.0", 100.0),
        ("#%1.0", 1.0),
        ("#%0.5", 0.5),
    ])
    def test_percent_values(self, input_val, expected):
        doc = odin.parse(f"rate = {input_val}")
        val = doc.get("rate")
        assert isinstance(val, OdinPercent)
        assert val.value == pytest.approx(expected)


# ══════════════════════════════════════════════════════════════════════════════
# Boolean Values
# ══════════════════════════════════════════════════════════════════════════════


class TestBooleanValues:
    """Boolean parsing with and without ? prefix."""

    @pytest.mark.parametrize("input_text,expected", [
        ("flag = true", True),
        ("flag = false", False),
        ("flag = ?true", True),
        ("flag = ?false", False),
    ])
    def test_boolean_variants(self, input_text, expected):
        doc = odin.parse(input_text)
        val = doc.get("flag")
        assert isinstance(val, OdinBoolean)
        assert val.value is expected


# ══════════════════════════════════════════════════════════════════════════════
# Null Values
# ══════════════════════════════════════════════════════════════════════════════


class TestNullValues:
    def test_null_tilde(self):
        doc = odin.parse("x = ~")
        assert isinstance(doc.get("x"), OdinNull)

    def test_null_is_singleton(self):
        doc = odin.parse("a = ~\nb = ~")
        assert doc.get("a") is doc.get("b")


# ══════════════════════════════════════════════════════════════════════════════
# Reference Values (@)
# ══════════════════════════════════════════════════════════════════════════════


class TestReferenceValues:
    """Reference prefix (@) parsing."""

    def test_simple_reference(self):
        doc = odin.parse("link = @otherField")
        val = doc.get("link")
        assert isinstance(val, OdinReference)
        assert val.path == "otherField"

    def test_dotted_reference(self):
        doc = odin.parse("link = @customer.address.city")
        assert doc.get("link").path == "customer.address.city"

    def test_array_reference(self):
        doc = odin.parse("link = @drivers[0]")
        assert doc.get("link").path == "drivers[0]"

    def test_nested_array_reference(self):
        doc = odin.parse("link = @items[0].details")
        assert doc.get("link").path == "items[0].details"


# ══════════════════════════════════════════════════════════════════════════════
# Binary Values (^)
# ══════════════════════════════════════════════════════════════════════════════


class TestBinaryValues:
    """Binary prefix (^) parsing."""

    def test_binary_hello(self):
        doc = odin.parse("data = ^SGVsbG8gV29ybGQh")
        val = doc.get("data")
        assert isinstance(val, OdinBinary)
        assert val.data == b"Hello World!"

    def test_binary_empty(self):
        doc = odin.parse("data = ^")
        val = doc.get("data")
        assert isinstance(val, OdinBinary)
        assert val.data == b""

    def test_binary_with_padding(self):
        doc = odin.parse("data = ^QQ==")
        assert doc.get("data").data == b"A"

    def test_binary_with_algorithm(self):
        doc = odin.parse("hash = ^sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        val = doc.get("hash")
        assert val.algorithm == "sha256"


# ══════════════════════════════════════════════════════════════════════════════
# Date / Timestamp / Time / Duration Values
# ══════════════════════════════════════════════════════════════════════════════


class TestTemporalValues:
    """Date, timestamp, time, and duration parsing."""

    @pytest.mark.parametrize("input_text,expected_raw", [
        ("d = 2024-01-15", "2024-01-15"),
        ("d = 2024-06-30", "2024-06-30"),
        ("d = 2024-12-31", "2024-12-31"),
        ("d = 2024-02-29", "2024-02-29"),    # leap year
        ("d = 2000-02-29", "2000-02-29"),    # century leap year
    ])
    def test_date_values(self, input_text, expected_raw):
        doc = odin.parse(input_text)
        val = doc.get("d")
        assert isinstance(val, OdinDate)
        assert val.raw == expected_raw

    def test_timestamp_utc(self):
        doc = odin.parse("ts = 2024-06-15T14:30:00Z")
        val = doc.get("ts")
        assert isinstance(val, OdinTimestamp)
        assert val.raw == "2024-06-15T14:30:00Z"

    def test_timestamp_offset_positive(self):
        doc = odin.parse("ts = 2024-06-15T14:30:00+05:30")
        assert doc.get("ts").raw == "2024-06-15T14:30:00+05:30"

    def test_timestamp_offset_negative(self):
        doc = odin.parse("ts = 2024-06-15T09:30:00-05:00")
        assert doc.get("ts").raw == "2024-06-15T09:30:00-05:00"

    def test_timestamp_with_millis(self):
        doc = odin.parse("ts = 2024-06-15T14:30:00.123Z")
        assert doc.get("ts").raw == "2024-06-15T14:30:00.123Z"

    def test_time_simple(self):
        doc = odin.parse("t = T09:30:00")
        val = doc.get("t")
        assert isinstance(val, OdinTime)
        assert val.value == "T09:30:00"

    def test_time_with_millis(self):
        doc = odin.parse("t = T09:30:00.500")
        assert doc.get("t").value == "T09:30:00.500"

    @pytest.mark.parametrize("input_text,expected_val", [
        ("dur = P6M", "P6M"),
        ("dur = P1Y", "P1Y"),
        ("dur = P2W", "P2W"),
        ("dur = PT24H", "PT24H"),
        ("dur = PT0S", "PT0S"),
        ("dur = P1Y2M3DT4H5M6S", "P1Y2M3DT4H5M6S"),
        ("dur = P5Y", "P5Y"),
    ])
    def test_duration_values(self, input_text, expected_val):
        doc = odin.parse(input_text)
        val = doc.get("dur")
        assert isinstance(val, OdinDuration)
        assert val.value == expected_val


# ══════════════════════════════════════════════════════════════════════════════
# Header Context
# ══════════════════════════════════════════════════════════════════════════════


class TestHeaderContextExtended:
    """Extended header tests: absolute, relative, reference, empty, nested."""

    def test_metadata_header(self):
        doc = odin.parse('{$}\nodin = "1.0.0"\nid = "doc1"\n\nname = "John"')
        assert doc.metadata["odin"].value == "1.0.0"
        assert doc.get("name").value == "John"

    def test_absolute_header(self):
        doc = odin.parse('{Person}\nname = "Alice"\nage = ##30')
        assert doc.get("Person.name").value == "Alice"
        assert doc.get("Person.age").value == 30

    def test_relative_header(self):
        doc = odin.parse('{vehicle}\nvin = "ABC"\n\n{.garaging}\ncity = "Dallas"')
        assert doc.get("vehicle.garaging.city").value == "Dallas"

    def test_relative_then_absolute_resets(self):
        doc = odin.parse('{A}\nx = ##1\n\n{.B}\ny = ##2\n\n{C}\nz = ##3')
        assert doc.get("A.x").value == 1
        assert doc.get("A.B.y").value == 2
        assert doc.get("C.z").value == 3

    def test_multiple_relative_headers(self):
        doc = odin.parse('{policy}\nid = "POL"\n\n{.insured}\nname = "John"\n\n{.address}\ncity = "Austin"')
        assert doc.get("policy.insured.name").value == "John"
        assert doc.get("policy.address.city").value == "Austin"

    def test_empty_header_resets(self):
        doc = odin.parse('{person}\nname = "John"\n\n{}\ntop = "root"')
        assert doc.get("person.name").value == "John"
        assert doc.get("top").value == "root"

    def test_header_with_array_index(self):
        doc = odin.parse('{items[0]}\nname = "Widget"\n{items[1]}\nname = "Gadget"')
        assert doc.get("items[0].name").value == "Widget"
        assert doc.get("items[1].name").value == "Gadget"

    def test_deep_dotted_header(self):
        doc = odin.parse('{A.B.C.D.E}\nval = ##1')
        assert doc.get("A.B.C.D.E.val").value == 1

    def test_eight_level_header(self):
        doc = odin.parse('{A.B.C.D.E.F.G.H}\nval = ##42')
        assert doc.get("A.B.C.D.E.F.G.H.val").value == 42

    def test_nested_sections_with_mixed_content(self):
        doc = odin.parse("{L1}\na = ##1\n{L1.L2}\nb = ##2\n{L1.L2.L3}\nc = ##3")
        assert doc.get("L1.a").value == 1
        assert doc.get("L1.L2.b").value == 2
        assert doc.get("L1.L2.L3.c").value == 3

    def test_deep_then_shallow(self):
        doc = odin.parse("{A.B.C.D.E}\ndeep = ##1\n{F}\nshallow = ##2")
        assert doc.get("A.B.C.D.E.deep").value == 1
        assert doc.get("F.shallow").value == 2

    def test_many_sections(self):
        lines = []
        for i in range(20):
            lines.append(f"{{S{i}}}")
            lines.append(f"field = ##{i}")
        doc = odin.parse("\n".join(lines))
        assert doc.get("S0.field").value == 0
        assert doc.get("S19.field").value == 19

    def test_case_sensitive_headers(self):
        doc = odin.parse('{Person}\nname = "John"\n{person}\nname = "Jane"')
        assert doc.get("Person.name").value == "John"
        assert doc.get("person.name").value == "Jane"


# ══════════════════════════════════════════════════════════════════════════════
# Tabular Arrays
# ══════════════════════════════════════════════════════════════════════════════


class TestTabularArrays:
    """Tabular array {items[] : col1, col2} parsing."""

    def test_basic_tabular(self):
        doc = odin.parse('{items[] : name, qty, price}\n"Widget", ##10, #$5.99\n"Gadget", ##5, #$12.50')
        assert doc.get("items[0].name").value == "Widget"
        assert doc.get("items[0].qty").value == 10
        assert float(doc.get("items[0].price").value) == pytest.approx(5.99)
        assert doc.get("items[1].name").value == "Gadget"

    def test_tabular_with_null(self):
        doc = odin.parse('{items[] : name, notes}\n"Widget", "ok"\n"Gadget", ~')
        assert isinstance(doc.get("items[1].notes"), OdinNull)

    def test_tabular_with_empty_string(self):
        doc = odin.parse('{items[] : name, notes}\n"Widget", "ok"\n"Gadget", ""')
        assert doc.get("items[1].notes").value == ""

    def test_tabular_primitive_array(self):
        doc = odin.parse('{tags[] : ~}\n"urgent"\n"important"')
        assert doc.get("tags[0]").value == "urgent"
        assert doc.get("tags[1]").value == "important"

    def test_tabular_dotted_columns(self):
        doc = odin.parse('{items[] : product.name, product.sku}\n"Widget", "WGT-001"')
        assert doc.get("items[0].product.name").value == "Widget"
        assert doc.get("items[0].product.sku").value == "WGT-001"

    def test_tabular_with_boolean(self):
        doc = odin.parse('{data[] : label, active}\n"Alpha", ?true\n"Beta", ?false')
        assert doc.get("data[0].active").value is True
        assert doc.get("data[1].active").value is False

    def test_tabular_with_references(self):
        doc = odin.parse('{a[] : driver, vehicle}\n@drivers[0], @vehicles[0]')
        assert doc.get("a[0].driver").path == "drivers[0]"
        assert doc.get("a[0].vehicle").path == "vehicles[0]"

    def test_tabular_many_rows(self):
        rows = []
        for i in range(50):
            rows.append(f'"item_{i}", ##{i}')
        text = "{items[] : name, count}\n" + "\n".join(rows)
        doc = odin.parse(text)
        assert doc.get("items[0].name").value == "item_0"
        assert doc.get("items[49].name").value == "item_49"
        assert doc.get("items[49].count").value == 49


# ══════════════════════════════════════════════════════════════════════════════
# Nested Paths
# ══════════════════════════════════════════════════════════════════════════════


class TestNestedPaths:
    """Dotted path and array index parsing."""

    def test_two_level_path(self):
        doc = odin.parse('a.b = "val"')
        assert doc.get("a.b").value == "val"

    def test_three_level_path(self):
        doc = odin.parse('a.b.c = "val"')
        assert doc.get("a.b.c").value == "val"

    def test_deep_dotted_path(self):
        doc = odin.parse("a.b.c.d.e.f.g.h = ##99")
        assert doc.get("a.b.c.d.e.f.g.h").value == 99

    def test_array_index_zero(self):
        doc = odin.parse('items[0] = "first"')
        assert doc.get("items[0]").value == "first"

    def test_array_index_path(self):
        doc = odin.parse('items[0].name = "Alice"')
        assert doc.get("items[0].name").value == "Alice"

    def test_nested_arrays(self):
        doc = odin.parse('a[0].b[0].c = "deep"')
        assert doc.get("a[0].b[0].c").value == "deep"

    def test_multiple_array_elements(self):
        doc = odin.parse('items[0].name = "A"\nitems[1].name = "B"\nitems[2].name = "C"')
        assert doc.get("items[0].name").value == "A"
        assert doc.get("items[1].name").value == "B"
        assert doc.get("items[2].name").value == "C"


# ══════════════════════════════════════════════════════════════════════════════
# Modifiers (!, *, -)
# ══════════════════════════════════════════════════════════════════════════════


class TestModifiersExtended:
    """Extended modifier tests."""

    @pytest.mark.parametrize("input_text,field,req,conf,depr", [
        ('f = !"value"', "f", True, False, False),
        ('f = *"value"', "f", False, True, False),
        ('f = -"value"', "f", False, False, True),
        ('f = !*"value"', "f", True, True, False),
        ('f = !-"value"', "f", True, False, True),
        ('f = *-"value"', "f", False, True, True),
        ('f = !*-"value"', "f", True, True, True),
        ('f = -*!"value"', "f", True, True, True),
    ])
    def test_modifier_combinations(self, input_text, field, req, conf, depr):
        doc = odin.parse(input_text)
        mods = doc.modifiers[field]
        assert mods.required is req
        assert mods.confidential is conf
        assert mods.deprecated is depr

    def test_modifier_on_integer(self):
        doc = odin.parse("count = !##42")
        assert doc.get("count").value == 42
        assert doc.modifiers["count"].required is True

    def test_modifier_on_number(self):
        doc = odin.parse("rate = -#3.14")
        assert isinstance(doc.get("rate"), OdinNumber)
        assert doc.modifiers["rate"].deprecated is True

    def test_modifier_on_currency(self):
        doc = odin.parse("price = !#$99.99")
        assert isinstance(doc.get("price"), OdinCurrency)
        assert doc.modifiers["price"].required is True

    def test_modifier_on_percent(self):
        doc = odin.parse("rate = !#%0.15")
        assert isinstance(doc.get("rate"), OdinPercent)
        assert doc.modifiers["rate"].required is True

    def test_modifier_on_boolean(self):
        doc = odin.parse("active = !true")
        assert doc.get("active").value is True
        assert doc.modifiers["active"].required is True

    def test_modifier_on_null(self):
        doc = odin.parse("deleted = *~")
        assert isinstance(doc.get("deleted"), OdinNull)
        assert doc.modifiers["deleted"].confidential is True

    def test_modifier_on_reference(self):
        doc = odin.parse("link = *@other.path")
        assert isinstance(doc.get("link"), OdinReference)
        assert doc.modifiers["link"].confidential is True

    def test_modifier_on_binary(self):
        doc = odin.parse("cert = !^SGVsbG8=")
        assert isinstance(doc.get("cert"), OdinBinary)
        assert doc.modifiers["cert"].required is True

    def test_modifier_on_date(self):
        doc = odin.parse("oldDate = -2024-01-15")
        assert isinstance(doc.get("oldDate"), OdinDate)
        assert doc.modifiers["oldDate"].deprecated is True

    def test_modifier_on_nested_path(self):
        doc = odin.parse('person.ssn = *"987-65-4321"')
        assert doc.modifiers["person.ssn"].confidential is True

    def test_modifier_on_array_element(self):
        doc = odin.parse('items[0].secret = *"hidden"')
        assert doc.modifiers["items[0].secret"].confidential is True

    def test_modifier_in_section(self):
        doc = odin.parse('{Secure}\npassword = *"secret"\nid = !##42')
        assert doc.modifiers["Secure.password"].confidential is True
        assert doc.modifiers["Secure.id"].required is True


# ══════════════════════════════════════════════════════════════════════════════
# Comments
# ══════════════════════════════════════════════════════════════════════════════


class TestComments:
    """Comment handling."""

    def test_full_line_comment(self):
        doc = odin.parse('; this is a comment\nname = "John"')
        assert doc.get("name").value == "John"
        assert len(doc) == 1

    def test_inline_comment(self):
        doc = odin.parse('name = "John" ; inline comment')
        assert doc.get("name").value == "John"

    def test_multiple_comments(self):
        doc = odin.parse('; first\n; second\n; third\nname = "John"')
        assert len(doc) == 1

    def test_comment_only_document(self):
        doc = odin.parse("; just comments\n; nothing else")
        assert len(doc) == 0

    def test_comment_between_assignments(self):
        doc = odin.parse('a = ##1\n; middle\nb = ##2')
        assert doc.get("a").value == 1
        assert doc.get("b").value == 2


# ══════════════════════════════════════════════════════════════════════════════
# Multi-line Strings
# ══════════════════════════════════════════════════════════════════════════════


class TestMultiLineStrings:
    """Triple-quoted multi-line string parsing."""

    def test_simple_multiline(self):
        doc = odin.parse('text = """hello\nworld"""')
        assert doc.get("text").value == "hello\nworld"

    def test_multiline_preserves_newlines(self):
        doc = odin.parse('text = """line1\nline2\nline3"""')
        assert doc.get("text").value == "line1\nline2\nline3"

    def test_multiline_with_quotes(self):
        doc = odin.parse('text = """say "hello" to the "world" """')
        assert '"hello"' in doc.get("text").value

    def test_multiline_empty(self):
        doc = odin.parse('text = """"""')
        assert doc.get("text").value == ""


# ══════════════════════════════════════════════════════════════════════════════
# Escape Sequences
# ══════════════════════════════════════════════════════════════════════════════


class TestEscapeSequences:
    """All supported escape sequences."""

    @pytest.mark.parametrize("input_esc,expected_char", [
        (r'"\n"', "\n"),
        (r'"\t"', "\t"),
        (r'"\r"', "\r"),
        (r'"\\"', "\\"),
        (r'"\""', '"'),
        (r'"\0"', "\0"),
    ])
    def test_single_escape(self, input_esc, expected_char):
        doc = odin.parse(f"val = {input_esc}")
        assert doc.get("val").value == expected_char

    def test_unicode_escape_4_digit(self):
        doc = odin.parse('val = "\\u0048ello"')
        assert doc.get("val").value == "Hello"

    def test_unicode_escape_8_digit(self):
        doc = odin.parse('val = "\\U0001F600"')
        assert doc.get("val").value == "\U0001F600"

    def test_multiple_escapes(self):
        doc = odin.parse('val = "a\\nb\\tc"')
        assert doc.get("val").value == "a\nb\tc"

    def test_escaped_backslash_in_path(self):
        doc = odin.parse('val = "C:\\\\Users\\\\admin"')
        assert doc.get("val").value == "C:\\Users\\admin"

    def test_escaped_quotes(self):
        doc = odin.parse('val = "say \\"hello\\""')
        assert doc.get("val").value == 'say "hello"'


# ══════════════════════════════════════════════════════════════════════════════
# Document Separators
# ══════════════════════════════════════════════════════════════════════════════


class TestDocumentSeparators:
    """Document separator (---) handling."""

    def test_single_separator(self):
        text = '{$}\nodin = "1.0.0"\nid = "d1"\n\nname = "John"\n\n---\n\n{$}\nodin = "1.0.0"\nid = "d2"\n\nname = "Jane"'
        doc = odin.parse(text)
        # First document returned
        assert doc.get("name").value == "John"

    def test_separator_preserves_first_doc(self):
        doc = odin.parse('a = ##1\n---\nb = ##2')
        assert doc.get("a").value == 1


# ══════════════════════════════════════════════════════════════════════════════
# Error Cases
# ══════════════════════════════════════════════════════════════════════════════


class TestParseErrorsExtended:
    """Extended error case testing."""

    def test_duplicate_path_p007(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('name = "John"\nname = "Jane"')
        assert exc_info.value.code == "P007"

    def test_duplicate_path_nested_p007(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('a.b = "first"\na.b = "second"')
        assert exc_info.value.code == "P007"

    def test_unterminated_string_p004(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('name = "John')
        assert exc_info.value.code == "P004"

    def test_unterminated_string_eol_p004(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('name = "John\nnext = ##1')
        assert exc_info.value.code == "P004"

    def test_invalid_escape_p005(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('name = "hello\\z world"')
        assert exc_info.value.code == "P005"

    def test_invalid_header_missing_close_p008(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('{Section\nname = "test"')
        assert exc_info.value.code == "P008"

    def test_non_contiguous_array_p013(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('items[0].name = "First"\nitems[5].name = "Fifth"')
        assert exc_info.value.code == "P013"

    def test_non_contiguous_array_skip_one_p013(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('items[0] = "a"\nitems[2] = "c"')
        assert exc_info.value.code == "P013"

    def test_negative_array_index_p003(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('items[-1].name = "Invalid"')
        assert exc_info.value.code == "P003"

    def test_array_index_too_large_p015(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('items[999999999].name = "too big"')
        assert exc_info.value.code == "P015"

    def test_max_depth_exceeded_p010(self):
        path = ".".join(f"s{i}" for i in range(200))
        with pytest.raises(ParseError) as exc_info:
            odin.parse(f'{path} = "deep"')
        assert exc_info.value.code == "P010"

    def test_invalid_type_prefix_p006(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse("value = ###42")
        assert exc_info.value.code == "P006"

    def test_empty_number_p006(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse("n = #")
        assert exc_info.value.code == "P006"

    def test_double_negative_p006(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse("n = #--5")
        assert exc_info.value.code == "P006"

    def test_bare_string_p002(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse("name = bare value")
        assert exc_info.value.code == "P002"

    def test_invalid_base64_p001(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse("data = ^SGVs!G8=")
        assert exc_info.value.code == "P001"

    def test_invalid_directive_p001(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('@invalid ./file.odin\nname = "test"')
        assert exc_info.value.code == "P001"

    def test_import_missing_path_p009(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('@import\nname = "test"')
        assert exc_info.value.code == "P009"

    def test_schema_missing_url_p009(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('@schema\nname = "test"')
        assert exc_info.value.code == "P009"

    def test_if_missing_condition_p009(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('@if\nname = "test"')
        assert exc_info.value.code == "P009"

    def test_import_trailing_as_p009(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('@import ./file.odin as\nname = "test"')
        assert exc_info.value.code == "P009"

    def test_unexpected_char_p001(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('@ = "test"')
        assert exc_info.value.code == "P001"

    def test_not_leap_year(self):
        with pytest.raises(ParseError):
            odin.parse("date = 2023-02-29")

    def test_century_not_leap(self):
        with pytest.raises(ParseError):
            odin.parse("date = 1900-02-29")

    def test_invalid_base64_padding(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse("data = ^SGVs=bG8")
        assert exc_info.value.code == "P001"


# ══════════════════════════════════════════════════════════════════════════════
# Edge Cases
# ══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_document(self):
        doc = odin.parse("")
        assert len(doc) == 0

    def test_whitespace_only(self):
        doc = odin.parse("   \n\n   \n")
        assert len(doc) == 0

    def test_single_assignment(self):
        doc = odin.parse('name = "val"')
        assert len(doc) == 1

    def test_paths_preserve_insertion_order(self):
        doc = odin.parse('z = "last"\na = "first"\nm = "middle"')
        assert doc.paths() == ["z", "a", "m"]

    def test_utf8_bom(self):
        doc = odin.parse('\ufeffname = "John"')
        assert doc.get("name").value == "John"

    def test_crlf_line_endings(self):
        doc = odin.parse('name = "John"\r\nage = ##30')
        assert doc.get("name").value == "John"
        assert doc.get("age").value == 30

    def test_mixed_line_endings(self):
        doc = odin.parse('a = "one"\r\nb = "two"\nc = "three"')
        assert len(doc) == 3

    def test_bom_with_crlf(self):
        doc = odin.parse('\ufeffname = "John"\r\nage = ##30\r\n')
        assert doc.get("name").value == "John"

    def test_bytes_input(self):
        doc = odin.parse(b'name = "John"')
        assert doc.get("name").value == "John"

    def test_100_assignments(self):
        lines = [f'field{i} = ##{i}' for i in range(100)]
        doc = odin.parse("\n".join(lines))
        assert len(doc) == 100
        assert doc.get("field0").value == 0
        assert doc.get("field99").value == 99

    def test_500_assignments(self):
        lines = [f'f{i} = "value_{i}"' for i in range(500)]
        doc = odin.parse("\n".join(lines))
        assert len(doc) == 500

    def test_large_array(self):
        lines = [f'items[{i}] = "item_{i}"' for i in range(100)]
        doc = odin.parse("\n".join(lines))
        assert doc.get("items[0]").value == "item_0"
        assert doc.get("items[99]").value == "item_99"

    def test_sections_with_arrays(self):
        doc = odin.parse('{S}\nitems[0] = "a"\nitems[1] = "b"')
        assert doc.get("S.items[0]").value == "a"
        assert doc.get("S.items[1]").value == "b"

    def test_multiple_sections_large_doc(self):
        lines = []
        for s in range(20):
            lines.append(f"{{Section{s}}}")
            for f in range(10):
                lines.append(f"field{f} = ##{s * 10 + f}")
        doc = odin.parse("\n".join(lines))
        assert len(doc) == 200

    def test_root_field_before_section(self):
        doc = odin.parse('top = ##1\n{S}\nbottom = ##2')
        assert doc.get("top").value == 1
        assert doc.get("S.bottom").value == 2

    def test_section_with_comments(self):
        doc = odin.parse('; comment\n{Section}\n; field comment\nf = ##1')
        assert doc.get("Section.f").value == 1

    def test_field_named_true(self):
        doc = odin.parse('true = "some value"')
        assert doc.get("true").value == "some value"

    def test_field_named_false(self):
        doc = odin.parse("false = ##42")
        assert doc.get("false").value == 42

    def test_field_named_null(self):
        doc = odin.parse('null = "not null"')
        assert doc.get("null").value == "not null"

    def test_different_case_fields_are_distinct(self):
        doc = odin.parse('Name = "Upper"\nname = "lower"')
        assert doc.get("Name").value == "Upper"
        assert doc.get("name").value == "lower"


# ══════════════════════════════════════════════════════════════════════════════
# Extension Paths
# ══════════════════════════════════════════════════════════════════════════════


class TestExtensionPathsExtended:
    """Extension path (&) parsing."""

    def test_simple_extension(self):
        doc = odin.parse('&com.acme.tier = "A"')
        val = doc.get("&com.acme.tier")
        assert isinstance(val, OdinString)
        assert val.value == "A"

    def test_extension_with_modifier(self):
        doc = odin.parse('&com.acme.secret = *"classified"')
        assert doc.modifiers["&com.acme.secret"].confidential is True

    def test_extension_with_regular_fields(self):
        doc = odin.parse('name = "Policy"\n&com.acme.tier = "Gold"')
        assert doc.get("name").value == "Policy"
        assert doc.get("&com.acme.tier").value == "Gold"


# ══════════════════════════════════════════════════════════════════════════════
# Directives
# ══════════════════════════════════════════════════════════════════════════════


class TestDirectivesExtended:
    """Directive (@import, @schema, @if) parsing."""

    def test_import_directive(self):
        doc = odin.parse('@import ./file.odin\n\nname = "test"')
        assert doc.get("name").value == "test"

    def test_import_with_alias(self):
        doc = odin.parse('@import ./file.odin as f\n\nname = "test"')
        assert doc.get("name").value == "test"

    def test_schema_directive(self):
        doc = odin.parse('@schema https://example.com/schema.odin\n\nname = "test"')
        assert doc.get("name").value == "test"


# ══════════════════════════════════════════════════════════════════════════════
# Verb Expressions
# ══════════════════════════════════════════════════════════════════════════════


class TestVerbExpressions:
    """Verb expression (%verb) parsing."""

    def test_simple_verb(self):
        doc = odin.parse("result = %upper @name")
        val = doc.get("result")
        assert isinstance(val, OdinVerbExpression)

    def test_verb_multi_arg(self):
        doc = odin.parse('fullName = %concat @firstName " " @lastName')
        val = doc.get("fullName")
        assert isinstance(val, OdinVerbExpression)


# ══════════════════════════════════════════════════════════════════════════════
# Security Limits
# ══════════════════════════════════════════════════════════════════════════════


class TestSecurityLimitsExtended:
    """Security boundary tests."""

    def test_deep_nesting_200(self):
        segments = [f"{chr(97 + i % 26)}{chr(97 + (i // 26) % 26)}" for i in range(200)]
        path = ".".join(segments)
        with pytest.raises(ParseError) as exc_info:
            odin.parse(f'{path} = "too deep"')
        assert exc_info.value.code == "P010"

    def test_array_index_bomb(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('items[2147483647].name = "bomb"')
        assert exc_info.value.code == "P015"

    def test_negative_large_index(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('items[-2147483648].name = "bomb"')
        assert exc_info.value.code == "P003"

    def test_chained_large_indices(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('a[999999].b[999999].c[999999] = "bomb"')
        assert exc_info.value.code == "P015"

    def test_max_document_size(self):
        opts = ParseOptions(max_document_size=100)
        with pytest.raises(ParseError) as exc_info:
            odin.parse("x" * 200, options=opts)
        assert exc_info.value.code == "P011"

    def test_custom_max_depth(self):
        opts = ParseOptions(max_nesting_depth=3)
        with pytest.raises(ParseError) as exc_info:
            odin.parse('a.b.c.d.e = "too deep"', options=opts)
        assert exc_info.value.code == "P010"


# ══════════════════════════════════════════════════════════════════════════════
# Numeric Precision
# ══════════════════════════════════════════════════════════════════════════════


class TestNumericPrecisionExtended:
    """Numeric precision and edge cases."""

    def test_integer_max_safe(self):
        doc = odin.parse("n = ##9007199254740991")
        assert doc.get("n").value == 9007199254740991

    def test_integer_min_safe(self):
        doc = odin.parse("n = ##-9007199254740991")
        assert doc.get("n").value == -9007199254740991

    def test_number_high_precision_raw(self):
        doc = odin.parse("n = #3.141592653589793238")
        assert doc.get("n").raw == "3.141592653589793238"

    def test_currency_one_cent(self):
        doc = odin.parse("n = #$0.01")
        assert float(doc.get("n").value) == pytest.approx(0.01)

    def test_currency_negative_precise(self):
        doc = odin.parse("n = #$-0.01")
        assert float(doc.get("n").value) == pytest.approx(-0.01)

    def test_number_negative_zero(self):
        doc = odin.parse("n = #-0")
        val = doc.get("n")
        assert isinstance(val, OdinNumber)

    def test_integer_positive_one(self):
        doc = odin.parse("n = ##1")
        assert doc.get("n").value == 1

    def test_number_leading_zero_decimal(self):
        doc = odin.parse("n = #0.5")
        assert doc.get("n").value == pytest.approx(0.5)


# ══════════════════════════════════════════════════════════════════════════════
# Temporal Edge Cases
# ══════════════════════════════════════════════════════════════════════════════


class TestTemporalEdgeCasesExtended:
    """Temporal value edge cases."""

    def test_leap_year_feb_29(self):
        doc = odin.parse("d = 2024-02-29")
        assert isinstance(doc.get("d"), OdinDate)

    def test_century_leap_year(self):
        doc = odin.parse("d = 2000-02-29")
        assert isinstance(doc.get("d"), OdinDate)

    def test_not_leap_year_error(self):
        with pytest.raises(ParseError):
            odin.parse("d = 2023-02-29")

    def test_century_not_leap_error(self):
        with pytest.raises(ParseError):
            odin.parse("d = 1900-02-29")

    def test_month_boundaries(self):
        doc = odin.parse("jan = 2024-01-31\nfeb = 2024-02-29\napr = 2024-04-30")
        assert doc.get("jan").raw == "2024-01-31"
        assert doc.get("feb").raw == "2024-02-29"
        assert doc.get("apr").raw == "2024-04-30"

    def test_timestamp_positive_offset(self):
        doc = odin.parse("ts = 2024-06-15T14:30:00+05:30")
        assert doc.get("ts").raw == "2024-06-15T14:30:00+05:30"

    def test_timestamp_negative_offset(self):
        doc = odin.parse("ts = 2024-06-15T09:30:00-05:00")
        assert doc.get("ts").raw == "2024-06-15T09:30:00-05:00"

    def test_time_midnight(self):
        doc = odin.parse("t = T00:00:00")
        assert doc.get("t").value == "T00:00:00"

    def test_time_end_of_day(self):
        doc = odin.parse("t = T23:59:59")
        assert doc.get("t").value == "T23:59:59"


# ══════════════════════════════════════════════════════════════════════════════
# Metadata
# ══════════════════════════════════════════════════════════════════════════════


class TestMetadataExtended:
    """Metadata header parsing."""

    def test_metadata_odin_version(self):
        doc = odin.parse('{$}\nodin = "1.0.0"\n\nname = "John"')
        assert doc.metadata["odin"].value == "1.0.0"

    def test_metadata_multiple_keys(self):
        doc = odin.parse('{$}\nodin = "1.0.0"\nid = "doc1"\nauthor = "admin"\n\nname = "John"')
        assert doc.metadata["odin"].value == "1.0.0"
        assert doc.metadata["id"].value == "doc1"
        assert doc.metadata["author"].value == "admin"

    def test_metadata_accessible_via_dollar_prefix(self):
        doc = odin.parse('{$}\nodin = "1.0.0"\n\nname = "John"')
        val = doc.get("$.odin")
        assert val is not None
        assert val.value == "1.0.0"

    def test_metadata_does_not_mix_with_data(self):
        doc = odin.parse('{$}\nodin = "1.0.0"\n\nname = "John"')
        assert doc.get("name").value == "John"
        # odin should not be in non-metadata paths (except $ prefixed)
        non_meta_paths = [p for p in doc.paths() if not p.startswith("$")]
        assert "odin" not in non_meta_paths


# ══════════════════════════════════════════════════════════════════════════════
# Mixed Type Documents
# ══════════════════════════════════════════════════════════════════════════════


class TestMixedDocuments:
    """Documents with many different value types together."""

    def test_all_types_in_one_doc(self):
        text = "\n".join([
            'str = "hello"',
            "num = #3.14",
            "int = ##42",
            "cur = #$99.99",
            "pct = #%0.15",
            "bool = true",
            "null = ~",
            "ref = @other",
            "bin = ^SGVsbG8=",
            "date = 2024-06-15",
            "ts = 2024-06-15T14:30:00Z",
            "time = T09:30:00",
            "dur = P6M",
        ])
        doc = odin.parse(text)
        assert isinstance(doc.get("str"), OdinString)
        assert isinstance(doc.get("num"), OdinNumber)
        assert isinstance(doc.get("int"), OdinInteger)
        assert isinstance(doc.get("cur"), OdinCurrency)
        assert isinstance(doc.get("pct"), OdinPercent)
        assert isinstance(doc.get("bool"), OdinBoolean)
        assert isinstance(doc.get("null"), OdinNull)
        assert isinstance(doc.get("ref"), OdinReference)
        assert isinstance(doc.get("bin"), OdinBinary)
        assert isinstance(doc.get("date"), OdinDate)
        assert isinstance(doc.get("ts"), OdinTimestamp)
        assert isinstance(doc.get("time"), OdinTime)
        assert isinstance(doc.get("dur"), OdinDuration)

    def test_sections_with_mixed_types(self):
        text = "\n".join([
            "{person}",
            'name = "Alice"',
            "age = ##30",
            "active = true",
            "{address}",
            'city = "Austin"',
            'state = "TX"',
        ])
        doc = odin.parse(text)
        assert doc.get("person.name").value == "Alice"
        assert doc.get("person.age").value == 30
        assert doc.get("person.active").value is True
        assert doc.get("address.city").value == "Austin"

    def test_complex_insurance_document(self):
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
        assert doc.get("policy.number").value == "PAP-2024-001"
        assert isinstance(doc.get("policy.effective"), OdinDate)
        assert isinstance(doc.get("policy.premium"), OdinCurrency)
        assert doc.modifiers["policy.premium"].required is True
        assert doc.get("vehicles[0].year").value == 2024
        assert doc.modifiers["drivers[0].license"].confidential is True
