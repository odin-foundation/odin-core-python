"""HTML/CSS renderer for parsed OdinForm models.

Produces an accessible HTML string with absolute-positioned layout matching
print coordinates, ARIA attributes, skip navigation, and optional data binding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from odin.types.values import (
    OdinBoolean,
    OdinInteger,
    OdinNumber,
    OdinString,
)

from .accessibility import (
    field_aria_attrs,
    field_group_html,
    field_label_html,
    generate_field_id,
    skip_link_html,
    tab_order_sort,
)
from .css import generate_form_css, generate_print_css
from .types import (
    BarcodeElement,
    CheckboxElement,
    CircleElement,
    DateElement,
    EllipseElement,
    FIELD_TYPES,
    FormElement,
    ImageElement,
    LineElement,
    MultiselectElement,
    OdinForm,
    PathElement,
    PolygonElement,
    PolylineElement,
    RadioElement,
    RectElement,
    RegionElement,
    RenderFormOptions,
    SelectElement,
    SignatureElement,
    TextElement,
    TextFieldElement,
)
from .units import to_pixels


@dataclass
class _RenderContext:
    page_number: int
    total_pages: int
    unit: str
    data: object
    page_width_px: float
    page_height_px: float


@dataclass
class _PlannedPage:
    elements: List[FormElement]
    item_slices: Optional[Dict[str, dict]] = None


def render_form(form: OdinForm, data=None, options: Optional[RenderFormOptions] = None) -> str:
    """Render an OdinForm to a complete HTML string.

    Args:
        form: Parsed OdinForm.
        data: Optional ODIN document for data binding.
        options: Optional rendering options.

    Returns:
        Complete HTML string including ``<form>``, ``<style>``, and elements.
    """
    title = form.metadata.title or "ODIN Form"
    class_name = f" {options.class_name}" if options and options.class_name else ""
    unit = form.page_defaults.unit if form.page_defaults else "inch"

    plan = _build_render_plan(form, data)
    total_pages = len(plan)
    page_w = to_pixels(form.page_defaults.width if form.page_defaults else 8.5, unit)
    page_h = to_pixels(form.page_defaults.height if form.page_defaults else 11.0, unit)

    parts: List[str] = []
    parts.append(f'<form role="form" aria-label="{_escape_attr(title)}" class="odin-form{class_name}">')
    parts.append(skip_link_html(title))
    parts.append(f"<style>{generate_form_css()}\n{generate_print_css()}</style>")

    for i, planned in enumerate(plan):
        ctx = _RenderContext(
            page_number=i + 1,
            total_pages=total_pages,
            unit=unit,
            data=data,
            page_width_px=page_w,
            page_height_px=page_h,
        )
        parts.append(_render_planned_page(planned, ctx))

    parts.append("</form>")
    return "".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Render Plan
# ─────────────────────────────────────────────────────────────────────────────


def _build_render_plan(form: OdinForm, data) -> List[_PlannedPage]:
    plan: List[_PlannedPage] = []

    for page in form.pages:
        plan.append(_PlannedPage(elements=page.elements))
        if data is None:
            continue

        for el in page.elements:
            if not isinstance(el, RegionElement):
                continue
            region = el
            if not region.bind or region.max is None or not region.overflow:
                continue
            if region.max < 1:
                continue
            count = _bound_array_length(region.bind, data)
            if count <= region.max:
                continue

            consumed = region.max
            template_name = region.overflow[1:] if region.overflow.startswith("@") else None
            guard = 0
            while consumed < count and guard < 10000:
                guard += 1
                tpl = form.templates.get(template_name) if (form.templates and template_name) else None
                tpl_region = None
                if tpl:
                    for e in tpl.elements:
                        if isinstance(e, RegionElement) and e.name == region.name:
                            tpl_region = e
                            break
                candidate_max = tpl_region.max if tpl_region and tpl_region.max is not None else region.max
                page_max = candidate_max if candidate_max >= 1 else region.max
                slices = {
                    region.name: {
                        "start": consumed,
                        "count": min(page_max, count - consumed),
                        "bind": region.bind,
                    }
                }
                elements = tpl.elements if tpl else page.elements
                plan.append(_PlannedPage(elements=elements, item_slices=slices))
                consumed += page_max
                if tpl_region and tpl_region.overflow and tpl_region.overflow.startswith("@"):
                    template_name = tpl_region.overflow[1:]

    return plan


# ─────────────────────────────────────────────────────────────────────────────
# Page Rendering
# ─────────────────────────────────────────────────────────────────────────────


def _render_planned_page(page: _PlannedPage, ctx: _RenderContext) -> str:
    page_index = ctx.page_number - 1
    parts: List[str] = []
    parts.append(
        f'<div class="odin-form-page" id="odin-form-content" data-page="{ctx.page_number}" '
        f'style="width:{_num(ctx.page_width_px)}px;height:{_num(ctx.page_height_px)}px;">'
    )

    for el in page.elements:
        if isinstance(el, ImageElement) and el.background:
            parts.append(_render_element(el, page_index, ctx, page))
    for el in page.elements:
        if isinstance(el, ImageElement) and el.background:
            continue
        if el.type not in FIELD_TYPES:
            parts.append(_render_element(el, page_index, ctx, page))
    for el in tab_order_sort(list(page.elements)):
        parts.append(_render_element(el, page_index, ctx, page))

    parts.append("</div>")
    return "".join(parts)


def _render_element(el: FormElement, page_index: int, ctx: _RenderContext, page: _PlannedPage) -> str:
    unit = ctx.unit
    t = el.type
    if t == "line":
        return _render_line(el, unit)
    if t == "rect":
        return _render_rect(el, unit)
    if t == "circle":
        return _render_circle(el, unit)
    if t == "ellipse":
        return _render_ellipse(el, unit)
    if t == "polygon":
        return _render_polygon(el, unit)
    if t == "polyline":
        return _render_polyline(el, unit)
    if t == "path":
        return _render_path(el, unit)
    if t == "text":
        return _render_text(el, ctx)
    if t == "img":
        return _render_image(el, ctx)
    if t == "barcode":
        return _render_barcode(el, ctx)
    if t == "field.text":
        return _render_text_field(el, page_index, ctx)
    if t == "field.checkbox":
        return _render_checkbox(el, page_index, ctx)
    if t == "field.radio":
        return _render_radio(el, page_index, ctx)
    if t == "field.select":
        return _render_select(el, page_index, ctx)
    if t == "field.multiselect":
        return _render_multiselect(el, page_index, ctx)
    if t == "field.date":
        return _render_date(el, page_index, ctx)
    if t == "field.signature":
        return _render_signature(el, page_index, ctx)
    if t == "region":
        return _render_region(el, ctx, page)
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Interpolation
# ─────────────────────────────────────────────────────────────────────────────

_INTERP = re.compile(r"\{@odin\.([a-z_]+)\}")


def _interpolate(text: str, ctx: _RenderContext) -> str:
    def repl(m):
        name = m.group(1)
        if name == "page":
            return str(ctx.page_number)
        if name == "total_pages":
            return str(ctx.total_pages)
        return m.group(0)

    return _INTERP.sub(repl, text)


# ─────────────────────────────────────────────────────────────────────────────
# Geometric Elements
# ─────────────────────────────────────────────────────────────────────────────

_SVG_WRAP = (
    '<svg class="odin-form-element" style="position:absolute;left:0;top:0;'
    'width:100%;height:100%;overflow:visible;">'
)


def _render_line(el: LineElement, unit: str) -> str:
    x1 = to_pixels(el.x1, unit)
    y1 = to_pixels(el.y1, unit)
    x2 = to_pixels(el.x2, unit)
    y2 = to_pixels(el.y2, unit)
    stroke = el.stroke or "#000000"
    stroke_width = to_pixels(el.stroke_width, unit) if el.stroke_width else 1
    return (
        _SVG_WRAP
        + f'<line x1="{_num(x1)}" y1="{_num(y1)}" x2="{_num(x2)}" y2="{_num(y2)}" '
        f'stroke="{stroke}" stroke-width="{_num(stroke_width)}"/>'
        + "</svg>"
    )


def _render_rect(el: RectElement, unit: str) -> str:
    x = to_pixels(el.x, unit)
    y = to_pixels(el.y, unit)
    w = to_pixels(el.w, unit)
    h = to_pixels(el.h, unit)
    border = ""
    if el.stroke:
        sw = to_pixels(el.stroke_width, unit) if el.stroke_width else 1
        border = f"border:{_num(sw)}px solid {el.stroke};"
    bg = f"background:{el.fill};" if el.fill and el.fill != "none" else ""
    rx = to_pixels(el.rx, unit) if el.rx else 0
    ry = to_pixels(el.ry, unit) if el.ry else 0
    radius = f"border-radius:{_num(rx)}px {_num(ry)}px;" if (rx or ry) else ""
    return (
        f'<div class="odin-form-element" style="position:absolute;left:{_num(x)}px;'
        f"top:{_num(y)}px;width:{_num(w)}px;height:{_num(h)}px;{border}{bg}{radius}\"></div>"
    )


def _render_circle(el: CircleElement, unit: str) -> str:
    cx = to_pixels(el.cx, unit)
    cy = to_pixels(el.cy, unit)
    r = to_pixels(el.r, unit)
    stroke = el.stroke or "#000000"
    stroke_width = to_pixels(el.stroke_width, unit) if el.stroke_width else 1
    fill = el.fill or "none"
    return (
        _SVG_WRAP
        + f'<circle cx="{_num(cx)}" cy="{_num(cy)}" r="{_num(r)}" stroke="{stroke}" '
        f'stroke-width="{_num(stroke_width)}" fill="{fill}"/>'
        + "</svg>"
    )


def _render_ellipse(el: EllipseElement, unit: str) -> str:
    cx = to_pixels(el.cx, unit)
    cy = to_pixels(el.cy, unit)
    rx = to_pixels(el.rx, unit)
    ry = to_pixels(el.ry, unit)
    stroke = el.stroke or "#000000"
    stroke_width = to_pixels(el.stroke_width, unit) if el.stroke_width else 1
    fill = el.fill or "none"
    return (
        _SVG_WRAP
        + f'<ellipse cx="{_num(cx)}" cy="{_num(cy)}" rx="{_num(rx)}" ry="{_num(ry)}" '
        f'stroke="{stroke}" stroke-width="{_num(stroke_width)}" fill="{fill}"/>'
        + "</svg>"
    )


def _render_polygon(el: PolygonElement, unit: str) -> str:
    points = _convert_points(el.points, unit)
    stroke = el.stroke or "#000000"
    stroke_width = to_pixels(el.stroke_width, unit) if el.stroke_width else 1
    fill = el.fill or "none"
    return (
        _SVG_WRAP
        + f'<polygon points="{points}" stroke="{stroke}" stroke-width="{_num(stroke_width)}" fill="{fill}"/>'
        + "</svg>"
    )


def _render_polyline(el: PolylineElement, unit: str) -> str:
    points = _convert_points(el.points, unit)
    stroke = el.stroke or "#000000"
    stroke_width = to_pixels(el.stroke_width, unit) if el.stroke_width else 1
    return (
        _SVG_WRAP
        + f'<polyline points="{points}" stroke="{stroke}" stroke-width="{_num(stroke_width)}" fill="none"/>'
        + "</svg>"
    )


def _render_path(el: PathElement, unit: str) -> str:
    stroke = el.stroke or "#000000"
    stroke_width = to_pixels(el.stroke_width, unit) if el.stroke_width else 1
    fill = el.fill or "none"
    return (
        _SVG_WRAP
        + f'<path d="{el.d}" stroke="{stroke}" stroke-width="{_num(stroke_width)}" fill="{fill}"/>'
        + "</svg>"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Content Elements
# ─────────────────────────────────────────────────────────────────────────────


def _render_text(el: TextElement, ctx: _RenderContext) -> str:
    unit = ctx.unit
    x = to_pixels(el.x, unit)
    y = to_pixels(el.y, unit)
    font_size = to_pixels(el.font_size, "pt") if el.font_size else to_pixels(12, "pt")
    font_weight = el.font_weight or "normal"
    color = el.color or "#000000"
    font_family = f"font-family:{el.font_family};" if el.font_family else ""
    font_style = "font-style:italic;" if el.font_style == "italic" else ""
    text_align = f"text-align:{el.text_align};" if el.text_align else ""
    content = _interpolate(el.content, ctx)
    return (
        f'<span class="odin-form-element" style="position:absolute;left:{_num(x)}px;'
        f"top:{_num(y)}px;font-size:{_num(font_size)}px;font-weight:{font_weight};"
        f'color:{color};{font_family}{font_style}{text_align}">{_escape_html(content)}</span>'
    )


def _render_image(el: ImageElement, ctx: _RenderContext) -> str:
    unit = ctx.unit
    x = to_pixels(el.x, unit)
    y = to_pixels(el.y, unit)
    w = to_pixels(el.w, unit)
    h = to_pixels(el.h, unit)
    src = _image_src_to_data_uri(el.src)
    alt = _interpolate(el.alt, ctx)
    z_index = "z-index:0;" if el.background else ""
    return (
        f'<img class="odin-form-element" src="{_escape_attr(src)}" alt="{_escape_attr(alt)}" '
        f'style="position:absolute;left:{_num(x)}px;top:{_num(y)}px;width:{_num(w)}px;'
        f'height:{_num(h)}px;{z_index}">'
    )


def _render_barcode(el: BarcodeElement, ctx: _RenderContext) -> str:
    unit = ctx.unit
    x = to_pixels(el.x, unit)
    y = to_pixels(el.y, unit)
    w = to_pixels(el.w, unit)
    h = to_pixels(el.h, unit)
    alt = _interpolate(el.alt, ctx)
    content = _interpolate(el.content, ctx)
    return (
        '<div class="odin-form-element odin-form-barcode" role="img" '
        f'aria-label="{_escape_attr(alt)}" data-barcode-type="{_escape_attr(el.barcode_type)}" '
        f'data-content="{_escape_attr(content)}" '
        f'style="position:absolute;left:{_num(x)}px;top:{_num(y)}px;width:{_num(w)}px;'
        f'height:{_num(h)}px;"></div>'
    )


def _image_src_to_data_uri(src: str) -> str:
    if not src.startswith("^"):
        return src
    rest = src[1:]
    colon = rest.find(":")
    if colon == -1:
        return f"data:image/png;base64,{rest}"
    fmt = rest[:colon]
    b64 = rest[colon + 1:]
    return f"data:image/{fmt};base64,{b64}"


# ─────────────────────────────────────────────────────────────────────────────
# Field Elements
# ─────────────────────────────────────────────────────────────────────────────


def _aria_required_attr(attrs: Dict[str, str]) -> str:
    return ' aria-required="true"' if attrs.get("aria-required") else ""


def _render_text_field(el: TextFieldElement, page_index: int, ctx: _RenderContext) -> str:
    unit = ctx.unit
    x = to_pixels(el.x, unit)
    y = to_pixels(el.y, unit)
    w = to_pixels(el.w, unit)
    h = to_pixels(el.h, unit)
    attrs = field_aria_attrs(el, page_index)
    input_id = generate_field_id(el.name, page_index)
    value = el.value if el.value is not None else _lookup_bound_value(el, ctx.data)
    value_attr = f' value="{_escape_attr(value)}"' if value is not None else ""
    required_attr = " required" if el.required else ""
    readonly_attr = " readonly" if el.readonly else ""
    placeholder_attr = f' placeholder="{_escape_attr(el.placeholder)}"' if el.placeholder else ""
    input_type = el.input_type or "text"
    return (
        f'<div class="odin-form-element" style="position:absolute;left:{_num(x)}px;'
        f'top:{_num(y)}px;width:{_num(w)}px;height:{_num(h)}px;">'
        + field_label_html(_interpolate(el.label, ctx), input_id)
        + f'<input type="{_escape_attr(input_type)}" class="odin-form-input" id="{attrs["id"]}" '
        f'aria-label="{_escape_attr(_interpolate(attrs["aria-label"], ctx))}"'
        f"{_aria_required_attr(attrs)}{value_attr}{required_attr}{readonly_attr}{placeholder_attr}>"
        + "</div>"
    )


def _render_checkbox(el: CheckboxElement, page_index: int, ctx: _RenderContext) -> str:
    unit = ctx.unit
    x = to_pixels(el.x, unit)
    y = to_pixels(el.y, unit)
    w = to_pixels(el.w, unit)
    h = to_pixels(el.h, unit)
    attrs = field_aria_attrs(el, page_index)
    input_id = generate_field_id(el.name, page_index)
    bound = _lookup_bound_value(el, ctx.data)
    is_checked = el.checked if el.checked is not None else (bound == "true")
    checked = " checked" if is_checked else ""
    return (
        f'<div class="odin-form-element" style="position:absolute;left:{_num(x)}px;'
        f'top:{_num(y)}px;width:{_num(w)}px;height:{_num(h)}px;">'
        + field_label_html(_interpolate(el.label, ctx), input_id)
        + f'<input type="checkbox" class="odin-form-checkbox" id="{attrs["id"]}" '
        f'aria-label="{_escape_attr(_interpolate(attrs["aria-label"], ctx))}"'
        f"{_aria_required_attr(attrs)}{checked}>"
        + "</div>"
    )


def _render_radio(el: RadioElement, page_index: int, ctx: _RenderContext) -> str:
    unit = ctx.unit
    x = to_pixels(el.x, unit)
    y = to_pixels(el.y, unit)
    w = to_pixels(el.w, unit)
    h = to_pixels(el.h, unit)
    attrs = field_aria_attrs(el, page_index)
    value = _lookup_bound_value(el, ctx.data)
    checked = " checked" if value == el.value else ""
    radio_html = (
        f'<input type="radio" class="odin-form-radio" id="{attrs["id"]}" '
        f'name="{_escape_attr(el.group)}" value="{_escape_attr(el.value)}" '
        f'aria-label="{_escape_attr(_interpolate(attrs["aria-label"], ctx))}"'
        f"{_aria_required_attr(attrs)}{checked}>"
        f'<label for="{attrs["id"]}">{_escape_html(_interpolate(el.label, ctx))}</label>'
    )
    return (
        f'<div class="odin-form-element" style="position:absolute;left:{_num(x)}px;'
        f'top:{_num(y)}px;width:{_num(w)}px;height:{_num(h)}px;">'
        + field_group_html(el.group, _interpolate(el.label, ctx), radio_html)
        + "</div>"
    )


def _render_select(el: SelectElement, page_index: int, ctx: _RenderContext) -> str:
    unit = ctx.unit
    x = to_pixels(el.x, unit)
    y = to_pixels(el.y, unit)
    w = to_pixels(el.w, unit)
    h = to_pixels(el.h, unit)
    attrs = field_aria_attrs(el, page_index)
    input_id = generate_field_id(el.name, page_index)
    value = el.selected if el.selected is not None else _lookup_bound_value(el, ctx.data)

    options_html = ""
    if el.placeholder:
        options_html += f'<option value="">{_escape_html(el.placeholder)}</option>'
    for opt in el.options:
        selected = " selected" if value == opt else ""
        options_html += f'<option value="{_escape_attr(opt)}"{selected}>{_escape_html(opt)}</option>'

    return (
        f'<div class="odin-form-element" style="position:absolute;left:{_num(x)}px;'
        f'top:{_num(y)}px;width:{_num(w)}px;height:{_num(h)}px;">'
        + field_label_html(_interpolate(el.label, ctx), input_id)
        + f'<select class="odin-form-select" id="{attrs["id"]}" '
        f'aria-label="{_escape_attr(_interpolate(attrs["aria-label"], ctx))}"'
        f"{_aria_required_attr(attrs)}>"
        + options_html
        + "</select></div>"
    )


def _render_multiselect(el: MultiselectElement, page_index: int, ctx: _RenderContext) -> str:
    unit = ctx.unit
    x = to_pixels(el.x, unit)
    y = to_pixels(el.y, unit)
    w = to_pixels(el.w, unit)
    h = to_pixels(el.h, unit)
    attrs = field_aria_attrs(el, page_index)
    input_id = generate_field_id(el.name, page_index)
    if el.selected is not None:
        selected_values = list(el.selected)
    else:
        value = _lookup_bound_value(el, ctx.data)
        selected_values = [v.strip() for v in value.split(",")] if value else []

    options_html = ""
    for opt in el.options:
        selected = " selected" if opt in selected_values else ""
        options_html += f'<option value="{_escape_attr(opt)}"{selected}>{_escape_html(opt)}</option>'

    return (
        f'<div class="odin-form-element" style="position:absolute;left:{_num(x)}px;'
        f'top:{_num(y)}px;width:{_num(w)}px;height:{_num(h)}px;">'
        + field_label_html(_interpolate(el.label, ctx), input_id)
        + f'<select multiple class="odin-form-select" id="{attrs["id"]}" '
        f'aria-label="{_escape_attr(_interpolate(attrs["aria-label"], ctx))}"'
        f"{_aria_required_attr(attrs)}>"
        + options_html
        + "</select></div>"
    )


def _render_date(el: DateElement, page_index: int, ctx: _RenderContext) -> str:
    unit = ctx.unit
    x = to_pixels(el.x, unit)
    y = to_pixels(el.y, unit)
    w = to_pixels(el.w, unit)
    h = to_pixels(el.h, unit)
    attrs = field_aria_attrs(el, page_index)
    input_id = generate_field_id(el.name, page_index)
    value = el.value if el.value is not None else _lookup_bound_value(el, ctx.data)
    value_attr = f' value="{_escape_attr(value)}"' if value is not None else ""
    required_attr = " required" if el.required else ""
    return (
        f'<div class="odin-form-element" style="position:absolute;left:{_num(x)}px;'
        f'top:{_num(y)}px;width:{_num(w)}px;height:{_num(h)}px;">'
        + field_label_html(_interpolate(el.label, ctx), input_id)
        + f'<input type="date" class="odin-form-input" id="{attrs["id"]}" '
        f'aria-label="{_escape_attr(_interpolate(attrs["aria-label"], ctx))}"'
        f"{_aria_required_attr(attrs)}{value_attr}{required_attr}>"
        + "</div>"
    )


def _render_signature(el: SignatureElement, page_index: int, ctx: _RenderContext) -> str:
    unit = ctx.unit
    x = to_pixels(el.x, unit)
    y = to_pixels(el.y, unit)
    w = to_pixels(el.w, unit)
    h = to_pixels(el.h, unit)
    attrs = field_aria_attrs(el, page_index)
    input_id = generate_field_id(el.name, page_index)
    return (
        f'<div class="odin-form-element" style="position:absolute;left:{_num(x)}px;'
        f'top:{_num(y)}px;width:{_num(w)}px;height:{_num(h)}px;">'
        + field_label_html(_interpolate(el.label, ctx), input_id)
        + f'<div class="odin-form-signature" id="{attrs["id"]}" '
        f'aria-label="{_escape_attr(_interpolate(attrs["aria-label"], ctx))}"'
        f'{_aria_required_attr(attrs)} role="img" tabindex="0" style="width:100%;height:100%;"></div>'
        + "</div>"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Region Rendering
# ─────────────────────────────────────────────────────────────────────────────


def _render_region(el: RegionElement, ctx: _RenderContext, page: _PlannedPage) -> str:
    unit = ctx.unit
    region_x = to_pixels(el.x, unit)
    region_y = to_pixels(el.y, unit)
    region_w = to_pixels(el.w, unit)
    region_h = to_pixels(el.h, unit)

    slice_ = page.item_slices.get(el.name) if page.item_slices else None
    bind = el.bind or (slice_["bind"] if slice_ else None)
    total = _bound_array_length(bind, ctx.data) if bind else 0
    start = 0
    if slice_:
        start = slice_["start"]
        count = slice_["count"]
    elif total > 0:
        count = min(el.max, total) if el.max is not None else total
    else:
        count = 1

    parts: List[str] = []
    parts.append(
        f'<div class="odin-form-element odin-form-region" data-region="{_escape_attr(el.name)}" '
        f'style="position:absolute;left:{_num(region_x)}px;top:{_num(region_y)}px;'
        f'width:{_num(region_w)}px;height:{_num(region_h)}px;">'
    )

    for i in range(count):
        item_index = start + i
        item_bind = f"{bind}[{item_index}]" if bind else None
        for child in el.children:
            parts.append(_render_region_child(child, i, item_bind, ctx))

    parts.append("</div>")
    return "".join(parts)


def _render_region_child(child: FormElement, i: int, item_bind: Optional[str], ctx: _RenderContext) -> str:
    import copy

    y_offset = child.y_offset or 0
    x_offset = child.x_offset or 0
    dx = child.x + x_offset * i
    dy = child.y + y_offset * i

    if isinstance(child, TextElement):
        rebased = copy.copy(child)
        rebased.x = dx
        rebased.y = dy
        return _render_text(rebased, ctx)

    resolved_bind = _resolve_relative_bind(child.bind, item_bind) or child.bind
    rebased = copy.copy(child)
    rebased.x = dx
    rebased.y = dy
    rebased.name = f"{child.name}_{i}"
    rebased.bind = resolved_bind
    child_page_index = -1 - i
    return _render_element(rebased, child_page_index, ctx, _PlannedPage(elements=[]))


def _resolve_relative_bind(bind: str, item_bind: Optional[str]) -> Optional[str]:
    if not bind:
        return None
    if bind.startswith("@."):
        if not item_bind:
            return None
        return f"{item_bind}.{bind[2:]}"
    return bind


def _bound_array_length(bind: str, data) -> int:
    if data is None:
        return 0
    path = bind[1:] if bind.startswith("@") else bind
    pattern = re.compile(rf"^{re.escape(path)}\[(\d+)\](?:\.|$)")
    max_idx = -1
    for p in data.paths():
        m = pattern.match(p)
        if m:
            idx = int(m.group(1))
            if idx > max_idx:
                max_idx = idx
    return max_idx + 1


# ─────────────────────────────────────────────────────────────────────────────
# Data Binding
# ─────────────────────────────────────────────────────────────────────────────


def _lookup_bound_value(el, data) -> Optional[str]:
    if data is None or not el.bind:
        return None
    path = el.bind[1:] if el.bind.startswith("@") else el.bind
    if not path:
        return None
    val = data.get(path)
    if val is None:
        return None
    if isinstance(val, OdinString):
        return val.value
    if isinstance(val, (OdinNumber, OdinInteger)):
        return str(val.value)
    if isinstance(val, OdinBoolean):
        return "true" if val.value else "false"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────


def _escape_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _escape_attr(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _convert_points(points: str, unit: str) -> str:
    out = []
    for pair in points.strip().split():
        if "," not in pair:
            out.append(pair)
            continue
        x_str, y_str = pair.split(",", 1)
        out.append(f"{_num(to_pixels(float(x_str), unit))},{_num(to_pixels(float(y_str), unit))}")
    return " ".join(out)


def _num(value) -> str:
    """Format a number without a trailing ``.0`` for integral values."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)
