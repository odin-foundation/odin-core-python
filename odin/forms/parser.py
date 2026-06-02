"""Parser from ODIN forms text to a typed OdinForm model.

Low-level ODIN parsing is delegated to ``odin.parse``; the resulting flat
path space is mapped onto the Forms 1.0 schema.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

import odin
from odin.types.values import (
    OdinBinary,
    OdinBoolean,
    OdinDate,
    OdinInteger,
    OdinNumber,
    OdinReference,
    OdinString,
    OdinTimestamp,
)

from .types import (
    BarcodeElement,
    CheckboxElement,
    CircleElement,
    DateElement,
    EllipseElement,
    FormElement,
    FormMetadata,
    FormPage,
    ImageElement,
    LineElement,
    MultiselectElement,
    OdinForm,
    PageDefaults,
    PageMargins,
    PageTemplate,
    PathElement,
    PolygonElement,
    PolylineElement,
    RadioElement,
    RectElement,
    RegionElement,
    ScreenSettings,
    SelectElement,
    SignatureElement,
    TextElement,
    TextFieldElement,
)

_VALID_UNITS = ("inch", "cm", "mm", "pt")
_VALID_BARCODE_TYPES = ("code39", "code128", "qr", "datamatrix", "pdf417")
_VALID_INPUT_TYPES = ("text", "email", "tel", "password", "number", "url")


def parse_form(text: str) -> OdinForm:
    """Parse an ODIN forms document into a typed OdinForm.

    Raises:
        ParseError: If the text is not valid ODIN.
    """
    doc = odin.parse(text)

    i18n = _extract_i18n(doc)
    return OdinForm(
        metadata=_extract_metadata(doc),
        page_defaults=_extract_page_defaults(doc),
        screen=_extract_screen(doc),
        i18n=i18n,
        pages=_extract_pages(doc, i18n),
        templates=_extract_templates(doc, i18n),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Metadata and Settings
# ─────────────────────────────────────────────────────────────────────────────


def _extract_metadata(doc) -> FormMetadata:
    return FormMetadata(
        title=_string(doc, "$.title") or "",
        id=_string(doc, "$.id") or "",
        lang=_string(doc, "$.lang") or "en",
        version=_string(doc, "$.forms"),
    )


def _extract_page_defaults(doc) -> Optional[PageDefaults]:
    width = _number(doc, "$.page.width")
    height = _number(doc, "$.page.height")
    unit = _string(doc, "$.page.unit")
    margin = _extract_margins(doc)

    if width is None and height is None and unit is None:
        return None

    resolved_unit = unit if unit in _VALID_UNITS else "inch"
    return PageDefaults(
        width=width if width is not None else 8.5,
        height=height if height is not None else 11.0,
        unit=resolved_unit,
        margin=margin,
    )


def _extract_margins(doc) -> Optional[PageMargins]:
    top = _number(doc, "$.page.margin.top")
    right = _number(doc, "$.page.margin.right")
    bottom = _number(doc, "$.page.margin.bottom")
    left = _number(doc, "$.page.margin.left")
    if top is None and right is None and bottom is None and left is None:
        return None
    return PageMargins(top=top, right=right, bottom=bottom, left=left)


def _extract_screen(doc) -> Optional[ScreenSettings]:
    scale = _number(doc, "$.screen.scale")
    if scale is None:
        return None
    return ScreenSettings(scale=scale)


def _extract_i18n(doc) -> Optional[Dict[str, str]]:
    prefix = "$.i18n."
    result: Dict[str, str] = {}
    for path in doc.paths():
        if not path.startswith(prefix):
            continue
        key = path[len(prefix):]
        value = _string(doc, path)
        if key and value is not None:
            result[key] = value
    return result or None


# ─────────────────────────────────────────────────────────────────────────────
# Pages and Templates
# ─────────────────────────────────────────────────────────────────────────────


_PAGE_PATH = re.compile(r"^page\[(\d+)\]\.")


def _extract_pages(doc, i18n) -> List[FormPage]:
    indices = set()
    for path in doc.paths():
        m = _PAGE_PATH.match(path)
        if m:
            indices.add(int(m.group(1)))
    pages: List[FormPage] = []
    for index in sorted(indices):
        pages.append(FormPage(elements=_extract_elements(doc, f"page[{index}].", i18n)))
    return pages


def _extract_templates(doc, i18n) -> Optional[Dict[str, PageTemplate]]:
    names: List[str] = []
    seen = set()
    for path in doc.paths():
        if not path.startswith("tpl_"):
            continue
        name = path.split(".", 1)[0]
        if name not in seen:
            seen.add(name)
            names.append(name)
    if not names:
        return None

    templates: Dict[str, PageTemplate] = {}
    for name in names:
        prefix = f"{name}."
        page_template = _boolean(doc, f"{prefix}page-template")
        templates[name] = PageTemplate(
            name=name,
            page_template=page_template if page_template is not None else True,
            continues=_string(doc, f"{prefix}continues"),
            form_id=_string(doc, f"{prefix}form-id"),
            elements=_extract_elements(doc, prefix, i18n),
        )
    return templates


# ─────────────────────────────────────────────────────────────────────────────
# Element Collection
# ─────────────────────────────────────────────────────────────────────────────

_RESERVED_KEYS = frozenset(
    {"page-template", "continues", "form-id"}
)


def _extract_elements(doc, prefix: str, i18n) -> List[FormElement]:
    keys_seen = set()
    keys_ordered: List[str] = []
    for path in doc.paths():
        if not path.startswith(prefix):
            continue
        rest = path[len(prefix):]
        parts = rest.split(".")
        if len(parts) < 2:
            continue
        if parts[0] in _RESERVED_KEYS:
            continue
        key = f"{parts[0]}.{parts[1]}"
        if key not in keys_seen:
            keys_seen.add(key)
            keys_ordered.append(key)

    elements: List[FormElement] = []
    id_counter = 0
    for key in keys_ordered:
        element_type, element_name = key.split(".", 1)
        element_prefix = f"{prefix}{key}."
        el = _build_element(doc, element_type, element_name, element_prefix, id_counter, i18n)
        if el is not None:
            elements.append(el)
            id_counter += 1
    return elements


def _build_element(doc, element_type, element_name, prefix, id_counter, i18n) -> Optional[FormElement]:
    element_id = f"{element_type}_{element_name}_{id_counter}"
    builders = {
        "line": _build_line,
        "rect": _build_rect,
        "circle": _build_circle,
        "ellipse": _build_ellipse,
        "polygon": _build_polygon,
        "polyline": _build_polyline,
        "path": _build_path,
    }
    if element_type in builders:
        return builders[element_type](doc, element_name, element_id, prefix)
    if element_type == "text":
        return _build_text(doc, element_name, element_id, prefix, i18n)
    if element_type == "img":
        return _build_image(doc, element_name, element_id, prefix, i18n)
    if element_type == "barcode":
        return _build_barcode(doc, element_name, element_id, prefix, i18n)
    if element_type == "field":
        return _build_field(doc, element_name, element_id, prefix, i18n)
    if element_type == "region":
        return _build_region(doc, element_name, element_id, prefix, i18n)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Geometric Builders
# ─────────────────────────────────────────────────────────────────────────────


def _build_line(doc, name, element_id, prefix) -> LineElement:
    el = LineElement(
        type="line",
        name=name,
        id=element_id,
        x1=_number(doc, f"{prefix}x1") or 0.0,
        y1=_number(doc, f"{prefix}y1") or 0.0,
        x2=_number(doc, f"{prefix}x2") or 0.0,
        y2=_number(doc, f"{prefix}y2") or 0.0,
    )
    _apply_stroke(doc, prefix, el)
    return el


def _build_rect(doc, name, element_id, prefix) -> RectElement:
    el = RectElement(
        type="rect",
        name=name,
        id=element_id,
        x=_number(doc, f"{prefix}x") or 0.0,
        y=_number(doc, f"{prefix}y") or 0.0,
        w=_number(doc, f"{prefix}w") or 0.0,
        h=_number(doc, f"{prefix}h") or 0.0,
        rx=_number(doc, f"{prefix}rx"),
        ry=_number(doc, f"{prefix}ry"),
    )
    _apply_stroke(doc, prefix, el)
    _apply_fill(doc, prefix, el)
    return el


def _build_circle(doc, name, element_id, prefix) -> CircleElement:
    el = CircleElement(
        type="circle",
        name=name,
        id=element_id,
        cx=_number(doc, f"{prefix}cx") or 0.0,
        cy=_number(doc, f"{prefix}cy") or 0.0,
        r=_number(doc, f"{prefix}r") or 0.0,
    )
    _apply_stroke(doc, prefix, el)
    _apply_fill(doc, prefix, el)
    return el


def _build_ellipse(doc, name, element_id, prefix) -> EllipseElement:
    el = EllipseElement(
        type="ellipse",
        name=name,
        id=element_id,
        cx=_number(doc, f"{prefix}cx") or 0.0,
        cy=_number(doc, f"{prefix}cy") or 0.0,
        rx=_number(doc, f"{prefix}rx") or 0.0,
        ry=_number(doc, f"{prefix}ry") or 0.0,
    )
    _apply_stroke(doc, prefix, el)
    _apply_fill(doc, prefix, el)
    return el


def _build_polygon(doc, name, element_id, prefix) -> PolygonElement:
    el = PolygonElement(
        type="polygon",
        name=name,
        id=element_id,
        points=_string(doc, f"{prefix}points") or "",
    )
    _apply_stroke(doc, prefix, el)
    _apply_fill(doc, prefix, el)
    return el


def _build_polyline(doc, name, element_id, prefix) -> PolylineElement:
    el = PolylineElement(
        type="polyline",
        name=name,
        id=element_id,
        points=_string(doc, f"{prefix}points") or "",
    )
    _apply_stroke(doc, prefix, el)
    return el


def _build_path(doc, name, element_id, prefix) -> PathElement:
    el = PathElement(
        type="path",
        name=name,
        id=element_id,
        d=_string(doc, f"{prefix}d") or "",
    )
    _apply_stroke(doc, prefix, el)
    _apply_fill(doc, prefix, el)
    return el


# ─────────────────────────────────────────────────────────────────────────────
# Content Builders
# ─────────────────────────────────────────────────────────────────────────────


def _build_text(doc, name, element_id, prefix, i18n) -> TextElement:
    el = TextElement(
        type="text",
        name=name,
        id=element_id,
        content=_label(doc, f"{prefix}content", i18n) or "",
        x=_number(doc, f"{prefix}x") or 0.0,
        y=_number(doc, f"{prefix}y") or 0.0,
        rotate=_number(doc, f"{prefix}rotate"),
    )
    _apply_font(doc, prefix, el)
    return el


def _build_image(doc, name, element_id, prefix, i18n) -> ImageElement:
    return ImageElement(
        type="img",
        name=name,
        id=element_id,
        src=_binary_literal(doc, f"{prefix}src") or "",
        alt=_label(doc, f"{prefix}alt", i18n) or "",
        x=_number(doc, f"{prefix}x") or 0.0,
        y=_number(doc, f"{prefix}y") or 0.0,
        w=_number(doc, f"{prefix}w") or 0.0,
        h=_number(doc, f"{prefix}h") or 0.0,
        background=_boolean(doc, f"{prefix}background"),
    )


def _build_barcode(doc, name, element_id, prefix, i18n) -> BarcodeElement:
    barcode_type = _string(doc, f"{prefix}type") or _string(doc, f"{prefix}barcode-type") or "code128"
    if barcode_type not in _VALID_BARCODE_TYPES:
        barcode_type = "code128"
    return BarcodeElement(
        type="barcode",
        name=name,
        id=element_id,
        barcode_type=barcode_type,
        content=_label(doc, f"{prefix}content", i18n) or "",
        alt=_label(doc, f"{prefix}alt", i18n) or "",
        x=_number(doc, f"{prefix}x") or 0.0,
        y=_number(doc, f"{prefix}y") or 0.0,
        w=_number(doc, f"{prefix}w") or 0.0,
        h=_number(doc, f"{prefix}h") or 0.0,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Field Builders
# ─────────────────────────────────────────────────────────────────────────────


def _build_field(doc, name, element_id, prefix, i18n) -> Optional[FormElement]:
    field_type = _string(doc, f"{prefix}type") or "text"
    base = _base_field_kwargs(doc, name, element_id, prefix, i18n)

    if field_type == "checkbox":
        return CheckboxElement(type="field.checkbox", checked=_boolean(doc, f"{prefix}checked"), **base)
    if field_type == "radio":
        return RadioElement(
            type="field.radio",
            group=_string(doc, f"{prefix}group") or "",
            value=_string(doc, f"{prefix}value") or "",
            **base,
        )
    if field_type == "select":
        return SelectElement(
            type="field.select",
            options=_field_array(doc, prefix, "options") or [],
            selected=_string(doc, f"{prefix}selected"),
            placeholder=_string(doc, f"{prefix}placeholder"),
            **base,
        )
    if field_type == "multiselect":
        return MultiselectElement(
            type="field.multiselect",
            options=_field_array(doc, prefix, "options") or [],
            selected=_field_array(doc, prefix, "selected"),
            min_select=_number_int(doc, f"{prefix}minSelect"),
            max_select=_number_int(doc, f"{prefix}maxSelect"),
            **base,
        )
    if field_type == "date":
        return DateElement(type="field.date", value=_scalar_string(doc, f"{prefix}value"), **base)
    if field_type == "signature":
        return SignatureElement(
            type="field.signature",
            value=_binary_literal(doc, f"{prefix}value"),
            date_field=_string(doc, f"{prefix}date_field") or _reference(doc, f"{prefix}date_field"),
            **base,
        )

    # text and unknown types fall through to a text field.
    input_type = _string(doc, f"{prefix}inputType")
    if input_type not in _VALID_INPUT_TYPES:
        input_type = None
    return TextFieldElement(
        type="field.text",
        value=_scalar_string(doc, f"{prefix}value"),
        input_type=input_type,
        mask=_string(doc, f"{prefix}mask"),
        placeholder=_string(doc, f"{prefix}placeholder"),
        multiline=_boolean(doc, f"{prefix}multiline"),
        max_lines=_number_int(doc, f"{prefix}maxLines"),
        **base,
    )


def _base_field_kwargs(doc, name, element_id, prefix, i18n) -> dict:
    bind_ref = _reference(doc, f"{prefix}bind")
    return {
        "name": name,
        "id": element_id,
        "label": _label(doc, f"{prefix}label", i18n) or "",
        "x": _number(doc, f"{prefix}x") or 0.0,
        "y": _number(doc, f"{prefix}y") or 0.0,
        "w": _number(doc, f"{prefix}w") or 0.0,
        "h": _number(doc, f"{prefix}h") or 0.0,
        "bind": f"@{bind_ref}" if bind_ref is not None else "",
        "required": _boolean(doc, f"{prefix}required"),
        "pattern": _string(doc, f"{prefix}pattern"),
        "min_length": _number_int(doc, f"{prefix}minLength"),
        "max_length": _number_int(doc, f"{prefix}maxLength"),
        "min": _number(doc, f"{prefix}min") if _number(doc, f"{prefix}min") is not None else _scalar_string(doc, f"{prefix}min"),
        "max": _number(doc, f"{prefix}max") if _number(doc, f"{prefix}max") is not None else _scalar_string(doc, f"{prefix}max"),
        "aria_label": _label(doc, f"{prefix}aria-label", i18n),
        "tabindex": _number_int(doc, f"{prefix}tabindex"),
        "readonly": _boolean(doc, f"{prefix}readonly"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Region Builder
# ─────────────────────────────────────────────────────────────────────────────

_REGION_OWN_PROPS = frozenset({"x", "y", "w", "h", "bind", "max", "overflow"})
_REGION_CHILD_TYPES = frozenset({"text", "field", "img", "barcode"})


def _build_region(doc, name, element_id, prefix, i18n) -> RegionElement:
    bind = _reference(doc, f"{prefix}bind")
    overflow_ref = _reference(doc, f"{prefix}overflow")
    overflow = overflow_ref or _string(doc, f"{prefix}overflow")
    overflow_value = None
    if overflow is not None:
        overflow_value = f"@{overflow}" if overflow_ref is not None else overflow

    return RegionElement(
        type="region",
        name=name,
        id=element_id,
        x=_number(doc, f"{prefix}x") or 0.0,
        y=_number(doc, f"{prefix}y") or 0.0,
        w=_number(doc, f"{prefix}w") or 0.0,
        h=_number(doc, f"{prefix}h") or 0.0,
        bind=f"@{bind}" if bind is not None else None,
        max=_number_int(doc, f"{prefix}max"),
        overflow=overflow_value,
        children=_extract_region_children(doc, prefix, i18n),
    )


def _extract_region_children(doc, prefix, i18n) -> List[FormElement]:
    keys_seen = set()
    keys_ordered: List[str] = []
    for path in doc.paths():
        if not path.startswith(prefix):
            continue
        rest = path[len(prefix):]
        parts = rest.split(".")
        if len(parts) < 2:
            continue
        if parts[0] in _REGION_OWN_PROPS:
            continue
        if parts[0] not in _REGION_CHILD_TYPES:
            continue
        key = f"{parts[0]}.{parts[1]}"
        if key not in keys_seen:
            keys_seen.add(key)
            keys_ordered.append(key)

    children: List[FormElement] = []
    id_counter = 0
    for key in keys_ordered:
        child_type, child_name = key.split(".", 1)
        child_prefix = f"{prefix}{key}."
        built = _build_element(doc, child_type, child_name, child_prefix, id_counter, i18n)
        if built is None:
            continue
        id_counter += 1
        y_offset = _number(doc, f"{child_prefix}y-offset")
        x_offset = _number(doc, f"{child_prefix}x-offset")
        if y_offset is not None:
            built.y_offset = y_offset
        if x_offset is not None:
            built.x_offset = x_offset
        children.append(built)
    return children


# ─────────────────────────────────────────────────────────────────────────────
# Style Mixins
# ─────────────────────────────────────────────────────────────────────────────


def _apply_stroke(doc, prefix, el) -> None:
    el.stroke = _string(doc, f"{prefix}stroke")
    el.stroke_width = _number(doc, f"{prefix}stroke-width")
    el.stroke_opacity = _number(doc, f"{prefix}stroke-opacity")
    el.stroke_dasharray = _string(doc, f"{prefix}stroke-dasharray")
    el.stroke_linecap = _string(doc, f"{prefix}stroke-linecap")
    el.stroke_linejoin = _string(doc, f"{prefix}stroke-linejoin")


def _apply_fill(doc, prefix, el) -> None:
    el.fill = _string(doc, f"{prefix}fill")
    el.fill_opacity = _number(doc, f"{prefix}fill-opacity")


def _apply_font(doc, prefix, el) -> None:
    el.font_family = _string(doc, f"{prefix}font-family")
    el.font_size = _number(doc, f"{prefix}font-size")
    el.font_weight = _string(doc, f"{prefix}font-weight")
    el.font_style = _string(doc, f"{prefix}font-style")
    el.text_align = _string(doc, f"{prefix}text-align")
    el.color = _string(doc, f"{prefix}color")


# ─────────────────────────────────────────────────────────────────────────────
# Arrays
# ─────────────────────────────────────────────────────────────────────────────


def _field_array(doc, prefix, name) -> Optional[List[str]]:
    direct = _collect_indexed(doc, f"{prefix}{name}")
    if direct:
        return direct

    pattern = re.compile(rf"^{re.escape(prefix)}(?:[^.]+\.)*{re.escape(name)}\[(\d+)\]$")
    found = []
    for path in doc.paths():
        m = pattern.match(path)
        if m:
            found.append((int(m.group(1)), path))
    if not found:
        return None
    found.sort(key=lambda t: t[0])
    out = []
    for _, path in found:
        value = _string(doc, path)
        if value is not None:
            out.append(value)
    return out


def _collect_indexed(doc, base) -> List[str]:
    out: List[str] = []
    i = 0
    while f"{base}[{i}]" in doc:
        value = _string(doc, f"{base}[{i}]")
        if value is not None:
            out.append(value)
        i += 1
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Value Accessors
# ─────────────────────────────────────────────────────────────────────────────


def _string(doc, path) -> Optional[str]:
    val = doc.get(path)
    if isinstance(val, OdinString):
        return val.value
    return None


def _label(doc, path, i18n) -> Optional[str]:
    val = doc.get(path)
    if val is None:
        return None
    if isinstance(val, OdinString):
        return val.value
    if isinstance(val, OdinReference):
        ref = val.path
        if ref.startswith("$.i18n."):
            key = ref[len("$.i18n."):]
            if i18n and key in i18n:
                return i18n[key]
            return ref
        return ref
    return None


def _scalar_string(doc, path) -> Optional[str]:
    val = doc.get(path)
    if isinstance(val, OdinString):
        return val.value
    if isinstance(val, (OdinDate, OdinTimestamp)):
        raw = getattr(val, "raw", None)
        return raw if raw is not None else str(val.value)
    return None


def _binary_literal(doc, path) -> Optional[str]:
    val = doc.get(path)
    if isinstance(val, OdinBinary):
        import base64

        b64 = base64.b64encode(val.data).decode("ascii")
        return f"^{val.algorithm}:{b64}" if val.algorithm else f"^{b64}"
    if isinstance(val, OdinString):
        return val.value
    return None


def _number(doc, path) -> Optional[float]:
    val = doc.get(path)
    if isinstance(val, (OdinNumber, OdinInteger)):
        return val.value
    return None


def _number_int(doc, path) -> Optional[int]:
    num = _number(doc, path)
    return int(num) if num is not None else None


def _boolean(doc, path) -> Optional[bool]:
    val = doc.get(path)
    if isinstance(val, OdinBoolean):
        return val.value
    return None


def _reference(doc, path) -> Optional[str]:
    val = doc.get(path)
    if isinstance(val, OdinReference):
        return val.path
    return None
