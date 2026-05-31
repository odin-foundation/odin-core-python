"""Tests for registry-aware (import-resolved) schema validation."""
import odin
from odin.resolver.import_resolver import ImportResolver
from odin.validation.schema_parser import parse_schema


class _MemReader:
    """In-memory file reader serving inline schemas by basename."""

    def __init__(self, files: dict[str, str]) -> None:
        self._files = files

    def read_file(self, path: str) -> str:
        return self._files[path.replace("\\", "/").split("/")[-1]]

    def resolve_path(self, base_path, import_path: str) -> str:
        return import_path


# A main schema that imports a tiny `types` schema and references one of its types.
_MAIN = (
    '@import "types.odin" as types\n'
    '{$}\nodin = "1.0.0"\nschema = "1.0.0"\n\n'
    "{policy}\nstatus_ref = @types.policy_status\n"
)
_TYPES = (
    '{$}\nodin = "1.0.0"\nschema = "1.0.0"\n\n'
    "{@policy_status}\nvalue = !\n"
)


class TestImportedTypeRef:
    def test_imported_typeref_resolved_with_registry(self):
        schema = parse_schema(_MAIN)
        resolver = ImportResolver(reader=_MemReader({"types.odin": _TYPES}))
        registry = resolver.resolve_schema(schema, "main.odin").resolution.type_registry
        assert "types.policy_status" in registry

        empty = odin.parse("")

        # Without the registry the imported type reference is unresolved (V013).
        baseline = odin.validate(empty, schema)
        assert any(e.code == "V013" for e in baseline.errors)

        # With the registry the reference resolves — no V013.
        result = odin.validate(empty, schema, type_registry=registry)
        assert [e for e in result.errors if e.code == "V013"] == []


class TestRelativeSubsection:
    def test_relative_subsection_nests_into_type(self):
        # {.term} nests its fields into the @policy type, not the schema root.
        schema = parse_schema(
            "{@policy}\nnumber = !\n{.term}\neffective = !date\nexpiration = !date\n"
        )
        policy_fields = schema.types["policy"].fields
        assert "term.effective" in policy_fields
        assert "term.expiration" in policy_fields
        # term.* must not leak to the schema root.
        assert "term.effective" not in schema.fields


class TestUnresolvedAlias:
    def test_unresolved_alias_still_reported(self):
        schema = parse_schema(
            '{$}\nodin = "1.0.0"\nschema = "1.0.0"\n\n{Policy}\nstatus = !@missing.thing'
        )
        res = odin.validate(odin.parse(""), schema)
        assert any(e.code == "V013" and e.path == "Policy.status" for e in res.errors)
