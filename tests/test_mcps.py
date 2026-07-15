"""Tests for MCP server registry: collection, CRUD, sync, and lifecycle."""

from __future__ import annotations

import json
import shutil
import tomllib
from uuid import uuid4

import pytest

from tests.constants import PROJECT_ROOT
from vaultspec_core.config import reset_config


def _make_workspace(tmp: object = None):
    """Create a minimal workspace with .vaultspec/mcps/ directory."""
    path = PROJECT_ROOT / ".pytest-tmp" / f"mcps-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    mcps_dir = path / ".vaultspec" / "mcps"
    mcps_dir.mkdir(parents=True, exist_ok=True)
    return path, mcps_dir


def _init_context(path):
    """Bootstrap a WorkspaceContext pointing at the given path."""
    from vaultspec_core.config.workspace import resolve_workspace
    from vaultspec_core.core.manifest import ManifestData, write_manifest_data
    from vaultspec_core.core.types import init_paths

    reset_config()
    # Create minimal .vaultspec structure for workspace resolution
    fw_dir = path / ".vaultspec"
    fw_dir.mkdir(parents=True, exist_ok=True)
    write_manifest_data(
        path,
        ManifestData(installed={"claude"}),
    )
    layout = resolve_workspace(target_override=path)
    return init_paths(layout)


def _owned_names(path, target_key: str = "claude:project") -> set[str]:
    """Read the real external MCP ownership record for one native target."""
    ownership = json.loads(
        (path / ".vaultspec" / "mcp-ownership.json").read_text(encoding="utf-8")
    )
    return set(ownership["targets"][target_key]["managed"])


@pytest.mark.unit
class TestServerName:
    def test_builtin_suffix(self):
        from vaultspec_core.core.mcps import _server_name

        assert _server_name("vaultspec-core.builtin.json") == "vaultspec-core"

    def test_json_suffix(self):
        from vaultspec_core.core.mcps import _server_name

        assert _server_name("my-server.json") == "my-server"

    def test_multi_dot_builtin(self):
        from vaultspec_core.core.mcps import _server_name

        assert _server_name("foo.bar.builtin.json") == "foo.bar"

    def test_multi_dot_json(self):
        from vaultspec_core.core.mcps import _server_name

        assert _server_name("foo.bar.json") == "foo.bar"

    def test_no_json_suffix(self):
        from vaultspec_core.core.mcps import _server_name

        assert _server_name("something") == "something"


@pytest.mark.unit
class TestCollectMcpServers:
    def test_empty_directory(self):
        path, _mcps_dir = _make_workspace()
        try:
            _init_context(path)
            from vaultspec_core.core.mcps import collect_mcp_servers

            result = collect_mcp_servers()
            assert result == {}
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_missing_directory(self):
        path = PROJECT_ROOT / ".pytest-tmp" / f"mcps-missing-{uuid4().hex}"
        path.mkdir(parents=True, exist_ok=True)
        try:
            _init_context(path)
            from vaultspec_core.core.mcps import collect_mcp_servers

            result = collect_mcp_servers()
            assert result == {}
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_single_builtin(self):
        path, mcps_dir = _make_workspace()
        try:
            config = {"command": "uv", "args": ["run", "test"]}
            (mcps_dir / "test-server.builtin.json").write_text(
                json.dumps(config), encoding="utf-8"
            )
            _init_context(path)
            from vaultspec_core.core.mcps import collect_mcp_servers

            result = collect_mcp_servers()
            assert "test-server" in result
            assert result["test-server"][1] == config
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_custom_definition(self):
        path, mcps_dir = _make_workspace()
        try:
            config = {"command": "node", "args": ["server.js"]}
            (mcps_dir / "custom-mcp.json").write_text(
                json.dumps(config), encoding="utf-8"
            )
            _init_context(path)
            from vaultspec_core.core.mcps import collect_mcp_servers

            result = collect_mcp_servers()
            assert "custom-mcp" in result
            assert result["custom-mcp"][1] == config
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_parse_error_captured_in_warnings(self):
        path, mcps_dir = _make_workspace()
        try:
            (mcps_dir / "bad.json").write_text("not valid json", encoding="utf-8")
            _init_context(path)
            from vaultspec_core.core.mcps import collect_mcp_servers

            warnings: list[str] = []
            result = collect_mcp_servers(warnings=warnings)
            assert result == {}
            assert len(warnings) == 1
            assert "bad.json" in warnings[0]
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_non_object_json_rejected(self):
        path, mcps_dir = _make_workspace()
        try:
            (mcps_dir / "array.json").write_text("[1, 2, 3]", encoding="utf-8")
            _init_context(path)
            from vaultspec_core.core.mcps import collect_mcp_servers

            warnings: list[str] = []
            result = collect_mcp_servers(warnings=warnings)
            assert result == {}
            assert len(warnings) == 1
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_mixed_builtin_and_custom(self):
        path, mcps_dir = _make_workspace()
        try:
            (mcps_dir / "core.builtin.json").write_text(
                json.dumps({"command": "uv"}), encoding="utf-8"
            )
            (mcps_dir / "custom.json").write_text(
                json.dumps({"command": "node"}), encoding="utf-8"
            )
            _init_context(path)
            from vaultspec_core.core.mcps import collect_mcp_servers

            result = collect_mcp_servers()
            assert len(result) == 2
            assert "core" in result
            assert "custom" in result
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_custom_shadows_builtin_in_collect(self):
        """When both foo.builtin.json and foo.json exist, custom config wins."""
        path, mcps_dir = _make_workspace()
        try:
            (mcps_dir / "srv.builtin.json").write_text(
                json.dumps({"command": "old-builtin"}), encoding="utf-8"
            )
            (mcps_dir / "srv.json").write_text(
                json.dumps({"command": "new-custom"}), encoding="utf-8"
            )
            _init_context(path)
            from vaultspec_core.core.mcps import collect_mcp_servers

            result = collect_mcp_servers()
            assert len(result) == 1
            assert result["srv"][1]["command"] == "new-custom"
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_empty_stem_filenames_skipped(self):
        """Files named '.json' or '.builtin.json' (no server name) are ignored."""
        path, mcps_dir = _make_workspace()
        try:
            (mcps_dir / ".json").write_text(
                json.dumps({"command": "bad"}), encoding="utf-8"
            )
            (mcps_dir / ".builtin.json").write_text(
                json.dumps({"command": "also-bad"}), encoding="utf-8"
            )
            (mcps_dir / "valid.json").write_text(
                json.dumps({"command": "good"}), encoding="utf-8"
            )
            _init_context(path)
            from vaultspec_core.core.mcps import collect_mcp_servers

            result = collect_mcp_servers()
            assert len(result) == 1
            assert "valid" in result
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)


@pytest.mark.unit
class TestMcpList:
    def test_shadowed_definition_shows_custom(self):
        path, mcps_dir = _make_workspace()
        try:
            (mcps_dir / "srv.builtin.json").write_text(
                json.dumps({"command": "old"}), encoding="utf-8"
            )
            (mcps_dir / "srv.json").write_text(
                json.dumps({"command": "new"}), encoding="utf-8"
            )
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_list

            items = mcp_list()
            assert len(items) == 1
            assert items[0]["name"] == "srv"
            assert "shadows" in items[0]["source"].lower()
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_lists_with_source_classification(self):
        path, mcps_dir = _make_workspace()
        try:
            (mcps_dir / "builtin-srv.builtin.json").write_text(
                json.dumps({"command": "uv"}), encoding="utf-8"
            )
            (mcps_dir / "custom-srv.json").write_text(
                json.dumps({"command": "node"}), encoding="utf-8"
            )
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_list

            items = mcp_list()
            names = {i["name"]: i["source"] for i in items}
            assert names["builtin-srv"] == "Built-in"
            assert names["custom-srv"] == "Custom"
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)


@pytest.mark.unit
class TestMcpAdd:
    def test_creates_definition_file(self):
        path, _mcps_dir = _make_workspace()
        try:
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_add

            result = mcp_add("my-server", config={"command": "test"})
            assert result.exists()
            content = json.loads(result.read_text(encoding="utf-8"))
            assert content["command"] == "test"
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_created_file_stays_within_mcps_dir(self):
        """Security invariant: the written file must be inside mcps_dir."""
        path, mcps_dir = _make_workspace()
        try:
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_add

            result = mcp_add("legit-server", config={"command": "test"})
            assert result.resolve().is_relative_to(mcps_dir.resolve())
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_raises_on_existing_without_force(self):
        path, mcps_dir = _make_workspace()
        try:
            (mcps_dir / "exists.json").write_text("{}", encoding="utf-8")
            _init_context(path)
            from vaultspec_core.core.exceptions import ResourceExistsError
            from vaultspec_core.core.mcps import mcp_add

            with pytest.raises(ResourceExistsError):
                mcp_add("exists")
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_overwrites_with_force(self):
        path, mcps_dir = _make_workspace()
        try:
            (mcps_dir / "exists.json").write_text("{}", encoding="utf-8")
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_add

            result = mcp_add("exists", config={"command": "new"}, force=True)
            content = json.loads(result.read_text(encoding="utf-8"))
            assert content["command"] == "new"
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_rejects_path_traversal(self):
        path, _mcps_dir = _make_workspace()
        try:
            _init_context(path)
            from vaultspec_core.core.exceptions import VaultSpecError
            from vaultspec_core.core.mcps import mcp_add

            with pytest.raises(VaultSpecError, match="Invalid"):
                mcp_add("../evil")
            with pytest.raises(VaultSpecError, match="Invalid"):
                mcp_add("foo/../bar")
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_rejects_empty_name(self):
        path, _mcps_dir = _make_workspace()
        try:
            _init_context(path)
            from vaultspec_core.core.exceptions import VaultSpecError
            from vaultspec_core.core.mcps import mcp_add

            with pytest.raises(VaultSpecError, match="empty"):
                mcp_add("")
            with pytest.raises(VaultSpecError, match="empty"):
                mcp_add("   ")
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_rejects_builtin_suffix(self):
        path, _mcps_dir = _make_workspace()
        try:
            _init_context(path)
            from vaultspec_core.core.exceptions import VaultSpecError
            from vaultspec_core.core.mcps import mcp_add

            with pytest.raises(VaultSpecError, match="builtin"):
                mcp_add("fake.builtin")
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_rejects_non_dict_config(self):
        path, _mcps_dir = _make_workspace()
        try:
            _init_context(path)
            from vaultspec_core.core.exceptions import VaultSpecError
            from vaultspec_core.core.mcps import mcp_add

            with pytest.raises(VaultSpecError, match="dict"):
                mcp_add("srv", config=[1, 2, 3])  # ty: ignore[invalid-argument-type]
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)


@pytest.mark.unit
class TestMcpRemove:
    def test_removes_json_file(self):
        path, mcps_dir = _make_workspace()
        try:
            target_file = mcps_dir / "removable.json"
            target_file.write_text("{}", encoding="utf-8")
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_remove

            result = mcp_remove("removable")
            assert result == target_file
            assert not target_file.exists()
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_removes_builtin_file(self):
        path, mcps_dir = _make_workspace()
        try:
            target_file = mcps_dir / "removable.builtin.json"
            target_file.write_text("{}", encoding="utf-8")
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_remove

            mcp_remove("removable")
            assert not target_file.exists()
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_custom_removed_before_builtin(self):
        """When both exist, custom .json is removed first (revert semantics)."""
        path, mcps_dir = _make_workspace()
        try:
            builtin = mcps_dir / "srv.builtin.json"
            custom = mcps_dir / "srv.json"
            builtin.write_text(json.dumps({"command": "old"}), encoding="utf-8")
            custom.write_text(json.dumps({"command": "new"}), encoding="utf-8")
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_remove

            mcp_remove("srv")
            assert not custom.exists(), "Custom .json should be removed first"
            assert builtin.exists(), "Builtin should survive first removal"
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_removed_file_was_within_mcps_dir(self):
        """Security invariant: only files inside mcps_dir can be removed."""
        path, mcps_dir = _make_workspace()
        try:
            target = mcps_dir / "safe.json"
            target.write_text("{}", encoding="utf-8")
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_remove

            result = mcp_remove("safe")
            assert result.resolve().is_relative_to(mcps_dir.resolve())
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_rejects_traversal_in_remove(self):
        path, _mcps_dir = _make_workspace()
        try:
            _init_context(path)
            from vaultspec_core.core.exceptions import VaultSpecError
            from vaultspec_core.core.mcps import mcp_remove

            with pytest.raises(VaultSpecError, match="Invalid"):
                mcp_remove("../escape")
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_rejects_empty_name_in_remove(self):
        path, _mcps_dir = _make_workspace()
        try:
            _init_context(path)
            from vaultspec_core.core.exceptions import VaultSpecError
            from vaultspec_core.core.mcps import mcp_remove

            with pytest.raises(VaultSpecError, match="empty"):
                mcp_remove("")
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_raises_when_not_found(self):
        path, _mcps_dir = _make_workspace()
        try:
            _init_context(path)
            from vaultspec_core.core.exceptions import ResourceNotFoundError
            from vaultspec_core.core.mcps import mcp_remove

            with pytest.raises(ResourceNotFoundError):
                mcp_remove("nonexistent")
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)


@pytest.mark.unit
class TestMcpSync:
    def test_creates_mcp_json_from_scratch(self):
        path, mcps_dir = _make_workspace()
        try:
            config = {"command": "uv", "args": ["run", "test"]}
            (mcps_dir / "test-srv.builtin.json").write_text(
                json.dumps(config), encoding="utf-8"
            )
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_sync

            result = mcp_sync()
            assert result.added == 1
            assert result.skipped == 0

            mcp_json = json.loads((path / ".mcp.json").read_text(encoding="utf-8"))
            assert mcp_json["mcpServers"]["test-srv"] == config
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_idempotent_sync(self):
        path, mcps_dir = _make_workspace()
        try:
            config = {"command": "uv", "args": ["run", "test"]}
            (mcps_dir / "test-srv.builtin.json").write_text(
                json.dumps(config), encoding="utf-8"
            )
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_sync

            mcp_sync()
            result = mcp_sync()
            assert result.added == 0
            # A re-sync of an identical entry is `unchanged`, not `skipped`
            # (cli-sync-vocabulary ADR).
            assert result.unchanged == 1
            assert result.skipped == 0
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_sync_records_canonical_action_strings(self):
        """Regression: mcp_sync items must use the canonical action
        vocabulary (``[ADD]``/``[UPDATE]``/``[UNCHANGED]``) so the shared
        outcome renderer classifies them correctly. Bare words like
        "added" silently fell through to the wrong outcome."""
        path, mcps_dir = _make_workspace()
        try:
            config = {"command": "uv", "args": ["run", "test"]}
            (mcps_dir / "srv.builtin.json").write_text(
                json.dumps(config), encoding="utf-8"
            )
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_sync

            added = mcp_sync()
            assert ("srv", "[ADD]") in added.items
            unchanged = mcp_sync()
            assert ("srv", "[UNCHANGED]") in unchanged.items
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_preserves_user_entries(self):
        path, mcps_dir = _make_workspace()
        try:
            (mcps_dir / "managed.builtin.json").write_text(
                json.dumps({"command": "uv"}), encoding="utf-8"
            )
            # Pre-populate .mcp.json with a user entry
            user_config = {
                "mcpServers": {"user-server": {"command": "custom", "args": []}}
            }
            (path / ".mcp.json").write_text(json.dumps(user_config), encoding="utf-8")
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_sync

            result = mcp_sync()
            assert result.added == 1

            mcp_json = json.loads((path / ".mcp.json").read_text(encoding="utf-8"))
            assert "user-server" in mcp_json["mcpServers"]
            assert "managed" in mcp_json["mcpServers"]
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_warns_on_diff_without_force(self):
        path, mcps_dir = _make_workspace()
        try:
            (mcps_dir / "srv.builtin.json").write_text(
                json.dumps({"command": "new"}), encoding="utf-8"
            )
            existing = {"mcpServers": {"srv": {"command": "old"}}}
            (path / ".mcp.json").write_text(json.dumps(existing), encoding="utf-8")
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_sync

            result = mcp_sync(force=False)
            assert result.skipped == 1
            assert result.updated == 0
            assert any("--force" in w for w in result.warnings)
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_force_overwrites_diff(self):
        path, mcps_dir = _make_workspace()
        try:
            new_config = {"command": "new"}
            (mcps_dir / "srv.builtin.json").write_text(
                json.dumps(new_config), encoding="utf-8"
            )
            existing = {"mcpServers": {"srv": {"command": "old"}}}
            (path / ".mcp.json").write_text(json.dumps(existing), encoding="utf-8")
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_sync

            result = mcp_sync(force=True)
            assert result.updated == 1

            mcp_json = json.loads((path / ".mcp.json").read_text(encoding="utf-8"))
            assert mcp_json["mcpServers"]["srv"] == new_config
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_dry_run_does_not_write(self):
        path, mcps_dir = _make_workspace()
        try:
            (mcps_dir / "srv.builtin.json").write_text(
                json.dumps({"command": "uv"}), encoding="utf-8"
            )
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_sync

            result = mcp_sync(dry_run=True)
            assert result.added == 1
            assert not (path / ".mcp.json").exists()
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)


@pytest.mark.unit
class TestMcpUninstall:
    def test_removes_managed_entries(self):
        path, mcps_dir = _make_workspace()
        try:
            (mcps_dir / "managed.builtin.json").write_text(
                json.dumps({"command": "uv"}), encoding="utf-8"
            )
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_sync, mcp_uninstall

            mcp_sync()
            mcp_data = json.loads((path / ".mcp.json").read_text(encoding="utf-8"))
            mcp_data["mcpServers"]["user"] = {"command": "custom"}
            (path / ".mcp.json").write_text(json.dumps(mcp_data), encoding="utf-8")

            removed = mcp_uninstall(path)
            assert removed.pruned == 1
            assert ("managed", "[DELETE]") in removed.items

            remaining = json.loads((path / ".mcp.json").read_text(encoding="utf-8"))
            assert "managed" not in remaining["mcpServers"]
            assert "user" in remaining["mcpServers"]
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_deletes_file_when_empty(self):
        path, mcps_dir = _make_workspace()
        try:
            (mcps_dir / "only.builtin.json").write_text(
                json.dumps({"command": "uv"}), encoding="utf-8"
            )
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_sync, mcp_uninstall

            mcp_sync()
            mcp_uninstall(path)
            assert not (path / ".mcp.json").exists()
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_unowned_entry_survives_without_registry_or_ownership(self):
        path = PROJECT_ROOT / ".pytest-tmp" / f"mcps-uninstall-{uuid4().hex}"
        path.mkdir(parents=True, exist_ok=True)
        try:
            mcp_data = {"mcpServers": {"vaultspec-core": {"command": "uv"}}}
            (path / ".mcp.json").write_text(json.dumps(mcp_data), encoding="utf-8")
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_uninstall

            removed = mcp_uninstall(path)
            assert removed.pruned == 0
            remaining = json.loads((path / ".mcp.json").read_text(encoding="utf-8"))
            assert "vaultspec-core" in remaining["mcpServers"]
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)


@pytest.mark.unit
class TestUninstallRemovesCustomMcps:
    def test_full_uninstall_removes_custom_mcp_entries(self):
        """Regression: uninstall must read registry BEFORE deleting .vaultspec/.

        If .vaultspec/ is deleted first, collect_mcp_servers() returns empty
        and only the hardcoded 'vaultspec-core' fallback is cleaned up,
        leaving custom entries behind.
        """
        path = PROJECT_ROOT / ".pytest-tmp" / f"mcps-uninstall-full-{uuid4().hex}"
        try:
            path.mkdir(parents=True, exist_ok=True)
            reset_config()

            from vaultspec_core.core.commands import install_run

            install_run(
                path=path, provider="all", upgrade=False, dry_run=False, force=False
            )

            # Add a custom MCP definition post-install
            mcps_dir = path / ".vaultspec" / "mcps"
            (mcps_dir / "custom-rag.json").write_text(
                json.dumps({"command": "uv", "args": ["run", "rag-server"]}),
                encoding="utf-8",
            )

            # Sync so the custom entry lands in .mcp.json
            from vaultspec_core.core.mcps import mcp_sync

            mcp_sync(force=True)

            mcp_before = json.loads((path / ".mcp.json").read_text(encoding="utf-8"))
            assert "custom-rag" in mcp_before["mcpServers"]
            assert "vaultspec-core" in mcp_before["mcpServers"]

            # Full uninstall
            from vaultspec_core.core.commands import uninstall_run

            uninstall_run(path, provider="all", force=True)

            # Both managed entries should be gone
            if (path / ".mcp.json").exists():
                mcp_after = json.loads((path / ".mcp.json").read_text(encoding="utf-8"))
                servers = mcp_after.get("mcpServers", {})
                assert "custom-rag" not in servers, (
                    "Custom MCP entry survived uninstall"
                )
                assert "vaultspec-core" not in servers
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)


@pytest.mark.unit
class TestMcpSyncPrune:
    """Reconciling sync — prune orphans on companion uninstall."""

    def test_prune_removes_orphan_managed_entry(self):
        path, mcps_dir = _make_workspace()
        try:
            (mcps_dir / "ephemeral.builtin.json").write_text(
                json.dumps({"command": "uv", "args": ["run", "ephemeral"]}),
                encoding="utf-8",
            )
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_sync

            # First sync: install
            result = mcp_sync()
            assert result.added == 1
            data = json.loads((path / ".mcp.json").read_text(encoding="utf-8"))
            assert "ephemeral" in data["mcpServers"]
            assert _owned_names(path) == {"ephemeral"}
            assert "_vaultspecManaged" not in data

            # Delete the source file to simulate companion uninstall
            (mcps_dir / "ephemeral.builtin.json").unlink()

            # Second sync with prune=True: should remove the orphan
            result = mcp_sync(prune=True)
            assert result.pruned == 1
            assert ("ephemeral", "[DELETE]") in result.items

            # File should be removed entirely (no managed, no servers)
            assert not (path / ".mcp.json").exists()
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_prune_default_false_leaves_orphans(self):
        path, mcps_dir = _make_workspace()
        try:
            (mcps_dir / "stay.builtin.json").write_text(
                json.dumps({"command": "uv"}), encoding="utf-8"
            )
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_sync

            mcp_sync()
            (mcps_dir / "stay.builtin.json").unlink()

            # Default prune=False: orphan stays put
            result = mcp_sync()
            assert result.pruned == 0
            data = json.loads((path / ".mcp.json").read_text(encoding="utf-8"))
            assert "stay" in data["mcpServers"]
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_prune_preserves_user_added_entries(self):
        path, mcps_dir = _make_workspace()
        try:
            (mcps_dir / "managed.builtin.json").write_text(
                json.dumps({"command": "uv"}), encoding="utf-8"
            )
            user_data = {"mcpServers": {"my-tool": {"command": "custom", "args": []}}}
            (path / ".mcp.json").write_text(json.dumps(user_data), encoding="utf-8")
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_sync

            mcp_sync()
            (mcps_dir / "managed.builtin.json").unlink()

            result = mcp_sync(prune=True)
            assert result.pruned == 1

            data = json.loads((path / ".mcp.json").read_text(encoding="utf-8"))
            # User entry survives the orphan prune
            assert "my-tool" in data["mcpServers"]
            assert "managed" not in data["mcpServers"]
            # Host schemas never carry Vaultspec ownership metadata.
            assert "_vaultspecManaged" not in data
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_user_added_with_shared_name_never_taken_over(self):
        """A user-added entry must not be taken over just because a
        source file appears with the same name later. The strict
        ownership rule: only entries created by mcp_sync itself
        enter the managed set.
        """
        path, mcps_dir = _make_workspace()
        try:
            # User pre-registers an entry with an empty legacy host marker, so
            # migration has no affirmative ownership evidence.
            existing = {
                "mcpServers": {"shared": {"command": "user-binary"}},
                "_vaultspecManaged": [],
            }
            (path / ".mcp.json").write_text(json.dumps(existing), encoding="utf-8")

            # Source file with the same name appears
            (mcps_dir / "shared.builtin.json").write_text(
                json.dumps({"command": "vaultspec-binary"}), encoding="utf-8"
            )

            _init_context(path)
            from vaultspec_core.core.mcps import mcp_sync

            result = mcp_sync()
            # Should NOT add (entry already there) and NOT enter managed
            assert result.added == 0
            assert result.skipped == 1
            assert any("externally managed" in w for w in result.warnings), (
                result.warnings
            )

            data = json.loads((path / ".mcp.json").read_text(encoding="utf-8"))
            # User's entry preserved unchanged
            assert data["mcpServers"]["shared"]["command"] == "user-binary"
            # Source name did NOT get added to external ownership state.
            ownership_path = path / ".vaultspec" / "mcp-ownership.json"
            assert not ownership_path.exists()
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_name_intersection_without_legacy_evidence_remains_external(self):
        """Names alone never transfer ownership during legacy migration."""
        path, mcps_dir = _make_workspace()
        try:
            existing = {
                "mcpServers": {
                    "alpha": {"command": "old-a"},
                    "beta": {"command": "old-b"},
                }
            }
            (path / ".mcp.json").write_text(json.dumps(existing), encoding="utf-8")
            (mcps_dir / "alpha.builtin.json").write_text(
                json.dumps({"command": "new-a"}), encoding="utf-8"
            )
            (mcps_dir / "beta.builtin.json").write_text(
                json.dumps({"command": "new-b"}), encoding="utf-8"
            )

            _init_context(path)
            from vaultspec_core.core.mcps import mcp_sync

            result = mcp_sync()
            assert result.skipped == 2
            assert all("externally managed" in warning for warning in result.warnings)
            assert not (path / ".vaultspec" / "mcp-ownership.json").exists()
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_legacy_migration_treats_pre_existing_as_managed(self):
        """Workspaces created before ownership tracking shipped have
        an affirmative `_vaultspecManaged` host marker. Migration accepts that
        marker once, moves ownership into the external sidecar, and removes the
        legacy field from host configuration.
        """
        path, mcps_dir = _make_workspace()
        try:
            # An affirmative legacy marker is accepted once as ownership evidence.
            existing = {
                "mcpServers": {"legacy": {"command": "old"}},
                "_vaultspecManaged": ["legacy"],
            }
            (path / ".mcp.json").write_text(json.dumps(existing), encoding="utf-8")
            (mcps_dir / "legacy.builtin.json").write_text(
                json.dumps({"command": "new"}), encoding="utf-8"
            )

            _init_context(path)
            from vaultspec_core.core.mcps import mcp_sync

            # First sync after upgrade — legacy migration kicks in
            result = mcp_sync(force=True)
            assert result.updated == 1

            data = json.loads((path / ".mcp.json").read_text(encoding="utf-8"))
            assert data["mcpServers"]["legacy"]["command"] == "new"
            assert "_vaultspecManaged" not in data
            assert _owned_names(path) == {"legacy"}
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_managed_key_persisted_across_syncs(self):
        path, mcps_dir = _make_workspace()
        try:
            (mcps_dir / "alpha.builtin.json").write_text(
                json.dumps({"command": "uv"}), encoding="utf-8"
            )
            (mcps_dir / "beta.builtin.json").write_text(
                json.dumps({"command": "uv"}), encoding="utf-8"
            )
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_sync

            mcp_sync()
            data = json.loads((path / ".mcp.json").read_text(encoding="utf-8"))
            assert "_vaultspecManaged" not in data
            assert _owned_names(path) == {"alpha", "beta"}

            # Re-sync: managed set should remain identical
            mcp_sync()
            data = json.loads((path / ".mcp.json").read_text(encoding="utf-8"))
            assert "_vaultspecManaged" not in data
            assert _owned_names(path) == {"alpha", "beta"}
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_prune_skips_entries_whose_source_failed_to_parse(self):
        """Critical regression: a managed source file that exists but
        currently fails JSON parsing must NOT be treated as deleted by
        the prune loop. Otherwise a single typo + ``sync --force``
        would silently destroy the corresponding ``.mcp.json`` entry,
        which is destructive and very hard to recover from.

        The fix: prune is gated on physical absence of the source
        file, not on whether it parsed successfully this run.
        """
        path, mcps_dir = _make_workspace()
        try:
            (mcps_dir / "fragile.builtin.json").write_text(
                json.dumps({"command": "uv", "args": ["run", "fragile"]}),
                encoding="utf-8",
            )
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_sync

            # First sync: install — entry takes ownership.
            mcp_sync()
            data = json.loads((path / ".mcp.json").read_text(encoding="utf-8"))
            assert "fragile" in data["mcpServers"]
            assert _owned_names(path) == {"fragile"}

            # Corrupt the source: file still exists but is invalid JSON.
            (mcps_dir / "fragile.builtin.json").write_text(
                "{not valid json", encoding="utf-8"
            )

            # Sync with prune=True. The entry MUST survive because the
            # source file is still present on disk — only the parser
            # is failing. A parse warning should be reported.
            result = mcp_sync(prune=True)
            assert result.pruned == 0, (
                "Entry was destructively pruned despite source file "
                "being present (parse failure should not trigger prune)"
            )
            assert any("fragile" in w for w in result.warnings)

            data = json.loads((path / ".mcp.json").read_text(encoding="utf-8"))
            assert "fragile" in data["mcpServers"]
            assert _owned_names(path) == {"fragile"}

            # Now genuinely delete the source — prune SHOULD remove it.
            (mcps_dir / "fragile.builtin.json").unlink()
            result = mcp_sync(prune=True)
            assert result.pruned == 1
            assert not (path / ".mcp.json").exists()
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_prune_preserves_user_top_level_keys(self):
        """Regression: when pruning empties ``mcpServers`` and ownership, the
        file must still survive if the user added other top-level keys.
        Only when the file holds nothing but an empty ``mcpServers``
        dict may it be unlinked.
        """
        path, mcps_dir = _make_workspace()
        try:
            (mcps_dir / "ephemeral.builtin.json").write_text(
                json.dumps({"command": "uv"}), encoding="utf-8"
            )
            _init_context(path)
            from vaultspec_core.core.mcps import mcp_sync

            # First sync creates host enrollment plus external ownership.
            mcp_sync()

            # User manually adds a custom top-level key (e.g. inputs).
            data = json.loads((path / ".mcp.json").read_text(encoding="utf-8"))
            data["inputs"] = [{"type": "promptString", "id": "api-key"}]
            (path / ".mcp.json").write_text(json.dumps(data), encoding="utf-8")

            # Delete the source and prune.
            (mcps_dir / "ephemeral.builtin.json").unlink()
            mcp_sync(prune=True)

            # File MUST still exist with the user's custom key intact.
            assert (path / ".mcp.json").exists()
            data = json.loads((path / ".mcp.json").read_text(encoding="utf-8"))
            assert data["inputs"] == [{"type": "promptString", "id": "api-key"}]
            assert data.get("mcpServers", {}) == {}
            assert "_vaultspecManaged" not in data
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_round_trip_install_uninstall_via_sync_provider(self):
        """End-to-end: install seeds an entry via sync_provider, then
        deleting the source and re-running sync_provider with force=True
        prunes the orphan cleanly. This is the canonical companion
        install/uninstall flow rag relies on.
        """
        path = PROJECT_ROOT / ".pytest-tmp" / f"mcp-roundtrip-{uuid4().hex}"
        try:
            path.mkdir(parents=True, exist_ok=True)
            reset_config()

            from vaultspec_core.core.commands import (
                install_run,
                sync_provider,
            )

            install_run(
                path=path,
                provider="all",
                upgrade=False,
                dry_run=False,
                force=False,
            )

            # Simulate a companion package dropping a source file
            mcps_dir = path / ".vaultspec" / "mcps"
            (mcps_dir / "companion.builtin.json").write_text(
                json.dumps({"command": "uv", "args": ["run", "companion"]}),
                encoding="utf-8",
            )

            # Companion install: sync to propagate
            sync_provider("all", force=False)
            data = json.loads((path / ".mcp.json").read_text(encoding="utf-8"))
            assert "companion" in data["mcpServers"]
            assert "companion" in _owned_names(path)
            assert "_vaultspecManaged" not in data

            # Companion uninstall: delete source + sync
            (mcps_dir / "companion.builtin.json").unlink()
            sync_provider("all", force=True)

            data = json.loads((path / ".mcp.json").read_text(encoding="utf-8"))
            assert "companion" not in data["mcpServers"]
            assert "companion" not in _owned_names(path)
            # vaultspec-core's own MCP entry is preserved
            assert "vaultspec-core" in data["mcpServers"]
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)


@pytest.mark.unit
class TestInstallSeedsMcps:
    def test_install_creates_mcp_json_from_registry(self):
        path = PROJECT_ROOT / ".pytest-tmp" / f"mcps-install-{uuid4().hex}"
        try:
            path.mkdir(parents=True, exist_ok=True)
            reset_config()

            from vaultspec_core.core.commands import install_run

            install_run(
                path=path, provider="all", upgrade=False, dry_run=False, force=False
            )

            mcp_json = json.loads((path / ".mcp.json").read_text(encoding="utf-8"))
            assert "vaultspec-core" in mcp_json["mcpServers"]
            server = mcp_json["mcpServers"]["vaultspec-core"]
            assert server["command"] == "uvx"
            expected_args = [
                "--from",
                "vaultspec-core",
                "python",
                "-m",
                "vaultspec_core.mcp_server.app",
            ]
            assert server["args"] == expected_args
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)


def _native_servers(path, provider: str) -> dict[str, dict[str, object]]:
    """Read one real project-scope provider target through its native schema."""
    if provider == "claude":
        raw = json.loads((path / ".mcp.json").read_text(encoding="utf-8"))
        return raw["mcpServers"]
    if provider == "antigravity":
        raw = json.loads(
            (path / ".agents" / "mcp_config.json").read_text(encoding="utf-8")
        )
        return raw["mcpServers"]
    raw = tomllib.loads((path / ".codex" / "config.toml").read_text(encoding="utf-8"))
    return raw["mcp_servers"]


@pytest.mark.unit
class TestProviderNativeMcpEnrollment:
    def test_explicit_public_seam_writes_all_native_targets(self):
        path, mcps_dir = _make_workspace()
        try:
            definition = {
                "command": "@@VAULTSPEC_INSTALL_MODE_COMMAND@@",
                "args": ["@@VAULTSPEC_INSTALL_MODE_ARGS@@"],
                "_vaultspec_mode_package": "vaultspec-rag",
                "_vaultspec_mode_module": "vaultspec_rag.mcp_server.app",
                "_vaultspec_mode_tool_spec": "vaultspec-rag[mcp]",
            }
            (mcps_dir / "vaultspec-rag.builtin.json").write_text(
                json.dumps(definition), encoding="utf-8"
            )
            reset_config()

            from vaultspec_core.core.enums import InstallMode, Tool
            from vaultspec_core.core.mcps import mcp_status, mcp_sync
            from vaultspec_core.core.workspace_mode import (
                PackageDeclaration,
                write_package_declaration,
            )

            enrolled = {Tool.CLAUDE, Tool.ANTIGRAVITY, Tool.CODEX}
            write_package_declaration(
                path,
                "vaultspec-rag",
                PackageDeclaration(install_mode=InstallMode.TOOL),
            )
            result = mcp_sync(
                target_dir=path,
                enrolled=enrolled,
                mode=InstallMode.TOOL,
            )

            assert result.added == 3
            assert set(result.per_tool) == {"claude", "antigravity", "codex"}
            for provider in result.per_tool:
                server = _native_servers(path, provider)["vaultspec-rag"]
                assert server["command"] == "uvx"
                assert server["args"] == [
                    "--from",
                    "vaultspec-rag[mcp]",
                    "python",
                    "-m",
                    "vaultspec_rag.mcp_server.app",
                ]
                assert all(not key.startswith("_vaultspec_") for key in server)

            ownership = json.loads(
                (path / ".vaultspec" / "mcp-ownership.json").read_text(encoding="utf-8")
            )
            assert set(ownership["targets"]) == {
                "claude:project",
                "antigravity:project",
                "codex:project",
            }
            assert "_vaultspecManaged" not in json.loads(
                (path / ".mcp.json").read_text(encoding="utf-8")
            )

            status = mcp_status(target_dir=path, enrolled=enrolled)
            assert status["status"] == "ok"
            assert all(
                provider_status["status"] == "ok"
                for provider_status in status["providers"].values()
            )
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_dry_run_is_byte_stable_and_creates_no_locks(self):
        path, mcps_dir = _make_workspace()
        try:
            (mcps_dir / "dry.builtin.json").write_text(
                json.dumps({"command": "dry-server"}), encoding="utf-8"
            )
            before = {
                file.relative_to(path): file.read_bytes()
                for file in path.rglob("*")
                if file.is_file()
            }
            reset_config()

            from vaultspec_core.core.enums import InstallMode, Tool
            from vaultspec_core.core.mcps import mcp_sync

            result = mcp_sync(
                target_dir=path,
                enrolled={Tool.CLAUDE, Tool.ANTIGRAVITY, Tool.CODEX},
                mode=InstallMode.TOOL,
                dry_run=True,
            )
            after = {
                file.relative_to(path): file.read_bytes()
                for file in path.rglob("*")
                if file.is_file()
            }

            assert result.added == 3
            assert after == before
            assert not list(path.rglob("*.lock"))
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_selective_uninstall_preserves_core_and_ownership_fingerprints(self):
        path, mcps_dir = _make_workspace()
        try:
            for name in ("vaultspec-core", "vaultspec-rag"):
                (mcps_dir / f"{name}.builtin.json").write_text(
                    json.dumps({"command": name}), encoding="utf-8"
                )
            reset_config()

            from vaultspec_core.core.enums import InstallMode, Tool
            from vaultspec_core.core.mcps import mcp_sync, mcp_uninstall

            enrolled = {Tool.CLAUDE, Tool.ANTIGRAVITY, Tool.CODEX}
            mcp_sync(
                target_dir=path,
                enrolled=enrolled,
                mode=InstallMode.TOOL,
            )
            ownership_path = path / ".vaultspec" / "mcp-ownership.json"
            before = json.loads(ownership_path.read_text(encoding="utf-8"))
            core_fingerprints = {
                key: record["managed"]["vaultspec-core"]
                for key, record in before["targets"].items()
            }

            result = mcp_uninstall(
                path,
                enrolled=enrolled,
                names=frozenset({"vaultspec-rag"}),
            )

            assert result.pruned == 3
            for provider in ("claude", "antigravity", "codex"):
                servers = _native_servers(path, provider)
                assert "vaultspec-core" in servers
                assert "vaultspec-rag" not in servers
            after = json.loads(ownership_path.read_text(encoding="utf-8"))
            assert {
                key: record["managed"]["vaultspec-core"]
                for key, record in after["targets"].items()
            } == core_fingerprints
            assert all(
                "vaultspec-rag" not in record["managed"]
                for record in after["targets"].values()
            )
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_codex_drift_is_independent_and_force_repairs_only_codex(self):
        path, mcps_dir = _make_workspace()
        try:
            (mcps_dir / "server.builtin.json").write_text(
                json.dumps({"command": "expected"}), encoding="utf-8"
            )
            reset_config()

            from vaultspec_core.core.enums import InstallMode, Tool
            from vaultspec_core.core.mcps import mcp_status, mcp_sync

            enrolled = {Tool.CLAUDE, Tool.CODEX}
            mcp_sync(
                target_dir=path,
                enrolled=enrolled,
                mode=InstallMode.TOOL,
            )
            claude_before = (path / ".mcp.json").read_bytes()
            codex_path = path / ".codex" / "config.toml"
            codex_path.write_text(
                codex_path.read_text(encoding="utf-8").replace(
                    'command = "expected"', 'command = "drifted"'
                ),
                encoding="utf-8",
            )

            status = mcp_status(target_dir=path, enrolled=enrolled)
            assert status["providers"]["claude"]["status"] == "ok"
            assert status["providers"]["codex"]["drifted"] == ["server"]

            repaired = mcp_sync(
                target_dir=path,
                enrolled=enrolled,
                provider=Tool.CODEX,
                mode=InstallMode.TOOL,
                force=True,
            )
            assert repaired.updated == 1
            assert _native_servers(path, "codex")["server"]["command"] == "expected"
            assert (path / ".mcp.json").read_bytes() == claude_before
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)

    def test_codex_local_scope_fails_without_writing(self):
        path, mcps_dir = _make_workspace()
        try:
            (mcps_dir / "server.builtin.json").write_text(
                json.dumps({"command": "expected"}), encoding="utf-8"
            )
            reset_config()

            from vaultspec_core.core.enums import Tool
            from vaultspec_core.core.mcps import mcp_sync

            result = mcp_sync(
                target_dir=path,
                enrolled={Tool.CODEX},
                provider=Tool.CODEX,
                scope="local",
            )

            assert result.errored == 1
            assert any("distinct local MCP scope" in error for error in result.errors)
            assert not (path / ".codex" / "config.toml").exists()
            assert not (path / ".vaultspec" / "mcp-ownership.json").exists()
        finally:
            reset_config()
            shutil.rmtree(path, ignore_errors=True)
