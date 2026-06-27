"""CLI tests for the vault rename verb.

Exercises ``vault rename`` through the real Typer CliRunner against on-disk
vault fixtures (no mocks).

Coverage:
    - rename: moves the file, removes the old, re-keys the node id
    - incoming-link rewrite: a doc referencing the old stem in ``related:`` is
      re-pointed to the new stem
    - collision: refuses when the target already exists, leaves the source
    - invalid target stem: refuses a path-separator / flag-shaped stem
    - blob-hash concurrency: stale expected hash refuses; matching hash allows
    - dry-run: writes nothing
    - exit codes: 0 updated, 1 refusal/conflict
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.cli import app
from vaultspec_core.vaultcore.blob_hash import git_blob_oid

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result

pytestmark = [pytest.mark.unit]


_ALPHA = (
    "---\n"
    "tags:\n"
    "  - '#adr'\n"
    "  - '#test-feat'\n"
    "date: '2026-01-01'\n"
    "modified: '2026-01-01'\n"
    "related: []\n"
    "---\n"
    "\n# Alpha ADR\n\nOriginal body.\n"
)

# Beta references alpha in ``related:`` so the incoming-link rewrite is exercised.
_BETA = (
    "---\n"
    "tags:\n"
    "  - '#adr'\n"
    "  - '#test-feat'\n"
    "date: '2026-01-01'\n"
    "modified: '2026-01-01'\n"
    "related:\n"
    "  - '[[2026-01-01-alpha-adr]]'\n"
    "---\n"
    "\n# Beta ADR\n\nBeta body.\n"
)


def _make_vault(tmp_path: Path) -> Path:
    """Build a minimal installed vault: alpha (renamed) + beta (references alpha)."""
    root = tmp_path / "project"
    root.mkdir()
    adr_dir = root / ".vault" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "2026-01-01-alpha-adr.md").write_text(_ALPHA, encoding="utf-8")
    (adr_dir / "2026-01-01-beta-adr.md").write_text(_BETA, encoding="utf-8")

    from vaultspec_core.config.workspace import resolve_workspace
    from vaultspec_core.core.commands import install_run
    from vaultspec_core.core.types import init_paths

    install_run(path=root, provider="all", upgrade=False, dry_run=False, force=True)
    layout = resolve_workspace(target_override=root)
    init_paths(layout)
    return root


def _alpha(root: Path) -> Path:
    return root / ".vault" / "adr" / "2026-01-01-alpha-adr.md"


def _beta(root: Path) -> Path:
    return root / ".vault" / "adr" / "2026-01-01-beta-adr.md"


def _gamma(root: Path) -> Path:
    return root / ".vault" / "adr" / "2026-01-01-gamma-adr.md"


def _run(runner, *args: str, target: Path, stdin: str | None = None) -> Result:
    return runner.invoke(app, ["--target", str(target), *args], input=stdin)


def _env(result: Result) -> dict:
    return json.loads(result.output)


class TestVaultRename:
    def test_moves_file_and_rekeys(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        result = _run(
            runner,
            "vault",
            "rename",
            "2026-01-01-alpha-adr",
            "--to",
            "2026-01-01-gamma-adr",
            "--json",
            target=root,
        )
        assert result.exit_code == 0, result.output
        env = _env(result)
        assert env["status"] == "updated"
        assert env["data"]["new_node_id"] == "doc:2026-01-01-gamma-adr"
        assert _gamma(root).exists()
        assert not _alpha(root).exists()

    def test_rewrites_incoming_related(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        result = _run(
            runner,
            "vault",
            "rename",
            "2026-01-01-alpha-adr",
            "--to",
            "2026-01-01-gamma-adr",
            "--json",
            target=root,
        )
        assert result.exit_code == 0, result.output
        # ``incoming_rewritten`` is now the shared cascade's per-LINK count
        # (``CheckResult.fixed_count``), not the former per-document tally.
        # Beta carries exactly one ``related:`` wiki-link to alpha, so exactly
        # one link is rewritten - here per-link and per-doc coincide at 1.
        assert _env(result)["data"]["incoming_rewritten"] == 1
        beta_text = _beta(root).read_text(encoding="utf-8")
        assert "[[2026-01-01-gamma-adr]]" in beta_text
        assert "[[2026-01-01-alpha-adr]]" not in beta_text

    def test_incoming_rewritten_counts_links_not_docs_on_dedup(self, runner, tmp_path):
        """A dedup-drop is reported but NOT counted - the per-link contract.

        When a referencing doc already lists the rename target ahead of the old
        stem, the shared cascade DROPS the now-duplicate old entry rather than
        rewriting it, so ``fixed_count`` (and thus ``incoming_rewritten``) is 0
        even though one document was modified. The retired per-document counter
        would have reported 1 here; this pins the deliberate semantic change.
        """
        root = _make_vault(tmp_path)
        # Order matters: the target stem precedes the old stem, so by the time
        # the old entry is visited the target is already a seen wiki-link and
        # the rewrite collapses to a drop.
        _beta(root).write_text(
            "---\n"
            "tags:\n"
            "  - '#adr'\n"
            "  - '#test-feat'\n"
            "date: '2026-01-01'\n"
            "modified: '2026-01-01'\n"
            "related:\n"
            "  - '[[2026-01-01-gamma-adr]]'\n"
            "  - '[[2026-01-01-alpha-adr]]'\n"
            "---\n"
            "\n# Beta ADR\n\nBeta body.\n",
            encoding="utf-8",
        )
        result = _run(
            runner,
            "vault",
            "rename",
            "2026-01-01-alpha-adr",
            "--to",
            "2026-01-01-gamma-adr",
            "--json",
            target=root,
        )
        assert result.exit_code == 0, result.output
        assert _env(result)["data"]["incoming_rewritten"] == 0
        beta_text = _beta(root).read_text(encoding="utf-8")
        assert beta_text.count("[[2026-01-01-gamma-adr]]") == 1
        assert "[[2026-01-01-alpha-adr]]" not in beta_text

    def test_collision_refuses_and_leaves_source(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        before = _alpha(root).read_text(encoding="utf-8")
        result = _run(
            runner,
            "vault",
            "rename",
            "2026-01-01-alpha-adr",
            "--to",
            "2026-01-01-beta-adr",
            "--json",
            target=root,
        )
        assert result.exit_code == 1
        env = _env(result)
        assert env["status"] == "failed"
        assert env["data"].get("collision") is True
        assert _alpha(root).read_text(encoding="utf-8") == before

    def test_invalid_target_stem_refuses(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        result = _run(
            runner,
            "vault",
            "rename",
            "2026-01-01-alpha-adr",
            "--to",
            "bad/stem",
            "--json",
            target=root,
        )
        assert result.exit_code == 1
        assert _env(result)["status"] == "failed"
        assert _alpha(root).exists()

    def test_stale_blob_hash_refuses(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        result = _run(
            runner,
            "vault",
            "rename",
            "2026-01-01-alpha-adr",
            "--to",
            "2026-01-01-gamma-adr",
            "--expected-blob-hash",
            "0" * 40,
            "--json",
            target=root,
        )
        assert result.exit_code == 1
        assert _env(result)["status"] == "failed"
        assert _alpha(root).exists()
        assert not _gamma(root).exists()

    def test_matching_blob_hash_allows(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        good = git_blob_oid(_alpha(root).read_bytes())
        result = _run(
            runner,
            "vault",
            "rename",
            "2026-01-01-alpha-adr",
            "--to",
            "2026-01-01-gamma-adr",
            "--expected-blob-hash",
            good,
            "--json",
            target=root,
        )
        assert result.exit_code == 0, result.output
        assert _gamma(root).exists()

    def test_dry_run_writes_nothing(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        result = _run(
            runner,
            "vault",
            "rename",
            "2026-01-01-alpha-adr",
            "--to",
            "2026-01-01-gamma-adr",
            "--dry-run",
            "--json",
            target=root,
        )
        assert result.exit_code == 0, result.output
        assert _env(result)["data"]["dry_run"] is True
        assert _alpha(root).exists()
        assert not _gamma(root).exists()

    def test_directory_at_destination_refuses_without_dangling(self, runner, tmp_path):
        """A blocked rename never rewrites incoming links (window closed).

        Plant a directory exactly where the target file would land. The
        rename is refused as a collision and, because the file is renamed
        BEFORE the link cascade, no incoming ``related:`` link is ever
        rewritten - beta still points at the live alpha stem, never a dangling
        gamma stem.
        """
        root = _make_vault(tmp_path)
        (root / ".vault" / "adr" / "2026-01-01-gamma-adr.md").mkdir()
        alpha_before = _alpha(root).read_bytes()
        beta_before = _beta(root).read_bytes()

        result = _run(
            runner,
            "vault",
            "rename",
            "2026-01-01-alpha-adr",
            "--to",
            "2026-01-01-gamma-adr",
            "--json",
            target=root,
        )
        assert result.exit_code == 1
        env = _env(result)
        assert env["status"] == "failed"
        assert env["data"].get("collision") is True
        # No mutation leaked: source and referrer are byte-identical and beta
        # still references the original (existing) stem - no dangling link.
        assert _alpha(root).read_bytes() == alpha_before
        assert _beta(root).read_bytes() == beta_before
        assert "[[2026-01-01-alpha-adr]]" in _beta(root).read_text(encoding="utf-8")

    def test_midapply_failure_rolls_back_byte_for_byte(self, tmp_path):
        """A mid-apply failure restores the vault and leaves no dangling link.

        Drives the exact transactional composition ``vault rename`` uses -
        ``RenameTransaction`` plus the shared ``rewrite_incoming_refs`` cascade -
        then raises a real exception AFTER the file rename and link rewrite have
        landed on disk. The transaction must roll the vault back byte-for-byte:
        the renamed file returns, the target vanishes, and the referrer's link
        is restored to the live stem (never left pointing at the missing one).
        """
        from vaultspec_core.vaultcore.checks._base import CheckResult
        from vaultspec_core.vaultcore.rename_engine import (
            RenameTransaction,
            docs_lock_target,
        )
        from vaultspec_core.vaultcore.rename_ops import rewrite_incoming_refs

        root = _make_vault(tmp_path)
        docs_dir = root / ".vault"
        alpha, beta, gamma = _alpha(root), _beta(root), _gamma(root)
        alpha_before = alpha.read_bytes()
        beta_before = beta.read_bytes()

        class _InducedError(RuntimeError):
            pass

        cascade = CheckResult(check_name="vault-rename")
        with (
            pytest.raises(_InducedError),
            RenameTransaction(docs_dir, lock_target=docs_lock_target(docs_dir)) as tx,
        ):
            tx.snapshot([alpha, beta])
            assert tx.rename(alpha, gamma) is True
            rewrite_incoming_refs(root, [(alpha.stem, gamma.stem)], cascade)
            # Both mutations are now on disk: prove they landed before the
            # induced failure so the rollback assertions below are meaningful.
            assert gamma.exists()
            assert "[[2026-01-01-gamma-adr]]" in beta.read_text(encoding="utf-8")
            raise _InducedError("induced mid-apply failure")

        assert alpha.read_bytes() == alpha_before
        assert beta.read_bytes() == beta_before
        assert not gamma.exists()
        beta_text = beta.read_text(encoding="utf-8")
        assert "[[2026-01-01-alpha-adr]]" in beta_text
        assert "[[2026-01-01-gamma-adr]]" not in beta_text

    def test_archived_doc_bytes_unchanged_by_rename(self, runner, tmp_path):
        """An archived doc referencing the renamed stem is never mutated.

        A document under ``.vault/_archive/`` is out of rename scope: the
        cascade must skip it (``exclude_dirs={'_archive'}``) and the rollback
        snapshot must not capture or stamp it. Its bytes - both the ``related:``
        wiki-link to the renamed stem AND the ``modified:`` stamp - stay
        byte-identical across a ``vault rename``. Mirrors the feature-rename
        suite's ``test_archived_doc_bytes_unchanged_by_rename``.
        """
        root = _make_vault(tmp_path)
        archived = root / ".vault" / "_archive" / "adr" / "2026-01-01-bygone-adr.md"
        archived.parent.mkdir(parents=True, exist_ok=True)
        archived.write_text(
            "---\n"
            "tags:\n"
            "  - '#adr'\n"
            "  - '#bygone'\n"
            "date: '2026-01-01'\n"
            "modified: '2026-01-01'\n"
            "related:\n"
            "  - '[[2026-01-01-alpha-adr]]'\n"
            "---\n"
            "\n# Bygone ADR\n\nArchived body.\n",
            encoding="utf-8",
        )
        before = archived.read_bytes()

        result = _run(
            runner,
            "vault",
            "rename",
            "2026-01-01-alpha-adr",
            "--to",
            "2026-01-01-gamma-adr",
            "--json",
            target=root,
        )
        assert result.exit_code == 0, result.output
        assert _env(result)["status"] == "updated"
        # The archived back-reference and its modified stamp are intact: the
        # cascade excludes _archive and the rollback snapshot never captures it,
        # so neither the related: rewrite nor the stamp refresh may touch it.
        assert archived.read_bytes() == before
