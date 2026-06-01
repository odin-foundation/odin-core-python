"""Schema-validation enforcement: invariant evaluation, currency and percent
bounds, override restrictiveness, intersection conflicts, tabular columns, and
default-value rules.
"""

import odin

H = '{$}\nodin = "1.0.0"\nschema = "1.0.0"\n\n'
_EMPTY = '{$}\nodin = "1.0.0"'


def run(schema_text: str, input_text: str):
    schema = odin.parse_schema(H + schema_text)
    doc = odin.parse(_EMPTY if input_text == "" else input_text)
    return odin.validate(doc, schema)


def codes_at(result, path):
    return [e.code for e in result.errors if e.path == path]


# ─────────────────────────────────────────────────────────────────────────────
# Invariant expression evaluation
# ─────────────────────────────────────────────────────────────────────────────


def test_invariant_three_term_additive_passes():
    r = run(
        "{order}\nsubtotal = #$\ntax = #$\nshipping = #$\ntotal = #$\n"
        ":invariant total = subtotal + tax + shipping",
        "{order}\nsubtotal = #$10.00\ntax = #$1.00\nshipping = #$2.00\ntotal = #$13.00",
    )
    assert r.valid is True


def test_invariant_three_term_additive_fails():
    r = run(
        "{order}\nsubtotal = #$\ntax = #$\nshipping = #$\ntotal = #$\n"
        ":invariant total = subtotal + tax + shipping",
        "{order}\nsubtotal = #$10.00\ntax = #$1.00\nshipping = #$2.00\ntotal = #$99.00",
    )
    assert r.valid is False
    assert "V008" in codes_at(r, "order")


def test_invariant_parentheses_and_precedence():
    schema = (
        "{discount}\nsubtotal = #$\npercentage = #\nfixed_amount = #$\ntotal = #$\n"
        ":invariant total = subtotal - (subtotal * percentage / 100) - fixed_amount"
    )
    assert run(
        schema,
        "{discount}\nsubtotal = #$100.00\npercentage = #10\nfixed_amount = #$5.00\ntotal = #$85.00",
    ).valid is True
    assert run(
        schema,
        "{discount}\nsubtotal = #$100.00\npercentage = #10\nfixed_amount = #$5.00\ntotal = #$80.00",
    ).valid is False


def test_invariant_logical_or():
    schema = (
        "{discount}\npercentage = #\nfixed_amount = #$\n"
        ":invariant percentage == 0 || fixed_amount == 0"
    )
    assert run(schema, "{discount}\npercentage = #0\nfixed_amount = #$5.00").valid is True
    assert run(schema, "{discount}\npercentage = #10\nfixed_amount = #$5.00").valid is False


def test_invariant_logical_and_and_negation():
    schema = "{f}\na = #\nb = #\n:invariant !(a > 10) && b < 5"
    assert run(schema, "{f}\na = #3\nb = #2").valid is True
    assert run(schema, "{f}\na = #20\nb = #2").valid is False


def test_invariant_modulo():
    schema = "{n}\nx = ##\n:invariant x % 2 == 0"
    assert run(schema, "{n}\nx = ##4").valid is True
    assert run(schema, "{n}\nx = ##5").valid is False


def test_invariant_null_operand_is_false():
    r = run(
        "{o}\ntotal = #$\nsubtotal = #$\ntax = ~#$\n:invariant total = subtotal + tax",
        "{o}\ntotal = #$10.00\nsubtotal = #$10.00\ntax = ~",
    )
    assert r.valid is False
    assert "V008" in codes_at(r, "o")


def test_invariant_absent_operand_is_inapplicable():
    r = run(
        "{o}\ntotal = #$\nsubtotal = #$\ntax = #$\n:invariant total = subtotal + tax",
        "{o}\ntotal = #$10.00",
    )
    assert r.valid is True


def test_invariant_malformed_is_v008():
    r = run("{o}\nx = #\n:invariant x + + ", "{o}\nx = #1")
    assert r.valid is False
    assert "V008" in codes_at(r, "o")


# ─────────────────────────────────────────────────────────────────────────────
# Currency decimal-place enforcement
# ─────────────────────────────────────────────────────────────────────────────


def test_currency_accepts_declared_places():
    assert run("{w}\nbtc = #$.8", "{w}\nbtc = #$1.00000000").valid is True


def test_currency_rejects_too_few_places():
    r = run("{w}\nbtc = #$.8", "{w}\nbtc = #$1.00")
    assert r.valid is False
    assert "V003" in codes_at(r, "w.btc")


def test_currency_defaults_to_two_places():
    assert run("{w}\nprice = #$", "{w}\nprice = #$9.99").valid is True
    assert run("{w}\nprice = #$", "{w}\nprice = #$9.999").valid is False


# ─────────────────────────────────────────────────────────────────────────────
# Percent bounds enforcement
# ─────────────────────────────────────────────────────────────────────────────


def test_percent_accepts_in_range():
    assert run("{r}\nrate = #%:(0..1)", "{r}\nrate = #%0.5").valid is True


def test_percent_rejects_out_of_range():
    r = run("{r}\nrate = #%:(0..1)", "{r}\nrate = #%1.5")
    assert r.valid is False
    assert "V003" in codes_at(r, "r.rate")


def test_percent_rejects_below_minimum():
    assert run("{r}\nrate = #%:(0.1..1)", "{r}\nrate = #%0.05").valid is False


# ─────────────────────────────────────────────────────────────────────────────
# Override restrictiveness
# ─────────────────────────────────────────────────────────────────────────────


def test_override_narrowing_bounds_accepted():
    assert run(
        "{@base}\namount = #$:(0..1000)\n\n{@narrow}\n= @base :override\namount = #$:(0..100)",
        "",
    ).valid is True


def test_override_widening_bounds_rejected():
    r = run(
        "{@base}\namount = #$:(0..100)\n\n{@wide}\n= @base :override\namount = #$:(0..1000)",
        "",
    )
    assert r.valid is False
    assert "V017" in codes_at(r, "@wide.amount")


def test_override_optional_to_required_but_not_reverse():
    assert run(
        "{@base}\nname =\n\n{@d}\n= @base :override\nname = !", ""
    ).valid is True
    r = run("{@base}\nname = !\n\n{@d}\n= @base :override\nname =", "")
    assert r.valid is False
    assert "V017" in codes_at(r, "@d.name")


def test_override_remove_nullable_but_not_add():
    assert run(
        "{@base}\nx = ~#\n\n{@d}\n= @base :override\nx = #", ""
    ).valid is True
    r = run("{@base}\nx = #\n\n{@d}\n= @base :override\nx = ~#", "")
    assert r.valid is False
    assert "V017" in codes_at(r, "@d.x")


def test_override_change_base_type_rejected():
    r = run("{@base}\nx = #\n\n{@d}\n= @base :override\nx =", "")
    assert r.valid is False
    assert "V017" in codes_at(r, "@d.x")


def test_override_rules_on_path_level_composition():
    r = run(
        "{@base}\namount = #$:(0..100)\n\n{order}\n= @base :override\namount = #$:(0..1000)",
        "",
    )
    assert r.valid is False
    assert "V017" in codes_at(r, "order.amount")


def test_override_does_not_flag_untouched_fields():
    assert run(
        "{@base}\na = #$:(0..100)\nb = !\n\n{@d}\n= @base :override\na = #$:(0..50)", ""
    ).valid is True


# ─────────────────────────────────────────────────────────────────────────────
# Intersection field conflicts
# ─────────────────────────────────────────────────────────────────────────────


def test_intersection_conflict_rejected():
    r = run("{@a}\nx = !\n\n{@b}\nx = !##\n\n{cust}\n= @a & @b", "{cust}\nx = ##5")
    assert r.valid is False
    assert "V017" in codes_at(r, "@cust.x")


def test_intersection_disjoint_or_identical_accepted():
    assert run(
        "{@a}\nx = !\nname = !\n\n{@b}\nx = !\nage = !##\n\n{cust}\n= @a & @b",
        '{cust}\nx = "hi"\nname = "n"\nage = ##5',
    ).valid is True


def test_intersection_three_way_conflict():
    r = run(
        "{@a}\nx = !\n\n{@b}\ny = !\n\n{@c}\nx = !##\n\n{cust}\n= @a & @b & @c",
        '{cust}\nx = "hi"\ny = "z"',
    )
    assert r.valid is False
    assert "V017" in codes_at(r, "@cust.x")


# ─────────────────────────────────────────────────────────────────────────────
# Tabular column rules
# ─────────────────────────────────────────────────────────────────────────────


def test_tabular_primitive_columns_accepted():
    assert run(
        "{contacts[] : name, email}\nname = !\nemail = !",
        '{contacts[0]}\nname = "a"\nemail = "b"',
    ).valid is True


def test_tabular_typeref_column_rejected():
    r = run(
        "{@addr}\nline1 = !\n\n{customers[] : name, address}\nname = !\naddress = @addr",
        '{customers[0]}\nname = "a"',
    )
    assert r.valid is False
    assert "V017" in codes_at(r, "customers[].address")


def test_tabular_primitive_columns_with_integer():
    assert run(
        "{rows[] : id, label}\nid = !##\nlabel = !",
        '{rows[0]}\nid = ##1\nlabel = "x"',
    ).valid is True


# ─────────────────────────────────────────────────────────────────────────────
# Default value rules
# ─────────────────────────────────────────────────────────────────────────────


def test_default_within_constraints_accepted():
    assert run("{root}\npriority = ##:(1..5) ##3", "").valid is True


def test_default_on_required_rejected():
    r = run('{root}\nstatus = !("a", "b") "a"', '{root}\nstatus = "a"')
    assert r.valid is False
    assert "V017" in codes_at(r, "root.status")


def test_default_violates_bounds_rejected():
    r = run("{root}\npriority = ##:(1..5) ##9", "")
    assert r.valid is False
    assert "V017" in codes_at(r, "root.priority")


def test_default_outside_enum_rejected():
    r = run('{root}\nstatus = ("a", "b") "c"', "")
    assert r.valid is False
    assert "V017" in codes_at(r, "root.status")


def test_default_matches_enum_accepted():
    assert run('{root}\nstatus = ("a", "b") "a"', "").valid is True
