"""Tests for the tabular serializer's ragged sub-array rule."""
import json
import re
import odin
from odin.types.document import OdinDocumentBuilder
from odin.types.values import OdinString, OdinInteger


def _build(pairs):
    b = OdinDocumentBuilder()
    for path, value in pairs:
        b.set(path, value)
    return b.build()


class TestRejectsTabularForRaggedSubArrays:
    def test_ragged_string_subarrays_emit_nested_form(self):
        doc = _build([
            ("records[0].name", OdinString("Alice")),
            ("records[0].tags[0]", OdinString("red")),
            ("records[0].tags[1]", OdinString("green")),
            ("records[0].tags[2]", OdinString("blue")),
            ("records[1].name", OdinString("Bob")),
            ("records[1].tags[0]", OdinString("yellow")),
        ])
        text = odin.dumps(doc)

        assert not re.search(r"\{records\[\][^}]*tags\[2\]", text)
        assert "{records[0]}" in text
        assert "{records[1]}" in text
        assert re.search(r"\{\.tags\[\]\s*:\s*~\}", text)

    def test_ragged_numeric_subarrays_emit_nested_form(self):
        doc = _build([
            ("points[0].label", OdinString("A")),
            ("points[0].coords[0]", OdinInteger(1)),
            ("points[0].coords[1]", OdinInteger(2)),
            ("points[1].label", OdinString("B")),
            ("points[1].coords[0]", OdinInteger(3)),
            ("points[1].coords[1]", OdinInteger(4)),
            ("points[1].coords[2]", OdinInteger(5)),
            ("points[1].coords[3]", OdinInteger(6)),
        ])
        text = odin.dumps(doc)

        assert not re.search(r"\{points\[\][^}]*coords\[3\]", text)
        assert "{points[0]}" in text
        assert "{points[1]}" in text
        assert re.search(r"\{\.coords\[\]\s*:\s*~\}", text)

    def test_ragged_subarrays_round_trip(self):
        # The serializer emits nested-form `{.subarr[] : ~}` blocks for
        # records with ragged sub-arrays. The parser must read them back
        # losslessly.
        doc = _build([
            ("entries[0].slug", OdinString("a/one")),
            ("entries[0].title", OdinString("One")),
            ("entries[0].types[0]", OdinString("alpha")),
            ("entries[0].types[1]", OdinString("beta")),
            ("entries[0].fields[0]", OdinString("id")),
            ("entries[0].fields[1]", OdinString("name")),
            ("entries[0].fields[2]", OdinString("desc")),
            ("entries[1].slug", OdinString("b/two")),
            ("entries[1].title", OdinString("Two")),
            ("entries[1].types[0]", OdinString("gamma")),
            ("entries[1].fields[0]", OdinString("id")),
        ])
        text = odin.dumps(doc)

        assert re.search(r"\{\.types\[\]\s*:\s*~\}", text)
        assert re.search(r"\{\.fields\[\]\s*:\s*~\}", text)

        parsed = odin.loads(text)
        assert odin.to_json(parsed) == odin.to_json(doc)


class TestPreservesTabularForDenseUniformShapes:
    def test_tabular_for_records_with_only_scalar_columns(self):
        doc = _build([
            ("rows[0].name", OdinString("Alice")),
            ("rows[0].age", OdinInteger(30)),
            ("rows[1].name", OdinString("Bob")),
            ("rows[1].age", OdinInteger(25)),
        ])
        text = odin.dumps(doc)

        assert re.search(r"\{rows\[\]\s*:\s*[^}]*name[^}]*age", text)
        assert "{rows[0]}" not in text

    def test_tabular_for_records_with_uniform_width_subarrays(self):
        doc = _build([
            ("points[0].label", OdinString("A")),
            ("points[0].coords[0]", OdinInteger(1)),
            ("points[0].coords[1]", OdinInteger(2)),
            ("points[1].label", OdinString("B")),
            ("points[1].coords[0]", OdinInteger(3)),
            ("points[1].coords[1]", OdinInteger(4)),
        ])
        text = odin.dumps(doc)

        assert re.search(r"\{points\[\]\s*:[^}]*coords\[0\][^}]*coords\[1\]", text)
        assert "{points[0]}" not in text


class TestSizeGuarantee:
    def test_output_smaller_than_padded_tabular_form(self):
        pairs = []
        for r in range(20):
            pairs.append((f"entries[{r}].slug", OdinString(f"record/{r}")))
            pairs.append((f"entries[{r}].title", OdinString(f"Record {r}")))
            tag_count = 1 + r * 2
            for t in range(tag_count):
                pairs.append((f"entries[{r}].tags[{t}]", OdinString(f"tag-{r}-{t}")))
        doc = _build(pairs)
        text = odin.dumps(doc)

        assert "tags[39]" not in text
        assert "{entries[0]}" in text
        assert "{entries[19]}" in text
        assert re.search(r"\{\.tags\[\]\s*:\s*~\}", text)

        # Round-trip: parser must reconstruct the same document.
        parsed = odin.loads(text)
        assert odin.to_json(parsed) == odin.to_json(doc)
