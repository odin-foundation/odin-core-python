"""ODIN Import Resolver — resolve @import directives in documents and schemas."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol

from odin.types.errors import OdinError


# ─────────────────────────────────────────────────────────────────────────────
# Error Codes
# ─────────────────────────────────────────────────────────────────────────────


class ImportErrorCodes:
    """Import/resolver error codes (I001-I099)."""
    I001 = "I001"  # Invalid import path (empty, null byte, remote URL)
    I003 = "I003"  # File extension not allowed
    I004 = "I004"  # Path escapes sandbox
    I005 = "I005"  # File too large
    I006 = "I006"  # File not found
    I008 = "I008"  # Failed to load file
    I011 = "I011"  # Circular import detected
    I012 = "I012"  # Maximum import depth exceeded
    I013 = "I013"  # Maximum total imports exceeded


class ImportError_(OdinError):
    """Exception during import resolution."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message, code)


# ─────────────────────────────────────────────────────────────────────────────
# File Reader Protocol
# ─────────────────────────────────────────────────────────────────────────────


class FileReader(Protocol):
    """Protocol for reading files during import resolution."""

    def read_file(self, path: str) -> str:
        """Read file contents as string."""
        ...

    def resolve_path(self, base_path: Optional[str], import_path: str) -> str:
        """Resolve an import path relative to a base path."""
        ...


class DefaultFileReader:
    """Default filesystem-based file reader."""

    def __init__(self, max_file_size: int = 10 * 1024 * 1024) -> None:
        self._max_file_size = max_file_size

    def read_file(self, path: str) -> str:
        """Read file contents as UTF-8 string."""
        file_path = Path(path)
        if not file_path.exists():
            raise ImportError_(f"File not found: {path}", ImportErrorCodes.I006)
        try:
            size = file_path.stat().st_size
            if size > self._max_file_size:
                raise ImportError_(
                    f"File too large: {size} bytes", ImportErrorCodes.I005
                )
            return file_path.read_text(encoding="utf-8")
        except ImportError_:
            raise
        except Exception as e:
            raise ImportError_(
                f"Failed to load file: {path} - {e}", ImportErrorCodes.I008
            )

    def resolve_path(self, base_path: Optional[str], import_path: str) -> str:
        """Resolve import path relative to the base file's directory."""
        if base_path:
            base_dir = Path(base_path).parent
        else:
            base_dir = Path(".")
        resolved = (base_dir / import_path).resolve()
        return str(resolved)


# ─────────────────────────────────────────────────────────────────────────────
# Options
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ResolverOptions:
    """Configuration options for import resolution."""
    sandbox_root: Optional[str] = None
    max_import_depth: int = 32
    schema_mode: bool = True
    allowed_extensions: List[str] = field(default_factory=lambda: [".odin"])
    max_file_size: int = 10 * 1024 * 1024

    @staticmethod
    def for_schemas() -> ResolverOptions:
        return ResolverOptions()

    @staticmethod
    def for_documents() -> ResolverOptions:
        return ResolverOptions(schema_mode=False)


# ─────────────────────────────────────────────────────────────────────────────
# Result Types
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ResolvedImport:
    """A single resolved import."""
    alias: Optional[str]
    path: str
    original_path: str
    schema: Any = None  # OdinSchema if schema mode
    document: Any = None  # OdinDocument if document mode
    line: int = 0


@dataclass
class ResolvedResult:
    """Result of resolving all imports."""
    imports: Dict[str, ResolvedImport] = field(default_factory=dict)
    type_registry: Dict[str, Any] = field(default_factory=dict)
    resolved_paths: List[str] = field(default_factory=list)


@dataclass
class ResolvedSchema:
    """A schema with its resolved imports."""
    schema: Any  # OdinSchema
    resolution: ResolvedResult


@dataclass
class ResolvedDocument:
    """A document with its resolved imports."""
    document: Any  # OdinDocument
    resolution: ResolvedResult


# ─────────────────────────────────────────────────────────────────────────────
# Circular Import Detector
# ─────────────────────────────────────────────────────────────────────────────


class _CircularDetector:
    """Track import chain to detect cycles."""

    def __init__(self) -> None:
        self._chain: List[str] = []
        self._chain_set: set[str] = set()

    def enter(self, path: str) -> None:
        normalized = _normalize_path(path)
        if normalized in self._chain_set:
            cycle = self._format_cycle(normalized)
            raise ImportError_(
                f"Circular import detected: {cycle}", ImportErrorCodes.I011
            )
        self._chain_set.add(normalized)
        self._chain.append(normalized)

    def exit(self) -> None:
        if self._chain:
            last = self._chain.pop()
            self._chain_set.discard(last)

    def is_circular(self, path: str) -> bool:
        return _normalize_path(path) in self._chain_set

    def _format_cycle(self, path: str) -> str:
        cycle: List[str] = []
        found = False
        for p in self._chain:
            if p.lower() == path.lower():
                found = True
            if found:
                cycle.append(p)
        cycle.append(path)
        return " -> ".join(cycle)


# ─────────────────────────────────────────────────────────────────────────────
# Cache Entry
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class _CachedEntry:
    schema: Any = None
    document: Any = None


# ─────────────────────────────────────────────────────────────────────────────
# Import Resolver
# ─────────────────────────────────────────────────────────────────────────────


class ImportResolver:
    """Resolves @import directives in ODIN schemas and documents.

    Supports:
    - File-based resolution from filesystem
    - Relative path resolution from importing document's directory
    - Circular import detection
    - Caching of resolved documents
    - Sandbox security (path escaping prevention)
    """

    def __init__(
        self,
        reader: Optional[FileReader] = None,
        options: Optional[ResolverOptions] = None,
    ) -> None:
        self._options = options or ResolverOptions()
        self._reader: FileReader = reader or DefaultFileReader(self._options.max_file_size)
        self._cache: Dict[str, _CachedEntry] = {}
        self._total_files_loaded = 0

        # Injectable parsers (for testing)
        self._document_parser: Optional[Callable[[str], Any]] = None
        self._schema_parser: Optional[Callable[[str], Any]] = None

    @property
    def options(self) -> ResolverOptions:
        return self._options

    def set_document_parser(self, parser: Callable[[str], Any]) -> None:
        """Set custom document parser (useful for testing)."""
        self._document_parser = parser

    def set_schema_parser(self, parser: Callable[[str], Any]) -> None:
        """Set custom schema parser (useful for testing)."""
        self._schema_parser = parser

    # ─── Public API ──────────────────────────────────────────────────────

    def resolve_schema(self, schema: Any, base_path: Optional[str] = None) -> ResolvedSchema:
        """Resolve all imports in a schema."""
        self._total_files_loaded = 0
        imports: Dict[str, ResolvedImport] = {}
        type_registry: Dict[str, Any] = {}
        resolved_paths: List[str] = []
        detector = _CircularDetector()

        # Copy existing types from schema
        if hasattr(schema, "types") and schema.types:
            type_registry.update(schema.types)

        # Resolve imports
        if hasattr(schema, "imports") and schema.imports:
            for imp_path in schema.imports:
                # Schema imports are stored as plain paths
                alias = _path_to_alias(imp_path)
                self._resolve_schema_import(
                    imp_path, alias, base_path, detector, 0,
                    imports, type_registry, resolved_paths,
                )

        resolution = ResolvedResult(
            imports=imports,
            type_registry=type_registry,
            resolved_paths=resolved_paths,
        )
        return ResolvedSchema(schema=schema, resolution=resolution)

    def resolve_document(self, document: Any, base_path: Optional[str] = None) -> ResolvedDocument:
        """Resolve all imports in a document."""
        self._total_files_loaded = 0
        imports: Dict[str, ResolvedImport] = {}
        type_registry: Dict[str, Any] = {}
        resolved_paths: List[str] = []
        detector = _CircularDetector()

        doc_imports = getattr(document, "imports", None) or []
        for imp in doc_imports:
            imp_path = imp if isinstance(imp, str) else getattr(imp, "path", str(imp))
            alias = imp if isinstance(imp, str) else getattr(imp, "alias", imp_path)
            self._resolve_document_import(
                imp_path, alias, base_path, detector, 0,
                imports, type_registry, resolved_paths,
            )

        resolution = ResolvedResult(
            imports=imports,
            type_registry=type_registry,
            resolved_paths=resolved_paths,
        )
        return ResolvedDocument(document=document, resolution=resolution)

    def resolve_schema_file(self, file_path: str) -> ResolvedSchema:
        """Load and resolve a schema file."""
        content = self._load_file(file_path)
        schema = self._parse_schema_text(content)
        return self.resolve_schema(schema, file_path)

    def resolve_document_file(self, file_path: str) -> ResolvedDocument:
        """Load and resolve a document file."""
        content = self._load_file(file_path)
        doc = self._parse_document_text(content)
        return self.resolve_document(doc, file_path)

    def resolve(self, path: str, base_path: Optional[str] = None) -> Any:
        """Resolve a single import path and return the parsed document/schema."""
        resolved_path = self._resolve_import_path(base_path, path)
        cache_key = _normalize_path(resolved_path)
        cached = self._cache.get(cache_key)
        if cached:
            return cached.schema or cached.document

        content = self._load_file(resolved_path)
        if self._options.schema_mode:
            result = self._parse_schema_text(content)
            self._cache[cache_key] = _CachedEntry(schema=result)
        else:
            result = self._parse_document_text(content)
            self._cache[cache_key] = _CachedEntry(document=result)
        return result

    # ─── Internal Resolution ─────────────────────────────────────────────

    def _resolve_schema_import(
        self,
        imp_path: str,
        alias: str,
        base_path: Optional[str],
        detector: _CircularDetector,
        depth: int,
        imports: Dict[str, ResolvedImport],
        type_registry: Dict[str, Any],
        resolved_paths: List[str],
    ) -> None:
        if depth > self._options.max_import_depth:
            raise ImportError_(
                f"Maximum import depth exceeded: {depth}",
                ImportErrorCodes.I012,
            )

        resolved_path = self._resolve_import_path(base_path, imp_path)
        normalized_path = _normalize_path(resolved_path)

        if detector.is_circular(normalized_path):
            raise ImportError_(
                f"Circular import detected: {normalized_path}",
                ImportErrorCodes.I011,
            )

        if alias in imports:
            return

        self._total_files_loaded += 1
        if self._total_files_loaded > 100:
            raise ImportError_(
                "Maximum total imports exceeded", ImportErrorCodes.I013
            )

        detector.enter(normalized_path)
        try:
            cache_key = _normalize_path(resolved_path)
            cached = self._cache.get(cache_key)
            if cached and cached.schema is not None:
                imported_schema = cached.schema
            else:
                content = self._load_file(resolved_path)
                imported_schema = self._parse_schema_text(content)
                self._cache[cache_key] = _CachedEntry(schema=imported_schema)

            resolved_paths.append(resolved_path)

            # Register imported types with namespace prefix
            namespace = alias
            if hasattr(imported_schema, "types") and imported_schema.types:
                for type_name, type_def in imported_schema.types.items():
                    qualified_name = f"{namespace}_{type_name}"
                    type_registry[qualified_name] = type_def

            # Recursively resolve nested imports
            if hasattr(imported_schema, "imports") and imported_schema.imports:
                for nested_path in imported_schema.imports:
                    nested_alias = _path_to_alias(nested_path)
                    self._resolve_schema_import(
                        nested_path, nested_alias, resolved_path, detector,
                        depth + 1, imports, type_registry, resolved_paths,
                    )

            imports[alias] = ResolvedImport(
                alias=alias,
                path=resolved_path,
                original_path=imp_path,
                schema=imported_schema,
            )
        finally:
            detector.exit()

    def _resolve_document_import(
        self,
        imp_path: str,
        alias: str,
        base_path: Optional[str],
        detector: _CircularDetector,
        depth: int,
        imports: Dict[str, ResolvedImport],
        type_registry: Dict[str, Any],
        resolved_paths: List[str],
    ) -> None:
        if depth > self._options.max_import_depth:
            raise ImportError_(
                f"Maximum import depth exceeded: {depth}",
                ImportErrorCodes.I012,
            )

        resolved_path = self._resolve_import_path(base_path, imp_path)
        normalized_path = _normalize_path(resolved_path)

        if detector.is_circular(normalized_path):
            raise ImportError_(
                f"Circular import detected: {normalized_path}",
                ImportErrorCodes.I011,
            )

        if alias in imports:
            return

        self._total_files_loaded += 1
        if self._total_files_loaded > 100:
            raise ImportError_(
                "Maximum total imports exceeded", ImportErrorCodes.I013
            )

        detector.enter(normalized_path)
        try:
            cache_key = _normalize_path(resolved_path)
            cached = self._cache.get(cache_key)
            if cached and cached.document is not None:
                imported_doc = cached.document
            else:
                content = self._load_file(resolved_path)
                imported_doc = self._parse_document_text(content)
                self._cache[cache_key] = _CachedEntry(document=imported_doc)

            resolved_paths.append(resolved_path)

            # Recursively resolve nested imports
            doc_imports = getattr(imported_doc, "imports", None) or []
            for nested_imp in doc_imports:
                nested_path = nested_imp if isinstance(nested_imp, str) else getattr(nested_imp, "path", str(nested_imp))
                nested_alias = nested_imp if isinstance(nested_imp, str) else getattr(nested_imp, "alias", nested_path)
                self._resolve_document_import(
                    nested_path, nested_alias, resolved_path, detector,
                    depth + 1, imports, type_registry, resolved_paths,
                )

            imports[alias] = ResolvedImport(
                alias=alias,
                path=resolved_path,
                original_path=imp_path,
                document=imported_doc,
            )
        finally:
            detector.exit()

    # ─── Parsing Helpers ─────────────────────────────────────────────────

    def _parse_document_text(self, content: str) -> Any:
        if self._document_parser:
            return self._document_parser(content)
        from odin.parsing.parser import OdinParser
        parser = OdinParser()
        return parser.parse(content)

    def _parse_schema_text(self, content: str) -> Any:
        if self._schema_parser:
            return self._schema_parser(content)
        from odin.validation.schema_parser import parse_schema
        return parse_schema(content)

    # ─── Path Resolution ─────────────────────────────────────────────────

    def _resolve_import_path(self, base_path: Optional[str], import_path: str) -> str:
        if not import_path:
            raise ImportError_("Empty import path", ImportErrorCodes.I001)

        if "\0" in import_path:
            raise ImportError_("Null byte in import path", ImportErrorCodes.I001)

        if import_path.startswith("http://") or import_path.startswith("https://"):
            raise ImportError_("Remote URLs not supported", ImportErrorCodes.I001)

        # Check file extension
        valid_ext = False
        import_lower = import_path.lower()
        for ext in self._options.allowed_extensions:
            if import_lower.endswith(ext.lower()):
                valid_ext = True
                break
        if not valid_ext:
            raise ImportError_(
                f"File extension not allowed: {import_path}",
                ImportErrorCodes.I003,
            )

        resolved = self._reader.resolve_path(base_path, import_path)

        # Sandbox check
        if self._options.sandbox_root:
            sandbox = Path(self._options.sandbox_root).resolve()
            resolved_path = Path(resolved).resolve()
            if not str(resolved_path).startswith(str(sandbox)):
                raise ImportError_(
                    f"Path escapes sandbox: {import_path}",
                    ImportErrorCodes.I004,
                )

        return resolved

    def _load_file(self, path: str) -> str:
        return self._reader.read_file(path)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _normalize_path(path: str) -> str:
    """Normalize path for comparison (forward slashes, lowercase)."""
    return path.replace("\\", "/").lower()


def _path_to_alias(path: str) -> str:
    """Extract an alias from an import path (stem of filename)."""
    # "./types.odin" -> "types"
    name = Path(path).stem
    return name


# ─────────────────────────────────────────────────────────────────────────────
# Legacy compatibility
# ─────────────────────────────────────────────────────────────────────────────


def resolve_imports(schema: Any, base_path: Optional[str] = None) -> Any:
    """Legacy convenience function for resolving schema imports."""
    resolver = ImportResolver()
    result = resolver.resolve_schema(schema, base_path)
    return result.schema
