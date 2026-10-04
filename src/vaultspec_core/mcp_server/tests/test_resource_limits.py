"""Resource-limit regressions against real files, children, and MCP calls."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from typing import TYPE_CHECKING

import pytest
from mcp import Client
from mcp.server.mcpserver.exceptions import ToolError

from vaultspec_core.core.document_io import (
    DocumentLimitError,
    document_budget_active,
    document_read_budget,
    read_document_bytes,
)
from vaultspec_core.graph import VaultGraph
from vaultspec_core.graph.cache import cache_path
from vaultspec_core.mcp_server.app import create_server
from vaultspec_core.mcp_server.tools.documents import (
    _DOCUMENT_FILE_BYTES,
    _FIND_RESPONSE_BYTES,
)
from vaultspec_core.mcp_server.tools.gateway import (
    _CAPTURE_BYTES,
    _MAX_TIMEOUT,
    OutputLimitError,
    _bounded_timeout,
    _child_environment,
    _run_verb,
)
from vaultspec_core.vaultcore.blob_hash import git_blob_oid

from .conftest import data_of
from .test_find_queries import _write_doc
from .test_gateway import _error_text, _gateway_server, _logged_child_pid
from .test_watchdog import _wait_for_pid_exit

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


@pytest.mark.parametrize("timeout", [0.0, -1.0, float("nan"), float("inf")])
async def test_invalid_timeout_never_spawns(
    timeout: float, caplog: pytest.LogCaptureFixture
) -> None:
    """Nonfinite and nonpositive deadlines cannot reach process creation."""
    caplog.set_level(logging.INFO, logger="vaultspec_core.mcp_server.tools.gateway")
    with pytest.raises(ToolError, match="finite and greater than zero"):
        await _run_verb(
            [sys.executable, "-c", "raise SystemExit(99)"],
            _child_environment(),
            timeout,
        )
    assert not any("child pid=" in record.getMessage() for record in caplog.records)


async def test_timeout_clamp_preserves_small_deadlines() -> None:
    """Huge finite requests clamp; the short-timeout contract stays intact."""
    assert _bounded_timeout(1e100) == _MAX_TIMEOUT
    assert _bounded_timeout(0.01) == 0.01


@pytest.mark.parametrize("streams", [(1,), (2,), (1, 2)])
async def test_output_overflow_reaps_child(
    streams: tuple[int, ...], caplog: pytest.LogCaptureFixture
) -> None:
    """Either pipe or their combined output stops a noisy, long-lived child."""
    caplog.set_level(logging.INFO, logger="vaultspec_core.mcp_server.tools.gateway")
    per_stream = _CAPTURE_BYTES // len(streams) + 1
    script = (
        "import os,time\n"
        f"for fd in {streams!r}:\n"
        f"    left = {per_stream}\n"
        "    while left:\n"
        "        left -= os.write(fd, b'x' * min(left, 16384))\n"
        "time.sleep(60)\n"
    )
    started = time.monotonic()
    with pytest.raises(OutputLimitError):
        await _run_verb([sys.executable, "-c", script], _child_environment(), 30)
    pid = _logged_child_pid(caplog)
    assert _wait_for_pid_exit(pid, 3), f"child {pid} survived output overflow"
    assert time.monotonic() - started < 15


async def test_exact_capture_limit_preserves_json() -> None:
    """A valid JSON stream exactly at the limit is complete and unmodified."""
    script = f"import sys\nsys.stdout.write('\"' + 'x' * {_CAPTURE_BYTES - 2} + '\"')\n"
    completed = await _run_verb(
        [sys.executable, "-c", script], _child_environment(), 30
    )
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert len(json.loads(completed.stdout)) == _CAPTURE_BYTES - 2


async def test_invoke_output_overflow_is_structured(vault_root: Path) -> None:
    """The real CLI's oversized JSON becomes an explicit output-limit error."""
    path = _write_doc(vault_root, "adr", "noisy", "2026-03-06")
    path.write_text(
        "---\ntags: ['#adr', '#noisy']\ndate: '"
        + "x" * (_CAPTURE_BYTES + 1)
        + "'\n---\n# Noisy\n",
        encoding="utf-8",
    )
    async with Client(_gateway_server()) as client:
        result = await client.call_tool("invoke", {"verb": "vault list"})
    payload = data_of(result)
    assert payload["ok"] is False
    assert payload["error"]["kind"] == "output_limit"
    assert len(result.model_dump_json().encode("utf-8")) < 2048


async def test_invoke_caps_response_below_capture_limit(vault_root: Path) -> None:
    """A completed verb's response has a separate serialized byte ceiling."""
    path = _write_doc(vault_root, "adr", "wide", "2026-03-06")
    path.write_text(
        "---\ntags: ['#adr', '#wide']\ndate: '" + "x" * 140_000 + "'\n---\n",
        encoding="utf-8",
    )
    async with Client(_gateway_server()) as client:
        result = await client.call_tool("invoke", {"verb": "vault list"})
    assert result.is_error
    assert "response exceeds" in _error_text(result)
    assert "tool already ran" in _error_text(result)


@pytest.mark.parametrize("body", ["none", "excerpt", "full"])
async def test_find_rejects_oversized_document_before_body_modes(
    vault_root: Path, body: str
) -> None:
    """Hash-only and excerpt reads obey the same limit as full bodies."""
    _write_doc(
        vault_root, "adr", "large", "2026-03-06", body="x" * _DOCUMENT_FILE_BYTES
    )
    async with Client(create_server()) as client:
        result = await client.call_tool(
            "find", {"type": ["adr"], "body": body, "limit": 1}
        )
    assert result.is_error
    assert "byte budget exceeded" in _error_text(result)


@pytest.mark.parametrize("enriched", [False, True])
async def test_feature_listing_has_the_same_file_budget(
    vault_root: Path, enriched: bool
) -> None:
    """Unfiltered and enriched feature modes cannot bypass document limits."""
    _write_doc(
        vault_root, "adr", "large", "2026-03-06", body="x" * _DOCUMENT_FILE_BYTES
    )
    async with Client(create_server()) as client:
        result = await client.call_tool("find", {"json": enriched})
    assert result.is_error
    assert "byte budget exceeded" in _error_text(result)


async def test_unselected_large_document_cannot_bypass_ingress(
    vault_root: Path,
) -> None:
    """A one-row search still bounds the graph's other documents."""
    _write_doc(vault_root, "adr", "small", "2026-03-06")
    _write_doc(
        vault_root,
        "research",
        "large",
        "2026-03-07",
        body="x" * _DOCUMENT_FILE_BYTES,
    )
    async with Client(create_server()) as client:
        result = await client.call_tool(
            "find", {"type": ["adr"], "feature": "small", "limit": 1}
        )
    assert result.is_error
    assert "byte budget exceeded" in _error_text(result)


async def test_find_caps_combined_response_and_keeps_excerpt_control(
    vault_root: Path,
) -> None:
    """Five individually small full bodies must still fit one byte budget."""
    for day in range(1, 6):
        _write_doc(
            vault_root, "adr", "combined", f"2026-03-{day:02d}", body="x" * 30_000
        )
    async with Client(create_server()) as client:
        full = await client.call_tool(
            "find", {"type": ["adr"], "feature": "combined", "body": "full", "limit": 5}
        )
        excerpt = await client.call_tool(
            "find",
            {"type": ["adr"], "feature": "combined", "body": "excerpt", "limit": 5},
        )
    assert full.is_error
    assert "response exceeds" in _error_text(full)
    assert len(data_of(excerpt)) == 5
    assert len(excerpt.model_dump_json().encode("utf-8")) <= _FIND_RESPONSE_BYTES


async def test_response_budget_counts_json_escaping(vault_root: Path) -> None:
    """Control-character escaping can exceed the cap despite small file bytes."""
    _write_doc(vault_root, "adr", "escaped", "2026-03-06", body="\t" * 70_000)
    async with Client(create_server()) as client:
        result = await client.call_tool(
            "find", {"type": ["adr"], "body": "full", "limit": 1}
        )
    assert result.is_error
    assert "response exceeds" in _error_text(result)


async def test_small_full_body_keeps_exact_hash_and_bytes(vault_root: Path) -> None:
    """Normal read/edit chaining and UTF-8 bodies retain their public fields."""
    path = _write_doc(vault_root, "adr", "normal", "2026-03-06", body="Hello 世界\n")
    raw = path.read_bytes()
    async with Client(create_server()) as client:
        result = await client.call_tool(
            "find", {"type": ["adr"], "feature": "normal", "body": "full", "limit": 1}
        )
    row = data_of(result)[0]
    assert row["blob_hash"] == git_blob_oid(raw)
    assert row["body"] == raw.decode("utf-8")
    assert row["body_bytes"] == len(raw)
    assert row["body_truncated"] is False


async def test_read_budget_is_aggregate_and_restored(tmp_path: Path) -> None:
    """Repeated reads count, exact limits pass, and scopes reset on failure."""
    path = tmp_path / "doc.md"
    path.write_bytes(b"12345678")
    with document_read_budget(8, 16):
        assert read_document_bytes(path) == b"12345678"
        assert read_document_bytes(path) == b"12345678"
        with pytest.raises(DocumentLimitError):
            read_document_bytes(path)
    assert not document_budget_active()
    assert read_document_bytes(path) == b"12345678"


async def test_budget_isolated_between_concurrent_requests(tmp_path: Path) -> None:
    """One request cannot spend another request's remaining bytes."""
    path = tmp_path / "doc.md"
    path.write_bytes(b"12345678")

    async def read_twice() -> None:
        with document_read_budget(8, 16):
            assert read_document_bytes(path) == b"12345678"
            await asyncio.sleep(0)
            assert read_document_bytes(path) == b"12345678"

    await asyncio.gather(read_twice(), read_twice())
    assert not document_budget_active()


async def test_graph_reads_cannot_bypass_budget_via_cache(vault_root: Path) -> None:
    """A warm graph cache cannot bypass aggregate ingestion limits."""
    path = _write_doc(vault_root, "adr", "cached", "2026-03-06", body="x" * 200)
    VaultGraph(vault_root)
    stored_cache = cache_path(vault_root)
    before = stored_cache.read_bytes()
    with (
        document_read_budget(_DOCUMENT_FILE_BYTES, 1),
        pytest.raises(DocumentLimitError),
    ):
        VaultGraph(vault_root)
    assert stored_cache.read_bytes() == before
    assert path.exists()
