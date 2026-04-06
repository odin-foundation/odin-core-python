"""Tests for ODIN diff and patch operations."""

import pytest
from collections import OrderedDict
from decimal import Decimal
from datetime import date, datetime

import odin
from odin.types.document import OdinDocument, OdinDocumentBuilder, OdinModifiers
from odin.types.values import (
    OdinNull, OdinBoolean, OdinString, OdinNumber, OdinInteger,
    OdinCurrency, OdinPercent, OdinDate, OdinTimestamp, OdinTime,
    OdinDuration, OdinReference, OdinBinary, NULL, TRUE, FALSE,
)
from odin.types.diff import OdinDiff, PathValue, PathChange, PathMove
from odin.types.errors import PatchError


def _doc(**kwargs: odin.OdinValue) -> OdinDocument:
    """Helper to build a document from keyword arguments."""
    b = OdinDocumentBuilder()
    for path, value in kwargs.items():
        b.set(path, value)
    return b.build()


def _doc_with_modifiers(entries: dict) -> OdinDocument:
    """Helper to build a document with modifiers. entries: {path: (value, modifiers)}"""
    b = OdinDocumentBuilder()
    for path, (value, mods) in entries.items():
        b.set(path, value, mods)
    return b.build()


# ─────────────────────────────────────────────────────────────────────────────
# Empty / Identical Documents
# ─────────────────────────────────────────────────────────────────────────────


class TestDiffEmpty:
    def test_empty_documents(self):
        a = _doc()
        b = _doc()
        d = odin.diff(a, b)
        assert d.is_empty

    def test_identical_documents(self):
        a = _doc(name=OdinString("John"), age=OdinInteger(42))
        b = _doc(name=OdinString("John"), age=OdinInteger(42))
        d = odin.diff(a, b)
        assert d.is_empty

    def test_identical_null_values(self):
        a = _doc(value=NULL)
        b = _doc(value=NULL)
        d = odin.diff(a, b)
        assert d.is_empty

    def test_identical_boolean_values(self):
        a = _doc(flag=TRUE)
        b = _doc(flag=TRUE)
        d = odin.diff(a, b)
        assert d.is_empty


# ─────────────────────────────────────────────────────────────────────────────
# Additions
# ─────────────────────────────────────────────────────────────────────────────


class TestDiffAdditions:
    def test_single_addition(self):
        a = _doc(name=OdinString("John"))
        b = _doc(name=OdinString("John"), age=OdinInteger(30))
        d = odin.diff(a, b)
        assert not d.is_empty
        assert len(d.additions) == 1
        assert d.additions[0].path == "age"
        assert d.additions[0].value == OdinInteger(30)

    def test_multiple_additions(self):
        a = _doc()
        b = _doc(name=OdinString("John"), age=OdinInteger(30))
        d = odin.diff(a, b)
        assert len(d.additions) == 2
        paths = {e.path for e in d.additions}
        assert paths == {"name", "age"}

    def test_addition_preserves_value_type(self):
        a = _doc()
        b = _doc(price=OdinCurrency(Decimal("99.99")))
        d = odin.diff(a, b)
        assert len(d.additions) == 1
        assert isinstance(d.additions[0].value, OdinCurrency)
        assert d.additions[0].value.value == Decimal("99.99")


# ─────────────────────────────────────────────────────────────────────────────
# Removals / Deletions
# ─────────────────────────────────────────────────────────────────────────────


class TestDiffDeletions:
    def test_single_deletion(self):
        a = _doc(name=OdinString("John"), age=OdinInteger(30))
        b = _doc(name=OdinString("John"))
        d = odin.diff(a, b)
        assert not d.is_empty
        assert len(d.deletions) == 1
        assert d.deletions[0].path == "age"
        assert d.deletions[0].value == OdinInteger(30)

    def test_multiple_deletions(self):
        a = _doc(name=OdinString("John"), age=OdinInteger(30), city=OdinString("Austin"))
        b = _doc()
        d = odin.diff(a, b)
        assert len(d.deletions) == 3

    def test_all_removed(self):
        a = _doc(x=OdinString("hello"))
        b = _doc()
        d = odin.diff(a, b)
        assert len(d.deletions) == 1
        assert len(d.additions) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Modifications (Changes)
# ─────────────────────────────────────────────────────────────────────────────


class TestDiffModifications:
    def test_string_change(self):
        a = _doc(name=OdinString("John"))
        b = _doc(name=OdinString("Jane"))
        d = odin.diff(a, b)
        assert len(d.modifications) == 1
        assert d.modifications[0].path == "name"
        assert d.modifications[0].old_value == OdinString("John")
        assert d.modifications[0].new_value == OdinString("Jane")

    def test_boolean_change(self):
        a = _doc(flag=TRUE)
        b = _doc(flag=FALSE)
        d = odin.diff(a, b)
        assert len(d.modifications) == 1

    def test_number_change(self):
        a = _doc(rate=OdinNumber(3.14))
        b = _doc(rate=OdinNumber(2.71))
        d = odin.diff(a, b)
        assert len(d.modifications) == 1

    def test_integer_change(self):
        a = _doc(count=OdinInteger(42))
        b = _doc(count=OdinInteger(100))
        d = odin.diff(a, b)
        assert len(d.modifications) == 1

    def test_type_change_integer_to_number(self):
        a = _doc(value=OdinInteger(42))
        b = _doc(value=OdinNumber(42.0))
        d = odin.diff(a, b)
        assert len(d.modifications) == 1

    def test_type_change_string_to_integer(self):
        a = _doc(value=OdinString("42"))
        b = _doc(value=OdinInteger(42))
        d = odin.diff(a, b)
        assert len(d.modifications) == 1

    def test_null_to_value(self):
        a = _doc(name=NULL)
        b = _doc(name=OdinString("John"))
        d = odin.diff(a, b)
        assert len(d.modifications) == 1

    def test_value_to_null(self):
        a = _doc(name=OdinString("John"))
        b = _doc(name=NULL)
        d = odin.diff(a, b)
        assert len(d.modifications) == 1

    def test_currency_different_value(self):
        a = _doc(price=OdinCurrency(Decimal("99.99")))
        b = _doc(price=OdinCurrency(Decimal("149.99")))
        d = odin.diff(a, b)
        assert len(d.modifications) == 1

    def test_currency_different_code(self):
        a = _doc(amount=OdinCurrency(Decimal("100.00"), currency_code="USD"))
        b = _doc(amount=OdinCurrency(Decimal("100.00"), currency_code="EUR"))
        d = odin.diff(a, b)
        assert len(d.modifications) == 1

    def test_currency_code_vs_no_code(self):
        a = _doc(price=OdinCurrency(Decimal("50.00"), currency_code="USD"))
        b = _doc(price=OdinCurrency(Decimal("50.00")))
        d = odin.diff(a, b)
        assert len(d.modifications) == 1

    def test_currency_same(self):
        a = _doc(price=OdinCurrency(Decimal("99.99")))
        b = _doc(price=OdinCurrency(Decimal("99.99")))
        d = odin.diff(a, b)
        assert d.is_empty

    def test_currency_same_with_code(self):
        a = _doc(amt=OdinCurrency(Decimal("100.00"), currency_code="USD"))
        b = _doc(amt=OdinCurrency(Decimal("100.00"), currency_code="USD"))
        d = odin.diff(a, b)
        assert d.is_empty

    def test_percent_change(self):
        a = _doc(rate=OdinPercent(0.15))
        b = _doc(rate=OdinPercent(0.25))
        d = odin.diff(a, b)
        assert len(d.modifications) == 1

    def test_percent_same(self):
        a = _doc(rate=OdinPercent(0.15))
        b = _doc(rate=OdinPercent(0.15))
        d = odin.diff(a, b)
        assert d.is_empty

    def test_percent_vs_number(self):
        a = _doc(value=OdinPercent(0.15))
        b = _doc(value=OdinNumber(0.15))
        d = odin.diff(a, b)
        assert len(d.modifications) == 1

    def test_date_change(self):
        a = _doc(effective=OdinDate(date(2024, 6, 15), raw="2024-06-15"))
        b = _doc(effective=OdinDate(date(2024, 6, 16), raw="2024-06-16"))
        d = odin.diff(a, b)
        assert len(d.modifications) == 1

    def test_date_same(self):
        a = _doc(effective=OdinDate(date(2024, 6, 15), raw="2024-06-15"))
        b = _doc(effective=OdinDate(date(2024, 6, 15), raw="2024-06-15"))
        d = odin.diff(a, b)
        assert d.is_empty

    def test_timestamp_change(self):
        a = _doc(created=OdinTimestamp(datetime(2024, 6, 15, 10, 30), raw="2024-06-15T10:30:00Z"))
        b = _doc(created=OdinTimestamp(datetime(2024, 6, 15, 11, 30), raw="2024-06-15T11:30:00Z"))
        d = odin.diff(a, b)
        assert len(d.modifications) == 1

    def test_timestamp_same(self):
        a = _doc(created=OdinTimestamp(datetime(2024, 6, 15, 10, 30), raw="2024-06-15T10:30:00Z"))
        b = _doc(created=OdinTimestamp(datetime(2024, 6, 15, 10, 30), raw="2024-06-15T10:30:00Z"))
        d = odin.diff(a, b)
        assert d.is_empty

    def test_time_change(self):
        a = _doc(start=OdinTime("09:30:00"))
        b = _doc(start=OdinTime("10:30:00"))
        d = odin.diff(a, b)
        assert len(d.modifications) == 1

    def test_time_same(self):
        a = _doc(start=OdinTime("09:30:00"))
        b = _doc(start=OdinTime("09:30:00"))
        d = odin.diff(a, b)
        assert d.is_empty

    def test_duration_change(self):
        a = _doc(term=OdinDuration("P6M"))
        b = _doc(term=OdinDuration("P1Y"))
        d = odin.diff(a, b)
        assert len(d.modifications) == 1

    def test_duration_same(self):
        a = _doc(term=OdinDuration("P6M"))
        b = _doc(term=OdinDuration("P6M"))
        d = odin.diff(a, b)
        assert d.is_empty

    def test_reference_change(self):
        a = _doc(primary=OdinReference("drivers[0]"))
        b = _doc(primary=OdinReference("drivers[1]"))
        d = odin.diff(a, b)
        assert len(d.modifications) == 1

    def test_reference_same(self):
        a = _doc(primary=OdinReference("drivers[0]"))
        b = _doc(primary=OdinReference("drivers[0]"))
        d = odin.diff(a, b)
        assert d.is_empty

    def test_binary_change(self):
        a = _doc(data=OdinBinary(b"Hello"))
        b = _doc(data=OdinBinary(b"World"))
        d = odin.diff(a, b)
        assert len(d.modifications) == 1

    def test_binary_same(self):
        a = _doc(data=OdinBinary(b"Hello"))
        b = _doc(data=OdinBinary(b"Hello"))
        d = odin.diff(a, b)
        assert d.is_empty

    def test_binary_different_algorithm(self):
        a = _doc(hash=OdinBinary(b"abc", algorithm="sha256"))
        b = _doc(hash=OdinBinary(b"abc", algorithm="md5"))
        d = odin.diff(a, b)
        assert len(d.modifications) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Moves
# ─────────────────────────────────────────────────────────────────────────────


class TestDiffMoves:
    def test_simple_move(self):
        a = _doc(oldField=OdinString("value"))
        b = _doc(newField=OdinString("value"))
        d = odin.diff(a, b)
        assert len(d.moves) == 1
        assert d.moves[0].from_path == "oldField"
        assert d.moves[0].to_path == "newField"
        # Moved items should NOT appear in additions/deletions
        assert len(d.additions) == 0
        assert len(d.deletions) == 0

    def test_move_with_integer_value(self):
        a = _doc(x=OdinInteger(42))
        b = _doc(y=OdinInteger(42))
        d = odin.diff(a, b)
        assert len(d.moves) == 1
        assert d.moves[0].from_path == "x"
        assert d.moves[0].to_path == "y"

    def test_move_does_not_match_different_values(self):
        a = _doc(x=OdinString("hello"))
        b = _doc(y=OdinString("world"))
        d = odin.diff(a, b)
        assert len(d.moves) == 0
        assert len(d.deletions) == 1
        assert len(d.additions) == 1

    def test_multiple_moves(self):
        a = _doc(a=OdinString("one"), b=OdinString("two"))
        b = _doc(c=OdinString("one"), d=OdinString("two"))
        d = odin.diff(a, b)
        assert len(d.moves) == 2
        assert len(d.additions) == 0
        assert len(d.deletions) == 0

    def test_move_first_match_wins(self):
        """When a value appears in multiple added paths, the first match wins."""
        a = _doc(x=OdinString("dup"))
        b = _doc(y=OdinString("dup"), z=OdinString("dup"))
        d = odin.diff(a, b)
        # x -> y is the move, z remains as addition
        assert len(d.moves) == 1
        assert d.moves[0].to_path == "y"
        assert len(d.additions) == 1
        assert d.additions[0].path == "z"


# ─────────────────────────────────────────────────────────────────────────────
# Modifier Changes
# ─────────────────────────────────────────────────────────────────────────────


class TestDiffModifiers:
    def test_modifier_added(self):
        a = _doc_with_modifiers({"name": (OdinString("John"), None)})
        b = _doc_with_modifiers({"name": (OdinString("John"), OdinModifiers(required=True))})
        d = odin.diff(a, b)
        assert len(d.modifications) == 1

    def test_modifier_removed(self):
        a = _doc_with_modifiers({"name": (OdinString("John"), OdinModifiers(required=True))})
        b = _doc_with_modifiers({"name": (OdinString("John"), None)})
        d = odin.diff(a, b)
        assert len(d.modifications) == 1

    def test_modifier_changed(self):
        a = _doc_with_modifiers({"ssn": (OdinString("123"), OdinModifiers(required=True))})
        b = _doc_with_modifiers({"ssn": (OdinString("123"), OdinModifiers(confidential=True))})
        d = odin.diff(a, b)
        assert len(d.modifications) == 1

    def test_same_value_same_modifier_equal(self):
        a = _doc_with_modifiers({"name": (OdinString("John"), OdinModifiers(required=True))})
        b = _doc_with_modifiers({"name": (OdinString("John"), OdinModifiers(required=True))})
        d = odin.diff(a, b)
        assert d.is_empty

    def test_combined_modifiers_same(self):
        mods = OdinModifiers(required=True, confidential=True)
        a = _doc_with_modifiers({"field": (OdinString("secret"), mods)})
        b = _doc_with_modifiers({"field": (OdinString("secret"), mods)})
        d = odin.diff(a, b)
        assert d.is_empty

    def test_combined_modifiers_different(self):
        a = _doc_with_modifiers({"field": (OdinString("val"), OdinModifiers(required=True))})
        b = _doc_with_modifiers({"field": (OdinString("val"), OdinModifiers(required=True, confidential=True))})
        d = odin.diff(a, b)
        assert len(d.modifications) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Mixed Operations
# ─────────────────────────────────────────────────────────────────────────────


class TestDiffMixed:
    def test_add_remove_change(self):
        a = _doc(name=OdinString("John"), age=OdinInteger(30), city=OdinString("Austin"))
        b = _doc(name=OdinString("Jane"), state=OdinString("TX"))
        d = odin.diff(a, b)
        assert len(d.modifications) == 1  # name changed
        assert len(d.additions) == 1  # state added
        assert len(d.deletions) == 2  # age, city removed

    def test_move_plus_change(self):
        a = _doc(x=OdinString("same"), y=OdinInteger(1))
        b = _doc(z=OdinString("same"), y=OdinInteger(2))
        d = odin.diff(a, b)
        assert len(d.moves) == 1  # x -> z
        assert len(d.modifications) == 1  # y changed


# ─────────────────────────────────────────────────────────────────────────────
# Patch - Basic Operations
# ─────────────────────────────────────────────────────────────────────────────


class TestPatchBasic:
    def test_patch_empty_diff(self):
        a = _doc(name=OdinString("John"))
        d = OdinDiff()
        result = odin.patch(a, d)
        assert result.get("name") == OdinString("John")

    def test_patch_addition(self):
        a = _doc(name=OdinString("John"))
        d = OdinDiff(additions=[PathValue("age", OdinInteger(30))])
        result = odin.patch(a, d)
        assert result.get("name") == OdinString("John")
        assert result.get("age") == OdinInteger(30)

    def test_patch_deletion(self):
        a = _doc(name=OdinString("John"), age=OdinInteger(30))
        d = OdinDiff(deletions=[PathValue("age", OdinInteger(30))])
        result = odin.patch(a, d)
        assert result.get("name") == OdinString("John")
        assert result.get("age") is None

    def test_patch_modification(self):
        a = _doc(name=OdinString("John"))
        d = OdinDiff(modifications=[PathChange("name", OdinString("John"), OdinString("Jane"))])
        result = odin.patch(a, d)
        assert result.get("name") == OdinString("Jane")

    def test_patch_move(self):
        a = _doc(old=OdinString("value"))
        d = OdinDiff(moves=[PathMove("old", "new")])
        result = odin.patch(a, d)
        assert result.get("old") is None
        assert result.get("new") == OdinString("value")


# ─────────────────────────────────────────────────────────────────────────────
# Patch - Error Cases
# ─────────────────────────────────────────────────────────────────────────────


class TestPatchErrors:
    def test_remove_nonexistent_path(self):
        a = _doc(name=OdinString("John"))
        d = OdinDiff(deletions=[PathValue("missing", OdinString("x"))])
        with pytest.raises(PatchError):
            odin.patch(a, d)

    def test_change_nonexistent_path(self):
        a = _doc(name=OdinString("John"))
        d = OdinDiff(modifications=[PathChange("missing", OdinString("a"), OdinString("b"))])
        with pytest.raises(PatchError):
            odin.patch(a, d)

    def test_move_nonexistent_source(self):
        a = _doc(name=OdinString("John"))
        d = OdinDiff(moves=[PathMove("missing", "target")])
        with pytest.raises(PatchError):
            odin.patch(a, d)


# ─────────────────────────────────────────────────────────────────────────────
# Roundtrip: patch(a, diff(a, b)) == b
# ─────────────────────────────────────────────────────────────────────────────


class TestDiffPatchRoundtrip:
    def _assert_docs_equal(self, a: OdinDocument, b: OdinDocument):
        """Assert two documents have the same assignments."""
        assert set(a.paths()) == set(b.paths()), f"Paths differ: {a.paths()} vs {b.paths()}"
        for p in a.paths():
            assert a.get(p) == b.get(p), f"Values differ at {p}: {a.get(p)} vs {b.get(p)}"

    def test_roundtrip_additions(self):
        a = _doc(name=OdinString("John"))
        b = _doc(name=OdinString("John"), age=OdinInteger(30))
        d = odin.diff(a, b)
        result = odin.patch(a, d)
        self._assert_docs_equal(result, b)

    def test_roundtrip_deletions(self):
        a = _doc(name=OdinString("John"), age=OdinInteger(30))
        b = _doc(name=OdinString("John"))
        d = odin.diff(a, b)
        result = odin.patch(a, d)
        self._assert_docs_equal(result, b)

    def test_roundtrip_modifications(self):
        a = _doc(name=OdinString("John"))
        b = _doc(name=OdinString("Jane"))
        d = odin.diff(a, b)
        result = odin.patch(a, d)
        self._assert_docs_equal(result, b)

    def test_roundtrip_moves(self):
        a = _doc(old=OdinString("value"))
        b = _doc(new=OdinString("value"))
        d = odin.diff(a, b)
        result = odin.patch(a, d)
        self._assert_docs_equal(result, b)

    def test_roundtrip_mixed(self):
        a = _doc(name=OdinString("John"), age=OdinInteger(30), city=OdinString("Austin"))
        b = _doc(name=OdinString("Jane"), state=OdinString("TX"))
        d = odin.diff(a, b)
        result = odin.patch(a, d)
        self._assert_docs_equal(result, b)

    def test_roundtrip_empty_to_populated(self):
        a = _doc()
        b = _doc(x=OdinString("a"), y=OdinInteger(1))
        d = odin.diff(a, b)
        result = odin.patch(a, d)
        self._assert_docs_equal(result, b)

    def test_roundtrip_populated_to_empty(self):
        a = _doc(x=OdinString("a"), y=OdinInteger(1))
        b = _doc()
        d = odin.diff(a, b)
        result = odin.patch(a, d)
        self._assert_docs_equal(result, b)

    def test_roundtrip_all_types(self):
        a = _doc(
            s=OdinString("hello"),
            n=OdinNumber(3.14),
            i=OdinInteger(42),
            b=TRUE,
            z=NULL,
        )
        b = _doc(
            s=OdinString("world"),
            n=OdinNumber(2.71),
            i=OdinInteger(99),
            b=FALSE,
            z=OdinString("not null"),
        )
        d = odin.diff(a, b)
        result = odin.patch(a, d)
        self._assert_docs_equal(result, b)

    def test_roundtrip_identity(self):
        """Diff of identical docs + patch = identical doc."""
        a = _doc(name=OdinString("John"), age=OdinInteger(30))
        d = odin.diff(a, a)
        assert d.is_empty
        result = odin.patch(a, d)
        self._assert_docs_equal(result, a)
