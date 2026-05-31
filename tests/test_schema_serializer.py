"""Tests for schema serializer — serialization and roundtrip."""
import pytest

from odin.validation.schema_parser import parse_schema
from odin.validation.schema_serializer import serialize_schema
from odin.types.schema import (
    OdinSchema,
    SchemaField,
    SchemaType,
    SchemaArray,
    StringType,
    BooleanType,
    NumberType,
    IntegerType,
    CurrencyType,
    PercentType,
    DateType,
    TimestampType,
    TimeType,
    DurationType,
    BinaryType,
    NullType,
    EnumType,
    TypeRefType,
    DecimalType,
    ReferenceType,
    BoundsConstraint,
    PatternConstraint,
    FormatConstraint,
    UniqueConstraint,
    SchemaInvariant,
    SchemaCardinality,
)


# ─── Basic Serialization ─────────────────────────────────────────────────────


class TestBasicSerialization:
    def test_empty_schema(self):
        schema = OdinSchema()
        result = serialize_schema(schema)
        assert result is not None

    def test_metadata_serialized(self):
        schema = OdinSchema(metadata={"odin": "1.0.0", "schema": "1.0.0"})
        result = serialize_schema(schema)
        assert "{$}" in result
        assert 'odin = "1.0.0"' in result
        assert 'schema = "1.0.0"' in result

    def test_import_directives(self):
        schema = OdinSchema(imports=["./types.odin", "./base.odin"])
        result = serialize_schema(schema)
        assert '@import "./types.odin"' in result
        assert '@import "./base.odin"' in result


# ─── Field Type Serialization ────────────────────────────────────────────────


class TestFieldTypeSerialization:
    def test_string_field(self):
        schema = OdinSchema(
            fields={"name": SchemaField(path="name", field_type=StringType())}
        )
        result = serialize_schema(schema)
        assert 'name = ""' in result

    def test_integer_field(self):
        schema = OdinSchema(
            fields={"count": SchemaField(path="count", field_type=IntegerType())}
        )
        result = serialize_schema(schema)
        assert "count = ##" in result

    def test_number_field(self):
        schema = OdinSchema(
            fields={"rate": SchemaField(path="rate", field_type=NumberType())}
        )
        result = serialize_schema(schema)
        assert "rate = #" in result

    def test_boolean_field(self):
        schema = OdinSchema(
            fields={"active": SchemaField(path="active", field_type=BooleanType())}
        )
        result = serialize_schema(schema)
        assert "active = ?" in result

    def test_currency_field(self):
        schema = OdinSchema(
            fields={"price": SchemaField(path="price", field_type=CurrencyType())}
        )
        result = serialize_schema(schema)
        assert "price = #$" in result

    def test_percent_field(self):
        schema = OdinSchema(
            fields={"rate": SchemaField(path="rate", field_type=PercentType())}
        )
        result = serialize_schema(schema)
        assert "rate = #%" in result

    def test_date_field(self):
        schema = OdinSchema(
            fields={"dob": SchemaField(path="dob", field_type=DateType())}
        )
        result = serialize_schema(schema)
        assert "dob = date" in result

    def test_timestamp_field(self):
        schema = OdinSchema(
            fields={"ts": SchemaField(path="ts", field_type=TimestampType())}
        )
        result = serialize_schema(schema)
        assert "ts = timestamp" in result

    def test_time_field(self):
        schema = OdinSchema(
            fields={"start": SchemaField(path="start", field_type=TimeType())}
        )
        result = serialize_schema(schema)
        assert "start = time" in result

    def test_duration_field(self):
        schema = OdinSchema(
            fields={"length": SchemaField(path="length", field_type=DurationType())}
        )
        result = serialize_schema(schema)
        assert "length = duration" in result

    def test_binary_field(self):
        schema = OdinSchema(
            fields={"data": SchemaField(path="data", field_type=BinaryType())}
        )
        result = serialize_schema(schema)
        assert "data = ^" in result

    def test_null_field(self):
        schema = OdinSchema(
            fields={"empty": SchemaField(path="empty", field_type=NullType())}
        )
        result = serialize_schema(schema)
        assert "empty = ~" in result


# ─── Modifier Serialization ──────────────────────────────────────────────────


class TestModifierSerialization:
    def test_required_modifier(self):
        schema = OdinSchema(
            fields={"name": SchemaField(path="name", field_type=StringType(), required=True)}
        )
        result = serialize_schema(schema)
        assert "name = !" in result

    def test_confidential_modifier(self):
        schema = OdinSchema(
            fields={"ssn": SchemaField(path="ssn", field_type=StringType(), redacted=True)}
        )
        result = serialize_schema(schema)
        assert "ssn = *" in result

    def test_deprecated_modifier(self):
        schema = OdinSchema(
            fields={"old": SchemaField(path="old", field_type=StringType(), deprecated=True)}
        )
        result = serialize_schema(schema)
        assert "old = -" in result


# ─── Constraint Serialization ────────────────────────────────────────────────


class TestConstraintSerialization:
    def test_bounds_constraint(self):
        schema = OdinSchema(
            fields={
                "age": SchemaField(
                    path="age",
                    field_type=IntegerType(),
                    constraints=[BoundsConstraint(min=0, max=150)],
                )
            }
        )
        result = serialize_schema(schema)
        assert ":(0..150)" in result

    def test_pattern_constraint(self):
        schema = OdinSchema(
            fields={
                "code": SchemaField(
                    path="code",
                    field_type=StringType(),
                    constraints=[PatternConstraint(pattern="^[A-Z]{3}$")],
                )
            }
        )
        result = serialize_schema(schema)
        assert ":/^[A-Z]{3}$/" in result

    def test_format_constraint(self):
        schema = OdinSchema(
            fields={
                "email": SchemaField(
                    path="email",
                    field_type=StringType(),
                    constraints=[FormatConstraint(format="email")],
                )
            }
        )
        result = serialize_schema(schema)
        assert ":format email" in result


# ─── Roundtrip Tests ─────────────────────────────────────────────────────────


class TestRoundtrip:
    def _roundtrip(self, text: str) -> OdinSchema:
        """Parse, serialize, then parse again."""
        schema1 = parse_schema(text)
        serialized = serialize_schema(schema1)
        schema2 = parse_schema(serialized)
        return schema2

    def test_roundtrip_simple_schema(self):
        text = "{$}\nodin = \"1.0.0\"\nschema = \"1.0.0\"\n\n{Person}\nname = \"\"\nage = ##"
        schema = self._roundtrip(text)
        assert "Person.name" in schema.fields
        assert "Person.age" in schema.fields

    def test_roundtrip_preserves_metadata(self):
        text = '{$}\nodin = "1.0.0"\nschema = "1.0.0"'
        schema = self._roundtrip(text)
        assert schema.metadata.get("odin") == "1.0.0"

    def test_roundtrip_type_definition(self):
        text = "{$}\nodin = \"1.0.0\"\n\n{@Person}\nname = \"\"\nage = ##"
        schema = self._roundtrip(text)
        assert "Person" in schema.types
        assert "name" in schema.types["Person"].fields
        assert "age" in schema.types["Person"].fields

    def test_roundtrip_boolean_field(self):
        text = "{$}\nodin = \"1.0.0\"\n\n{Root}\nactive = ?"
        schema = self._roundtrip(text)
        assert "Root.active" in schema.fields
        assert isinstance(schema.fields["Root.active"].field_type, BooleanType)

    def test_roundtrip_currency_field(self):
        text = "{$}\nodin = \"1.0.0\"\n\n{Root}\nprice = #$"
        schema = self._roundtrip(text)
        assert "Root.price" in schema.fields
        assert isinstance(schema.fields["Root.price"].field_type, CurrencyType)

    def test_serialize_and_reparse(self):
        text = "{$}\nodin = \"1.0.0\"\nschema = \"1.0.0\"\n\n{@Person}\nname = !\"\""
        original = parse_schema(text)
        serialized = serialize_schema(original)
        assert serialized is not None
        assert len(serialized) > 0
