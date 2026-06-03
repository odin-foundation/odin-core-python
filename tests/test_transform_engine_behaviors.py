"""Engine behaviors that span verbs: multi-sink accumulators, lazy control-flow
branch evaluation, and month/year date clamping."""

from odin.transform.transform_parser import parse_transform
from odin.transform.engine import TransformEngine
from odin.transform.verb_registry import create_default_registry


HEADER = '{$}\nodin = "1.0.0"\ntransform = "1.0.0"\ndirection = "json->json"\n\n'


def execute(body, source=None):
    transform = parse_transform(HEADER + body)
    return TransformEngine(create_default_registry()).execute(transform, source or {})


def out_field(body, field, source=None):
    """Read a field from the {out} segment, returning a native value."""
    result = execute(body, source)
    out = result.output.as_object()["out"].as_object()
    r = out.get(field)
    if r is None or r.is_null():
        return None
    if r.is_bool():
        return r.as_bool()
    if r.is_integer():
        return r.as_int()
    if r.is_float() or r.is_number():
        return r.as_float()
    return r.as_string()


# ── Multi-sink: several _-prefixed sinks advance in one loop pass ─────

class TestMultiSink:
    def test_total_and_count_both_advance(self):
        body = (
            '{$accumulator}\n'
            'total = ##0\ntotal._persist = true\n'
            'count = ##0\ncount._persist = true\n\n'
            '{lines[]}\n_loop = "@items"\namount = @.amount\n'
            '_ = %accumulate total @.amount\n'
            '_count = %accumulate count ##1\n\n'
            '{out}\n'
            'total = "@$accumulator.total"\n'
            'count = "@$accumulator.count"'
        )
        source = {"items": [{"amount": 10}, {"amount": 20}, {"amount": 30}]}
        assert out_field(body, "total", source) == 60
        assert out_field(body, "count", source) == 3

    def test_set_into_two_sinks(self):
        body = (
            '{$accumulator}\n'
            'lastVal = ##0\nlastVal._persist = true\n'
            'lastLabel = ""\nlastLabel._persist = true\n\n'
            '{lines[]}\n_loop = "@items"\nval = @.v\n'
            '_ = %set lastVal @.v\n'
            '_label = %set lastLabel @.label\n\n'
            '{out}\n'
            'finalVal = "@$accumulator.lastVal"\n'
            'finalLabel = "@$accumulator.lastLabel"'
        )
        source = {"items": [{"v": 10, "label": "a"}, {"v": 20, "label": "b"}, {"v": 30, "label": "c"}]}
        assert out_field(body, "finalVal", source) == 30
        assert out_field(body, "finalLabel", source) == "c"


# ── Lazy control-flow: only the selected branch runs ─────────────────

class TestLazyControlFlow:
    def test_and_short_circuits_false_left(self):
        body = (
            '{$accumulator}\nx = ##0\nx._persist = true\n\n'
            '{_s}\n_ = %and ?false %accumulate x ##1\n\n'
            '{out}\nx = "@$accumulator.x"'
        )
        assert out_field(body, "x") == 0

    def test_or_short_circuits_true_left(self):
        body = (
            '{$accumulator}\nx = ##0\nx._persist = true\n\n'
            '{_s}\n_ = %or ?true %accumulate x ##1\n\n'
            '{out}\nx = "@$accumulator.x"'
        )
        assert out_field(body, "x") == 0

    def test_coalesce_stops_at_first_non_null(self):
        body = (
            '{$accumulator}\nx = ##0\nx._persist = true\n\n'
            '{_s}\n_ = %coalesce "first" %accumulate x ##1\n\n'
            '{out}\nx = "@$accumulator.x"'
        )
        assert out_field(body, "x") == 0

    def test_ifelse_runs_only_selected_branch(self):
        body = (
            '{$accumulator}\n'
            'chosen = ##0\nchosen._persist = true\n'
            'skipped = ##0\nskipped._persist = true\n\n'
            '{_s}\n_ = %ifElse ?true %accumulate chosen ##1 %accumulate skipped ##1\n\n'
            '{out}\n'
            'chosen = "@$accumulator.chosen"\n'
            'skipped = "@$accumulator.skipped"'
        )
        assert out_field(body, "chosen") == 1
        assert out_field(body, "skipped") == 0

    def test_ifelse_selects_value(self):
        assert out_field('{out}\nr = %ifElse %gt ##5 ##3 "big" "small"', "r") == "big"
        assert out_field('{out}\nr = %ifElse %gt ##1 ##3 "big" "small"', "r") == "small"

    def test_ifnull_and_ifempty_fall_back(self):
        assert out_field('{out}\nr = %ifNull ~ "fallback"', "r") == "fallback"
        assert out_field('{out}\nr = %ifEmpty "" "fallback"', "r") == "fallback"
        assert out_field('{out}\nr = %ifNull "present" "fallback"', "r") == "present"

    def test_coalesce_returns_first_present(self):
        assert out_field('{out}\nr = %coalesce ~ ~ "third"', "r") == "third"

    def test_and_or_compute_booleans(self):
        assert out_field('{out}\nr = %and ?true ?false', "r") is False
        assert out_field('{out}\nr = %or ?false ?true', "r") is True

    def test_cond_and_switch_select(self):
        assert out_field('{out}\nr = %cond %eq ##2 ##1 "one" %eq ##2 ##2 "two" "default"', "r") == "two"
        assert out_field('{out}\nr = %cond %eq ##9 ##1 "one" %eq ##9 ##2 "two" "default"', "r") == "default"
        assert out_field('{out}\nr = %switch "b" "a" ##1 "b" ##2 ##99', "r") == 2
        assert out_field('{out}\nr = %switch "z" "a" ##1 "b" ##2 ##99', "r") == 99


# ── Date clamping to the target month end ────────────────────────────

class TestDateClamping:
    def _invoke(self, verb, *raw):
        from odin.transform.dyn_value import DynValue
        args = [
            DynValue.of_string(a) if isinstance(a, str) else DynValue.of_integer(a)
            for a in raw
        ]
        return TransformEngine(create_default_registry()).invoke_verb(verb, args)

    def test_add_months_clamps_to_leap_february(self):
        assert self._invoke("addMonths", "2024-01-31", 1).as_string() == "2024-02-29"

    def test_add_months_clamps_to_non_leap_february(self):
        assert self._invoke("addMonths", "2023-01-31", 1).as_string() == "2023-02-28"

    def test_add_years_leap_day_clamps(self):
        assert self._invoke("addYears", "2024-02-29", 1).as_string() == "2025-02-28"

    def test_add_years_leap_day_to_leap_year(self):
        assert self._invoke("addYears", "2024-02-29", 4).as_string() == "2028-02-29"
