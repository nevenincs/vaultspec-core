"""End-to-end tests that mutating CLI verbs refresh the modified stamp.

Implements the verification surface for the vault-orientation ADR's
decision D3: every CLI verb that mutates a vault document refreshes that
document's ``modified:`` frontmatter stamp to today, and a pre-backfill
document that lacks the field gains it after ``date:``. A pure
``--dry-run`` mutation writes nothing.

Every test drives the real Typer application through ``CliRunner``
against documents on the real filesystem. No mocks, patches, stubs, or
skips: the verbs read and rewrite genuine ``.vault/`` files and the
assertions read those files back. Each seeded document carries a
deliberately stale stamp (or none) so a refresh to today is an
observable, non-tautological change.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory
from vaultspec_core.vaultcore import parse_vault_metadata

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration]

# A stamp old enough that a refresh to today is unmistakable, distinct
# from the documents' creation ``date:`` so the two fields never alias.
_STALE_STAMP = "2020-01-01"
_CREATED = "2024-03-04"


def _today() -> str:
    return datetime.date.today().isoformat()


def _run(root: Path, *args: str):
    """Invoke the CLI against *root* via the root ``-t`` target callback.

    Plan-mutator verbs take a positional plan PATH and expose no
    per-command ``--target`` option, so the workspace target is wired
    only through the root-level ``-t`` flag; stem-resolving verbs
    (``adr supersede``, ``link add``) resolve against that same root.
    """
    runner = CliRunner(env={"NO_COLOR": "1"})
    return runner.invoke(app, ["-t", str(root), *args])


def _stamp_of(path: Path) -> str | None:
    metadata, _ = parse_vault_metadata(path.read_text(encoding="utf-8"))
    return metadata.modified


def _write_adr(path: Path, stem: str, feature: str, *, modified: str | None) -> None:
    lines = [
        "---",
        "tags:",
        "  - '#adr'",
        f"  - '#{feature}'",
        f"date: '{_CREATED}'",
    ]
    if modified is not None:
        lines.append(f"modified: '{modified}'")
    lines += [
        "related: []",
        "---",
        "",
        f"# `{feature}` adr: `{stem}` | (**status:** `accepted`)",
        "",
        "## Problem Statement",
        "",
        "Body.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_plan(
    path: Path, feature: str, *, modified: str | None, checked: bool = False
) -> None:
    box = "x" if checked else " "
    lines = [
        "---",
        "tags:",
        "  - '#plan'",
        f"  - '#{feature}'",
        f"date: '{_CREATED}'",
    ]
    if modified is not None:
        lines.append(f"modified: '{modified}'")
    lines += [
        "tier: L1",
        "related:",
        f"  - '[[{_CREATED}-{feature}-adr]]'",
        "---",
        "",
        f"# `{feature}` plan",
        "",
        f"{feature} L1 plan body.",
        "",
        f"- [{box}] `S01` - audit the widget; `src/module/widget.py`.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


class TestPlanStepCheckRefreshesStamp:
    """`vault plan step check` refreshes the plan's modified stamp."""

    def test_check_refreshes_stale_stamp(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / ".vault" / "plan"
        plan_dir.mkdir(parents=True)
        plan = plan_dir / f"{_CREATED}-widget-plan.md"
        _write_plan(plan, "widget", modified=_STALE_STAMP)

        result = _run(tmp_path, "vault", "plan", "step", "check", str(plan), "S01")

        assert result.exit_code == 0, result.output
        assert _stamp_of(plan) == _today()
        # The step really closed - the mutation was genuine, not a no-op.
        assert "- [x] `S01`" in plan.read_text(encoding="utf-8")


class TestStamplessPlanGainsField:
    """A plan with no modified field gains one on the first mutation."""

    def test_mutation_adds_field_after_date(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / ".vault" / "plan"
        plan_dir.mkdir(parents=True)
        plan = plan_dir / f"{_CREATED}-gizmo-plan.md"
        _write_plan(plan, "gizmo", modified=None)
        assert _stamp_of(plan) is None

        result = _run(tmp_path, "vault", "plan", "step", "check", str(plan), "S01")

        assert result.exit_code == 0, result.output
        assert _stamp_of(plan) == _today()
        # The stamp lands directly after the date line, in schema position.
        frontmatter = plan.read_text(encoding="utf-8").split("---")[1]
        stripped = [ln.strip() for ln in frontmatter.strip().splitlines()]
        date_index = stripped.index(f"date: '{_CREATED}'")
        assert stripped[date_index + 1] == f"modified: '{_today()}'"


class TestAdrSupersedeRefreshesBoth:
    """`vault adr supersede` refreshes both the old and the new ADR."""

    def test_both_stamps_refresh(self, tmp_path: Path) -> None:
        WorkspaceFactory(tmp_path).install()
        adr_dir = tmp_path / ".vault" / "adr"
        adr_dir.mkdir(parents=True, exist_ok=True)
        old_stem = f"{_CREATED}-old-widget-adr"
        new_stem = f"{_CREATED}-new-widget-adr"
        old = adr_dir / f"{old_stem}.md"
        new = adr_dir / f"{new_stem}.md"
        _write_adr(old, "old decision", "widget", modified=_STALE_STAMP)
        _write_adr(new, "new decision", "widget", modified=_STALE_STAMP)

        result = _run(tmp_path, "vault", "adr", "supersede", old_stem, "--by", new_stem)

        assert result.exit_code == 0, result.output
        assert _stamp_of(old) == _today()
        assert _stamp_of(new) == _today()
        # The supersession itself landed: the old ADR's status flipped and
        # the new ADR records the supersedes edge.
        old_meta, _ = parse_vault_metadata(old.read_text(encoding="utf-8"))
        new_meta, _ = parse_vault_metadata(new.read_text(encoding="utf-8"))
        assert old_meta.superseded_by == new_stem
        assert old_stem in new_meta.supersedes


class TestLinkAddRefreshesTarget:
    """`vault link add` refreshes the source document it rewrites."""

    def test_src_stamp_refreshes(self, tmp_path: Path) -> None:
        WorkspaceFactory(tmp_path).install()
        adr_dir = tmp_path / ".vault" / "adr"
        adr_dir.mkdir(parents=True, exist_ok=True)
        src_stem = f"{_CREATED}-src-widget-adr"
        dst_stem = f"{_CREATED}-dst-widget-adr"
        src = adr_dir / f"{src_stem}.md"
        dst = adr_dir / f"{dst_stem}.md"
        _write_adr(src, "source", "widget", modified=_STALE_STAMP)
        _write_adr(dst, "destination", "widget", modified=_STALE_STAMP)

        result = _run(tmp_path, "vault", "link", "add", src_stem, dst_stem)

        assert result.exit_code == 0, result.output
        # The edge was genuinely written into the source's related: block.
        src_meta, _ = parse_vault_metadata(src.read_text(encoding="utf-8"))
        assert f"[[{dst_stem}]]" in src_meta.related
        assert _stamp_of(src) == _today()


class TestDryRunLeavesFileUntouched:
    """A pure --dry-run mutation writes nothing, stamp included."""

    def test_plan_check_dry_run_does_not_write(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / ".vault" / "plan"
        plan_dir.mkdir(parents=True)
        plan = plan_dir / f"{_CREATED}-doodad-plan.md"
        _write_plan(plan, "doodad", modified=_STALE_STAMP)
        before = plan.read_text(encoding="utf-8")

        result = _run(
            tmp_path, "vault", "plan", "step", "check", str(plan), "S01", "--dry-run"
        )

        assert result.exit_code == 0, result.output
        # File is byte-for-byte unchanged: the stale stamp survives.
        assert plan.read_text(encoding="utf-8") == before
        assert _stamp_of(plan) == _STALE_STAMP
        # The truthful preview still shows the stamp change in the diff.
        assert f"modified: '{_today()}'" in result.output

    def test_adr_supersede_dry_run_does_not_write(self, tmp_path: Path) -> None:
        WorkspaceFactory(tmp_path).install()
        adr_dir = tmp_path / ".vault" / "adr"
        adr_dir.mkdir(parents=True, exist_ok=True)
        old_stem = f"{_CREATED}-dry-old-adr"
        new_stem = f"{_CREATED}-dry-new-adr"
        old = adr_dir / f"{old_stem}.md"
        new = adr_dir / f"{new_stem}.md"
        _write_adr(old, "old", "doodad", modified=_STALE_STAMP)
        _write_adr(new, "new", "doodad", modified=_STALE_STAMP)
        old_before = old.read_text(encoding="utf-8")
        new_before = new.read_text(encoding="utf-8")

        result = _run(
            tmp_path,
            "vault",
            "adr",
            "supersede",
            old_stem,
            "--by",
            new_stem,
            "--dry-run",
        )

        assert result.exit_code == 0, result.output
        assert old.read_text(encoding="utf-8") == old_before
        assert new.read_text(encoding="utf-8") == new_before
