"""End-to-end tests for the ``--dev`` flag and the team-shared gitignore policy.

The ``--dev`` flag authorises install/uninstall/sync writes inside the
vaultspec-core source repository itself (the source-repo write guard).
It is hidden from ``--help`` (a developer-only flag, per the
cli-paper-cuts ADR) yet still callable.

Per the cli-spec-gitignore ADR the managed ``.gitignore`` block lists
only per-machine runtime by-products; the spec layer (``.vaultspec/``
rules, skills, agents, system), the synthesised ``CLAUDE.md``, and
``.mcp.json`` are team-shared and committed to git so a teammate
cloning the project inherits its authoritative policy. The recommended
entry set no longer varies by source-repo mode.

These tests pin the contract:

- ``get_recommended_entries(target)`` lists only runtime by-products
  and never the bare ``.vaultspec/`` line.
- The Typer commands ``install``, ``uninstall``, and ``sync`` accept a
  ``--dev`` flag that is hidden from ``--help`` yet still callable, and
  the CLI source no longer references the dropped env-var bypass.
"""

from __future__ import annotations

import re
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def _make_dev_repo(root: Path) -> Path:
    """Materialise the minimum on-disk shape for ``is_dev_repo`` to fire.

    The hardened detection (issue #88) needs both signals to coincide:
    a ``pyproject.toml`` declaring ``name = "vaultspec-core"`` *and*
    the package source layout at ``src/vaultspec_core/__init__.py``.
    """
    (root / "pyproject.toml").write_text(
        '[project]\nname = "vaultspec-core"\n', encoding="utf-8"
    )
    pkg = root / "src" / "vaultspec_core"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (root / ".vaultspec").mkdir(parents=True, exist_ok=True)
    return root


def _make_consumer_repo(root: Path) -> Path:
    """Materialise an unrelated consumer project with a ``.vaultspec/`` dir."""
    (root / "pyproject.toml").write_text(
        '[project]\nname = "downstream-app"\n', encoding="utf-8"
    )
    (root / ".vaultspec").mkdir(parents=True, exist_ok=True)
    return root


class TestRecommendedEntriesShape:
    """``get_recommended_entries`` lists only runtime by-products; the spec
    layer is team-shared (cli-spec-gitignore ADR)."""

    def test_spec_layer_is_not_blanket_ignored(self, tmp_path: Path) -> None:
        from vaultspec_core.core.gitignore import get_recommended_entries

        _make_consumer_repo(tmp_path)
        entries = get_recommended_entries(tmp_path)
        # Authored content under .vaultspec/ (rules, skills, agents,
        # system) is committed so teammates inherit it. The bare
        # directory ignore must never appear.
        assert ".vaultspec/" not in entries

    def test_runtime_children_stay_ignored(self, tmp_path: Path) -> None:
        from vaultspec_core.core.gitignore import get_recommended_entries

        _make_consumer_repo(tmp_path)
        entries = get_recommended_entries(tmp_path)
        # Per-machine runtime state stays ignored: the snapshot
        # directory, advisory-lock sentinels, and the install manifest.
        assert ".vaultspec/_snapshots/" in entries
        assert ".vaultspec/*.lock" in entries
        assert ".vaultspec/providers.json" in entries

    def test_mcp_config_is_shared(self, tmp_path: Path) -> None:
        from vaultspec_core.core.gitignore import get_recommended_entries

        _make_consumer_repo(tmp_path)
        (tmp_path / ".mcp.json").write_text("{}", encoding="utf-8")
        entries = get_recommended_entries(tmp_path)
        # .mcp.json is committed so teammates inherit the MCP config;
        # only its advisory-lock sentinel is per-machine runtime state.
        assert ".mcp.json" not in entries
        assert "/.mcp.json.lock" in entries

    def test_no_framework_no_entries(self, tmp_path: Path) -> None:
        """Without a ``.vaultspec/`` directory the function emits nothing for it."""
        from vaultspec_core.core.gitignore import get_recommended_entries

        # No `.vaultspec/` dir.
        entries = get_recommended_entries(tmp_path)
        assert ".vaultspec/" not in entries
        assert ".vaultspec/_snapshots/" not in entries


class TestCliSurface:
    """``--dev`` is a hidden developer flag: absent from ``--help``,
    still accepted by the parser; the env-var bypass is gone."""

    def _help_for(self, command: str) -> str:
        result = subprocess.run(
            [sys.executable, "-m", "vaultspec_core", command, "--help"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return result.stdout + result.stderr

    def _dev_flag_accepted(self, command: str) -> bool:
        """True when the parser accepts ``--dev`` (hidden, not unknown)."""
        result = subprocess.run(
            [sys.executable, "-m", "vaultspec_core", command, "--dev", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0 and "No such option" not in (
            result.stdout + result.stderr
        )

    def test_install_hides_but_accepts_dev_flag(self) -> None:
        assert not re.search(r"--dev\b", self._help_for("install"))
        assert self._dev_flag_accepted("install")

    def test_uninstall_hides_but_accepts_dev_flag(self) -> None:
        assert not re.search(r"--dev\b", self._help_for("uninstall"))
        assert self._dev_flag_accepted("uninstall")

    def test_sync_hides_but_accepts_dev_flag(self) -> None:
        assert not re.search(r"--dev\b", self._help_for("sync"))
        assert self._dev_flag_accepted("sync")

    def test_cli_source_does_not_reference_env_var(self) -> None:
        import pathlib

        cli_root = (
            pathlib.Path(__file__).resolve().parents[1]
            / "src"
            / "vaultspec_core"
            / "cli"
            / "root.py"
        )
        text = cli_root.read_text(encoding="utf-8")
        assert "VAULTSPEC_ALLOW_DEV_WRITES" not in text


class TestSourceRepoIntegration:
    """Two full integration paths through ``install_run`` to confirm wiring."""

    def test_install_run_in_source_repo_without_dev_raises(
        self, tmp_path: Path
    ) -> None:
        from vaultspec_core.core.commands import install_run
        from vaultspec_core.core.guards import DevRepoProtectionError

        _make_dev_repo(tmp_path)
        with pytest.raises(DevRepoProtectionError, match="source repository"):
            install_run(path=tmp_path, dry_run=True)

    def test_install_run_in_source_repo_with_dev_proceeds_dry_run(
        self, tmp_path: Path
    ) -> None:
        """``dev=True`` lifts the guard; dry-run avoids any real writes."""
        from vaultspec_core.core.commands import install_run

        _make_dev_repo(tmp_path)
        result = install_run(path=tmp_path, dry_run=True, dev=True)
        assert result["action"] == "dry_run"
