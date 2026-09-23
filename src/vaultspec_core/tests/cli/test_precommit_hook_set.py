"""The canonical pre-commit hook set gates and never mutates the tree.

A commit hook that rewrites files runs inside the hook runner's
stash-and-restore cycle, which in a shared worktree can destroy other
writers' uncommitted edits, and with ``pass_filenames: false`` its blast radius
is the whole corpus whatever the commit touched. These tests pin that every
rendered hook is a read-only gate, and that a hook retired for violating that
leaves existing installs through the ordinary sync and migrate paths. Real
filesystem, no test doubles.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.enums import InstallMode
from vaultspec_core.core.precommit import (
    ALL_MANAGED_HOOK_IDS,
    CANONICAL_HOOK_IDS,
    RETIRED_HOOK_IDS,
    canonical_precommit_hooks_for_mode,
    entry_prefix_for_mode,
    scaffold_precommit,
    strip_managed_precommit_hooks,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

_CONFIG = ".pre-commit-config.yaml"

# Subcommand shapes that write to the working tree. ``sanitize`` verbs strip
# content by definition; ``--fix`` turns any checker into a repairer.
_MUTATING = re.compile(r"(^|\s)(--fix|sanitize)(\s|$)")

_RETIRED_YAML_HOOK = (
    "  - id: vault-sanitize-annotations\n"
    "    name: Vault sanitize annotations\n"
    "    entry: uv run --no-sync vaultspec-core vault sanitize annotations\n"
    "    language: system\n"
    "    pass_filenames: false\n"
)


def _local_hook_ids(config: Path) -> list[str]:
    import yaml

    data = yaml.safe_load(config.read_text(encoding="utf-8"))
    return [
        hook["id"]
        for repo in data["repos"]
        if repo.get("repo") == "local"
        for hook in repo["hooks"]
    ]


@pytest.mark.parametrize("mode", list(InstallMode))
def test_every_canonical_hook_is_a_read_only_gate(mode: InstallMode) -> None:
    prefix = entry_prefix_for_mode(mode)
    for hook in canonical_precommit_hooks_for_mode(mode):
        entry = str(hook["entry"])
        assert entry.startswith(prefix + " "), entry
        subcommand = entry[len(prefix) + 1 :]
        assert not _MUTATING.search(subcommand), (
            f"hook {hook['id']!r} renders a tree-mutating command: {entry!r}"
        )


def test_retired_ids_are_not_rendered_but_stay_managed() -> None:
    assert not RETIRED_HOOK_IDS & CANONICAL_HOOK_IDS
    assert RETIRED_HOOK_IDS <= ALL_MANAGED_HOOK_IDS


class TestRetiredHookLeavesExistingInstalls:
    def test_scaffold_removes_the_retired_hook_and_keeps_the_rest(
        self, tmp_path: Path
    ) -> None:
        config = tmp_path / _CONFIG
        config.write_text(
            "repos:\n"
            "- repo: local\n"
            "  hooks:\n"
            "  - id: ruff-check\n"
            "    name: ruff\n"
            "    entry: ruff check\n"
            "    language: system\n" + _RETIRED_YAML_HOOK,
            encoding="utf-8",
        )

        assert scaffold_precommit(tmp_path, mode=InstallMode.DEPENDENCY)

        ids = _local_hook_ids(config)
        assert "vault-sanitize-annotations" not in ids
        assert "ruff-check" in ids
        assert set(ids) >= CANONICAL_HOOK_IDS

    def test_uninstall_strips_the_retired_hook(self, tmp_path: Path) -> None:
        config = tmp_path / _CONFIG
        config.write_text(
            "repos:\n- repo: local\n  hooks:\n" + _RETIRED_YAML_HOOK,
            encoding="utf-8",
        )

        assert strip_managed_precommit_hooks(config)
        assert not config.exists()


class TestMigrateDropsTheRetiredHookFromPrek:
    def _stale_block(self) -> str:
        from vaultspec_core.core.prek_boundary import render_prek_hook_block

        block = render_prek_hook_block(InstallMode.DEPENDENCY)
        retired = (
            "\n[[repos.hooks]]\n"
            'id = "vault-sanitize-annotations"\n'
            'name = "Vault sanitize annotations"\n'
            'entry = "uv run --no-sync vaultspec-core vault sanitize annotations"\n'
            'language = "system"\n'
            "pass_filenames = false\n"
        )
        end = block.rindex("# <<<")
        return block[:end] + retired.lstrip("\n") + block[end:]

    def test_managed_block_is_re_rendered(self, tmp_path: Path) -> None:
        from vaultspec_core.core.prek_boundary import (
            migrate_hooks_to_prek,
            render_prek_hook_block,
        )

        operator = '[[repos]]\nrepo = "local"\n'
        prek = tmp_path / "prek.toml"
        prek.write_text(operator + "\n" + self._stale_block(), encoding="utf-8")

        result = migrate_hooks_to_prek(tmp_path, mode=InstallMode.DEPENDENCY)

        assert result.status == "migrated"
        text = prek.read_text(encoding="utf-8")
        assert "vault-sanitize-annotations" not in text
        assert text == operator + "\n" + render_prek_hook_block(InstallMode.DEPENDENCY)
        second = migrate_hooks_to_prek(tmp_path, mode=InstallMode.DEPENDENCY)
        assert second.status == "unchanged"

    def test_operator_authored_retired_hook_is_left_alone(self, tmp_path: Path) -> None:
        from vaultspec_core.core.prek_boundary import (
            migrate_hooks_to_prek,
            render_prek_hook_block,
        )

        operator = (
            '[[repos]]\nrepo = "local"\n\n[[repos.hooks]]\n'
            'id = "vault-sanitize-annotations"\n'
            'entry = "my own command"\n'
            'language = "system"\n'
        )
        prek = tmp_path / "prek.toml"
        content = operator + "\n" + render_prek_hook_block(InstallMode.DEPENDENCY)
        prek.write_text(content, encoding="utf-8")

        result = migrate_hooks_to_prek(tmp_path, mode=InstallMode.DEPENDENCY)

        assert result.status == "unchanged"
        assert prek.read_text(encoding="utf-8") == content
