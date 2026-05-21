"""End-to-end tests for the ``--dev`` flag and dev-shaped gitignore output.

Issue #88: vaultspec-core is itself the source of the framework rules
that the wheel bundles into ``vaultspec_core/builtins/``.  In a consumer
project the install/sync logic correctly emits a managed
``.gitignore`` block that includes a bare ``.vaultspec/`` line, so the
generated install target does not pollute git history.  In the source
repo that exact rule silently swallows new framework content from
``git status`` and ``git add``.

These tests pin the new contract:

- ``get_recommended_entries(target, dev=False)`` keeps the consumer
  shape (includes ``.vaultspec/``).
- ``get_recommended_entries(target, dev=True)`` switches to the source
  shape (omits ``.vaultspec/``, retains the truly-generated children).
- The Typer commands ``install``, ``uninstall``, and ``sync`` accept a
  ``--dev`` flag that is hidden from ``--help`` (a developer-only flag,
  per the cli-paper-cuts ADR) yet still callable, and the CLI source no
  longer references the dropped env-var bypass.
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
    """``get_recommended_entries`` must change shape on the ``dev=`` flag."""

    def test_consumer_shape_includes_bare_vaultspec(self, tmp_path: Path) -> None:
        from vaultspec_core.core.gitignore import get_recommended_entries

        _make_consumer_repo(tmp_path)
        entries = get_recommended_entries(tmp_path, dev=False)
        # In consumer mode the bare ignore is correct: `.vaultspec/` is a
        # generated install target.
        assert ".vaultspec/" in entries
        # Truly-generated children remain ignored in both modes.
        assert ".vaultspec/_snapshots/" in entries
        assert ".vaultspec/*.lock" in entries

    def test_dev_shape_drops_bare_vaultspec(self, tmp_path: Path) -> None:
        from vaultspec_core.core.gitignore import get_recommended_entries

        _make_dev_repo(tmp_path)
        entries = get_recommended_entries(tmp_path, dev=True)
        # The bare line is the bug.  In dev mode it must NOT appear, so
        # new agents/skills/templates added under .vaultspec/rules/ stay
        # visible to git.
        assert ".vaultspec/" not in entries
        # Generated children stay ignored.
        assert ".vaultspec/_snapshots/" in entries
        assert ".vaultspec/*.lock" in entries
        # providers.json is local install state in either mode; dev mode
        # explicitly ignores it because the bare `.vaultspec/` line that
        # would otherwise have masked it is gone.
        assert ".vaultspec/providers.json" in entries

    def test_dev_shape_default_false_preserves_consumer_behaviour(
        self, tmp_path: Path
    ) -> None:
        """Calling without the keyword must keep the legacy consumer output."""
        from vaultspec_core.core.gitignore import get_recommended_entries

        _make_consumer_repo(tmp_path)
        # No ``dev=`` keyword -> default False -> consumer shape.
        entries = get_recommended_entries(tmp_path)
        assert ".vaultspec/" in entries

    def test_no_framework_no_entries(self, tmp_path: Path) -> None:
        """Without a ``.vaultspec/`` directory the function emits nothing for it."""
        from vaultspec_core.core.gitignore import get_recommended_entries

        # No `.vaultspec/` dir.
        entries = get_recommended_entries(tmp_path, dev=True)
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
