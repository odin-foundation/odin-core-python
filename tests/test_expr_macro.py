"""Tests for the %expr formula macro: precedence, associativity, unary handling,
functions, variables under an explicit bindings object, and compile errors."""

import pytest

from odin.transform.transform_parser import parse_transform
from odin.transform.engine import TransformEngine
from odin.transform.verb_registry import create_default_registry
from odin.transform.expr import ExprSyntaxError


HEADER = '{$}\nodin = "1.0.0"\ntransform = "1.0.0"\ndirection = "json->json"\n\n'


def eval_expr(formula, variables=None):
    """Compile and run a formula end-to-end, returning the native output value."""
    if variables is None:
        body = '{out}\nr = %expr "' + formula + '"'
        source = {}
    else:
        body = '{out}\nr = %expr "' + formula + '" @.v'
        source = {"v": variables}
    transform = parse_transform(HEADER + body)
    result = TransformEngine(create_default_registry()).execute(transform, source)
    out = result.output.as_object()["out"].as_object()
    r = out.get("r")
    if r is None or r.is_null():
        return None
    if r.is_integer():
        return r.as_int()
    if r.is_float() or r.is_number():
        return r.as_float()
    return r.as_string()


class TestPrecedenceAndAssociativity:
    def test_multiplication_before_addition(self):
        assert eval_expr("2 + 3 * 4") == 14

    def test_power_right_associative(self):
        assert eval_expr("2^3^2") == 512

    def test_unary_minus_binds_looser_than_power(self):
        assert eval_expr("-2^2") == -4

    def test_parens_negate_base(self):
        assert eval_expr("(-2)^2") == 4

    def test_nested_parens(self):
        assert eval_expr("((1 + 2) * 3)") == 9


class TestOperators:
    def test_division_yields_fraction(self):
        assert eval_expr("1 / 2") == 0.5

    def test_modulo(self):
        assert eval_expr("5 % 2") == 1

    def test_divide_by_zero_is_null(self):
        assert eval_expr("1 / 0") is None


class TestFunctions:
    def test_abs(self):
        assert eval_expr("abs(-7)") == 7

    def test_min_max_variadic(self):
        assert eval_expr("min(3, 5, 1) + max(3, 5, 1)") == 6

    def test_round_default_scale(self):
        assert eval_expr("round(3.7)") == 4

    def test_sqrt_with_bindings(self):
        assert eval_expr("sqrt(x^2 + y^2)", {"x": 3, "y": 4}) == 5


class TestVariables:
    def test_variables_resolve_under_bindings(self):
        assert eval_expr("a + b", {"a": 10, "b": 5}) == 15


class TestCompileErrors:
    def _compile(self, formula, with_bindings=False):
        body = '{out}\nr = %expr "' + formula + '"'
        if with_bindings:
            body += " @.v"
        parse_transform(HEADER + body)

    def test_unknown_function(self):
        with pytest.raises(ExprSyntaxError) as exc:
            self._compile("sin(x)", with_bindings=True)
        assert exc.value.code == "T015"

    def test_unbalanced_parens(self):
        with pytest.raises(ExprSyntaxError) as exc:
            self._compile("(1 + 2")
        assert exc.value.code == "T015"

    def test_trailing_operator(self):
        with pytest.raises(ExprSyntaxError) as exc:
            self._compile("2 +")
        assert exc.value.code == "T015"

    def test_variable_without_bindings(self):
        with pytest.raises(ExprSyntaxError) as exc:
            self._compile("a + b")
        assert exc.value.code == "T015"
