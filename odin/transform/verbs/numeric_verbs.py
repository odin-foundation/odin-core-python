"""Numeric verbs for the ODIN transform engine."""

from __future__ import annotations

import math
import random
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple

from odin.transform.dyn_value import DynValue, DynType
from odin.transform.verbs.helpers import coerce_num, coerce_str, numeric_result, to_number


def _to_double(v: DynValue):
    """Convert DynValue to float, returning None if not convertible."""
    return coerce_num(v)


def _is_currency(v: DynValue) -> bool:
    """Check if a DynValue is a currency type."""
    return v.type in (DynType.CURRENCY, DynType.CURRENCY_RAW)


def _to_decimal(v: DynValue) -> Optional[Decimal]:
    """Convert DynValue to Decimal, returning None if not convertible."""
    if v.is_null():
        return None
    if v.type == DynType.INTEGER:
        return Decimal(v._int_value)
    if v.type == DynType.FLOAT:
        return Decimal(str(v._float_value))
    if v.type in (DynType.CURRENCY, DynType.PERCENT):
        return Decimal(str(v._float_value))
    if v.type in (DynType.FLOAT_RAW, DynType.CURRENCY_RAW):
        try:
            return Decimal(v._string_value or "0")
        except InvalidOperation:
            return None
    if v.type == DynType.BOOL:
        return Decimal(1) if v._bool_value else Decimal(0)
    if v.type == DynType.STRING:
        try:
            return Decimal(v._string_value or "0")
        except InvalidOperation:
            return None
    return None


def _decimal_result(v: Decimal, force_currency: bool = False) -> DynValue:
    """Return a DynValue from a Decimal, preserving currency type if needed."""
    if force_currency:
        return DynValue.of_currency(v)
    # Check if the Decimal is a whole number using Decimal arithmetic (no float epsilon)
    if v == v.to_integral_value():
        return DynValue.of_integer(int(v))
    return DynValue.of_float(float(v))


def _safe_numeric_result(v: float) -> DynValue:
    """Return numeric result, null for NaN/Infinity."""
    if math.isnan(v) or math.isinf(v):
        return DynValue.of_null()
    return numeric_result(v)


def _away_from_zero_round(value: float, decimals: int) -> float:
    """Round using away-from-zero (not Python's default banker's rounding)."""
    if decimals < 0:
        decimals = 0
    factor = 10 ** decimals
    scaled = value * factor
    if scaled >= 0:
        return math.floor(scaled + 0.5) / factor
    else:
        return math.ceil(scaled - 0.5) / factor


# ── Verb implementations ────────────────────────────────────────────

def verb_format_number(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    n = _to_double(args[0])
    if n is None:
        return DynValue.of_null()
    decimals = _to_double(args[1])
    if decimals is None:
        return DynValue.of_null()
    dp = max(0, int(decimals))
    return DynValue.of_string(f"{n:.{dp}f}")


def verb_format_integer(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    n = _to_double(args[0])
    if n is None:
        return DynValue.of_null()
    return DynValue.of_string(str(int(math.floor(n))))


def verb_format_currency(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    n = _to_double(args[0])
    if n is None:
        return DynValue.of_null()
    dp = 2
    if len(args) >= 2:
        d = _to_double(args[1])
        if d is not None:
            dp = max(0, int(d))
    return DynValue.of_string(f"{n:.{dp}f}")


def verb_format_percent(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    n = _to_double(args[0])
    if n is None:
        return DynValue.of_null()
    dp = 0
    if len(args) >= 2:
        d = _to_double(args[1])
        if d is not None:
            dp = max(0, int(d))
    pct = _away_from_zero_round(n * 100, dp)
    return DynValue.of_string(f"{pct:.{dp}f}%")


def verb_add(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    # Use Decimal arithmetic when either operand is currency
    if _is_currency(args[0]) or _is_currency(args[1]):
        da = _to_decimal(args[0])
        db = _to_decimal(args[1])
        if da is None or db is None:
            return DynValue.of_null()
        return _decimal_result(da + db)
    return numeric_result(to_number(args[0]) + to_number(args[1]))


def verb_subtract(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    if _is_currency(args[0]) or _is_currency(args[1]):
        da = _to_decimal(args[0])
        db = _to_decimal(args[1])
        if da is None or db is None:
            return DynValue.of_null()
        return _decimal_result(da - db)
    return numeric_result(to_number(args[0]) - to_number(args[1]))


def verb_multiply(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    if _is_currency(args[0]) or _is_currency(args[1]):
        da = _to_decimal(args[0])
        db = _to_decimal(args[1])
        if da is None or db is None:
            return DynValue.of_null()
        return _decimal_result(da * db)
    return numeric_result(to_number(args[0]) * to_number(args[1]))


def verb_divide(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    if _is_currency(args[0]) or _is_currency(args[1]):
        da = _to_decimal(args[0])
        db = _to_decimal(args[1])
        if da is None or db is None or db == 0:
            return DynValue.of_null()
        return DynValue.of_float(float(da / db))
    b = to_number(args[1])
    if b == 0:
        return DynValue.of_null()
    return DynValue.of_float(to_number(args[0]) / b)


def verb_mod(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    b = to_number(args[1])
    if b == 0:
        return DynValue.of_null()
    return numeric_result(math.fmod(to_number(args[0]), b))


def verb_abs(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    return numeric_result(abs(to_number(args[0])))


def verb_floor(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    return DynValue.of_integer(math.floor(to_number(args[0])))


def verb_ceil(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    return DynValue.of_integer(math.ceil(to_number(args[0])))


def verb_round(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    n = _to_double(args[0])
    if n is None:
        return DynValue.of_null()
    dp = 0
    if len(args) >= 2:
        d = _to_double(args[1])
        if d is not None:
            dp = max(0, int(d))
    # Use banker's rounding (round half to even) via Decimal for precision
    from decimal import Decimal, ROUND_HALF_EVEN
    dec = Decimal(str(n))
    quantize_str = "1" if dp == 0 else "0." + "0" * dp
    rounded = float(dec.quantize(Decimal(quantize_str), rounding=ROUND_HALF_EVEN))
    return numeric_result(rounded)


def verb_negate(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    return numeric_result(-to_number(args[0]))


def verb_sign(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    n = to_number(args[0])
    if n > 0:
        return DynValue.of_integer(1)
    elif n < 0:
        return DynValue.of_integer(-1)
    else:
        return DynValue.of_integer(0)


def verb_trunc(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    return DynValue.of_integer(math.trunc(to_number(args[0])))


def _string_to_seed(s: str) -> int:
    """DJB2 hash starting at 0."""
    h = 0
    for ch in s:
        h = ((h << 5) - h + ord(ch)) & 0xFFFFFFFF
    return h


class _Mulberry32:
    """Seeded 32-bit PRNG (Mulberry32)."""

    def __init__(self, seed: int) -> None:
        self._state = seed & 0xFFFFFFFF

    def next_float(self) -> float:
        self._state = (self._state + 0x6D2B79F5) & 0xFFFFFFFF
        t = self._state
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t = (t ^ (t + ((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0


def verb_random(args: List[DynValue], ctx: object) -> DynValue:
    # 1-arg string: seeded float in [0, 1)
    if len(args) == 1 and args[0].is_string():
        seed_str = coerce_str(args[0])
        seed_val = _string_to_seed(seed_str)
        rng = _Mulberry32(seed_val)
        return DynValue.of_float(rng.next_float())
    # 3-arg (min, max, seed_str): seeded integer in [min, max]
    if len(args) >= 3 and args[2].is_string():
        lo = _to_double(args[0])
        hi = _to_double(args[1])
        seed_str = coerce_str(args[2])
        if lo is not None and hi is not None:
            if lo > hi:
                return DynValue.of_null()
            lo_i = math.floor(lo)
            hi_i = math.floor(hi)
            seed_val = _string_to_seed(seed_str)
            rng = _Mulberry32(seed_val)
            f = rng.next_float()
            val = int(f * (hi_i - lo_i + 1)) + lo_i
            return DynValue.of_integer(val)
    # 2-arg (min, max): random float in [min, max]
    if len(args) >= 2:
        lo = _to_double(args[0])
        hi = _to_double(args[1])
        if lo is not None and hi is not None:
            if lo > hi:
                return DynValue.of_null()
            return DynValue.of_float(random.uniform(lo, hi))
    return DynValue.of_float(random.random())


def verb_min_of(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) == 0:
        return DynValue.of_null()
    # If first arg is an array, use it
    if len(args) == 1 and args[0].is_array():
        items = args[0].as_array()
    else:
        items = args
    result = None
    for item in items:
        n = _to_double(item)
        if n is not None and math.isfinite(n):
            if result is None or n < result:
                result = n
    if result is None:
        return DynValue.of_null()
    return numeric_result(result)


def verb_max_of(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) == 0:
        return DynValue.of_null()
    if len(args) == 1 and args[0].is_array():
        items = args[0].as_array()
    else:
        items = args
    result = None
    for item in items:
        n = _to_double(item)
        if n is not None and math.isfinite(n):
            if result is None or n > result:
                result = n
    if result is None:
        return DynValue.of_null()
    return numeric_result(result)


def verb_parse_int(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    v = args[0]
    if v.is_null():
        return DynValue.of_null()
    # Support optional radix/base as second argument
    radix = 10
    if len(args) >= 2:
        r = _to_double(args[1])
        if r is not None:
            radix = int(r)
    if radix != 10:
        # Parse string with given radix
        s = coerce_str(v)
        if not s:
            return DynValue.of_null()
        try:
            return DynValue.of_integer(int(s.strip(), radix))
        except (ValueError, TypeError):
            return DynValue.of_null()
    if v.type == DynType.INTEGER:
        return DynValue.of_integer(v._int_value)
    n = _to_double(v)
    if n is None:
        return DynValue.of_null()
    return DynValue.of_integer(int(math.floor(n)))


def verb_safe_divide(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    a = _to_double(args[0])
    b = _to_double(args[1])
    default_val = args[2] if len(args) >= 3 else DynValue.of_null()
    if a is None or b is None or b == 0 or math.isinf(b) or math.isnan(b):
        return default_val
    return numeric_result(a / b)


def verb_format_locale_number(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    n = _to_double(args[0])
    if n is None or math.isnan(n) or math.isinf(n):
        return DynValue.of_null()
    locale = coerce_str(args[1]) if len(args) >= 2 else "en-US"
    # Separators by locale group: (thousands, decimal)
    group, decimal = _LOCALE_SEPARATORS.get(locale.lower(), (",", "."))
    dp = -1
    if len(args) >= 3:
        d = _to_double(args[2])
        if d is not None:
            dp = max(0, int(d))
    if dp >= 0:
        base = f"{n:,.{dp}f}"
    elif n == math.floor(n):
        base = f"{int(n):,}"
    else:
        # Up to 3 fraction digits, trailing zeros trimmed
        base = f"{n:,.3f}".rstrip("0").rstrip(".")
    # Remap default en-US separators (',' group, '.' decimal) to the locale's
    return DynValue.of_string(
        base.replace(",", "\x00").replace(".", decimal).replace("\x00", group)
    )


_LOCALE_SEPARATORS = {
    "de-de": (".", ","),
    "fr-fr": (" ", ","),
    "en-us": (",", "."),
    "en-gb": (",", "."),
}


# ── Math functions (also registered here) ──────────────────

def verb_log(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    n = to_number(args[0])
    if n <= 0:
        return DynValue.of_null()
    if len(args) >= 2:
        base = to_number(args[1])
        if base <= 0 or base == 1:
            return DynValue.of_null()
        return _safe_numeric_result(math.log(n) / math.log(base))
    return _safe_numeric_result(math.log(n))


def verb_ln(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    n = _to_double(args[0])
    if n is None or n <= 0:
        return DynValue.of_null()
    return _safe_numeric_result(math.log(n))


def verb_log10(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    n = _to_double(args[0])
    if n is None or n <= 0:
        return DynValue.of_null()
    return _safe_numeric_result(math.log10(n))


def verb_exp(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    n = _to_double(args[0])
    if n is None:
        return DynValue.of_null()
    return _safe_numeric_result(math.exp(n))


def verb_pow(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    base = _to_double(args[0])
    exp = _to_double(args[1])
    if base is None or exp is None:
        return DynValue.of_null()
    try:
        result = math.pow(base, exp)
    except (OverflowError, ValueError):
        return DynValue.of_null()
    return _safe_numeric_result(result)


def verb_sqrt(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    n = _to_double(args[0])
    if n is None or n < 0:
        return DynValue.of_null()
    return _safe_numeric_result(math.sqrt(n))


def verb_clamp(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 3:
        return DynValue.of_null()
    n = _to_double(args[0])
    lo = _to_double(args[1])
    hi = _to_double(args[2])
    if n is None or lo is None or hi is None:
        return DynValue.of_null()
    return numeric_result(max(lo, min(hi, n)))


def verb_pi(args: List[DynValue], ctx: object) -> DynValue:
    return DynValue.of_float(math.pi)


def verb_e(args: List[DynValue], ctx: object) -> DynValue:
    return DynValue.of_float(math.e)


# Unit conversion families: unit -> factor relative to base unit
_UNIT_FAMILIES: Dict[str, Dict[str, float]] = {
    "mass": {"g": 1.0, "kg": 1000.0, "mg": 0.001, "lb": 453.59237, "oz": 28.3495, "ton": 907185.0, "tonne": 1000000.0},
    "length": {"m": 1.0, "km": 1000.0, "cm": 0.01, "mm": 0.001, "mi": 1609.344, "yd": 0.9144, "ft": 0.3048, "in": 0.0254},
    "volume": {"l": 1.0, "ml": 0.001, "gal": 3.78541, "qt": 0.946353, "pt": 0.473176, "cup": 0.236588, "floz": 0.0295735},
    "speed": {"m/s": 1.0, "km/h": 0.277778, "mph": 0.44704, "knot": 0.514444, "ft/s": 0.3048},
    "area": {"m2": 1.0, "km2": 1000000.0, "cm2": 0.0001, "ha": 10000.0, "acre": 4046.86, "ft2": 0.092903, "in2": 0.00064516, "mi2": 2589988.0},
    "data": {"B": 1.0, "KB": 1024.0, "MB": 1048576.0, "GB": 1073741824.0, "TB": 1099511627776.0},
    "time": {"s": 1.0, "ms": 0.001, "min": 60.0, "h": 3600.0, "d": 86400.0, "wk": 604800.0},
}

_TEMP_UNITS = {"C", "F", "K"}


def _find_unit_family(unit: str) -> Optional[Tuple[str, float]]:
    """Find which family a unit belongs to and its factor."""
    for family_name, units in _UNIT_FAMILIES.items():
        if unit in units:
            return (family_name, units[unit])
    return None


def _convert_temperature(value: float, from_unit: str, to_unit: str) -> float:
    """Convert between temperature units."""
    # Convert to Celsius first
    if from_unit == "F":
        celsius = (value - 32) * 5 / 9
    elif from_unit == "K":
        celsius = value - 273.15
    else:
        celsius = value
    # Convert from Celsius to target
    if to_unit == "F":
        return celsius * 9 / 5 + 32
    elif to_unit == "K":
        return celsius + 273.15
    return celsius


def verb_convert_unit(args: List[DynValue], ctx: object) -> DynValue:
    """Convert a value between units."""
    if len(args) < 3:
        return DynValue.of_null()
    n = _to_double(args[0])
    if n is None:
        return DynValue.of_null()
    from_unit = args[1].as_string() if args[1].is_string() else str(args[1].value())
    to_unit = args[2].as_string() if args[2].is_string() else str(args[2].value())
    # Temperature special case
    if from_unit in _TEMP_UNITS and to_unit in _TEMP_UNITS:
        result = _convert_temperature(n, from_unit, to_unit)
        result = round(result * 1000000) / 1000000
        return _safe_numeric_result(result)
    # One is temp, other is not → incompatible
    if from_unit in _TEMP_UNITS or to_unit in _TEMP_UNITS:
        return DynValue.of_null()
    from_info = _find_unit_family(from_unit)
    to_info = _find_unit_family(to_unit)
    if from_info is None or to_info is None:
        return DynValue.of_null()
    from_family, from_factor = from_info
    to_family, to_factor = to_info
    if from_family != to_family:
        return DynValue.of_null()
    result = n * from_factor / to_factor
    result = round(result * 1000000) / 1000000
    return _safe_numeric_result(result)


def verb_gcd(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    a = abs(math.trunc(to_number(args[0])))
    b = abs(math.trunc(to_number(args[1])))
    while b != 0:
        a, b = b, a % b
    return DynValue.of_integer(a)


def verb_lcm(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    a = abs(math.trunc(to_number(args[0])))
    b = abs(math.trunc(to_number(args[1])))
    if a == 0 or b == 0:
        return DynValue.of_integer(0)
    x, y = a, b
    while y != 0:
        x, y = y, x % y
    return DynValue.of_integer((a // x) * b)


def verb_factorial(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    n = to_number(args[0])
    if n != math.floor(n) or n < 0 or n > 18:
        return DynValue.of_null()
    n = int(n)
    result = 1
    for i in range(2, n + 1):
        result *= i
    return DynValue.of_integer(result)
