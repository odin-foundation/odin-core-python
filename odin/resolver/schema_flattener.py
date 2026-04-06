"""Flatten ODIN schemas by resolving imports and merging types."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from odin.types.schema import (
    OdinSchema,
    SchemaField,
    SchemaType,
    SchemaArray,
    SchemaObjectConstraint,
    TypeRefType,
    ReferenceType,
    UnionType,
)
from odin.resolver.import_resolver import (
    ImportResolver,
    ResolverOptions,
    ResolvedSchema,
    ResolvedResult,
)


# ─────────────────────────────────────────────────────────────────────────────
# Options
# ─────────────────────────────────────────────────────────────────────────────


class ConflictResolution(Enum):
    """How to handle type name conflicts during flattening."""
    NAMESPACE = "namespace"
    OVERWRITE = "overwrite"
    ERROR = "error"


@dataclass
class FlattenerOptions:
    """Configuration for schema flattening."""
    conflict_resolution: ConflictResolution = ConflictResolution.NAMESPACE
    tree_shake: bool = True
    resolver_options: ResolverOptions = field(default_factory=ResolverOptions)


# ─────────────────────────────────────────────────────────────────────────────
# Result
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class FlattenedResult:
    """Result of flattening a schema."""
    schema: OdinSchema
    source_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Schema Flattener
# ─────────────────────────────────────────────────────────────────────────────


class SchemaFlattener:
    """Flatten a schema by resolving imports and merging type definitions.

    Features:
    - Process @import directives
    - Merge imported type definitions into the main schema
    - Detect and report namespace conflicts
    - Tree-shake unused imported types
    """

    def __init__(self, options: Optional[FlattenerOptions] = None) -> None:
        self._options = options or FlattenerOptions()
        self._warnings: List[str] = []
        self._type_source_map: Dict[str, Optional[str]] = {}  # typeName -> namespace (None = local)
        self._referenced_types: Set[str] = set()

    # ─── Public API ──────────────────────────────────────────────────────

    def flatten_file(self, file_path: str) -> FlattenedResult:
        """Load a schema file and flatten it (resolve all imports)."""
        resolver = ImportResolver(options=self._options.resolver_options)
        resolved = resolver.resolve_schema_file(file_path)
        return self.flatten_resolved(resolved)

    def flatten_resolved(self, resolved: ResolvedSchema) -> FlattenedResult:
        """Flatten a previously resolved schema."""
        self._warnings.clear()
        self._type_source_map.clear()
        self._referenced_types.clear()

        schema = resolved.schema
        resolution = resolved.resolution

        # 1. Build type source map
        self._build_type_source_map(resolution, schema)

        # 2. Merge all types
        merged_types = self._merge_types(resolution, schema)

        # 3. Merge fields, arrays, constraints
        merged_fields = self._merge_fields(resolution, schema)
        merged_arrays = self._merge_arrays(resolution, schema)
        merged_constraints = self._merge_constraints(resolution, schema)

        # 4. Tree shake if enabled
        if self._options.tree_shake and merged_types:
            self._collect_referenced_types(
                schema, merged_types, merged_fields, merged_arrays
            )
            original_count = len(merged_types)
            merged_types = {
                k: v for k, v in merged_types.items()
                if k in self._referenced_types
            }
            removed = original_count - len(merged_types)
            if removed > 0:
                self._warnings.append(
                    f"Tree shaking removed {removed} unused types"
                )

        # 5. Build flattened schema
        flat_schema = OdinSchema(
            metadata=schema.metadata.copy() if schema.metadata else {},
            types=merged_types,
            fields=merged_fields,
            arrays=merged_arrays,
            imports=[],  # imports are resolved, so clear them
            constraints=merged_constraints,
        )

        source_files = list(resolution.resolved_paths)
        return FlattenedResult(
            schema=flat_schema,
            source_files=source_files,
            warnings=list(self._warnings),
        )

    # ─── Type Source Map ─────────────────────────────────────────────────

    def _build_type_source_map(
        self, resolution: ResolvedResult, schema: OdinSchema
    ) -> None:
        for name in resolution.type_registry:
            underscore = name.find("_")
            if underscore >= 0:
                ns = name[:underscore]
                type_name = name[underscore + 1:]
                self._type_source_map[type_name] = ns

        if schema.types:
            for type_name in schema.types:
                self._type_source_map[type_name] = None

    # ─── Merge Types ─────────────────────────────────────────────────────

    def _merge_types(
        self, resolution: ResolvedResult, schema: OdinSchema
    ) -> Dict[str, SchemaType]:
        merged: Dict[str, SchemaType] = {}

        # Imported types first
        for name, type_def in resolution.type_registry.items():
            self._add_type(merged, name, type_def)

        # Primary schema types win
        if schema.types:
            for name, type_def in schema.types.items():
                self._add_type(merged, name, type_def)

        return merged

    def _add_type(
        self,
        merged: Dict[str, SchemaType],
        qualified_name: str,
        schema_type: SchemaType,
    ) -> None:
        if qualified_name in merged:
            if self._options.conflict_resolution == ConflictResolution.ERROR:
                self._warnings.append(f"Type name conflict: {qualified_name}")
                return
            elif self._options.conflict_resolution == ConflictResolution.OVERWRITE:
                self._warnings.append(
                    f"Type '{qualified_name}' overwritten by import"
                )
            else:
                self._warnings.append(
                    f"Type '{qualified_name}' conflicts with existing type"
                )

        merged[qualified_name] = schema_type

    # ─── Merge Fields ────────────────────────────────────────────────────

    def _merge_fields(
        self, resolution: ResolvedResult, schema: OdinSchema
    ) -> Dict[str, SchemaField]:
        merged: Dict[str, SchemaField] = {}

        for imp_entry in resolution.imports.values():
            imp_schema = imp_entry.schema
            if imp_schema and hasattr(imp_schema, "fields") and imp_schema.fields:
                for path, field_def in imp_schema.fields.items():
                    qualified_path = path
                    if (
                        self._options.conflict_resolution == ConflictResolution.NAMESPACE
                        and imp_entry.alias
                    ):
                        qualified_path = f"{imp_entry.alias}_{path}"
                    merged[qualified_path] = field_def

        if schema.fields:
            merged.update(schema.fields)

        return merged

    # ─── Merge Arrays ────────────────────────────────────────────────────

    def _merge_arrays(
        self, resolution: ResolvedResult, schema: OdinSchema
    ) -> Dict[str, SchemaArray]:
        merged: Dict[str, SchemaArray] = {}

        for imp_entry in resolution.imports.values():
            imp_schema = imp_entry.schema
            if imp_schema and hasattr(imp_schema, "arrays") and imp_schema.arrays:
                for path, arr in imp_schema.arrays.items():
                    qualified_path = path
                    if (
                        self._options.conflict_resolution == ConflictResolution.NAMESPACE
                        and imp_entry.alias
                    ):
                        qualified_path = f"{imp_entry.alias}_{path}"
                    merged[qualified_path] = arr

        if schema.arrays:
            merged.update(schema.arrays)

        return merged

    # ─── Merge Constraints ───────────────────────────────────────────────

    def _merge_constraints(
        self, resolution: ResolvedResult, schema: OdinSchema
    ) -> Dict[str, List[SchemaObjectConstraint]]:
        merged: Dict[str, List[SchemaObjectConstraint]] = {}

        for imp_entry in resolution.imports.values():
            imp_schema = imp_entry.schema
            if imp_schema and hasattr(imp_schema, "constraints") and imp_schema.constraints:
                for path, constraints in imp_schema.constraints.items():
                    qualified_path = path
                    if (
                        self._options.conflict_resolution == ConflictResolution.NAMESPACE
                        and imp_entry.alias
                    ):
                        qualified_path = f"{imp_entry.alias}_{path}"
                    merged.setdefault(qualified_path, []).extend(constraints)

        if schema.constraints:
            for path, constraints in schema.constraints.items():
                merged.setdefault(path, []).extend(constraints)

        return merged

    # ─── Tree Shaking ────────────────────────────────────────────────────

    def _collect_referenced_types(
        self,
        primary_schema: OdinSchema,
        all_types: Dict[str, SchemaType],
        merged_fields: Dict[str, SchemaField],
        merged_arrays: Dict[str, SchemaArray],
    ) -> None:
        # Start with all types defined in the primary schema
        if primary_schema.types:
            for type_name in primary_schema.types:
                self._mark_type_referenced(
                    type_name, all_types, merged_fields, merged_arrays, set()
                )

        # Types referenced from primary schema fields
        if primary_schema.fields:
            for field_def in primary_schema.fields.values():
                self._collect_type_refs_from_field_type(
                    field_def.field_type, all_types, merged_fields, merged_arrays, set()
                )

    def _mark_type_referenced(
        self,
        type_name: str,
        all_types: Dict[str, SchemaType],
        merged_fields: Dict[str, SchemaField],
        merged_arrays: Dict[str, SchemaArray],
        processed: Set[str],
    ) -> None:
        if type_name in self._referenced_types:
            return
        self._referenced_types.add(type_name)

        type_def = all_types.get(type_name)
        if type_def:
            for field_def in type_def.fields.values():
                self._collect_type_refs_from_field_type(
                    field_def.field_type, all_types, merged_fields, merged_arrays, processed
                )
            if type_def.base_type:
                self._mark_type_referenced(
                    type_def.base_type, all_types, merged_fields, merged_arrays, processed
                )

    def _collect_type_refs_from_field_type(
        self,
        field_type: Any,
        all_types: Dict[str, SchemaType],
        merged_fields: Dict[str, SchemaField],
        merged_arrays: Dict[str, SchemaArray],
        processed: Set[str],
    ) -> None:
        if field_type is None:
            return

        target = None
        if isinstance(field_type, TypeRefType):
            target = field_type.name
        elif isinstance(field_type, ReferenceType):
            target = field_type.target_path
        elif isinstance(field_type, UnionType):
            for member in field_type.types:
                self._collect_type_refs_from_field_type(
                    member, all_types, merged_fields, merged_arrays, processed
                )
            return
        else:
            return

        if target:
            self._mark_type_referenced(
                target, all_types, merged_fields, merged_arrays, processed
            )


# ─────────────────────────────────────────────────────────────────────────────
# Convenience Function
# ─────────────────────────────────────────────────────────────────────────────


def flatten_schema(
    schema: OdinSchema,
    resolver: Optional[ImportResolver] = None,
    options: Optional[FlattenerOptions] = None,
) -> OdinSchema:
    """Flatten a schema by resolving imports and merging type definitions.

    Args:
        schema: The schema to flatten.
        resolver: Import resolver to use (creates default if None).
        options: Flattener options.

    Returns:
        A new OdinSchema with all imports resolved and types merged.
    """
    if resolver is None:
        resolver = ImportResolver()

    resolved = resolver.resolve_schema(schema)
    flattener = SchemaFlattener(options)
    result = flattener.flatten_resolved(resolved)
    return result.schema
