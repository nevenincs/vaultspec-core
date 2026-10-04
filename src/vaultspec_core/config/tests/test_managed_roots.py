"""Managed roots must remain plain directories at validation and reuse."""

from __future__ import annotations

import os
import subprocess
from contextvars import ContextVar
from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.builtins import seed_builtins
from vaultspec_core.config import get_config, reset_config
from vaultspec_core.config.workspace import (
    LayoutMode,
    WorkspaceError,
    WorkspaceLayout,
    resolve_workspace,
    validate_managed_roots,
)
from vaultspec_core.core import types
from vaultspec_core.core.manifest import (
    ManifestData,
    read_manifest_data,
    write_manifest_data,
)
from vaultspec_core.core.revert import (
    get_snapshot_content,
    list_modified_builtins,
    prune_orphan_snapshots,
    snapshot_builtins,
)
from vaultspec_core.core.scaffold import scaffold_core
from vaultspec_core.core.workspace_mode import read_workspace_declaration
from vaultspec_core.vaultcore.hydration import (
    DocumentIdentity,
    create_vault_doc,
    get_template_path,
)
from vaultspec_core.vaultcore.models import DocType
from vaultspec_core.vaultcore.scanner import scan_vault

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    reset_config()
    fresh_context: ContextVar[types.WorkspaceContext] = ContextVar("managed_roots_test")
    monkeypatch.setattr(types, "workspace_ctx", fresh_context)
    try:
        yield
    finally:
        reset_config()


def _link(link: Path, destination: Path) -> None:
    try:
        link.symlink_to(destination, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Directory symlinks unavailable: {exc}")
    assert link.is_symlink()


@pytest.mark.parametrize("root_name", [".vaultspec", ".vault"])
@pytest.mark.parametrize("destination_kind", ["external", "internal", "missing"])
@pytest.mark.parametrize("discovery", ["explicit", "cwd", "git", "structural"])
def test_resolution_rejects_linked_roots(
    tmp_path: Path, root_name: str, destination_kind: str, discovery: str
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    if root_name != ".vaultspec":
        (workspace / ".vaultspec").mkdir()
    destination = (
        workspace / "redirect"
        if destination_kind == "internal"
        else tmp_path / "outside"
    )
    if destination_kind != "missing":
        destination.mkdir()
    _link(workspace / root_name, destination)
    if discovery == "git":
        (workspace / ".git").mkdir()
    with pytest.raises(WorkspaceError, match="redirected"):
        resolve_workspace(
            target_override=workspace if discovery == "explicit" else None,
            framework_root=workspace / ".vaultspec"
            if discovery == "structural"
            else None,
            cwd=workspace,
        )


@pytest.mark.parametrize("root_name", [".vaultspec", ".vault"])
def test_resolution_rejects_windows_junctions(tmp_path: Path, root_name: str) -> None:
    if os.name != "nt":
        pytest.skip("Windows junctions require Windows")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    if root_name != ".vaultspec":
        (workspace / ".vaultspec").mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = workspace / root_name
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
        check=True,
        capture_output=True,
        timeout=10,
    )
    assert link.is_junction()
    with pytest.raises(WorkspaceError, match="redirected"):
        resolve_workspace(target_override=workspace)


@pytest.mark.parametrize("name", ["../outside", "nested/../../outside"])
def test_framework_name_cannot_escape(tmp_path: Path, name: str) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (tmp_path / "outside").mkdir()
    with pytest.raises(WorkspaceError):
        resolve_workspace(target_override=workspace, framework_dir_name=name)


def test_explicit_source_is_checked_without_breaking_split_sync(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    source = tmp_path / "source"
    source.mkdir()
    framework = source / ".vaultspec"
    framework.mkdir()
    layout = resolve_workspace(target_override=target, framework_root=framework)
    context = types.init_paths(layout)
    assert types.get_context() is context
    framework.rmdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    _link(framework, outside)
    with pytest.raises(WorkspaceError, match="redirected"):
        types.get_context()


@pytest.mark.parametrize("root_name", [".vault", ".vaultspec"])
def test_cached_context_and_config_recheck_roots(
    tmp_path: Path, root_name: str
) -> None:
    (tmp_path / ".vaultspec").mkdir()
    (tmp_path / ".vault").mkdir()
    types.init_paths(resolve_workspace(target_override=tmp_path))
    get_config(root=tmp_path)
    root = tmp_path / root_name
    root.rmdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    _link(root, outside)
    with pytest.raises(WorkspaceError, match="redirected"):
        types.get_context()
    with pytest.raises(WorkspaceError, match="redirected"):
        get_config(root=tmp_path)


def test_manual_layout_is_validated_before_initialization(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    _link(tmp_path / ".vaultspec", outside)
    layout = WorkspaceLayout(
        target_dir=tmp_path,
        vault_dir=tmp_path / ".vault",
        vaultspec_dir=tmp_path / ".vaultspec",
        mode=LayoutMode.EXPLICIT,
        git=None,
    )
    with pytest.raises(WorkspaceError, match="redirected"):
        types.init_paths(layout)


def test_replaced_context_target_is_rechecked(tmp_path: Path) -> None:
    (tmp_path / ".vaultspec").mkdir()
    context = types.init_paths(resolve_workspace(target_override=tmp_path))
    target = tmp_path / "destination"
    target.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    _link(target / ".vault", outside)
    types.set_context(replace(context, target_dir=target))
    with pytest.raises(WorkspaceError, match="redirected"):
        types.get_context()


def test_configured_roots_reject_linked_ancestors(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    _link(tmp_path / "nested", outside)
    for setting in ("docs_dir", "framework_dir"):
        for name in ("nested/managed", str(tmp_path / "nested" / "managed")):
            with pytest.raises(WorkspaceError, match="redirected"):
                get_config({setting: name}, root=tmp_path)


def test_explicit_external_vault_must_be_a_plain_directory(tmp_path: Path) -> None:
    target = tmp_path / "workspace"
    target.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    assert get_config({"docs_dir": str(external)}, root=target).docs_dir == str(
        external
    )
    external.rmdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    _link(external, outside)
    with pytest.raises(WorkspaceError, match="redirected"):
        get_config({"docs_dir": str(external)}, root=target)


def test_cached_custom_config_rechecks_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VAULTSPEC_DOCS_DIR", "nested/docs")
    custom = tmp_path / "nested" / "docs"
    custom.mkdir(parents=True)
    assert get_config(root=tmp_path).docs_dir == "nested/docs"
    custom.rmdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    _link(custom, outside)
    with pytest.raises(WorkspaceError, match="redirected"):
        get_config(root=tmp_path)


def test_direct_framework_sinks_preserve_external_bytes(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "providers.json"
    original = b'{"installed": ["claude"]}\n'
    sentinel.write_bytes(original)
    _link(workspace / ".vaultspec", outside)
    operations = (
        lambda: scaffold_core(workspace),
        lambda: seed_builtins(workspace / ".vaultspec", force=True),
        lambda: read_manifest_data(workspace),
        lambda: write_manifest_data(workspace, ManifestData()),
        lambda: read_workspace_declaration(workspace),
        lambda: snapshot_builtins(workspace / ".vaultspec"),
        lambda: prune_orphan_snapshots(workspace / ".vaultspec"),
        lambda: get_snapshot_content(workspace / ".vaultspec", "rules", "x.builtin.md"),
        lambda: list_modified_builtins(workspace / ".vaultspec"),
    )
    for operation in operations:
        with pytest.raises(WorkspaceError, match="redirected"):
            operation()
        assert sentinel.read_bytes() == original
        assert list(outside.iterdir()) == [sentinel]


def test_direct_scan_refuses_redirected_vault(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    _link(workspace / ".vault", outside)
    with pytest.raises(WorkspaceError, match="redirected"):
        list(scan_vault(workspace))


def test_explicit_template_source_cannot_be_linked(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    framework = source / ".vaultspec"
    _link(framework, outside)
    with pytest.raises(WorkspaceError, match="redirected"):
        get_template_path(tmp_path, DocType.ADR, content_root=framework)


@pytest.mark.parametrize("root_name", [".vault", ".vaultspec"])
def test_direct_creation_validates_its_destination_workspace(
    tmp_path: Path, root_name: str
) -> None:
    active = tmp_path / "active"
    (active / ".vaultspec").mkdir(parents=True)
    types.init_paths(resolve_workspace(target_override=active))
    target = tmp_path / "destination"
    target.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    if root_name == ".vault":
        seed_builtins(target / ".vaultspec")
    else:
        seed_builtins(outside)
    original = {
        path.relative_to(outside): path.read_bytes()
        for path in outside.rglob("*")
        if path.is_file()
    }
    _link(target / root_name, outside)
    with pytest.raises(WorkspaceError, match="redirected"):
        create_vault_doc(target, DocumentIdentity(DocType.ADR, "test", "2026-10-04"))
    assert {
        path.relative_to(outside): path.read_bytes()
        for path in outside.rglob("*")
        if path.is_file()
    } == original


def test_missing_roots_and_plain_custom_roots_remain_valid(tmp_path: Path) -> None:
    validate_managed_roots(tmp_path)
    config = get_config(
        {"docs_dir": "nested/docs", "framework_dir": "nested/fw"}, root=tmp_path
    )
    assert config.docs_dir == "nested/docs"
    (tmp_path / "nested" / "fw").mkdir(parents=True)
    layout = resolve_workspace(target_override=tmp_path, framework_dir_name="nested/fw")
    assert (
        types.init_paths(layout).rules_src_dir == tmp_path / "nested" / "fw" / "rules"
    )


def test_workspace_alias_is_allowed(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".vaultspec").mkdir()
    alias = tmp_path / "alias"
    _link(alias, workspace)
    layout = resolve_workspace(target_override=alias)
    assert layout.target_dir == workspace.resolve()
    validate_managed_roots(alias)


def test_non_directory_root_is_rejected(tmp_path: Path) -> None:
    (tmp_path / ".vault").write_text("obstacle", encoding="utf-8")
    with pytest.raises(WorkspaceError, match="not a directory"):
        validate_managed_roots(tmp_path)
