"""Regression tests for the manifest / migration version cluster.

Covers three rough edges reported against 0.1.20, exercised against a real
``WorkspaceFactory`` install with on-disk manifests. No mocks or patches.

- #119: the "manifest newer than package" advisory must not fire when the
  manifest version equals the highest version the running package knows about,
  which includes a bundled migration target above the package version (0.1.20
  shipped a migration tagged 0.1.21).
- #121: ``migrations status`` must not label entries "applied" when the manifest
  has no version baseline - the applied state is genuinely unknown.
- #124: ``sync`` and the ``gitignore_reversal`` migration must converge the
  nested ``.vaultspec/rules/rules/.gitignore`` to the shipped team-shared policy
  so custom rule sources stop being silently un-tracked.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.core.helpers import package_version, parse_version_tuple
from vaultspec_core.core.manifest import read_manifest_data, write_manifest_data
from vaultspec_core.migrations import REGISTRY, reset_workspace_cache
from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def _reset() -> Iterator[None]:
    reset_config()
    reset_workspace_cache()
    yield
    reset_config()
    reset_workspace_cache()


def _activate_context(root: Path) -> None:
    from vaultspec_core.config.workspace import resolve_workspace
    from vaultspec_core.core.types import init_paths

    init_paths(resolve_workspace(target_override=root))


def _known_ceiling() -> str:
    """Highest version the running package knows about (package or migration)."""
    versions = [package_version(), *(m.target_version for m in REGISTRY)]
    return max(versions, key=parse_version_tuple)


def _bump_patch(version: str) -> str:
    parts = list(parse_version_tuple(version))
    parts[-1] += 1
    return ".".join(str(p) for p in parts)


# ---------------------------------------------------------------------------
# #119 - version advisory must respect bundled migration targets
# ---------------------------------------------------------------------------
class TestVersionAdvisoryGating:
    def _warn_for_manifest_version(self, root: Path, version: str) -> bool:
        from vaultspec_core.core.diagnosis.diagnosis import WorkspaceDiagnosis
        from vaultspec_core.core.diagnosis.signals import FrameworkSignal
        from vaultspec_core.core.resolver import (
            ResolutionPlan,
            _resolve_version_warning,
        )

        data = read_manifest_data(root)
        data.vaultspec_version = version
        write_manifest_data(root, data)
        plan = ResolutionPlan()
        _resolve_version_warning(
            plan, WorkspaceDiagnosis(framework=FrameworkSignal.PRESENT)
        )
        return any("Consider upgrading" in w for w in plan.warnings)

    def test_manifest_at_known_ceiling_does_not_warn(self, tmp_path: Path) -> None:
        """A manifest stamped to a bundled migration target must not advise upgrade.

        The 0.1.20 package bundles a migration tagged 0.1.21, so running
        ``migrations run`` stamps the manifest to 0.1.21 - above the package
        version. The advisory previously pointed at a release that does not
        exist on PyPI (issue #119).
        """
        WorkspaceFactory(tmp_path).install("core")
        _activate_context(tmp_path)
        assert self._warn_for_manifest_version(tmp_path, _known_ceiling()) is False

    def test_manifest_beyond_known_ceiling_still_warns(self, tmp_path: Path) -> None:
        """A manifest genuinely newer than anything the package knows still warns."""
        WorkspaceFactory(tmp_path).install("core")
        _activate_context(tmp_path)
        beyond = _bump_patch(_known_ceiling())
        assert self._warn_for_manifest_version(tmp_path, beyond) is True


# ---------------------------------------------------------------------------
# #121 - migrations status must not assert "applied" without a baseline
# ---------------------------------------------------------------------------
class TestMigrationStatusUnknownBaseline:
    def test_unset_manifest_renders_unknown_not_applied(self, tmp_path: Path) -> None:
        from typer.testing import CliRunner

        from vaultspec_core.cli import app

        WorkspaceFactory(tmp_path).install("core")
        data = read_manifest_data(tmp_path)
        data.vaultspec_version = ""
        write_manifest_data(tmp_path, data)

        result = CliRunner(env={"NO_COLOR": "1"}).invoke(
            app, ["migrations", "status", "--target", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        assert "unset" in result.output
        # Without a baseline the applied state is unknowable; never claim applied.
        assert "applied" not in result.output
        assert "unknown" in result.output


# ---------------------------------------------------------------------------
# #124 - the nested rules/.gitignore must converge on sync and migration
# ---------------------------------------------------------------------------
_STALE_NESTED_GITIGNORE = (
    "# Custom rules (plain *.md) are gitignored.\n*.md\n!*.builtin.md\n"
)


def _nested_gitignore(root: Path) -> Path:
    # Pre-flatten layout: the gitignore_reversal migration (0.1.20) runs before
    # the framework-flatten migration, so it still targets the nested
    # rules/rules path.
    return root / ".vaultspec" / "rules" / "rules" / ".gitignore"


def _rules_gitignore(root: Path) -> Path:
    # Post-flatten layout: the spec-layer gitignore lives in the flat rules dir.
    return root / ".vaultspec" / "rules" / ".gitignore"


def _shipped_policy() -> str:
    from vaultspec_core.builtins import _builtins_root

    return (_builtins_root() / "rules" / ".gitignore").read_text(encoding="utf-8")


class TestNestedGitignoreConvergence:
    def test_sync_converges_stale_nested_gitignore(self, tmp_path: Path) -> None:
        WorkspaceFactory(tmp_path).install("core")
        gitignore = _rules_gitignore(tmp_path)
        gitignore.parent.mkdir(parents=True, exist_ok=True)
        gitignore.write_text(_STALE_NESTED_GITIGNORE, encoding="utf-8")

        WorkspaceFactory(tmp_path).sync("all")

        assert gitignore.read_text(encoding="utf-8") == _shipped_policy()

    def test_convergence_leaves_operator_customised_file_untouched(
        self, tmp_path: Path
    ) -> None:
        from vaultspec_core.core.rules import converge_spec_layer_gitignore

        rules_src = tmp_path / ".vaultspec" / "rules"
        rules_src.mkdir(parents=True, exist_ok=True)
        custom = "# our policy\nsecrets/*.md\n"
        (rules_src / ".gitignore").write_text(custom, encoding="utf-8")

        changed = converge_spec_layer_gitignore(rules_src)

        assert changed is False
        assert (rules_src / ".gitignore").read_text(encoding="utf-8") == custom

    def test_convergence_is_idempotent(self, tmp_path: Path) -> None:
        from vaultspec_core.core.rules import converge_spec_layer_gitignore

        rules_src = tmp_path / ".vaultspec" / "rules"
        rules_src.mkdir(parents=True, exist_ok=True)
        (rules_src / ".gitignore").write_text(_STALE_NESTED_GITIGNORE, encoding="utf-8")

        first = converge_spec_layer_gitignore(rules_src)
        second = converge_spec_layer_gitignore(rules_src)

        assert first is True
        assert second is False
        assert (rules_src / ".gitignore").read_text(
            encoding="utf-8"
        ) == _shipped_policy()

    def test_gitignore_reversal_migration_converges_nested(
        self, tmp_path: Path
    ) -> None:
        from vaultspec_core.migrations.m_0_1_20_gitignore_reversal import migrate

        WorkspaceFactory(tmp_path).install("core")
        nested = _nested_gitignore(tmp_path)
        nested.parent.mkdir(parents=True, exist_ok=True)
        nested.write_text(_STALE_NESTED_GITIGNORE, encoding="utf-8")

        result = migrate(tmp_path)

        assert result.counts.get("nested_gitignore") == 1
        assert nested.read_text(encoding="utf-8") == _shipped_policy()
