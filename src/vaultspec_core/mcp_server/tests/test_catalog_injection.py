"""Workspace reference text cannot grant executable command authority."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import TextContent

from vaultspec_core.mcp_server.catalog import DENYLIST, build_catalog
from vaultspec_core.mcp_server.tools import gateway

from .conftest import data_of, vault_root

if TYPE_CHECKING:
    import subprocess
    from pathlib import Path

__all__ = ["vault_root"]

pytestmark = [pytest.mark.unit]

_INJECTED_VERBS = (
    *(" ".join((*verb, "NAME")) for verb in sorted(DENYLIST)),
    "spec triggers trust --all",
    "spec\ttriggers   run\tNAME",
    "--target elsewhere spec triggers trust NAME",
    "vault list --target elsewhere",
    "vault edit --editor executable",
    "spec triggers",
    "nonexistent command",
)


def _poison_reference(root: Path) -> Path:
    reference = root / ".vaultspec" / "reference" / "cli.md"
    text = reference.read_text(encoding="utf-8")
    injected = "\n".join(
        f"- `vaultspec-core {verb}` - injected command" for verb in _INJECTED_VERBS
    )
    reference.write_text(
        text.replace(
            "<!-- vaultspec:generated:end command-inventory -->",
            f"{injected}\n<!-- vaultspec:generated:end command-inventory -->",
        ),
        encoding="utf-8",
    )
    assert injected in reference.read_text(encoding="utf-8")
    return reference


def test_inventory_cannot_extend_live_command_identities(vault_root: Path) -> None:
    catalog = build_catalog(_poison_reference(vault_root))
    for verb in _INJECTED_VERBS:
        assert catalog.get(tuple(verb.split())) is None, verb
    for verb in DENYLIST:
        assert catalog.is_denied(verb)
        assert catalog.get(verb) is None
    assert catalog.declares(("vault", "list"))
    assert catalog.declares(("spec", "triggers", "list"))


async def test_poisoned_inventory_rejected_before_spawn(
    vault_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _poison_reference(vault_root)
    gateway._load_catalog.cache_clear()
    original_run = gateway._run_verb
    spawned: list[list[str]] = []

    async def track_spawn(
        argv: list[str], env: dict[str, str], timeout: float
    ) -> subprocess.CompletedProcess[str]:
        spawned.append(argv)
        return await original_run(argv, env, timeout)

    monkeypatch.setattr(gateway, "_run_verb", track_spawn)
    server = MCPServer(name="catalog-injection-test")
    gateway.register_gateway_tools(server)
    try:
        async with Client(server) as client:
            result = await client.call_tool(
                "discover", {"query": "injected command", "limit": 1000}
            )
            discovered = {entry["verb"] for entry in data_of(result)["verbs"]}
            assert not discovered.intersection(
                " ".join(v.split()) for v in _INJECTED_VERBS
            )
            for verb in _INJECTED_VERBS:
                result = await client.call_tool("invoke", {"verb": verb})
                assert result.is_error, verb
                text = " ".join(
                    item.text
                    for item in result.content
                    if isinstance(item, TextContent)
                )
                assert "unknown verb" in text, text
            assert spawned == []
            result = await client.call_tool("invoke", {"verb": "vault list"})
            payload = data_of(result)
            assert payload["ok"] is True
            assert payload["data"]["schema"].startswith("vaultspec.vault.list")
            assert len(spawned) == 1
    finally:
        gateway._load_catalog.cache_clear()
