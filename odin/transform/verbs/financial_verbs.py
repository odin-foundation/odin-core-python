"""Financial verbs for the ODIN transform engine."""

from __future__ import annotations

import math
from typing import List, Optional

from odin.transform.dyn_value import DynValue, DynType
from odin.transform.verbs.helpers import coerce_num, numeric_result


def _to_double(v: DynValue) -> Optional[float]:
    return coerce_num(v)


def _safe_result(v: float) -> DynValue:
    """Return numeric result, null for NaN/Infinity."""
    if math.isnan(v) or math.isinf(v):
        return DynValue.of_null()
    return numeric_result(v)


def _extract_doubles(v: DynValue) -> List[float]:
    """Extract numeric array from DynValue."""
    if not v.is_array():
        return []
    result = []
    for item in v.as_array():
        n = coerce_num(item)
        if n is not None:
            result.append(n)
    return result


def _fsum(values) -> float:
    """Left-fold summation from 0.0 (sequential accumulation)."""
    total = 0.0
    for v in values:
        total += v
    return total


def _mean(values: List[float]) -> float:
    return _fsum(values) / len(values)


def _population_variance(values: List[float]) -> Optional[float]:
    if not values:
        return None
    mean = _mean(values)
    return _fsum((x - mean) ** 2 for x in values) / len(values)


def _sample_variance(values: List[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    mean = _mean(values)
    return _fsum((x - mean) ** 2 for x in values) / (len(values) - 1)


# ── Time Value of Money ─────────────────────────────────────────────

def verb_compound(args: List[DynValue], ctx: object) -> DynValue:
    """FV = principal * (1 + rate)^periods"""
    if len(args) < 3:
        return DynValue.of_null()
    p = _to_double(args[0])
    r = _to_double(args[1])
    n = _to_double(args[2])
    if p is None or r is None or n is None:
        return DynValue.of_null()
    result = p * math.pow(1 + r, n)
    return _safe_result(result)


def verb_discount(args: List[DynValue], ctx: object) -> DynValue:
    """PV = FV / (1 + rate)^periods"""
    if len(args) < 3:
        return DynValue.of_null()
    fv = _to_double(args[0])
    r = _to_double(args[1])
    n = _to_double(args[2])
    if fv is None or r is None or n is None:
        return DynValue.of_null()
    divisor = math.pow(1 + r, n)
    if divisor == 0:
        return DynValue.of_null()
    result = fv / divisor
    return _safe_result(result)


def verb_pmt(args: List[DynValue], ctx: object) -> DynValue:
    """Payment for a loan."""
    if len(args) < 3:
        return DynValue.of_null()
    p = _to_double(args[0])
    r = _to_double(args[1])
    n = _to_double(args[2])
    if p is None or r is None or n is None or n <= 0:
        return DynValue.of_null()
    if r == 0:
        return _safe_result(p / n)
    pv = math.pow(1 + r, n)
    result = (p * r * pv) / (pv - 1)
    return _safe_result(result)


def verb_fv(args: List[DynValue], ctx: object) -> DynValue:
    """Future value of annuity."""
    if len(args) < 3:
        return DynValue.of_null()
    pmt = _to_double(args[0])
    r = _to_double(args[1])
    n = _to_double(args[2])
    if pmt is None or r is None or n is None:
        return DynValue.of_null()
    if r == 0:
        return _safe_result(pmt * n)
    result = pmt * (math.pow(1 + r, n) - 1) / r
    return _safe_result(result)


def verb_pv(args: List[DynValue], ctx: object) -> DynValue:
    """Present value of annuity."""
    if len(args) < 3:
        return DynValue.of_null()
    pmt = _to_double(args[0])
    r = _to_double(args[1])
    n = _to_double(args[2])
    if pmt is None or r is None or n is None:
        return DynValue.of_null()
    if r == 0:
        return _safe_result(pmt * n)
    result = pmt * (1 - math.pow(1 + r, -n)) / r
    return _safe_result(result)


def verb_npv(args: List[DynValue], ctx: object) -> DynValue:
    """Net Present Value."""
    if len(args) < 2:
        return DynValue.of_null()
    r = _to_double(args[0])
    if r is None:
        return DynValue.of_null()
    cashflows = _extract_doubles(args[1])
    if not cashflows:
        return DynValue.of_null()
    total = 0.0
    for t, cf in enumerate(cashflows):
        total += cf / math.pow(1 + r, t)
    return _safe_result(total)


def verb_irr(args: List[DynValue], ctx: object) -> DynValue:
    """Internal Rate of Return (Newton-Raphson)."""
    if len(args) < 1:
        return DynValue.of_null()
    cashflows = _extract_doubles(args[0])
    if len(cashflows) < 2:
        return DynValue.of_null()
    guess = 0.1
    if len(args) >= 2:
        g = _to_double(args[1])
        if g is not None:
            guess = g

    rate = guess
    for _ in range(200):
        npv_val = 0.0
        dnpv = 0.0
        for t, cf in enumerate(cashflows):
            denom = math.pow(1 + rate, t)
            if denom == 0:
                return DynValue.of_null()
            npv_val += cf / denom
            if t > 0:
                dnpv -= t * cf / math.pow(1 + rate, t + 1)
        if abs(dnpv) < 1e-15:
            return DynValue.of_null()
        new_rate = rate - npv_val / dnpv
        if abs(new_rate - rate) < 1e-10:
            return _safe_result(new_rate)
        rate = new_rate
        if abs(rate) > 1e6:
            return DynValue.of_null()
    return DynValue.of_null()


def verb_rate(args: List[DynValue], ctx: object) -> DynValue:
    """Interest rate per period (Newton-Raphson)."""
    if len(args) < 3:
        return DynValue.of_null()
    nper = _to_double(args[0])
    pmt = _to_double(args[1])
    pv_val = _to_double(args[2])
    fv_val = 0.0
    if len(args) >= 4:
        f = _to_double(args[3])
        if f is not None:
            fv_val = f
    if nper is None or pmt is None or pv_val is None:
        return DynValue.of_null()

    rate = 0.1
    for _ in range(100):
        pn = math.pow(1 + rate, nper)
        f_val = pv_val * pn + pmt * (pn - 1) / rate + fv_val if rate != 0 else pv_val + pmt * nper + fv_val
        if rate == 0:
            break
        df = pv_val * nper * math.pow(1 + rate, nper - 1) + pmt * (nper * math.pow(1 + rate, nper - 1) * rate - (pn - 1)) / (rate * rate)
        if abs(df) < 1e-15:
            return DynValue.of_null()
        new_rate = rate - f_val / df
        if abs(new_rate - rate) < 1e-10:
            return _safe_result(new_rate)
        rate = new_rate
    return _safe_result(rate)


def verb_nper(args: List[DynValue], ctx: object) -> DynValue:
    """Number of periods."""
    if len(args) < 3:
        return DynValue.of_null()
    r = _to_double(args[0])
    pmt = _to_double(args[1])
    pv_val = _to_double(args[2])
    if r is None or pmt is None or pv_val is None:
        return DynValue.of_null()
    if r == 0:
        if pmt == 0:
            return DynValue.of_null()
        return _safe_result(-pv_val / pmt)
    ratio = pmt / (pmt + r * pv_val)
    if ratio <= 0:
        return DynValue.of_null()
    result = math.log(ratio) / math.log(1 + r)
    return _safe_result(result)


def verb_depreciation(args: List[DynValue], ctx: object) -> DynValue:
    """Straight-line depreciation."""
    if len(args) < 3:
        return DynValue.of_null()
    cost = _to_double(args[0])
    salvage = _to_double(args[1])
    life = _to_double(args[2])
    if cost is None or salvage is None or life is None or life <= 0:
        return DynValue.of_null()
    if salvage > cost:
        return DynValue.of_null()
    return _safe_result((cost - salvage) / life)


# ── Statistical ─────────────────────────────────────────────────────

def verb_variance(args: List[DynValue], ctx: object) -> DynValue:
    """Population variance."""
    if len(args) < 1:
        return DynValue.of_null()
    values = _extract_doubles(args[0])
    result = _population_variance(values)
    if result is None:
        return DynValue.of_null()
    return _safe_result(result)


def verb_variance_sample(args: List[DynValue], ctx: object) -> DynValue:
    """Sample variance (n-1)."""
    if len(args) < 1:
        return DynValue.of_null()
    values = _extract_doubles(args[0])
    result = _sample_variance(values)
    if result is None:
        return DynValue.of_null()
    return _safe_result(result)


def verb_std(args: List[DynValue], ctx: object) -> DynValue:
    """Population standard deviation."""
    if len(args) < 1:
        return DynValue.of_null()
    values = _extract_doubles(args[0])
    v = _population_variance(values)
    if v is None:
        return DynValue.of_null()
    return _safe_result(math.sqrt(v))


def verb_std_sample(args: List[DynValue], ctx: object) -> DynValue:
    """Sample standard deviation."""
    if len(args) < 1:
        return DynValue.of_null()
    values = _extract_doubles(args[0])
    v = _sample_variance(values)
    if v is None:
        return DynValue.of_null()
    return _safe_result(math.sqrt(v))


def verb_median(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    values = _extract_doubles(args[0])
    if not values:
        return DynValue.of_null()
    values.sort()
    n = len(values)
    if n % 2 == 1:
        return _safe_result(values[n // 2])
    return _safe_result((values[n // 2 - 1] + values[n // 2]) / 2)


def verb_mode(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 1:
        return DynValue.of_null()
    values = _extract_doubles(args[0])
    if not values:
        return DynValue.of_null()
    counts: dict = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    max_count = max(counts.values())
    for v in values:
        if counts[v] == max_count:
            return _safe_result(v)
    return DynValue.of_null()


def verb_percentile(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    values = _extract_doubles(args[0])
    pct = _to_double(args[1])
    if not values or pct is None or pct < 0 or pct > 100:
        return DynValue.of_null()
    values.sort()
    n = len(values)
    if n == 1:
        return _safe_result(values[0])
    idx = (pct / 100) * (n - 1)
    lower = int(math.floor(idx))
    upper = min(lower + 1, n - 1)
    frac = idx - lower
    result = values[lower] + frac * (values[upper] - values[lower])
    return _safe_result(result)


def verb_quantile(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    q = _to_double(args[1])
    if q is None or q < 0 or q > 1:
        return DynValue.of_null()
    # Convert quantile to percentile
    new_args = [args[0], DynValue.of_float(q * 100)]
    return verb_percentile(new_args, ctx)


def verb_covariance(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    x_vals = _extract_doubles(args[0])
    y_vals = _extract_doubles(args[1])
    n = min(len(x_vals), len(y_vals))
    if n == 0:
        return DynValue.of_null()
    x_vals = x_vals[:n]
    y_vals = y_vals[:n]
    x_mean = sum(x_vals) / n
    y_mean = sum(y_vals) / n
    cov = sum((x_vals[i] - x_mean) * (y_vals[i] - y_mean) for i in range(n)) / n
    return _safe_result(cov)


def verb_correlation(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    x_vals = _extract_doubles(args[0])
    y_vals = _extract_doubles(args[1])
    n = min(len(x_vals), len(y_vals))
    if n == 0:
        return DynValue.of_null()
    x_vals = x_vals[:n]
    y_vals = y_vals[:n]
    x_mean = sum(x_vals) / n
    y_mean = sum(y_vals) / n
    cov = sum((x_vals[i] - x_mean) * (y_vals[i] - y_mean) for i in range(n))
    x_var = sum((x - x_mean) ** 2 for x in x_vals)
    y_var = sum((y - y_mean) ** 2 for y in y_vals)
    denom = math.sqrt(x_var * y_var)
    if denom == 0:
        return DynValue.of_null()
    return _safe_result(cov / denom)


def verb_zscore(args: List[DynValue], ctx: object) -> DynValue:
    """Z-score of a value relative to an array's mean and population stddev."""
    if len(args) < 2:
        return DynValue.of_null()
    value = _to_double(args[0])
    values = _extract_doubles(args[1])
    if value is None or not values:
        return DynValue.of_null()
    mean = _mean(values)
    var = _fsum((x - mean) ** 2 for x in values) / len(values)
    stddev = math.sqrt(var)
    if stddev == 0:
        return DynValue.of_null()
    return _safe_result((value - mean) / stddev)


def verb_interpolate(args: List[DynValue], ctx: object) -> DynValue:
    """Linear interpolation between (x1,y1) and (x2,y2) at x."""
    if len(args) < 5:
        return DynValue.of_null()
    x = _to_double(args[0])
    x1 = _to_double(args[1])
    y1 = _to_double(args[2])
    x2 = _to_double(args[3])
    y2 = _to_double(args[4])
    if None in (x, x1, y1, x2, y2):
        return DynValue.of_null()
    if x2 == x1:
        return _safe_result(y1)
    return _safe_result(y1 + (x - x1) * (y2 - y1) / (x2 - x1))


def verb_weighted_avg(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    values = _extract_doubles(args[0])
    weights = _extract_doubles(args[1])
    n = min(len(values), len(weights))
    if n == 0:
        return DynValue.of_null()
    total = sum(values[i] * weights[i] for i in range(n))
    total_weight = sum(weights[:n])
    if total_weight == 0:
        return DynValue.of_null()
    return _safe_result(total / total_weight)


def verb_moving_avg(args: List[DynValue], ctx: object) -> DynValue:
    """Rolling window average over an array of numbers."""
    if len(args) < 2:
        return DynValue.of_null()
    arr = args[0]
    if not arr.is_array():
        return DynValue.of_null()
    items = arr.as_array()
    window = _to_double(args[1])
    if window is None or window < 1:
        return DynValue.of_null()
    win = int(window)
    values: List[float] = []
    for item in items:
        v = _to_double(item)
        values.append(v if v is not None else 0.0)
    result: List[DynValue] = []
    for i in range(len(values)):
        start = max(0, i - win + 1)
        window_vals = values[start:i + 1]
        avg = sum(window_vals) / len(window_vals)
        result.append(_safe_result(avg))
    return DynValue.of_array(result)


def _extract_days(v: DynValue) -> Optional[List[float]]:
    """Extract an array of day numbers from dates, timestamps, or numerics."""
    from datetime import date, datetime
    if not v.is_array():
        return None
    out: List[float] = []
    for item in v.as_array():
        if item.type in (DynType.DATE, DynType.TIMESTAMP):
            s = item._string_value or ""
            try:
                if "T" in s:
                    dt = datetime.fromisoformat(s)
                    out.append(dt.timestamp() / 86400.0)
                else:
                    d = date.fromisoformat(s[:10])
                    out.append((d - date(1970, 1, 1)).days)
            except ValueError:
                out.append(float("nan"))
        else:
            n = coerce_num(item)
            out.append(n if n is not None else float("nan"))
    return out


def _xnpv_at(rate: float, amounts: List[float], days: List[float]) -> float:
    d0 = days[0]
    total = 0.0
    for amt, d in zip(amounts, days):
        total += amt / math.pow(1 + rate, (d - d0) / 365.0)
    return total


def verb_xnpv(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 3:
        return DynValue.of_null()
    rate = _to_double(args[0])
    if rate is None:
        return DynValue.of_null()
    amounts = _extract_doubles(args[1]) if args[1].is_array() else None
    days = _extract_days(args[2])
    if not amounts or not days or len(amounts) != len(days):
        return DynValue.of_null()
    if any(not math.isfinite(x) for x in amounts + days):
        return DynValue.of_null()
    return _safe_result(_xnpv_at(rate, amounts, days))


def verb_xirr(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    amounts = _extract_doubles(args[0]) if args[0].is_array() else None
    days = _extract_days(args[1])
    if not amounts or not days or len(amounts) < 2 or len(amounts) != len(days):
        return DynValue.of_null()
    if any(not math.isfinite(x) for x in amounts + days):
        return DynValue.of_null()
    rate = _to_double(args[2]) if len(args) >= 3 else 0.1
    if rate is None:
        rate = 0.1
    d0 = days[0]
    for _ in range(100):
        value = 0.0
        derivative = 0.0
        for amt, d in zip(amounts, days):
            exp = (d - d0) / 365.0
            value += amt / math.pow(1 + rate, exp)
            derivative -= (exp * amt) / math.pow(1 + rate, exp + 1)
        if abs(value) < 1e-7:
            return _safe_result(rate)
        if abs(derivative) < 1e-12:
            return DynValue.of_null()
        nxt = rate - value / derivative
        if not math.isfinite(nxt) or nxt <= -1:
            return DynValue.of_null()
        rate = nxt
    return DynValue.of_null()
