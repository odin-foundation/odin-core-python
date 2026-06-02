"""Unit tests for ODIN Forms parsing, rendering, units, and accessibility."""

import pytest

import odin
from odin.forms import (
    CheckboxElement,
    DateElement,
    MultiselectElement,
    RadioElement,
    RectElement,
    RegionElement,
    RenderFormOptions,
    SelectElement,
    SignatureElement,
    TextElement,
    TextFieldElement,
    contrast_ratio,
    field_aria_attrs,
    field_group_html,
    field_label_html,
    from_pixels,
    generate_field_id,
    generate_form_css,
    generate_print_css,
    meets_contrast_aa,
    parse_form,
    render_form,
    skip_link_html,
    sr_only_html,
    tab_order_sort,
    to_pixels,
)


# ─────────────────────────────────────────────────────────────────────────────
# Units
# ─────────────────────────────────────────────────────────────────────────────


def test_to_pixels_inch():
    assert to_pixels(1, "inch") == 96
    assert to_pixels(8.5, "inch") == 816


def test_to_pixels_cm_mm_pt():
    assert to_pixels(2.54, "cm") == 96
    assert to_pixels(25.4, "mm") == 96
    assert to_pixels(72, "pt") == 96


def test_from_pixels_roundtrip():
    assert from_pixels(96, "inch") == 1
    assert from_pixels(to_pixels(3.5, "inch"), "inch") == 3.5


def test_unknown_unit_raises():
    with pytest.raises(ValueError):
        to_pixels(1, "league")
    with pytest.raises(ValueError):
        from_pixels(1, "league")


# ─────────────────────────────────────────────────────────────────────────────
# Accessibility
# ─────────────────────────────────────────────────────────────────────────────


def test_generate_field_id():
    assert generate_field_id("ssn", 0) == "odin-field-0-ssn"
    assert generate_field_id("name", 2) == "odin-field-2-name"


def test_field_label_html():
    assert field_label_html("Name", "odin-field-0-name") == (
        '<label for="odin-field-0-name" class="odin-form-label">Name</label>'
    )


def test_field_aria_attrs_defaults_to_label():
    el = TextFieldElement(type="field.text", name="n", label="Full Name")
    attrs = field_aria_attrs(el, 0)
    assert attrs["id"] == "odin-field-0-n"
    assert attrs["aria-label"] == "Full Name"
    assert "aria-required" not in attrs


def test_field_aria_attrs_override_and_required():
    el = TextFieldElement(
        type="field.text", name="n", label="Visible", aria_label="Screen", required=True
    )
    attrs = field_aria_attrs(el, 0)
    assert attrs["aria-label"] == "Screen"
    assert attrs["aria-required"] == "true"


def test_field_group_html():
    html = field_group_html("gender", "Gender", "<input>")
    assert "<fieldset" in html
    assert "<legend class=\"odin-form-legend\">Gender</legend>" in html
    assert "<input>" in html


def test_tab_order_sort_excludes_non_fields_and_sorts():
    text = TextElement(type="text", name="t", x=0, y=0)
    a = TextFieldElement(type="field.text", name="a", x=5, y=2)
    b = TextFieldElement(type="field.text", name="b", x=1, y=1)
    c = TextFieldElement(type="field.text", name="c", x=9, y=1)
    ordered = tab_order_sort([text, a, b, c])
    assert [e.name for e in ordered] == ["b", "c", "a"]


def test_skip_link_and_sr_only():
    assert "#odin-form-content" in skip_link_html("My Form")
    assert sr_only_html("hidden") == '<span class="odin-form-sr-only">hidden</span>'


def test_contrast_ratio_extremes():
    assert round(contrast_ratio("#000000", "#ffffff"), 1) == 21.0
    assert contrast_ratio("#123456", "#123456") == 1.0


def test_meets_contrast_aa_thresholds():
    assert meets_contrast_aa("#000000", "#ffffff", 12) is True
    assert meets_contrast_aa("#777777", "#ffffff", 12) is False
    assert meets_contrast_aa("#777777", "#ffffff", 24) is True


# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────


def test_form_css_scoped():
    css = generate_form_css()
    assert ".odin-form" in css
    assert ".odin-form-input:focus" in css


def test_print_css_media_query():
    css = generate_print_css()
    assert "@media print" in css
    assert "page-break-after" in css


# ─────────────────────────────────────────────────────────────────────────────
# Parser — metadata and page defaults
# ─────────────────────────────────────────────────────────────────────────────


SIMPLE = """{$}
odin = "1.0.0"
forms = "1.0.0"
title = "Test Form"
id = "test_form"
lang = "en"

{$.page}
width = #8.5
height = #11
unit = "inch"
margin.top = #0.5
margin.left = #0.75

{$.screen}
scale = #1.5

{page[0]}
{.text.header}
x = #0.5
y = #0.5
content = "Hello"
font-size = ##14
font-weight = "bold"

{.field.name}
type = "text"
x = #0.6
y = #1.5
w = #3
h = #0.3
label = "Full Name"
required = ?true
bind = @insured.name
"""


def test_parse_metadata():
    form = parse_form(SIMPLE)
    assert form.metadata.title == "Test Form"
    assert form.metadata.id == "test_form"
    assert form.metadata.lang == "en"
    assert form.metadata.version == "1.0.0"


def test_parse_page_defaults_and_margins():
    form = parse_form(SIMPLE)
    pd = form.page_defaults
    assert pd.width == 8.5
    assert pd.height == 11
    assert pd.unit == "inch"
    assert pd.margin.top == 0.5
    assert pd.margin.left == 0.75
    assert pd.margin.right is None


def test_parse_screen_settings():
    form = parse_form(SIMPLE)
    assert form.screen.scale == 1.5


def test_parse_text_element():
    form = parse_form(SIMPLE)
    text = form.pages[0].elements[0]
    assert isinstance(text, TextElement)
    assert text.content == "Hello"
    assert text.font_size == 14
    assert text.font_weight == "bold"


def test_parse_text_field_bind_prefixed():
    form = parse_form(SIMPLE)
    field = form.pages[0].elements[1]
    assert isinstance(field, TextFieldElement)
    assert field.type == "field.text"
    assert field.required is True
    assert field.bind == "@insured.name"


# ─────────────────────────────────────────────────────────────────────────────
# Parser — field types
# ─────────────────────────────────────────────────────────────────────────────


def test_parse_checkbox_and_select_and_date():
    form = parse_form(
        open_fixture("inline-values.odin")
    )
    els = {e.name: e for e in form.pages[0].elements}
    assert isinstance(els["agree"], CheckboxElement)
    assert els["agree"].checked is True
    assert isinstance(els["dob"], DateElement)
    assert els["dob"].value == "1985-03-15"
    assert els["dob"].min == "1900-01-01"
    assert els["dob"].max == "2010-01-01"
    select = els["state"]
    assert isinstance(select, SelectElement)
    assert select.selected == "TX"
    assert select.options == ["AL", "CA", "NY", "TX"]


def test_parse_text_field_input_type():
    form = parse_form(open_fixture("inline-values.odin"))
    name = {e.name: e for e in form.pages[0].elements}["name"]
    assert name.value == "John Smith"
    assert name.input_type == "email"


def test_parse_radio_and_signature():
    form = parse_form(open_fixture("signature-radio.odin"))
    els = {e.name: e for e in form.pages[0].elements}
    radio = els["gender_f"]
    assert isinstance(radio, RadioElement)
    assert radio.group == "gender"
    assert radio.value == "F"
    sig = els["applicant_sig"]
    assert isinstance(sig, SignatureElement)
    assert sig.value == "^png:iVBORw0KGgo="


def test_parse_geometric_types():
    form = parse_form(open_fixture("geometric-elements.odin"))
    types = [e.type for e in form.pages[0].elements]
    assert types == ["circle", "ellipse", "polygon", "polyline", "path"]
    rect = parse_form(
        "{page[0]}\n{.rect.box}\nx=#1\ny=#2\nw=#3\nh=#4\nfill = \"#f5f5f5\"\nstroke = \"#cccccc\""
    ).pages[0].elements[0]
    assert isinstance(rect, RectElement)
    assert rect.fill == "#f5f5f5"
    assert rect.stroke == "#cccccc"


def test_parse_i18n_label_resolution():
    form = parse_form(open_fixture("content-elements.odin"))
    name = {e.name: e for e in form.pages[0].elements}["name"]
    assert name.label == "Full Legal Name"


def test_parse_background_image_and_barcode():
    form = parse_form(open_fixture("content-elements.odin"))
    els = {e.name: e for e in form.pages[0].elements}
    assert els["template"].background is True
    assert els["doc"].barcode_type == "qr"


# ─────────────────────────────────────────────────────────────────────────────
# Parser — regions and templates
# ─────────────────────────────────────────────────────────────────────────────


def test_parse_region_and_template():
    form = parse_form(open_fixture("page-template.odin"))
    region = {e.name: e for e in form.pages[0].elements}["vehicles"]
    assert isinstance(region, RegionElement)
    assert region.bind == "@policy.vehicles"
    assert region.max == 3
    assert region.overflow == "@tpl_vehicles_continued"
    assert len(region.children) == 1
    assert region.children[0].type == "field.text"
    assert region.children[0].y_offset == 1.8

    tpl = form.templates["tpl_vehicles_continued"]
    assert tpl.page_template is True
    assert tpl.continues == "region.vehicles"
    assert tpl.form_id == "PA (Cont)"


# ─────────────────────────────────────────────────────────────────────────────
# Renderer
# ─────────────────────────────────────────────────────────────────────────────


def test_render_wraps_form_and_style():
    form = parse_form(SIMPLE)
    html = render_form(form)
    assert html.startswith('<form role="form"')
    assert 'aria-label="Test Form"' in html
    assert "<style>" in html
    assert "@media print" in html


def test_render_class_name_option():
    form = parse_form(SIMPLE)
    html = render_form(form, None, RenderFormOptions(target="html", class_name="theme-x"))
    assert 'class="odin-form theme-x"' in html


def test_render_text_field_and_label():
    form = parse_form(SIMPLE)
    html = render_form(form)
    assert 'type="text"' in html
    assert 'id="odin-field-0-name"' in html
    assert "Full Name" in html
    assert " required" in html


def test_render_inline_values():
    form = parse_form(open_fixture("inline-values.odin"))
    html = render_form(form)
    assert 'type="email"' in html
    assert 'value="John Smith"' in html
    assert 'value="1985-03-15"' in html
    assert '<option value="TX" selected>' in html


def test_render_interpolation_and_overflow():
    form = parse_form(open_fixture("page-template.odin"))
    data = odin.parse(
        "{policy}\n{.vehicles[0]}\nvin = \"V0\"\n{.vehicles[1]}\nvin = \"V1\"\n"
        "{.vehicles[2]}\nvin = \"V2\"\n{.vehicles[3]}\nvin = \"V3\"\n{.vehicles[4]}\nvin = \"V4\""
    )
    html = render_form(form, data)
    assert "Page 1 of 2" in html
    assert "Page 2 of 2" in html
    assert 'value="V0"' in html
    assert 'value="V4"' in html
    assert "{@odin.page}" not in html
    assert "{@odin.total_pages}" not in html


def test_render_radio_group_checked_from_data():
    form = parse_form(open_fixture("signature-radio.odin"))
    data = odin.parse('{applicant}\ngender = "F"')
    html = render_form(form, data)
    assert 'name="gender" value="F" aria-label="Female" checked>' in html
    assert 'name="gender" value="M" aria-label="Male" checked' not in html


def test_render_background_image_lowest_zindex():
    form = parse_form(open_fixture("content-elements.odin"))
    html = render_form(form)
    assert "z-index:0;" in html
    assert "data:image/png;base64," in html
    assert 'data-barcode-type="qr"' in html


def test_render_multiselect_inline_selected():
    src = """{page[0]}
{.field.cov}
type = "multiselect"
x = #0
y = #0
w = #3
h = #1
label = "Coverages"
bind = @policy.coverages

{.field.cov.options[] : ~}
"liability"
"collision"
"comprehensive"

{.field.cov.selected[] : ~}
"collision"
"""
    form = parse_form(src)
    el = form.pages[0].elements[0]
    assert isinstance(el, MultiselectElement)
    assert el.options == ["liability", "collision", "comprehensive"]
    assert el.selected == ["collision"]
    html = render_form(form)
    assert '<option value="collision" selected>' in html
    assert '<option value="liability">' in html


def test_render_html_escaping():
    src = """{page[0]}
{.text.t}
x = #0
y = #0
content = "A <b> & \\"C\\""
"""
    form = parse_form(src)
    html = render_form(form)
    assert "&lt;b&gt;" in html
    assert "&amp;" in html


# ─────────────────────────────────────────────────────────────────────────────
# Top-level API surface
# ─────────────────────────────────────────────────────────────────────────────


def test_top_level_exports():
    assert odin.parse_form is not None
    assert odin.render_form is not None
    assert odin.to_pixels(1, "inch") == 96
    assert odin.from_pixels(96, "inch") == 1
    assert "@media print" in odin.generate_print_css()
    assert ".odin-form" in odin.generate_form_css()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def open_fixture(name):
    from pathlib import Path

    return (Path(__file__).parent / "forms_fixtures" / name).read_text(encoding="utf-8")
