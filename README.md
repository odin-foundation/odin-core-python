# odin-foundation

[![PyPI](https://img.shields.io/pypi/v/odin-foundation)](https://pypi.org/project/odin-foundation) [![License](https://img.shields.io/pypi/l/odin-foundation)](https://github.com/odin-foundation/odin-core-python/blob/main/LICENSE)

Official Python SDK for [ODIN](https://odin.foundation) (Open Data Interchange Notation) — a canonical data model for transporting meaning between systems, standards, and AI.

## Install

```bash
pip install odin-foundation
```

**Requires Python 3.8+**

## Quick Start

```python
import odin

doc = odin.parse("""
{policy}
number = "PAP-2024-001"
effective = 2024-06-01
premium = #$747.50
active = ?true
""")

print(doc["policy.number"])   # "PAP-2024-001"
print(doc["policy.premium"])  # 747.50

text = odin.dumps(doc)
```

## Core API

| Function | Description | Example |
|----------|-------------|---------|
| `odin.parse(text)` | Parse ODIN text into a document | `doc = odin.parse(src)` |
| `odin.dumps(doc)` | Serialize document to ODIN text | `text = odin.dumps(doc)` |
| `odin.loads(text)` | Alias for `parse` (Python-idiomatic) | `doc = odin.loads(src)` |
| `odin.stringify(doc)` | Alias for `dumps` | `text = odin.stringify(doc)` |
| `odin.canonicalize(doc)` | Deterministic bytes for hashing/signatures | `b = odin.canonicalize(doc)` |
| `odin.validate(doc, schema)` | Validate against an ODIN schema | `result = odin.validate(doc, schema)` |
| `odin.parse_schema(text)` | Parse a schema definition | `schema = odin.parse_schema(src)` |
| `odin.diff(a, b)` | Structured diff between two documents | `changes = odin.diff(doc_a, doc_b)` |
| `odin.patch(doc, diff)` | Apply a diff to a document | `updated = odin.patch(doc, changes)` |
| `odin.parse_transform(text)` | Parse a transform specification | `tx = odin.parse_transform(src)` |
| `odin.execute_transform(tx, source)` | Run a transform on data | `out = odin.execute_transform(tx, doc)` |
| `doc.to_json()` | Export to JSON | `json_str = doc.to_json()` |
| `doc.to_xml()` | Export to XML | `xml_str = doc.to_xml()` |
| `doc.to_csv()` | Export to CSV | `csv_str = doc.to_csv()` |
| `odin.dumps(doc)` | Export to ODIN | `odin_str = odin.dumps(doc)` |
| `odin.builder()` | Fluent document builder | `odin.builder().section("policy")...` |

## Schema Validation

```python
import odin

schema = odin.parse_schema("""
{policy}
!number : string
!effective : date
!premium : currency
active : boolean
""")

doc = odin.parse(source)
result = odin.validate(doc, schema)

if not result.valid:
    for error in result.errors:
        print(error)
```

## Transforms

```python
import odin

transform = odin.parse_transform("""
map policy -> record
  policy.number -> record.id
  policy.premium -> record.amount
""")

result = odin.execute_transform(transform, doc)
```

## Export

```python
odin_str = odin.dumps(doc)    # ODIN string
json_str = doc.to_json()     # JSON string
xml_str  = doc.to_xml()      # XML string
csv_str  = doc.to_csv()      # CSV string
```

## Builder

```python
doc = (odin.builder()
    .section("policy")
    .set("number", "PAP-2024-001")
    .set("effective", date(2024, 6, 1))
    .set("premium", odin.currency(747.50))
    .set("active", True)
    .build())
```

## Testing

Tests use [pytest](https://docs.pytest.org/) and the shared golden test suite:

```bash
pytest
```

## Links

- [.Odin Foundation Website](https://odin.foundation)
- [GitHub](https://github.com/odin-foundation/odin)
- [Golden Test Suite](https://github.com/odin-foundation/odin/tree/main/sdk/golden)
- [License (Apache 2.0)](https://github.com/odin-foundation/odin/blob/main/LICENSE)
