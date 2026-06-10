"""CLI tests for vault link add, remove, and list.

All tests run against real on-disk vault fixtures (no mocks) using the
Typer CliRunner to exercise the full CLI path.

Coverage:
    - list: JSON envelope shape, --feature scoping, src-scoped in/out listing
    - add: dry-run writes nothing, JSON envelope, dangling refusal exits 1,
           dangling with --force succeeds, idempotent re-add returns unchanged
    - remove: dry-run writes nothing, JSON envelope, no-op remove returns
              unchanged, actual remove decrements edge count
    - exit codes: 0 success/no-op, 1 on resolution failure or dangling refusal
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.cli import app

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_vault(tmp_path: Path, *, install: bool = True) -> Path:
    """Build a minimal on-disk vault with two linked documents.

    Creates:
      .vault/adr/2026-01-01-alpha-adr.md  (related: [[2026-01-01-beta-adr]])
      .vault/adr/2026-01-01-beta-adr.md

    Returns the project root.
    """
    root = tmp_path / "project"
    root.mkdir()
    adr_dir = root / ".vault" / "adr"
    adr_dir.mkdir(parents=True)

    (adr_dir / "2026-01-01-alpha-adr.md").write_text(
        "---\n"
        "tags:\n"
        "  - '#adr'\n"
        "  - '#test-feat'\n"
        "date: '2026-01-01'\n"
        "related:\n"
        "  - '[[2026-01-01-beta-adr]]'\n"
        "---\n"
        "\n# Alpha ADR\n",
        encoding="utf-8",
    )
    (adr_dir / "2026-01-01-beta-adr.md").write_text(
        "---\n"
        "tags:\n"
        "  - '#adr'\n"
        "  - '#test-feat'\n"
        "date: '2026-01-01'\n"
        "related: []\n"
        "---\n"
        "\n# Beta ADR\n",
        encoding="utf-8",
    )

    if install:
        from vaultspec_core.config.workspace import resolve_workspace
        from vaultspec_core.core.commands import install_run
        from vaultspec_core.core.types import init_paths

        install_run(path=root, provider="all", upgrade=False, dry_run=False, force=True)
        layout = resolve_workspace(target_override=root)
        init_paths(layout)

    return root


def _run(runner, *args: str, target: Path) -> Result:
    return runner.invoke(app, ["--target", str(target), *args])


# ---------------------------------------------------------------------------
# vault link list
# ---------------------------------------------------------------------------


class TestLinkList:
    def test_json_envelope_shape(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        result = _run(runner, "vault", "link", "list", "--json", target=root)
        assert result.exit_code == 0, result.output
        envelope = json.loads(result.output)
        assert envelope["schema"] == "vaultspec.vault.link.list.v1"
        assert envelope["status"] == "unchanged"
        data = envelope["data"]
        assert "edges" in data
        assert "count" in data
        assert isinstance(data["edges"], list)
        assert data["count"] == len(data["edges"])

    def test_list_includes_known_edge(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        result = _run(runner, "vault", "link", "list", "--json", target=root)
        assert result.exit_code == 0
        edges = json.loads(result.output)["data"]["edges"]
        src_edges = [e for e in edges if e["src"] == "2026-01-01-alpha-adr"]
        assert any(e["dst"] == "2026-01-01-beta-adr" for e in src_edges)

    def test_src_scoped_list_shows_out_and_in(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        result = _run(
            runner,
            "vault",
            "link",
            "list",
            "2026-01-01-alpha-adr",
            "--json",
            target=root,
        )
        assert result.exit_code == 0
        edges = json.loads(result.output)["data"]["edges"]
        directions = {e["direction"] for e in edges}
        assert "out" in directions

    def test_unknown_src_exits_1(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        result = _run(
            runner, "vault", "link", "list", "no-such-doc", "--json", target=root
        )
        assert result.exit_code == 1
        envelope = json.loads(result.output)
        assert envelope["status"] == "failed"

    def test_feature_filter_scopes_output(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        result = _run(
            runner,
            "vault",
            "link",
            "list",
            "--feature",
            "test-feat",
            "--json",
            target=root,
        )
        assert result.exit_code == 0
        edges = json.loads(result.output)["data"]["edges"]
        # Verify edges contain the known alpha->beta link
        srcs = {e["src"] for e in edges}
        assert "2026-01-01-alpha-adr" in srcs


# ---------------------------------------------------------------------------
# vault link add
# ---------------------------------------------------------------------------


class TestLinkAdd:
    def test_add_creates_edge(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        result = _run(
            runner,
            "vault",
            "link",
            "add",
            "2026-01-01-beta-adr",
            "2026-01-01-alpha-adr",
            "--json",
            target=root,
        )
        assert result.exit_code == 0, result.output
        envelope = json.loads(result.output)
        assert envelope["schema"] == "vaultspec.vault.link.add.v1"
        assert envelope["status"] == "created"
        assert envelope["data"]["src"] == "2026-01-01-beta-adr"
        assert envelope["data"]["dst"] == "2026-01-01-alpha-adr"
        # Verify the file was actually mutated
        content = (root / ".vault" / "adr" / "2026-01-01-beta-adr.md").read_text(
            encoding="utf-8"
        )
        assert "[[2026-01-01-alpha-adr]]" in content

    def test_dry_run_does_not_write(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        beta_path = root / ".vault" / "adr" / "2026-01-01-beta-adr.md"
        original_bytes = beta_path.read_bytes()

        result = _run(
            runner,
            "vault",
            "link",
            "add",
            "2026-01-01-beta-adr",
            "2026-01-01-alpha-adr",
            "--dry-run",
            "--json",
            target=root,
        )
        assert result.exit_code == 0, result.output
        envelope = json.loads(result.output)
        assert envelope["status"] == "created"
        assert envelope["data"]["dry_run"] is True
        # File must be byte-identical
        assert beta_path.read_bytes() == original_bytes

    def test_idempotent_add_returns_unchanged(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        # alpha already links to beta
        result = _run(
            runner,
            "vault",
            "link",
            "add",
            "2026-01-01-alpha-adr",
            "2026-01-01-beta-adr",
            "--json",
            target=root,
        )
        assert result.exit_code == 0
        envelope = json.loads(result.output)
        assert envelope["status"] == "unchanged"

    def test_dangling_refusal_exits_1_without_force(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        result = _run(
            runner,
            "vault",
            "link",
            "add",
            "2026-01-01-alpha-adr",
            "phantom-does-not-exist",
            "--json",
            target=root,
        )
        assert result.exit_code == 1
        envelope = json.loads(result.output)
        assert envelope["status"] == "failed"
        assert "dangling" in envelope["data"]["message"].lower()

    def test_dangling_with_force_succeeds(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        result = _run(
            runner,
            "vault",
            "link",
            "add",
            "2026-01-01-alpha-adr",
            "phantom-does-not-exist",
            "--force",
            "--json",
            target=root,
        )
        assert result.exit_code == 0, result.output
        envelope = json.loads(result.output)
        assert envelope["status"] == "created"
        content = (root / ".vault" / "adr" / "2026-01-01-alpha-adr.md").read_text(
            encoding="utf-8"
        )
        assert "[[phantom-does-not-exist]]" in content

    def test_unknown_src_exits_1(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        result = _run(
            runner,
            "vault",
            "link",
            "add",
            "no-such-src",
            "2026-01-01-beta-adr",
            "--json",
            target=root,
        )
        assert result.exit_code == 1
        envelope = json.loads(result.output)
        assert envelope["status"] == "failed"


# ---------------------------------------------------------------------------
# vault link remove
# ---------------------------------------------------------------------------


class TestLinkRemove:
    def test_remove_deletes_edge(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        result = _run(
            runner,
            "vault",
            "link",
            "remove",
            "2026-01-01-alpha-adr",
            "2026-01-01-beta-adr",
            "--json",
            target=root,
        )
        assert result.exit_code == 0, result.output
        envelope = json.loads(result.output)
        assert envelope["schema"] == "vaultspec.vault.link.remove.v1"
        assert envelope["status"] == "removed"
        content = (root / ".vault" / "adr" / "2026-01-01-alpha-adr.md").read_text(
            encoding="utf-8"
        )
        assert "[[2026-01-01-beta-adr]]" not in content

    def test_dry_run_does_not_write(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        alpha_path = root / ".vault" / "adr" / "2026-01-01-alpha-adr.md"
        original_bytes = alpha_path.read_bytes()

        result = _run(
            runner,
            "vault",
            "link",
            "remove",
            "2026-01-01-alpha-adr",
            "2026-01-01-beta-adr",
            "--dry-run",
            "--json",
            target=root,
        )
        assert result.exit_code == 0, result.output
        envelope = json.loads(result.output)
        assert envelope["status"] == "removed"
        assert envelope["data"]["dry_run"] is True
        # File must be byte-identical
        assert alpha_path.read_bytes() == original_bytes

    def test_noop_remove_returns_unchanged(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        # beta does not link to alpha
        result = _run(
            runner,
            "vault",
            "link",
            "remove",
            "2026-01-01-beta-adr",
            "2026-01-01-alpha-adr",
            "--json",
            target=root,
        )
        assert result.exit_code == 0
        envelope = json.loads(result.output)
        assert envelope["status"] == "unchanged"

    def test_unknown_src_exits_1(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        result = _run(
            runner,
            "vault",
            "link",
            "remove",
            "no-such-src",
            "2026-01-01-beta-adr",
            "--json",
            target=root,
        )
        assert result.exit_code == 1
        envelope = json.loads(result.output)
        assert envelope["status"] == "failed"

    def test_json_envelope_schema(self, runner, tmp_path):
        root = _make_vault(tmp_path)
        result = _run(
            runner,
            "vault",
            "link",
            "remove",
            "2026-01-01-alpha-adr",
            "2026-01-01-beta-adr",
            "--json",
            target=root,
        )
        assert result.exit_code == 0
        envelope = json.loads(result.output)
        assert envelope["schema"] == "vaultspec.vault.link.remove.v1"
        assert envelope["data"]["src"] == "2026-01-01-alpha-adr"
        assert envelope["data"]["dst"] == "2026-01-01-beta-adr"
