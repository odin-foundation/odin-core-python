"""Tests for ODIN import resolver and schema flattener."""
import os
import tempfile

import pytest

from odin.resolver.import_resolver import (
    ImportResolver,
    ResolverOptions,
    ResolvedImport,
    ResolvedResult,
    ResolvedSchema,
    ResolvedDocument,
    ImportError_,
    ImportErrorCodes,
    DefaultFileReader,
)
from odin.resolver.schema_flattener import (
    SchemaFlattener,
    FlattenerOptions,
    FlattenedResult,
    ConflictResolution,
    flatten_schema,
)
from odin.types.schema import (
    OdinSchema,
    SchemaField,
    SchemaType,
    SchemaArray,
    StringType,
    IntegerType,
    TypeRefType,
)


# ─── Factory / Constructor Tests ─────────────────────────────────────────────


class TestImportResolverFactory:
    def test_create_default(self):
        resolver = ImportResolver()
        assert resolver is not None

    def test_create_with_options(self):
        opts = ResolverOptions()
        resolver = ImportResolver(options=opts)
        assert resolver is not None

    def test_for_schemas(self):
        opts = ResolverOptions.for_schemas()
        assert opts.schema_mode is True

    def test_for_documents(self):
        opts = ResolverOptions.for_documents()
        assert opts.schema_mode is False


# ─── Options Tests ───────────────────────────────────────────────────────────


class TestResolverOptions:
    def test_default_max_depth(self):
        opts = ResolverOptions()
        assert opts.max_import_depth == 32

    def test_default_max_file_size(self):
        opts = ResolverOptions()
        assert opts.max_file_size == 10 * 1024 * 1024

    def test_default_allowed_extensions(self):
        opts = ResolverOptions()
        assert ".odin" in opts.allowed_extensions

    def test_default_no_sandbox(self):
        opts = ResolverOptions()
        assert opts.sandbox_root is None

    def test_custom_options(self):
        opts = ResolverOptions(
            sandbox_root="/sandbox",
            max_import_depth=10,
            schema_mode=False,
            allowed_extensions=[".odin", ".schema"],
            max_file_size=1024,
        )
        assert opts.sandbox_root == "/sandbox"
        assert opts.max_import_depth == 10
        assert opts.max_file_size == 1024
        assert len(opts.allowed_extensions) == 2


# ─── Resolve Schema Tests ───────────────────────────────────────────────────


class TestResolveSchema:
    def test_resolve_schema_with_no_imports(self):
        schema = OdinSchema()
        resolver = ImportResolver()
        result = resolver.resolve_schema(schema, "/test/schema.odin")
        assert result is not None
        assert result.resolution is not None
        assert len(result.resolution.imports) == 0

    def test_resolve_schema_preserves_schema(self):
        schema = OdinSchema()
        resolver = ImportResolver()
        result = resolver.resolve_schema(schema, "/test/schema.odin")
        assert result.schema is schema

    def test_resolve_schema_has_type_registry(self):
        schema = OdinSchema()
        resolver = ImportResolver()
        result = resolver.resolve_schema(schema, "/test/schema.odin")
        assert result.resolution.type_registry is not None

    def test_resolve_schema_has_resolved_paths(self):
        schema = OdinSchema()
        resolver = ImportResolver()
        result = resolver.resolve_schema(schema, "/test/schema.odin")
        assert result.resolution.resolved_paths is not None


# ─── Path Security Tests ────────────────────────────────────────────────────


class TestPathSecurity:
    def test_empty_import_path_rejected(self):
        schema = OdinSchema(imports=[""])
        resolver = ImportResolver()
        with pytest.raises(ImportError_) as exc_info:
            resolver.resolve_schema(schema, "/base/schema.odin")
        assert exc_info.value.code == "I001"

    def test_http_url_rejected(self):
        schema = OdinSchema(imports=["http://example.com/schema.odin"])
        resolver = ImportResolver()
        with pytest.raises(ImportError_) as exc_info:
            resolver.resolve_schema(schema, "/base/schema.odin")
        assert exc_info.value.code == "I001"

    def test_https_url_rejected(self):
        schema = OdinSchema(imports=["https://example.com/schema.odin"])
        resolver = ImportResolver()
        with pytest.raises(ImportError_) as exc_info:
            resolver.resolve_schema(schema, "/base/schema.odin")
        assert exc_info.value.code == "I001"

    def test_invalid_extension_rejected(self):
        schema = OdinSchema(imports=["./evil.exe"])
        resolver = ImportResolver()
        with pytest.raises(ImportError_) as exc_info:
            resolver.resolve_schema(schema, "/base/schema.odin")
        assert exc_info.value.code == "I003"

    def test_null_byte_in_path_rejected(self):
        schema = OdinSchema(imports=["./file\0.odin"])
        resolver = ImportResolver()
        with pytest.raises(ImportError_) as exc_info:
            resolver.resolve_schema(schema, "/base/schema.odin")
        assert exc_info.value.code == "I001"


# ─── File Loading Error Tests ───────────────────────────────────────────────


class TestFileLoadingErrors:
    def test_missing_file_throws(self):
        resolver = ImportResolver()
        with pytest.raises(ImportError_):
            resolver.resolve_schema_file("/nonexistent/path/to/file.odin")

    def test_missing_file_error_code(self):
        resolver = ImportResolver()
        with pytest.raises(ImportError_) as exc_info:
            resolver.resolve_schema_file("/nonexistent/path/schema.odin")
        assert exc_info.value.code in ("I006", "I008")

    def test_missing_document_file_throws(self):
        resolver = ImportResolver(options=ResolverOptions.for_documents())
        with pytest.raises(ImportError_):
            resolver.resolve_document_file("/nonexistent/doc.odin")


# ─── File-Based Import Tests ────────────────────────────────────────────────


class TestFileBasedImports:
    def test_resolve_actual_schema_file(self, tmp_path):
        schema_content = '{$}\nodin = "1.0.0"\nschema = "1.0.0"\n\nname = ""'
        schema_file = tmp_path / "test.odin"
        schema_file.write_text(schema_content, encoding="utf-8")

        resolver = ImportResolver()
        result = resolver.resolve_schema_file(str(schema_file))
        assert result.schema is not None

    def test_resolve_actual_document_file(self, tmp_path):
        doc_content = 'name = "Alice"\nage = ##30'
        doc_file = tmp_path / "doc.odin"
        doc_file.write_text(doc_content, encoding="utf-8")

        resolver = ImportResolver(options=ResolverOptions.for_documents())
        result = resolver.resolve_document_file(str(doc_file))
        assert result.document is not None

    def test_import_chain_a_imports_b_imports_c(self, tmp_path):
        c_content = '{$}\nodin = "1.0.0"\nschema = "1.0.0"\n\n{@Phone}\nnumber = ""'
        (tmp_path / "c.odin").write_text(c_content, encoding="utf-8")

        b_content = '{$}\nodin = "1.0.0"\nschema = "1.0.0"\n@import ./c.odin\n\n{@Address}\nstreet = ""'
        (tmp_path / "b.odin").write_text(b_content, encoding="utf-8")

        a_content = '{$}\nodin = "1.0.0"\nschema = "1.0.0"\n@import ./b.odin\n\n{@Person}\nname = ""'
        (tmp_path / "a.odin").write_text(a_content, encoding="utf-8")

        resolver = ImportResolver()
        result = resolver.resolve_schema_file(str(tmp_path / "a.odin"))
        assert result is not None
        assert len(result.resolution.imports) > 0

    def test_file_too_large_rejected(self, tmp_path):
        opts = ResolverOptions(max_file_size=10)
        resolver = ImportResolver(options=opts)

        content = 'a_very_long_string_that_exceeds_10_bytes = "value"'
        file = tmp_path / "big.odin"
        file.write_text(content, encoding="utf-8")

        with pytest.raises(ImportError_):
            resolver.resolve_schema_file(str(file))


# ─── Circular Import Detection ──────────────────────────────────────────────


class TestCircularImportDetection:
    def test_self_import_detected(self, tmp_path):
        content = '{$}\nodin = "1.0.0"\n@import ./self.odin\n\nname = ""'
        (tmp_path / "self.odin").write_text(content, encoding="utf-8")

        resolver = ImportResolver()
        with pytest.raises(ImportError_) as exc_info:
            resolver.resolve_schema_file(str(tmp_path / "self.odin"))
        assert exc_info.value.code == "I011"

    def test_mutual_import_detected(self, tmp_path):
        a_content = '{$}\nodin = "1.0.0"\n@import ./b.odin\n\nname = ""'
        b_content = '{$}\nodin = "1.0.0"\n@import ./a.odin\n\nname = ""'
        (tmp_path / "a.odin").write_text(a_content, encoding="utf-8")
        (tmp_path / "b.odin").write_text(b_content, encoding="utf-8")

        resolver = ImportResolver()
        with pytest.raises(ImportError_) as exc_info:
            resolver.resolve_schema_file(str(tmp_path / "a.odin"))
        assert exc_info.value.code == "I011"


# ─── Sandbox Tests ──────────────────────────────────────────────────────────


class TestSandbox:
    def test_sandbox_options_set(self, tmp_path):
        opts = ResolverOptions(sandbox_root=str(tmp_path))
        assert opts.sandbox_root == str(tmp_path)

    def test_path_outside_sandbox_rejected(self, tmp_path):
        sandbox_dir = tmp_path / "sandbox"
        sandbox_dir.mkdir()

        opts = ResolverOptions(sandbox_root=str(sandbox_dir))
        resolver = ImportResolver(options=opts)

        schema = OdinSchema(imports=["../../outside.odin"])
        base = str(sandbox_dir / "base.odin")

        with pytest.raises(ImportError_) as exc_info:
            resolver.resolve_schema(schema, base)
        assert exc_info.value.code == "I004"


# ─── Result Types Tests ─────────────────────────────────────────────────────


class TestResultTypes:
    def test_resolved_import_fields(self):
        ri = ResolvedImport(alias="alias", path="/path", original_path="./rel", line=5)
        assert ri.alias == "alias"
        assert ri.path == "/path"
        assert ri.original_path == "./rel"
        assert ri.line == 5
        assert ri.schema is None
        assert ri.document is None

    def test_resolved_result_defaults(self):
        rr = ResolvedResult()
        assert len(rr.imports) == 0
        assert len(rr.type_registry) == 0
        assert len(rr.resolved_paths) == 0


# ─── Schema Flattener Factory Tests ──────────────────────────────────────────


class TestSchemaFlattenerFactory:
    def test_create_default(self):
        flattener = SchemaFlattener()
        assert flattener is not None

    def test_create_with_options(self):
        opts = FlattenerOptions()
        flattener = SchemaFlattener(opts)
        assert flattener is not None

    def test_create_with_none(self):
        flattener = SchemaFlattener(None)
        assert flattener is not None


# ─── Flattener Options Tests ────────────────────────────────────────────────


class TestFlattenerOptions:
    def test_default_conflict_resolution(self):
        opts = FlattenerOptions()
        assert opts.conflict_resolution == ConflictResolution.NAMESPACE

    def test_default_tree_shake(self):
        opts = FlattenerOptions()
        assert opts.tree_shake is True

    def test_custom_options(self):
        opts = FlattenerOptions(
            conflict_resolution=ConflictResolution.ERROR,
            tree_shake=False,
        )
        assert opts.conflict_resolution == ConflictResolution.ERROR
        assert opts.tree_shake is False

    def test_overwrite_mode(self):
        opts = FlattenerOptions(conflict_resolution=ConflictResolution.OVERWRITE)
        assert opts.conflict_resolution == ConflictResolution.OVERWRITE


# ─── Flatten Resolved Schema Tests ──────────────────────────────────────────


class TestFlattenResolved:
    def test_flatten_schema_with_no_imports(self):
        schema = OdinSchema()
        resolution = ResolvedResult()
        resolved = ResolvedSchema(schema=schema, resolution=resolution)

        flattener = SchemaFlattener()
        result = flattener.flatten_resolved(resolved)
        assert result.schema is not None
        assert len(result.source_files) == 0

    def test_flatten_preserves_metadata(self):
        schema = OdinSchema(metadata={"id": "test-id", "title": "Test"})
        resolution = ResolvedResult()
        resolved = ResolvedSchema(schema=schema, resolution=resolution)

        result = SchemaFlattener().flatten_resolved(resolved)
        assert result.schema.metadata.get("id") == "test-id"
        assert result.schema.metadata.get("title") == "Test"

    def test_flatten_removes_imports(self):
        schema = OdinSchema(imports=["./other.odin"])
        resolution = ResolvedResult()
        resolved = ResolvedSchema(schema=schema, resolution=resolution)

        result = SchemaFlattener().flatten_resolved(resolved)
        assert len(result.schema.imports) == 0

    def test_flatten_preserves_primary_types(self):
        person_type = SchemaType(
            name="Person",
            fields={"name": SchemaField(path="name", field_type=StringType())},
        )
        schema = OdinSchema(types={"Person": person_type})
        resolution = ResolvedResult()
        resolved = ResolvedSchema(schema=schema, resolution=resolution)

        opts = FlattenerOptions(tree_shake=False)
        result = SchemaFlattener(opts).flatten_resolved(resolved)
        assert "Person" in result.schema.types

    def test_flatten_merges_imported_types(self):
        address_type = SchemaType(
            name="Address",
            fields={"street": SchemaField(path="street", field_type=StringType())},
        )
        person_type = SchemaType(name="Person", fields={})
        schema = OdinSchema(types={"Person": person_type})

        type_registry = {"base_Address": address_type, "Person": person_type}
        resolution = ResolvedResult(type_registry=type_registry)
        resolved = ResolvedSchema(schema=schema, resolution=resolution)

        opts = FlattenerOptions(tree_shake=False)
        result = SchemaFlattener(opts).flatten_resolved(resolved)
        assert "Person" in result.schema.types
        assert "base_Address" in result.schema.types

    def test_flatten_preserves_fields(self):
        schema = OdinSchema(
            fields={"name": SchemaField(path="name", field_type=StringType())}
        )
        resolution = ResolvedResult()
        resolved = ResolvedSchema(schema=schema, resolution=resolution)

        result = SchemaFlattener().flatten_resolved(resolved)
        assert "name" in result.schema.fields

    def test_flatten_preserves_arrays(self):
        schema = OdinSchema(
            arrays={"items": SchemaArray(path="items")}
        )
        resolution = ResolvedResult()
        resolved = ResolvedSchema(schema=schema, resolution=resolution)

        result = SchemaFlattener().flatten_resolved(resolved)
        assert "items" in result.schema.arrays


# ─── Tree Shaking Tests ─────────────────────────────────────────────────────


class TestTreeShaking:
    def test_tree_shaking_keeps_primary_types(self):
        person_type = SchemaType(name="Person", fields={})
        schema = OdinSchema(types={"Person": person_type})

        unused_type = SchemaType(name="Unused", fields={})
        type_registry = {"Unused": unused_type, "Person": person_type}
        resolution = ResolvedResult(type_registry=type_registry)
        resolved = ResolvedSchema(schema=schema, resolution=resolution)

        opts = FlattenerOptions(tree_shake=True)
        result = SchemaFlattener(opts).flatten_resolved(resolved)
        assert "Person" in result.schema.types

    def test_no_tree_shaking_keeps_all(self):
        person = SchemaType(name="Person", fields={})
        extra = SchemaType(name="Extra", fields={})
        schema = OdinSchema(types={"Person": person, "Extra": extra})

        resolution = ResolvedResult()
        resolved = ResolvedSchema(schema=schema, resolution=resolution)

        opts = FlattenerOptions(tree_shake=False)
        result = SchemaFlattener(opts).flatten_resolved(resolved)
        assert len(result.schema.types) == 2


# ─── FlattenedResult Tests ──────────────────────────────────────────────────


class TestFlattenedResult:
    def test_result_has_warnings(self):
        schema = OdinSchema()
        resolution = ResolvedResult()
        resolved = ResolvedSchema(schema=schema, resolution=resolution)

        result = SchemaFlattener().flatten_resolved(resolved)
        assert result.warnings is not None

    def test_result_has_source_files(self):
        schema = OdinSchema()
        resolution = ResolvedResult(resolved_paths=["file1.odin"])
        resolved = ResolvedSchema(schema=schema, resolution=resolution)

        result = SchemaFlattener().flatten_resolved(resolved)
        assert len(result.source_files) == 1


# ─── File-Based Flatten Tests ───────────────────────────────────────────────


class TestFileBasedFlatten:
    def test_flatten_actual_file(self, tmp_path):
        schema_content = '{$}\nodin = "1.0.0"\nschema = "1.0.0"\n\n{@Person}\nname = ""'
        file = tmp_path / "schema.odin"
        file.write_text(schema_content, encoding="utf-8")

        flattener = SchemaFlattener()
        result = flattener.flatten_file(str(file))
        assert result.schema is not None

    def test_flatten_missing_file_throws(self):
        flattener = SchemaFlattener()
        with pytest.raises(ImportError_):
            flattener.flatten_file("/nonexistent/schema.odin")


# ─── Convenience Function Test ──────────────────────────────────────────────


class TestConvenienceFunction:
    def test_flatten_schema_function(self):
        schema = OdinSchema(
            types={"Person": SchemaType(name="Person", fields={})}
        )
        result = flatten_schema(schema)
        assert result is not None
        assert "Person" in result.types
