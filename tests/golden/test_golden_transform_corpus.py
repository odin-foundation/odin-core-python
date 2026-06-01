"""Golden tests for the verified transform example corpus.

Each fixture under sdk/golden/transform-corpus/<family>/<id>.json stores a mapping
block (transform), an ODIN source (input), and the exact engine-produced output
(expectedOutput). The standard odin->odin header is prepended, the transform is
executed, and result.formatted is compared to expectedOutput.

Error fixtures (family "error") instead assert that the declared T-code surfaces.
Fixtures marked tsOnly are TS-precision/format/RNG-specific and are skipped.
"""

import json
from pathlib import Path

import pytest

from tests.golden.conftest import find_golden_dir


def _corpus_dir():
    return find_golden_dir() / "transform-corpus"


def build_header(target_format="odin", target_options=None, header_fields=None):
    """Standard odin->target header prepended to each fixture transform."""
    meta = ['odin = "1.0.0"', 'transform = "1.0.0"', f'direction = "odin->{target_format}"']
    for k, v in (header_fields or {}).items():
        meta.append(f"{k} = {v}")
    target = [f'format = "{target_format}"']
    for k, v in (target_options or {}).items():
        target.append(f'{k} = "{v}"')
    return (
        "{$}\n"
        + "\n".join(meta)
        + "\n\n{$source}\nformat = \"odin\"\n\n{$target}\n"
        + "\n".join(target)
        + "\n\n"
    )


def header_for(fixture):
    return build_header(
        fixture.get("targetFormat", "odin"),
        fixture.get("targetOptions"),
        fixture.get("headerFields"),
    )


def discover_corpus_fixtures():
    """Walk <family>/*.json (manifest.json excluded), sorted by file path."""
    try:
        corpus = _corpus_dir()
    except RuntimeError:
        return []
    if not corpus.is_dir():
        return []
    loaded = []
    for family in sorted(p for p in corpus.iterdir() if p.is_dir()):
        for f in sorted(family.glob("*.json")):
            if f.name == "manifest.json":
                continue
            fixture = json.loads(f.read_text(encoding="utf-8"))
            loaded.append((fixture, f))
    params = []
    for fixture, f in sorted(loaded, key=lambda x: str(x[1])):
        params.append(pytest.param(fixture, f, id=f"{fixture['family']}/{fixture['id']}"))
    return params


def _parse_odin_input(raw: str):
    """Parse ODIN source the way the engine receives it: parse -> toJSON -> source."""
    import odin
    from odin.transform.source_parsers.json_parser import parse_json

    json_str = odin.to_json(odin.parse(raw), indent=None, omit_nulls=False)
    return parse_json(json_str)


@pytest.mark.golden
@pytest.mark.parametrize("fixture, file", discover_corpus_fixtures())
def test_golden_transform_corpus(fixture, file):
    """Execute a corpus fixture and compare formatted output (or surfaced error)."""
    import odin

    if fixture.get("tsOnly"):
        pytest.skip("tsOnly: TS-precision/format/RNG-specific fixture")

    transform_text = header_for(fixture) + fixture["transform"]
    source = _parse_odin_input(fixture["input"])

    if fixture["family"] == "error":
        if fixture.get("enforced") is False:
            pytest.skip("documented error gap (enforced=false)")
        code = fixture["code"]

        def fmt(items):
            return "\n".join(f"{getattr(e, 'code', None)} {getattr(e, 'message', '')}" for e in (items or []))

        surfaced = ""
        try:
            transform = odin.parse_transform(transform_text)
            result = odin.execute_transform(transform, source)
            surfaced = fmt(result.errors) + "\n" + fmt(result.warnings)
        except Exception as e:  # noqa: BLE001
            surfaced = f"{getattr(e, 'code', '')} {e}"
        assert code in surfaced, f"{code} not surfaced in {file}\nsurfaced: {surfaced!r}"
        return

    transform = odin.parse_transform(transform_text)
    result = odin.execute_transform(transform, source)
    assert not result.errors, (
        f"errors in {file}: "
        + ", ".join(f"[{e.code}] {e.message}" if e.code else e.message for e in result.errors)
    )

    actual = (result.formatted or "").replace("\r\n", "\n").rstrip()
    expected = fixture["expectedOutput"].replace("\r\n", "\n").rstrip()
    assert actual == expected, f"output mismatch in {file}"
