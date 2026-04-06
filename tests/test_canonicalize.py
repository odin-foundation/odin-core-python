"""Tests for ODIN canonicalize serialization."""
import hashlib
import pytest
import odin
from odin.types.document import OdinDocumentBuilder, OdinModifiers
from odin.types.values import (
    OdinNull, OdinBoolean, OdinString, OdinNumber, OdinInteger,
    OdinCurrency, OdinPercent, OdinDate, OdinTimestamp, OdinTime,
    OdinDuration, OdinReference, OdinBinary, OdinVerbExpression,
    NULL, TRUE, FALSE,
)
from decimal import Decimal
from datetime import date, datetime


# ─── Value Formatting ───

class TestCanonicalValues:
    """Test canonical value formatting."""

    def test_null(self):
        doc = OdinDocumentBuilder().set("value", NULL).build()
        assert odin.canonicalize(doc) == b"value = ~\n"

    def test_boolean_true(self):
        doc = OdinDocumentBuilder().set("flag", TRUE).build()
        assert odin.canonicalize(doc) == b"flag = true\n"

    def test_boolean_false(self):
        doc = OdinDocumentBuilder().set("flag", FALSE).build()
        assert odin.canonicalize(doc) == b"flag = false\n"

    def test_string(self):
        doc = OdinDocumentBuilder().set("name", OdinString("John")).build()
        assert odin.canonicalize(doc) == b'name = "John"\n'

    def test_string_escape(self):
        doc = OdinDocumentBuilder().set("text", OdinString("line1\nline2")).build()
        assert odin.canonicalize(doc) == b'text = "line1\\nline2"\n'

    def test_string_tab_escape(self):
        doc = OdinDocumentBuilder().set("text", OdinString("col1\tcol2")).build()
        assert odin.canonicalize(doc) == b'text = "col1\\tcol2"\n'

    def test_string_quote_escape(self):
        doc = OdinDocumentBuilder().set("text", OdinString('say "hello"')).build()
        assert odin.canonicalize(doc) == b'text = "say \\"hello\\""\n'

    def test_number(self):
        doc = OdinDocumentBuilder().set("rate", OdinNumber(3.14)).build()
        assert odin.canonicalize(doc) == b"rate = #3.14\n"

    def test_number_trailing_zeros_stripped(self):
        doc = OdinDocumentBuilder().set("rate", OdinNumber(3.14, raw="3.140")).build()
        # Canonical ignores raw, strips trailing zeros
        assert odin.canonicalize(doc) == b"rate = #3.14\n"

    def test_number_integer_form(self):
        doc = OdinDocumentBuilder().set("count", OdinNumber(42.0)).build()
        assert odin.canonicalize(doc) == b"count = #42\n"

    def test_integer(self):
        doc = OdinDocumentBuilder().set("count", OdinInteger(42)).build()
        assert odin.canonicalize(doc) == b"count = ##42\n"

    def test_integer_negative(self):
        doc = OdinDocumentBuilder().set("offset", OdinInteger(-100)).build()
        assert odin.canonicalize(doc) == b"offset = ##-100\n"

    def test_currency_simple(self):
        doc = OdinDocumentBuilder().set("price", OdinCurrency(Decimal("99.99"))).build()
        assert odin.canonicalize(doc) == b"price = #$99.99\n"

    def test_currency_with_code(self):
        doc = OdinDocumentBuilder().set("amount", OdinCurrency(Decimal("100.00"), currency_code="USD")).build()
        assert odin.canonicalize(doc) == b"amount = #$100.00:USD\n"

    def test_currency_code_uppercased(self):
        doc = OdinDocumentBuilder().set("price", OdinCurrency(Decimal("50.00"), currency_code="gbp")).build()
        assert odin.canonicalize(doc) == b"price = #$50.00:GBP\n"

    def test_currency_negative(self):
        doc = OdinDocumentBuilder().set("refund", OdinCurrency(Decimal("-25.00"))).build()
        assert odin.canonicalize(doc) == b"refund = #$-25.00\n"

    def test_currency_trailing_zeros(self):
        """Currency always has at least 2 decimal places."""
        doc = OdinDocumentBuilder().set("price", OdinCurrency(Decimal("10"), decimal_places=0)).build()
        assert odin.canonicalize(doc) == b"price = #$10.00\n"

    def test_percent(self):
        doc = OdinDocumentBuilder().set("rate", OdinPercent(0.15, raw="0.15")).build()
        assert odin.canonicalize(doc) == b"rate = #%0.15\n"

    def test_percent_whole(self):
        doc = OdinDocumentBuilder().set("complete", OdinPercent(1.0, raw="1")).build()
        assert odin.canonicalize(doc) == b"complete = #%1\n"

    def test_percent_negative(self):
        doc = OdinDocumentBuilder().set("loss", OdinPercent(-0.05, raw="-0.05")).build()
        assert odin.canonicalize(doc) == b"loss = #%-0.05\n"

    def test_date(self):
        doc = OdinDocumentBuilder().set("effective", OdinDate(date(2024, 6, 15), raw="2024-06-15")).build()
        assert odin.canonicalize(doc) == b"effective = 2024-06-15\n"

    def test_timestamp(self):
        doc = OdinDocumentBuilder().set("created", OdinTimestamp(datetime(2024, 6, 15, 10, 30), raw="2024-06-15T10:30:00Z")).build()
        assert odin.canonicalize(doc) == b"created = 2024-06-15T10:30:00Z\n"

    def test_time(self):
        doc = OdinDocumentBuilder().set("start", OdinTime("T09:30:00")).build()
        assert odin.canonicalize(doc) == b"start = T09:30:00\n"

    def test_duration(self):
        doc = OdinDocumentBuilder().set("term", OdinDuration("P6M")).build()
        assert odin.canonicalize(doc) == b"term = P6M\n"

    def test_reference(self):
        doc = OdinDocumentBuilder().set("primary", OdinReference("drivers[0]")).build()
        assert odin.canonicalize(doc) == b"primary = @drivers[0]\n"

    def test_binary(self):
        doc = OdinDocumentBuilder().set("data", OdinBinary(b"Hello")).build()
        assert odin.canonicalize(doc) == b"data = ^SGVsbG8=\n"

    def test_binary_algorithm(self):
        doc = OdinDocumentBuilder().set("hash", OdinBinary(b"Hello", algorithm="sha256")).build()
        assert odin.canonicalize(doc) == b"hash = ^sha256:SGVsbG8=\n"


# ─── Path Sorting ───

class TestCanonicalPathSorting:
    """Test canonical path sorting."""

    def test_alphabetical_sorting(self):
        b = OdinDocumentBuilder()
        b.set("zebra", OdinString("last"))
        b.set("alpha", OdinString("first"))
        b.set("middle", OdinString("second"))
        result = odin.canonicalize(b.build()).decode('utf-8')
        assert result == 'alpha = "first"\nmiddle = "second"\nzebra = "last"\n'

    def test_metadata_first(self):
        b = OdinDocumentBuilder()
        b.set("name", OdinString("Policy"))
        b.set_metadata("odin", OdinString("1.0.0"))
        result = odin.canonicalize(b.build()).decode('utf-8')
        assert result.startswith('$.odin = "1.0.0"')

    def test_array_indices_numeric(self):
        """Array indices sort numerically, not lexicographically."""
        b = OdinDocumentBuilder()
        for i in range(11):
            b.set(f"items[{i}]", OdinString(str(i)))
        result = odin.canonicalize(b.build()).decode('utf-8')
        lines = result.strip().split('\n')
        assert len(lines) == 11
        # items[2] should come before items[10]
        idx_2 = next(i for i, l in enumerate(lines) if 'items[2]' in l)
        idx_10 = next(i for i, l in enumerate(lines) if 'items[10]' in l)
        assert idx_2 < idx_10

    def test_section_sorting(self):
        """Section paths sorted by full path."""
        b = OdinDocumentBuilder()
        b.set("customer.name", OdinString("John"))
        b.set("address.city", OdinString("Austin"))
        result = odin.canonicalize(b.build()).decode('utf-8')
        assert result.startswith('address.city')

    def test_nested_sorting(self):
        b = OdinDocumentBuilder()
        b.set("a.z.val", OdinInteger(1))
        b.set("a.m.val", OdinInteger(2))
        result = odin.canonicalize(b.build()).decode('utf-8')
        assert result == "a.m.val = ##2\na.z.val = ##1\n"


# ─── Modifier Preservation ───

class TestCanonicalModifiers:
    """Test modifier preservation in canonical form."""

    def test_required(self):
        b = OdinDocumentBuilder()
        b.set("name", OdinString("John"), OdinModifiers(required=True))
        assert odin.canonicalize(b.build()) == b'name = !"John"\n'

    def test_confidential(self):
        b = OdinDocumentBuilder()
        b.set("ssn", OdinString("123-45-6789"), OdinModifiers(confidential=True))
        assert odin.canonicalize(b.build()) == b'ssn = *"123-45-6789"\n'

    def test_deprecated(self):
        b = OdinDocumentBuilder()
        b.set("oldField", OdinString("legacy"), OdinModifiers(deprecated=True))
        assert odin.canonicalize(b.build()) == b'oldField = -"legacy"\n'

    def test_combined_order(self):
        """Combined modifiers in canonical order: !*-"""
        b = OdinDocumentBuilder()
        b.set("important", OdinString("secret"),
              OdinModifiers(required=True, confidential=True, deprecated=True))
        assert odin.canonicalize(b.build()) == b'important = !*-"secret"\n'


# ─── Normalization ───

class TestCanonicalNormalization:
    """Test canonical normalization via parse."""

    def test_strip_comments(self):
        text = "; This is a comment\nname = \"John\"\n; Another comment\nage = ##30"
        result = odin.canonicalize(odin.parse(text)).decode('utf-8')
        assert result == 'age = ##30\nname = "John"\n'

    def test_strip_blank_lines(self):
        text = 'name = "John"\n\n\nage = ##30\n\n'
        result = odin.canonicalize(odin.parse(text)).decode('utf-8')
        assert result == 'age = ##30\nname = "John"\n'

    def test_crlf_to_lf(self):
        text = 'name = "John"\r\nage = ##30\r\n'
        result = odin.canonicalize(odin.parse(text)).decode('utf-8')
        assert result == 'age = ##30\nname = "John"\n'
        assert '\r' not in result

    def test_bom_stripped(self):
        text = '\uFEFFname = "John"\nage = ##30'
        result = odin.canonicalize(odin.parse(text)).decode('utf-8')
        assert result == 'age = ##30\nname = "John"\n'

    def test_whitespace_normalized(self):
        text = 'name  =  "John"\nage=##30\ncity =    "Austin"'
        result = odin.canonicalize(odin.parse(text)).decode('utf-8')
        assert result == 'age = ##30\ncity = "Austin"\nname = "John"\n'

    def test_section_paths_expanded(self):
        text = "{customer}\nname = \"John\"\n{address}\ncity = \"Austin\""
        result = odin.canonicalize(odin.parse(text)).decode('utf-8')
        assert result == 'address.city = "Austin"\ncustomer.name = "John"\n'

    def test_nested_paths_expanded(self):
        text = "{person}\nname = \"Alice\"\n{person}\nage = ##30"
        result = odin.canonicalize(odin.parse(text)).decode('utf-8')
        assert result == 'person.age = ##30\nperson.name = "Alice"\n'

    def test_boolean_no_prefix(self):
        text = "active = ?true\nenabled = ?false"
        result = odin.canonicalize(odin.parse(text)).decode('utf-8')
        assert result == "active = true\nenabled = false\n"


# ─── UTF-8 Binary Output ───

class TestCanonicalBinaryOutput:
    """Test binary (UTF-8) output correctness."""

    def test_empty_document(self):
        doc = OdinDocumentBuilder().build()
        result = odin.canonicalize(doc)
        assert result == b""
        assert len(result) == 0

    def test_single_null_bytes(self):
        doc = odin.parse("value = ~")
        result = odin.canonicalize(doc)
        assert result.hex() == "76616c7565203d207e0a"

    def test_unicode_latin(self):
        doc = odin.parse('city = "Zürich"')
        result = odin.canonicalize(doc)
        assert result.hex() == "63697479203d20225ac3bc72696368220a"

    def test_unicode_cjk(self):
        doc = odin.parse('greeting = "你好"')
        result = odin.canonicalize(doc)
        assert result.hex() == "6772656574696e67203d2022e4bda0e5a5bd220a"

    def test_unicode_emoji(self):
        doc = odin.parse('icon = "🌍"')
        result = odin.canonicalize(doc)
        assert result.hex() == "69636f6e203d2022f09f8c8d220a"

    def test_insertion_order_irrelevant(self):
        """Same fields in different insertion order produce same canonical output."""
        doc1 = odin.parse("alpha = ##1\nbeta = ##2\ngamma = ##3")
        doc2 = odin.parse("gamma = ##3\nalpha = ##1\nbeta = ##2")
        assert odin.canonicalize(doc1) == odin.canonicalize(doc2)

    def test_hash_stability(self):
        doc = odin.parse("alpha = ##1\nbeta = ##2\ngamma = ##3")
        result = odin.canonicalize(doc)
        sha = hashlib.sha256(result).hexdigest()
        assert sha == "e2a221798a95fb8d517873c25149e044b14052fdcaf74b5d4a94cfd565dbc4e5"


# ─── Tabular Expansion ───

class TestCanonicalTabularExpansion:
    """Test tabular syntax expansion in canonical form."""

    def test_tabular_to_expanded(self):
        text = '{items[] : name, qty, price}\n"Widget", ##10, #$5.99\n"Gadget", ##5, #$12.50'
        result = odin.canonicalize(odin.parse(text)).decode('utf-8')
        expected = (
            'items[0].name = "Widget"\n'
            'items[0].price = #$5.99\n'
            'items[0].qty = ##10\n'
            'items[1].name = "Gadget"\n'
            'items[1].price = #$12.50\n'
            'items[1].qty = ##5\n'
        )
        assert result == expected

    def test_primitive_array_expanded(self):
        text = '{tags[] : ~}\n"urgent"\n"important"\n"reviewed"'
        result = odin.canonicalize(odin.parse(text)).decode('utf-8')
        expected = 'tags[0] = "urgent"\ntags[1] = "important"\ntags[2] = "reviewed"\n'
        assert result == expected

    def test_tabular_columns_sorted(self):
        text = '{items[] : zebra, alpha}\n"z-val", "a-val"'
        result = odin.canonicalize(odin.parse(text)).decode('utf-8')
        expected = 'items[0].alpha = "a-val"\nitems[0].zebra = "z-val"\n'
        assert result == expected

    def test_tabular_null_preserved(self):
        text = '{items[] : name, description}\n"Widget", ~'
        result = odin.canonicalize(odin.parse(text)).decode('utf-8')
        expected = 'items[0].description = ~\nitems[0].name = "Widget"\n'
        assert result == expected

    def test_relative_header_expanded(self):
        text = '{vehicles[0]}\nvin = "ABC123"\n\n{.garaging}\ncity = "Dallas"'
        result = odin.canonicalize(odin.parse(text)).decode('utf-8')
        expected = 'vehicles[0].garaging.city = "Dallas"\nvehicles[0].vin = "ABC123"\n'
        assert result == expected

    def test_tabular_dot_columns(self):
        text = '{items[] : product.name, product.sku, qty}\n"Widget", "WGT-001", ##10'
        result = odin.canonicalize(odin.parse(text)).decode('utf-8')
        expected = (
            'items[0].product.name = "Widget"\n'
            'items[0].product.sku = "WGT-001"\n'
            'items[0].qty = ##10\n'
        )
        assert result == expected
