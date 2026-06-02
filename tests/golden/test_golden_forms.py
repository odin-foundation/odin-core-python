"""Golden forms tests - cross-language conformance suite."""

import json
from pathlib import Path

import pytest

import odin


def find_golden_dir():
    """Locate sdk/golden/ directory."""
    candidates = [
        Path(__file__).parent.parent.parent.parent / "golden",
        Path(__file__).parent.parent.parent / ".." / "golden",
    ]
    for p in candidates:
        resolved = p.resolve()
        if resolved.is_dir():
            return resolved
    raise RuntimeError("Cannot find sdk/golden/ directory")


GOLDEN_DIR = find_golden_dir()
FORMS_DIR = GOLDEN_DIR / "forms"

# Mapping from manifest attribute keys to model attribute names.
_ATTR_MAP = {
    "type": "type",
    "value": "value",
    "inputType": "input_type",
    "checked": "checked",
    "min": "min",
    "max": "max",
    "selected": "selected",
    "options": "options",
    "bind": "bind",
    "overflow": "overflow",
    "barcodeType": "barcode_type",
    "background": "background",
    "label": "label",
}


def load_forms_tests():
    """Load all form test cases from the forms manifest."""
    manifest = json.loads((FORMS_DIR / "manifest.json").read_text(encoding="utf-8"))
    suite = manifest.get("suite", "forms")
    tests = []
    for test in manifest.get("tests", []):
        test_id = f"{suite}::{test.get('id', 'unknown')}"
        tests.append(pytest.param(test, id=test_id))
    return tests


def _read_form(test):
    text = (FORMS_DIR / test["formFile"]).read_text(encoding="utf-8")
    return odin.parse_form(text)


def _find_element(elements, name):
    for el in elements:
        if el.name == name:
            return el
    return None


def _assert_parse(form, expect):
    if "pages" in expect:
        assert len(form.pages) == expect["pages"]

    if "margins" in expect:
        margin = form.page_defaults.margin
        for side, value in expect["margins"].items():
            assert getattr(margin, side) == value

    if "templates" in expect:
        for tpl_name, tpl_expect in expect["templates"].items():
            tpl = form.templates[tpl_name]
            assert tpl.page_template == tpl_expect["pageTemplate"]
            assert tpl.continues == tpl_expect["continues"]
            assert tpl.form_id == tpl_expect["formId"]
            assert [e.type for e in tpl.elements] == tpl_expect["elementTypes"]

    if "page0" in expect:
        page0 = expect["page0"]
        elements = form.pages[0].elements
        if "elementTypes" in page0:
            assert [e.type for e in elements] == page0["elementTypes"]
        for el_name, el_expect in page0.get("elements", {}).items():
            el = _find_element(elements, el_name)
            assert el is not None, f"element {el_name} not found"
            for key, value in el_expect.items():
                if key == "childCount":
                    assert len(el.children) == value
                    continue
                attr = _ATTR_MAP.get(key, key)
                got = getattr(el, attr)
                if isinstance(value, list):
                    got = list(got)
                assert got == value, f"{el_name}.{key}: {got!r} != {value!r}"


@pytest.mark.parametrize("test", load_forms_tests())
def test_golden_forms(test):
    form = _read_form(test)

    if "expectParse" in test:
        _assert_parse(form, test["expectParse"])

    if "renderContains" in test or "renderNotContains" in test:
        data = odin.parse(test["renderData"]) if "renderData" in test else None
        html = odin.render_form(form, data)
        for needle in test.get("renderContains", []):
            assert needle in html, f"missing: {needle!r}"
        for needle in test.get("renderNotContains", []):
            assert needle not in html, f"unexpected: {needle!r}"
