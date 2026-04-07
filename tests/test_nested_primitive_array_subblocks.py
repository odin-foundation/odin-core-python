"""Round-trip tests for relative `{.subarr[] : ~}` headers nested under an absolute record block."""
import odin
from odin.types.document import OdinDocumentBuilder
from odin.types.values import OdinString, OdinInteger


def _build(pairs):
    b = OdinDocumentBuilder()
    for path, value in pairs:
        b.set(path, value)
    return b.build()


class TestNestedPrimitiveArraySubBlockRoundTrip:
    def test_string_subarrays_round_trip(self):
        doc = _build([
            ("entries[0].slug", OdinString("a/one")),
            ("entries[0].title", OdinString("One")),
            ("entries[0].types[0]", OdinString("alpha")),
            ("entries[0].types[1]", OdinString("beta")),
            ("entries[0].fields[0]", OdinString("id")),
            ("entries[0].fields[1]", OdinString("name")),
            ("entries[0].fields[2]", OdinString("description")),
            ("entries[1].slug", OdinString("b/two")),
            ("entries[1].title", OdinString("Two")),
            ("entries[1].types[0]", OdinString("gamma")),
            ("entries[2].slug", OdinString("c/three")),
            ("entries[2].title", OdinString("Three")),
            ("entries[2].fields[0]", OdinString("only")),
        ])
        text = odin.dumps(doc)
        parsed = odin.loads(text)
        assert odin.to_json(parsed) == odin.to_json(doc)

    def test_integer_subarrays_round_trip(self):
        doc = _build([
            ("points[0].label", OdinString("A")),
            ("points[0].coords[0]", OdinInteger(1)),
            ("points[0].coords[1]", OdinInteger(2)),
            ("points[0].coords[2]", OdinInteger(3)),
            ("points[1].label", OdinString("B")),
            ("points[1].coords[0]", OdinInteger(10)),
            ("points[2].label", OdinString("C")),
            ("points[2].coords[0]", OdinInteger(100)),
            ("points[2].coords[1]", OdinInteger(200)),
        ])
        text = odin.dumps(doc)
        parsed = odin.loads(text)
        assert odin.to_json(parsed) == odin.to_json(doc)

    def test_parses_handwritten_relative_primitive_array_block(self):
        text = (
            "{entries[0]}\n"
            'slug = "a/one"\n'
            'title = "One"\n'
            "{.types[] : ~}\n"
            '"alpha"\n'
            '"beta"\n'
            "{.fields[] : ~}\n"
            '"id"\n'
            '"name"\n'
            '"description"\n'
            "\n"
            "{entries[1]}\n"
            'slug = "b/two"\n'
            "{.types[] : ~}\n"
            '"gamma"\n'
        )
        doc = odin.loads(text)
        result = odin.to_json(doc)
        import json
        as_dict = json.loads(result) if isinstance(result, str) else result
        assert as_dict["entries"][0]["types"] == ["alpha", "beta"]
        assert as_dict["entries"][0]["fields"] == ["id", "name", "description"]
        assert as_dict["entries"][1]["types"] == ["gamma"]
