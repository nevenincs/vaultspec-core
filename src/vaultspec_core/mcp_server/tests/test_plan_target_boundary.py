"""Plan targets must stay inside the MCP server's plan directory."""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

import pytest
from mcp import Client
from typer.testing import CliRunner

from vaultspec_core.cli import app
from vaultspec_core.mcp_server.plan_resolver import PlanResolutionError, resolve_plan

from .conftest import data_of, vault_root
from .test_gateway import _gateway_server

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["vault_root"]

pytestmark = pytest.mark.unit

_PLAN = (
    "---\n"
    "tags: ['#plan', '#boundary']\n"
    "date: '2026-10-04'\n"
    "modified: '2026-10-04'\n"
    "tier: L1\n"
    "---\n\n"
    "# `boundary` plan\n\n"
    "- [ ] `S01` - implement the boundary; `src/a.py`.\n"
)


def _write_plan(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_PLAN, encoding="utf-8")


@pytest.mark.parametrize("verb", ["vault plan step toggle", "vault plan check"])
@pytest.mark.parametrize(
    "form",
    [
        "absolute",
        "relative",
        "windows",
        "traversal",
        "dot_prefix",
        "dot_suffix",
        "windows_dot_suffix",
        "drive_relative",
        "unc",
    ],
)
async def test_gateway_rejects_path_targets(
    vault_root: Path, tmp_path: Path, verb: str, form: str
) -> None:
    external = tmp_path / "boundary.md"
    _write_plan(external)
    if verb.endswith("check"):
        external.write_text(_PLAN.replace("- [ ]", "- [X]"), encoding="utf-8")
    local = vault_root / ".vault" / "plan" / external.name
    _write_plan(local)
    target = {
        "absolute": str(external),
        "relative": ".vault/plan/boundary.md",
        "windows": r"C:\outside\boundary.md",
        "traversal": "../boundary.md",
        "dot_prefix": "./boundary.md",
        "dot_suffix": "boundary/.",
        "windows_dot_suffix": r"boundary\.",
        "drive_relative": "C:boundary.md",
        "unc": r"\\server\share\boundary.md",
    }[form]
    positionals = [target, "S01"] if verb.endswith("toggle") else [target]
    before = external.read_bytes(), local.read_bytes()
    async with Client(_gateway_server()) as client:
        result = await client.call_tool(
            "invoke",
            {
                "verb": verb,
                "positionals": positionals,
                "arguments": {} if verb.endswith("toggle") else {"fix": True},
            },
        )
    payload = data_of(result)
    assert payload["ok"] is False
    assert "stem or feature" in payload["error"]["stderr"]
    assert (external.read_bytes(), local.read_bytes()) == before
    assert not (tmp_path / ".vault").exists()


@pytest.mark.parametrize("target", ["boundary", "boundary.md", "#boundary"])
async def test_gateway_mutates_local_plan_by_identifier(
    vault_root: Path, target: str
) -> None:
    local = vault_root / ".vault" / "plan" / "boundary.md"
    _write_plan(local)
    async with Client(_gateway_server()) as client:
        result = await client.call_tool(
            "invoke",
            {"verb": "vault plan step toggle", "positionals": [target, "S01"]},
        )
    assert data_of(result)["ok"] is True
    assert "[x] `S01`" in local.read_text(encoding="utf-8")


def test_trusted_cli_keeps_external_literal_paths(
    vault_root: Path, tmp_path: Path
) -> None:
    external = tmp_path / "boundary.md"
    _write_plan(external)
    result = CliRunner().invoke(
        app,
        [
            "-t",
            str(vault_root),
            "vault",
            "plan",
            "step",
            "toggle",
            str(external),
            "S01",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "[x] `S01`" in external.read_text(encoding="utf-8")


@pytest.mark.parametrize("target", ["../boundary.md", r"C:\outside\boundary.md"])
def test_dedicated_resolver_rejects_path_aliases(vault_root: Path, target: str) -> None:
    _write_plan(vault_root / ".vault" / "plan" / "boundary.md")
    with pytest.raises(PlanResolutionError):
        resolve_plan(vault_root, target)


@pytest.mark.parametrize(
    "link_kind",
    [
        "file",
        "plan_directory",
        "vault_directory",
        pytest.param(
            "plan_junction",
            marks=pytest.mark.skipif(os.name != "nt", reason="Windows junction"),
        ),
    ],
)
@pytest.mark.parametrize("target", ["boundary", "#boundary"])
async def test_linked_targets_cannot_escape_plan_directory(
    vault_root: Path, tmp_path: Path, link_kind: str, target: str
) -> None:
    external = tmp_path / "outside" / "plan" / "boundary.md"
    _write_plan(external)
    vault = vault_root / ".vault"
    plan_dir = vault / "plan"
    if link_kind == "file":
        link, destination = plan_dir / "boundary.md", external
    elif link_kind in ("plan_directory", "plan_junction"):
        plan_dir.rename(vault / "original-plan")
        link, destination = plan_dir, external.parent
    else:
        vault.rename(vault_root / "original-vault")
        link, destination = vault, external.parent.parent
    if link_kind == "plan_junction":
        subprocess.run(
            ["cmd", "/d", "/c", "mklink", "/J", str(link), str(destination)],
            check=True,
            capture_output=True,
            timeout=30,
        )
        assert link.is_junction()
    else:
        link.symlink_to(destination, target_is_directory=link_kind != "file")
    before = external.read_bytes()
    with pytest.raises(PlanResolutionError):
        resolve_plan(vault_root, target)
    async with Client(_gateway_server()) as client:
        result = await client.call_tool(
            "invoke",
            {"verb": "vault plan step toggle", "positionals": [target, "S01"]},
        )
    # Workspace root validation may refuse a redirected .vault before dispatch.
    assert result.is_error or data_of(result)["ok"] is False
    assert external.read_bytes() == before


async def test_gateway_refuses_directory_named_like_a_plan(vault_root: Path) -> None:
    (vault_root / ".vault" / "plan" / "directory.md").mkdir()
    async with Client(_gateway_server()) as client:
        result = await client.call_tool(
            "invoke",
            {"verb": "vault plan step toggle", "positionals": ["directory", "S01"]},
        )
    payload = data_of(result)
    assert payload["ok"] is False
    assert "regular file" in payload["error"]["stderr"]
