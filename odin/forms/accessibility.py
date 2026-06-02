"""Accessibility helpers for the form HTML renderer.

Pure functions producing accessible markup: IDs, labels, ARIA attributes,
fieldset grouping, tab ordering, skip links, and WCAG contrast checks.
"""

from __future__ import annotations

from typing import Dict, List

from .types import FIELD_TYPES, BaseFieldElement, FormElement


def generate_field_id(element_name: str, page_index: int) -> str:
    """Return a stable HTML element ID for a form field."""
    return f"odin-field-{page_index}-{element_name}"


def field_label_html(label: str, input_id: str) -> str:
    """Return an HTML ``<label>`` bound to the given input ID."""
    return f'<label for="{input_id}" class="odin-form-label">{label}</label>'


def field_aria_attrs(element: BaseFieldElement, page_index: int) -> Dict[str, str]:
    """Return ARIA and ``id`` attributes for a field element."""
    attrs: Dict[str, str] = {
        "id": generate_field_id(element.name, page_index),
        "aria-label": element.aria_label or element.label,
    }
    if element.required:
        attrs["aria-required"] = "true"
    return attrs


def field_group_html(group_name: str, legend: str, content: str) -> str:
    """Wrap content in a ``<fieldset>`` with a ``<legend>`` for grouped controls."""
    del group_name
    return (
        '<fieldset class="odin-form-fieldset">'
        f'<legend class="odin-form-legend">{legend}</legend>'
        f"{content}"
        "</fieldset>"
    )


def tab_order_sort(elements: List[FormElement]) -> List[FormElement]:
    """Return field elements sorted top-to-bottom then left-to-right."""
    fields = [el for el in elements if el.type in FIELD_TYPES]
    return sorted(fields, key=lambda el: (el.y, el.x))


def skip_link_html(form_title: str) -> str:
    """Return a skip-navigation link targeting the form content."""
    return (
        '<a class="odin-form-sr-only odin-form-skip" href="#odin-form-content">'
        f"Skip to {form_title}"
        "</a>"
    )


def sr_only_html(text: str) -> str:
    """Wrap text in a visually-hidden span announced by screen readers."""
    return f'<span class="odin-form-sr-only">{text}</span>'


def _linearize(channel: int) -> float:
    srgb = channel / 255
    if srgb <= 0.04045:
        return srgb / 12.92
    return ((srgb + 0.055) / 1.055) ** 2.4


def _parse_hex(hex_str: str) -> tuple:
    clean = hex_str[1:] if hex_str.startswith("#") else hex_str
    if len(clean) != 6 or any(c not in "0123456789abcdefABCDEF" for c in clean):
        raise ValueError(f'Invalid hex colour: "{hex_str}"')
    return (
        int(clean[0:2], 16),
        int(clean[2:4], 16),
        int(clean[4:6], 16),
    )


def _relative_luminance(hex_str: str) -> float:
    r, g, b = _parse_hex(hex_str)
    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)


def contrast_ratio(fg: str, bg: str) -> float:
    """Return the WCAG 2.x contrast ratio between two hex colours."""
    l1 = _relative_luminance(fg)
    l2 = _relative_luminance(bg)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def meets_contrast_aa(fg: str, bg: str, font_size: float) -> bool:
    """Return whether the contrast meets WCAG 2.x Level AA for the font size."""
    ratio = contrast_ratio(fg, bg)
    is_large_text = font_size >= 18
    return ratio >= 3.0 if is_large_text else ratio >= 4.5
