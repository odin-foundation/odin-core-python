"""Extended tests for financial verbs — ~200 tests covering all financial verbs thoroughly."""

import math
import pytest
from odin.transform.dyn_value import DynValue, DynType
from odin.transform.engine import TransformEngine
from odin.transform.verb_registry import create_default_registry


def _engine():
    return TransformEngine(create_default_registry())


def invoke(verb_name, *raw_args):
    engine = _engine()
    args = [_to_dyn(a) for a in raw_args]
    return engine.invoke_verb(verb_name, args)


def _to_dyn(v):
    if isinstance(v, DynValue):
        return v
    if v is None:
        return DynValue.of_null()
    if isinstance(v, bool):
        return DynValue.of_bool(v)
    if isinstance(v, int):
        return DynValue.of_integer(v)
    if isinstance(v, float):
        return DynValue.of_float(v)
    if isinstance(v, str):
        return DynValue.of_string(v)
    if isinstance(v, list):
        return DynValue.of_array([_to_dyn(x) for x in v])
    if isinstance(v, dict):
        return DynValue.of_object({k: _to_dyn(val) for k, val in v.items()})
    return DynValue.of_string(str(v))


def assert_numeric(result, expected, tol=0.01):
    n = result.as_float() if result.type in (DynType.FLOAT, DynType.INTEGER) else None
    assert n is not None, f"Expected numeric, got {result.type}"
    assert abs(n - expected) < tol, f"Expected {expected}, got {n}"


# ══════════════════════════════════════════════════════════════════════
# compound: FV = principal * (1 + rate)^periods
# ══════════════════════════════════════════════════════════════════════

class TestCompoundExtended:
    @pytest.mark.parametrize("principal,rate,periods,expected", [
        (1000.0, 0.05, 10, 1000 * (1.05 ** 10)),
        (1000.0, 0.0, 10, 1000.0),
        (500.0, 0.10, 1, 550.0),
        (1000.0, 0.05, 0, 1000.0),
        (0.0, 0.05, 10, 0.0),
        (1000.0, 0.12, 5, 1000 * (1.12 ** 5)),
        (10000.0, 0.08, 20, 10000 * (1.08 ** 20)),
        (100.0, 0.01, 360, 100 * (1.01 ** 360)),
    ])
    def test_various(self, principal, rate, periods, expected):
        r = invoke("compound", principal, rate, periods)
        assert_numeric(r, expected, tol=0.1)

    def test_negative_rate(self):
        r = invoke("compound", 1000.0, -0.05, 10)
        assert_numeric(r, 1000 * (0.95 ** 10), tol=0.01)

    def test_null_principal(self):
        r = invoke("compound", None, 0.05, 10)
        assert r.is_null()

    def test_null_rate(self):
        r = invoke("compound", 1000.0, None, 10)
        assert r.is_null()

    def test_null_periods(self):
        r = invoke("compound", 1000.0, 0.05, None)
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# discount: PV = FV / (1 + rate)^periods
# ══════════════════════════════════════════════════════════════════════

class TestDiscountExtended:
    @pytest.mark.parametrize("fv,rate,periods,expected", [
        (1000.0, 0.05, 10, 1000 / (1.05 ** 10)),
        (1100.0, 0.10, 1, 1000.0),
        (1000.0, 0.0, 10, 1000.0),
        (1000.0, 0.05, 0, 1000.0),
        (0.0, 0.05, 10, 0.0),
        (5000.0, 0.08, 5, 5000 / (1.08 ** 5)),
    ])
    def test_various(self, fv, rate, periods, expected):
        r = invoke("discount", fv, rate, periods)
        assert_numeric(r, expected, tol=0.01)

    def test_compound_discount_inverse(self):
        # compound then discount should return original
        principal = 1000.0
        rate = 0.05
        periods = 10
        fv = invoke("compound", principal, rate, periods)
        pv = invoke("discount", fv.as_float(), rate, periods)
        assert_numeric(pv, principal, tol=0.01)

    def test_null_fv(self):
        r = invoke("discount", None, 0.05, 10)
        assert r.is_null()

    def test_null_rate(self):
        r = invoke("discount", 1000.0, None, 10)
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# pmt: loan payment
# ══════════════════════════════════════════════════════════════════════

class TestPmtExtended:
    def test_typical_mortgage(self):
        # 200k loan, 0.5% monthly rate, 360 months
        r = invoke("pmt", 200000.0, 0.005, 360.0)
        n = r.as_float()
        assert 1000 < n < 1500

    @pytest.mark.parametrize("principal,rate,nper,expected", [
        (12000.0, 0.0, 12.0, 1000.0),
        (10000.0, 0.0, 10.0, 1000.0),
        (60000.0, 0.0, 60.0, 1000.0),
    ])
    def test_zero_rate(self, principal, rate, nper, expected):
        r = invoke("pmt", principal, rate, nper)
        assert_numeric(r, expected)

    def test_one_period(self):
        r = invoke("pmt", 1000.0, 0.05, 1.0)
        assert_numeric(r, 1050.0)

    def test_zero_periods_returns_null(self):
        r = invoke("pmt", 1000.0, 0.05, 0.0)
        assert r.is_null()

    def test_null_principal(self):
        r = invoke("pmt", None, 0.05, 12.0)
        assert r.is_null()

    def test_null_rate(self):
        r = invoke("pmt", 1000.0, None, 12.0)
        assert r.is_null()

    def test_null_nper(self):
        r = invoke("pmt", 1000.0, 0.05, None)
        assert r.is_null()

    def test_small_rate(self):
        r = invoke("pmt", 100000.0, 0.001, 120.0)
        n = r.as_float()
        assert n > 0


# ══════════════════════════════════════════════════════════════════════
# fv: future value of annuity
# ══════════════════════════════════════════════════════════════════════

class TestFvExtended:
    @pytest.mark.parametrize("pmt_val,rate,nper,expected", [
        (100.0, 0.0, 12.0, 1200.0),
        (100.0, 0.0, 1.0, 100.0),
        (0.0, 0.05, 12.0, 0.0),
    ])
    def test_various(self, pmt_val, rate, nper, expected):
        r = invoke("fv", pmt_val, rate, nper)
        assert_numeric(r, expected)

    def test_with_rate(self):
        r = invoke("fv", 100.0, 0.01, 12.0)
        n = r.as_float()
        assert n > 1200  # compound interest adds value

    def test_with_high_rate(self):
        r = invoke("fv", 100.0, 0.10, 10.0)
        n = r.as_float()
        assert n > 1000

    def test_null_pmt(self):
        r = invoke("fv", None, 0.05, 12.0)
        assert r.is_null()

    def test_single_period_with_rate(self):
        r = invoke("fv", 100.0, 0.05, 1.0)
        assert_numeric(r, 100.0)  # FV = pmt * ((1+r)^1 - 1) / r = pmt * 1 = 100


# ══════════════════════════════════════════════════════════════════════
# pv: present value of annuity
# ══════════════════════════════════════════════════════════════════════

class TestPvExtended:
    def test_basic(self):
        r = invoke("pv", 100.0, 0.01, 12.0)
        n = r.as_float()
        assert 0 < n < 1200

    @pytest.mark.parametrize("pmt_val,rate,nper,expected", [
        (100.0, 0.0, 12.0, 1200.0),
        (100.0, 0.0, 1.0, 100.0),
        (0.0, 0.05, 12.0, 0.0),
    ])
    def test_zero_rate(self, pmt_val, rate, nper, expected):
        r = invoke("pv", pmt_val, rate, nper)
        assert_numeric(r, expected)

    def test_high_rate_lowers_pv(self):
        pv_low = invoke("pv", 100.0, 0.01, 12.0).as_float()
        pv_high = invoke("pv", 100.0, 0.10, 12.0).as_float()
        assert pv_high < pv_low

    def test_null_pmt(self):
        r = invoke("pv", None, 0.05, 12.0)
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# npv: net present value
# ══════════════════════════════════════════════════════════════════════

class TestNpvExtended:
    def test_basic(self):
        r = invoke("npv", 0.1, [-1000.0, 300.0, 400.0, 500.0])
        expected = -1000 + 300 / 1.1 + 400 / (1.1 ** 2) + 500 / (1.1 ** 3)
        assert_numeric(r, expected)

    def test_zero_rate(self):
        r = invoke("npv", 0.0, [-1000.0, 500.0, 500.0])
        assert_numeric(r, 0.0)

    def test_single_flow(self):
        r = invoke("npv", 0.1, [500.0])
        assert_numeric(r, 500.0)

    def test_all_positive(self):
        r = invoke("npv", 0.05, [100.0, 200.0, 300.0])
        n = r.as_float()
        assert n > 0

    def test_all_negative(self):
        r = invoke("npv", 0.05, [-100.0, -200.0, -300.0])
        n = r.as_float()
        assert n < 0

    def test_high_discount_rate(self):
        r = invoke("npv", 0.5, [-1000.0, 800.0, 800.0])
        n = r.as_float()
        # At 50%, future values are heavily discounted
        assert n < 800

    def test_null_rate(self):
        r = invoke("npv", None, [-1000.0, 500.0])
        assert r.is_null()

    def test_empty_cashflows(self):
        r = invoke("npv", 0.1, [])
        assert r.is_null()

    def test_typical_project(self):
        # Typical capital budgeting: invest 10k, get 3k/year for 5 years at 10%
        cashflows = [-10000.0, 3000.0, 3000.0, 3000.0, 3000.0, 3000.0]
        r = invoke("npv", 0.10, cashflows)
        n = r.as_float()
        assert n > 1000  # NPV should be positive (good project)


# ══════════════════════════════════════════════════════════════════════
# irr: internal rate of return
# ══════════════════════════════════════════════════════════════════════

class TestIrrExtended:
    def test_basic(self):
        r = invoke("irr", [-1000.0, 300.0, 400.0, 500.0])
        n = r.as_float()
        assert n is not None
        assert abs(n) < 1

    def test_even_cashflows(self):
        r = invoke("irr", [-1000.0, 500.0, 500.0, 500.0])
        n = r.as_float()
        assert n > 0

    def test_too_few_cashflows(self):
        r = invoke("irr", [100.0])
        assert r.is_null()

    def test_known_irr(self):
        # -100 followed by 110 => IRR = 10%
        r = invoke("irr", [-100.0, 110.0])
        assert_numeric(r, 0.10, tol=0.001)

    def test_break_even(self):
        # -100 followed by 100 => IRR = 0%
        r = invoke("irr", [-100.0, 100.0])
        assert_numeric(r, 0.0, tol=0.001)

    def test_high_return(self):
        # -100 followed by 200 => IRR = 100%
        r = invoke("irr", [-100.0, 200.0])
        assert_numeric(r, 1.0, tol=0.001)

    def test_null_input(self):
        r = invoke("irr", None)
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# rate: interest rate per period
# ══════════════════════════════════════════════════════════════════════

class TestRateExtended:
    def test_basic(self):
        r = invoke("rate", 10.0, -100.0, 1000.0, 0.0)
        n = r.as_float()
        assert n is not None
        assert math.isfinite(n)

    def test_known_rate(self):
        # If you pay 100/period for 10 periods on a 1000 loan,
        # the rate should be small and positive
        r = invoke("rate", 10.0, -100.0, 1000.0, 0.0)
        n = r.as_float()
        assert 0 < n < 0.1

    def test_null_nper(self):
        r = invoke("rate", None, -100.0, 1000.0, 0.0)
        assert r.is_null()

    def test_null_pmt(self):
        r = invoke("rate", 10.0, None, 1000.0, 0.0)
        assert r.is_null()

    def test_null_pv(self):
        r = invoke("rate", 10.0, -100.0, None, 0.0)
        assert r.is_null()

    def test_with_fv(self):
        # Solve for rate with FV target
        r = invoke("rate", 12.0, -100.0, 1000.0, 200.0)
        n = r.as_float()
        assert math.isfinite(n)


# ══════════════════════════════════════════════════════════════════════
# nper: number of periods
# ══════════════════════════════════════════════════════════════════════

class TestNperExtended:
    @pytest.mark.parametrize("rate,pmt,pv,expected", [
        (0.0, -100.0, 5000.0, 50.0),
        (0.0, -200.0, 10000.0, 50.0),
        (0.0, -500.0, 5000.0, 10.0),
    ])
    def test_zero_rate(self, rate, pmt, pv, expected):
        r = invoke("nper", rate, pmt, pv)
        assert_numeric(r, expected)

    def test_with_rate(self):
        r = invoke("nper", 0.01, -100.0, 5000.0)
        n = r.as_float()
        assert n > 0
        assert n < 100

    def test_higher_rate_more_periods(self):
        # Higher interest means more goes to interest, so more periods needed
        # Use a payment large enough to cover interest at both rates
        n_low = invoke("nper", 0.005, -200.0, 5000.0).as_float()
        n_high = invoke("nper", 0.02, -200.0, 5000.0).as_float()
        assert n_high > n_low

    def test_null_rate(self):
        r = invoke("nper", None, -100.0, 5000.0)
        assert r.is_null()

    def test_null_pmt(self):
        r = invoke("nper", 0.01, None, 5000.0)
        assert r.is_null()

    def test_null_pv(self):
        r = invoke("nper", 0.01, -100.0, None)
        assert r.is_null()

    def test_zero_pmt_zero_rate_returns_null(self):
        r = invoke("nper", 0.0, 0.0, 5000.0)
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# depreciation: straight-line
# ══════════════════════════════════════════════════════════════════════

class TestDepreciationExtended:
    @pytest.mark.parametrize("cost,salvage,life,expected", [
        (10000.0, 1000.0, 5.0, 1800.0),
        (10000.0, 0.0, 5.0, 2000.0),
        (50000.0, 5000.0, 10.0, 4500.0),
        (1000.0, 1000.0, 5.0, 0.0),
        (20000.0, 2000.0, 1.0, 18000.0),
    ])
    def test_various(self, cost, salvage, life, expected):
        r = invoke("depreciation", cost, salvage, life)
        assert_numeric(r, expected)

    def test_zero_life_returns_null(self):
        r = invoke("depreciation", 10000.0, 1000.0, 0.0)
        assert r.is_null()

    def test_null_cost(self):
        r = invoke("depreciation", None, 1000.0, 5.0)
        assert r.is_null()

    def test_null_salvage(self):
        r = invoke("depreciation", 10000.0, None, 5.0)
        assert r.is_null()

    def test_null_life(self):
        r = invoke("depreciation", 10000.0, 1000.0, None)
        assert r.is_null()

    def test_negative_life_returns_null(self):
        r = invoke("depreciation", 10000.0, 1000.0, -5.0)
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# variance / varianceSample
# ══════════════════════════════════════════════════════════════════════

class TestVarianceExtended:
    def test_population_known_dataset(self):
        # Known: [2,4,4,4,5,5,7,9] => mean=5, var=4.0
        r = invoke("variance", [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        assert_numeric(r, 4.0)

    def test_population_uniform(self):
        # All same values => variance 0
        r = invoke("variance", [5.0, 5.0, 5.0, 5.0])
        assert_numeric(r, 0.0)

    def test_population_two_values(self):
        # [0, 10] => mean=5, var=25
        r = invoke("variance", [0.0, 10.0])
        assert_numeric(r, 25.0)

    def test_empty_returns_null(self):
        r = invoke("variance", [])
        assert r.is_null()

    def test_single_item(self):
        r = invoke("variance", [5.0])
        assert_numeric(r, 0.0)

    def test_null_input(self):
        r = invoke("variance", None)
        assert r.is_null()


class TestVarianceSampleExtended:
    def test_known_dataset(self):
        # [2,4,4,4,5,5,7,9] => sample var = 32/7 ≈ 4.571
        r = invoke("varianceSample", [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        assert_numeric(r, 32.0 / 7.0, tol=0.01)

    def test_greater_than_population(self):
        data = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        pop = invoke("variance", data).as_float()
        samp = invoke("varianceSample", data).as_float()
        assert samp > pop

    def test_single_item_returns_null(self):
        r = invoke("varianceSample", [5.0])
        assert r.is_null()

    def test_empty_returns_null(self):
        r = invoke("varianceSample", [])
        assert r.is_null()

    def test_two_items(self):
        # [0, 10] => mean=5, sample var = 50
        r = invoke("varianceSample", [0.0, 10.0])
        assert_numeric(r, 50.0)


# ══════════════════════════════════════════════════════════════════════
# std / stdSample
# ══════════════════════════════════════════════════════════════════════

class TestStdExtended:
    def test_known_dataset(self):
        r = invoke("std", [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        assert_numeric(r, 2.0)

    def test_uniform(self):
        r = invoke("std", [5.0, 5.0, 5.0])
        assert_numeric(r, 0.0)

    def test_empty_returns_null(self):
        r = invoke("std", [])
        assert r.is_null()

    def test_is_sqrt_of_variance(self):
        data = [1.0, 3.0, 5.0, 7.0, 9.0]
        var_val = invoke("variance", data).as_float()
        std_val = invoke("std", data).as_float()
        assert abs(std_val - math.sqrt(var_val)) < 0.001


class TestStdSampleExtended:
    def test_known_dataset(self):
        r = invoke("stdSample", [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        n = r.as_float()
        assert n > 2.0  # sample std > population std

    def test_single_item_returns_null(self):
        r = invoke("stdSample", [5.0])
        assert r.is_null()

    def test_empty_returns_null(self):
        r = invoke("stdSample", [])
        assert r.is_null()

    def test_is_sqrt_of_sample_variance(self):
        data = [1.0, 3.0, 5.0, 7.0, 9.0]
        var_val = invoke("varianceSample", data).as_float()
        std_val = invoke("stdSample", data).as_float()
        assert abs(std_val - math.sqrt(var_val)) < 0.001


# ══════════════════════════════════════════════════════════════════════
# median
# ══════════════════════════════════════════════════════════════════════

class TestMedianExtended:
    @pytest.mark.parametrize("data,expected", [
        ([1.0, 3.0, 2.0], 2.0),
        ([1.0, 2.0, 3.0, 4.0], 2.5),
        ([5.0], 5.0),
        ([1.0, 2.0], 1.5),
        ([10.0, 20.0, 30.0, 40.0, 50.0], 30.0),
        ([1.0, 1.0, 1.0, 100.0], 1.0),
        ([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], 3.5),
    ])
    def test_various(self, data, expected):
        r = invoke("median", data)
        assert_numeric(r, expected)

    def test_empty_returns_null(self):
        r = invoke("median", [])
        assert r.is_null()

    def test_unsorted_input(self):
        r = invoke("median", [5.0, 1.0, 3.0])
        assert_numeric(r, 3.0)

    def test_negative_values(self):
        r = invoke("median", [-5.0, -1.0, -3.0])
        assert_numeric(r, -3.0)


# ══════════════════════════════════════════════════════════════════════
# mode
# ══════════════════════════════════════════════════════════════════════

class TestModeExtended:
    @pytest.mark.parametrize("data,expected", [
        ([1.0, 2.0, 2.0, 3.0], 2.0),
        ([1.0, 1.0, 2.0, 2.0, 3.0], 1.0),   # first mode wins on tie
        ([5.0, 5.0, 5.0], 5.0),
        ([1.0, 2.0, 3.0], 1.0),               # all unique, first wins
        ([3.0, 3.0, 3.0, 1.0, 1.0], 3.0),
    ])
    def test_various(self, data, expected):
        r = invoke("mode", data)
        assert_numeric(r, expected)

    def test_empty_returns_null(self):
        r = invoke("mode", [])
        assert r.is_null()

    def test_single_item(self):
        r = invoke("mode", [42.0])
        assert_numeric(r, 42.0)


# ══════════════════════════════════════════════════════════════════════
# percentile / quantile
# ══════════════════════════════════════════════════════════════════════

class TestPercentileExtended:
    @pytest.mark.parametrize("data,pct,expected", [
        ([1.0, 2.0, 3.0, 4.0, 5.0], 0.0, 1.0),
        ([1.0, 2.0, 3.0, 4.0, 5.0], 25.0, 2.0),
        ([1.0, 2.0, 3.0, 4.0, 5.0], 50.0, 3.0),
        ([1.0, 2.0, 3.0, 4.0, 5.0], 75.0, 4.0),
        ([1.0, 2.0, 3.0, 4.0, 5.0], 100.0, 5.0),
    ])
    def test_standard_percentiles(self, data, pct, expected):
        r = invoke("percentile", data, pct)
        assert_numeric(r, expected, tol=0.01)

    def test_single_item(self):
        r = invoke("percentile", [42.0], 50.0)
        assert_numeric(r, 42.0)

    def test_empty_returns_null(self):
        r = invoke("percentile", [], 50.0)
        assert r.is_null()

    def test_negative_pct_returns_null(self):
        r = invoke("percentile", [1.0, 2.0, 3.0], -10.0)
        assert r.is_null()

    def test_over_100_pct_returns_null(self):
        r = invoke("percentile", [1.0, 2.0, 3.0], 101.0)
        assert r.is_null()

    def test_interpolation(self):
        # With [1, 2, 3, 4, 5], p=30 => idx = 0.3*4 = 1.2; interp between 2 and 3
        r = invoke("percentile", [1.0, 2.0, 3.0, 4.0, 5.0], 30.0)
        n = r.as_float()
        assert 2.0 <= n <= 3.0


class TestQuantileExtended:
    @pytest.mark.parametrize("data,q,expected", [
        ([1.0, 2.0, 3.0, 4.0, 5.0], 0.0, 1.0),
        ([1.0, 2.0, 3.0, 4.0, 5.0], 0.25, 2.0),
        ([1.0, 2.0, 3.0, 4.0, 5.0], 0.50, 3.0),
        ([1.0, 2.0, 3.0, 4.0, 5.0], 0.75, 4.0),
        ([1.0, 2.0, 3.0, 4.0, 5.0], 1.0, 5.0),
    ])
    def test_standard_quantiles(self, data, q, expected):
        r = invoke("quantile", data, q)
        assert_numeric(r, expected, tol=0.01)

    def test_negative_q_returns_null(self):
        r = invoke("quantile", [1.0, 2.0, 3.0], -0.1)
        assert r.is_null()

    def test_over_1_q_returns_null(self):
        r = invoke("quantile", [1.0, 2.0, 3.0], 1.1)
        assert r.is_null()

    def test_empty_returns_null(self):
        r = invoke("quantile", [], 0.5)
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# covariance
# ══════════════════════════════════════════════════════════════════════

class TestCovarianceExtended:
    def test_perfect_positive(self):
        r = invoke("covariance", [1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
        n = r.as_float()
        assert n > 0

    def test_perfect_negative(self):
        r = invoke("covariance", [1.0, 2.0, 3.0], [3.0, 2.0, 1.0])
        n = r.as_float()
        assert n < 0

    def test_no_covariance(self):
        # Constant y => covariance = 0
        r = invoke("covariance", [1.0, 2.0, 3.0], [5.0, 5.0, 5.0])
        assert_numeric(r, 0.0)

    def test_known_value(self):
        # x=[1,2,3], y=[2,4,6] => means=(2,4), cov = ((1-2)(2-4)+(2-2)(4-4)+(3-2)(6-4))/3 = (2+0+2)/3 = 4/3
        r = invoke("covariance", [1.0, 2.0, 3.0], [2.0, 4.0, 6.0])
        assert_numeric(r, 4.0 / 3.0, tol=0.01)

    def test_empty_returns_null(self):
        r = invoke("covariance", [], [])
        assert r.is_null()

    def test_mismatched_lengths(self):
        # Should use min length
        r = invoke("covariance", [1.0, 2.0], [1.0, 2.0, 3.0])
        n = r.as_float()
        assert n is not None  # should not crash


# ══════════════════════════════════════════════════════════════════════
# correlation
# ══════════════════════════════════════════════════════════════════════

class TestCorrelationExtended:
    def test_perfect_positive(self):
        r = invoke("correlation", [1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
        assert_numeric(r, 1.0, tol=0.001)

    def test_perfect_negative(self):
        r = invoke("correlation", [1.0, 2.0, 3.0], [3.0, 2.0, 1.0])
        assert_numeric(r, -1.0, tol=0.001)

    def test_no_correlation(self):
        # Constant y => zero denominator => null
        r = invoke("correlation", [1.0, 2.0, 3.0], [5.0, 5.0, 5.0])
        assert r.is_null()

    def test_scaled_relationship(self):
        # y = 2x => perfect positive correlation
        r = invoke("correlation", [1.0, 2.0, 3.0, 4.0], [2.0, 4.0, 6.0, 8.0])
        assert_numeric(r, 1.0, tol=0.001)

    def test_between_minus_one_and_one(self):
        r = invoke("correlation", [1.0, 3.0, 5.0, 7.0], [2.0, 1.0, 6.0, 3.0])
        n = r.as_float()
        assert -1.0 <= n <= 1.0

    def test_empty_returns_null(self):
        r = invoke("correlation", [], [])
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# zscore
# ══════════════════════════════════════════════════════════════════════

class TestZscoreExtended:
    # z-score of a value against the mean and population stddev of an array.
    @pytest.mark.parametrize("value,array,expected", [
        (9.0, [1.0, 3.0, 5.0, 7.0, 9.0], 1.4142135623730951),
        (5.0, [1.0, 3.0, 5.0, 7.0, 9.0], 0.0),
        (1.0, [1.0, 3.0, 5.0, 7.0, 9.0], -1.4142135623730951),
    ])
    def test_various(self, value, array, expected):
        r = invoke("zscore", value, array)
        assert_numeric(r, expected)

    def test_zero_stddev_returns_null(self):
        r = invoke("zscore", 10.0, [5.0, 5.0, 5.0])
        assert r.is_null()

    def test_null_value(self):
        r = invoke("zscore", None, [1.0, 2.0, 3.0])
        assert r.is_null()

    def test_empty_array(self):
        r = invoke("zscore", 10.0, [])
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# interpolate: linear interpolation between (x1,y1) and (x2,y2) at x
# ══════════════════════════════════════════════════════════════════════

class TestInterpolateExtended:
    # Mapped as interpolation between (0, a) and (1, b) at x=t.
    @pytest.mark.parametrize("a,b,t,expected", [
        (0.0, 10.0, 0.0, 0.0),
        (0.0, 10.0, 0.5, 5.0),
        (0.0, 10.0, 1.0, 10.0),
        (0.0, 10.0, 0.25, 2.5),
        (0.0, 10.0, 0.75, 7.5),
        (10.0, 20.0, 0.5, 15.0),
        (-10.0, 10.0, 0.5, 0.0),
        (100.0, 200.0, 0.0, 100.0),
        (100.0, 200.0, 1.0, 200.0),
    ])
    def test_various(self, a, b, t, expected):
        r = invoke("interpolate", t, 0.0, a, 1.0, b)
        assert_numeric(r, expected)

    def test_extrapolation_above(self):
        r = invoke("interpolate", 2.0, 0.0, 0.0, 1.0, 10.0)
        assert_numeric(r, 20.0)

    def test_extrapolation_below(self):
        r = invoke("interpolate", -1.0, 0.0, 0.0, 1.0, 10.0)
        assert_numeric(r, -10.0)

    def test_null_x(self):
        r = invoke("interpolate", None, 0.0, 0.0, 1.0, 10.0)
        assert r.is_null()

    def test_null_y1(self):
        r = invoke("interpolate", 0.5, 0.0, None, 1.0, 10.0)
        assert r.is_null()

    def test_equal_x(self):
        # x2 == x1 returns y1 to avoid division by zero.
        r = invoke("interpolate", 0.5, 1.0, 7.0, 1.0, 9.0)
        assert_numeric(r, 7.0)


# ══════════════════════════════════════════════════════════════════════
# weightedAvg
# ══════════════════════════════════════════════════════════════════════

class TestWeightedAvgExtended:
    @pytest.mark.parametrize("values,weights,expected", [
        ([80.0, 90.0], [1.0, 3.0], 87.5),
        ([100.0], [1.0], 100.0),
        ([50.0, 50.0], [1.0, 1.0], 50.0),
        ([0.0, 100.0], [1.0, 1.0], 50.0),
        ([80.0, 90.0, 100.0], [1.0, 2.0, 1.0], 90.0),
        ([10.0, 20.0, 30.0], [3.0, 2.0, 1.0], 16.666666),
    ])
    def test_various(self, values, weights, expected):
        r = invoke("weightedAvg", values, weights)
        assert_numeric(r, expected, tol=0.01)

    def test_empty_returns_null(self):
        r = invoke("weightedAvg", [], [])
        assert r.is_null()

    def test_zero_weights_returns_null(self):
        r = invoke("weightedAvg", [10.0, 20.0], [0.0, 0.0])
        assert r.is_null()

    def test_single_value(self):
        r = invoke("weightedAvg", [42.0], [5.0])
        assert_numeric(r, 42.0)

    def test_unequal_length_uses_min(self):
        r = invoke("weightedAvg", [10.0, 20.0], [1.0])
        # Only first pair used
        assert_numeric(r, 10.0)

    def test_null_values(self):
        r = invoke("weightedAvg", None, [1.0, 2.0])
        assert r.is_null()

    def test_null_weights(self):
        r = invoke("weightedAvg", [10.0, 20.0], None)
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# Null handling across all financial verbs
# ══════════════════════════════════════════════════════════════════════

class TestFinancialNullHandling:
    @pytest.mark.parametrize("verb,args", [
        ("compound", [None, 0.05, 10]),
        ("compound", [1000.0, None, 10]),
        ("compound", [1000.0, 0.05, None]),
        ("discount", [None, 0.05, 10]),
        ("discount", [1000.0, None, 10]),
        ("discount", [1000.0, 0.05, None]),
        ("pmt", [None, 0.05, 12.0]),
        ("pmt", [1000.0, None, 12.0]),
        ("pmt", [1000.0, 0.05, None]),
        ("fv", [None, 0.05, 12.0]),
        ("fv", [100.0, None, 12.0]),
        ("fv", [100.0, 0.05, None]),
        ("pv", [None, 0.05, 12.0]),
        ("pv", [100.0, None, 12.0]),
        ("pv", [100.0, 0.05, None]),
        ("npv", [None, [-1000.0, 500.0]]),
        ("nper", [None, -100.0, 5000.0]),
        ("nper", [0.01, None, 5000.0]),
        ("nper", [0.01, -100.0, None]),
        ("depreciation", [None, 1000.0, 5.0]),
        ("depreciation", [10000.0, None, 5.0]),
        ("depreciation", [10000.0, 1000.0, None]),
        ("zscore", [None, 5.0, 2.0]),
        ("zscore", [10.0, None, 2.0]),
        ("zscore", [10.0, 5.0, None]),
        ("interpolate", [None, 10.0, 0.5]),
        ("interpolate", [0.0, None, 0.5]),
        ("interpolate", [0.0, 10.0, None]),
    ])
    def test_null_inputs_return_null(self, verb, args):
        r = invoke(verb, *args)
        assert r.is_null()


# ══════════════════════════════════════════════════════════════════════
# Edge cases: zero/boundary values
# ══════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_compound_zero_principal(self):
        r = invoke("compound", 0.0, 0.05, 10)
        assert_numeric(r, 0.0)

    def test_compound_zero_periods(self):
        r = invoke("compound", 1000.0, 0.05, 0)
        assert_numeric(r, 1000.0)

    def test_fv_zero_payment(self):
        r = invoke("fv", 0.0, 0.05, 12.0)
        assert_numeric(r, 0.0)

    def test_pv_zero_payment(self):
        r = invoke("pv", 0.0, 0.05, 12.0)
        assert_numeric(r, 0.0)

    def test_npv_single_positive(self):
        r = invoke("npv", 0.1, [1000.0])
        assert_numeric(r, 1000.0)

    def test_depreciation_cost_equals_salvage(self):
        r = invoke("depreciation", 5000.0, 5000.0, 5.0)
        assert_numeric(r, 0.0)

    def test_variance_single_value(self):
        r = invoke("variance", [42.0])
        assert_numeric(r, 0.0)

    def test_std_single_value(self):
        r = invoke("std", [42.0])
        assert_numeric(r, 0.0)

    def test_median_single(self):
        r = invoke("median", [42.0])
        assert_numeric(r, 42.0)

    def test_mode_single(self):
        r = invoke("mode", [42.0])
        assert_numeric(r, 42.0)

    def test_correlation_two_points(self):
        r = invoke("correlation", [1.0, 2.0], [3.0, 4.0])
        assert_numeric(r, 1.0, tol=0.001)

    def test_weighted_avg_single(self):
        r = invoke("weightedAvg", [50.0], [1.0])
        assert_numeric(r, 50.0)
