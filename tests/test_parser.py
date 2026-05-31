"""Unit tests for the ODIN parser."""
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


# ── Basic Parsing ─────────────────────────────────────────────────────────


class TestBasicParsing:
    def test_empty_input(self):
        doc = odin.parse("")
        assert len(doc) == 0

    def test_whitespace_only(self):
        doc = odin.parse("  \n\n  ")
        assert len(doc) == 0

    def test_comment_only(self):
        doc = odin.parse("; just a comment\n; another")
        assert len(doc) == 0

    def test_quoted_string(self):
        doc = odin.parse('name = "John"')
        val = doc.get("name")
        assert isinstance(val, OdinString)
        assert val.value == "John"

    def test_empty_string(self):
        doc = odin.parse('empty = ""')
        val = doc.get("empty")
        assert isinstance(val, OdinString)
        assert val.value == ""

    def test_multiple_assignments(self):
        doc = odin.parse('first = "John"\nlast = "Smith"')
        assert doc.get("first").value == "John"
        assert doc.get("last").value == "Smith"

    def test_nested_path(self):
        doc = odin.parse('customer.name.first = "John"')
        val = doc.get("customer.name.first")
        assert isinstance(val, OdinString)
        assert val.value == "John"

    def test_assignment_with_comment(self):
        doc = odin.parse('name = "John" ; inline comment')
        assert doc.get("name").value == "John"

    def test_full_line_comment(self):
        doc = odin.parse('; comment\nname = "John"\n; another')
        assert doc.get("name").value == "John"
        assert len(doc) == 1

    def test_paths_in_order(self):
        doc = odin.parse('z = "last"\na = "first"\nm = "middle"')
        assert doc.paths() == ["z", "a", "m"]

    def test_whitespace_preserved_in_quotes(self):
        doc = odin.parse('name = "  John  "')
        assert doc.get("name").value == "  John  "


# ── Value Types ──────────────────────────────────────────────────────────


class TestValueTypes:
    def test_null(self):
        doc = odin.parse("value = ~")
        assert isinstance(doc.get("value"), OdinNull)

    def test_boolean_true_prefixed(self):
        doc = odin.parse("flag = ?true")
        val = doc.get("flag")
        assert isinstance(val, OdinBoolean)
        assert val.value is True

    def test_boolean_false_prefixed(self):
        doc = odin.parse("flag = ?false")
        assert doc.get("flag").value is False

    def test_boolean_true_bare(self):
        doc = odin.parse("flag = true")
        assert isinstance(doc.get("flag"), OdinBoolean)
        assert doc.get("flag").value is True

    def test_boolean_false_bare(self):
        doc = odin.parse("flag = false")
        assert doc.get("flag").value is False

    def test_number_integer_form(self):
        doc = odin.parse("count = #42")
        val = doc.get("count")
        assert isinstance(val, OdinNumber)
        assert val.value == 42.0

    def test_number_decimal(self):
        doc = odin.parse("rate = #3.14159")
        val = doc.get("rate")
        assert isinstance(val, OdinNumber)
        assert abs(val.value - 3.14159) < 1e-10

    def test_number_negative(self):
        doc = odin.parse("temp = #-273.15")
        val = doc.get("temp")
        assert isinstance(val, OdinNumber)
        assert abs(val.value - (-273.15)) < 1e-10

    def test_number_exponent(self):
        doc = odin.parse("big = #6.022e23")
        val = doc.get("big")
        assert isinstance(val, OdinNumber)
        assert abs(val.value - 6.022e23) < 1e15

    def test_integer(self):
        doc = odin.parse("count = ##42")
        val = doc.get("count")
        assert isinstance(val, OdinInteger)
        assert val.value == 42

    def test_integer_negative(self):
        doc = odin.parse("offset = ##-100")
        val = doc.get("offset")
        assert isinstance(val, OdinInteger)
        assert val.value == -100

    def test_integer_zero(self):
        doc = odin.parse("n = ##0")
        assert doc.get("n").value == 0

    def test_integer_large(self):
        doc = odin.parse("n = ##9007199254740991")
        val = doc.get("n")
        assert isinstance(val, OdinInteger)
        assert val.value == 9007199254740991

    def test_currency_simple(self):
        doc = odin.parse("price = #$99.99")
        val = doc.get("price")
        assert isinstance(val, OdinCurrency)
        assert float(val.value) == pytest.approx(99.99)
        assert val.decimal_places == 2

    def test_currency_with_code(self):
        doc = odin.parse("price = #$99.99:USD")
        val = doc.get("price")
        assert isinstance(val, OdinCurrency)
        assert val.currency_code == "USD"

    def test_currency_lowercase_code(self):
        doc = odin.parse("price = #$50.00:gbp")
        assert doc.get("price").currency_code == "GBP"

    def test_currency_negative(self):
        doc = odin.parse("refund = #$-50.00")
        val = doc.get("refund")
        assert float(val.value) == pytest.approx(-50.00)

    def test_percent(self):
        doc = odin.parse("rate = #%0.15")
        val = doc.get("rate")
        assert isinstance(val, OdinPercent)
        assert abs(val.value - 0.15) < 1e-10

    def test_percent_negative(self):
        doc = odin.parse("loss = #%-0.05")
        val = doc.get("loss")
        assert abs(val.value - (-0.05)) < 1e-10

    def test_date(self):
        doc = odin.parse("effective = 2024-06-15")
        val = doc.get("effective")
        assert isinstance(val, OdinDate)
        assert val.raw == "2024-06-15"

    def test_timestamp_utc(self):
        doc = odin.parse("created = 2025-12-06T14:30:00Z")
        val = doc.get("created")
        assert isinstance(val, OdinTimestamp)
        assert val.raw == "2025-12-06T14:30:00Z"

    def test_timestamp_offset(self):
        doc = odin.parse("created = 2025-12-06T09:30:00-05:00")
        val = doc.get("created")
        assert val.raw == "2025-12-06T09:30:00-05:00"

    def test_time(self):
        doc = odin.parse("start = T09:30:00")
        val = doc.get("start")
        assert isinstance(val, OdinTime)
        assert val.value == "T09:30:00"

    def test_time_with_millis(self):
        doc = odin.parse("start = T09:30:00.500")
        assert doc.get("start").value == "T09:30:00.500"

    def test_duration(self):
        doc = odin.parse("term = P6M")
        val = doc.get("term")
        assert isinstance(val, OdinDuration)
        assert val.value == "P6M"

    def test_duration_complex(self):
        doc = odin.parse("period = P1Y2M3DT4H5M6S")
        assert doc.get("period").value == "P1Y2M3DT4H5M6S"

    def test_reference(self):
        doc = odin.parse("primary = @drivers[0]")
        val = doc.get("primary")
        assert isinstance(val, OdinReference)
        assert val.path == "drivers[0]"

    def test_reference_nested(self):
        doc = odin.parse("billing = @customer.address.billing")
        val = doc.get("billing")
        assert val.path == "customer.address.billing"

    def test_binary(self):
        doc = odin.parse("data = ^SGVsbG8gV29ybGQh")
        val = doc.get("data")
        assert isinstance(val, OdinBinary)
        assert val.data == b"Hello World!"

    def test_binary_with_algorithm(self):
        doc = odin.parse("hash = ^sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        val = doc.get("hash")
        assert isinstance(val, OdinBinary)
        assert val.algorithm == "sha256"

    def test_binary_empty(self):
        doc = odin.parse("data = ^")
        val = doc.get("data")
        assert isinstance(val, OdinBinary)
        assert val.data == b""

    def test_verb_simple(self):
        doc = odin.parse("result = %upper @name")
        val = doc.get("result")
        assert isinstance(val, OdinVerbExpression)

    def test_verb_multi_arg(self):
        doc = odin.parse('fullName = %concat @firstName " " @lastName')
        val = doc.get("fullName")
        assert isinstance(val, OdinVerbExpression)


# ── Header Context ───────────────────────────────────────────────────────


class TestHeaderContext:
    def test_simple_header(self):
        doc = odin.parse('{person}\nname = "John"\nage = ##30')
        assert doc.get("person.name").value == "John"
        assert doc.get("person.age").value == 30

    def test_two_headers(self):
        doc = odin.parse('{person}\nname = "John"\n\n{address}\ncity = "Austin"')
        assert doc.get("person.name").value == "John"
        assert doc.get("address.city").value == "Austin"

    def test_relative_header_basic(self):
        doc = odin.parse('{vehicles[0]}\nvin = "ABC"\n\n{.garaging}\ncity = "Dallas"')
        assert doc.get("vehicles[0].vin").value == "ABC"
        assert doc.get("vehicles[0].garaging.city").value == "Dallas"

    def test_relative_header_multiple(self):
        doc = odin.parse('{vehicles[0]}\nvin = "ABC"\n\n{.garaging}\ncity = "Dallas"\n\n{.lienholder}\nname = "Bank"')
        assert doc.get("vehicles[0].garaging.city").value == "Dallas"
        assert doc.get("vehicles[0].lienholder.name").value == "Bank"

    def test_relative_then_absolute(self):
        doc = odin.parse('{vehicles[0]}\nvin = "ABC"\n\n{.garaging}\ncity = "Dallas"\n\n{drivers[0]}\nname = "John"')
        assert doc.get("vehicles[0].garaging.city").value == "Dallas"
        assert doc.get("drivers[0].name").value == "John"

    def test_relative_siblings(self):
        doc = odin.parse('{policy}\nid = "POL-001"\n\n{.insured}\nname = "John"\n\n{.address}\ncity = "Austin"')
        assert doc.get("policy.id").value == "POL-001"
        assert doc.get("policy.insured.name").value == "John"
        assert doc.get("policy.address.city").value == "Austin"

    def test_empty_header_resets(self):
        doc = odin.parse('{person}\nname = "John"\n\n{}\ntop = "root"')
        assert doc.get("person.name").value == "John"
        assert doc.get("top").value == "root"

    def test_metadata_header(self):
        doc = odin.parse('{$}\nodin = "1.0.0"\nid = "doc1"\n\nname = "John"')
        assert doc.get("name").value == "John"
        assert doc.metadata.get("odin").value == "1.0.0"
        assert doc.metadata.get("id").value == "doc1"

    def test_case_sensitive_headers(self):
        doc = odin.parse('{Person}\nname = "John"\n{person}\nname = "Jane"')
        assert doc.get("Person.name").value == "John"
        assert doc.get("person.name").value == "Jane"

    def test_header_with_array_index(self):
        doc = odin.parse('{items[0]}\nname = "Widget"\n{items[1]}\nname = "Gadget"')
        assert doc.get("items[0].name").value == "Widget"
        assert doc.get("items[1].name").value == "Gadget"


# ── Array Handling ───────────────────────────────────────────────────────


class TestArrayHandling:
    def test_array_indices(self):
        doc = odin.parse('items[0].name = "First"\nitems[1].name = "Second"')
        assert doc.get("items[0].name").value == "First"
        assert doc.get("items[1].name").value == "Second"

    def test_array_with_header(self):
        doc = odin.parse('{items[0]}\nname = "Widget"\nqty = ##10')
        assert doc.get("items[0].name").value == "Widget"
        assert doc.get("items[0].qty").value == 10

    def test_nested_arrays(self):
        doc = odin.parse('a[0].b[0].c = "deep"')
        assert doc.get("a[0].b[0].c").value == "deep"


# ── Modifiers ────────────────────────────────────────────────────────────


class TestModifiers:
    def test_required_string(self):
        doc = odin.parse('name = !"John"')
        assert doc.get("name").value == "John"
        mods = doc.modifiers.get("name")
        assert mods is not None
        assert mods.required is True

    def test_confidential_string(self):
        doc = odin.parse('ssn = *"123-45-6789"')
        assert doc.get("ssn").value == "123-45-6789"
        assert doc.modifiers["ssn"].confidential is True

    def test_deprecated_string(self):
        doc = odin.parse('old = -"legacy"')
        assert doc.get("old").value == "legacy"
        assert doc.modifiers["old"].deprecated is True

    def test_combined_modifiers(self):
        doc = odin.parse('ssn = !*"123-45-6789"')
        mods = doc.modifiers["ssn"]
        assert mods.required is True
        assert mods.confidential is True

    def test_all_three_modifiers(self):
        doc = odin.parse('secret = !*-"classified"')
        mods = doc.modifiers["secret"]
        assert mods.required is True
        assert mods.confidential is True
        assert mods.deprecated is True

    def test_modifier_order_normalized(self):
        doc = odin.parse('field = -*!"value"')
        mods = doc.modifiers["field"]
        assert mods.required is True
        assert mods.confidential is True
        assert mods.deprecated is True

    def test_required_integer(self):
        doc = odin.parse("count = !##42")
        assert doc.get("count").value == 42
        assert doc.modifiers["count"].required is True

    def test_confidential_null(self):
        doc = odin.parse("deleted = *~")
        assert isinstance(doc.get("deleted"), OdinNull)
        assert doc.modifiers["deleted"].confidential is True

    def test_required_boolean(self):
        doc = odin.parse("active = !true")
        assert doc.get("active").value is True
        assert doc.modifiers["active"].required is True

    def test_deprecated_date(self):
        doc = odin.parse("oldDate = -2024-01-15")
        assert isinstance(doc.get("oldDate"), OdinDate)
        assert doc.modifiers["oldDate"].deprecated is True

    def test_modifier_on_nested_path(self):
        doc = odin.parse('person.ssn = *"987-65-4321"')
        assert doc.modifiers["person.ssn"].confidential is True

    def test_modifier_on_array_element(self):
        doc = odin.parse('items[0].secret = *"hidden"')
        assert doc.modifiers["items[0].secret"].confidential is True

    def test_required_currency(self):
        doc = odin.parse("premium = !#$99.99")
        assert isinstance(doc.get("premium"), OdinCurrency)
        assert doc.modifiers["premium"].required is True

    def test_confidential_reference(self):
        doc = odin.parse("link = *@other.path")
        assert isinstance(doc.get("link"), OdinReference)
        assert doc.modifiers["link"].confidential is True

    def test_required_binary(self):
        doc = odin.parse("cert = !^SGVsbG8=")
        assert isinstance(doc.get("cert"), OdinBinary)
        assert doc.modifiers["cert"].required is True

    def test_required_percent(self):
        doc = odin.parse("taxRate = !#%0.0825")
        assert isinstance(doc.get("taxRate"), OdinPercent)
        assert doc.modifiers["taxRate"].required is True


# ── String Escapes ───────────────────────────────────────────────────────


class TestStringEscapes:
    def test_escape_backslash(self):
        doc = odin.parse('path = "C:\\\\Users\\\\admin"')
        assert doc.get("path").value == "C:\\Users\\admin"

    def test_escape_double_quote(self):
        doc = odin.parse('msg = "say \\"hello\\""')
        assert doc.get("msg").value == 'say "hello"'

    def test_escape_newline(self):
        doc = odin.parse('text = "line1\\nline2"')
        assert doc.get("text").value == "line1\nline2"

    def test_escape_tab(self):
        doc = odin.parse('text = "col1\\tcol2"')
        assert doc.get("text").value == "col1\tcol2"

    def test_escape_carriage_return(self):
        doc = odin.parse('text = "line1\\rline2"')
        assert doc.get("text").value == "line1\rline2"

    def test_unicode_short(self):
        doc = odin.parse('text = "\\u0048ello"')
        assert doc.get("text").value == "Hello"

    def test_unicode_emoji(self):
        doc = odin.parse('emoji = "\\U0001F600"')
        assert doc.get("emoji").value == "\U0001F600"


# ── Extension Paths ──────────────────────────────────────────────────────


class TestExtensionPaths:
    def test_extension_path(self):
        doc = odin.parse('&com.acme.tier = "A"')
        val = doc.get("&com.acme.tier")
        assert isinstance(val, OdinString)
        assert val.value == "A"

    def test_extension_with_modifier(self):
        doc = odin.parse('&com.acme.secret = *"classified"')
        assert doc.get("&com.acme.secret").value == "classified"
        assert doc.modifiers["&com.acme.secret"].confidential is True

    def test_extension_mixed_with_regular(self):
        doc = odin.parse('name = "Policy"\n&com.acme.tier = "Gold"')
        assert doc.get("name").value == "Policy"
        assert doc.get("&com.acme.tier").value == "Gold"


# ── Case Sensitivity ────────────────────────────────────────────────────


class TestCaseSensitivity:
    def test_different_case_fields(self):
        doc = odin.parse('Name = "Upper"\nname = "lower"')
        assert doc.get("Name").value == "Upper"
        assert doc.get("name").value == "lower"

    def test_field_named_true(self):
        doc = odin.parse('true = "some value"')
        assert doc.get("true").value == "some value"

    def test_field_named_false(self):
        doc = odin.parse("false = ##42")
        assert doc.get("false").value == 42

    def test_field_named_null(self):
        doc = odin.parse('null = "not null"')
        assert doc.get("null").value == "not null"


# ── Error Handling ───────────────────────────────────────────────────────


class TestParseErrors:
    def test_bare_string_error_p002(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse("name = bare value")
        assert exc_info.value.code == "P002"

    def test_unterminated_string_p004(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('name = "John')
        assert exc_info.value.code == "P004"

    def test_duplicate_path_p007(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('name = "John"\nname = "Jane"')
        assert exc_info.value.code == "P007"

    def test_invalid_header_p008(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse("{Section\nname = \"test\"")
        assert exc_info.value.code == "P008"

    def test_max_depth_p010(self):
        # Create a path deeper than max depth
        path = ".".join(f"s{i}" for i in range(200))
        with pytest.raises(ParseError) as exc_info:
            odin.parse(f'{path} = "deep"')
        assert exc_info.value.code == "P010"

    def test_non_contiguous_array_p013(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('items[0].name = "First"\nitems[5].name = "Fifth"')
        assert exc_info.value.code == "P013"

    def test_negative_array_index_p003(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('items[-1].name = "Invalid"')
        assert exc_info.value.code == "P003"

    def test_array_index_out_of_range_p015(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('items[999999999].name = "too big"')
        assert exc_info.value.code == "P015"

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

    def test_invalid_header_unclosed_bracket_p003(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse("{invalid[}")
        assert exc_info.value.code == "P003"

    def test_unexpected_char_at_line_start_p001(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('@ = "test"')
        assert exc_info.value.code == "P001"


# ── Security Limits ──────────────────────────────────────────────────────


class TestSecurityLimits:
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


# ── BOM and CRLF ────────────────────────────────────────────────────────


class TestBomAndCrlf:
    def test_crlf_line_endings(self):
        doc = odin.parse('name = "John"\r\nage = ##30')
        assert doc.get("name").value == "John"
        assert doc.get("age").value == 30

    def test_mixed_line_endings(self):
        doc = odin.parse('first = "John"\r\nsecond = "Jane"\nthird = "Bob"')
        assert len(doc) == 3

    def test_utf8_bom(self):
        doc = odin.parse('\ufeffname = "John"\nage = ##30')
        assert doc.get("name").value == "John"
        assert doc.get("age").value == 30

    def test_bom_with_crlf(self):
        doc = odin.parse('\ufeffname = "John"\r\nage = ##30\r\n')
        assert doc.get("name").value == "John"
        assert doc.get("age").value == 30


# ── Temporal Edge Cases ──────────────────────────────────────────────────


class TestTemporalEdgeCases:
    def test_leap_year_feb_29(self):
        doc = odin.parse("date = 2024-02-29")
        assert isinstance(doc.get("date"), OdinDate)
        assert doc.get("date").raw == "2024-02-29"

    def test_century_leap_year(self):
        doc = odin.parse("y2000 = 2000-02-29")
        assert isinstance(doc.get("y2000"), OdinDate)

    def test_not_leap_year_error(self):
        with pytest.raises(ParseError):
            odin.parse("date = 2023-02-29")

    def test_century_not_leap_error(self):
        with pytest.raises(ParseError):
            odin.parse("date = 1900-02-29")

    def test_month_boundaries(self):
        doc = odin.parse("jan = 2024-01-31\nfeb = 2024-02-29\napr = 2024-04-30")
        assert doc.get("jan").raw == "2024-01-31"
        assert doc.get("feb").raw == "2024-02-29"
        assert doc.get("apr").raw == "2024-04-30"

    def test_timestamp_milliseconds(self):
        doc = odin.parse("ts = 2024-06-15T14:30:00.123Z")
        assert doc.get("ts").raw == "2024-06-15T14:30:00.123Z"

    def test_timestamp_positive_offset(self):
        doc = odin.parse("ts = 2024-06-15T14:30:00+05:30")
        assert doc.get("ts").raw == "2024-06-15T14:30:00+05:30"

    def test_duration_variants(self):
        cases = [
            ("d1 = P5Y", "P5Y"),
            ("d2 = P6M", "P6M"),
            ("d3 = P2W", "P2W"),
            ("d4 = PT24H", "PT24H"),
            ("d5 = PT0S", "PT0S"),
        ]
        for input_text, expected in cases:
            doc = odin.parse(input_text)
            key = input_text.split(" = ")[0]
            assert doc.get(key).value == expected


# ── Document Metadata ────────────────────────────────────────────────────


class TestMetadata:
    def test_metadata_assignments(self):
        doc = odin.parse('{$}\nodin = "1.0.0"\nid = "doc1"\n\nname = "John"')
        assert doc.metadata["odin"].value == "1.0.0"
        assert doc.metadata["id"].value == "doc1"
        assert doc.get("name").value == "John"

    def test_metadata_in_assignments_with_prefix(self):
        doc = odin.parse('{$}\nodin = "1.0.0"\n\nname = "John"')
        # Metadata is also stored in assignments with $. prefix
        val = doc.get("$.odin")
        assert val is not None
        assert val.value == "1.0.0"


# ── Bytes Input ──────────────────────────────────────────────────────────


class TestBytesInput:
    def test_bytes_input(self):
        doc = odin.parse(b'name = "John"')
        assert doc.get("name").value == "John"

    def test_loads_alias(self):
        doc = odin.loads('name = "John"')
        assert doc.get("name").value == "John"

    def test_load_from_file(self):
        import io
        fp = io.StringIO('name = "John"')
        doc = odin.load(fp)
        assert doc.get("name").value == "John"


# ── Numeric Precision ────────────────────────────────────────────────────


class TestNumericPrecision:
    def test_integer_max_safe(self):
        doc = odin.parse("n = ##9007199254740991")
        assert doc.get("n").value == 9007199254740991

    def test_integer_min_safe(self):
        doc = odin.parse("n = ##-9007199254740991")
        assert doc.get("n").value == -9007199254740991

    def test_integer_beyond_safe_has_raw(self):
        doc = odin.parse("n = ##9007199254740992")
        val = doc.get("n")
        assert val.raw == "9007199254740992"

    def test_number_scientific_uppercase(self):
        doc = odin.parse("n = #1.5E10")
        assert doc.get("n").value == pytest.approx(1.5e10)

    def test_number_scientific_explicit_plus(self):
        doc = odin.parse("n = #1.5e+10")
        assert doc.get("n").value == pytest.approx(1.5e10)

    def test_number_high_precision_has_raw(self):
        doc = odin.parse("n = #3.141592653589793238")
        val = doc.get("n")
        assert val.raw == "3.141592653589793238"

    def test_currency_zero(self):
        doc = odin.parse("n = #$0.00")
        assert float(doc.get("n").value) == pytest.approx(0.0)

    def test_currency_one_cent(self):
        doc = odin.parse("n = #$0.01")
        assert float(doc.get("n").value) == pytest.approx(0.01)


# ── Tabular Mode ────────────────────────────────────────────────────────


class TestTabularMode:
    def test_basic_tabular(self):
        doc = odin.parse('{items[] : name, qty, price}\n"Widget", ##10, #$5.99\n"Gadget", ##5, #$12.50')
        assert doc.get("items[0].name").value == "Widget"
        assert doc.get("items[0].qty").value == 10
        assert float(doc.get("items[0].price").value) == pytest.approx(5.99)
        assert doc.get("items[1].name").value == "Gadget"

    def test_tabular_null_cell(self):
        doc = odin.parse('{items[] : name, notes}\n"Widget", "ok"\n"Gadget", ~')
        assert isinstance(doc.get("items[1].notes"), OdinNull)

    def test_tabular_empty_string_cell(self):
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

    def test_tabular_reference_cell(self):
        doc = odin.parse('{a[] : driver, vehicle}\n@drivers[0], @vehicles[0]')
        assert doc.get("a[0].driver").path == "drivers[0]"
        assert doc.get("a[0].vehicle").path == "vehicles[0]"


class TestInlineHeaderDirective:
    def test_inline_type_emits_synthetic_field(self):
        doc = odin.parse('{Vehicle :type "AUTO"}\nmake = "Honda"')
        assert doc.get("Vehicle._type").value == "AUTO"
        assert doc.get("Vehicle.make").value == "Honda"

    def test_inline_if_captures_unquoted_verb_expression(self):
        doc = odin.parse('{HighRisk :if %eq @driver.tier "dui"}\nband = "high"')
        assert doc.get("HighRisk._if").value == '%eq @driver.tier "dui"'
        assert doc.get("HighRisk.band").value == "high"

    def test_inline_if_captures_bare_reference(self):
        doc = odin.parse('{DuiDetails :if @driver.hasDui}\nstate = "TX"')
        assert doc.get("DuiDetails._if").value == "@driver.hasDui"
        assert doc.get("DuiDetails.state").value == "TX"

    def test_inline_elif_and_else(self):
        doc = odin.parse('{Young :elif %lt @age ##25}\nband = "young"')
        assert doc.get("Young._elif").value == "%lt @age ##25"
        doc2 = odin.parse('{Standard :else}\nband = "standard"')
        assert doc2.get("Standard._else").value == "true"

    def test_inline_directive_does_not_trigger_tabular(self):
        doc = odin.parse('{Section :if @cond}\nname = "X"')
        assert doc.get("Section._if").value == "@cond"
        assert doc.get("Section.name").value == "X"

    def test_tabular_colon_still_parses_columns(self):
        doc = odin.parse('{items[] : name, qty}\n"Widget", ##10')
        assert doc.get("items[0].name").value == "Widget"
        assert doc.get("items[0].qty").value == 10


# ── Document Chaining ────────────────────────────────────────────────────


class TestDocumentChaining:
    def test_single_doc_separator(self):
        doc = odin.parse('{$}\nodin = "1.0.0"\nid = "doc1"\n\nname = "John"\n\n---\n\n{$}\nodin = "1.0.0"\nid = "doc2"\n\nname = "Jane"')
        # First document
        assert doc.get("name").value == "John"

    def test_metadata_and_data_separate(self):
        doc = odin.parse('{$}\nodin = "1.0.0"\nid = "doc1"\n\nname = "John"')
        assert doc.metadata["odin"].value == "1.0.0"
        assert doc.get("name").value == "John"


# ── Directives ───────────────────────────────────────────────────────────


class TestDirectives:
    def test_import_directive_valid(self):
        doc = odin.parse('@import ./file.odin\n\nname = "test"')
        assert doc.get("name").value == "test"

    def test_import_directive_with_alias(self):
        doc = odin.parse('@import ./file.odin as f\n\nname = "test"')
        assert doc.get("name").value == "test"

    def test_schema_directive(self):
        doc = odin.parse('@schema https://example.com/schema.odin\n\nname = "test"')
        assert doc.get("name").value == "test"

    def test_import_missing_path_p009(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse("@import\n\nname = \"test\"")
        assert exc_info.value.code == "P009"

    def test_schema_missing_url_p009(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse("@schema\n\nname = \"test\"")
        assert exc_info.value.code == "P009"

    def test_if_missing_condition_p009(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse("@if\n\nname = \"test\"")
        assert exc_info.value.code == "P009"

    def test_import_trailing_as_p009(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse("@import ./file.odin as\n\nname = \"test\"")
        assert exc_info.value.code == "P009"

    def test_invalid_directive_p001(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse("@invalid ./file.odin\n\nname = \"test\"")
        assert exc_info.value.code == "P001"


# ── Escape Sequences ────────────────────────────────────────────────────


class TestEscapeErrors:
    def test_invalid_escape_p005(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse('name = "hello\\z world"')
        assert exc_info.value.code == "P005"

    def test_null_char_escape(self):
        doc = odin.parse('text = "null\\0byte"')
        assert doc.get("text").value == "null\x00byte"


# ── Binary Edge Cases ───────────────────────────────────────────────────


class TestBinaryEdgeCases:
    def test_binary_with_padding(self):
        doc = odin.parse("data = ^QQ==")
        val = doc.get("data")
        assert isinstance(val, OdinBinary)
        assert val.data == b"A"

    def test_invalid_base64_char(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse("data = ^SGVs!G8=")
        assert exc_info.value.code == "P001"

    def test_invalid_base64_padding(self):
        with pytest.raises(ParseError) as exc_info:
            odin.parse("data = ^SGVs=bG8")
        assert exc_info.value.code == "P001"
