"""Geo verbs for the ODIN transform engine."""

from __future__ import annotations

import math
from typing import List, Optional

from odin.transform.dyn_value import DynValue
from odin.transform.verbs.helpers import coerce_num

EARTH_RADIUS_KM = 6371.0
EARTH_RADIUS_MILES = 3959.0
DEG_TO_RAD = math.pi / 180.0
RAD_TO_DEG = 180.0 / math.pi


def _to_double(v: DynValue) -> Optional[float]:
    return coerce_num(v)


def _validate_lat(lat: float) -> bool:
    return -90 <= lat <= 90


def _validate_lon(lon: float) -> bool:
    return -180 <= lon <= 180


# ── Verb implementations ────────────────────────────────────────────

def verb_distance(args: List[DynValue], ctx: object) -> DynValue:
    """Haversine great-circle distance."""
    if len(args) < 4:
        return DynValue.of_null()
    lat1 = _to_double(args[0])
    lon1 = _to_double(args[1])
    lat2 = _to_double(args[2])
    lon2 = _to_double(args[3])
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return DynValue.of_null()
    if not (_validate_lat(lat1) and _validate_lat(lat2) and
            _validate_lon(lon1) and _validate_lon(lon2)):
        return DynValue.of_null()

    radius = EARTH_RADIUS_KM
    if len(args) >= 5:
        from odin.transform.verbs.helpers import coerce_str
        unit = coerce_str(args[4]).lower()
        valid_units = ("km", "mi", "miles")
        if unit in ("miles", "mi"):
            radius = EARTH_RADIUS_MILES
        elif unit not in valid_units:
            # T011 INCOMPATIBLE_CONVERSION: unknown unit for distance.
            # Verbs currently cannot push errors onto the context, so we
            # return null.  When VerbContext gains an errors list this
            # should emit:
            #   incompatible_conversion_error(
            #       "distance",
            #       f"unknown unit '{unit}' (expected 'km', 'mi', or 'miles')",
            #   )
            return DynValue.of_null()

    dlat = (lat2 - lat1) * DEG_TO_RAD
    dlon = (lon2 - lon1) * DEG_TO_RAD
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(lat1 * DEG_TO_RAD) * math.cos(lat2 * DEG_TO_RAD) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return DynValue.of_float(radius * c)


def verb_in_bounding_box(args: List[DynValue], ctx: object) -> DynValue:
    """Check if point is within bounding box."""
    if len(args) < 6:
        return DynValue.of_null()
    lat = _to_double(args[0])
    lon = _to_double(args[1])
    min_lat = _to_double(args[2])
    min_lon = _to_double(args[3])
    max_lat = _to_double(args[4])
    max_lon = _to_double(args[5])
    if any(v is None for v in [lat, lon, min_lat, min_lon, max_lat, max_lon]):
        return DynValue.of_null()
    return DynValue.of_bool(min_lat <= lat <= max_lat and min_lon <= lon <= max_lon)


def verb_to_radians(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    n = _to_double(args[0])
    if n is None:
        return DynValue.of_null()
    return DynValue.of_float(n * DEG_TO_RAD)


def verb_to_degrees(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    n = _to_double(args[0])
    if n is None:
        return DynValue.of_null()
    return DynValue.of_float(n * RAD_TO_DEG)


def verb_bearing(args: List[DynValue], ctx: object) -> DynValue:
    """Initial bearing from point 1 to point 2 (0-360 degrees)."""
    if len(args) < 4:
        return DynValue.of_null()
    lat1 = _to_double(args[0])
    lon1 = _to_double(args[1])
    lat2 = _to_double(args[2])
    lon2 = _to_double(args[3])
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return DynValue.of_null()
    if not (_validate_lat(lat1) and _validate_lat(lat2) and
            _validate_lon(lon1) and _validate_lon(lon2)):
        return DynValue.of_null()

    lat1_r = lat1 * DEG_TO_RAD
    lat2_r = lat2 * DEG_TO_RAD
    dlon = (lon2 - lon1) * DEG_TO_RAD

    y = math.sin(dlon) * math.cos(lat2_r)
    x = (math.cos(lat1_r) * math.sin(lat2_r) -
         math.sin(lat1_r) * math.cos(lat2_r) * math.cos(dlon))
    bearing = math.atan2(y, x) * RAD_TO_DEG
    return DynValue.of_float((bearing + 360) % 360)


def verb_midpoint(args: List[DynValue], ctx: object) -> DynValue:
    """Geographic midpoint on great circle."""
    if len(args) < 4:
        return DynValue.of_null()
    lat1 = _to_double(args[0])
    lon1 = _to_double(args[1])
    lat2 = _to_double(args[2])
    lon2 = _to_double(args[3])
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return DynValue.of_null()
    if not (_validate_lat(lat1) and _validate_lat(lat2) and
            _validate_lon(lon1) and _validate_lon(lon2)):
        return DynValue.of_null()

    lat1_r = lat1 * DEG_TO_RAD
    lat2_r = lat2 * DEG_TO_RAD
    lon1_r = lon1 * DEG_TO_RAD
    dlon = (lon2 - lon1) * DEG_TO_RAD

    bx = math.cos(lat2_r) * math.cos(dlon)
    by = math.cos(lat2_r) * math.sin(dlon)

    mid_lat = math.atan2(
        math.sin(lat1_r) + math.sin(lat2_r),
        math.sqrt((math.cos(lat1_r) + bx) ** 2 + by ** 2)
    )
    mid_lon = lon1_r + math.atan2(by, math.cos(lat1_r) + bx)

    return DynValue.of_object({
        "lat": DynValue.of_float(mid_lat * RAD_TO_DEG),
        "lon": DynValue.of_float(mid_lon * RAD_TO_DEG),
    })
