"""Form model types for ODIN Forms 1.0.

Declarative form definitions for print and screen rendering: print-first,
absolute positioning, bidirectional data binding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Union


# ─────────────────────────────────────────────────────────────────────────────
# Metadata and Settings
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class FormMetadata:
    """Document-level metadata from the ``{$}`` header."""

    title: str = ""
    id: str = ""
    lang: str = "en"
    version: Optional[str] = None


@dataclass
class PageMargins:
    """Per-side page margins under ``{$.page}``."""

    top: Optional[float] = None
    right: Optional[float] = None
    bottom: Optional[float] = None
    left: Optional[float] = None


@dataclass
class PageDefaults:
    """Default page dimensions applied to all pages. Corresponds to ``{$.page}``."""

    width: float = 8.5
    height: float = 11.0
    unit: str = "inch"
    margin: Optional[PageMargins] = None


@dataclass
class ScreenSettings:
    """Screen/web rendering options. Corresponds to ``{$.screen}``."""

    scale: float = 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Base Element
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class BaseElement:
    """Properties common to every form element."""

    type: str = ""
    name: str = ""
    id: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Geometric Elements
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class LineElement(BaseElement):
    """Line segment between two endpoints. (``{.line.*}``)"""

    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    stroke: Optional[str] = None
    stroke_width: Optional[float] = None
    stroke_opacity: Optional[float] = None
    stroke_dasharray: Optional[str] = None
    stroke_linecap: Optional[str] = None
    stroke_linejoin: Optional[str] = None


@dataclass
class RectElement(BaseElement):
    """Rectangle, optionally rounded. (``{.rect.*}``)"""

    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    rx: Optional[float] = None
    ry: Optional[float] = None
    stroke: Optional[str] = None
    stroke_width: Optional[float] = None
    stroke_opacity: Optional[float] = None
    stroke_dasharray: Optional[str] = None
    stroke_linecap: Optional[str] = None
    stroke_linejoin: Optional[str] = None
    fill: Optional[str] = None
    fill_opacity: Optional[float] = None


@dataclass
class CircleElement(BaseElement):
    """Circle defined by center and radius. (``{.circle.*}``)"""

    cx: float = 0.0
    cy: float = 0.0
    r: float = 0.0
    stroke: Optional[str] = None
    stroke_width: Optional[float] = None
    stroke_opacity: Optional[float] = None
    stroke_dasharray: Optional[str] = None
    stroke_linecap: Optional[str] = None
    stroke_linejoin: Optional[str] = None
    fill: Optional[str] = None
    fill_opacity: Optional[float] = None


@dataclass
class EllipseElement(BaseElement):
    """Ellipse defined by center and two radii. (``{.ellipse.*}``)"""

    cx: float = 0.0
    cy: float = 0.0
    rx: float = 0.0
    ry: float = 0.0
    stroke: Optional[str] = None
    stroke_width: Optional[float] = None
    stroke_opacity: Optional[float] = None
    stroke_dasharray: Optional[str] = None
    stroke_linecap: Optional[str] = None
    stroke_linejoin: Optional[str] = None
    fill: Optional[str] = None
    fill_opacity: Optional[float] = None


@dataclass
class PolygonElement(BaseElement):
    """Closed polygon from a list of points. (``{.polygon.*}``)"""

    points: str = ""
    stroke: Optional[str] = None
    stroke_width: Optional[float] = None
    stroke_opacity: Optional[float] = None
    stroke_dasharray: Optional[str] = None
    stroke_linecap: Optional[str] = None
    stroke_linejoin: Optional[str] = None
    fill: Optional[str] = None
    fill_opacity: Optional[float] = None


@dataclass
class PolylineElement(BaseElement):
    """Open polyline from a list of points. (``{.polyline.*}``)"""

    points: str = ""
    stroke: Optional[str] = None
    stroke_width: Optional[float] = None
    stroke_opacity: Optional[float] = None
    stroke_dasharray: Optional[str] = None
    stroke_linecap: Optional[str] = None
    stroke_linejoin: Optional[str] = None


@dataclass
class PathElement(BaseElement):
    """Arbitrary SVG-style path. (``{.path.*}``)"""

    d: str = ""
    stroke: Optional[str] = None
    stroke_width: Optional[float] = None
    stroke_opacity: Optional[float] = None
    stroke_dasharray: Optional[str] = None
    stroke_linecap: Optional[str] = None
    stroke_linejoin: Optional[str] = None
    fill: Optional[str] = None
    fill_opacity: Optional[float] = None


# ─────────────────────────────────────────────────────────────────────────────
# Content Elements
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class TextElement(BaseElement):
    """Static text label. (``{.text.*}``)"""

    content: str = ""
    x: float = 0.0
    y: float = 0.0
    rotate: Optional[float] = None
    font_family: Optional[str] = None
    font_size: Optional[float] = None
    font_weight: Optional[str] = None
    font_style: Optional[str] = None
    text_align: Optional[str] = None
    color: Optional[str] = None
    y_offset: Optional[float] = None
    x_offset: Optional[float] = None


@dataclass
class ImageElement(BaseElement):
    """Embedded image. (``{.img.*}``)"""

    src: str = ""
    alt: str = ""
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    background: Optional[bool] = None


@dataclass
class BarcodeElement(BaseElement):
    """1D or 2D barcode. (``{.barcode.*}``)"""

    barcode_type: str = "code128"
    content: str = ""
    alt: str = ""
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Field Elements
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class BaseFieldElement(BaseElement):
    """Properties shared by all field elements."""

    label: str = ""
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    bind: str = ""
    required: Optional[bool] = None
    pattern: Optional[str] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min: Optional[Union[str, float]] = None
    max: Optional[Union[str, float]] = None
    aria_label: Optional[str] = None
    tabindex: Optional[int] = None
    readonly: Optional[bool] = None
    y_offset: Optional[float] = None
    x_offset: Optional[float] = None


@dataclass
class TextFieldElement(BaseFieldElement):
    """Text input field. (``type = text``)"""

    value: Optional[str] = None
    input_type: Optional[str] = None
    mask: Optional[str] = None
    placeholder: Optional[str] = None
    multiline: Optional[bool] = None
    max_lines: Optional[int] = None


@dataclass
class CheckboxElement(BaseFieldElement):
    """Boolean checkbox field. (``type = checkbox``)"""

    checked: Optional[bool] = None


@dataclass
class RadioElement(BaseFieldElement):
    """Radio button field, part of a group. (``type = radio``)"""

    group: str = ""
    value: str = ""


@dataclass
class SelectElement(BaseFieldElement):
    """Single-selection dropdown field. (``type = select``)"""

    options: List[str] = field(default_factory=list)
    selected: Optional[str] = None
    placeholder: Optional[str] = None


@dataclass
class MultiselectElement(BaseFieldElement):
    """Multiple-selection list field. (``type = multiselect``)"""

    options: List[str] = field(default_factory=list)
    selected: Optional[List[str]] = None
    min_select: Optional[int] = None
    max_select: Optional[int] = None


@dataclass
class DateElement(BaseFieldElement):
    """Date input field. (``type = date``)"""

    value: Optional[str] = None


@dataclass
class SignatureElement(BaseFieldElement):
    """Signature capture area. (``type = signature``)"""

    value: Optional[str] = None
    date_field: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Regions and Templates
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class RegionElement(BaseElement):
    """Container grouping repeating content bound to an array. (``{.region.*}``)"""

    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    bind: Optional[str] = None
    max: Optional[int] = None
    overflow: Optional[str] = None
    children: List["FormElement"] = field(default_factory=list)


@dataclass
class FormPage:
    """A single form page with an ordered list of elements. (``{page[n]}``)"""

    elements: List["FormElement"] = field(default_factory=list)


@dataclass
class PageTemplate:
    """Layout for dynamically generated overflow pages. (``{@tpl_*}``)"""

    name: str = ""
    page_template: bool = True
    continues: Optional[str] = None
    form_id: Optional[str] = None
    elements: List["FormElement"] = field(default_factory=list)


@dataclass
class OdinForm:
    """Root ODIN Forms document."""

    metadata: FormMetadata = field(default_factory=FormMetadata)
    page_defaults: Optional[PageDefaults] = None
    screen: Optional[ScreenSettings] = None
    i18n: Optional[dict] = None
    pages: List[FormPage] = field(default_factory=list)
    templates: Optional[dict] = None


@dataclass
class RenderFormOptions:
    """Options passed to the form renderer."""

    target: str = "html"
    lang: Optional[str] = None
    scale: Optional[float] = None
    class_name: Optional[str] = None


# Discriminated element union.
FormElement = Union[
    LineElement,
    RectElement,
    CircleElement,
    EllipseElement,
    PolygonElement,
    PolylineElement,
    PathElement,
    TextElement,
    ImageElement,
    BarcodeElement,
    TextFieldElement,
    CheckboxElement,
    RadioElement,
    SelectElement,
    MultiselectElement,
    DateElement,
    SignatureElement,
    RegionElement,
]

FormFieldElement = Union[
    TextFieldElement,
    CheckboxElement,
    RadioElement,
    SelectElement,
    MultiselectElement,
    DateElement,
    SignatureElement,
]

FIELD_TYPES = frozenset(
    {
        "field.text",
        "field.checkbox",
        "field.radio",
        "field.select",
        "field.multiselect",
        "field.date",
        "field.signature",
    }
)
