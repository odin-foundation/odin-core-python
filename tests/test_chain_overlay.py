"""Unit tests for chain overlay current-state computation (collapse_chain)."""
import odin

# ── Replace ────────────────────────────────────────────────────────────────


class TestReplace:
    def test_replaces_repeated_path_with_later_value(self):
        doc = odin.collapse_chain('{p}\nname = "A"\n\n---\n\n{p}\nname = "B"')
        assert doc.get("p.name").value == "B"

    def test_keeps_untouched_paths_from_earlier_documents(self):
        doc = odin.collapse_chain('{p}\nname = "A"\nkeep = "x"\n\n---\n\n{p}\nname = "B"')
        assert doc.get("p.keep").value == "x"
        assert doc.get("p.name").value == "B"

    def test_adds_new_paths_introduced_later(self):
        doc = odin.collapse_chain('{p}\nname = "A"\n\n---\n\n{p}\nextra = "new"')
        assert doc.get("p.extra").value == "new"
        assert doc.get("p.name").value == "A"


# ── Null removal ───────────────────────────────────────────────────────────


class TestNullRemoval:
    def test_removes_field_set_to_null_later(self):
        doc = odin.collapse_chain('{p}\nname = "A"\nold = "gone"\n\n---\n\n{p}\nold = ~')
        assert doc.get("p.old") is None
        assert doc.get("p.name").value == "A"

    def test_removes_nested_descendants_when_parent_nulled(self):
        doc = odin.collapse_chain('{p}\na.b = "x"\na.c = "y"\nkeep = "z"\n\n---\n\n{p}\na = ~')
        assert doc.get("p.a.b") is None
        assert doc.get("p.a.c") is None
        assert doc.get("p.keep").value == "z"

    def test_reassign_after_removal(self):
        doc = odin.collapse_chain('{p}\nx = "old"\n\n---\n\n{p}\nx = ~\n\n---\n\n{p}\nx = "new"')
        assert doc.get("p.x").value == "new"


# ── Array clear ────────────────────────────────────────────────────────────


class TestArrayClear:
    def test_clears_all_elements_of_array(self):
        doc = odin.collapse_chain(
            '{p}\ntags[0] = "x"\ntags[1] = "y"\nkeep = "z"\n\n---\n\n{p}\ntags[] = ~'
        )
        assert doc.get("p.tags[0]") is None
        assert doc.get("p.tags[1]") is None
        assert doc.get("p.keep").value == "z"

    def test_repopulate_after_clear(self):
        doc = odin.collapse_chain(
            '{p}\ntags[0] = "x"\n\n---\n\n{p}\ntags[] = ~\n\n---\n\n{p}\ntags[0] = "fresh"'
        )
        assert doc.get("p.tags[0]").value == "fresh"


# ── Metadata isolation ─────────────────────────────────────────────────────


class TestMetadataIsolation:
    def test_carries_only_final_document_metadata(self):
        doc = odin.collapse_chain(
            '{$}\nid = "first"\nrole = "base"\n\n{p}\nn = "A"\n\n'
            '---\n\n{$}\nid = "second"\n\n{p}\nn = "B"'
        )
        assert doc.metadata.get("id").value == "second"
        assert doc.metadata.get("role") is None
        assert doc.get("$.role") is None
        assert doc.get("p.n").value == "B"


# ── Multi-document chains and pass-through ─────────────────────────────────


class TestMultiDocument:
    def test_three_document_chain_resolves_to_last_value(self):
        doc = odin.collapse_chain('{p}\nv = "1"\n\n---\n\n{p}\nv = "2"\n\n---\n\n{p}\nv = "3"')
        assert doc.get("p.v").value == "3"

    def test_single_document_passthrough(self):
        doc = odin.collapse_chain('{p}\nv = "1"')
        assert doc.get("p.v").value == "1"

    def test_accepts_pre_parsed_document_list(self):
        docs = odin.parse_documents('{p}\nv = "1"\n\n---\n\n{p}\nv = "2"')
        doc = odin.collapse_chain(docs)
        assert doc.get("p.v").value == "2"


# ── Edge cases ─────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_null_in_first_document_removes_nothing(self):
        doc = odin.collapse_chain('{p}\nx = ~\n\n---\n\n{p}\ny = "kept"')
        assert doc.get("p.x") is None
        assert doc.get("p.y").value == "kept"

    def test_array_clear_only_affects_named_array(self):
        doc = odin.collapse_chain(
            '{p}\na[0] = "1"\nb[0] = "2"\n\n---\n\n{p}\na[] = ~'
        )
        assert doc.get("p.a[0]") is None
        assert doc.get("p.b[0]").value == "2"

    def test_subtree_removal_does_not_affect_sibling_prefix(self):
        # nulling "a" must not remove "ab" which merely shares a prefix
        doc = odin.collapse_chain('{p}\na = "1"\nab = "2"\n\n---\n\n{p}\na = ~')
        assert doc.get("p.a") is None
        assert doc.get("p.ab").value == "2"
