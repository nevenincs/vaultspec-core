"""Tests for the consolidated execution ledger's row parser."""

from __future__ import annotations

import pytest

from vaultspec_core.vaultcore.exec_ledger import (
    append_rows,
    format_row,
    is_ledger_stem,
    ledger_step_ids,
    parse_ledger_rows,
)

LEDGER = """# `demo` ledger

## Changes

- `S01` `M` `src/a.py`
- `S01` `A` `tests/test_a.py`
- `S02` `D` `src/b.py`
- `S02` `R` `src/old.py` -> `src/new.py`
- `S02` `verify:` `uv run pytest` -> `pass`

## Notes

- `S02` left a scaffold in `src/new.py`.
"""


def test_is_ledger_stem_matches_only_the_suffix() -> None:
    assert is_ledger_stem("2026-08-23-demo-ledger")
    assert not is_ledger_stem("2026-08-23-demo-S01")
    assert not is_ledger_stem("2026-08-23-demo-P01-summary")


def test_parses_step_op_and_paths() -> None:
    rows = parse_ledger_rows(LEDGER)

    assert rows[0].step_id == "S01"
    assert rows[0].op == "M"
    assert rows[0].paths == ("src/a.py",)
    assert rows[3].op == "R"
    assert rows[3].paths == ("src/old.py", "src/new.py")


def test_verify_row_carries_no_op() -> None:
    verify = parse_ledger_rows(LEDGER)[4]

    assert verify.step_id == "S02"
    assert verify.op is None
    assert "uv run pytest" in verify.paths


def test_per_step_record_rows_carry_no_step_id() -> None:
    rows = parse_ledger_rows("## Changes\n\n- `M` `src/a.py`\n")

    assert rows[0].step_id is None
    assert rows[0].op == "M"
    assert rows[0].paths == ("src/a.py",)


def test_notes_rows_are_never_parsed_as_changes() -> None:
    """A Notes row naming a Step must not register that Step as covered."""
    assert ledger_step_ids(LEDGER) == ("S01", "S02")


def test_absent_changes_section_yields_nothing() -> None:
    assert parse_ledger_rows("# heading\n\n## Scope\n\n- `a.py`\n") == ()
    assert ledger_step_ids("# heading\n") == ()


def test_malformed_rows_are_skipped_not_raised() -> None:
    body = "## Changes\n\n- no backticks here\n-\n- `S01` `M` `src/a.py`\n"

    assert ledger_step_ids(body) == ("S01",)


def test_step_ids_are_deduplicated_in_first_seen_order() -> None:
    body = "## Changes\n\n- `S02` `M` `b.py`\n- `S01` `M` `a.py`\n- `S02` `M` `c.py`\n"

    assert ledger_step_ids(body) == ("S02", "S01")


class TestAppendRows:
    """The ledger is append-only and idempotent."""

    def test_format_row_renders_cells(self) -> None:
        assert format_row("S01", "M", "src/a.py") == "- `S01` `M` `src/a.py`"
        assert (
            format_row("S02", "R", "src/old.py", "src/new.py")
            == "- `S02` `R` `src/old.py` -> `src/new.py`"
        )

    def test_appends_into_changes_not_end_of_document(self) -> None:
        updated = append_rows(LEDGER, [format_row("S03", "A", "src/c.py")])

        assert ledger_step_ids(updated) == ("S01", "S02", "S03")
        # The Notes section survives, still after Changes.
        assert updated.index("## Notes") > updated.index("- `S03`")
        assert "left a scaffold" in updated

    def test_existing_rows_are_never_rewritten(self) -> None:
        updated = append_rows(LEDGER, [format_row("S03", "A", "src/c.py")])
        before = list(parse_ledger_rows(LEDGER))
        after = list(parse_ledger_rows(updated))

        assert after[: len(before)] == before

    def test_duplicate_row_is_not_appended_twice(self) -> None:
        row = format_row("S01", "M", "src/a.py")
        updated = append_rows(LEDGER, [row])

        assert updated == LEDGER

    def test_repeated_appends_do_not_accumulate_blank_lines(self) -> None:
        body = LEDGER
        for index in range(3):
            body = append_rows(body, [format_row("S03", "A", f"src/c{index}.py")])

        assert "\n\n\n" not in body
        assert ledger_step_ids(body) == ("S01", "S02", "S03")

    def test_missing_changes_section_raises(self) -> None:
        with pytest.raises(ValueError, match="no '## Changes' section"):
            append_rows("# heading\n\n## Scope\n\n- `a.py`\n", ["- `S01` `M` `a.py`"])


class TestLedgerFilenameIsAValidExecName:
    """The ledger name must be declared beside the other exec conventions.

    A name the convention does not recognise is not merely reported: `vault
    check structure --fix` renames it to '...-ledger-exec.md', which no
    longer satisfies `is_ledger_stem`, so the document silently stops being
    a ledger. This is a regression guard for that.
    """

    def test_ledger_filename_is_accepted(self) -> None:
        from vaultspec_core.vaultcore.models import DocType, VaultConstants

        errors = VaultConstants.validate_filename(
            "2026-08-23-demo-ledger.md", DocType.EXEC
        )

        assert errors == []

    def test_renamed_ledger_would_not_read_as_a_ledger(self) -> None:
        """Why the exemption matters, stated as a property."""
        assert is_ledger_stem("2026-08-23-demo-ledger")
        assert not is_ledger_stem("2026-08-23-demo-ledger-exec")

    def test_step_and_summary_names_still_accepted(self) -> None:
        from vaultspec_core.vaultcore.models import DocType, VaultConstants

        assert (
            VaultConstants.validate_filename("2026-08-23-demo-S01.md", DocType.EXEC)
            == []
        )
        assert (
            VaultConstants.validate_filename(
                "2026-08-23-demo-P01-summary.md", DocType.EXEC
            )
            == []
        )

    def test_a_bogus_exec_name_is_still_rejected(self) -> None:
        from vaultspec_core.vaultcore.models import DocType, VaultConstants

        errors = VaultConstants.validate_filename("not-a-vault-name.md", DocType.EXEC)

        assert errors
