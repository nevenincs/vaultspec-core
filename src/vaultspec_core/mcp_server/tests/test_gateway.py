"""Tests for the discover/invoke gateway against the real installed binary.

Drives the gateway tools over the in-memory MCPServer client on a
:class:`WorkspaceFactory`-installed vault, with ``invoke`` spawning the real
``vaultspec-core`` module entry (``sys.executable -m vaultspec_core``) as an
argv-list subprocess - no mocks, stubs, or skips. Covers a read-only verb
returning parsed JSON, an unknown and a denylisted verb rejected before any
spawn, a non-zero exit folding stderr into the structured error payload,
reserved and unknown flag rejection, the ``discover`` ranking order, and a
reference stripped of its command-inventory markers refusing with
remediation text rather than a bare ``Error executing tool``.

The cancellation and timeout cases at the end exercise real children against
real pids: a cancelled call and a timed-out call must both reap the child
promptly rather than wait it out, and a ``notifications/cancelled`` sent over
the raw in-memory wire must leave its request unanswered.
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys
import time
from typing import TYPE_CHECKING, Any

import anyio
import pytest
from mcp import Client
from mcp.client._memory import InMemoryTransport
from mcp.server.mcpserver import MCPServer
from mcp.shared.message import SessionMessage
from mcp.types import (
    LATEST_PROTOCOL_VERSION,
    CallToolResult,
    JSONRPCNotification,
    JSONRPCRequest,
    TextContent,
)

from vaultspec_core.mcp_server.tools.gateway import (
    _child_environment,
    _load_catalog,
    _run_verb,
    register_gateway_tools,
)

from .conftest import data_of, vault_root
from .test_watchdog import _wait_for_pid_exit

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["vault_root"]

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _gateway_server() -> MCPServer[None]:
    """Build an MCPServer exposing only the two gateway tools.

    Registering onto a local instance exercises the gateway handlers in
    isolation end-to-end through the same session transport; the full
    nine-tool ``create_server`` wiring is covered by the surface test.
    """
    mcp = MCPServer(name="vaultspec-core-mcp-gateway-test")
    register_gateway_tools(mcp)
    return mcp


def _error_text(result: CallToolResult) -> str:
    """Concatenate the text content of a ``CallToolResult`` for assertions."""
    parts = [c.text for c in result.content if isinstance(c, TextContent)]
    return " ".join(parts).lower()


async def test_invoke_readonly_verb_returns_parsed_json(vault_root: Path) -> None:
    """A ``--json``-supporting read-only verb returns parsed structured data."""
    mcp = _gateway_server()
    async with Client(mcp) as client:
        result = await client.call_tool("invoke", {"verb": "vault list"})
        payload = data_of(result)
        assert payload["ok"] is True
        assert payload["exit_code"] == 0
        assert payload["format"] == "json"
        # The parsed payload is the real ``vault list`` envelope, not raw text.
        assert payload["data"]["schema"].startswith("vaultspec.vault.list")
        # Optional nulls are pruned from the wire, so an unset field is absent
        # rather than present-and-null; both read the same to a JSON consumer.
        assert payload.get("stdout") is None
        assert payload["command"][0] == "vaultspec-core"


async def test_invoke_unknown_verb_rejected_before_spawn(vault_root: Path) -> None:
    """An undeclared verb raises a protocol error and never spawns a process."""
    mcp = _gateway_server()
    async with Client(mcp) as client:
        result = await client.call_tool("invoke", {"verb": "totally bogus verb"})
        assert result.is_error
        text = _error_text(result)
        assert "unknown verb" in text


async def test_invoke_denied_verb_rejected_before_spawn(vault_root: Path) -> None:
    """Denylisted verbs are rejected before any spawn at the invoke boundary."""
    mcp = _gateway_server()
    async with Client(mcp) as client:
        for verb in ("uninstall", "vault feature index", "spec mcps add"):
            result = await client.call_tool("invoke", {"verb": verb})
            assert result.is_error, verb
            text = _error_text(result)
            assert "denylist" in text or "out of scope" in text, verb


async def test_invoke_nonzero_exit_folds_stderr(vault_root: Path) -> None:
    """A verb that runs and exits non-zero folds stderr into the error payload."""
    mcp = _gateway_server()
    async with Client(mcp) as client:
        # ``vault plan status`` requires a positional PATH; omitting it makes the
        # real binary exit non-zero with a usage error on stderr.
        result = await client.call_tool("invoke", {"verb": "vault plan status"})
        payload = data_of(result)
        assert payload["ok"] is False
        assert payload["exit_code"] != 0
        assert payload["error"]["kind"] == "nonzero_exit"
        assert payload["error"]["exit_code"] == payload["exit_code"]
        assert "missing argument" in payload["error"]["stderr"].lower()


async def test_invoke_reserved_flag_rejected(vault_root: Path) -> None:
    """A caller cannot shadow the server-managed ``--json`` / ``--target``."""
    mcp = _gateway_server()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "invoke", {"verb": "vault list", "arguments": {"json": True}}
        )
        assert result.is_error
        text = _error_text(result)
        assert "reserved" in text


async def test_invoke_unknown_flag_rejected(vault_root: Path) -> None:
    """An argument naming an undeclared flag is rejected before spawn."""
    mcp = _gateway_server()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "invoke", {"verb": "vault list", "arguments": {"nonesuch": "x"}}
        )
        assert result.is_error
        text = _error_text(result)
        assert "unknown flag" in text


async def test_invoke_value_flag_passed_through(vault_root: Path) -> None:
    """A declared value flag reaches the binary as a discrete argv item."""
    mcp = _gateway_server()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "invoke",
            {"verb": "vault list", "arguments": {"feature": "no-such-feature"}},
        )
        payload = data_of(result)
        assert payload["ok"] is True
        assert "--feature" in payload["command"]
        assert "no-such-feature" in payload["command"]


async def test_invoke_positional_verb_runs_end_to_end(vault_root: Path) -> None:
    """A verb needing a positional operand is callable via ``positionals``.

    ``vault add <DOC_TYPE> --feature <tag>`` needs the document type as an
    ordered positional; the gateway must place it in the operand slot ahead of
    the ``--feature`` flag and the injected ``--json`` for the real binary to
    scaffold the document and exit clean.
    """
    mcp = _gateway_server()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "invoke",
            {
                "verb": "vault add",
                "positionals": ["research"],
                "arguments": {"feature": "gateway-positional-probe"},
            },
        )
        payload = data_of(result)
        assert payload["ok"] is True, payload
        assert payload["exit_code"] == 0
        assert payload["format"] == "json"
        # The positional lands in the operand slot: right after the verb path
        # (which itself follows the injected --target) and before the flags.
        command = payload["command"]
        add_index = command.index("add")
        assert command[add_index - 1] == "vault"
        assert command[add_index + 1] == "research"
        feature_index = command.index("--feature")
        assert feature_index > add_index + 1
        # The verb really ran: a research document now exists for the feature.
        created = list(
            (vault_root / ".vault" / "research").glob("*gateway-positional-probe*.md")
        )
        assert created, "invoke did not scaffold the research document"


async def test_invoke_rejects_positional_for_argless_verb(vault_root: Path) -> None:
    """A positional supplied to a verb that declares none is rejected pre-spawn."""
    mcp = _gateway_server()
    async with Client(mcp) as client:
        # ``vault stats`` declares no positional arguments; a stray operand
        # is refused by catalog validation before any process spawns.
        result = await client.call_tool(
            "invoke", {"verb": "vault stats", "positionals": ["stray"]}
        )
        assert result.is_error
        text = _error_text(result)
        assert "no positional" in text


async def test_invoke_rejects_dash_leading_positional(vault_root: Path) -> None:
    """A ``-``-leading positional is refused pre-spawn, closing flag smuggling.

    ``vault add`` accepts a positional DOC_TYPE, but a positional that looks
    like an option (``--json``, ``-x``) would be parsed by Click as a flag, so
    the gateway must reject it before any process spawns rather than let a
    reserved or unknown flag ride in through the operand slot.
    """
    mcp = _gateway_server()
    async with Client(mcp) as client:
        for smuggled in ("--json", "-x", "--target"):
            result = await client.call_tool(
                "invoke",
                {
                    "verb": "vault add",
                    "positionals": [smuggled],
                    "arguments": {"feature": "dash-probe"},
                },
            )
            assert result.is_error, smuggled
            text = _error_text(result)
            assert "begins with '-'" in text or "must not look like options" in text, (
                smuggled,
                text,
            )
        # No document was scaffolded: the reserved flag never reached the binary.
        research = vault_root / ".vault" / "research"
        assert not list(research.glob("*dash-probe*.md"))


async def test_discover_returns_ranked_schemas(vault_root: Path) -> None:
    """``discover`` ranks a known verb first and returns its parameter schema."""
    mcp = _gateway_server()
    async with Client(mcp) as client:
        result = await client.call_tool("discover", {"query": "list vault documents"})
        payload = data_of(result)
        assert payload["count"] >= 1
        verbs = payload["verbs"]
        assert "vault list" in {v["verb"] for v in verbs}
        # Ranking is non-increasing by score.
        scores = [v["score"] for v in verbs]
        assert scores == sorted(scores, reverse=True)
        # The ranked entry carries its full flag schema for on-demand loading.
        vault_list = next(v for v in verbs if v["verb"] == "vault list")
        assert vault_list["supports_json"] is True
        assert "--feature" in {f["name"] for f in vault_list["flags"]}


async def test_discover_excludes_denylisted_verbs(vault_root: Path) -> None:
    """A denied verb never appears in discover results."""
    mcp = _gateway_server()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "discover", {"query": "feature index generate", "limit": 50}
        )
        payload = data_of(result)
        assert "vault feature index" not in {v["verb"] for v in payload["verbs"]}


async def test_unparseable_reference_refuses_with_remediation(
    vault_root: Path,
) -> None:
    """A reference stripped of its markers refuses with text the caller can act on.

    Issue #330 left this one open: the catalog parse failure is reachable from
    a tool call, but was raised as a bare ``ValueError``, so the caller got
    ``Error executing tool <name>`` and nothing else - and since every call
    fails identically until the install is repaired, blind retry never
    recovers. Both gateway tools must name the condition and the remedy.
    """
    reference = vault_root / ".vaultspec" / "reference" / "cli.md"
    assert reference.is_file()
    reference.write_text("# CLI reference\n\nNo inventory here.\n", encoding="utf-8")
    _load_catalog.cache_clear()

    mcp = _gateway_server()
    async with Client(mcp) as client:
        for tool, arguments in (
            ("discover", {"query": "vault list"}),
            ("invoke", {"verb": "vault list"}),
        ):
            result = await client.call_tool(tool, arguments)
            assert result.is_error, tool
            text = _error_text(result)
            assert "command-inventory markers" in text, tool
            assert "spec reference generate" in text, tool


async def test_invoke_rejects_the_editor_flag(vault_root: Path) -> None:
    """``--editor`` is refused for a gateway call even where a verb declares it.

    The gateway's other two screens both pass this flag by design: the
    positional guard sees no operand, and the flag-name guard sees a declared
    option. Neither ever looks at the value, which for this flag is a command
    the CLI would then execute. It is rejected by name instead, because a
    tool call has no terminal and therefore no legitimate use for it.
    """
    mcp = _gateway_server()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "invoke",
            {
                "verb": "spec rules edit",
                "positionals": ["some-rule"],
                "arguments": {"editor": "vim"},
            },
        )
        assert result.is_error
        text = _error_text(result)
        assert "not available through the gateway" in text


async def test_discover_withholds_the_editor_flag_from_schemas(
    vault_root: Path,
) -> None:
    """A blocked flag is not advertised as a parameter it could pass."""
    mcp = _gateway_server()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "discover", {"query": "spec rules edit", "limit": 20}
        )
        payload = data_of(result)
        edit_verbs = [v for v in payload["verbs"] if v["verb"].endswith("edit")]
        assert edit_verbs, "discover found no edit verb to inspect"
        for verb in edit_verbs:
            names = [flag["name"] for flag in verb.get("flags", [])]
            assert "--editor" not in names, verb["verb"]


async def test_invoke_marks_its_child_as_non_interactive(vault_root: Path) -> None:
    """A real spawned child refuses to open an editor, whatever is configured.

    This is the second, independent half of the closure and it is asserted
    end to end: the flag never leaves the handler, and even so the child that
    does start declines to launch an editor from *any* source - the config
    file, the environment, the built-in fallback. The refusal comes back as
    the verb's own stderr, so it is the real CLI answering, not this test
    inspecting the handler.

    The marker lives in the environment the gateway composes, and a caller's
    only channels into ``invoke`` are the verb path, the argument object and
    the positionals; none of them reach that mapping, so the distinction it
    draws cannot be spoofed from outside.
    """
    mcp = _gateway_server()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "invoke",
            {"verb": "spec rules edit", "positionals": ["any-rule-name"]},
        )
        payload = data_of(result)
        assert payload["ok"] is False
        assert "no terminal" in payload["error"]["stderr"].lower()


# ---------------------------------------------------------------------------
# cancellation and timeout
# ---------------------------------------------------------------------------

#: A child that outlives any test budget, so only the reap discipline ends it.
_SLEEPER_ARGV = [sys.executable, "-c", "import time; time.sleep(60)"]

_GATEWAY_LOGGER = "vaultspec_core.mcp_server.tools.gateway"
_PID_LINE = re.compile(r"invoke: child pid=(\d+)")

#: Wall-clock ceiling for a reap: terminate is immediate and the grace is 2s,
#: so anything approaching the child's own 60s lifetime means it was waited out
#: rather than killed.
_REAP_BUDGET = 15.0


def _logged_child_pid(caplog: pytest.LogCaptureFixture) -> int:
    """Return the pid the gateway logged for its spawned child.

    Liveness is asserted by pid rather than through the ``Process`` object,
    because the object reports what the parent believes while the pid reports
    what the OS still has.
    """
    for record in caplog.records:
        match = _PID_LINE.fullmatch(record.getMessage())
        if match:
            return int(match.group(1))
    raise AssertionError("the gateway logged no child pid")


async def _await_child_pid(
    caplog: pytest.LogCaptureFixture, timeout: float = 30.0
) -> int:
    """Wait until the gateway logs its child pid, then return it.

    Polling for the spawn rather than sleeping a fixed interval keeps the test
    honest on a slow machine: the cancel must arrive while the child is
    genuinely running, not before it started or after it was reaped.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for record in caplog.records:
            match = _PID_LINE.fullmatch(record.getMessage())
            if match:
                return int(match.group(1))
        await anyio.sleep(0.05)
    raise AssertionError("the gateway logged no child pid before the deadline")


async def test_run_verb_cancellation_reaps_the_child(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Cancelling the handler kills the child instead of leaking it.

    The blocking ``subprocess.run`` this replaced pinned the event loop for the
    child's whole lifetime, so a ``notifications/cancelled`` was not even read
    until the verb finished. The coroutine must instead take the cancellation
    at its next await, reap the child, and let ``CancelledError`` propagate -
    the SDK discards a cancelled handler's result, so there is nothing to
    return.
    """
    caplog.set_level(logging.INFO, logger=_GATEWAY_LOGGER)
    task = asyncio.ensure_future(_run_verb(_SLEEPER_ARGV, _child_environment(), 60.0))
    pid = await _await_child_pid(caplog)
    await asyncio.sleep(0.2)

    task.cancel()
    started = time.monotonic()
    with pytest.raises(asyncio.CancelledError):
        await task
    elapsed = time.monotonic() - started

    assert _wait_for_pid_exit(pid, 3.0), f"child {pid} survived cancellation"
    # The child sleeps far longer than this bound, so a reap that merely waited
    # it out would also leave the pid gone. Only the elapsed time separates
    # "killed" from "outlived", which is the whole point of the change.
    assert elapsed < _REAP_BUDGET, (
        f"cancellation took {elapsed:.1f}s; the child was waited out, not killed"
    )


async def test_run_verb_timeout_reaps_the_child(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The timeout path takes the same kill discipline as cancellation.

    Timeout and cancellation differ only in what follows the reap: the timeout
    raises for the handler to fold into the structured payload, where the
    cancellation re-raises and returns nothing.
    """
    caplog.set_level(logging.INFO, logger=_GATEWAY_LOGGER)
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        await _run_verb(_SLEEPER_ARGV, _child_environment(), 0.5)
    elapsed = time.monotonic() - started

    pid = _logged_child_pid(caplog)
    assert _wait_for_pid_exit(pid, 3.0), f"child {pid} survived the timeout"
    assert elapsed < _REAP_BUDGET, (
        f"timeout took {elapsed:.1f}s; the child was waited out, not killed"
    )


async def test_invoke_folds_a_timeout_into_the_structured_error(
    vault_root: Path,
) -> None:
    """A verb that outlives its budget returns the ``timeout`` error kind.

    A budget below interpreter startup makes the real binary miss it every
    time, so the folded payload is exercised without a contrived slow verb.
    """
    mcp = _gateway_server()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "invoke", {"verb": "vault list", "timeout": 0.01}
        )
        payload = data_of(result)
        assert payload["ok"] is False
        assert payload["exit_code"] == -1
        assert payload["error"]["kind"] == "timeout"
        assert payload["error"]["exit_code"] == -1


async def _send(stream: Any, message: Any) -> None:
    """Put one raw JSON-RPC message on the client's write stream."""
    await stream.send(SessionMessage(message=message))


def _wire_id(received: Any) -> Any:
    """Return the JSON-RPC id of one received wire item.

    The stream carries ``SessionMessage | Exception``; a transport failure is
    a test failure rather than something to skip past, so it is raised here.
    """
    if isinstance(received, Exception):
        raise received
    return getattr(received.message, "id", None)


async def _recv_id(stream: Any, request_id: int, timeout: float = 30.0) -> None:
    """Receive until the reply to *request_id* arrives."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with anyio.move_on_after(deadline - time.monotonic()):
            if _wire_id(await stream.receive()) == request_id:
                return
    raise AssertionError(f"no reply to request {request_id} arrived")


async def test_invoke_cancellation_over_the_protocol(
    vault_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A real ``notifications/cancelled`` stops a real ``invoke`` mid-flight.

    Driven over the raw in-memory wire rather than through ``Client`` so the
    request id is this test's own and the server's write stream can be
    inspected directly. That costs a dependency on a private SDK module; if a
    future SDK drops it, drive the same exchange through whatever public
    transport replaces it rather than deleting the test, because nothing else
    covers the whole path from a protocol cancellation to a dead child.

    The child's death is the assertion that discriminates. The unanswered
    request does not: the SDK discards any response to a cancelled id itself,
    so a handler that swallowed ``CancelledError`` and returned a result
    still leaves the wire silent - measured, not assumed. It is asserted
    anyway because a response appearing for a cancelled id would be a
    protocol violation worth catching, not because it proves this code
    cancels.
    """
    caplog.set_level(logging.INFO, logger=_GATEWAY_LOGGER)
    mcp = _gateway_server()
    async with InMemoryTransport(mcp) as (read_stream, write_stream):
        await _send(
            write_stream,
            JSONRPCRequest(
                jsonrpc="2.0",
                id=1,
                method="initialize",
                params={
                    "protocolVersion": LATEST_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "gateway-cancel-test", "version": "0"},
                },
            ),
        )
        await _recv_id(read_stream, 1)
        await _send(
            write_stream,
            JSONRPCNotification(jsonrpc="2.0", method="notifications/initialized"),
        )

        call_id = 2
        await _send(
            write_stream,
            JSONRPCRequest(
                jsonrpc="2.0",
                id=call_id,
                method="tools/call",
                params={"name": "invoke", "arguments": {"verb": "vault list"}},
            ),
        )
        pid = await _await_child_pid(caplog)
        await _send(
            write_stream,
            JSONRPCNotification(
                jsonrpc="2.0",
                method="notifications/cancelled",
                params={"requestId": call_id, "reason": "test cancellation"},
            ),
        )

        # Nothing may be written for the cancelled id. Draining for longer than
        # the verb needs to finish distinguishes "never answered" from "not
        # answered yet".
        with anyio.move_on_after(5.0):
            while True:
                assert _wire_id(await read_stream.receive()) != call_id, (
                    "the cancelled request was answered"
                )

        assert _wait_for_pid_exit(pid, 5.0), f"child {pid} survived the cancellation"
