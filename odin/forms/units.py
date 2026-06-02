"""Pixel conversions for form layout units."""

_DPI = 96
_CONVERSIONS = {
    "inch": _DPI,
    "cm": _DPI / 2.54,
    "mm": _DPI / 25.4,
    "pt": _DPI / 72,
}


def to_pixels(value: float, unit: str) -> float:
    """Convert a measurement in the given unit to pixels."""
    factor = _CONVERSIONS.get(unit)
    if factor is None:
        raise ValueError(f"Unknown unit: {unit}")
    return round(value * factor * 1000) / 1000


def from_pixels(px: float, unit: str) -> float:
    """Convert a pixel measurement back to the given unit."""
    factor = _CONVERSIONS.get(unit)
    if factor is None:
        raise ValueError(f"Unknown unit: {unit}")
    return round((px / factor) * 1000) / 1000
