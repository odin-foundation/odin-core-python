"""Tests for registry-aware (import-resolved) schema validation."""
import odin
from odin.resolver.import_resolver import ImportResolver
from odin.validation.schema_parser import parse_schema

CANONICAL = "C:/dev/odin/schemas/insurance/personal/auto/policy.schema.odin"


def _load_canonical():
    return parse_schema(open(CANONICAL, encoding="utf-8").read())


class TestImportParsing:
    def test_quotes_stripped_and_alias_captured(self):
        schema = _load_canonical()
        by_alias = {imp.alias: imp.path for imp in schema.imports}
        assert by_alias["types"] == "../../common/types.schema.odin"
        assert by_alias["pc"] == "../types.schema.odin"
        # No quotes leaked into the path
        assert all(not imp.path.startswith('"') for imp in schema.imports)

    def test_distinct_aliases_no_collision(self):
        schema = _load_canonical()
        reg = ImportResolver().resolve_schema(schema, CANONICAL).resolution.type_registry
        assert reg.get("types.policy_status") is not None
        assert reg.get("pc.excluded_driver") is not None
        # Two imports that both stem to "types" must not collide
        assert "types.policy_status" in reg
        assert "pc.excluded_driver" in reg


class TestCanonicalValidation:
    def test_no_spurious_v013(self):
        schema = _load_canonical()
        res = odin.validate_with_imports(odin.parse(""), schema, CANONICAL)
        v013 = [e for e in res.errors if e.code == "V013"]
        assert v013 == []

    def test_term_nested_in_policy_type(self):
        # {.term} nests into the @policy type, not the schema root.
        schema = _load_canonical()
        policy_fields = schema.types["policy"].fields
        assert "term.effective" in policy_fields
        assert "term.expiration" in policy_fields

    def test_empty_doc_has_no_root_required_errors(self):
        # term.* is inside @policy now, so an empty doc raises no root required errors.
        schema = _load_canonical()
        res = odin.validate_with_imports(odin.parse(""), schema, CANONICAL)
        v001 = [e for e in res.errors if e.code == "V001"]
        assert v001 == []

    def test_unresolved_alias_still_reported(self):
        schema = parse_schema(
            '{$}\nodin = "1.0.0"\nschema = "1.0.0"\n\n{Policy}\nstatus = !@missing.thing'
        )
        res = odin.validate(odin.parse(""), schema)
        assert any(e.code == "V013" and e.path == "Policy.status" for e in res.errors)
