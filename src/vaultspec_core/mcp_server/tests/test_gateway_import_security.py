"""Real gateway children must use the server's trusted Python package."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from mcp import Client

from vaultspec_core.mcp_server.tools.gateway import _child_environment

from .conftest import data_of
from .test_gateway import _gateway_server

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


@pytest.mark.parametrize("source", ["cwd", "pythonpath", "pythonexecutable"])
async def test_invoke_ignores_shadow_packages(
    vault_root: Path, monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    """Workspace packages and Python startup overrides cannot execute in a child."""
    hostile_root = vault_root if source == "cwd" else vault_root / "python-injection"
    package = hostile_root / "vaultspec_core"
    package.mkdir(parents=True)
    marker = vault_root / "shadow-imported"
    attack = (
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed', encoding='utf-8')\n"
        "raise SystemExit(73)\n"
    )
    (package / "__init__.py").write_text(attack, encoding="utf-8")
    (package / "__main__.py").write_text(attack, encoding="utf-8")
    (hostile_root / "typer.py").write_text(attack, encoding="utf-8")
    monkeypatch.chdir(vault_root)
    monkeypatch.delenv("PYTHONPATH", raising=False)
    if source == "pythonpath":
        monkeypatch.setenv("PYTHONPATH", str(hostile_root))
    elif source == "pythonexecutable":
        # Python honors this launcher override even with -I; no exe is needed.
        monkeypatch.setenv("PYTHONEXECUTABLE", str(hostile_root / "python.exe"))
    if source != "cwd":
        # This runs at interpreter startup, before the CLI bootstrap can act.
        (hostile_root / "sitecustomize.py").write_text(attack, encoding="utf-8")

    async with Client(_gateway_server()) as client:
        result = await client.call_tool("invoke", {"verb": "vault list"})
        payload = data_of(result)

    assert not marker.exists(), "the child executed attacker-controlled Python"
    assert payload["ok"] is True, payload
    assert payload["data"]["schema"].startswith("vaultspec.vault.list")


async def test_gateway_environment_removes_python_import_overrides(
    vault_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Import overrides are scrubbed while product settings still reach the CLI."""
    overrides = {
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTHONUSERBASE",
        "PYTHONSTARTUP",
        "PYTHONEXECUTABLE",
        "__PYVENV_LAUNCHER__",
    }
    for name in overrides:
        monkeypatch.setenv(name, str(vault_root / "hostile-python"))
    monkeypatch.setenv("VAULTSPEC_MCP_GATEWAY_INVOCATION", "0")
    monkeypatch.setenv("VAULTSPEC_NO_HINTS", "1")
    env = _child_environment()
    assert not overrides & env.keys()
    assert env["VAULTSPEC_MCP_GATEWAY_INVOCATION"] == "1"
    assert env["VAULTSPEC_NO_HINTS"] == "1"

    async with Client(_gateway_server()) as client:
        result = await client.call_tool("invoke", {"verb": "vault list"})
    payload = data_of(result)
    assert payload["ok"] is True, payload
    assert payload["data"]["schema"].startswith("vaultspec.vault.list")


async def test_invoke_preserves_relative_cli_paths(
    vault_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A trusted startup directory must not change how CLI operands resolve."""
    monkeypatch.chdir(vault_root)
    async with Client(_gateway_server()) as client:
        result = await client.call_tool(
            "invoke",
            {
                "verb": "project context",
                "positionals": ["prepare the release"],
                "arguments": {"no-hosted": True, "limit": 1},
            },
        )
        first = data_of(result)
        assert first["ok"] is True, first
        previous = "previous result's (saved).json"
        (vault_root / previous).write_text(json.dumps(first["data"]), encoding="utf-8")
        result = await client.call_tool(
            "invoke",
            {
                "verb": "project context",
                "positionals": ["prepare the release"],
                "arguments": {
                    "no-hosted": True,
                    "limit": 1,
                    "previous": previous,
                },
            },
        )
    payload = data_of(result)
    assert payload["ok"] is True, payload
    assert payload["data"]["schema"] == "vaultspec.project.context.v1"
