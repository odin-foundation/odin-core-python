"""Tests for encoding verbs."""

import pytest
from odin.transform.dyn_value import DynValue, DynType
from odin.transform.engine import TransformEngine, VerbContext
from odin.transform.verb_registry import create_default_registry


def _engine():
    return TransformEngine(create_default_registry())


def invoke(verb_name, *raw_args):
    engine = _engine()
    args = [_to_dyn(a) for a in raw_args]
    return engine.invoke_verb(verb_name, args)


def _to_dyn(v):
    if isinstance(v, DynValue):
        return v
    if v is None:
        return DynValue.of_null()
    if isinstance(v, bool):
        return DynValue.of_bool(v)
    if isinstance(v, int):
        return DynValue.of_integer(v)
    if isinstance(v, float):
        return DynValue.of_float(v)
    if isinstance(v, str):
        return DynValue.of_string(v)
    if isinstance(v, list):
        return DynValue.of_array([_to_dyn(x) for x in v])
    if isinstance(v, dict):
        return DynValue.of_object({k: _to_dyn(val) for k, val in v.items()})
    return DynValue.of_string(str(v))


# ── base64Encode / base64Decode ───────────────────────────────────────────────

def test_base64_encode():
    r = invoke("base64Encode", "Hello World")
    assert r.as_string() == "SGVsbG8gV29ybGQ="

def test_base64_decode():
    r = invoke("base64Decode", "SGVsbG8gV29ybGQ=")
    assert r.as_string() == "Hello World"

def test_base64_roundtrip():
    encoded = invoke("base64Encode", "test data")
    decoded = invoke("base64Decode", encoded)
    assert decoded.as_string() == "test data"

def test_base64_encode_null():
    assert invoke("base64Encode", None).is_null()

def test_base64_decode_null():
    assert invoke("base64Decode", None).is_null()

def test_base64_decode_invalid():
    assert invoke("base64Decode", "!!!invalid!!!").is_null()


# ── urlEncode / urlDecode ─────────────────────────────────────────────────────

def test_url_encode():
    r = invoke("urlEncode", "hello world")
    assert r.as_string() == "hello%20world"

def test_url_decode():
    r = invoke("urlDecode", "hello%20world")
    assert r.as_string() == "hello world"

def test_url_encode_special():
    r = invoke("urlEncode", "a=1&b=2")
    assert "=" not in r.as_string().replace("%3D", "x")

def test_url_encode_null():
    assert invoke("urlEncode", None).is_null()

def test_url_decode_null():
    assert invoke("urlDecode", None).is_null()


# ── hexEncode / hexDecode ─────────────────────────────────────────────────────

def test_hex_encode():
    r = invoke("hexEncode", "ABC")
    assert r.as_string() == "414243"

def test_hex_decode():
    r = invoke("hexDecode", "414243")
    assert r.as_string() == "ABC"

def test_hex_roundtrip():
    encoded = invoke("hexEncode", "test")
    decoded = invoke("hexDecode", encoded)
    assert decoded.as_string() == "test"

def test_hex_encode_null():
    assert invoke("hexEncode", None).is_null()

def test_hex_decode_null():
    assert invoke("hexDecode", None).is_null()

def test_hex_decode_odd_length():
    assert invoke("hexDecode", "414").is_null()

def test_hex_decode_invalid():
    assert invoke("hexDecode", "GHIJ").is_null()


# ── sha256 / sha1 / sha512 / md5 / crc32 ────────────────────────────────────

def test_sha256():
    r = invoke("sha256", "hello")
    assert r.as_string() == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

def test_sha256_null():
    assert invoke("sha256", None).is_null()

def test_sha1():
    r = invoke("sha1", "hello")
    assert r.as_string() == "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d"

def test_sha512():
    r = invoke("sha512", "hello")
    assert len(r.as_string()) == 128

def test_md5():
    r = invoke("md5", "hello")
    assert r.as_string() == "5d41402abc4b2a76b9719d911017c592"

def test_md5_null():
    assert invoke("md5", None).is_null()

def test_crc32():
    r = invoke("crc32", "hello")
    assert len(r.as_string()) == 8
    # Known CRC32 for "hello"
    assert r.as_string() == "3610a686"

def test_crc32_null():
    assert invoke("crc32", None).is_null()


# ── jsonEncode / jsonDecode ───────────────────────────────────────────────────

def test_json_encode_object():
    r = invoke("jsonEncode", _to_dyn({"name": "Alice", "age": 30}))
    import json
    parsed = json.loads(r.as_string())
    assert parsed["name"] == "Alice"
    assert parsed["age"] == 30

def test_json_encode_string():
    r = invoke("jsonEncode", "hello \"world\"")
    assert '"hello \\"world\\""' == r.as_string()

def test_json_encode_null():
    assert invoke("jsonEncode", None).is_null()

def test_json_decode_object():
    r = invoke("jsonDecode", '{"name":"Alice","age":30}')
    assert r.is_object()
    assert r.get("name").as_string() == "Alice"
    assert r.get("age").as_int() == 30

def test_json_decode_invalid():
    assert invoke("jsonDecode", "not json").is_null()

def test_json_decode_null():
    assert invoke("jsonDecode", None).is_null()


# ── jsonPath ──────────────────────────────────────────────────────────────────

def test_json_path_simple():
    obj = _to_dyn({"name": "Alice", "address": {"city": "NYC"}})
    r = invoke("jsonPath", obj, "$.address.city")
    assert r.as_string() == "NYC"

def test_json_path_array():
    obj = _to_dyn({"items": [10, 20, 30]})
    r = invoke("jsonPath", obj, "$.items[1]")
    assert r.as_int() == 20

def test_json_path_null():
    assert invoke("jsonPath", None, "$.name").is_null()

def test_json_path_missing():
    obj = _to_dyn({"name": "Alice"})
    r = invoke("jsonPath", obj, "$.address.city")
    assert r.is_null()
