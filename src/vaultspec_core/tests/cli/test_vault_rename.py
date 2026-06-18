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
        assert _env(result)["data"]["incoming_rewritten"] >= 1
        beta_text = _beta(root).read_text(encoding="utf-8")
        assert "[[2026-01-01-gamma-adr]]" in beta_text
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
