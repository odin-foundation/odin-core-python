"""Unit tests for typed tabular cells — guards against column drop/shift."""

import odin
from odin.types.values import OdinInteger, OdinString, OdinCurrency


def _doc(text: str):
    return odin.parse(text)


# ── Happy path ──────────────────────────────────────────────────────────────


class TestTypedCellsHappy:
    def test_integer_first_column_keeps_trailing_column(self):
        doc = _doc('{rows[] : qty, name}\n##5, "widget"\n##12, "gadget"')
        assert isinstance(doc.get("rows[0].qty"), OdinInteger)
        assert doc.get("rows[0].qty").value == 5
        assert doc.get("rows[0].name").value == "widget"
        assert doc.get("rows[1].qty").value == 12
        assert doc.get("rows[1].name").value == "gadget"

    def test_mixed_typed_order(self):
        doc = _doc(
            '{items[] : qty, name, price}\n'
            '##10, "Widget", #$5.99\n'
            '##5, "Gadget", #$12.50'
        )
        assert isinstance(doc.get("items[0].qty"), OdinInteger)
        assert isinstance(doc.get("items[0].name"), OdinString)
        assert isinstance(doc.get("items[0].price"), OdinCurrency)
        assert doc.get("items[0].qty").value == 10
        assert doc.get("items[0].name").value == "Widget"
        assert float(doc.get("items[1].price").value) == 12.50


# ── Edge cases ──────────────────────────────────────────────────────────────


class TestTypedCellsEdge:
    def test_negative_integer_keeps_sign_and_column(self):
        doc = _doc('{temps[] : label, value}\n"low", ##-5\n"high", ##42')
        assert doc.get("temps[0].label").value == "low"
        assert doc.get("temps[0].value").value == -5
        assert doc.get("temps[1].value").value == 42

    def test_all_typed_row_keeps_every_column(self):
        doc = _doc('{points[] : x, y, z}\n##1, ##2, ##3\n##-4, ##5, ##-6')
        assert doc.get("points[0].x").value == 1
        assert doc.get("points[0].y").value == 2
        assert doc.get("points[0].z").value == 3
        assert doc.get("points[1].x").value == -4
        assert doc.get("points[1].z").value == -6

    def test_single_typed_column_produces_object_array(self):
        doc = _doc('{counts[] : value}\n##42\n##0')
        assert doc.get("counts[0].value").value == 42
        assert doc.get("counts[1].value").value == 0

    def test_large_integer_full_precision(self):
        doc = _doc('{big[] : label, n}\n"max", ##9007199254740991')
        assert doc.get("big[0].n").value == 9007199254740991
