"""%expr formula macro: compile an infix arithmetic string into a verb tree.

This is a parse-time macro. The formula is compiled into a tree of existing
transform verbs (add, subtract, multiply, divide, mod, negate, pow, and a
whitelist of numeric functions); there is no runtime evaluator. Variables
resolve under an explicit bindings object passed as the second argument:
``%expr "a + b" @.vars`` reads ``a`` as ``@.vars.a``.

Precedence, high to low:
  1. parentheses, function call
  2. ^ power (right-associative)
  3. unary - / +  (binds looser than ^, so -2^2 = -(2^2); (-2)^2 = 4)
  4. * / %  (left-associative)
  5. + -    (left-associative)
"""

from __future__ import annotations

import re
from typing import List, Optional

from odin.transform.types import LiteralArg, ReferenceArg, VerbArg, VerbCall, VerbCallArg
from odin.types.values import OdinInteger, OdinNumber


class ExprSyntaxError(Exception):
    """Raised when a %expr formula cannot be compiled. Carries the T015 code."""

    code = "T015"

    def __init__(self, message: str) -> None:
        super().__init__(f"Invalid %expr formula: {message}")


_BINARY_OP = {"+": "add", "-": "subtract", "*": "multiply", "/": "divide", "%": "mod"}

# function name -> (verb, min_args, max_args); max None means unbounded
_FUNCTIONS = {
    "abs": ("abs", 1, 1),
    "floor": ("floor", 1, 1),
    "ceil": ("ceil", 1, 1),
    "trunc": ("trunc", 1, 1),
    "sqrt": ("sqrt", 1, 1),
    "round": ("round", 1, 2),
    "pow": ("pow", 2, 2),
    "min": ("minOf", 1, None),
    "max": ("maxOf", 1, None),
}

_NUM_RE = re.compile(r"[0-9]")
_IDENT_START_RE = re.compile(r"[A-Za-z_]")
_IDENT_RE = re.compile(r"[A-Za-z0-9_.]")


class _Token:
    __slots__ = ("kind", "value", "is_float")

    def __init__(self, kind: str, value: str, is_float: bool = False) -> None:
        self.kind = kind
        self.value = value
        self.is_float = is_float


def _tokenize(src: str) -> List[_Token]:
    tokens: List[_Token] = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c.isspace():
            i += 1
            continue
        if c.isdigit():
            j = i
            is_float = False
            while j < n and src[j].isdigit():
                j += 1
            if j < n and src[j] == ".":
                is_float = True
                j += 1
                while j < n and src[j].isdigit():
                    j += 1
            if j < n and src[j] in "eE":
                is_float = True
                j += 1
                if j < n and src[j] in "+-":
                    j += 1
                while j < n and src[j].isdigit():
                    j += 1
            tokens.append(_Token("num", src[i:j], is_float))
            i = j
            continue
        if _IDENT_START_RE.match(c):
            j = i
            while j < n and _IDENT_RE.match(src[j]):
                j += 1
            tokens.append(_Token("ident", src[i:j]))
            i = j
            continue
        if c == "(":
            tokens.append(_Token("lparen", c))
            i += 1
            continue
        if c == ")":
            tokens.append(_Token("rparen", c))
            i += 1
            continue
        if c == ",":
            tokens.append(_Token("comma", c))
            i += 1
            continue
        if c in "+-*/%^":
            tokens.append(_Token("op", c))
            i += 1
            continue
        raise ExprSyntaxError(f"unexpected character '{c}'")
    return tokens


def _literal(text: str, is_float: bool) -> VerbArg:
    value = OdinNumber(value=float(text)) if is_float else OdinInteger(value=int(text))
    return LiteralArg(value=value)


def _verb_node(verb: str, args: List[VerbArg]) -> VerbArg:
    return VerbCallArg(call=VerbCall(verb=verb, is_custom=False, args=args))


class _Parser:
    def __init__(self, tokens: List[_Token], binding_path: Optional[str]) -> None:
        self._tokens = tokens
        self._binding = binding_path
        self._pos = 0

    def _peek(self) -> Optional[_Token]:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else None

    def _next(self) -> Optional[_Token]:
        t = self._peek()
        if t is not None:
            self._pos += 1
        return t

    def parse(self) -> VerbArg:
        if not self._tokens:
            raise ExprSyntaxError("empty formula")
        expr = self._additive()
        if self._pos < len(self._tokens):
            raise ExprSyntaxError(f"unexpected token '{self._peek().value}'")
        return expr

    def _additive(self) -> VerbArg:
        left = self._multiplicative()
        while True:
            t = self._peek()
            if t and t.kind == "op" and t.value in ("+", "-"):
                op = self._next().value
                right = self._multiplicative()
                left = _verb_node(_BINARY_OP[op], [left, right])
            else:
                return left

    def _multiplicative(self) -> VerbArg:
        left = self._unary()
        while True:
            t = self._peek()
            if t and t.kind == "op" and t.value in ("*", "/", "%"):
                op = self._next().value
                right = self._unary()
                left = _verb_node(_BINARY_OP[op], [left, right])
            else:
                return left

    def _unary(self) -> VerbArg:
        t = self._peek()
        if t and t.kind == "op" and t.value in ("-", "+"):
            self._next()
            operand = self._unary()
            return _verb_node("negate", [operand]) if t.value == "-" else operand
        return self._power()

    def _power(self) -> VerbArg:
        base = self._primary()
        t = self._peek()
        if t and t.kind == "op" and t.value == "^":
            self._next()
            exponent = self._unary()
            return _verb_node("pow", [base, exponent])
        return base

    def _primary(self) -> VerbArg:
        t = self._next()
        if t is None:
            raise ExprSyntaxError("unexpected end of formula")
        if t.kind == "num":
            return _literal(t.value, t.is_float)
        if t.kind == "lparen":
            inner = self._additive()
            close = self._next()
            if close is None or close.kind != "rparen":
                raise ExprSyntaxError("missing closing parenthesis")
            return inner
        if t.kind == "ident":
            nxt = self._peek()
            if nxt and nxt.kind == "lparen":
                return self._call(t.value)
            if self._binding is None:
                raise ExprSyntaxError(
                    f"variable '{t.value}' requires a bindings object, e.g. %expr \"...\" @.vars"
                )
            return ReferenceArg(path=self._binding + "." + t.value)
        raise ExprSyntaxError(f"unexpected token '{t.value}'")

    def _call(self, name: str) -> VerbArg:
        fn = _FUNCTIONS.get(name)
        if fn is None:
            raise ExprSyntaxError(f"unknown function '{name}'")
        verb, lo, hi = fn
        self._next()  # consume '('
        args: List[VerbArg] = []
        if self._peek() is None or self._peek().kind != "rparen":
            args.append(self._additive())
            while self._peek() and self._peek().kind == "comma":
                self._next()
                args.append(self._additive())
        close = self._next()
        if close is None or close.kind != "rparen":
            raise ExprSyntaxError(f"missing ) after {name}(")
        if len(args) < lo or (hi is not None and len(args) > hi):
            bounds = str(lo) if lo == hi else f"{lo}-{hi if hi is not None else ''}"
            raise ExprSyntaxError(f"{name}() takes {bounds} arguments, got {len(args)}")
        if name == "round" and len(args) == 1:
            args.append(LiteralArg(value=OdinInteger(value=0)))
        return _verb_node(verb, args)


def compile_expr(formula: str, binding_path: Optional[str] = None) -> VerbArg:
    """Compile an infix arithmetic formula into a verb-tree argument node."""
    return _Parser(_tokenize(formula), binding_path).parse()
