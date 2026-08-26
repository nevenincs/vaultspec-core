"""Static conformance guard on how the tool modules raise refusals.

The MCP SDK reports every failure other than ``MCPError`` as a ``ToolError``
whose message begins ``Error executing tool <name>``; an anticipated failure -
one raised as ``ToolError`` - keeps its own text after that prefix, while
anything else becomes ``UnexpectedToolError`` and its message is discarded so a
crash cannot leak internals (``mcp/server/mcpserver/tools/base.py``).

Issue #330: seventeen deliberate refusals in ``mcp_server/tools/`` were raised
as bare ``ValueError``, so every one of them reached the client as the bare
string ``Error executing tool <name>``. The denylist and flag-smuggling guards
still refused correctly - no security property was bypassed - but a caller, and
an agent caller especially, could not learn *why*, leaving blind retry as the
only recovery. The refusals were fixed at the source; these tests stop the same
mistake being reintroduced the next time a refusal is added.

The rule this file enforces is a source rule, not a runtime one: no
``raise ValueError`` anywhere inside ``mcp_server/tools/``. Whether a given
raise would actually escape to the SDK is not statically decidable, so the ban
is drawn one level wider than the bug. A helper genuinely wanting value-error
semantics belongs in a lower layer (``catalog.py``, ``plan_resolver.py``, the
core packages), with the tool boundary translating it - the idiom ``plan.py``,
``orientation.py``, and ``gateway.py`` already use::

    try:
        ...
    except ValueError as exc:
        raise ToolError(str(exc)) from exc

The companion runtime test asserts the one refusal that #330 left open for a
decision - the catalog parse failure - now reaches the caller with its text.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from vaultspec_core.mcp_server import tools as tools_pkg
from vaultspec_core.mcp_server.catalog import CatalogParseError

pytestmark = [pytest.mark.unit]

#: The package whose refusal raises are constrained: every module here is a
#: tool boundary the SDK calls directly.
_TOOLS_DIR = Path(tools_pkg.__file__).parent

#: The remediation this failure points at, quoted in the guard message.
_GUIDANCE = (
    "Raise ToolError (from mcp.server.mcpserver.exceptions) instead, or move "
    "the ValueError into a lower layer and translate it at the tool boundary "
    "with 'raise ToolError(str(exc)) from exc'. See issue #330: the SDK "
    "discards the message of anything that is not a ToolError, so a bare "
    "ValueError reaches the client as 'Error executing tool <name>' and "
    "nothing else."
)


def _tool_modules() -> list[Path]:
    """Collect the tool modules the conformance rule applies to.

    Returns:
        Every ``.py`` file directly under ``mcp_server/tools/``, sorted so the
        parametrised ids are stable.
    """
    return sorted(_TOOLS_DIR.glob("*.py"))


def _value_error_raises(source: str) -> list[int]:
    """Find every ``raise ValueError(...)`` line in *source*.

    Matches both the bare name and a dotted spelling, with or without a call,
    so ``raise ValueError``, ``raise ValueError(msg)``, and
    ``raise builtins.ValueError(msg)`` are all caught.

    Args:
        source: The module source text to parse.

    Returns:
        The 1-based line numbers of the offending ``raise`` statements.
    """
    offenders: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        exc = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
        name = (
            exc.id
            if isinstance(exc, ast.Name)
            else exc.attr
            if isinstance(exc, ast.Attribute)
            else None
        )
        if name == "ValueError":
            offenders.append(node.lineno)
    return offenders


def test_tool_modules_exist() -> None:
    """The scan has something to scan - a silent empty glob would pass."""
    modules = _tool_modules()
    assert {path.name for path in modules} >= {
        "documents.py",
        "gateway.py",
        "orientation.py",
        "plan.py",
    }


@pytest.mark.parametrize("module", _tool_modules(), ids=lambda path: path.name)
def test_no_bare_value_error_raised_in_tool_modules(module: Path) -> None:
    """No tool module raises ``ValueError``; refusals must be ``ToolError``."""
    offenders = _value_error_raises(module.read_text(encoding="utf-8"))
    assert not offenders, (
        f"{module.name} raises ValueError at line(s) "
        f"{', '.join(str(line) for line in offenders)}. {_GUIDANCE}"
    )


def test_detector_catches_a_planted_value_error() -> None:
    """The detector fails on the shape it is meant to forbid.

    Without this the guard could silently degrade into an unconditional pass -
    an AST walk that matches nothing looks exactly like a clean tree.
    """
    planted = (
        "def refuse() -> None:\n"
        "    msg = 'nope'\n"
        "    raise ValueError(msg)\n"
        "\n"
        "def rethrow() -> None:\n"
        "    raise builtins.ValueError('nope')\n"
        "\n"
        "def bare() -> None:\n"
        "    raise ValueError\n"
    )
    assert _value_error_raises(planted) == [3, 6, 9]


def test_detector_ignores_tool_error_and_reraise() -> None:
    """The permitted idioms do not trip the guard."""
    permitted = (
        "def refuse() -> None:\n"
        "    raise ToolError('nope')\n"
        "\n"
        "def translate() -> None:\n"
        "    try:\n"
        "        inner()\n"
        "    except ValueError as exc:\n"
        "        raise ToolError(str(exc)) from exc\n"
        "\n"
        "def propagate() -> None:\n"
        "    try:\n"
        "        inner()\n"
        "    except ValueError:\n"
        "        raise\n"
    )
    assert _value_error_raises(permitted) == []


def test_catalog_parse_error_is_a_value_error() -> None:
    """The narrowed catalog failure stays a ``ValueError`` to indifferent callers.

    ``build_catalog`` is public and used outside the server; narrowing the raise
    so the gateway can translate exactly one condition must not change what any
    other caller catches.
    """
    assert issubclass(CatalogParseError, ValueError)
