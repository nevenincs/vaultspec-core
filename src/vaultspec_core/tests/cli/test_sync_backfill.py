"""Regression tests for provider structural backfill and its dry-run preview.

- #133: ``sync`` / ``install --upgrade`` must create a structural provider
  directory (e.g. antigravity's ``workflows/``) that a newer release adds,
  rather than reporting success while leaving the provider ``partial``.
- #134: ``sync --dry-run`` and ``install --upgrade --dry-run`` must enumerate
  that backfill rather than printing an empty preview, and must not mutate.

All tests drive the real install/sync engine against a ``WorkspaceFactory``
install; no mocks. antigravity is used because it is the provider that owns a
content-less ``workflows/`` structural directory.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.core.commands import sync_provider
from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def _reset() -> Iterator[None]:
    reset_config()
    yield
    reset_config()


def _activate_context(root: Path) -> None:
    from vaultspec_core.config.workspace import resolve_workspace
    from vaultspec_core.core.types import init_paths

    init_paths(resolve_workspace(target_override=root))


def _all_item_paths(results: list) -> list[str]:
    return [rel for result in results for rel, _action in result.items]


class TestProviderStructuralBackfill:
    def test_sync_recreates_missing_structural_dir(self, tmp_path: Path) -> None:
        """sync backfills a missing structural provider directory (#133)."""
        WorkspaceFactory(tmp_path).install("antigravity")
        workflows = tmp_path / ".agents" / "workflows"
        assert workflows.is_dir()

        shutil.rmtree(workflows)
        assert not workflows.exists()

        _activate_context(tmp_path)
        results = sync_provider("antigravity")

        assert workflows.is_dir()
        assert any("workflows" in rel for rel in _all_item_paths(results))

    def test_install_upgrade_recreates_missing_structural_dir(
        self, tmp_path: Path
    ) -> None:
        """install --upgrade backfills the missing structural directory (#133)."""
        WorkspaceFactory(tmp_path).install("antigravity")
        workflows = tmp_path / ".agents" / "workflows"
        shutil.rmtree(workflows)
        assert not workflows.exists()

        WorkspaceFactory(tmp_path).install("antigravity", upgrade=True)

        assert workflows.is_dir()

    def test_sync_dry_run_previews_backfill_without_creating(
        self, tmp_path: Path
    ) -> None:
        """sync --dry-run enumerates the backfill but writes nothing (#134)."""
        WorkspaceFactory(tmp_path).install("antigravity")
        workflows = tmp_path / ".agents" / "workflows"
        shutil.rmtree(workflows)

        _activate_context(tmp_path)
        results = sync_provider("antigravity", dry_run=True)

        assert any("workflows" in rel for rel in _all_item_paths(results))
        assert not workflows.exists()

    def test_backfill_is_noop_when_structure_present(self, tmp_path: Path) -> None:
        """A complete provider yields no structural backfill items."""
        WorkspaceFactory(tmp_path).install("antigravity")
        _activate_context(tmp_path)

        results = sync_provider("antigravity")

        backfilled = [rel for rel in _all_item_paths(results) if "workflows" in rel]
        assert backfilled == []
