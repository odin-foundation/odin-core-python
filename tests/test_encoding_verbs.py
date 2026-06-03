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
    assert 'hello \\"world\\"' == r.as_string()

def test_json_encode_null():
    assert invoke("jsonEncode", None).is_null()

def test_json_decode_object():
    r = invoke("jsonDecode", '{"name":"Alice","age":30}')
    assert r.is_object()
    assert r.get("name").as_string() == "Alice"
    assert r.get("age").as_int() == 30

def test_json_decode_invalid():
    # An invalid escape sequence cannot be unescaped as a JSON string
    assert invoke("jsonDecode", "bad\\xescape").is_null()

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


# ── base64url ────────────────────────────────────────────────────────

def test_base64url_encode():
    r = invoke("base64urlEncode", "hello world?>>")
    assert r.as_string() == "aGVsbG8gd29ybGQ_Pj4"

def test_base64url_decode():
    r = invoke("base64urlDecode", "aGVsbG8gd29ybGQ_Pj4")
    assert r.as_string() == "hello world?>>"

def test_base64url_decode_tolerates_padding():
    r = invoke("base64urlDecode", "SGVsbG8=")
    assert r.as_string() == "Hello"

def test_base64url_decode_empty():
    r = invoke("base64urlDecode", "")
    assert r.as_string() == ""

def test_base64url_roundtrip():
    r = invoke("base64urlDecode", invoke("base64urlEncode", "hello world?>>"))
    assert r.as_string() == "hello world?>>"


# ── hmac ─────────────────────────────────────────────────────────────

def test_hmac_default_sha256():
    r = invoke("hmac", "message", "secret")
    assert r.as_string() == "8b5f48702995c1598c573db1e21866a9b825d4a794d169d7060a03605796360b"

def test_hmac_sha1():
    r = invoke("hmac", "message", "secret", "sha1")
    assert r.as_string() == "0caf649feee4953d87bf903ac1176c45e028df16"

def test_hmac_deterministic():
    assert invoke("hmac", "m", "k").as_string() == invoke("hmac", "m", "k").as_string()

def test_hmac_missing_key():
    assert invoke("hmac", "message").is_null()


# ── parseUrl ─────────────────────────────────────────────────────────

def test_parse_url_full():
    r = invoke("parseUrl", "https://example.com:8080/a/b?z=1&a=2#frag")
    obj = r.as_object()
    assert obj["scheme"].as_string() == "https"
    assert obj["host"].as_string() == "example.com"
    assert obj["port"].as_int() == 8080
    assert obj["path"].as_string() == "/a/b"
    assert obj["fragment"].as_string() == "frag"
    query = obj["query"].as_object()
    assert query["a"].as_string() == "2"
    assert query["z"].as_string() == "1"
    assert list(query.keys()) == ["a", "z"]

def test_parse_url_null_port():
    r = invoke("parseUrl", "https://example.com/x")
    obj = r.as_object()
    assert obj["port"].is_null()
    assert obj["fragment"].as_string() == ""

def test_parse_url_invalid():
    assert invoke("parseUrl", "not a url").is_null()


# ── buildUrl ─────────────────────────────────────────────────────────

def test_build_url():
    parts = {
        "scheme": "https", "host": "example.com", "port": 8080,
        "path": "/a/b", "query": {"z": 1, "a": 2}, "fragment": "frag",
    }
    r = invoke("buildUrl", parts)
    assert r.as_string() == "https://example.com:8080/a/b?a=2&z=1#frag"

def test_build_url_missing_scheme():
    assert invoke("buildUrl", {"host": "example.com"}).is_null()


# ── parseQuery ───────────────────────────────────────────────────────

def test_parse_query_sorts_keys():
    r = invoke("parseQuery", "z=1&a=2")
    obj = r.as_object()
    assert list(obj.keys()) == ["a", "z"]
    assert obj["a"].as_string() == "2"

def test_parse_query_leading_question_mark():
    r = invoke("parseQuery", "?a=2")
    assert r.as_object()["a"].as_string() == "2"


# ── buildQuery ───────────────────────────────────────────────────────

def test_build_query_sorts_keys():
    r = invoke("buildQuery", {"z": 1, "a": 2})
    assert r.as_string() == "a=2&z=1"

def test_build_query_skips_null():
    r = invoke("buildQuery", {"a": 1, "b": None})
    assert r.as_string() == "a=1"


# ── stableStringify ──────────────────────────────────────────────────

def test_stable_stringify_sorts_keys_recursively():
    r = invoke("stableStringify", {"b": 2, "a": 1, "nested": {"y": 2, "x": 1}})
    assert r.as_string() == '{"a":1,"b":2,"nested":{"x":1,"y":2}}'

def test_stable_stringify_array_order_preserved():
    r = invoke("stableStringify", [3, 1, 2])
    assert r.as_string() == "[3,1,2]"

def test_stable_stringify_scalar():
    r = invoke("stableStringify", 42)
    assert r.as_string() == "42"


# ── canonicalHash ────────────────────────────────────────────────────

def test_canonical_hash_value():
    r = invoke("canonicalHash", {"b": 2, "a": 1})
    assert r.as_string() == "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777"

def test_canonical_hash_order_independent():
    h1 = invoke("canonicalHash", {"b": 2, "a": 1}).as_string()
    h2 = invoke("canonicalHash", {"a": 1, "b": 2}).as_string()
    assert h1 == h2
