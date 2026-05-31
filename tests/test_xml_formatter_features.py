"""XML transform formatter: namespaces + emitTypeHints coverage."""

from odin.transform.transform_parser import parse_transform
from odin.transform.engine import TransformEngine
from odin.transform.verb_registry import create_default_registry


def _format(transform_text: str, source: dict) -> str:
    """Parse a transform, run it, return the formatted XML string."""
    t = parse_transform(transform_text)
    engine = TransformEngine(create_default_registry())
    return engine.execute(t, source).formatted


# odin->xml transform with integer + currency typed fields.
_TYPED = """{$}
direction = "odin->xml"
target.format = "xml"
{Root}
Count = @count :type integer
Price = @price :type currency :currencyCode "USD"
"""

# Same, with type hints suppressed.
_TYPED_NO_HINTS = """{$}
direction = "odin->xml"
target.format = "xml"
{$target}
emitTypeHints = ?false
{Root}
Count = @count :type integer
Price = @price :type currency :currencyCode "USD"
"""

_TYPED_INPUT = {"count": 42, "price": 9.99}


# ── emitTypeHints default (true) ────────────────────────────────────────────────


class TestEmitTypeHintsDefault:
    def test_emits_type_attributes(self):
        xml = _format(_TYPED, _TYPED_INPUT)
        assert 'odin:type="integer"' in xml
        assert 'odin:type="currency"' in xml

    def test_emits_odin_namespace(self):
        xml = _format(_TYPED, _TYPED_INPUT)
        assert 'xmlns:odin="https://odin.foundation/ns"' in xml

    def test_values_present(self):
        xml = _format(_TYPED, _TYPED_INPUT)
        assert ">42<" in xml
        assert ">9.99<" in xml

    def test_emits_currency_code(self):
        import odin
        source = odin.parse("total = #$9.99:USD")
        transform = """{$}
direction = "odin->xml"
target.format = "xml"
{Root}
total = @total
"""
        t = parse_transform(transform)
        engine = TransformEngine(create_default_registry())
        xml = engine.execute(t, source).formatted
        assert 'odin:type="currency"' in xml
        assert 'odin:currencyCode="USD"' in xml

    def test_codeless_currency_is_currency_with_scale(self):
        import odin
        source = odin.parse("total = #$50.00")
        transform = """{$}
direction = "odin->xml"
target.format = "xml"
{Root}
total = @total
"""
        t = parse_transform(transform)
        engine = TransformEngine(create_default_registry())
        xml = engine.execute(t, source).formatted
        assert 'odin:type="currency"' in xml
        assert "odin:currencyCode" not in xml
        assert ">50.00<" in xml

    def test_coded_currency_preserves_scale(self):
        import odin
        source = odin.parse("total = #$9.99:USD")
        transform = """{$}
direction = "odin->xml"
target.format = "xml"
{Root}
total = @total
"""
        t = parse_transform(transform)
        engine = TransformEngine(create_default_registry())
        xml = engine.execute(t, source).formatted
        assert 'odin:type="currency"' in xml
        assert 'odin:currencyCode="USD"' in xml
        assert ">9.99<" in xml


# ── emitTypeHints = ?false ──────────────────────────────────────────────────────


class TestEmitTypeHintsFalse:
    def test_no_odin_attributes(self):
        xml = _format(_TYPED_NO_HINTS, _TYPED_INPUT)
        assert "odin:type" not in xml
        assert "odin:currencyCode" not in xml
        assert "xmlns:odin" not in xml
        assert "odin:" not in xml

    def test_values_still_present(self):
        xml = _format(_TYPED_NO_HINTS, _TYPED_INPUT)
        assert ">42<" in xml
        assert ">9.99<" in xml


# ── :ns prefixing + root xmlns ──────────────────────────────────────────────────


class TestNamespacePrefixing:
    _SINGLE = """{$}
direction = "odin->xml"
target.format = "xml"
{$target.namespace}
p = "urn:x"
{Root}
Alpha = @a :ns p
Beta = @b
"""

    def test_root_declares_namespace(self):
        xml = _format(self._SINGLE, {"a": "one", "b": "two"})
        assert 'xmlns:p="urn:x"' in xml

    def test_ns_field_is_prefixed(self):
        xml = _format(self._SINGLE, {"a": "one", "b": "two"})
        assert "<p:Alpha>one</p:Alpha>" in xml

    def test_plain_field_not_prefixed(self):
        xml = _format(self._SINGLE, {"a": "one", "b": "two"})
        assert "<Beta>two</Beta>" in xml
        assert "p:Beta" not in xml


# ── multiple namespaces ─────────────────────────────────────────────────────────


class TestMultipleNamespaces:
    _MULTI = """{$}
direction = "odin->xml"
target.format = "xml"
{$target.namespace}
p = "urn:x"
q = "urn:y"
{Root}
Alpha = @a :ns p
Beta = @b :ns q
"""

    def test_both_declared_on_root(self):
        xml = _format(self._MULTI, {"a": "one", "b": "two"})
        assert 'xmlns:p="urn:x"' in xml
        assert 'xmlns:q="urn:y"' in xml

    def test_both_prefixed(self):
        xml = _format(self._MULTI, {"a": "one", "b": "two"})
        assert "<p:Alpha>one</p:Alpha>" in xml
        assert "<q:Beta>two</q:Beta>" in xml


# ── namespace + emitTypeHints=false together ────────────────────────────────────


class TestNamespaceWithoutTypeHints:
    _COMBO = """{$}
direction = "odin->xml"
target.format = "xml"
{$target}
emitTypeHints = ?false
{$target.namespace}
p = "urn:x"
{Root}
Count = @count :type integer
Alpha = @a :ns p
"""

    def test_namespace_present_no_odin(self):
        xml = _format(self._COMBO, {"count": 42, "a": "one"})
        assert 'xmlns:p="urn:x"' in xml
        assert "<p:Alpha>one</p:Alpha>" in xml
        assert "odin:" not in xml

    def test_typed_value_still_rendered(self):
        xml = _format(self._COMBO, {"count": 42, "a": "one"})
        assert ">42<" in xml
