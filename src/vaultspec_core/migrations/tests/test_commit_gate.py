"""Tests for the ``commit_gate`` registry entry.

Exercises :func:`vaultspec_core.migrations.m_0_2_5_commit_gate.migrate`, and
the driver that runs it, against real workspaces: retired hooks converge on the
gate in a YAML config (including one ``sync`` no longer manages) and in a
managed ``prek.toml`` block, the operator's own hooks survive, and declined,
hook-free, block-free and config-free workspaces are left exactly as found.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.prek_boundary import (
    MARKER_BEGIN,
    MARKER_END,
    render_prek_hook_block,
)
from vaultspec_core.migrations.m_0_2_5_commit_gate import migrate, preview

if TYPE_CHECKING:
    from pathlib import Path

    from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

pytestmark = [pytest.mark.integration]

_YAML = ".pre-commit-config.yaml"
_YML = ".pre-commit-config.yml"
_GATE = "vaultspec-commit-gate"

# The hook set 0.2.4 scaffolded, beside an operator hook that must survive.
_RETIRED = (
    "repos:\n"
    "- repo: local\n"
    "  hooks:\n"
    "  # The operator's own gate.\n"
    "  - id: ruff\n"
    "    entry: ruff check\n"
    "    language: system\n"
    "  - id: vault-fix\n"
    "    name: Vault gate\n"
    "    entry: uv run --no-sync vaultspec-core vault check all\n"
    "    language: system\n"
    "    pass_filenames: false\n"
    "  - id: spec-check\n"
    "    name: Spec check\n"
    "    entry: uv run --no-sync vaultspec-core spec doctor --gate-errors\n"
    "    language: system\n"
    "    pass_filenames: false\n"
    "  - id: check-provider-artifacts\n"
    "    name: Check provider artifacts\n"
    "    entry: uv run --no-sync vaultspec-core check-providers\n"
    "    always_run: true\n"
    "    language: system\n"
    "    pass_filenames: false\n"
)

_OPERATOR_TOML = '[[repos]]\nrepo = "local"\n\n[[repos.hooks]]\nid = "mine"\n'

_RETIRED_BLOCK = (
    f"{MARKER_BEGIN}\n"
    "[[repos]]\n"
    'repo = "local"\n'
    "\n"
    "[[repos.hooks]]\n"
    'id = "vault-fix"\n'
    'name = "Vault gate"\n'
    'entry = "uv run --no-sync vaultspec-core vault check all"\n'
    'language = "system"\n'
    "pass_filenames = false\n"
    f"{MARKER_END}\n"
)


@pytest.fixture
def factory(tmp_path: Path) -> WorkspaceFactory:
    from vaultspec_core.tests.cli.workspace_factory import WorkspaceFactory

    return WorkspaceFactory(tmp_path)


def _ids(path: Path) -> list[str]:
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [
        h["id"] for r in data["repos"] if r.get("repo") == "local" for h in r["hooks"]
    ]


def _decline(root: Path) -> None:
    from vaultspec_core.core.workspace_mode import (
        HooksDeclaration,
        write_hooks_declaration,
    )

    write_hooks_declaration(root, HooksDeclaration(pre_commit=False))


class TestYamlConfig:
    def test_retired_hooks_converge_and_the_operators_hook_survives(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / _YAML).write_text(_RETIRED, encoding="utf-8")

        result = migrate(tmp_path)

        assert result.counts == {"yaml": 1, "prek": 0}
        assert _ids(tmp_path / _YAML) == ["ruff", _GATE]
        assert "# The operator's own gate." in (tmp_path / _YAML).read_text(
            encoding="utf-8"
        )

    def test_a_second_run_does_nothing(self, tmp_path: Path) -> None:
        (tmp_path / _YAML).write_text(_RETIRED, encoding="utf-8")
        migrate(tmp_path)
        before = (tmp_path / _YAML).read_bytes()

        result = migrate(tmp_path)

        assert result.counts == {"yaml": 0, "prek": 0}
        assert (tmp_path / _YAML).read_bytes() == before

    def test_the_yml_spelling_is_converged_in_place(self, tmp_path: Path) -> None:
        (tmp_path / _YML).write_text(_RETIRED, encoding="utf-8")

        migrate(tmp_path)

        assert _ids(tmp_path / _YML) == ["ruff", _GATE]
        assert not (tmp_path / _YAML).exists()

    def test_an_install_sync_no_longer_manages_still_converges(
        self, factory: WorkspaceFactory
    ) -> None:
        """The case the release migration exists for: sync skips this config."""
        from vaultspec_core.core.manifest import read_manifest_data, write_manifest_data

        factory.install()
        manifest = read_manifest_data(factory.root)
        manifest.precommit_managed = False
        write_manifest_data(factory.root, manifest)
        (factory.root / _YAML).write_text(_RETIRED, encoding="utf-8")

        factory.sync()
        assert "vault-fix" in _ids(factory.root / _YAML)

        migrate(factory.root)

        assert _ids(factory.root / _YAML) == ["ruff", _GATE]

    def test_a_config_without_vaultspec_hooks_is_left_alone(
        self, tmp_path: Path
    ) -> None:
        text = "repos:\n- repo: local\n  hooks:\n  - id: ruff\n    entry: ruff\n"
        (tmp_path / _YAML).write_text(text, encoding="utf-8")

        migrate(tmp_path)

        assert (tmp_path / _YAML).read_text(encoding="utf-8") == text

    def test_no_config_is_created(self, tmp_path: Path) -> None:
        migrate(tmp_path)

        assert not (tmp_path / _YAML).exists()
        assert not (tmp_path / _YML).exists()

    def test_a_declined_workspace_is_left_alone(self, tmp_path: Path) -> None:
        (tmp_path / _YAML).write_text(_RETIRED, encoding="utf-8")
        _decline(tmp_path)

        result = migrate(tmp_path)

        assert result.counts == {"yaml": 0, "prek": 0}
        assert (tmp_path / _YAML).read_text(encoding="utf-8") == _RETIRED


class TestPrekConfig:
    def test_a_stale_managed_block_is_re_rendered(self, tmp_path: Path) -> None:
        from vaultspec_core.core.enums import InstallMode

        (tmp_path / "prek.toml").write_text(
            _OPERATOR_TOML + "\n" + _RETIRED_BLOCK, encoding="utf-8"
        )

        result = migrate(tmp_path)

        assert result.counts == {"yaml": 0, "prek": 1}
        text = (tmp_path / "prek.toml").read_text(encoding="utf-8")
        assert text == _OPERATOR_TOML + "\n" + render_prek_hook_block(
            InstallMode.DEPENDENCY
        )
        assert migrate(tmp_path).counts == {"yaml": 0, "prek": 0}

    def test_a_prek_toml_without_a_managed_block_gets_none(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "prek.toml").write_text(_OPERATOR_TOML, encoding="utf-8")
        (tmp_path / _YAML).write_text(_RETIRED, encoding="utf-8")

        result = migrate(tmp_path)

        assert result.counts == {"yaml": 0, "prek": 0}
        assert (tmp_path / "prek.toml").read_text(encoding="utf-8") == _OPERATOR_TOML
        # prek reads prek.toml alone, so the superseded YAML is not converged.
        assert (tmp_path / _YAML).read_text(encoding="utf-8") == _RETIRED


def test_preview_deletes_nothing(tmp_path: Path) -> None:
    (tmp_path / _YAML).write_text(_RETIRED, encoding="utf-8")

    assert preview(tmp_path) == []


def test_the_driver_runs_it_for_a_0_2_4_workspace(factory: WorkspaceFactory) -> None:
    """Installed at 0.2.4, the registry converges the config and records 0.2.5."""
    from vaultspec_core.core.manifest import read_manifest_data, write_manifest_data
    from vaultspec_core.migrations import run_pending_migrations

    factory.install()
    manifest = read_manifest_data(factory.root)
    manifest.vaultspec_version = "0.2.4"
    write_manifest_data(factory.root, manifest)
    (factory.root / _YAML).write_text(_RETIRED, encoding="utf-8")

    results = run_pending_migrations(factory.root)

    assert [r.name for r in results] == ["commit_gate"]
    assert _ids(factory.root / _YAML) == ["ruff", _GATE]
    assert read_manifest_data(factory.root).vaultspec_version == "0.2.5"


class TestLeavesWhatItCannotRead:
    def test_a_crlf_prek_toml_keeps_its_line_endings(self, tmp_path: Path) -> None:
        """Only vaultspec's lines between the markers may change.

        The migration runs unattended, so re-emitting a CRLF file as LF - or
        adding a trailing newline the operator's tail never had - would be a
        whole-file diff nobody asked for.
        """
        crlf_block = _RETIRED_BLOCK.replace("\n", "\r\n")
        tail = "# operator tail, no final newline"
        original = _OPERATOR_TOML.replace("\n", "\r\n") + "\r\n" + crlf_block + tail
        (tmp_path / "prek.toml").write_bytes(original.encode())

        assert migrate(tmp_path).counts == {"yaml": 0, "prek": 1}

        rewritten = (tmp_path / "prek.toml").read_bytes().decode()
        assert "\n" not in rewritten.replace("\r\n", "")
        assert rewritten.startswith(_OPERATOR_TOML.replace("\n", "\r\n"))
        assert rewritten.endswith("\r\n" + tail)
        assert _GATE in rewritten

    def test_an_unparseable_yaml_config_is_reported_not_called_clean(
        self, tmp_path: Path
    ) -> None:
        broken = "repos: [unclosed\n  - id: vault-fix\n"
        (tmp_path / _YAML).write_text(broken, encoding="utf-8")

        result = migrate(tmp_path)

        assert "could not be read" in result.summary
        assert (tmp_path / _YAML).read_text(encoding="utf-8") == broken

    def test_an_invalid_prek_toml_is_left_untouched(self, tmp_path: Path) -> None:
        broken = "[[repos\n" + _RETIRED_BLOCK
        (tmp_path / "prek.toml").write_text(broken, encoding="utf-8")

        result = migrate(tmp_path)

        assert "could not be read" in result.summary
        assert (tmp_path / "prek.toml").read_text(encoding="utf-8") == broken
