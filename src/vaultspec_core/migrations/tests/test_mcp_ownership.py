"""Upgrade ownership without promoting repository claims into authority."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core.enums import McpScope
from vaultspec_core.core.manifest import (
    ManifestData,
    read_manifest_data,
    write_manifest_data,
)
from vaultspec_core.core.mcps_ownership import ownership_path
from vaultspec_core.migrations import (
    REGISTRY,
    WRITE_PLACEMENT_SCOPES,
    MigrationError,
    MigrationScope,
    list_pending,
    run_pending_migrations,
)
from vaultspec_core.migrations.m_0_3_2_mcp_ownership import MIGRATION, migrate, preview

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.mark.parametrize("contents", ["malformed json", '{"version":1,"targets":{}}'])
def test_retires_claims_without_importing_or_mutating_hosts(
    tmp_path: Path, contents: str
) -> None:
    workspace = tmp_path / "repo"
    sidecar = workspace / ".vaultspec" / "mcp-ownership.json"
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text(contents, encoding="utf-8")
    project = workspace / ".mcp.json"
    project.write_text(
        '{"mcpServers":{"victim":{"command":"external"}}}', encoding="utf-8"
    )
    local = tmp_path / ".claude.json"
    local.write_text('{"projects":{}}', encoding="utf-8")
    before = {path: path.read_bytes() for path in (project, local)}
    assert preview(workspace) == [sidecar]
    assert sidecar.exists()

    result = migrate(workspace)

    assert result.counts == {"retired": 1}
    assert "--force" in result.summary
    assert not sidecar.exists()
    assert not ownership_path(workspace, McpScope.PROJECT).exists()
    assert {path: path.read_bytes() for path in before} == before
    assert migrate(workspace).counts == {"retired": 0}
    assert preview(workspace) == []


def test_preserves_existing_trusted_ownership(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    sidecar = workspace / ".vaultspec" / "mcp-ownership.json"
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text('{"attacker":"claim"}', encoding="utf-8")
    trusted = ownership_path(workspace, McpScope.PROJECT)
    trusted.parent.mkdir(parents=True)
    target = str((workspace / ".mcp.json").resolve())
    trusted.write_text(
        json.dumps(
            {
                "version": 1,
                "targets": {
                    f"claude:project:{target}": {
                        "provider": "claude",
                        "scope": "project",
                        "path": target,
                        "managed": {"owned": "a" * 64},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    before = trusted.read_bytes()
    migrate(workspace)
    assert trusted.read_bytes() == before


def test_absent_sidecar_is_true_noop(tmp_path: Path) -> None:
    workspace = tmp_path / "absent"
    assert migrate(workspace).counts == {"retired": 0}
    assert not workspace.exists()


@pytest.mark.parametrize("linked_parent", [False, True])
def test_rejects_repository_links(tmp_path: Path, linked_parent: bool) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    external = outside / "mcp-ownership.json"
    external.write_text("external state", encoding="utf-8")
    framework = workspace / ".vaultspec"
    try:
        if linked_parent:
            framework.symlink_to(outside, target_is_directory=True)
        else:
            framework.mkdir()
            (framework / "mcp-ownership.json").symlink_to(external)
    except OSError as exc:
        pytest.skip(f"Cannot create test link: {exc}")
    with pytest.raises(MigrationError, match="linked path"):
        migrate(workspace)
    assert external.read_text(encoding="utf-8") == "external state"


def test_registered_upgrade_runs_once_and_respects_scope(tmp_path: Path) -> None:
    assert MIGRATION in REGISTRY
    assert MIGRATION.scope is MigrationScope.ENVIRONMENT
    workspace = tmp_path / "repo"
    write_manifest_data(workspace, ManifestData(vaultspec_version="0.3.1"))
    sidecar = workspace / ".vaultspec" / "mcp-ownership.json"
    sidecar.write_text('{"version":1,"targets":{}}', encoding="utf-8")
    assert list_pending(workspace, registry=[MIGRATION]) == [MIGRATION]
    assert (
        run_pending_migrations(
            workspace, registry=[MIGRATION], scopes=WRITE_PLACEMENT_SCOPES
        )
        == []
    )
    assert sidecar.exists()
    results = run_pending_migrations(workspace, registry=[MIGRATION])
    assert len(results) == 1
    assert results[0].counts == {"retired": 1}
    assert read_manifest_data(workspace).vaultspec_version == "0.3.2"
    assert run_pending_migrations(workspace, registry=[MIGRATION]) == []
