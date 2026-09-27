"""Tests for the MCP ``log`` tool, the execution ledger writer.

Drives the real MCPServer over the in-memory client transport against a
:class:`WorkspaceFactory`-installed vault. The tool must land the same rows
the CLI verb lands, refuse the same malformed specs, and be absent from the
read-only surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from mcp import Client
from mcp.types import TextContent

from vaultspec_core.mcp_server.app import create_server
from vaultspec_core.vaultcore.exec_ledger import ledger_step_evidence

from .conftest import data_of

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

_PLAN_STEM = "2026-05-17-log-feat-plan"


def _plan(vault_root: Path) -> None:
    plan_dir = vault_root / ".vault" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / f"{_PLAN_STEM}.md").write_text(
        "---\ntags:\n  - '#plan'\n  - '#log-feat'\ndate: '2026-05-17'\n"
        "modified: '2026-05-17'\ntier: L1\nrelated: []\n---\n\n"
        "# `log-feat` plan\n\n## Description\n\nProse.\n\n## Steps\n\n"
        "- [ ] `S01` - first; `src/foo.py`.\n- [ ] `S02` - second; `src/bar.py`.\n\n"
        "## Parallelization\n\nProse.\n\n## Verification\n\nProse.\n",
        encoding="utf-8",
    )


async def _log(client: Client, **args: Any) -> Any:
    base = {"feature": "log-feat", "plan": _PLAN_STEM}
    return data_of(await client.call_tool("log", {**base, **args}))


def _ledger(vault_root: Path) -> Path:
    return (
        vault_root
        / ".vault"
        / "exec"
        / "2026-05-17-log-feat"
        / "2026-05-17-log-feat-ledger.md"
    )


async def test_log_creates_then_appends_the_ledger(vault_root: Path) -> None:
    _plan(vault_root)
    mcp = create_server()
    async with Client(mcp) as client:
        first = await _log(
            client,
            step="S01",
            rows=["M:src/foo.py", "A:tests/test_foo.py"],
            verify=["pytest -q=pass", "ruff check=fail"],
            by="vaultspec-low-executor",
        )
        second = await _log(
            client, step="S02", rows=["D:src/bar.py"], notes=["skipped docs"]
        )

    assert first["created"] is True and first["changed"] is True
    assert first["step"] == "S01" and first["rows"] == 5
    assert second["created"] is False and second["changed"] is True
    assert second["notes"] == 1
    text = _ledger(vault_root).read_text(encoding="utf-8")
    assert "- `S01` `M` `src/foo.py`" in text
    assert "- `S01` `verify:` `pytest -q` -> `pass`" in text
    assert "- `S01` `verify:` `ruff check` -> `fail`" in text
    assert "- `S01` `by:` `vaultspec-low-executor`" in text
    assert "- `S02` `D` `src/bar.py`" in text
    assert "- `S02` skipped docs" in text
    assert first["path"].replace("\\", "/").startswith(".vault/exec/")


async def test_relog_is_idempotent(vault_root: Path) -> None:
    _plan(vault_root)
    mcp = create_server()
    async with Client(mcp) as client:
        await _log(client, step="S01", rows=["M:src/foo.py"])
        before = _ledger(vault_root).read_text(encoding="utf-8")
        again = await _log(client, step="S01", rows=["M:src/foo.py"])

    assert again["changed"] is False
    assert _ledger(vault_root).read_text(encoding="utf-8") == before


@pytest.mark.parametrize(
    "results", [("pass", "fail", "pass"), ("fail", "pass", "fail")]
)
async def test_relogging_preserves_latest_verification(
    vault_root: Path, results: tuple[str, ...]
) -> None:
    _plan(vault_root)
    async with Client(create_server()) as client:
        for result in results:
            logged = await _log(client, step="S01", verify=[f"pytest={result}"])
            assert logged["changed"] is True
            body = _ledger(vault_root).read_text(encoding="utf-8")
            assert ledger_step_evidence(body)["S01"].verify == result

        retry = await _log(client, step="S01", verify=[f"pytest={results[-1]}"])
        assert retry["changed"] is False


@pytest.mark.parametrize(
    "args",
    [
        {"step": "S01", "rows": ["src/foo.py"]},
        {"step": "S01", "rows": ["X:src/foo.py"]},
        {"step": "S01", "verify": ["pytest=pass", "pytest=maybe"]},
        {"step": "S99", "rows": ["M:src/foo.py"]},
        {"step": "S01", "rows": ["M:src/foo.py"], "plan": "no-such-plan"},
    ],
)
async def test_malformed_requests_are_protocol_errors(
    vault_root: Path, args: dict[str, Any]
) -> None:
    _plan(vault_root)
    mcp = create_server()
    async with Client(mcp) as client:
        base = {"feature": "log-feat", "plan": _PLAN_STEM}
        result = await client.call_tool("log", {**base, **args})

    assert result.is_error
    assert not _ledger(vault_root).exists()


async def test_log_is_absent_from_the_read_only_surface(vault_root: Path) -> None:
    tools = await create_server(read_only=True).list_tools()

    assert "log" not in {tool.name for tool in tools}


async def test_the_text_summary_names_the_step_and_the_ledger(
    vault_root: Path,
) -> None:
    _plan(vault_root)
    mcp = create_server()
    async with Client(mcp) as client:
        first = await client.call_tool(
            "log",
            {
                "feature": "log-feat",
                "plan": _PLAN_STEM,
                "step": "S01",
                "rows": ["M:src/foo.py"],
            },
        )
        again = await client.call_tool(
            "log",
            {
                "feature": "log-feat",
                "plan": _PLAN_STEM,
                "step": "S01",
                "rows": ["M:src/foo.py"],
            },
        )

    summaries = [
        content.text
        for result in (first, again)
        for content in result.content
        if isinstance(content, TextContent)
    ]
    assert summaries[0].startswith("created: S01 -> ")
    assert summaries[0].endswith("(1 rows)")
    assert summaries[1].startswith("unchanged: S01 -> ")
