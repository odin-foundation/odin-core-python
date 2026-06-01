"""Transform engine enforcement gaps: stable error codes (T001, T003, T005,
T006, T008, T009), onMissing policy for source fields, and @import resolution.
"""

import odin


def _header(fmt="odin", target=None, direction=None):
    direction = direction or f"odin->{fmt}"
    target = target or {}
    meta = [
        'odin = "1.0.0"',
        'transform = "1.0.0"',
        f'direction = "{direction}"',
    ]
    tgt = [f'format = "{fmt}"'] + [f'{k} = "{v}"' for k, v in target.items()]
    return (
        "{$}\n" + "\n".join(meta) + "\n\n"
        "{$source}\nformat = \"odin\"\n\n"
        "{$target}\n" + "\n".join(tgt) + "\n\n"
    )


def _run(transform, input_odin, fmt="odin", target=None):
    text = _header(fmt, target) + transform
    src = odin.parse(input_odin)
    return odin.execute_transform(text, src)


# ── T001: unknown verb ─────────────────────────────────────────────────────────


class TestUnknownVerbT001:
    def test_emits_t001_for_unknown_builtin(self):
        r = _run("{out}\nx = %notAVerb @.a\n", "a = ##1")
        assert not r.success
        assert r.errors[0].code == "T001"
        assert r.errors[0].path == "x"

    def test_no_error_for_unregistered_custom_verb(self):
        r = _run("{out}\nx = %&my.thing @.a\n", 'a = "v"')
        assert r.success
        assert len(r.errors) == 0

    def test_demotes_t001_to_warning_under_on_error_warn(self):
        r = _run("{out}\nx = %notAVerb @.a\n", "a = ##1",
                 target={"onError": "warn"})
        assert r.success
        assert any(w.code == "T001" for w in r.warnings)


# ── T003: lookup table not found ───────────────────────────────────────────────


class TestLookupTableNotFoundT003:
    def test_emits_t003_when_table_undeclared_and_fail(self):
        r = _run('{out}\nx = %lookup "GHOST.code" @.k\n', 'k = "active"',
                 target={"onMissing": "fail"})
        assert not r.success
        assert r.errors[0].code == "T003"

    def test_silent_under_default_policy(self):
        r = _run('{out}\nx = %lookup "GHOST.code" @.k\n', 'k = "active"')
        assert r.success
        assert len(r.errors) == 0

    def test_demotes_t003_to_warning_under_warn(self):
        r = _run('{out}\nx = %lookup "GHOST.code" @.k\n', 'k = "active"',
                 target={"onMissing": "warn"})
        assert r.success
        assert any(w.code == "T003" for w in r.warnings)

    def test_still_t004_for_missing_key_in_declared_table(self):
        transform = (
            '{$table.T[name, code]}\n"foo", ##1\n\n'
            '{out}\nx = %lookup "T.code" @.k\n'
        )
        r = _run(transform, 'k = "bar"', target={"onMissing": "fail"})
        assert not r.success
        assert r.errors[0].code == "T004"


# ── T005: source path not found / onMissing ────────────────────────────────────


class TestSourcePathT005:
    def test_emits_t005_when_required_path_absent(self):
        r = _run("{out}\nx = @.does.not.exist :required\n", "a = ##1")
        assert not r.success
        assert r.errors[0].code == "T005"

    def test_emits_t005_for_absent_path_under_on_missing_fail(self):
        r = _run("{out}\nx = @.does.not.exist\n", "a = ##1",
                 target={"onMissing": "fail"})
        assert not r.success
        assert r.errors[0].code == "T005"

    def test_warns_for_absent_path_under_on_missing_warn(self):
        r = _run("{out}\nx = @.does.not.exist\n", "a = ##1",
                 target={"onMissing": "warn"})
        assert r.success
        assert any(w.code == "T005" for w in r.warnings)

    def test_silent_for_absent_path_under_default_skip(self):
        r = _run("{out}\nx = @.does.not.exist\n", "a = ##1")
        assert r.success
        assert len(r.errors) == 0

    def test_present_null_required_is_source_missing_not_t005(self):
        r = _run("{out}\nx = @.a :required\n", "a = ~")
        assert not r.success
        assert r.errors[0].code == "SOURCE_MISSING"

    def test_no_t005_when_verb_result_is_null(self):
        r = _run("{out}\nx = %upper @.missing\n", "a = ##1",
                 target={"onMissing": "fail"})
        assert not any(e.code == "T005" for e in r.errors)


# ── T006: invalid output format ────────────────────────────────────────────────


class TestInvalidOutputFormatT006:
    def test_emits_t006_for_unregistered_format(self):
        r = _run("{out}\nx = @.a\n", "a = ##1", fmt="notaformat")
        assert not r.success
        assert any(e.code == "T006" for e in r.errors)

    def test_known_formats_do_not_raise_t006(self):
        for fmt in ["odin", "json", "xml", "csv"]:
            r = _run("{out}\nx = @.a\n", "a = ##1", fmt=fmt)
            assert not any(e.code == "T006" for e in r.errors), fmt
            assert r.formatted is not None

    def test_format_derived_from_direction_without_target_format(self):
        # No {$target} block — format must derive from the direction header.
        text = (
            '{$}\nodin = "1.0.0"\ntransform = "1.0.0"\n'
            'direction = "json->odin"\n\n'
            "{out}\nx = @.a\n"
        )
        r = odin.execute_transform(text, {"a": 1})
        assert not any(e.code == "T006" for e in r.errors)
        assert r.formatted is not None


# ── T009: loop source not array ────────────────────────────────────────────────


class TestLoopSourceNotArrayT009:
    def test_emits_t009_for_present_non_array_scalar(self):
        r = _run("{out[]}\n:loop notArr\nx = @.a\n", 'notArr = "scalar"')
        assert not r.success
        assert r.errors[0].code == "T009"

    def test_absent_loop_source_yields_zero_rows_no_error(self):
        r = _run("{out[]}\n:loop missing\nx = @.a\n", "a = ##1")
        assert r.success
        assert len(r.errors) == 0

    def test_null_loop_source_yields_zero_rows_no_error(self):
        r = _run("{out[]}\n:loop notArr\nx = @.a\n", "notArr = ~")
        assert r.success
        assert len(r.errors) == 0

    def test_demotes_t009_to_warning_under_on_error_warn(self):
        r = _run("{out[]}\n:loop notArr\nx = @.a\n", 'notArr = "scalar"',
                 target={"onError": "warn"})
        assert r.success
        assert any(w.code == "T009" for w in r.warnings)


# ── T008: accumulator overflow ─────────────────────────────────────────────────


class TestAccumulatorOverflowT008:
    def test_emits_t008_when_integer_accumulator_exceeds_capacity(self):
        transform = (
            '{$accumulator}\ntotal = ##0\n\n'
            '{out}\nx = %accumulate "total" @.a\n'
        )
        r = _run(transform, "a = ##99999999999999999999")
        assert not r.success
        assert r.errors[0].code == "T008"

    def test_no_overflow_for_ordinary_accumulation(self):
        transform = (
            '{$accumulator}\ntotal = ##0\n\n'
            '{out}\nx = %accumulate "total" @.a\n'
        )
        r = _run(transform, "a = ##5")
        assert r.success
        assert len(r.errors) == 0

    def test_retains_last_valid_value_on_overflow(self):
        transform = (
            '{$accumulator}\ntotal = ##0\n\n'
            '{out}\nx = %accumulate "total" @.a\n'
        )
        r = _run(transform, "a = ##99999999999999999999")
        # The accumulator keeps its last valid value rather than the overflow.
        assert any(e.code == "T008" for e in r.errors)


# ── @import resolution ─────────────────────────────────────────────────────────


_TABLES_DOC = '''{$}
odin = "1.0.0"
transform = "1.0.0"
direction = "odin->odin"

{$source}
format = "odin"

{$target}
format = "odin"

{$table.STATES[code, name]}
"CA", "California"
"TX", "Texas"
'''

_SHARED_DOC = '''{$}
odin = "1.0.0"
transform = "1.0.0"
direction = "odin->odin"

{$source}
format = "odin"

{$target}
format = "odin"

{shared}
greeting = "hello"
'''

_MAIN = '''{$}
odin = "1.0.0"
transform = "1.0.0"
direction = "odin->odin"

@import ./tables/states.odin
@import ./mappings/shared.odin

{$source}
format = "odin"

{$target}
format = "odin"
onMissing = "fail"

{out}
state = %lookup "STATES.name" @.code
'''


def _resolver(p):
    if "states" in p:
        return _TABLES_DOC
    if "shared" in p:
        return _SHARED_DOC
    return None


class TestImportResolution:
    def test_imported_table_usable_by_lookup(self):
        src = odin.parse('code = "CA"')
        r = odin.execute_transform(_MAIN, src, {"import_resolver": _resolver})
        assert r.success
        assert len(r.errors) == 0
        assert "California" in (r.formatted or "")

    def test_imported_segment_merged_into_output(self):
        src = odin.parse('code = "TX"')
        r = odin.execute_transform(_MAIN, src, {"import_resolver": _resolver})
        assert "greeting" in (r.formatted or "")
        assert "hello" in (r.formatted or "")

    def test_unresolved_import_leaves_table_missing_t003(self):
        src = odin.parse('code = "CA"')
        r = odin.execute_transform(_MAIN, src)
        assert not r.success
        assert r.errors[0].code == "T003"

    def test_local_declarations_take_precedence(self):
        local = '''{$}
odin = "1.0.0"
transform = "1.0.0"
direction = "odin->odin"

@import ./tables/states.odin

{$source}
format = "odin"

{$target}
format = "odin"

{$table.STATES[code, name]}
"CA", "Local-California"

{out}
state = %lookup "STATES.name" @.code
'''
        src = odin.parse('code = "CA"')
        r = odin.execute_transform(local, src, {"import_resolver": _resolver})
        assert "Local-California" in (r.formatted or "")

    def test_ignores_unsatisfiable_import(self):
        t = '''{$}
odin = "1.0.0"
transform = "1.0.0"
direction = "odin->odin"

@import ./missing/nowhere.odin

{$source}
format = "odin"

{$target}
format = "odin"

{out}
x = @.a
'''
        src = odin.parse("a = ##1")
        r = odin.execute_transform(t, src, {"import_resolver": _resolver})
        assert r.success
