"""Invariant expression evaluation.

Recursive-descent evaluator over the invariant grammar:
    expression     = logic_or
    logic_or       = logic_and , { "||" , logic_and }
    logic_and      = equality , { "&&" , equality }
    equality       = comparison , { ( "==" | "!=" | "=" ) , comparison }
    comparison     = additive , { ( ">" | "<" | ">=" | "<=" ) , additive }
    additive       = multiplicative , { ( "+" | "-" ) , multiplicative }
    multiplicative = unary , { ( "*" | "/" | "%" ) , unary }
    unary          = [ "!" ] , primary
    primary        = path | number | string | "(" , expression , ")"
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable, List, Optional, Union

from odin.types.values import (
    OdinValue,
    OdinNull,
    OdinBoolean,
    OdinString,
    OdinNumber,
    OdinInteger,
    OdinCurrency,
    OdinPercent,
    OdinDate,
    OdinTimestamp,
)

Operand = Union[float, int, str, bool, None]
FieldResolver = Callable[[str], Optional[OdinValue]]

_MULTI_CHAR_OPS = ["==", "!=", ">=", "<=", "&&", "||"]
_SINGLE_CHAR_OPS = set("+-*/%><=!")
_BOOLEAN_LITERALS = {"true": True, "false": False}
_EPSILON = 1e-9
_NAN = float("nan")


@dataclass
class InvariantResult:
    """Outcome of evaluating an invariant expression."""

    value: Optional[bool]
    """True/False when fully evaluable; None when an operand field is absent."""

    null_operand: bool
    """True if any referenced field is present but null."""


@dataclass
class _Token:
    kind: str  # op | number | string | ident | lparen | rparen
    text: str


def _tokenize(expr: str) -> List[_Token]:
    """Tokenize an invariant expression. Raises on unrecognized input."""
    tokens: List[_Token] = []
    i = 0
    n = len(expr)
    while i < n:
        c = expr[i]
        if c in " \t":
            i += 1
            continue
        if c == "(":
            tokens.append(_Token("lparen", "("))
            i += 1
            continue
        if c == ")":
            tokens.append(_Token("rparen", ")"))
            i += 1
            continue
        if c == '"' or c == "'":
            quote = c
            j = i + 1
            text = ""
            while j < n and expr[j] != quote:
                text += expr[j]
                j += 1
            if j >= n:
                raise ValueError("Unterminated string literal")
            tokens.append(_Token("string", text))
            i = j + 1
            continue
        two = expr[i:i + 2]
        if two in _MULTI_CHAR_OPS:
            tokens.append(_Token("op", two))
            i += 2
            continue
        if c in _SINGLE_CHAR_OPS:
            tokens.append(_Token("op", c))
            i += 1
            continue
        if c.isdigit():
            j = i
            while j < n and (expr[j].isdigit() or expr[j] == "."):
                j += 1
            tokens.append(_Token("number", expr[i:j]))
            i = j
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (expr[j].isalnum() or expr[j] in "_."):
                j += 1
            tokens.append(_Token("ident", expr[i:j]))
            i = j
            continue
        raise ValueError(f"Unexpected character '{c}' in invariant expression")
    return tokens


def evaluate_invariant(expr: str, resolve: FieldResolver) -> InvariantResult:
    """Parse and evaluate an invariant expression against document field values."""
    tokens = _tokenize(expr)
    state = {"pos": 0, "absent": False, "null": False}

    def peek() -> Optional[_Token]:
        return tokens[state["pos"]] if state["pos"] < len(tokens) else None

    def nxt() -> Optional[_Token]:
        tok = tokens[state["pos"]] if state["pos"] < len(tokens) else None
        state["pos"] += 1
        return tok

    def parse_expression() -> Operand:
        return parse_logic_or()

    def parse_logic_or() -> Operand:
        left = parse_logic_and()
        while peek() is not None and peek().text == "||":
            nxt()
            right = parse_logic_and()
            left = _to_bool(left) or _to_bool(right)
        return left

    def parse_logic_and() -> Operand:
        left = parse_equality()
        while peek() is not None and peek().text == "&&":
            nxt()
            right = parse_equality()
            left = _to_bool(left) and _to_bool(right)
        return left

    def parse_equality() -> Operand:
        left = parse_comparison()
        while peek() is not None and peek().text in ("==", "!=", "="):
            op = nxt().text
            right = parse_comparison()
            eq = _loose_equals(left, right)
            left = (not eq) if op == "!=" else eq
        return left

    def parse_comparison() -> Operand:
        left = parse_additive()
        while peek() is not None and peek().text in (">", "<", ">=", "<="):
            op = nxt().text
            right = parse_additive()
            left = _compare(left, op, right)
        return left

    def parse_additive() -> Operand:
        left = parse_multiplicative()
        while peek() is not None and peek().text in ("+", "-"):
            op = nxt().text
            right = parse_multiplicative()
            ln = _to_num(left)
            rn = _to_num(right)
            if ln is None or rn is None:
                left = _NAN
            else:
                left = ln + rn if op == "+" else ln - rn
        return left

    def parse_multiplicative() -> Operand:
        left = parse_unary()
        while peek() is not None and peek().text in ("*", "/", "%"):
            op = nxt().text
            right = parse_unary()
            ln = _to_num(left)
            rn = _to_num(right)
            if ln is None or rn is None:
                left = _NAN
            elif op == "*":
                left = ln * rn
            elif op == "/":
                left = _NAN if rn == 0 else ln / rn
            else:
                left = _NAN if rn == 0 else ln % rn
        return left

    def parse_unary() -> Operand:
        if peek() is not None and peek().text == "!":
            nxt()
            operand = parse_unary()
            return not _to_bool(operand)
        return parse_primary()

    def parse_primary() -> Operand:
        tok = nxt()
        if tok is None:
            raise ValueError("Unexpected end of invariant expression")

        if tok.kind == "lparen":
            inner = parse_expression()
            close = nxt()
            if close is None or close.kind != "rparen":
                raise ValueError("Expected closing parenthesis")
            return inner
        if tok.kind == "number":
            try:
                return float(tok.text)
            except ValueError:
                raise ValueError(f"Invalid number '{tok.text}'")
        if tok.kind == "string":
            return tok.text
        if tok.kind == "ident":
            if tok.text in _BOOLEAN_LITERALS:
                return _BOOLEAN_LITERALS[tok.text]
            value = resolve(tok.text)
            if value is None:
                state["absent"] = True
                return _NAN
            if isinstance(value, OdinNull):
                state["null"] = True
                return None
            return _operand_from_value(value)
        raise ValueError(f"Unexpected token '{tok.text}'")

    final = parse_expression()
    if peek() is not None:
        raise ValueError("Unexpected trailing tokens in invariant expression")

    if state["null"]:
        result: Optional[bool] = False
    elif state["absent"]:
        result = None
    else:
        result = _to_bool(final)

    return InvariantResult(value=result, null_operand=state["null"])


def _operand_from_value(value: OdinValue) -> Operand:
    """Extract a comparable operand from an OdinValue."""
    if isinstance(value, (OdinNumber, OdinInteger, OdinPercent)):
        return value.value
    if isinstance(value, OdinCurrency):
        return float(value.value)
    if isinstance(value, OdinString):
        return value.value
    if isinstance(value, OdinBoolean):
        return value.value
    if isinstance(value, (OdinDate, OdinTimestamp)):
        v = value.value
        if isinstance(v, (date, datetime)):
            return v.toordinal() if not isinstance(v, datetime) else v.timestamp()
    return _NAN


def _is_nan(v: Operand) -> bool:
    return isinstance(v, float) and v != v


def _to_num(v: Operand) -> Optional[float]:
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return None if _is_nan(v) else float(v)
    return None


def _to_bool(v: Operand) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return not _is_nan(v) and v != 0
    if isinstance(v, str):
        return len(v) > 0
    return False


def _loose_equals(a: Operand, b: Operand) -> bool:
    if isinstance(a, bool) and isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and not isinstance(a, bool) and \
       isinstance(b, (int, float)) and not isinstance(b, bool):
        return abs(a - b) < _EPSILON
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    an = _to_num(a)
    bn = _to_num(b)
    if an is not None and bn is not None:
        return abs(an - bn) < _EPSILON
    return a == b


def _compare(a: Operand, op: str, b: Operand) -> bool:
    an = _to_num(a)
    bn = _to_num(b)
    if an is not None and bn is not None:
        if op == ">":
            return an > bn
        if op == "<":
            return an < bn
        if op == ">=":
            return an >= bn
        if op == "<=":
            return an <= bn
    if isinstance(a, str) and isinstance(b, str):
        if op == ">":
            return a > b
        if op == "<":
            return a < b
        if op == ">=":
            return a >= b
        if op == "<=":
            return a <= b
    return False
